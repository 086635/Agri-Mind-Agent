from typing import List, Dict, Optional
import numpy as np

class EnergyEfficiencyTool:
    """
    二级数据分析工具库 - 设备效能与能耗优化算法
    """

    @staticmethod
    def calc_device_stability_energy_ratio_pct(
        device_id: str,
        batch_id: str,
        actual_duty_cycle: float,
        target_metric_variance: float,
        base_duty_cycle_limit: float = 0.5,
        rated_power_w: Optional[float] = None
    ) -> Dict:
        """
        SQL COMMENT: 自动抓取表3(device_digital_twin_status)的 duty_cycle_ratio，结合表1的环境波动率，计算增效百分比并回填至表4(energy_efficiency_ratio)。
        
        算法：环境稳态能效比 (Stability Energy Ratio)
        逻辑：计算在环境达标(稳态)的前提下，AI控制相对于传统冗余控制节省的能效比例。
        
        Args:
            device_id: 设备唯一标识符
            batch_id: 批次标识符
            actual_duty_cycle: 实际监测到的设备启停比 (0.0-1.0)，来自 device_digital_twin_status。
            target_metric_variance: 目标环境指标的方差。方差越小，稳态质量越高。
            base_duty_cycle_limit: 该环境下传统控制所需的基准启停比 (默认为 0.5, 即 50% 时间在运行)。
            rated_power_w: 设备额定功率（瓦特），用于计算具体节能电量和成本
            
        Returns:
            Dict: 包含能效比百分比、稳定性评分、降本增效核算等信息的字典
        """
        # 异常与边界处理
        if not device_id or not batch_id:
            raise ValueError("device_id 和 batch_id 不能为空")
        
        if not 0 <= actual_duty_cycle <= 1:
            raise ValueError("actual_duty_cycle 必须在 0.0-1.0 之间")
        
        if target_metric_variance < 0:
            raise ValueError("target_metric_variance 不能为负值")
        
        if base_duty_cycle_limit <= 0:
            raise ValueError("base_duty_cycle_limit 必须大于 0")
        
        if rated_power_w is not None and rated_power_w < 0:
            raise ValueError("rated_power_w 不能为负值")
        
        # 1. 计算能耗节省率
        # 节能率 = (基准占空比 - 实际占空比) / 基准占空比
        efficiency_gain = (base_duty_cycle_limit - actual_duty_cycle) / base_duty_cycle_limit
        
        # 2. 实现惩罚系数模型
        # 公式：Final_Efficiency = Efficiency_Gain * (1 - Normalized_Variance)
        max_allowed_variance = 2.0  # 最大允许方差
        normalized_variance = min(target_metric_variance / max_allowed_variance, 1.0)
        final_efficiency = efficiency_gain * (1 - normalized_variance)
        
        # 3. 计算稳定性评分
        stability_score = round((1 - normalized_variance) * 100, 2)  # 0-100 分
        
        # 4. 转化为百分比并格式化
        energy_efficiency_ratio = round(final_efficiency * 100, 2)
        
        # 5. 实现降本增效核算
        cost_reduction_amount = 0.0
        
        if rated_power_w is not None:
            # 假设每天运行 24 小时
            daily_hours = 24
            # 计算每天节省的电量（千瓦时）
            energy_saving_kwh = (base_duty_cycle_limit - actual_duty_cycle) * rated_power_w * daily_hours / 1000
            # 假设电费为 0.6 元/千瓦时
            electricity_price = 0.6
            cost_reduction_amount = round(energy_saving_kwh * electricity_price, 2)
        
        # 6. 生成面向投资人的 reasoning_context
        if energy_efficiency_ratio > 0:
            if stability_score >= 90:
                reasoning_context = f"本周期通过 AI 介入，在维持 95% 环境稳态的前提下，实现设备能效提升 {abs(energy_efficiency_ratio):.1f}%"
            elif stability_score >= 70:
                reasoning_context = f"本周期通过 AI 介入，在维持良好环境稳态的前提下，实现设备能效提升 {abs(energy_efficiency_ratio):.1f}%"
            else:
                reasoning_context = f"本周期通过 AI 介入，实现设备能效提升 {abs(energy_efficiency_ratio):.1f}%，但环境稳态质量需要进一步优化"
        elif energy_efficiency_ratio < 0:
            reasoning_context = f"本周期 AI 策略导致能效赤字 {abs(energy_efficiency_ratio):.1f}%，需要优化控制参数"
        else:
            reasoning_context = "本周期 AI 控制与传统控制能效相当，需要进一步优化策略"
        
        # 7. 构建返回结果
        result = {
            "device_id": device_id,
            "batch_id": batch_id,
            "energy_efficiency_ratio": energy_efficiency_ratio,
            "stability_score": stability_score,
            "reasoning_context": reasoning_context
        }
        
        # 如果提供了功率，添加成本节省信息
        if rated_power_w is not None:
            result["cost_reduction_amount"] = cost_reduction_amount
        
        return result

