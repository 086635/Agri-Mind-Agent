import pandas as pd
from datetime import datetime
from typing import List, Tuple, Optional

class DeviceDiagnosticsAnalytics:
    """
    设备诊断算法工具包 - 针对数字孪生与预测性维护
    集成 MCP 语义规范，用于设备健康特征提取
    """

    @staticmethod
    def calculate_device_action_latency_realtime_ms(
        command_sent_at: datetime,
        sensor_data_series: List[Tuple[datetime, float]],
        device_id: str,
        reliability_score: float = 1.0,
        min_reliability_threshold: float = 0.5,
        trigger_threshold_pct: float = 0.05
    ) -> dict:
        """
        计算指令达标延迟时间 (Action Latency)
        
        计算逻辑：
        1. 以指令下达时间为基点，获取初始环境数值。
        2. 遍历后续传感器序列，寻找第一个变化量超过阈值 (trigger_threshold_pct) 的时间点。
        3. 延迟 Δt = 触发时间 - 指令时间。
        
        Args:
            command_sent_at: 指令下达的精确时间戳
            sensor_data_series: 指令后的传感器数据序列 [(时间, 数值), ...]
            device_id: 设备 ID，用于标识不同设备的计算
            reliability_score: 传感器数据的可靠性分数 (0.0-1.0)，默认 1.0
            min_reliability_threshold: 最小可靠性阈值，低于此值停止计算，默认 0.5
            trigger_threshold_pct: 显著性变化阈值（默认 5%，防止传感器噪声误判）
            
        Returns:
            dict: 包含以下字段的字典：
                - value: 指令达标时延 (ms)，若在观察期内未达标，返回 None
                - unit: 单位，固定为 "ms"
                - status: 状态，"success" | "timeout" | "error"
                - reasoning_context: 基于物理量变化的详细描述
                
        SQL COMMENT:
        该指标用于预测性维护，通过分析设备响应时间评估设备健康状态。
        属于 OpenClaw 架构中的 L3 设备孪生/运维层指标，对应 device_digital_twin_status 表的 action_latency_ms 字段。
        """
        # 1. 置信度过滤
        if reliability_score < min_reliability_threshold:
            return {
                "value": None,
                "unit": "ms",
                "status": "error",
                "reasoning_context": f"设备 {device_id} 的传感器数据可靠性分数过低 ({reliability_score})，低于阈值 ({min_reliability_threshold})，停止计算"
            }

        # 2. 数据有效性检查
        if not sensor_data_series:
            return {
                "value": None,
                "unit": "ms",
                "status": "error",
                "reasoning_context": f"设备 {device_id} 没有提供传感器数据序列"
            }

        # 3. 找到指令时刻或其后的第一个参考点作为初始值
        post_cmd_series = [s for s in sensor_data_series if s[0] >= command_sent_at]
        if not post_cmd_series:
            return {
                "value": None,
                "unit": "ms",
                "status": "error",
                "reasoning_context": f"设备 {device_id} 没有指令下达后的传感器数据"
            }
            
        initial_value = post_cmd_series[0][1]
        
        # 4. 遍历传感器数据，寻找达标点
        for timestamp, current_value in post_cmd_series:
            # 计算变化率，使用 epsilon 避免除零错误
            change_rate = abs(current_value - initial_value) / (abs(initial_value) + 1e-6)
            
            if change_rate >= trigger_threshold_pct:
                # 5. 计算延迟时间
                latency_delta = timestamp - command_sent_at
                latency_ms = round(latency_delta.total_seconds() * 1000, 2)
                
                # 6. 识别变化方向
                direction = "上升" if current_value > initial_value else "下降"
                
                # 7. 生成详细的物理描述
                change_rate_pct = round(change_rate * 100, 2)
                reasoning_context = f"设备 {device_id} 启动后，环境数值在 {latency_ms}ms 内从 {initial_value} {direction} 至 {current_value} (变化率 {change_rate_pct}%)，判定为响应成功"
                
                # 8. 返回结构化结果
                return {
                    "value": latency_ms,
                    "unit": "ms",
                    "status": "success",
                    "reasoning_context": reasoning_context
                }
        
        # 9. 超时情况
        return {
            "value": None,
            "unit": "ms",
            "status": "timeout",
            "reasoning_context": f"设备 {device_id} 在观察期内未达到阈值变化，判定为响应超时"
        }

