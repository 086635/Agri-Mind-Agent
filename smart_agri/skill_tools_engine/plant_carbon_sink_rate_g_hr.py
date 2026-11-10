import numpy as np
from datetime import datetime
from typing import List, Tuple, Dict, Any

class GrowthAnalysisTool:
    """
    二级数据分析工具库 - 植物生长动力学算法
    """

    @staticmethod
    def calc_plant_carbon_sink_rate_g_hr(
        device_id: str,
        batch_id: str,
        co2_time_series: List[Tuple[datetime, float]], 
        chamber_volume_m3: float,
        air_temp_c: float,
        chamber_pressure_hpa: float = 1013.25,
        is_ventilation_active: bool = False
    ) -> Dict[str, Any]:
        """
        SQL COMMENT: 自动提取表1(raw_environmental_readings)的co2_ppm序列，联动表3(device_digital_twin_status)的通风开关状态，计算碳汇速率并回填至表2(carbon_sink_rate)。
        
        算法：光合碳汇速率 (Photosynthetic Carbon Sink Rate)
        逻辑：基于理想气体方程，将密闭空间内 CO2 的 ppm 下降速率转化为克/小时。
        
        Args:
            device_id: 设备唯一标识符
            batch_id: 批次唯一标识符
            co2_time_series: [(时间, CO2_ppm), ...] 至少需要两个采样点
            chamber_volume_m3: 密闭空间/温室的有效体积 (立方米)
            air_temp_c: 当前环境平均温度
            chamber_pressure_hpa: 舱内气压 (百帕)，默认标准大气压
            is_ventilation_active: 设备干预标记。如果通风开启，则计算无效，返回 0.0
            
        Returns:
            Dict[str, Any]: 包含碳汇速率、置信度、干物质估算等信息的字典
            - device_id: 设备唯一标识符
            - batch_id: 批次唯一标识符
            - carbon_sink_rate_g_hr: 碳汇速率 (g/hr)。正数代表吸收，负数代表释放(呼吸)
            - data_reliability_score: 数据可靠性评分 (0-100)
            - daily_dry_matter_est_g: 每日干物质估算 (g)
        """
        # 1. 异常与边界处理
        try:
            # 安全校验：如果正在通风或数据不足，无法计算有效的闭合变化
            if is_ventilation_active or len(co2_time_series) < 2:
                return {
                    "device_id": device_id,
                    "batch_id": batch_id,
                    "carbon_sink_rate_g_hr": 0.0,
                    "data_reliability_score": 0,
                    "daily_dry_matter_est_g": 0.0
                }

            # 数据有效性检查
            for timestamp, ppm in co2_time_series:
                if not isinstance(timestamp, datetime):
                    return {
                        "device_id": device_id,
                        "batch_id": batch_id,
                        "carbon_sink_rate_g_hr": 0.0,
                        "data_reliability_score": 0,
                        "daily_dry_matter_est_g": 0.0
                    }
                if not isinstance(ppm, (int, float)) or ppm < 0:
                    return {
                        "device_id": device_id,
                        "batch_id": batch_id,
                        "carbon_sink_rate_g_hr": 0.0,
                        "data_reliability_score": 0,
                        "daily_dry_matter_est_g": 0.0
                    }

            # 参数范围检查
            if chamber_volume_m3 <= 0:
                return {
                    "device_id": device_id,
                    "batch_id": batch_id,
                    "carbon_sink_rate_g_hr": 0.0,
                    "data_reliability_score": 0,
                    "daily_dry_matter_est_g": 0.0
                }

            if chamber_pressure_hpa <= 0:
                return {
                    "device_id": device_id,
                    "batch_id": batch_id,
                    "carbon_sink_rate_g_hr": 0.0,
                    "data_reliability_score": 0,
                    "daily_dry_matter_est_g": 0.0
                }

            # 2. 提取时间(小时)和浓度(ppm)
            times = np.array([(t[0] - co2_time_series[0][0]).total_seconds() / 3600.0 for t in co2_time_series])
            ppm_values = np.array([t[1] for t in co2_time_series])

            # 3. 线性回归计算斜率 (dC/dt) - ppm/hr
            # 我们关注下降速率，如果斜率为负，说明植物在吸收
            slope, intercept = np.polyfit(times, ppm_values, 1)
            
            # 4. 物理转换：ppm -> g/m³ -> g_total
            # 理想气体常数修正后的 CO2 摩尔质量转换
            # 考虑气压补偿的完整公式
            molar_mass_co2 = 44.01  # g/mol
            ideal_gas_constant = 8.314  # J/(mol·K)
            temp_k = 273.15 + air_temp_c  # 开尔文温度
            pressure_pa = chamber_pressure_hpa * 100  # 转换为帕斯卡
            
            # ppm 变化转质量变化 (mg/m³ / ppm)
            # 使用理想气体定律进行更精确的计算
            # 1 ppm = 1e-6 体积分数
            # 计算1立方米空气中的总摩尔数
            total_moles_per_m3 = pressure_pa / (ideal_gas_constant * temp_k)
            # 计算1 ppm CO2的摩尔数
            co2_moles_per_m3_per_ppm = total_moles_per_m3 * 1e-6
            # 转换为质量 (mg/m³ / ppm)
            mg_per_m3_per_ppm = co2_moles_per_m3_per_ppm * molar_mass_co2 * 1000
            
            # 总质量变化率 (g/hr) = (ppm/hr) * (mg/m³/ppm) * m³ / 1000
            # 注意：植物吸收 CO2，浓度下降，slope 为负，所以我们取反得到吸收速率
            sink_rate_g_hr = -slope * mg_per_m3_per_ppm * chamber_volume_m3 / 1000.0

            # 5. 置信度评分系统
            data_reliability_score = GrowthAnalysisTool._calculate_confidence(
                co2_time_series, slope, ppm_values
            )

            # 6. ESG 价值转化：计算每日干物质估算
            # 基于“每消耗 1kg CO2 产生约 0.6kg 干物质”的生物学常数
            # 假设每日光照时间为 12 小时
            daily_light_hours = 12.0
            daily_co2_absorption_g = max(sink_rate_g_hr, 0) * daily_light_hours
            daily_dry_matter_est_g = daily_co2_absorption_g * 0.6  # 0.6kg 干物质 / 1kg CO2

            # 7. 结果限制和四舍五入
            sink_rate_g_hr = round(max(sink_rate_g_hr, -5.0), 4)  # 允许轻微负值表示净呼吸，但设限防止异常
            daily_dry_matter_est_g = round(daily_dry_matter_est_g, 2)

            return {
                "device_id": device_id,
                "batch_id": batch_id,
                "carbon_sink_rate_g_hr": sink_rate_g_hr,
                "data_reliability_score": data_reliability_score,
                "daily_dry_matter_est_g": daily_dry_matter_est_g
            }
        except Exception as e:
            return {
                "device_id": device_id,
                "batch_id": batch_id,
                "carbon_sink_rate_g_hr": 0.0,
                "data_reliability_score": 0,
                "daily_dry_matter_est_g": 0.0
            }

    @staticmethod
    def _calculate_confidence(co2_time_series: List[Tuple[datetime, float]], slope: float, ppm_values: np.ndarray) -> int:
        """
        计算置信度评分
        
        Args:
            co2_time_series: CO2时间序列数据
            slope: 线性回归斜率
            ppm_values: CO2浓度值数组
            
        Returns:
            int: 置信度评分 (0-100)
        """
        score = 0
        
        # 1. 数据点数量评分 (最高40分)
        data_points = len(co2_time_series)
        if data_points >= 5:
            score += 40
        elif data_points >= 3:
            score += 25
        else:  # 至少2个点
            score += 10
        
        # 2. 测量时间跨度评分 (最高20分)
        duration_hr = (co2_time_series[-1][0] - co2_time_series[0][0]).total_seconds() / 3600.0
        if duration_hr >= 0.5:  # 30分钟
            score += 20
        elif duration_hr >= 0.1667:  # 10分钟
            score += 15
        else:
            score += 5
        
        # 3. 数据一致性评分 (最高20分)
        # 计算R²值
        times = np.array([(t[0] - co2_time_series[0][0]).total_seconds() / 3600.0 for t in co2_time_series])
        mean_ppm = np.mean(ppm_values)
        ss_total = np.sum((ppm_values - mean_ppm) ** 2)
        ss_residual = np.sum((ppm_values - (slope * times + np.mean(ppm_values))) ** 2)
        r_squared = 1 - (ss_residual / ss_total) if ss_total > 0 else 0
        
        if r_squared >= 0.95:
            score += 20
        elif r_squared >= 0.8:
            score += 15
        elif r_squared >= 0.6:
            score += 10
        else:
            score += 5
        
        # 4. 变化幅度评分 (最高20分)
        max_ppm = np.max(ppm_values)
        min_ppm = np.min(ppm_values)
        ppm_range = max_ppm - min_ppm
        
        if ppm_range >= 50:
            score += 20
        elif ppm_range >= 20:
            score += 15
        elif ppm_range >= 5:
            score += 10
        else:
            score += 5
        
        return min(score, 100)

    @staticmethod
    def _calculate_esg_value(sink_rate_g_hr: float, confidence_score: int) -> float:
        """
        计算ESG价值
        
        Args:
            sink_rate_g_hr: 碳汇速率 (g/hr)
            confidence_score: 置信度评分 (0-100)
            
        Returns:
            float: ESG价值评估
        """
        # 基础ESG价值：基于碳汇速率
        base_esg = max(sink_rate_g_hr, 0) * 0.01  # 假设每克CO2吸收价值0.01单位
        
        # 置信度调整
        confidence_factor = confidence_score / 100.0
        
        # 最终ESG价值
        esg_value = base_esg * confidence_factor
        
        return esg_value

