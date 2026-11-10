from typing import Dict, Optional, Any
from device_manager import get_device_manager

class SystemPrompt:
    """
    系统提示模板引擎
    支持动态注入传感器数据、设备状态和格式指令
    """
    
    def __init__(self):
        """
        初始化系统提示模板
        """
        self.device_manager = get_device_manager()
        self.base_template = """
你是一个智能农场控制助手，负责理解用户指令并生成合适的控制命令。

# 农场实时状态
{farm_status}

# 设备状态
{device_status}

# 任务要求
1. 分析用户指令和当前农场状态
2. 生成控制命令或回答用户问题
3. 严格按照指定格式输出结果

# 输出格式要求
请按照以下JSON格式输出结果：
{{
  "type": "control" | "qa",
  "text": "给用户的回复",
  "payload": {{
    "target": "设备名称",
    "cmd": "指令码"
  }} | null
}}

注意：
- type为"control"时，payload不能为空
- type为"qa"时，payload必须为null
- 设备名称必须使用英文（pump、fan、light）
- 指令码为"1"表示开启，"2"表示关闭

# 响应示例
示例 1 (查询):
{{ "type": "qa", "text": "当前温度为 25℃，非常舒适。", "payload": null }}

示例 2 (控制):
{{ "type": "control", "text": "好的，正在为您开启水泵。", "payload": {{ "target": "pump", "cmd": "1" }} }}

用户指令：{user_command}
        """
    
    def build(self, user_command: str, sensor_data: Optional[Dict[str, Any]] = None) -> str:
        """
        构建系统提示
        
        Args:
            user_command: 用户指令
            sensor_data: 传感器数据（可选）
            
        Returns:
            构建好的系统提示字符串
        """
        # 构建农场状态部分
        farm_status = self._build_farm_status(sensor_data)
        
        # 构建设备状态部分
        device_status = self._build_device_status()
        
        # 填充模板
        prompt = self.base_template.format(
            farm_status=farm_status,
            device_status=device_status,
            user_command=user_command
        )
        
        return prompt
    
    def _build_farm_status(self, sensor_data: Optional[Dict[str, Any]]) -> str:
        """
        构建农场状态部分
        
        Args:
            sensor_data: 传感器数据
            
        Returns:
            农场状态字符串
        """
        if not sensor_data:
            return "暂无传感器数据"
        
        status_lines = []
        status_lines.append("传感器数据：")
        
        if "temp" in sensor_data:
            status_lines.append(f"- 温度: {sensor_data['temp']}℃")
        if "humid" in sensor_data:
            status_lines.append(f"- 湿度: {sensor_data['humid']}%")
        if "light" in sensor_data:
            status_lines.append(f"- 光照: {sensor_data['light']} lux")
        if "soil_status" in sensor_data:
            soil_status = "湿润" if sensor_data['soil_status'] == 1 else "干燥"
            status_lines.append(f"- 土壤状态: {soil_status}")
        if "timestamp" in sensor_data:
            status_lines.append(f"- 更新时间: {sensor_data['timestamp']}")
        
        return "\n".join(status_lines)
    
    def _build_device_status(self) -> str:
        """
        构建设备状态部分
        
        Returns:
            设备状态字符串
        """
        devices = self.device_manager.get_all_devices()
        
        status_lines = []
        status_lines.append("可用设备：")
        
        for device_en, device_cn in devices.items():
            status_lines.append(f"- {device_cn} ({device_en})")
        
        status_lines.append("\n控制指令：")
        status_lines.append("- 开启设备：指令码 1")
        status_lines.append("- 关闭设备：指令码 2")
        
        return "\n".join(status_lines)

# 全局实例
prompt_engine = SystemPrompt()
