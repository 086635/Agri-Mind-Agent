import pandas as pd

class EcoValueSustainabilityAnalytics:
    """
    生态价值与碳中和分析工具包
    用于加工 ESG 价值层数据，量化系统的“数据资产”变现能力
    """

    @staticmethod
    def calculate_plant_net_zero_ratio(
        biomass_carbon_sequestration_g: float,
        operational_carbon_footprint_g: float,
        input_reliability_avg: float = 1.0,
        device_id: str = None,
        batch_id: str = None
    ) -> dict:
        """
        计算碳平衡率 (Net Zero Ratio)
        
        SQL COMMENT: 映射至 esg_value_realization.net_zero_ratio。计算逻辑：生物质固碳量/设备碳足迹。用于量化系统的生态变现与碳中和能力。
        
        计算逻辑:
        Ratio = 生物质固碳量 / 设备运行碳足迹
        - Ratio > 1.0: 实现局部碳负排放（Carbon Negative）
        - Ratio = 1.0: 达到碳中和（Carbon Neutral）
        - Ratio < 1.0: 碳正排放
        
        Args:
            biomass_carbon_sequestration_g (float): 植物通过光合作用固定的碳总量 (克)
            operational_carbon_footprint_g (float): 设备电力消耗折算的碳排放量 (克)
            input_reliability_avg (float): CO2 与 电能表数据的平均置信度 (默认 1.0)
            device_id (str): 设备 ID (可选)
            batch_id (str): 批次 ID (可选)
            
        Returns:
            dict: 包含 value、status、label、reasoning_context、device_id、batch_id 的字典
        """
        # 防止除以零异常（例如设备未开启的极限情况）
        if operational_carbon_footprint_g <= 0:
            # 如果有固碳但没耗电，理论上趋于无穷大，此处返回 99.99 表示极高
            if biomass_carbon_sequestration_g > 0:
                value = 99.99
                label = "Pure Green Asset"
            else:
                value = 0.0
                label = "Carbon Positive (排放抵消不足)"
        else:
            # 核心逻辑计算
            net_zero_ratio = biomass_carbon_sequestration_g / operational_carbon_footprint_g
            value = round(net_zero_ratio, 3)
            
            # 确定标签
            if value > 1.0:
                label = "Carbon Negative (局部碳负排放)"
            elif 0.95 <= value <= 1.05:
                label = "Carbon Neutral (趋近碳中和)"
            else:
                label = "Carbon Positive (排放抵消不足)"
        
        # 确定状态
        status = "warning" if input_reliability_avg < 0.7 else "success"
        
        # 构建 reasoning_context
        reasoning_context = f"计算逻辑: 生物质固碳量 {biomass_carbon_sequestration_g}g / 设备碳足迹 {operational_carbon_footprint_g}g = {value}"
        
        # 添加数据质量警告
        if input_reliability_avg < 0.7:
            reasoning_context += "\nESG 数据可信度低，建议校准 CO2 传感器或检查电表网关"
        
        # 添加主动控制反馈
        if value < 0.8:
            reasoning_context += "\n当前碳平衡率较低，建议优化补光策略或核查风扇能效比"
        elif value > 1.2:
            reasoning_context += "\n系统表现优异，可生成绿色资产证明用于品牌宣传"
        
        # 返回结果
        return {
            "value": value,
            "status": status,
            "label": label,
            "reasoning_context": reasoning_context,
            "device_id": device_id,
            "batch_id": batch_id
        }

def run_analysis(data: pd.DataFrame, config: dict) -> dict:
    """
    统一入口函数 - 计算植物碳平衡率
    
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
        input_reliability_avg = config.get('input_reliability_avg', 1.0)
        
        # 从 DataFrame 中提取数据
        # 假设 DataFrame 包含 biomass_carbon_sequestration_g 和 operational_carbon_footprint_g 列
        if 'biomass_carbon_sequestration_g' not in data.columns or 'operational_carbon_footprint_g' not in data.columns:
            return {
                'data_status': 'INVALID',
                'error': 'Missing required columns: biomass_carbon_sequestration_g or operational_carbon_footprint_g'
            }
        
        # 提取数据值
        biomass_carbon_sequestration_g = data['biomass_carbon_sequestration_g'].sum()
        operational_carbon_footprint_g = data['operational_carbon_footprint_g'].sum()
        
        # 调用计算函数
        result = EcoValueSustainabilityAnalytics.calculate_plant_net_zero_ratio(
            biomass_carbon_sequestration_g=biomass_carbon_sequestration_g,
            operational_carbon_footprint_g=operational_carbon_footprint_g,
            input_reliability_avg=input_reliability_avg,
            device_id=device_id,
            batch_id=batch_id
        )
        
        # 转换结果格式，确保符合 AgriAnalyticalMetric 表字段
        return {
            'device_id': device_id,
            'batch_id': batch_id,
            'net_zero_ratio': result['value'],
            'status': result['status'],
            'label': result['label'],
            'reasoning_context': result['reasoning_context']
        }
    except Exception as e:
        return {
            'data_status': 'INVALID',
            'error': str(e)
        }

# --- 模拟 ESG 报表生成场景 ---
if __name__ == "__main__":
    # 模拟数据：
    # 一个月内，大棚蓝莓估算固碳 5000g
    # 补光灯与水泵耗电折算碳排放 4200g
    sequestration = 5000.0
    emissions = 4200.0
    
    # 测试正常场景
    result = EcoValueSustainabilityAnalytics.calculate_plant_net_zero_ratio(
        sequestration, 
        emissions,
        device_id="greenhouse_001",
        batch_id="batch_2024_01"
    )
    
    print(f"--- 碳资产评估报告 ---")
    print(f"生物质固碳量: {sequestration} g")
    print(f"设备碳足迹: {emissions} g")
    print(f"当前碳平衡率 (net_zero_ratio): {result['value']}")
    print(f"状态: {result['status']}")
    print(f"标签: {result['label']}")
    print(f"设备 ID: {result['device_id']}")
    print(f"批次 ID: {result['batch_id']}")
    print(f"详细说明: {result['reasoning_context']}")
    
    # 测试低置信度场景
    print("\n--- 低置信度场景测试 ---")
    result_low_conf = EcoValueSustainabilityAnalytics.calculate_plant_net_zero_ratio(
        sequestration, 
        emissions,
        input_reliability_avg=0.5,
        device_id="greenhouse_001",
        batch_id="batch_2024_01"
    )
    print(f"碳平衡率: {result_low_conf['value']}")
    print(f"状态: {result_low_conf['status']}")
    print(f"标签: {result_low_conf['label']}")
    print(f"详细说明: {result_low_conf['reasoning_context']}")
    
    # 测试纯绿色资产场景
    print("\n--- 纯绿色资产场景测试 ---")
    result_pure_green = EcoValueSustainabilityAnalytics.calculate_plant_net_zero_ratio(
        1000.0, 
        0.0,
        device_id="greenhouse_001",
        batch_id="batch_2024_01"
    )
    print(f"碳平衡率: {result_pure_green['value']}")
    print(f"状态: {result_pure_green['status']}")
    print(f"标签: {result_pure_green['label']}")
    print(f"详细说明: {result_pure_green['reasoning_context']}")