def run_analysis(data: pd.DataFrame, config: dict) -> dict:
    """
    统一入口函数 - 计算设备动作延迟时间
    
    Args:
        data: 包含过去 24 小时传感器数据的 Pandas DataFrame
        config: 包含设备 ID、策略阈值等配置
        
    Returns:
        dict: 包含计算结果的字典，Key 对应 AgriAnalyticalMetric 数据库表中的字段名
    """
    try:
        # 从配置中提取参数
        device_id = config.get('device_id', 'unknown')
        batch_id = config.get('batch_id', 'unknown')
        reliability_score = config.get('reliability_score', 1.0)
        min_reliability_threshold = config.get('min_reliability_threshold', 0.5)
        trigger_threshold_pct = config.get('trigger_threshold_pct', 0.05)
        
        # 从 DataFrame 中提取数据
        # 假设 DataFrame 包含 command_sent_at 和 sensor_data 列
        if 'command_sent_at' not in data.columns or 'sensor_data' not in data.columns:
            return {
                'data_status': 'INVALID',
                'error': 'Missing required columns: command_sent_at or sensor_data'
            }
        
        # 提取指令发送时间
        command_sent_at_str = data['command_sent_at'].iloc[0]
        if isinstance(command_sent_at_str, str):
            command_sent_at = datetime.fromisoformat(command_sent_at_str)
        else:
            command_sent_at = command_sent_at_str
        
        # 构建传感器数据序列
        sensor_data_series = []
        for _, row in data.iterrows():
            timestamp_str = row['timestamp'] if 'timestamp' in data.columns else row['command_sent_at']
            if isinstance(timestamp_str, str):
                timestamp = datetime.fromisoformat(timestamp_str)
            else:
                timestamp = timestamp_str
            sensor_value = row['sensor_data']
            sensor_data_series.append((timestamp, sensor_value))
        
        # 调用计算函数
        result = DeviceDiagnosticsAnalytics.calculate_device_action_latency_realtime_ms(
            command_sent_at=command_sent_at,
            sensor_data_series=sensor_data_series,
            device_id=device_id,
            reliability_score=reliability_score,
            min_reliability_threshold=min_reliability_threshold,
            trigger_threshold_pct=trigger_threshold_pct
        )
        
        # 转换结果格式，确保符合 AgriAnalyticalMetric 表字段
        return {
            'device_id': device_id,
            'batch_id': batch_id,
            'device_action_latency_ms': result['value'],
            'unit': result['unit'],
            'status': result['status'],
            'reasoning_context': result['reasoning_context']
        }
    except Exception as e:
        return {
            'data_status': 'INVALID',
            'error': str(e)
        }

# --- 模拟 OpenClaw 硬件反馈场景 ---
if __name__ == "__main__":
    from datetime import timedelta
    
    # 场景：14:00:00 下发开启水泵指令
    cmd_time = datetime(2026, 3, 28, 14, 0, 0)
    
    # 模拟传感器数据（前 3 秒没反应，第 4 秒湿度开始上升）
    mock_sensor_logs = [
        (cmd_time + timedelta(seconds=0), 30.0),
        (cmd_time + timedelta(seconds=1), 30.01),
        (cmd_time + timedelta(seconds=2), 30.02),
        (cmd_time + timedelta(seconds=3), 30.05),
        (cmd_time + timedelta(seconds=4), 32.50), # 变化超过 5%，达标
        (cmd_time + timedelta(seconds=5), 35.00),
    ]
    
    latency = DeviceDiagnosticsAnalytics.calculate_device_action_latency_realtime_ms(
        cmd_time, mock_sensor_logs, device_id="pump_001"
    )
    
    print(f"指令下达时间: {cmd_time}")
    print(f"检测到物理响应耗时 (device_action_latency_ms): {latency['value']} ms")
    print(f"状态: {latency['status']}")
    print(f"详细描述: {latency['reasoning_context']}")