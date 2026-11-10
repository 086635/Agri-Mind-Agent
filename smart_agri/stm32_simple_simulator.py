import json
import random
import time
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler

# 全局变量
device_id = "HD_STUDENT_001"

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

# 模拟多个设备的状态
device_states = {
    "pump": 0,
    "fan": 0,
    "light": 0
}

# 处理IoT指令的函数
def process_iot_command(cmd, target):
    global device_states, current_sensor_data
    cmd_int = int(cmd)
    
    # 动态匹配设备名
    if target in device_states:
        device_states[target] = 1 if cmd_int == 1 else 0
        # 如果是水泵，关联到原来的 s 状态位，方便你之前的网页显示
        if target == "pump":
            current_sensor_data["s"] = device_states["pump"]
            
        print(f"--- [多设备反馈] 目标:{target} 动作:{'开启' if cmd_int==1 else '关闭'} ---")
    else:
        print(f"--- [警告] 收到未知设备指令: {target} ---")

# 真实的MQTT客户端处理
import paho.mqtt.client as mqtt

class RealMQTTClient:
    def __init__(self):
        self.client = mqtt.Client()
        self.client.on_connect = self.on_connect
        self.client.on_message = self.on_message
        print("[STM32 模拟器] 初始化真实 MQTT 客户端...")
    
    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            print("[STM32 模拟器] MQTT 连接成功")
            client.subscribe(control_topic)
            print(f"[STM32 模拟器] 订阅控制频道: {control_topic}")
        else:
            print(f"[STM32 模拟器] MQTT 连接失败，错误码: {rc}")
    
    def on_message(self, client, userdata, msg):
        print(f"[STM32 模拟器] 收到 MQTT 消息: {msg.topic} -> {msg.payload.decode()}")
        try:
            import json
            payload = json.loads(msg.payload.decode())
            # 兼容性处理：无论 AI 给的是 cmd 还是 action，都给它抓出来
            cmd = payload.get("cmd") or payload.get("action")
            target = payload.get("target") or "pump" # 如果没给 target，默认为水泵
            
            # 强制转换类型，确保 1 就能触发
            if cmd is not None:
                process_iot_command(cmd, target)
                global last_command
                last_command = {"cmd": str(cmd), "target": target, "src": "MQTT"}
        except Exception as e:
            print(f"[STM32 模拟器] 解析 MQTT 消息失败: {e}")
    
    def connect(self, broker, port, keepalive):
        print(f"[STM32 模拟器] 连接到 MQTT 服务器: {broker}:{port}")
        try:
            self.client.connect(broker, port, keepalive)
            return True
        except Exception as e:
            print(f"[STM32 模拟器] 连接失败: {e}")
            return False
    
    def loop_start(self):
        print("[STM32 模拟器] 启动 MQTT 循环...")
        self.client.loop_start()
    
    def publish(self, topic, payload):
        print(f"[STM32 模拟器] 上报状态: {payload}")
        try:
            self.client.publish(topic, payload)
        except Exception as e:
            print(f"[STM32 模拟器] 发布消息失败: {e}")
    
    # 新增这个函数，用来转发订阅请求给真正的 client
    def subscribe(self, topic):
        print(f"[STM32 模拟器] 正在订阅主题: {topic}")
        self.client.subscribe(topic)

# 初始化真实MQTT客户端
status_topic = f"farm/{device_id}/status"
control_topic = f"farm/{device_id}/control"
mqtt_client = RealMQTTClient()

# 定时上报数据
def publish_status():
    while True:
        # 模拟传感器数据变化
        current_sensor_data["t"] = round(20 + random.uniform(0, 10), 1)
        current_sensor_data["h"] = round(50 + random.uniform(0, 30), 1)
        current_sensor_data["l"] = random.randint(1000, 10000)
        
        payload = json.dumps(current_sensor_data)
        mqtt_client.publish(status_topic, payload)
        time.sleep(5)

