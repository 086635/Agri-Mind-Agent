import pandas as pd
import numpy as np
from datetime import datetime
from typing import List, Tuple

class GrowthAnalysisTool:
    """
    二级数据分析工具库 - 植物生长动力学算法
    """

    @staticmethod
    def calculate_plant_carbon_sink_rate_g_hr(
        co2_time_series: List[Tuple[datetime, float]], 
        chamber_volume_m3: float,
        air_temp_c: float,
        is_ventilation_active: bool = False,
        device_id: str = None,
        min_reliability: float = 0.6,
        min_sink_safety: float = -5.0,
        reliability_scores: List[float] = None
    ) -> dict:
        """
        算法：光合碳汇速率 (Photosynthetic Carbon Sink Rate)
        逻辑：基于理想气体方程，将密闭空间内 CO2 的 ppm 下降速率转化为克/小时。
        
        SQL COMMENT: 
            指标映射：agri_analytical_metrics.carbon_sink_rate
            业务意义：基于密闭空间 CO2 浓度下降斜率，推算植物净光合速率（单位质量/小时）
        
        Args:
            co2_time_series: [(时间, CO2_ppm), ...] 至少需要两个采样点
            chamber_volume_m3: 密闭空间/温室的有效体积 (立方米)
            air_temp_c: 当前环境平均温度
            is_ventilation_active: 设备干预标记。如果通风开启，则计算无效，返回 0.0
            device_id: 设备 ID，用于标识不同设备的计算
            min_reliability: 最小可靠性阈值，默认 0.6
            min_sink_safety: 碳汇速率安全下限，默认 -5.0
            reliability_scores: 可靠性评分列表，默认 None
            
        Returns:
            dict: 包含碳汇速率、决策理由、状态、单位和动作反馈的字典，status 可能为 "success"、"warning" 或 "error"
        """
        # 1. 参数有效性检查
        if chamber_volume_m3 <= 0 or air_temp_c <= 0:
            return {
                "value": 0.0,
                "reasoning_context": f"参数无效：chamber_volume_m3={chamber_volume_m3}，air_temp_c={air_temp_c} 必须为正数",
                "actual_delta": 0.0,
                "device_id": device_id,
                "status": "error",
                "unit": "g/hr"
            }
        
        # 2. 安全校验：如果正在通风或数据不足，无法计算有效的闭合变化
        if is_ventilation_active:
            return {
                "value": 0.0,
                "reasoning_context": "通风系统已开启，无法进行密闭空间碳汇速率计算",
                "actual_delta": 0.0,
                "device_id": device_id,
                "status": "warning",
                "unit": "g/hr"
            }
        
        if len(co2_time_series) < 2:
            return {
                "value": 0.0,
                "reasoning_context": "数据点不足，至少需要两个采样点才能计算碳汇速率",
                "actual_delta": 0.0,
                "device_id": device_id,
                "status": "warning",
                "unit": "g/hr"
            }
        
        # 3. 数据可信度评估
        if reliability_scores and len(reliability_scores) == len(co2_time_series):
            avg_reliability = sum(reliability_scores) / len(reliability_scores)
            if avg_reliability < min_reliability:
                return {
                "value": 0.0,
                "reasoning_context": f"数据可信度不足 (平均可信度: {avg_reliability:.2f}，低于阈值: {min_reliability})，计算结果可能不准确",
                "actual_delta": 0.0,
                "device_id": device_id,
                "status": "warning",
                "reliability_score": avg_reliability,
                "unit": "g/hr"
            }

        # 2. 提取时间(小时)和浓度(ppm)
        times = np.array([(t[0] - co2_time_series[0][0]).total_seconds() / 3600.0 for t in co2_time_series])
        ppm_values = np.array([t[1] for t in co2_time_series])

        # 3. 线性回归计算斜率 (dC/dt) - ppm/hr
        # 我们关注下降速率，如果斜率为负，说明植物在吸收
        slope, intercept = np.polyfit(times, ppm_values, 1)
        
        # 计算 R² 以评估拟合度
        predicted = slope * times + intercept
        residuals = ppm_values - predicted
        ssr = np.sum(residuals ** 2)
        mean_ppm = np.mean(ppm_values)
        sst = np.sum((ppm_values - mean_ppm) ** 2)
        r_squared = 1 - (ssr / sst) if sst > 0 else 0.0
        
        # 4. 物理转换：ppm -> g/m³ -> g_total
        # 使用理想气体方程 (M * P) / (R * T) 计算
        # 转换为 mg/m³/ppm
        molar_mass_co2 = 44.01  # g/mol
        pressure_kpa = 101.325  # 标准大气压 (kPa)
        gas_constant = 8.314  # J/(mol·K)
        temp_kelvin = 273.15 + air_temp_c  # 转换为开尔文
        
        # 理想气体方程计算：(M * P) / (R * T) 得到 g/m³/ppm
        # 转换为 mg/m³/ppm
        mg_per_m3_per_ppm = (molar_mass_co2 * pressure_kpa) / (gas_constant * temp_kelvin) * 1000 / 1000000
        
        # 总质量变化率 (g/hr) = (ppm/hr) * (mg/m³/ppm) * m³ / 1000
        # 注意：植物吸收 CO2，浓度下降，slope 为负，所以我们取反得到吸收速率
        sink_rate_g_hr = -slope * mg_per_m3_per_ppm * chamber_volume_m3 / 1000.0
        sink_rate_g_hr = max(sink_rate_g_hr, min_sink_safety)

        # 5. 生成决策理由
        if sink_rate_g_hr > 0:
            reasoning_context = f"植物正在吸收 CO2，碳汇速率为 {sink_rate_g_hr:.4f} g/hr"
        else:
            reasoning_context = f"植物可能在释放 CO2（呼吸作用），净碳汇速率为 {sink_rate_g_hr:.4f} g/hr"
        
        # 检查 R² 是否低于阈值
        if r_squared < 0.8:
            reasoning_context += f" (警告：R² = {r_squared:.4f} < 0.8，拟合度较差，结果可能不可靠)"

        return {
            "value": round(sink_rate_g_hr, 4),
            "reasoning_context": reasoning_context,
            "actual_delta": sink_rate_g_hr,
            "device_id": device_id,
            "status": "success",
            "unit": "g/hr"
        }

