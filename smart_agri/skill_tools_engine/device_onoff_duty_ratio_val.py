from datetime import datetime, timedelta
from typing import List, Dict

class DeviceDiagnosticsTool:
    """
    运维数据分析工具库 - 设备数字孪生与预防性维护
    """

    @staticmethod
    def calc_device_onoff_duty_ratio_val(
        device_id: str,
        action_logs: List[Dict], 
        window_start_time: datetime,
        observation_window_hrs: float = 24.0
    ) -> Dict:
        """
        SQL COMMENT: 统计表6(agent_action_audit)中指定 device_id 在过去 window 小时内的成功动作，计算结果回填至表3(device_digital_twin_status)。
        
        算法：设备启停比 (Device On/Off Duty Ratio)
        逻辑：分析设备在观察周期内的开启频率与单次持续时间的关系。
        
        Args:
            device_id: 设备ID
            action_logs: 动作审计日志列表，每个元素含 {'start_time': dt, 'end_time': dt, 'execution_status': str}
            window_start_time: 观察窗口开始时间
            observation_window_hrs: 观察窗口时长 (小时)
            
        Returns:
            Dict 包含：
                - device_id: 设备ID
                - on_off_cycles: 开启总次数
                - duty_cycle_ratio: 0.0-1.0 (总运行占比)
                - failure_probability: 故障概率 (对应震荡风险评分 0-1)
                - reasoning_context: 运维建议
        """
        # 异常与边界处理
        if not device_id:
            raise ValueError("device_id 不能为空")
        if not isinstance(window_start_time, datetime):
            raise TypeError("window_start_time 必须是 datetime 类型")
        if observation_window_hrs <= 0:
            raise ValueError("observation_window_hrs 必须大于 0")
        if not action_logs:
            return {
                "device_id": device_id,
                "on_off_cycles": 0,
                "duty_cycle_ratio": 0.0,
                "failure_probability": 0.0,
                "reasoning_context": "设备无动作记录，状态正常"
            }

        total_runtime_sec = 0.0
        valid_cycles = 0
        window_end_time = window_start_time + timedelta(hours=observation_window_hrs)
        
        # 1. 计算总运行时间，过滤成功动作并处理跨窗口动作
        for log in action_logs:
            # 过滤执行状态为 "Success" 的动作
            if log.get('execution_status') != 'Success':
                continue
            
            # 处理跨窗口动作的截断
            start_time = log['start_time']
            end_time = log['end_time']
            
            # 只计算窗口内的部分
            if end_time <= window_start_time:
                continue
            if start_time >= window_end_time:
                continue
            
            # 截断时间范围
            actual_start = max(start_time, window_start_time)
            actual_end = min(end_time, window_end_time)
            
            duration = (actual_end - actual_start).total_seconds()
            total_runtime_sec += max(duration, 0)
            valid_cycles += 1

        # 2. 计算占空比 (Duty Cycle Ratio)
        total_window_sec = observation_window_hrs * 3600
        duty_cycle_ratio = total_runtime_sec / total_window_sec if total_window_sec > 0 else 0

        # 3. 震荡风险评估 (Oscillation Risk)
        # 逻辑：如果开启次数 > 20次/天 且 平均单次时长 < 60秒，判定为高风险震荡
        avg_session_sec = total_runtime_sec / valid_cycles if valid_cycles > 0 else 0
        
        # 简易风险模型：次数越多且时长越短，风险越高
        oscillation_risk = min((valid_cycles / 50.0) * (60.0 / max(avg_session_sec, 1.0)), 1.0)

        # 4. 生成运维建议
        if oscillation_risk < 0.3:
            reasoning_context = f"设备 {device_id} 运行状态正常，24h内启停 {valid_cycles} 次，运行稳定"
        elif oscillation_risk < 0.7:
            reasoning_context = f"设备 {device_id} 24h内启停频率较高({valid_cycles}次)，建议检查控制参数设置"
        else:
            reasoning_context = f"设备 {device_id} 24h内启停频率过高({valid_cycles}次)，单次运行时长极短，检测到控制死区过窄，建议上调表5中的风险阈值"

        # 5. 返回结果
        return {
            "device_id": device_id,
            "on_off_cycles": valid_cycles,
            "duty_cycle_ratio": round(duty_cycle_ratio, 4),
            "failure_probability": round(oscillation_risk, 2),
            "reasoning_context": reasoning_context
        }

