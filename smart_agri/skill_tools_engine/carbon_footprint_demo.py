from calculate_device_stability_energy_ratio_pct import EnergyEfficiencyTool


class ESGCounterTool:
    """
    ESG 价值核算工具类
    用于计算设备碳足迹和 ESG 价值
    """

    # 不同地区的电网排放因子 (单位: g CO2/kWh)
    REGIONAL_EMISSION_FACTORS = {
        "CN_HZ": 600,  # 中国杭州
        "CN_BJ": 580,  # 中国北京
        "CN_SH": 590,  # 中国上海
        "US_CA": 300,  # 美国加州
        "EU_DE": 200   # 德国
    }

    @staticmethod
    def calculate_device_carbon_footprint_g(
        energy_efficiency_ratio: float,  # 能效比（百分比）
        device_power: float,  # 设备功率 (kW)
        operation_hours: float,  # 运行时间 (h)
        device_id: str,  # 设备 ID
        batch_id: str,  # 批次 ID
        reliability_score: float = 1.0,  # 数据可靠性评分
        location_code: str = "CN_HZ"  # 地域代码
    ) -> dict:
        """
        计算设备运行碳足迹

        SQL COMMENT: 映射至 esg_value_realization.operational_carbon_footprint_g。
        计算逻辑：实际能耗(kWh) * 电网排放因子。

        Args:
            energy_efficiency_ratio: 能效比（百分比），正值表示节能
            device_power: 设备功率 (kW)
            operation_hours: 运行时间 (h)
            device_id: 设备 ID
            batch_id: 批次 ID
            reliability_score: 数据可靠性评分 (默认 1.0)
            location_code: 地域代码 (默认 "CN_HZ")

        Returns:
            dict: 包含碳足迹计算结果的字典
        """
        # 确定状态
        status = "success"
        if reliability_score < 0.7:
            status = "warning"

        # 获取地域排放因子
        grid_emission_factor = ESGCounterTool.REGIONAL_EMISSION_FACTORS.get(
            location_code, ESGCounterTool.REGIONAL_EMISSION_FACTORS["CN_HZ"]
        )

        # 基准能耗 (kWh)
        baseline_energy = device_power * operation_hours

        # 实际能耗 (kWh) = 基准能耗 * (1 - 能效比/100)
        actual_energy = baseline_energy * (1 - energy_efficiency_ratio / 100)

        # 能耗冗余校验：实际能耗不能超过设备额定功率在统计周期内的理论最大值
        theoretical_max_energy = device_power * operation_hours
        if actual_energy > theoretical_max_energy:
            status = "error"
            # 计算碳足迹和碳减排量（即使超限也计算，以便提供完整信息）
            operational_carbon_footprint_g = (
                actual_energy * grid_emission_factor
            )
            carbon_reduction = (
                (baseline_energy - actual_energy) * grid_emission_factor
            )
            return {
                "status": status,
                "reasoning_context": "数据超限，请检查表 3 运行时间统计是否存在坏账",
                "operational_carbon_footprint_g": round(
                    operational_carbon_footprint_g, 2
                ),
                "baseline_energy": round(baseline_energy, 2),
                "actual_energy": round(actual_energy, 2),
                "carbon_reduction": round(carbon_reduction, 2),
                "theoretical_max_energy": round(theoretical_max_energy, 2),
                "energy_efficiency_ratio": energy_efficiency_ratio,
                "grid_emission_factor": grid_emission_factor,
                "device_id": device_id,
                "batch_id": batch_id,
                "location_code": location_code
            }

        # 计算碳足迹 (g CO2)
        operational_carbon_footprint_g = actual_energy * grid_emission_factor

        # 计算碳减排量 (g CO2)
        carbon_reduction = (
            (baseline_energy - actual_energy) * grid_emission_factor
        )

        # 构建决策理由
        reasoning_context = (
            f"本周期（{operation_hours}h）设备 {device_id} 运行，"
            f"AI 优化后的能效比为 {energy_efficiency_ratio}%，"
            f"对比基准节省了 {round(carbon_reduction, 2)} g 碳排放，"
            "数据已同步至 ESG 资产表。"
        )

        # 添加置信度警告
        if reliability_score < 0.7:
            reasoning_context += "\n数据可靠性评分较低，计算结果可能存在误差"

        # 返回结果
        return {
            "status": status,
            "reasoning_context": reasoning_context,
            "operational_carbon_footprint_g": round(
                operational_carbon_footprint_g, 2
            ),
            "baseline_energy": round(baseline_energy, 2),
            "actual_energy": round(actual_energy, 2),
            "carbon_reduction": round(carbon_reduction, 2),
            "energy_efficiency_ratio": energy_efficiency_ratio,
            "grid_emission_factor": grid_emission_factor,
            "device_id": device_id,
            "batch_id": batch_id,
            "location_code": location_code
        }


# 设备功率示例 (单位: kW)
DEVICE_POWER = 10.0  # 10kW 设备

# 运行时间 (单位: 小时)
OPERATION_HOURS = 24  # 一天运行24小时