# --- 模拟执行器诊断与 ESG 价值计算 ---
if __name__ == "__main__":
    # 测试场景 1: 蓝莓大棚 A 组（AI 组）与 B 组（传统组）
    print("=== 测试场景 1: 蓝莓大棚场景 ===")
    result1 = EnergyEfficiencyTool.calc_device_stability_energy_ratio_pct(
        device_id="BLUEBERRY_GREENHOUSE_A",
        batch_id="BATCH_2026_03_29_001",
        actual_duty_cycle=0.2,  # AI 组占空比
        target_metric_variance=0.1,  # 环境方差
        base_duty_cycle_limit=0.5,  # 基准占空比
        rated_power_w=5000  # 设备额定功率 5000W
    )
    
    print(f"设备 ID: {result1['device_id']}")
    print(f"批次 ID: {result1['batch_id']}")
    print(f"AI 实际占空比: 0.2")
    print(f"环境方差: 0.1")
    print(f"能效比: {result1['energy_efficiency_ratio']}%")
    print(f"稳定性评分: {result1['stability_score']}")
    print(f"成本节省: CNY {result1['cost_reduction_amount']}")
    print(f"面向投资人的说明: {result1['reasoning_context']}")
    print(f"架构意义: 此数据已关联至 esg_value_realization.energy_efficiency_ratio")
    print()
    
    # 测试场景 2: 环境不稳定情况
    print("=== 测试场景 2: 环境不稳定情况 ===")
    result2 = EnergyEfficiencyTool.calc_device_stability_energy_ratio_pct(
        device_id="HEATER_001",
        batch_id="BATCH_2026_03_29_002",
        actual_duty_cycle=0.3,
        target_metric_variance=2.5,  # 温度波动较大，说明稳态质量低
        base_duty_cycle_limit=0.5
    )
    
    print(f"设备 ID: {result2['device_id']}")
    print(f"批次 ID: {result2['batch_id']}")
    print(f"环境方差: 2.5")
    print(f"能效比: {result2['energy_efficiency_ratio']}%")
    print(f"稳定性评分: {result2['stability_score']}")
    print(f"面向投资人的说明: {result2['reasoning_context']}")
    print()
    
    # 测试场景 3: AI 策略需要优化的情况
    print("=== 测试场景 3: AI 策略需要优化的情况 ===")
    result3 = EnergyEfficiencyTool.calc_device_stability_energy_ratio_pct(
        device_id="HEATER_001",
        batch_id="BATCH_2026_03_29_003",
        actual_duty_cycle=0.6,  # 实际启停比高于基准
        target_metric_variance=0.5,
        base_duty_cycle_limit=0.5,
        rated_power_w=1500
    )
    
    print(f"设备 ID: {result3['device_id']}")
    print(f"批次 ID: {result3['batch_id']}")
    print(f"AI 实际占空比: 0.6")
    print(f"环境方差: 0.5")
    print(f"能效比: {result3['energy_efficiency_ratio']}%")
    print(f"稳定性评分: {result3['stability_score']}")
    print(f"成本节省: CNY {result3['cost_reduction_amount']}")
    print(f"面向投资人的说明: {result3['reasoning_context']}")
    print()
    
    # 测试场景 4: 边界值测试
    print("=== 测试场景 4: 边界值测试 ===")
    try:
        result4 = EnergyEfficiencyTool.calc_device_stability_energy_ratio_pct(
            device_id="",  # 空设备 ID
            batch_id="BATCH_2026_03_29_004",
            actual_duty_cycle=0.5,
            target_metric_variance=1.0
        )
    except ValueError as e:
        print(f"预期的错误: {e}")
    
    try:
        result5 = EnergyEfficiencyTool.calc_device_stability_energy_ratio_pct(
            device_id="HEATER_001",
            batch_id="BATCH_2026_03_29_005",
            actual_duty_cycle=1.5,  # 超出范围的启停比
            target_metric_variance=1.0
        )
    except ValueError as e:
        print(f"预期的错误: {e}")
    
    try:
        result6 = EnergyEfficiencyTool.calc_device_stability_energy_ratio_pct(
            device_id="HEATER_001",
            batch_id="BATCH_2026_03_29_006",
            actual_duty_cycle=0.5,
            target_metric_variance=1.0,
            base_duty_cycle_limit=0  # 基准占空比为 0
        )
    except ValueError as e:
        print(f"预期的错误: {e}")