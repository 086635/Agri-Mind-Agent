"""
设备治理层 (Device Governance Layer)
统一管理设备语义、Topic 生成和设备状态指令规范
"""
import os
from typing import Dict, Optional
from enum import Enum


class DeviceState(Enum):
    """设备状态枚举"""
    OFF = 0
    ON = 1
    ADJUST = 2


class DeviceManager:
    """
    设备管理器
    负责设备名称映射、Topic 生成、状态管理
    """
    
    def __init__(self):
        """初始化设备管理器"""
        # 从环境变量读取配置，如果没有则使用默认值
        self.base_topic = os.getenv("BASE_TOPIC", "farm")
        self.device_id = os.getenv("DEVICE_ID", "HD_STUDENT_001")
        
        # 中英文设备名称映射
        self._device_name_map: Dict[str, str] = {
            # 中文转英文
            "水泵": "pump",
            "泵": "pump",
            "风扇": "fan",
            "灯": "light",
            "补光灯": "light",
            # 英文保持原样
            "pump": "pump",
            "fan": "fan",
            "light": "light"
        }
        
        # 设备状态映射（指令码转状态）
        self._cmd_to_state: Dict[str, DeviceState] = {
            "1": DeviceState.ON,
            "2": DeviceState.OFF,
            "3": DeviceState.ADJUST
        }
        
        # 状态转指令码
        self._state_to_cmd: Dict[DeviceState, str] = {
            DeviceState.ON: "1",
            DeviceState.OFF: "2",
            DeviceState.ADJUST: "3"
        }
    
    def normalize_device_name(self, name: str) -> str:
        """
        标准化设备名称（中文转英文）
        
        Args:
            name: 设备名称（中文或英文）
            
        Returns:
            标准化的英文设备名称
        """
        return self._device_name_map.get(name, name)
    
    def get_device_display_name(self, name: str, use_chinese: bool = True) -> str:
        """
        获取设备显示名称
        
        Args:
            name: 设备名称
            use_chinese: 是否使用中文显示
            
        Returns:
            显示名称
        """
        normalized = self.normalize_device_name(name)
        
        if use_chinese:
            # 英文转中文
            reverse_map = {v: k for k, v in self._device_name_map.items() if len(k) > 1}
            return reverse_map.get(normalized, normalized)
        
        return normalized
    
    def generate_control_topic(self, device_name: Optional[str] = None) -> str:
        """
        生成控制 Topic
        
        Args:
            device_name: 设备名称（可选，默认使用全局 device_id）
            
        Returns:
            MQTT 控制 Topic
        """
        return f"{self.base_topic}/{self.device_id}/control"
    
    def generate_status_topic(self, device_name: Optional[str] = None) -> str:
        """
        生成状态上报 Topic
        
        Args:
            device_name: 设备名称（可选）
            
        Returns:
            MQTT 状态 Topic
        """
        return f"{self.base_topic}/{self.device_id}/status"
    
    def parse_command(self, cmd: str) -> DeviceState:
        """
        解析指令码为设备状态
        
        Args:
            cmd: 指令码字符串 ("1", "2", "3")
            
        Returns:
            DeviceState 枚举
        """
        return self._cmd_to_state.get(cmd, DeviceState.OFF)
    
    def state_to_command(self, state: DeviceState) -> str:
        """
        将设备状态转换为指令码
        
        Args:
            state: DeviceState 枚举
            
        Returns:
            指令码字符串
        """
        return self._state_to_cmd.get(state, "2")
    
    def is_valid_device(self, name: str) -> bool:
        """
        检查设备名称是否有效
        
        Args:
            name: 设备名称
            
        Returns:
            是否有效
        """
        normalized = self.normalize_device_name(name)
        return normalized in ["pump", "fan", "light"]
    
    def get_all_devices(self) -> Dict[str, str]:
        """
        获取所有设备的中英文名称映射
        
        Returns:
            设备映射字典 {英文名：中文名}
        """
        return {
            "pump": "水泵",
            "fan": "风扇",
            "light": "补光灯"
        }


# 全局单例
_device_manager: Optional[DeviceManager] = None


def get_device_manager() -> DeviceManager:
    """
    获取全局 DeviceManager 单例
    
    Returns:
        DeviceManager 实例
    """
    global _device_manager
    if _device_manager is None:
        _device_manager = DeviceManager()
    return _device_manager