# --- 模拟 OpenClaw 运维诊断上下文 ---
if __name__ == "__main__":
    # 测试场景1: 频繁启停场景
    now = datetime.now()
    mock_logs1 = [
        {'start_time': now - timedelta(hours=i), 'end_time': now - timedelta(hours=i, seconds=45), 'execution_status': 'Success'}
        for i in range(24) # 24小时内开了24次，每次只开45秒
    ]
    
    analysis1 = DeviceDiagnosticsTool.calc_device_onoff_duty_ratio_val(
        device_id="Pump-001",
        action_logs=mock_logs1,
        window_start_time=now - timedelta(hours=24)
    )
    
    print(f"--- 测试场景1: 频繁启停场景 ---")
    print(f"设备ID: {analysis1['device_id']}")
    print(f"开启频率: {analysis1['on_off_cycles']} 次/24h")
    print(f"实际占空比: {analysis1['duty_cycle_ratio']}")
    print(f"故障概率: {analysis1['failure_probability']}")
    print(f"运维建议: {analysis1['reasoning_context']}")
    print()
    
    # 测试场景2: 正常运行场景
    mock_logs2 = [
        {'start_time': now - timedelta(hours=23), 'end_time': now - timedelta(hours=11), 'execution_status': 'Success'},
        {'start_time': now - timedelta(hours=10), 'end_time': now, 'execution_status': 'Success'}
    ]
    
    analysis2 = DeviceDiagnosticsTool.calc_device_onoff_duty_ratio_val(
        device_id="Pump-002",
        action_logs=mock_logs2,
        window_start_time=now - timedelta(hours=24)
    )
    
    print(f"--- 测试场景2: 正常运行场景 ---")
    print(f"设备ID: {analysis2['device_id']}")
    print(f"开启频率: {analysis2['on_off_cycles']} 次/24h")
    print(f"实际占空比: {analysis2['duty_cycle_ratio']}")
    print(f"故障概率: {analysis2['failure_probability']}")
    print(f"运维建议: {analysis2['reasoning_context']}")
    print()
    
    # 测试场景3: 跨窗口动作场景
    mock_logs3 = [
        {'start_time': now - timedelta(hours=25), 'end_time': now - timedelta(hours=23), 'execution_status': 'Success'},
        {'start_time': now - timedelta(hours=2), 'end_time': now + timedelta(hours=1), 'execution_status': 'Success'}
    ]
    
    analysis3 = DeviceDiagnosticsTool.calc_device_onoff_duty_ratio_val(
        device_id="Pump-003",
        action_logs=mock_logs3,
        window_start_time=now - timedelta(hours=24)
    )
    
    print(f"--- 测试场景3: 跨窗口动作场景 ---")
    print(f"设备ID: {analysis3['device_id']}")
    print(f"开启频率: {analysis3['on_off_cycles']} 次/24h")
    print(f"实际占空比: {analysis3['duty_cycle_ratio']}")
    print(f"故障概率: {analysis3['failure_probability']}")
    print(f"运维建议: {analysis3['reasoning_context']}")
    print()
    
    # 测试场景4: 无动作记录场景
    analysis4 = DeviceDiagnosticsTool.calc_device_onoff_duty_ratio_val(
        device_id="Pump-004",
        action_logs=[],
        window_start_time=now - timedelta(hours=24)
    )
    
    print(f"--- 测试场景4: 无动作记录场景 ---")
    print(f"设备ID: {analysis4['device_id']}")
    print(f"开启频率: {analysis4['on_off_cycles']} 次/24h")
    print(f"实际占空比: {analysis4['duty_cycle_ratio']}")
    print(f"故障概率: {analysis4['failure_probability']}")
    print(f"运维建议: {analysis4['reasoning_context']}")
    
    # 测试场景5: 水泵 24 小时内 100 次"开 10 秒即关"的震荡行为
    mock_logs5 = []
    for i in range(100):
        start = now - timedelta(hours=24) + timedelta(minutes=i*14.4)  # 14.4分钟一次，24小时100次
        end = start + timedelta(seconds=10)  # 开10秒即关
        mock_logs5.append({'start_time': start, 'end_time': end, 'execution_status': 'Success'})
    
    analysis5 = DeviceDiagnosticsTool.calc_device_onoff_duty_ratio_val(
        device_id="Pump-005",
        action_logs=mock_logs5,
        window_start_time=now - timedelta(hours=24)
    )
    
    print(f"\n--- 测试场景5: 水泵 24 小时内 100 次'开 10 秒即关'的震荡行为 ---")
    print(f"设备ID: {analysis5['device_id']}")
    print(f"开启频率: {analysis5['on_off_cycles']} 次/24h")
    print(f"实际占空比: {analysis5['duty_cycle_ratio']}")
    print(f"故障概率: {analysis5['failure_probability']}")
    print(f"运维建议: {analysis5['reasoning_context']}")
    
    print(f"\n架构意义: 此数据已写入 device_digital_twin_status 表，将触发预测性维护建议。")