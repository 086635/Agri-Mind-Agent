import paho.mqtt.client as mqtt
import asyncio
from typing import Optional, Any

class AsyncMQTTWrapper:
    """
    MQTT客户端的异步封装
    使用asyncio.Queue作为指令缓冲区，实现生产者-消费者模型
    """
    
    def __init__(self, broker: str, port: int = 1883, client_id: Optional[str] = None):
        self.broker = broker
        self.port = port
        self.client_id = client_id
        
        self.client = mqtt.Client(client_id=client_id)
        
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        
        self.client.reconnect_delay_set(min_delay=1, max_delay=120)
        
        self.queue = asyncio.Queue(maxsize=100)
        
        self.running = False
        self.connected = False
        self.consumer_task = None
    
    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: dict, rc: int):
        if rc == 0:
            print("[AsyncMQTT] 连接成功")
            self.connected = True
        else:
            print(f"[AsyncMQTT] 连接失败，错误码: {rc}")
            self.connected = False
    
    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int):
        print(f"[AsyncMQTT] 连接断开，错误码: {rc}")
        print("[AsyncMQTT] 正在尝试重连...")
        self.connected = False
    
    async def connect(self):
        try:
            self.client.connect(self.broker, self.port, 60)
            self.client.loop_start()
            print("[AsyncMQTT] 客户端初始化成功，开始监听连接状态")
            
            for _ in range(10):
                if self.connected:
                    break
                await asyncio.sleep(0.5)
            
            return self.connected
        except Exception as e:
            print(f"[AsyncMQTT] 连接超时或失败: {e}")
            print("[AsyncMQTT] 将在后台继续尝试重连")
            self.client.loop_start()
            return False
    
    async def disconnect(self):
        try:
            await self.stop()
            self.client.disconnect()
            self.client.loop_stop()
            print("[AsyncMQTT] 连接已断开")
            return True
        except Exception as e:
            print(f"[AsyncMQTT] 断开连接失败: {e}")
            return False
    
    async def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False):
        await self.queue.put((topic, payload, qos, retain))
    
    async def _process_queue(self):
        while self.running:
            try:
                try:
                    topic, payload, qos, retain = await asyncio.wait_for(self.queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    continue
                
                if self.connected:
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self.client.publish, topic, payload, qos, retain)
                    print(f"[AsyncMQTT] 消息已发布到 {topic}")
                else:
                    print(f"[AsyncMQTT] 未连接，无法发布消息到 {topic}")
                
                self.queue.task_done()
            except asyncio.CancelledError:
                break
            except Exception as e:
                print(f"[AsyncMQTT] 处理消息失败: {e}")
                try:
                    self.queue.task_done()
                except:
                    pass
            
            await asyncio.sleep(0.01)
    
    async def start(self):
        if not self.running:
            self.running = True
            self.consumer_task = asyncio.create_task(self._process_queue())
            print("[AsyncMQTT] 消费者循环已启动")
    
    async def stop(self):
        if self.running:
            self.running = False
            if self.consumer_task:
                await self.consumer_task
                self.consumer_task = None
            await self.queue.join()
            print("[AsyncMQTT] 消费者循环已停止，所有消息处理完毕")
    
    def is_connected(self) -> bool:
        return self.connected