def run_analysis(data: pd.DataFrame, config: dict) -> dict:
    """
    统一入口函数 - 计算植物碳汇速率
    
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
        chamber_volume_m3 = config.get('chamber_volume_m3', 10.0)
        air_temp_c = config.get('air_temp_c', 25.0)
        is_ventilation_active = config.get('is_ventilation_active', False)
        min_reliability = config.get('min_reliability', 0.6)
        min_sink_safety = config.get('min_sink_safety', -5.0)
        
        # 从 DataFrame 中提取数据
        # 假设 DataFrame 包含 timestamp 和 co2_ppm 列
        if 'timestamp' not in data.columns or 'co2_ppm' not in data.columns:
            return {
                'data_status': 'INVALID',
                'error': 'Missing required columns: timestamp or co2_ppm'
            }
        
        # 构建 CO2 时间序列
        co2_time_series = []
        for _, row in data.iterrows():
            timestamp = row['timestamp']
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            co2_time_series.append((timestamp, row['co2_ppm']))
        
        # 提取可靠性分数（如果存在）
        reliability_scores = None
        if 'reliability_score' in data.columns:
            reliability_scores = data['reliability_score'].tolist()
        
        # 调用计算函数
        result = GrowthAnalysisTool.calculate_plant_carbon_sink_rate_g_hr(
            co2_time_series=co2_time_series,
            chamber_volume_m3=chamber_volume_m3,
            air_temp_c=air_temp_c,
            is_ventilation_active=is_ventilation_active,
            device_id=device_id,
            min_reliability=min_reliability,
            min_sink_safety=min_sink_safety,
            reliability_scores=reliability_scores
        )
        
        # 转换结果格式，确保符合 AgriAnalyticalMetric 表字段
        return {
            'device_id': device_id,
            'batch_id': batch_id,
            'plant_carbon_sink_rate_g_hr': result['value'],
            'unit': result['unit'],
            'status': result['status'],
            'reasoning_context': result['reasoning_context']
        }
    except Exception as e:
        return {
            'data_status': 'INVALID',
            'error': str(e)
        }

# --- 模拟 OpenClaw 技能调用上下文 ---
if __name__ == "__main__":
    # 模拟 10 分钟内的 3 次采样 (10m³ 的密闭生长箱)
    mock_data = [
        (datetime(2026, 3, 28, 10, 0), 800.0),
        (datetime(2026, 3, 28, 10, 5), 785.0),
        (datetime(2026, 3, 28, 10, 10), 772.0)
    ]
    
    volume = 10.0  # 10 立方米
    temp = 25.0    # 25 摄氏度
    
    rate = GrowthAnalysisTool.calculate_plant_carbon_sink_rate_g_hr(
        mock_data, 
        volume, 
        temp, 
        device_id="device_001"
    )
    
    print(f"--- 碳汇资产核算 ---")
    print(f"数据周期: 10 min")
    print(f"CO2 下降趋势: 800 -> 772 ppm")
    print(f"实时指标 (plant_carbon_sink_rate_g_hr): {rate['value']} g/hr")
    print(f"决策理由: {rate['reasoning_context']}")
    print(f"价值评估: 该速率下，24小时可累积干物质约 {rate['value'] * 12: .2f} g (假设日间12h)")