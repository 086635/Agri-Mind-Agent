import pandas as pd
import math
from typing import Dict, Any

class SystemEfficiencyAnalytics:
    """
    系统能效分析工具包 - 针对 AI 自动控制优化
    集成 MCP 语义规范，用于二级数据特征提取与策略复盘
    """

    @staticmethod
    def calculate_device_energy_optimization_index(
        initial_val: float,
        final_val: float,
        device_power_w: float,
        duration_sec: float,
        device_id: str,
        metric_type: str,
        target_direction: str
    ) -> dict:
        """
        计算能耗自动优化指数 (Energy Optimization Index)
        
        计算逻辑：
        η = |目标环境指标变化量| / (消耗能量 Joule)
        其中：Consumed_Energy = Power(W) * Duration(s)
        
        Args:
            initial_val (float): 执行动作前的原始环境数值 (如湿度 80%)
            final_val (float): 执行动作后的环境数值 (如湿度 70%)
            device_power_w (float): 执行设备的实时/额定功率 (W)
            duration_sec (float): 设备持续运行的时间 (s)
            device_id (str): 设备 ID，用于标识不同设备的计算
            metric_type (str): 指标类型，决定改善方向 (如降低湿度为正向)
            target_direction (str): 目标变化方向，'down' 表示降低，'up' 表示升高
            
        Returns:
            dict: 包含以下字段的字典：
                - value: 能效指数（每千焦耳的变化量 * 1000）
                - unit: 单位，固定为 "delta/kJ"
                - status: 状态，"success" | "warning" | "error"
                - reasoning_context: 基于物理推导的详细描述
            
        SQL COMMENT:
        该指标用于资源效率评估，通过分析设备运行的能效水平衡量环境改善效果。
        数据去向：agri_analytical_metrics.energy_optimization_index
        属于 OpenClaw 架构中的二级数据特征提取工具，用于 L6 层的动作审计和策略复盘。
        
        PID 优化说明：
        该指数可帮助 Agent 在 policy_risk_thresholds 之后优化 PID 参数：
        - 当指数较高时，说明当前 PID 参数设置合理，可适当减小控制幅度以节约能源
        - 当指数较低时，说明当前 PID 参数设置不够高效，需要调整比例、积分或微分参数以提高响应速度
        - 当指数为负时，说明控制方向错误，需要反转控制逻辑
        """
        # 1. 数据防错：非负拦截
        if device_power_w <= 0:
            return {
                "value": 0.0,
                "unit": "delta/kJ",
                "status": "error",
                "reasoning_context": f"设备 {device_id} 的功率不能为 0 或负数: {device_power_w}"
            }
        
        if duration_sec <= 0:
            return {
                "value": 0.0,
                "unit": "delta/kJ",
                "status": "error",
                "reasoning_context": f"设备 {device_id} 的运行时间不能为 0 或负数: {duration_sec}"
            }
        
        # 2. 计算总消耗能量 (单位: Joule 焦耳)
        consumed_energy_j = device_power_w * duration_sec
        
        # 3. 计算环境变化量
        delta_e = final_val - initial_val
        delta_abs = abs(delta_e)
        
        # 4. 判定改善方向
        direction = "升高" if delta_e > 0 else "降低"
        is_positive_improvement = False
        
        if target_direction == 'up' and delta_e > 0:
            is_positive_improvement = True
        elif target_direction == 'down' and delta_e < 0:
            is_positive_improvement = True
        
        # 5. 计算能效比 (为了方便记录，通常扩大系数，表示为 每千焦耳产生的变化量)
        # η = (ΔE / Joule) * 1000
        energy_optimization_index = (delta_abs / consumed_energy_j) * 1000
        
        # 6. 生成详细的物理推导描述
        if is_positive_improvement:
            reasoning_context = f"设备 {device_id} 运行 {duration_sec}s 消耗 {consumed_energy_j}J，使 {metric_type} {direction} 了 {delta_abs}，能效指数为 {round(energy_optimization_index, 4)}。"
            status = "success"
        else:
            reasoning_context = f"设备 {device_id} 运行 {duration_sec}s 消耗 {consumed_energy_j}J，但 {metric_type} {direction} 了 {delta_abs}，与目标方向相反，判定为无效干预。能效指数为 {round(energy_optimization_index, 4)}。"
            status = "warning"
        
        # 7. 返回结构化结果
        return {
            "value": round(energy_optimization_index, 4),
            "unit": "delta/kJ",
            "status": status,
            "reasoning_context": reasoning_context
        }

