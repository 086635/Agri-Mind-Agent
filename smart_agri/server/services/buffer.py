import numpy as np
from collections import defaultdict
import logging

# 配置日志输出
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 物理异常拦截阈值配置字典 (可根据你的蓝莓温室实际情况调整)
SENSOR_THRESHOLDS = {
    "air_temp": {"min": -20.0, "max": 60.0},
    "air_humi": {"min": 0.0, "max": 100.0},
    "air_lux": {"min": 0.0, "max": 200000.0},
    "co2": {"min": 0.0, "max": 5000.0},
    "soil_temp": {"min": -10.0, "max": 50.0},
    "soil_ec": {"min": 0.0, "max": 10.0},
    "soil_npk": {"min": 0.0, "max": 2000.0}
}

class DataBufferManager:
    def __init__(self):
        # 数据结构: { "device_id:sensor_type": [value1, value2, ...] }
        self._buffer = defaultdict(list)

    def _is_valid(self, sensor_type: str, value: float) -> bool:
        """物理常识拦截器"""
        limits = SENSOR_THRESHOLDS.get(sensor_type)
        if limits:
            return limits["min"] <= value <= limits["max"]
        return True # 如果未定义阈值，暂时放行

    def add_data(self, device_id: str, sensor_type: str, value: float):
        """接收高频数据录入内存"""
        if not self._is_valid(sensor_type, value):
            logger.warning(f"🚨 异常拦截: {device_id} 的 {sensor_type} 读数违背物理常识 ({value})，已丢弃。")
            return
        
        key = f"{device_id}:{sensor_type}"
        self._buffer[key].append(float(value))

    def get_and_clear_batch(self):
        """提取缓冲区数据并清空，应用中位数降频算子"""
        batch_to_save = []
        for key, values in self._buffer.items():
            if not values:
                continue
            
            device_id, sensor_type = key.split(":")
            # 降频核心：计算这段时间内的中位数 (Median)，相比平均值更能过滤突发尖峰
            median_value = float(np.median(values))
            
            batch_to_save.append({
                "device_id": device_id,
                "sensor_type": sensor_type,
                "raw_value": median_value
            })
            
        self._buffer.clear()
        return batch_to_save

# 实例化全局单例缓冲池
buffer_manager = DataBufferManager()