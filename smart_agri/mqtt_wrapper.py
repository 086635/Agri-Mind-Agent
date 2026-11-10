import paho.mqtt.client as mqtt
import asyncio
from typing import Optional, Any

class AsyncMQTTWrapper:
    """
    MQTT客户端的异步封装
    使用asyncio.Queue作为指令缓冲区，实现生产者-消费者模型
    """
    
    def __init__(self, broker: str, port: int = 1883, client_id: Optional[str] = None):
        """
        初始化AsyncMQTTWrapper
        
        Args:
            broker: MQTT broker地址
            port: MQTT broker端口
            client_id: 客户端ID
        """
        self.broker = broker
        self.port = port
        self.client_id = client_id
        
        # 创建paho-mqtt客户端
        self.client = mqtt.Client(client_id=client_id)
        
        # 设置回调函数
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        
        # 配置自动重连
        self.client.reconnect_delay_set(min_delay=1, max_delay=120)
        
        # 创建消息队列，设置最大容量为100
        self.queue = asyncio.Queue(maxsize=100)
        
        # 运行状态
        self.running = False
        self.connected = False
        self.consumer_task = None
    
    def _on_connect(self, client: mqtt.Client, userdata: Any, flags: dict, rc: int):
        """
        MQTT连接回调
        
        Args:
            client: MQTT客户端
            userdata: 用户数据
            flags: 连接标志
            rc: 连接结果码
        """
        if rc == 0:
            print("[AsyncMQTT] 连接成功")
            self.connected = True
        else:
            print(f"[AsyncMQTT] 连接失败，错误码: {rc}")
            self.connected = False
    
    def _on_disconnect(self, client: mqtt.Client, userdata: Any, rc: int):
        """
        MQTT断开连接回调
        
        Args:
            client: MQTT客户端
            userdata: 用户数据
            rc: 断开结果码
        """
        print(f"[AsyncMQTT] 连接断开，错误码: {rc}")
        print("[AsyncMQTT] 正在尝试重连...")
        self.connected = False
    
    async def connect(self):
        """
        连接到MQTT broker
        """
        try:
            # 尝试连接
            self.client.connect(self.broker, self.port, 60)
            # 启动客户端循环
            self.client.loop_start()
            print("[AsyncMQTT] 客户端初始化成功，开始监听连接状态")
            
            # 等待连接成功
            for _ in range(10):
                if self.connected:
                    break
                await asyncio.sleep(0.5)
            
            return self.connected
        except Exception as e:
            print(f"[AsyncMQTT] 连接超时或失败: {e}")
            print("[AsyncMQTT] 将在后台继续尝试重连")
            # 即使连接失败，也要启动loop，这样才能自动重连
            self.client.loop_start()
            return False
    
    async def disconnect(self):
        """
        断开MQTT连接
        """
        try:
            # 停止消费者任务
            await self.stop()
            # 断开连接
            self.client.disconnect()
            # 停止客户端循环
            self.client.loop_stop()
            print("[AsyncMQTT] 连接已断开")
            return True
        except Exception as e:
            print(f"[AsyncMQTT] 断开连接失败: {e}")
            return False
    
    async def publish(self, topic: str, payload: str, qos: int = 0, retain: bool = False):
        """
        发布MQTT消息
        
        Args:
            topic: 主题
            payload: 消息内容
            qos: 服务质量
            retain: 是否保留消息
        """
        # 将消息放入队列
        await self.queue.put((topic, payload, qos, retain))
    
    async def _process_queue(self):
        """
        处理队列中的消息
        """
        while self.running:
            try:
                # 从队列中获取消息，设置超时
                try:
                    topic, payload, qos, retain = await asyncio.wait_for(self.queue.get(), timeout=0.1)
                except asyncio.TimeoutError:
                    continue
                
                # 检查连接状态
                if self.connected:
                    # 发布消息（非阻塞）
                    loop = asyncio.get_event_loop()
                    await loop.run_in_executor(None, self.client.publish, topic, payload, qos, retain)
                    print(f"[AsyncMQTT] 消息已发布到 {topic}")
                else:
                    print(f"[AsyncMQTT] 未连接，无法发布消息到 {topic}")
                
                # 标记任务完成
                self.queue.task_done()
            except asyncio.CancelledError:
                # 任务被取消，退出循环
                break
            except Exception as e:
                print(f"[AsyncMQTT] 处理消息失败: {e}")
                # 标记任务完成
                try:
                    self.queue.task_done()
                except:
                    pass
            
            # 短暂休眠，避免CPU占用过高
            await asyncio.sleep(0.01)
    
    async def start(self):
        """
        启动消费者循环
        """
        if not self.running:
            self.running = True
            # 创建并启动消费者任务
            self.consumer_task = asyncio.create_task(self._process_queue())
            print("[AsyncMQTT] 消费者循环已启动")
    
    async def stop(self):
        """
        停止消费者循环
        """
        if self.running:
            self.running = False
            # 等待消费者任务完成
            if self.consumer_task:
                await self.consumer_task
                self.consumer_task = None
            # 等待队列中所有消息处理完毕
            await self.queue.join()
            print("[AsyncMQTT] 消费者循环已停止，所有消息处理完毕")
    
    def is_connected(self) -> bool:
        """
        检查MQTT连接状态
        
        Returns:
            是否连接
        """
        return self.connected
