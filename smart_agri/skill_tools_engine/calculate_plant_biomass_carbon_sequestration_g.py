import pandas as pd
from datetime import datetime
from typing import List, Tuple

class EcoValueAnalytics:
    """
    生态价值与 ESG 分析工具包
    集成 MCP 语义规范，用于价值层特征提取
    """

    @staticmethod
    def calculate_plant_biomass_carbon_sequestration_g(
        air_co2_ppm_series: List[Tuple[datetime, float]],
        room_volume_m3: float = 100.0,
        temp_c: float = 25.0,
        pressure_kpa: float = 101.325,
        max_ppm_delta: float = 200.0,
        carbon_to_biomass_ratio: float = 0.6,
        device_id: str = None
    ) -> dict:
        """
        计算单位时间内植物通过光合作用固定的生物质碳量 (g)
        
        计算逻辑:
        1. 计算 CO2 浓度下降的总量 (仅统计日间光合作用导致的下降段)。
        2. 根据理想气体状态方程推算消耗的 CO2 质量: 
           m = (ΔP * V * M) / (R * T) 其中 ΔP 为分压变化。
        3. 转化系数: 每消耗 1g CO2，约产生 0.6g 生质干物质 (基于碳水化合物合成比例)。
        
        Args:
            air_co2_ppm_series: CO2 浓度序列 [(时间, ppm), ...]
            room_volume_m3: 密闭种植空间有效体积 (m³)
            temp_c: 平均气温，用于密度修正
            pressure_kpa: 大气压力 (kPa)，用于密度修正
            max_ppm_delta: 最大允许的 ppm 变化值，用于过滤异常跳变点
            carbon_to_biomass_ratio: 碳到生物质的转化系数
            device_id: 设备 ID，用于标识不同设备的计算
            
        Returns:
            dict: 包含固碳量、状态、决策理由和设备 ID 的字典
        
        SQL COMMENT:
        该指标用于评估植物通过光合作用固定的生物质碳量，基于日间 CO2 浓度下降斜率，
        利用理想气体状态方程推算植物光合作用产生的干物质重量。
        数据去向：esg_value_realization.biomass_carbon_sequestration_g
        属于 OpenClaw 架构中的 L4 价值实现层指标，为 ESG 价值评估提供数据支撑。
        """
        # 1. 数据防御与异常处理
        if not air_co2_ppm_series or len(air_co2_ppm_series) < 2:
            return {
                "value": 0.0,
                "unit": "g",
                "status": "warning",
                "reasoning_context": "CO2 浓度序列为空或长度不足，无法计算固碳量",
                "device_id": device_id
            }

        if room_volume_m3 <= 0:
            return {
                "value": 0.0,
                "unit": "g",
                "status": "warning",
                "reasoning_context": f"种植空间体积必须为正数: {room_volume_m3}",
                "device_id": device_id
            }

        if temp_c < -273.15 or temp_c > 100:
            return {
                "value": 0.0,
                "unit": "g",
                "status": "warning",
                "reasoning_context": f"温度值超出合理范围: {temp_c}°C",
                "device_id": device_id
            }

        if pressure_kpa <= 0 or pressure_kpa > 200:
            return {
                "value": 0.0,
                "unit": "g",
                "status": "warning",
                "reasoning_context": f"气压值超出合理范围: {pressure_kpa} kPa",
                "device_id": device_id
            }

        # 2. 按时间排序
        sorted_series = sorted(air_co2_ppm_series, key=lambda x: x[0])
        
        total_delta_ppm = 0.0
        valid_points = 0
        filtered_points = 0
        
        for i in range(len(sorted_series) - 1):
            val_start = sorted_series[i][1]
            val_end = sorted_series[i+1][1]
            
            # 仅统计浓度下降的部分 (光合作用消耗)
            diff = val_start - val_end
            if diff > 0:
                # 过滤异常跳变点
                if diff <= max_ppm_delta:
                    total_delta_ppm += diff
                    valid_points += 1
                else:
                    filtered_points += 1
        
        # 3. 高精度物理修正
        # 温度转换为开尔文
        temp_k = temp_c + 273.15
        
        # 理想气体状态方程计算 CO2 密度
        # M(CO2) = 44.01 g/mol
        # R = 8.314 J/(mol·K)
        # 压力转换为帕斯卡
        pressure_pa = pressure_kpa * 1000
        
        # 计算 CO2 摩尔质量 (g/mol)
        co2_molar_mass = 44.01
        
        # 理想气体常数
        gas_constant = 8.314
        
        # 计算 CO2 密度 (g/m³)
        co2_density = (pressure_pa * co2_molar_mass) / (gas_constant * temp_k)
        
        # 4. 将 ppm 转化为消耗的质量 (g)
        # 1 ppm = 10^-6 体积比
        consumed_co2_g = (total_delta_ppm * 1e-6) * room_volume_m3 * co2_density
        
        # 5. 转化为生物质干物质质量
        # 注：该系数应根据不同作物（如蓝莓 vs 中药材）从 policy_risk_thresholds 表动态获取
        plant_biomass_carbon_sequestration_g = consumed_co2_g * carbon_to_biomass_ratio
        
        # 6. 生成决策理由
        reasoning_context = f"在 {temp_c:.1f}°C/{pressure_kpa:.2f}kPa 下，累计有效下降 {total_delta_ppm:.2f}ppm，基于 {carbon_to_biomass_ratio} 转化率计算"
        if filtered_points > 0:
            reasoning_context += f"，过滤了 {filtered_points} 个异常跳变点"
        
        status = "success" if valid_points > 0 else "warning"
        if valid_points == 0:
            reasoning_context = "未检测到有效的 CO2 浓度下降，无法计算固碳量"
        
        return {
            "value": round(plant_biomass_carbon_sequestration_g, 4),
            "unit": "g",
            "status": status,
            "reasoning_context": reasoning_context,
            "device_id": device_id
        }