# --- 模拟 OpenClaw 技能调用上下文 ---
if __name__ == "__main__":
    # 测试场景1: 密闭蓝莓育苗箱场景
    print("=== 测试场景1: 密闭蓝莓育苗箱场景 ===")
    # 模拟 10 分钟内的 3 次采样 (10m³ 的密闭生长箱)
    mock_data1 = [
        (datetime(2026, 3, 28, 10, 0), 800.0),
        (datetime(2026, 3, 28, 10, 5), 785.0),
        (datetime(2026, 3, 28, 10, 10), 770.0)
    ]
    
    result1 = GrowthAnalysisTool.calc_plant_carbon_sink_rate_g_hr(
        device_id="BLUEBERRY_GREENHOUSE_001",
        batch_id="BATCH-20260328-001",
        co2_time_series=mock_data1,
        chamber_volume_m3=10.0,  # 10 立方米
        air_temp_c=25.0,  # 25 摄氏度
        chamber_pressure_hpa=1013.25  # 标准大气压
    )
    
    print(f"设备ID: {result1['device_id']}")
    print(f"批次ID: {result1['batch_id']}")
    print(f"碳汇速率: {result1['carbon_sink_rate_g_hr']} g/hr")
    print(f"数据可靠性评分: {result1['data_reliability_score']}/100")
    print(f"每日干物质估算: {result1['daily_dry_matter_est_g']} g")
    print()
    
    # 测试场景2: 通风开启情况
    print("=== 测试场景2: 通风开启情况 ===")
    result2 = GrowthAnalysisTool.calc_plant_carbon_sink_rate_g_hr(
        device_id="BLUEBERRY_GREENHOUSE_001",
        batch_id="BATCH-20260328-002",
        co2_time_series=mock_data1,
        chamber_volume_m3=10.0,
        air_temp_c=25.0,
        is_ventilation_active=True
    )
    
    print(f"设备ID: {result2['device_id']}")
    print(f"批次ID: {result2['batch_id']}")
    print(f"碳汇速率: {result2['carbon_sink_rate_g_hr']} g/hr")
    print(f"数据可靠性评分: {result2['data_reliability_score']}/100")
    print(f"每日干物质估算: {result2['daily_dry_matter_est_g']} g")
    print()
    
    # 测试场景3: 数据点不足情况
    print("=== 测试场景3: 数据点不足情况 ===")
    mock_data3 = [
        (datetime(2026, 3, 28, 10, 0), 800.0)
    ]
    
    result3 = GrowthAnalysisTool.calc_plant_carbon_sink_rate_g_hr(
        device_id="BLUEBERRY_GREENHOUSE_001",
        batch_id="BATCH-20260328-003",
        co2_time_series=mock_data3,
        chamber_volume_m3=10.0,
        air_temp_c=25.0
    )
    
    print(f"设备ID: {result3['device_id']}")
    print(f"批次ID: {result3['batch_id']}")
    print(f"碳汇速率: {result3['carbon_sink_rate_g_hr']} g/hr")
    print(f"数据可靠性评分: {result3['data_reliability_score']}/100")
    print(f"每日干物质估算: {result3['daily_dry_matter_est_g']} g")
    print()
    
    # 测试场景4: 不同气压情况
    print("=== 测试场景4: 不同气压情况 ===")
    result4 = GrowthAnalysisTool.calc_plant_carbon_sink_rate_g_hr(
        device_id="BLUEBERRY_GREENHOUSE_001",
        batch_id="BATCH-20260328-004",
        co2_time_series=mock_data1,
        chamber_volume_m3=10.0,
        air_temp_c=25.0,
        chamber_pressure_hpa=950.0  # 低气压环境（高海拔地区）
    )
    
    print(f"设备ID: {result4['device_id']}")
    print(f"批次ID: {result4['batch_id']}")
    print(f"碳汇速率: {result4['carbon_sink_rate_g_hr']} g/hr")
    print(f"数据可靠性评分: {result4['data_reliability_score']}/100")
    print(f"每日干物质估算: {result4['daily_dry_matter_est_g']} g")
    print()
    
    # 测试场景5: 高置信度情况
    print("=== 测试场景5: 高置信度情况 ===")
    mock_data5 = [
        (datetime(2026, 3, 28, 10, 0), 900.0),
        (datetime(2026, 3, 28, 10, 10), 850.0),
        (datetime(2026, 3, 28, 10, 20), 800.0),
        (datetime(2026, 3, 28, 10, 30), 750.0),
        (datetime(2026, 3, 28, 10, 40), 700.0)
    ]
    
    result5 = GrowthAnalysisTool.calc_plant_carbon_sink_rate_g_hr(
        device_id="BLUEBERRY_GREENHOUSE_001",
        batch_id="BATCH-20260328-005",
        co2_time_series=mock_data5,
        chamber_volume_m3=10.0,
        air_temp_c=25.0
    )
    
    print(f"设备ID: {result5['device_id']}")
    print(f"批次ID: {result5['batch_id']}")
    print(f"碳汇速率: {result5['carbon_sink_rate_g_hr']} g/hr")
    print(f"数据可靠性评分: {result5['data_reliability_score']}/100")
    print(f"每日干物质估算: {result5['daily_dry_matter_est_g']} g")