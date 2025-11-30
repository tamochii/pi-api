# app/power.py
import smbus
import time
import os
import threading

class PowerManager:
    def __init__(self):
        self.ADDR = 0x2d
        self.LOW_VOL = 3150  # mV
        self.bus = smbus.SMBus(1)
        self.low_count = 0
        
        # 用于存储最新的电池数据，供API读取
        self.latest_data = {
            "status": "Unknown",
            "vbus_voltage": 0,
            "vbus_current": 0,
            "battery_voltage": 0,
            "battery_percent": 0,
            "is_low_power": False,
            "shutdown_countdown": -1
        }
        
        # 线程锁，防止读写冲突
        self.lock = threading.Lock()
        self.running = False

    def read_hardware(self):
        """
        读取硬件数据的核心逻辑（原代码的改造版）
        """
        try:
            # 1. 读取充电状态
            data = self.bus.read_i2c_block_data(self.ADDR, 0x02, 0x01)
            state = "Idle"
            if data[0] & 0x40: state = "Fast Charging"
            elif data[0] & 0x80: state = "Charging"
            elif data[0] & 0x20: state = "Discharging"

            # 2. VBUS 信息
            data = self.bus.read_i2c_block_data(self.ADDR, 0x10, 0x06)
            vbus_vol = data[0] | data[1] << 8
            vbus_cur = data[2] | data[3] << 8
            vbus_pow = data[4] | data[5] << 8

            # 3. 电池信息
            data = self.bus.read_i2c_block_data(self.ADDR, 0x20, 0x0C)
            bat_vol = data[0] | data[1] << 8
            bat_cur = (data[2] | data[3] << 8)
            if bat_cur > 0x7FFF: bat_cur -= 0xFFFF
            bat_pct = int(data[4] | data[5] << 8)
            
            # 计算剩余时间
            if bat_cur < 0:
                time_str = f"Empty in {data[8] | data[9] << 8} min"
            else:
                time_str = f"Full in {data[10] | data[11] << 8} min"

            # 4. 电芯电压 (用于低电量判断)
            data = self.bus.read_i2c_block_data(self.ADDR, 0x30, 0x08)
            v1 = (data[0] | data[1] << 8)
            v2 = (data[2] | data[3] << 8)
            v3 = (data[4] | data[5] << 8)
            v4 = (data[6] | data[7] << 8)

            # --- 低电量关机逻辑 ---
            shutdown_timer = -1
            if ((v1 < self.LOW_VOL) or (v2 < self.LOW_VOL) or (v3 < self.LOW_VOL) or (v4 < self.LOW_VOL)) and (bat_cur < 50):
                self.low_count += 1
                shutdown_timer = 60 - 2 * self.low_count
                
                if self.low_count >= 30:
                    print("System shutdown initiated due to low battery.")
                    # 发送关机指令
                    os.popen("i2cset -y 1 0x2d 0x01 0x55")
                    os.system("sudo poweroff")
            else:
                self.low_count = 0

            # 更新共享数据
            new_data = {
                "status": state,
                "vbus_voltage_mv": vbus_vol,
                "vbus_current_ma": vbus_cur,
                "battery_voltage_mv": bat_vol,
                "battery_current_ma": bat_cur,
                "battery_percent": bat_pct,
                "time_info": time_str,
                "cells": [v1, v2, v3, v4],
                "warning": "Low Battery" if self.low_count > 0 else "Normal",
                "shutdown_in_seconds": shutdown_timer if self.low_count > 0 else None
            }

            with self.lock:
                self.latest_data = new_data

        except Exception as e:
            print(f"Power read error: {e}")

    def start_monitoring(self):
        """启动后台线程"""
        self.running = True
        t = threading.Thread(target=self._loop, daemon=True)
        t.start()

    def _loop(self):
        while self.running:
            self.read_hardware()
            time.sleep(2) # 每2秒刷新一次

    def get_data(self):
        """API调用的方法"""
        with self.lock:
            return self.latest_data