if __name__ == "__main__":
    print("=== 能效比到碳足迹转化演示 ===")
    print(f"设备功率: {DEVICE_POWER} kW")
    print(f"运行时间: {OPERATION_HOURS} 小时")
    print(
        f"默认电网排放因子 (杭州): "
        f"{ESGCounterTool.REGIONAL_EMISSION_FACTORS['CN_HZ']} g CO2/kWh"
    )
    print()

    # 场景 1: AI 节能显著场景（杭州基地）
    print("场景 1: AI 节能显著场景（杭州基地）")
    result_saving = EnergyEfficiencyTool.calculate_device_stability_energy_ratio_pct(
        actual_duty_cycle=0.2,
        target_metric_variance=0.15,
        base_duty_cycle_limit=0.5,
        device_id="device_001"
    )

    print(f"能效比: {result_saving['value']}%")
    print(f"状态: {result_saving['status']}")
    print("详细说明:")
    print(f"{result_saving['reasoning_context']}")

    carbon_result_saving = ESGCounterTool.calculate_device_carbon_footprint_g(
        energy_efficiency_ratio=result_saving['value'],
        device_power=DEVICE_POWER,
        operation_hours=OPERATION_HOURS,
        device_id="device_001",
        batch_id="batch_2024_01",
        location_code="CN_HZ"
    )

    print(f"基准能耗: {carbon_result_saving['baseline_energy']} kWh")
    print(f"实际能耗: {carbon_result_saving['actual_energy']} kWh")
    print(
        f"运行碳足迹: "
        f"{carbon_result_saving['operational_carbon_footprint_g']} g CO2"
    )
    print(f"碳减排量: {carbon_result_saving['carbon_reduction']} g CO2")
    print(f"状态: {carbon_result_saving['status']}")
    print("详细说明:")
    print(f"{carbon_result_saving['reasoning_context']}")
    print()

    # 场景 2: AI 费能场景（杭州基地）
    print("场景 2: AI 费能场景（杭州基地）")
    result_wasting = EnergyEfficiencyTool.calculate_device_stability_energy_ratio_pct(
        actual_duty_cycle=0.6,
        target_metric_variance=0.15,
        base_duty_cycle_limit=0.5,
        device_id="device_001"
    )

    print(f"能效比: {result_wasting['value']}%")
    print(f"状态: {result_wasting['status']}")
    print("详细说明:")
    print(f"{result_wasting['reasoning_context']}")

    carbon_result_wasting = ESGCounterTool.calculate_device_carbon_footprint_g(
        energy_efficiency_ratio=result_wasting['value'],
        device_power=DEVICE_POWER,
        operation_hours=OPERATION_HOURS,
        device_id="device_001",
        batch_id="batch_2024_01",
        location_code="CN_HZ"
    )

    print(f"基准能耗: {carbon_result_wasting['baseline_energy']} kWh")
    print(f"实际能耗: {carbon_result_wasting['actual_energy']} kWh")
    print(
        f"运行碳足迹: "
        f"{carbon_result_wasting['operational_carbon_footprint_g']} g CO2"
    )
    print(f"碳减排量: {carbon_result_wasting['carbon_reduction']} g CO2")
    print(f"状态: {carbon_result_wasting['status']}")
    print("详细说明:")
    print(f"{carbon_result_wasting['reasoning_context']}")
    print()

    # 场景 3: 低置信度场景（杭州基地）
    print("场景 3: 低置信度场景（杭州基地）")
    carbon_result_low_conf = ESGCounterTool.calculate_device_carbon_footprint_g(
        energy_efficiency_ratio=20.0,  # 假设能效比为 20%
        device_power=DEVICE_POWER,
        operation_hours=OPERATION_HOURS,
        device_id="device_001",
        batch_id="batch_2024_01",
        reliability_score=0.5,
        location_code="CN_HZ"
    )

    print(f"能效比: 20.0%")
    print(
        f"运行碳足迹: "
        f"{carbon_result_low_conf['operational_carbon_footprint_g']} g CO2"
    )
    print(f"碳减排量: {carbon_result_low_conf['carbon_reduction']} g CO2")
    print(f"状态: {carbon_result_low_conf['status']}")
    print("详细说明:")
    print(f"{carbon_result_low_conf['reasoning_context']}")
    print()

    # 场景 4: 能耗超限场景（杭州基地）
    print("场景 4: 能耗超限场景（杭州基地）")
    # 能效比为负数，表示能耗增加，实际能耗超过理论最大值
    carbon_result_overlimit = ESGCounterTool.calculate_device_carbon_footprint_g(
        energy_efficiency_ratio=-50.0,  # 假设能效比为 -50%，表示能耗增加 50%
        device_power=DEVICE_POWER,
        operation_hours=OPERATION_HOURS,
        device_id="device_001",
        batch_id="batch_2024_01",
        location_code="CN_HZ"
    )

    print(f"能效比: -50.0%")
    print(f"状态: {carbon_result_overlimit['status']}")
    print("详细说明:")
    print(f"{carbon_result_overlimit['reasoning_context']}")
    print()

    print("=== 结论 ===")
    print("通过能效比计算，可以量化 AI 控制策略对碳足迹的影响：")
    print(
        f"1. 节能场景下，碳减排量: {carbon_result_saving['carbon_reduction']} g CO2"
    )
    print(
        f"2. 费能场景下，额外碳排放: "
        f"{abs(carbon_result_wasting['carbon_reduction'])} g CO2"
    )
    print("3. 能耗超限场景下，系统会返回错误状态并提示数据超限")
    print("这展示了 AI 控制策略在 ESG 价值评估中的重要性。")