# HTTP服务器处理类
class MonitorHandler(BaseHTTPRequestHandler):
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
                <meta http-equiv="refresh" content="3">
                <style>
                    body {{ font-family: monospace; margin: 20px; background-color: #f0f0f0; }}
                    .container {{ max-width: 600px; margin: 0 auto; background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
                    h1 {{ color: #333; border-bottom: 2px solid #333; padding-bottom: 10px; }}
                    .section {{ margin: 20px 0; }}
                    .data {{ background: #f9f9f9; padding: 10px; border-radius: 4px; font-family: monospace; }}
                    .command {{ background: #e3f2fd; padding: 10px; border-radius: 4px; font-family: monospace; }}
                    .timestamp {{ color: #666; font-size: 0.9em; }}
                </style>
            </head>
            <body>
                <div class="container">
                    <h1>STM32 模拟器监控</h1>
                    <div class="section">
                        <h2>当前传感器数据</h2>
                        <div class="data">
                            <pre>{sensor_data}</pre>
                        </div>
                        <div class="timestamp">更新时间: {timestamp}</div>
                    </div>
                    <div class="section">
                        <h2>设备实时状态</h2>
                        <div class="data">
                            <p>💧 水泵状态: <b>{pump_status}</b></p>
                            <p>🌀 风扇状态: <b>{fan_status}</b></p>
                            <p>💡 补光灯状态: <b>{light_status}</b></p>
                        </div>
                    </div>
                    <div class="section">
                        <h2>最后收到的指令</h2>
                        <div class="command">
                            <pre>{last_command}</pre>
                        </div>
                    </div>
                    <div class="section">
                        <h2>MQTT 信息</h2>
                        <p>设备ID: {device_id}</p>
                        <p>状态上报主题: {status_topic}</p>
                        <p>控制订阅主题: {control_topic}</p>
                        <p>MQTT 服务器: broker.emqx.io</p>
                    </div>
                    <div class="section">
                        <h2>模拟控制测试</h2>
                        <form action="/control" method="POST">
                            <label>指令码 (1=开启, 2=关闭, 3=调节):</label>
                            <input type="text" name="cmd" value="1"><br>
                            <label>目标设备:</label>
                            <input type="text" name="target" value="pump"><br>
                            <label>数值 (仅调节时使用):</label>
                            <input type="text" name="val" value="75"><br>
                            <input type="submit" value="发送指令">
                        </form>
                    </div>
                </div>
            </body>
            </html>
            """
            
            html = html_template.format(
                sensor_data=json.dumps(current_sensor_data, indent=2, ensure_ascii=False),
                device_states=json.dumps(device_states, indent=2, ensure_ascii=False),
                timestamp=time.strftime("%Y-%m-%d %H:%M:%S"),
                last_command=json.dumps(last_command, indent=2, ensure_ascii=False) if last_command else "无",
                device_id=device_id,
                status_topic=status_topic,
                control_topic=control_topic,
                pump_status="开启 (ON)" if device_states["pump"]==1 else "关闭 (OFF)",
                fan_status="开启 (ON)" if device_states["fan"]==1 else "关闭 (OFF)",
                light_status="开启 (ON)" if device_states["light"]==1 else "关闭 (OFF)"
            )
            self.wfile.write(html.encode())
        elif self.path == "/ping":
            self.send_response(200)
            self.send_header("Content-type", "application/json")
            self.end_headers()
            response = {"status": "pong"}
            self.wfile.write(json.dumps(response).encode())
        elif self.path == "/control":
            self.send_response(303)
            self.send_header("Location", "/monitor")
            self.end_headers()
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
            process_iot_command(params.get("cmd"), params.get("target"))
            
            # 更新最后指令
            global last_command
            last_command = params
            
            self.send_response(303)
            self.send_header("Location", "/monitor")
            self.end_headers()

# 启动HTTP服务器
def start_http_server():
    server_address = ('', 8000)
    httpd = HTTPServer(server_address, MonitorHandler)
    print(f"[STM32 模拟器] Web服务器启动在 http://localhost:8000/monitor")
    httpd.serve_forever()

# 主函数
def main():
    print("[STM32 模拟器] 启动中...")
    
    # 初始化MQTT
    mqtt_client.connect("broker.emqx.io", 1883, 60)
    mqtt_client.subscribe(control_topic)
    mqtt_client.loop_start()
    
    # 启动数据上报线程
    publish_thread = threading.Thread(target=publish_status, daemon=True)
    publish_thread.start()
    
    # 启动HTTP服务器
    start_http_server()

if __name__ == "__main__":
    main()