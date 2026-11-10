import pandas as pd

class ESGAccountingTool:
    """
    二级数据分析工具库 - 碳中和与 ESG 价值算法
    """

    # 中国电网平均排放因子 (2026参考值): 0.5703 kgCO2/kWh
    GRID_EMISSION_FACTOR = 0.5703

    @staticmethod
    def calculate_device_carbon_footprint_cumulative_g(
        runtime_hrs: float, 
        rated_power_w: float,
        device_id: str
    ) -> dict:
        """
        算法：设备运营碳足迹 (Operational Carbon Footprint)
        逻辑：将硬件运行时间转化为二氧化碳排放量。
        
        Args:
            runtime_hrs (float): 设备累计运行时间 (来自 device_digital_twin_status.runtime_total)
            rated_power_w (float): 设备额定功率 (单位: W)
            device_id (str): 设备 ID，用于标识不同设备的计算
            
        Returns:
            dict: 包含以下字段的字典：
                - value: 碳足迹值 (float|None)
                - unit: 单位，固定为 "g"
                - status: 状态，"success" | "error"
                - reasoning_context: 基于物理核算的详细描述
            
        SQL COMMENT:
        该指标用于 ESG 价值评估，通过分析设备运行时间和功率计算碳足迹。
        数据来源：device_digital_twin_status.runtime_total
        数据去向：esg_value_realization.operational_carbon_footprint_g
        属于 OpenClaw 架构中的 L4 ESG/价值层指标，作为 calculate_net_zero_ratio 的分母参与碳平衡率计算。
        """
        # 1. 数据防错：非负校验
        if runtime_hrs < 0:
            return {
                "value": None,
                "unit": "g",
                "status": "error",
                "reasoning_context": f"设备 {device_id} 的运行时间不能为负数: {runtime_hrs}"
            }
        
        if rated_power_w < 0:
            return {
                "value": None,
                "unit": "g",
                "status": "error",
                "reasoning_context": f"设备 {device_id} 的额定功率不能为负数: {rated_power_w}"
            }
        
        # 2. 单位标准化：Wh -> kWh
        energy_consumption_wh = runtime_hrs * rated_power_w
        energy_consumption_kwh = energy_consumption_wh / 1000.0
        
        # 3. 单位标准化：kWh -> kgCO2
        carbon_mass_kg = energy_consumption_kwh * ESGAccountingTool.GRID_EMISSION_FACTOR
        
        # 4. 单位标准化：kgCO2 -> gCO2
        carbon_mass_g = carbon_mass_kg * 1000.0
        
        # 5. 生成详细的物理核算描述
        reasoning_context = f"设备 {device_id} 累计运行 {runtime_hrs}h，按额定功率 {rated_power_w}W 核算，折合产生运营碳足迹 {round(carbon_mass_g, 2)}g。"
        
        # 6. 返回结构化结果
        return {
            "value": round(carbon_mass_g, 2),
            "unit": "g",
            "status": "success",
            "reasoning_context": reasoning_context
        }

    @staticmethod
    def calculate_net_zero_ratio(
        biomass_carbon_sequestration_g: float,
        operational_carbon_footprint_g: float,
        device_id: str
    ) -> dict:
        """
        算法：碳平衡率 (Net Zero Ratio)
        逻辑：计算生物质固碳量与运营碳足迹的比值，评估碳平衡程度。
        
        Args:
            biomass_carbon_sequestration_g: 生物质固碳量 (g)
            operational_carbon_footprint_g: 运营碳足迹 (g)，来自 calculate_device_carbon_footprint_cumulative_g
            device_id: 设备 ID，用于标识不同设备的计算
            
        Returns:
            dict: 包含碳平衡率值和决策理由的字典
            
        说明：
        - 当 operational_carbon_footprint_g 为 0 时，返回 0
        - 比值 >= 1 表示碳平衡或碳中和
        - 比值 < 1 表示碳赤字
        """
        # 占位函数，仅提供接口和说明
        # 实际实现需要根据具体业务逻辑进行开发
        pass

def run_analysis(data: pd.DataFrame, config: dict) -> dict:
    """
    统一入口函数 - 计算设备碳足迹
    
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
        rated_power_w = config.get('rated_power_w', 100.0)
        
        # 从 DataFrame 中提取数据
        # 假设 DataFrame 包含 runtime_hrs 列
        if 'runtime_hrs' not in data.columns:
            return {
                'data_status': 'INVALID',
                'error': 'Missing required column: runtime_hrs'
            }
        
        # 计算总运行时间
        runtime_hrs = data['runtime_hrs'].sum()
        
        # 调用计算函数
        result = ESGAccountingTool.calculate_device_carbon_footprint_cumulative_g(
            runtime_hrs=runtime_hrs,
            rated_power_w=rated_power_w,
            device_id=device_id
        )
        
        # 转换结果格式，确保符合 AgriAnalyticalMetric 表字段
        return {
            'device_id': device_id,
            'batch_id': batch_id,
            'device_carbon_footprint_cumulative_g': result['value'],
            'unit': result['unit'],
            'status': result['status'],
            'reasoning_context': result['reasoning_context']
        }
    except Exception as e:
        return {
            'data_status': 'INVALID',
            'error': str(e)
        }

# --- 模拟 ESG 价值计算上下文 ---
if __name__ == "__main__":
    # 模拟场景：一台额定功率 150W 的补光灯，本月累计运行了 240 小时
    mock_runtime = 240.0
    mock_power = 150.0 # 150 瓦
    
    footprint_g = ESGAccountingTool.calculate_device_carbon_footprint_cumulative_g(
        runtime_hrs=mock_runtime,
        rated_power_w=mock_power,
        device_id="device_001"
    )
    
    print(f"--- 碳足迹核算报告 (L4 ESG Value) ---")
    print(f"设备运行总时长: {mock_runtime} 小时")
    print(f"设备额定功率: {mock_power} W")
    print(f"核心指标 (device_carbon_footprint_cumulative_g): {footprint_g['value']} g CO2")
    print(f"状态: {footprint_g['status']}")
    print(f"决策理由: {footprint_g['reasoning_context']}")
    print(f"架构关联: 该数据将填入 esg_value_realization 表，并参与 net_zero_ratio 的计算。")