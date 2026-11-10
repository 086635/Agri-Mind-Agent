import json
import paho.mqtt.client as mqtt
import time
import os
import sys
import asyncio

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.dirname(__file__)))
from database_manager import db_manager

# MQTT配置
MQTT_BROKER = "broker.emqx.io"
MQTT_PORT = 1883
MQTT_TOPIC = "farm/+/status"

# 初始化数据库
async def init_db():
    """
    初始化数据库，创建表结构
    """
    try:
        # 使用db_manager进行初始化
        await db_manager.connect()
        print("[Storage] 数据库初始化成功")
    except Exception as e:
        print(f"[Storage] 数据库初始化失败: {e}")

# 保存数据到数据库
async def save_to_db(data):
    """
    保存传感器数据到数据库
    """
    try:
        # 使用异步数据库操作
        await db_manager.execute('''
        INSERT INTO sensor_history (device_id, temp, humid, light, soil_status)
        VALUES (?, ?, ?, ?, ?)
        ''', (
            data.get('id'),
            data.get('t'),
            data.get('h'),
            data.get('l'),
            data.get('s')
        ))
        await db_manager.commit()
        
        # 打印日志
        print(f"[Storage] 已固化来自 {data.get('id')} 的数据: {data.get('t')}℃")
    except Exception as e:
        print(f"[Storage] 数据保存失败: {e}")

# 全局事件循环
loop = None

# MQTT消息回调
def on_message(client, userdata, msg):
    """
    处理收到的MQTT消息
    """
    try:
        # 解析消息 payload
        payload = json.loads(msg.payload.decode())
        
        # 验证数据格式
        if 'id' in payload and 't' in payload and 'h' in payload and 'l' in payload and 's' in payload:
            # 异步保存数据到数据库
            if loop:
                asyncio.run_coroutine_threadsafe(save_to_db(payload), loop)
        else:
            print(f"[Storage] 数据格式不正确: {payload}")
    except json.JSONDecodeError:
        print(f"[Storage] JSON解析失败: {msg.payload.decode()}")
    except Exception as e:
        print(f"[Storage] 处理消息失败: {e}")

# MQTT连接回调
def on_connect(client, userdata, flags, rc):
    """
    MQTT连接成功回调
    """
    if rc == 0:
        print("[Storage] MQTT连接成功")
        # 订阅主题
        client.subscribe(MQTT_TOPIC)
        print(f"[Storage] 已订阅主题: {MQTT_TOPIC}")
    else:
        print(f"[Storage] MQTT连接失败，错误码: {rc}")

# 主函数
async def main():
    """
    主函数
    """
    global loop
    # 获取事件循环
    loop = asyncio.get_event_loop()
    
    # 初始化数据库
    await init_db()
    
    # 创建MQTT客户端
    client = mqtt.Client()
    
    # 设置回调函数
    client.on_connect = on_connect
    client.on_message = on_message
    
    # 连接MQTT服务器
    print(f"[Storage] 连接到MQTT服务器: {MQTT_BROKER}:{MQTT_PORT}")
    try:
        client.connect(MQTT_BROKER, MQTT_PORT, 60)
        # 启动非阻塞监听
        client.loop_start()
        print("[Storage] 开始监听传感器数据...")
        
        # 保持运行
        while True:
            await asyncio.sleep(1)
    except Exception as e:
        print(f"[Storage] 启动失败: {e}")
    finally:
        client.loop_stop()

if __name__ == "__main__":
    asyncio.run(main())
