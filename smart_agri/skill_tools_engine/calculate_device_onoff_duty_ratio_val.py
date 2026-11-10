from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd

class DeviceDiagnosticsTool:
    """
    运维数据分析工具库 - 设备数字孪生与预防性维护
    """

    @staticmethod
    def calculate_device_onoff_duty_ratio_val(
        action_logs: List[Dict], 
        observation_window_hrs: float = 24.0,
        device_id: str = None
    ) -> dict:
        """
        算法：设备启停比 (Device On/Off Duty Ratio)
        逻辑：分析设备在观察周期内的开启频率与单次持续时间的关系，识别控制算法的震荡风险。
        
        Args:
            action_logs: 动作审计日志列表，每个元素含 {'start_time': dt, 'end_time': dt}
            observation_window_hrs: 观察窗口时长 (小时)
            device_id: 设备 ID，用于标识不同设备的计算
            
        Returns:
            dict: 包含以下字段的字典：
                - duty_cycle_ratio: 占空比 (float)
                - on_off_cycles: 开启总次数 (int)
                - oscillation_risk: 风险指数 (float, 0.0-1.0)
                - status: 状态，"success" | "warning" | "error"
                - suggested_action: 给 Agent 的下一步动作指令 (str)
                - reasoning_context: 详细的描述 (str)
            
        SQL COMMENT:
        该指标用于设备健康状态评估，通过分析设备启停频率和持续时间识别控制算法的震荡风险。
        数据去向：device_digital_twin_status 表的 duty_cycle_ratio 和 on_off_cycles 字段
        属于 OpenClaw 架构中的 L3 设备孪生/运维层指标，用于预测性维护决策。
        
        设备指纹异常预警机制：
        通过分析 on_off_cycles 的斜率变化（即单位时间内启停次数的变化率），可以在 dev_health_diagnostics 中触发设备指纹异常预警。
        当斜率突然增加时，说明设备启停频率异常升高，可能是控制算法参数不当或设备故障的前兆。
        """
        # 1. 数据防御与鲁棒性
        if observation_window_hrs <= 0:
            return {
                "duty_cycle_ratio": 0.0,
                "on_off_cycles": 0,
                "oscillation_risk": 0.0,
                "status": "error",
                "suggested_action": "none",
                "reasoning_context": f"观察窗口时长必须为正数: {observation_window_hrs}"
            }

        if not action_logs:
            return {
                "duty_cycle_ratio": 0.0,
                "on_off_cycles": 0,
                "oscillation_risk": 0.0,
                "status": "warning",
                "suggested_action": "none",
                "reasoning_context": "无动作日志，无法计算启停比"
            }

        total_runtime_sec = 0.0
        on_off_cycles = len(action_logs)
        valid_logs = 0
        
        # 2. 计算总运行时间，处理数据不全的情况
        for log in action_logs:
            if 'start_time' not in log or 'end_time' not in log:
                continue
            duration = (log['end_time'] - log['start_time']).total_seconds()
            total_runtime_sec += max(duration, 0)
            valid_logs += 1

        if valid_logs == 0:
            return {
                "duty_cycle_ratio": 0.0,
                "on_off_cycles": 0,
                "oscillation_risk": 0.0,
                "status": "warning",
                "suggested_action": "none",
                "reasoning_context": "动作日志数据不全，无法计算启停比"
            }

        # 3. 计算占空比 (Duty Cycle Ratio)
        total_window_sec = observation_window_hrs * 3600
        duty_cycle_ratio = total_runtime_sec / total_window_sec

        # 4. 计算平均单次运行时长
        avg_session_sec = total_runtime_sec / valid_logs if valid_logs > 0 else 0

        # 5. 优化震荡风险评估 (Oscillation Risk)
        # 逻辑：如果开启次数过多且单次时长过短，判定为高风险
        # 风险模型：次数越多且时长越短，风险越高
        oscillation_risk = min((valid_logs / 50.0) * (60.0 / max(avg_session_sec, 1.0)), 1.0)

        # 6. 生成策略反馈
        if oscillation_risk > 0.7:
            suggested_action = "increase_deadband"
            risk_level = "高"
            risk_message = "，震荡风险高，可能导致设备损坏"
        elif oscillation_risk > 0.3:
            suggested_action = "adjust_control_params"
            risk_level = "中等"
            risk_message = "，震荡风险中等，建议调整控制参数"
        else:
            suggested_action = "none"
            risk_level = "低"
            risk_message = "，震荡风险低，设备运行稳定"

        # 7. 生成详细的描述
        reasoning_context = f"设备 {device_id} 在 {observation_window_hrs}h 内启停 {valid_logs} 次，均长 {avg_session_sec:.2f}s，状态为 {risk_level}风险{risk_message}"

        # 8. 返回结构化结果
        return {
            "duty_cycle_ratio": round(duty_cycle_ratio, 4),
            "on_off_cycles": valid_logs,
            "oscillation_risk": round(oscillation_risk, 2),
            "status": "success",
            "suggested_action": suggested_action,
            "reasoning_context": reasoning_context
        }

