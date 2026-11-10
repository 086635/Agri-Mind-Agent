from typing import List, Dict
import numpy as np
import pandas as pd

class EnergyEfficiencyTool:
    """
    二级数据分析工具库 - 设备效能与能耗优化算法
    """

    @staticmethod
    def calculate_device_stability_energy_ratio_pct(
        actual_duty_cycle: float,
        target_metric_variance: float,
        base_duty_cycle_limit: float = 0.5,
        variance_limit: float = 2.0,
        device_id: str = None
    ) -> dict:
        """
        算法：环境稳态能效比 (Stability Energy Ratio)
        逻辑：计算在环境达标(稳态)的前提下，AI控制相对于传统冗余控制节省的能效比例。
        
        Args:
            actual_duty_cycle: 实际监测到的设备启停比 (0.0-1.0)，来自 device_digital_twin_status。
            target_metric_variance: 目标环境指标的方差。方差越小，稳态质量越高。
            base_duty_cycle_limit: 该环境下传统控制所需的基准启停比 (默认为 0.5, 即 50% 时间在运行)。
            variance_limit: 环境稳态判断的方差阈值，超过此值则认为环境未达稳态。
            device_id: 设备 ID，用于标识不同设备的计算
            
        Returns:
            dict: 包含能效比、状态、决策理由和动作反馈的字典
        
        SQL COMMENT:
        该指标用于评估 AI 策略的财务与社会价值，通过比较 AI 控制与传统控制的能耗差异，
        衡量在确保环境稳态的前提下的能效提升。
        数据去向：esg_value_realization.energy_efficiency_ratio
        属于 OpenClaw 架构中的 L4 价值实现层指标，为 ESG 价值评估提供数据支撑。
        
        环境背景支撑：
        该算法为 biomass_carbon_sequestration_g（生物质固碳量）提供环境背景支撑。
        只有在环境稳态下，固碳计算才具备高信度，因为稳态环境确保了生物质生长条件的一致性。
        """
        # 1. 数据防御与鲁棒性
        if base_duty_cycle_limit <= 0:
            return {
                "value": 0.0,
                "status": "error",
                "reasoning_context": f"基准占空比必须为正数: {base_duty_cycle_limit}",
                "actual_delta": 0.0,
                "unit": "pct",
                "device_id": device_id
            }

        if target_metric_variance is None or target_metric_variance < 0:
            return {
                "value": 0.0,
                "status": "error",
                "reasoning_context": f"目标环境指标方差无效: {target_metric_variance}",
                "actual_delta": 0.0,
                "unit": "pct",
                "device_id": device_id
            }

        # 2. 稳态质量评估
        # 如果方差过大，说明环境根本不稳，此时不计算能效比（或返回 0）
        if target_metric_variance > variance_limit:
            return {
                "value": 0.0,
                "status": "warning",
                "reasoning_context": f"环境波动过大（方差: {target_metric_variance}），稳态未达成，无法计算能效比",
                "actual_delta": 0.0,
                "unit": "pct",
                "device_id": device_id
            }

        # 3. 计算能耗节省率
        # 节能率 = (基准占空比 - 实际占空比) / 基准占空比
        efficiency_gain = (base_duty_cycle_limit - actual_duty_cycle) / base_duty_cycle_limit
        
        # 4. 转化为百分比并格式化
        # 即使实际占空比略高于基准，也保留负值以反馈 AI 策略需优化
        efficiency_gain_pct = efficiency_gain * 100

        # 5. 生成决策理由和状态
        if efficiency_gain_pct > 0:
            reasoning_context = f"设备 {device_id} AI控制较基准节省 {efficiency_gain_pct:.2f}% 能耗，稳态质量：{target_metric_variance}"
            status = "success"
        elif efficiency_gain_pct < 0:
            reasoning_context = f"设备 {device_id} AI控制较基准多消耗 {-efficiency_gain_pct:.2f}% 能耗，需要优化控制策略，稳态质量：{target_metric_variance}"
            status = "warning"
        else:
            reasoning_context = f"设备 {device_id} AI控制与传统控制能耗相当，稳态质量：{target_metric_variance}"
            status = "success"

        return {
            "value": round(efficiency_gain_pct, 2),
            "status": status,
            "reasoning_context": reasoning_context,
            "actual_delta": efficiency_gain_pct,
            "unit": "pct",
            "device_id": device_id
        }

# --- 模拟执行器诊断与 ESG 价值计算 ---
if __name__ == "__main__":
    # 场景：AI 优化后的加热器控制
    # 传统控制为了控温，每分钟开 30 秒 (Duty Cycle = 0.5)
    # AI 经过 PID 调优后，由于预测了热惯性，每分钟仅需开 12 秒 (Duty Cycle = 0.2)
    
    ai_duty_cycle = 0.2
    env_variance = 0.15  # 温度波动极小，说明稳态质量极高
    
    ser_pct = EnergyEfficiencyTool.calculate_device_stability_energy_ratio_pct(
        actual_duty_cycle=ai_duty_cycle,
        target_metric_variance=env_variance,
        base_duty_cycle_limit=0.5,
        device_id="device_001"
    )
    
    print(f"--- 设备能效分析报告 ---")
print(f"环境稳定性: 极高 (Variance: {env_variance})")
print(f"AI 实际启停比: {ai_duty_cycle}")
print(f"核心指标 (device_stability_energy_ratio_pct): {ser_pct['value']}%")
print(f"决策理由: {ser_pct['reasoning_context']}")
print(f"架构意义: 此数据已关联至 esg_value_realization.energy_efficiency_ratio")


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
        base_duty_cycle_limit = config.get('base_duty_cycle_limit', 0.5)
        variance_limit = config.get('variance_limit', 2.0)
        
        # 从 data 中提取实际占空比和目标指标方差
        actual_duty_cycle = None
        target_metric_variance = None
        
        if 'actual_duty_cycle' in data.columns:
            actual_duty_cycle = data['actual_duty_cycle'].mean()
        elif 'duty_cycle' in data.columns:
            actual_duty_cycle = data['duty_cycle'].mean()
        
        if 'target_metric_variance' in data.columns:
            target_metric_variance = data['target_metric_variance'].mean()
        elif 'variance' in data.columns:
            target_metric_variance = data['variance'].mean()
        
        # 确保参数有效
        if actual_duty_cycle is None or target_metric_variance is None:
            return {
                'data_status': 'INVALID',
                'error_message': 'Missing required parameters: actual_duty_cycle or target_metric_variance'
            }
        
        # 调用核心算法
        result = EnergyEfficiencyTool.calculate_device_stability_energy_ratio_pct(
            actual_duty_cycle=actual_duty_cycle,
            target_metric_variance=target_metric_variance,
            base_duty_cycle_limit=base_duty_cycle_limit,
            variance_limit=variance_limit,
            device_id=device_id
        )
        
        # 转换为符合 AgriAnalyticalMetric 表字段的返回格式
        return {
            'energy_efficiency_ratio': result['value'],
            'device_id': device_id,
            'status': result['status'],
            'reasoning_context': result['reasoning_context']
        }
    except Exception as e:
        # 异常处理
        return {
            'data_status': 'INVALID',
            'error_message': str(e)
        }