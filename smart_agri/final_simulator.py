#!/usr/bin/env python3
"""
STM32 虚拟硬件仿真环境
功能：
1. 模拟 MQTT 客户端连接
2. 定时上报传感器数据
3. 响应控制指令
4. 提供 Web 监控页面
"""

import json
import random
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# 全局配置
DEVICE_ID = "A0001"
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
STATUS_TOPIC = f"farm/{DEVICE_ID}/status"
CONTROL_TOPIC = f"farm/{DEVICE_ID}/control"

# 模拟数据
current_sensor_data = {
    "id": DEVICE_ID,
    "t": 25.0,  # 温度
    "h": 60.0,  # 湿度
    "l": 5000,  # 光照
    "s": 0      # 执行器状态
}

last_command = {}  # 最后收到的指令

class MockMQTT:
    """模拟MQTT客户端"""
    def __init__(self):
        self.connected = False
    
    def connect(self, broker, port, keepalive):
        print(f"[MQTT] 连接到 {broker}:{port}")
        self.connected = True
    
    def subscribe(self, topic):
        print(f"[MQTT] 订阅主题: {topic}")
    
    def publish(self, topic, payload):
        print(f"[MQTT] 发布消息到 {topic}: {payload}")
    
    def loop_start(self):
        print("[MQTT] 启动消息循环")

def publish_sensor_data():
    """定时上报传感器数据"""
    mqtt = MockMQTT()
    mqtt.connect(MQTT_BROKER, MQTT_PORT, 60)
    mqtt.subscribe(CONTROL_TOPIC)
    mqtt.loop_start()
    
    while True:
        # 模拟数据变化
        current_sensor_data["t"] = round(20 + random.uniform(0, 10), 1)
        current_sensor_data["h"] = round(50 + random.uniform(0, 30), 1)
        current_sensor_data["l"] = random.randint(1000, 10000)
        
        # 发布数据
        payload = json.dumps(current_sensor_data)
        mqtt.publish(STATUS_TOPIC, payload)
        
        time.sleep(5)

class MonitorServer(BaseHTTPRequestHandler):
    """Web监控服务器"""
    def do_GET(self):
        if self.path == "/monitor":
            self.send_response(200)
            self.send_header("Content-type", "text/html; charset=utf-8")
            self.end_headers()
            
            html_template = """
            <!DOCTYPE html>
            <html>
            <head>
                <title>STM32 模拟器监控</title>
                <meta charset="UTF-8">
                <style>
                    body {{ font-family: monospace; margin: 20px; background: #f0f0f0; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                    h1 {{ color: #333; border-bottom: 2px solid #333; padding-bottom: 10px; }}
                    .section {{ margin: 20px 0; }}
                    .data {{ background: #f9f9f9; padding: 10px; border-radius: 4px; font-family: monospace; }}
                    .command {{ background: #e3f2fd; padding: 10px; border-radius: 4px; font-family: monospace; }}
                    .timestamp {{ color: #666; font-size: 0.9em; }}
                    form {{ margin-top: 10px; }}
                    input {{ margin: 5px 0; padding: 5px; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>STM32 模拟器监控</h1>
                    
                    <div class="section">
                        <h2>传感器数据</h2>
                        <div class="data">
                            <pre>{sensor_data}</pre>
                        </div>
                        <div class="timestamp">更新时间: {timestamp}</div>
                    </div>
                    
                    <div class="section">
                        <h2>最后指令</h2>
                        <div class="command">
                            <pre>{last_command}</pre>
                        </div>
                    </div>
                    
                    <div class="section">
                        <h2>MQTT 信息</h2>
                        <p>设备ID: {device_id}</p>
                        <p>状态主题: {status_topic}</p>
                        <p>控制主题: {control_topic}</p>
                        <p>服务器: {mqtt_broker}</p>
                    </div>
                    
                    <div class="section">
                        <h2>发送控制指令</h2>
                        <form action="/control" method="POST">
                            <label>指令码 (1=开启, 2=关闭, 3=调节):</label><br>
                            <input type="text" name="cmd" value="1"><br>
                            <label>目标设备:</label><br>
                            <input type="text" name="target" value="pump"><br>
                            <label>数值 (调节用):</label><br>
                            <input type="text" name="val" value="75"><br>
                            <input type="submit" value="发送指令">
                        </form>
                    </div>
                </div>
            </body>
            </html>
            """
            
            response = html_template.format(
                sensor_data=json.dumps(current_sensor_data, indent=2),
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                last_command=json.dumps(last_command, indent=2) if last_command else "无",
                device_id=DEVICE_ID,
                status_topic=STATUS_TOPIC,
                control_topic=CONTROL_TOPIC,
                mqtt_broker=MQTT_BROKER
            )
            
            self.wfile.write(response.encode())
        else:
            self.send_response(404)
            self.end_headers()
    
    def do_POST(self):
        if self.path == "/control":
            content_length = int(self.headers['Content-Length'])
            post_data = self.rfile.read(content_length).decode()
            
            # 解析表单数据
            params = {}
            for param in post_data.split('&'):
                key, value = param.split('=')
                params[key] = value
            
            # 处理指令
            global last_command
            last_command = params
            
            cmd = int(params.get("cmd", 0))
            target = params.get("target", "unknown")
            
            if cmd == 1:
                print(f"[STM32] 接收到串口指令，正在拉高引脚 PA5，开启{target}...")
            elif cmd == 2:
                print(f"[STM32] 接收到串口指令，正在拉低引脚 PA5，关闭{target}...")
            elif cmd == 3:
                val = params.get("val", 0)
                print(f"[STM32] 接收到串口指令，正在调节{target}至 {val}...")
            
            # 重定向回监控页面
            self.send_response(303)
            self.send_header("Location", "/monitor")
            self.end_headers()

def start_web_server():
    """启动Web服务器"""
    server = HTTPServer(('', 8000), MonitorServer)
    print("[Web] 服务器启动在 http://localhost:8000/monitor")
    server.serve_forever()

def main():
    """主函数"""
    print("[STM32 模拟器] 启动中...")
    
    # 启动数据上报线程
    publish_thread = threading.Thread(target=publish_sensor_data, daemon=True)
    publish_thread.start()
    
    # 启动Web服务器
    start_web_server()

if __name__ == "__main__":
    main()