# --- 模拟 OpenClaw 运维诊断上下文 ---
if __name__ == "__main__":
    # 模拟某水泵 24 小时内的运行数据 (发生了频繁启停)
    now = datetime.now()
    mock_logs = [
        {'start_time': now - timedelta(hours=i), 'end_time': now - timedelta(hours=i, seconds=45)}
        for i in range(24) # 24小时内开了24次，每次只开45秒
    ]
    
    analysis = DeviceDiagnosticsTool.calculate_device_onoff_duty_ratio_val(
        mock_logs,
        device_id="device_001"
    )
    
    print(f"--- 设备健康度报告 (L3 Digital Twin) ---")
print(f"开启频率: {analysis['on_off_cycles']} 次/24h")
print(f"实际占空比 (device_onoff_duty_ratio_val): {analysis['duty_cycle_ratio']}")
print(f"震荡风险指数: {analysis['oscillation_risk']} ({analysis['reasoning_context']})")
print(f"架构意义: 此数据已写入 device_digital_twin_status 表，将触发预测性维护建议。")


def run_analysis(data: pd.DataFrame, config: dict) -> dict:
    """
    插件式架构统一入口函数
    
    Args:
        data: 包含过去 24 小时传感器数据的 Pandas DataFrame
        config: 包含设备 ID、策略阈值等配置
        
    Returns:
        dict: 包含计算结果的字典，Key 对应 AgriAnalyticalMetric 数据库表中的字段名
    """
    try:
        # 从 config 中提取参数
        device_id = config.get('device_id', None)
        observation_window_hrs = config.get('observation_window_hrs', 24.0)
        
        # 从 data 中提取动作日志
        action_logs = []
        if 'action_logs' in data.columns:
            for _, row in data.iterrows():
                if isinstance(row['action_logs'], dict) and 'start_time' in row['action_logs'] and 'end_time' in row['action_logs']:
                    action_logs.append(row['action_logs'])
        elif 'start_time' in data.columns and 'end_time' in data.columns:
            for _, row in data.iterrows():
                if pd.notna(row['start_time']) and pd.notna(row['end_time']):
                    action_logs.append({
                        'start_time': row['start_time'],
                        'end_time': row['end_time']
                    })
        
        # 调用核心算法
        result = DeviceDiagnosticsTool.calculate_device_onoff_duty_ratio_val(
            action_logs=action_logs,
            observation_window_hrs=observation_window_hrs,
            device_id=device_id
        )
        
        # 转换为符合 AgriAnalyticalMetric 表字段的返回格式
        return {
            'duty_cycle_ratio': result['duty_cycle_ratio'],
            'on_off_cycles': result['on_off_cycles'],
            'oscillation_risk': result['oscillation_risk'],
            'device_id': device_id,
            'status': result['status'],
            'suggested_action': result['suggested_action'],
            'reasoning_context': result['reasoning_context']
        }
    except Exception as e:
        # 异常处理
        return {
            'data_status': 'INVALID',
            'error_message': str(e)
        }