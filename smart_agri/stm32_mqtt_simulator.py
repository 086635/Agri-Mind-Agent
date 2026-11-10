import asyncio
import json
import random
import time
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
import paho.mqtt.client as mqtt

# 全局变量
device_id = "A0001"
broker = "broker.emqx.io"
port = 1883
status_topic = f"farm/{device_id}/status"
control_topic = f"farm/{device_id}/control"

# 模拟传感器数据
current_sensor_data = {
    "id": device_id,
    "t": 25.0,
    "h": 60.0,
    "l": 5000,
    "s": 0
}

# 最后收到的指令
last_command = {}

# MQTT客户端
mqtt_client = mqtt.Client()

# FastAPI应用
app = FastAPI()

# MQTT回调函数
def on_connect(client, userdata, flags, rc):
    print(f"[STM32 模拟器] 连接到 MQTT 服务器: {rc}")
    client.subscribe(control_topic)
    print(f"[STM32 模拟器] 订阅控制频道: {control_topic}")

def on_message(client, userdata, msg):
    global last_command
    payload = msg.payload.decode()
    print(f"[STM32 模拟器] 收到消息: {msg.topic} -> {payload}")
    try:
        command = json.loads(payload)
        last_command = command
        # 处理指令
        if command.get("cmd") == 1:
            target = command.get("target", "unknown")
            print(f"[STM32 模拟器] 接收到串口指令，正在拉高引脚 PA5，开启{target}...")
        elif command.get("cmd") == 2:
            target = command.get("target", "unknown")
            print(f"[STM32 模拟器] 接收到串口指令，正在拉低引脚 PA5，关闭{target}...")
        elif command.get("cmd") == 3:
            target = command.get("target", "unknown")
            val = command.get("val", 0)
            print(f"[STM32 模拟器] 接收到串口指令，正在调节{target}至 {val}...")
    except json.JSONDecodeError:
        print(f"[STM32 模拟器] 无效的JSON数据: {payload}")

# 初始化MQTT客户端
def init_mqtt():
    mqtt_client.on_connect = on_connect
    mqtt_client.on_message = on_message
    mqtt_client.connect(broker, port, 60)
    mqtt_client.loop_start()

# 定时上报数据
async def publish_status():
    while True:
        # 模拟传感器数据变化
        current_sensor_data["t"] = round(20 + random.uniform(0, 10), 1)
        current_sensor_data["h"] = round(50 + random.uniform(0, 30), 1)
        current_sensor_data["l"] = random.randint(1000, 10000)
        
        payload = json.dumps(current_sensor_data)
        mqtt_client.publish(status_topic, payload)
        print(f"[STM32 模拟器] 上报状态: {payload}")
        await asyncio.sleep(5)

# FastAPI页面
@app.get("/monitor", response_class=HTMLResponse)
async def monitor():
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>STM32 模拟器监控</title>
        <style>
            body { font-family: monospace; margin: 20px; background-color: #f0f0f0; }
            .container { max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }
            h1 { color: #333; border-bottom: 2px solid #333; padding-bottom: 10px; }
            .section { margin: 20px 0; }
            .data { background: #f9f9f9; padding: 10px; border-radius: 4px; font-family: monospace; }
            .command { background: #e3f2fd; padding: 10px; border-radius: 4px; font-family: monospace; }
            .timestamp { color: #666; font-size: 0.9em; }
        </style>
    </head>
    <body>
        <div class="container">
            <h1>STM32 模拟器监控</h1>
            <div class="section">
                <h2>当前传感器数据</h2>
                <div class="data">
                    <pre>{}</pre>
                </div>
                <div class="timestamp">更新时间: {}</div>
            </div>
            <div class="section">
                <h2>最后收到的指令</h2>
                <div class="command">
                    <pre>{}</pre>
                </div>
            </div>
            <div class="section">
                <h2>MQTT 信息</h2>
                <p>设备ID: {}</p>
                <p>状态上报主题: {}</p>
                <p>控制订阅主题: {}</p>
                <p>MQTT 服务器: {}</p>
            </div>
        </div>
    </body>
    </html>
    """.format(
        json.dumps(current_sensor_data, indent=2),
        time.strftime("%Y-%m-%d %H:%M:%S"),
        json.dumps(last_command, indent=2) if last_command else "无",
        device_id,
        status_topic,
        control_topic,
        broker
    )

# 启动函数
@app.on_event("startup")
async def startup_event():
    print("[STM32 模拟器] 启动中...")
    init_mqtt()
    asyncio.create_task(publish_status())
    print("[STM32 模拟器] 启动完成！")
    print(f"[STM32 模拟器] Web监控页面: http://localhost:8000/monitor")

if __name__ == "__main__":
    try:
        import uvicorn
        print("[STM32 模拟器] 启动 uvicorn 服务器...")
        uvicorn.run(app, host="0.0.0.0", port=8000)
    except Exception as e:
        print(f"[STM32 模拟器] 启动失败: {e}")
        import traceback
        traceback.print_exc()