def run_analysis(data: pd.DataFrame, config: dict) -> dict:
    """
    统一入口函数 - 计算设备能耗优化指数
    
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
        metric_type = config.get('metric_type', 'humidity')
        target_direction = config.get('target_direction', 'down')
        device_power_w = config.get('device_power_w', 100.0)
        
        # 从 DataFrame 中提取数据
        # 假设 DataFrame 包含 initial_val, final_val, duration_sec 列
        if 'initial_val' not in data.columns or 'final_val' not in data.columns or 'duration_sec' not in data.columns:
            return {
                'data_status': 'INVALID',
                'error': 'Missing required columns: initial_val, final_val, or duration_sec'
            }
        
        # 计算能耗优化指数
        initial_val = data['initial_val'].iloc[0]
        final_val = data['final_val'].iloc[0]
        duration_sec = data['duration_sec'].iloc[0]
        
        # 调用计算函数
        result = SystemEfficiencyAnalytics.calculate_device_energy_optimization_index(
            initial_val=initial_val,
            final_val=final_val,
            device_power_w=device_power_w,
            duration_sec=duration_sec,
            device_id=device_id,
            metric_type=metric_type,
            target_direction=target_direction
        )
        
        # 转换结果格式，确保符合 AgriAnalyticalMetric 表字段
        return {
            'device_id': device_id,
            'batch_id': batch_id,
            'energy_optimization_index': result['value'],
            'unit': result['unit'],
            'status': result['status'],
            'reasoning_context': result['reasoning_context']
        }
    except Exception as e:
        return {
            'data_status': 'INVALID',
            'error': str(e)
        }

# --- 模拟 OpenClaw 决策复盘场景 ---
if __name__ == "__main__":
    # 场景对比：
    # A方案：强力除湿（风扇 100W，运行 60秒，湿度从 80% 降到 75%）
    # B方案：温和除湿（风扇 20W，运行 300秒，湿度从 80% 降到 75%）
    
    # 虽然 ΔE 相同，但能耗不同
    schema_a = {
        "initial": 80.0, "final": 75.0, "power": 100.0, "duration": 60.0
    }
    schema_b = {
        "initial": 80.0, "final": 75.0, "power": 20.0, "duration": 300.0
    }
    
    index_a = SystemEfficiencyAnalytics.calculate_device_energy_optimization_index(
        schema_a["initial"], schema_a["final"], schema_a["power"], schema_a["duration"],
        device_id="fan_001", metric_type="humidity", target_direction="down"
    )
    
    index_b = SystemEfficiencyAnalytics.calculate_device_energy_optimization_index(
        schema_b["initial"], schema_b["final"], schema_b["power"], schema_b["duration"],
        device_id="fan_001", metric_type="humidity", target_direction="down"
    )
    
    print(f"方案 A 能效指数: {index_a['value']} {index_a['unit']}")
    print(f"状态: {index_a['status']}")
    print(f"理由: {index_a['reasoning_context']}")
    print()
    print(f"方案 B 能效指数: {index_b['value']} {index_b['unit']}")
    print(f"状态: {index_b['status']}")
    print(f"理由: {index_b['reasoning_context']}")
    print()
    
    if index_a['value'] > index_b['value']:
        print(">>> AI 建议：选择 A 方案（大功率短时运行更省电）")
    else:
        print(">>> AI 建议：选择 B 方案（小功率长时运行更省电）")