def run_analysis(data: pd.DataFrame, config: dict) -> dict:
    """
    统一入口函数 - 计算植物生物质固碳量
    
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
        room_volume_m3 = config.get('room_volume_m3', 100.0)
        temp_c = config.get('temp_c', 25.0)
        pressure_kpa = config.get('pressure_kpa', 101.325)
        max_ppm_delta = config.get('max_ppm_delta', 200.0)
        carbon_to_biomass_ratio = config.get('carbon_to_biomass_ratio', 0.6)
        
        # 从 DataFrame 中提取数据
        # 假设 DataFrame 包含 timestamp 和 co2_ppm 列
        if 'timestamp' not in data.columns or 'co2_ppm' not in data.columns:
            return {
                'data_status': 'INVALID',
                'error': 'Missing required columns: timestamp or co2_ppm'
            }
        
        # 构建 CO2 浓度序列
        air_co2_ppm_series = []
        for _, row in data.iterrows():
            timestamp = row['timestamp']
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            air_co2_ppm_series.append((timestamp, row['co2_ppm']))
        
        # 调用计算函数
        result = EcoValueAnalytics.calculate_plant_biomass_carbon_sequestration_g(
            air_co2_ppm_series=air_co2_ppm_series,
            room_volume_m3=room_volume_m3,
            temp_c=temp_c,
            pressure_kpa=pressure_kpa,
            max_ppm_delta=max_ppm_delta,
            carbon_to_biomass_ratio=carbon_to_biomass_ratio,
            device_id=device_id
        )
        
        # 转换结果格式，确保符合 AgriAnalyticalMetric 表字段
        return {
            'device_id': device_id,
            'batch_id': batch_id,
            'plant_biomass_carbon_sequestration_g': result['value'],
            'unit': result['unit'],
            'status': result['status'],
            'reasoning_context': result['reasoning_context']
        }
    except Exception as e:
        return {
            'data_status': 'INVALID',
            'error': str(e)
        }

# --- 模拟 ESG 数据汇总场景 ---
if __name__ == "__main__":
    # 模拟大棚下午 4 小时的 CO2 数据 (从 800ppm 下降到 400ppm)
    mock_co2_data = [
        (datetime(2026, 3, 28, 10, 0), 800.0),
        (datetime(2026, 3, 28, 12, 0), 600.0),
        (datetime(2026, 3, 28, 14, 0), 400.0),
    ]
    
    biomass_result = EcoValueAnalytics.calculate_plant_biomass_carbon_sequestration_g(
        mock_co2_data, 
        room_volume_m3=50.0,
        device_id="greenhouse_001"
    )
    
    print(f"--- 植物固碳量分析报告 ---")
    print(f"设备 ID: {biomass_result['device_id']}")
    print(f"密闭空间体积: 50 m³")
    print(f"今日累计固碳生物质 (plant_biomass_carbon_sequestration_g): {biomass_result['value']} {biomass_result['unit']}")
    print(f"状态: {biomass_result['status']}")
    print(f"计算背景: {biomass_result['reasoning_context']}")
    print(f"架构意义: 此数据已关联至 esg_value_realization.biomass_carbon_sequestration_g")