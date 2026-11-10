from typing import Dict, Optional

class ESGAccountingTool:
    """
    二级数据分析工具库 - 碳中和与 ESG 价值算法
    """

    # 中国电网平均排放因子 (2026参考值): 0.5703 kgCO2/kWh
    GRID_EMISSION_FACTOR = 0.5703

    @staticmethod
    def sync_device_carbon_to_esg_metrics(
        device_id: str,
        batch_id: str,
        runtime_hrs: float,
        rated_power_w: float,
        duty_cycle_ratio: float = 1.0,
        biomass_carbon_sequestration_g: Optional[float] = None
    ) -> Dict:
        """
        SQL COMMENT: 聚合表3的runtime_total，计算结果回填至表4的operational_carbon_footprint_g字段。
        
        算法：设备运营碳足迹 (Operational Carbon Footprint)
        逻辑：将硬件运行时间转化为二氧化碳排放量，并计算碳平衡率。
        
        Args:
            device_id (str): 设备ID
            batch_id (str): 批次ID
            runtime_hrs (float): 设备累计运行时间 (来自 device_digital_twin_status.runtime_total)
            rated_power_w (float): 设备额定功率 (单位: W)
            duty_cycle_ratio (float): 占空比，默认全功率运行
            biomass_carbon_sequestration_g (Optional[float]): 生物固碳量 (单位: g)
            
        Returns:
            Dict: 包含设备碳足迹和ESG指标的字典
        """
        # 1. 计算实际耗电量 (Wh -> kWh)，考虑占空比
        energy_consumption_kwh = (runtime_hrs * rated_power_w * duty_cycle_ratio) / 1000.0
        
        # 2. 转化为碳排放 (kg -> g)
        carbon_mass_kg = energy_consumption_kwh * ESGAccountingTool.GRID_EMISSION_FACTOR
        operational_carbon_footprint_g = carbon_mass_kg * 1000.0
        operational_carbon_footprint_g = round(operational_carbon_footprint_g, 2)
        
        # 3. 计算碳平衡率
        if operational_carbon_footprint_g == 0:
            net_zero_ratio = 100.0
        elif biomass_carbon_sequestration_g is not None:
            net_zero_ratio = biomass_carbon_sequestration_g / operational_carbon_footprint_g
            net_zero_ratio = round(net_zero_ratio, 2)
        else:
            net_zero_ratio = 0.0
        
        # 4. 生成决策理由
        if operational_carbon_footprint_g > 0:
            if biomass_carbon_sequestration_g is not None and net_zero_ratio > 1:
                reasoning_context = f"该设备本月排放 {operational_carbon_footprint_g}g CO2，碳平衡率为 {net_zero_ratio}，已实现局部碳负排放"
            else:
                reasoning_context = f"该设备本月排放 {operational_carbon_footprint_g}g CO2，碳平衡率为 {net_zero_ratio}"
        else:
            reasoning_context = "该设备本月无碳排放，碳平衡率为 100.0，已实现完全碳中和"
        
        # 5. 返回结果
        return {
            "device_id": device_id,
            "batch_id": batch_id,
            "operational_carbon_footprint_g": operational_carbon_footprint_g,
            "net_zero_ratio": net_zero_ratio,
            "reasoning_context": reasoning_context
        }

# --- 模拟 ESG 价值计算上下文 ---
if __name__ == "__main__":
    # 模拟运行时间
    mock_runtime = 240.0  # 小时
    
    # 模拟生物固碳量（假设值）
    mock_biomass_carbon = 500.0  # g
    
    # 场景 1: 高效 LED 补光灯 (150W)
    print("=== 场景 1: 高效 LED 补光灯 (150W) ===")
    led_result = ESGAccountingTool.sync_device_carbon_to_esg_metrics(
        device_id="led_001",
        batch_id="batch_202603",
        runtime_hrs=mock_runtime,
        rated_power_w=150.0,
        duty_cycle_ratio=0.8,  # 假设 80% 功率运行
        biomass_carbon_sequestration_g=mock_biomass_carbon
    )
    
    print(f"设备 ID: {led_result['device_id']}")
    print(f"批次 ID: {led_result['batch_id']}")
    print(f"运行时间: {mock_runtime} 小时")
    print(f"额定功率: 150 W")
    print(f"占空比: 0.8")
    print(f"碳足迹: {led_result['operational_carbon_footprint_g']} g CO2")
    print(f"碳平衡率: {led_result['net_zero_ratio']}")
    print(f"决策理由: {led_result['reasoning_context']}")
    print()
    
    # 场景 2: 传统高压钠灯 (400W)
    print("=== 场景 2: 传统高压钠灯 (400W) ===")
    sodium_result = ESGAccountingTool.sync_device_carbon_to_esg_metrics(
        device_id="sodium_001",
        batch_id="batch_202603",
        runtime_hrs=mock_runtime,
        rated_power_w=400.0,
        duty_cycle_ratio=1.0,  # 全功率运行
        biomass_carbon_sequestration_g=mock_biomass_carbon
    )
    
    print(f"设备 ID: {sodium_result['device_id']}")
    print(f"批次 ID: {sodium_result['batch_id']}")
    print(f"运行时间: {mock_runtime} 小时")
    print(f"额定功率: 400 W")
    print(f"占空比: 1.0")
    print(f"碳足迹: {sodium_result['operational_carbon_footprint_g']} g CO2")
    print(f"碳平衡率: {sodium_result['net_zero_ratio']}")
    print(f"决策理由: {sodium_result['reasoning_context']}")
    print()
    
    # 对比分析
    print("=== 对比分析 ===")
    carbon_diff = sodium_result['operational_carbon_footprint_g'] - led_result['operational_carbon_footprint_g']
    ratio_diff = led_result['net_zero_ratio'] - sodium_result['net_zero_ratio']
    print(f"LED 补光灯相比传统高压钠灯节省碳排放: {carbon_diff:.2f} g CO2")
    print(f"LED 补光灯相比传统高压钠灯碳平衡率提升: {ratio_diff:.2f}")


# --- MCP 协议调用说明 ---
"""
MCP (Model Context Protocol) 接口对接说明：

1. 此模块可作为 MCP 工具函数集成到 Trae 技能系统中
2. 对接方式：
   - 在 MCP 配置文件中注册此工具函数
   - 输入参数：
     {
       "device_id": "设备ID",
       "batch_id": "批次ID",
       "runtime_hrs": 设备运行时间,
       "rated_power_w": 设备额定功率,
       "duty_cycle_ratio": 0.8,  # 可选，默认 1.0
       "biomass_carbon_sequestration_g": 500.0  # 可选
     }
   - 输出：结构化 JSON 报告，可直接返回给调用方

3. 数据来源：
   - runtime_hrs: 从表 3 (device_digital_twin_status) 的 runtime_total 字段获取
   - rated_power_w: 从设备元数据中获取
   - duty_cycle_ratio: 从表 3 (device_digital_twin_status) 的 duty_cycle 字段获取
   - biomass_carbon_sequestration_g: 从表 4 (esg_value_realization) 的相应字段获取

4. 集成建议：
   - 可在 Agent 决策过程中调用此 Skill，根据设备碳足迹和碳平衡率调整设备运行策略
   - 可定期运行此 Skill，更新表 4 (esg_value_realization) 的 operational_carbon_footprint_g 字段
   - 可将此 Skill 与其他 ESG 相关 Skill 组合使用，构建完整的 ESG 评估体系
"""
