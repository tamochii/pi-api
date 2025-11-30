# app/main.py (基于你之前的代码修改)
import io
import time
from fastapi import FastAPI
from fastapi.responses import StreamingResponse, HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from picamera2 import Picamera2

# 1. 导入刚才写的电源管理类
from app.power import PowerManager 

app = FastAPI()

# 配置 CORS (保持不变)
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# --- 硬件初始化 ---
print("初始化摄像头...")
picam2 = Picamera2()
config = picam2.create_preview_configuration(
    main={"size": (640, 480), "format": "XRGB8888"},
    controls={"FrameRate": 30}
)
picam2.configure(config)
picam2.start()

# 2. 初始化电源管理器
print("启动电源监控...")
power_manager = PowerManager()
power_manager.start_monitoring() # 开始后台线程

# --- 视频流逻辑 (保持不变) ---
def generate_frames():
    while True:
        try:
            stream = io.BytesIO()
            picam2.capture_file(stream, format="jpeg")
            image_bytes = stream.getvalue()
            yield (b'--frame\r\n' b'Content-Type: image/jpeg\r\n\r\n' + image_bytes + b'\r\n')
        except Exception:
            time.sleep(0.1)

@app.get("/video_feed")
def video_feed():
    return StreamingResponse(generate_frames(), media_type="multipart/x-mixed-replace; boundary=frame")

# --- 3. 新增电源 API ---
@app.get("/api/power")
def get_power_stats():
    return power_manager.get_data()

@app.on_event("shutdown")
def shutdown_event():
    picam2.stop()
    # 这里的 power_manager 作为一个后台 daemon 线程，随主程序退出即可，不需要显式停止