from fastapi import FastAPI
import uvicorn

app = FastAPI()

# 定义一个根路由
@app.get("/")
def read_root():
    return {"Hello": "Raspberry Pi", "Status": "Running"}

# 定义一个带参数的路由
@app.get("/items/{item_id}")
def read_item(item_id: int):
    return {"item_id": item_id, "platform": "Linux/ARM"}

if __name__ == "__main__":
    # 注意：这里直接运行 app 对象，host 设为 0.0.0.0 以便局域网访问
    # 端口改为 3001
    uvicorn.run(app, host="127.0.0.1", port=3000) 