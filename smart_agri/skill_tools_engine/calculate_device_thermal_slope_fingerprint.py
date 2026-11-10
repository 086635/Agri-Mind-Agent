import pandas as pd
import numpy as np
from typing import List, Dict, Tuple
from sklearn.linear_model import LinearRegression

class DeviceDiagnosticAnalytics:
    """
    设备数字孪生与诊断工具包
    用于分析设备执行效率（手脚健康度）与预测性维护
    """

    @staticmethod
    def calculate_device_thermal_slope_fingerprint(
        time_series_sec: List[float], 
        value_series: List[float],
        ideal_slope: float = 0.5
    ) -> Dict[str, float]:
        """
        计算设备热力/动力响应指纹
        
        算法逻辑:
        1. 使用一元线性回归拟合设备开启后的变化曲线：Value = Slope * Time + Intercept
        2. 计算实际斜率 (Actual Slope) 与理想斜率 (Ideal Slope) 的偏移量。
        3. 偏移量越大，代表设备效率衰减（如加热棒结垢、风机轴承摩擦）。
        
        Args:
            time_series_sec (List): 时间序列（相对启动时间，单位：秒）
            value_series (List): 物理量序列（如温度 env_temp_c）
            ideal_slope (float): 该设备出厂时的理想响应斜率
            
        Returns:
            Dict: 包含实时斜率、响应延迟及故障概率预判
        """
        if len(time_series_sec) < 2:
            return {"slope": 0.0, "failure_prob": 0.0}

        # 1. 线性回归提取斜率 (dy/dt)
        X = np.array(time_series_sec).reshape(-1, 1)
        y = np.array(value_series)
        model = LinearRegression().fit(X, y)
        actual_slope = model.coef_[0]
        r_squared = model.score(X, y) # 相关系数，判断响应是否线性平稳

        # 2. 残差分析与故障概率计算
        # 效率衰减率 = (理想斜率 - 实际斜率) / 理想斜率
        efficiency_loss = max(0, (ideal_slope - actual_slope) / ideal_slope)
        
        # 故障概率映射（非线性加权）
        failure_probability_pct = min(100.0, (efficiency_loss ** 2) * 100)

        return {
            "device_thermal_slope": round(actual_slope, 4),
            "response_consistency_r2": round(r_squared, 4),
            "failure_probability_pct": round(failure_probability_pct, 2)
        }

def run_analysis(data: pd.DataFrame, config: dict) -> dict:
    """
    统一入口函数 - 计算设备热力响应指纹
    
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
        ideal_slope = config.get('ideal_slope', 0.5)
        
        # 从 DataFrame 中提取数据
        # 假设 DataFrame 包含 time_sec 和 value 列
        if 'time_sec' not in data.columns or 'value' not in data.columns:
            return {
                'data_status': 'INVALID',
                'error': 'Missing required columns: time_sec or value'
            }
        
        # 提取数据值
        time_series_sec = data['time_sec'].tolist()
        value_series = data['value'].tolist()
        
        # 调用计算函数
        result = DeviceDiagnosticAnalytics.calculate_device_thermal_slope_fingerprint(
            time_series_sec=time_series_sec,
            value_series=value_series,
            ideal_slope=ideal_slope
        )
        
        # 转换结果格式，确保符合 AgriAnalyticalMetric 表字段
        return {
            'device_id': device_id,
            'batch_id': batch_id,
            'device_thermal_slope': result['device_thermal_slope'],
            'response_consistency_r2': result['response_consistency_r2'],
            'failure_probability_pct': result['failure_probability_pct']
        }
    except Exception as e:
        return {
            'data_status': 'INVALID',
            'error': str(e)
        }

# --- 模拟 OpenClaw 运维监控场景 ---
if __name__ == "__main__":
    # 场景：加热棒开启 60 秒内的温度变化
    time_data = [0, 10, 20, 30, 40, 50, 60]
    
    # 模拟“健康”状态：温度稳步上升
    healthy_temp = [20.0, 21.5, 23.0, 24.5, 26.0, 27.5, 29.0] # 斜率约为 0.15
    
    # 模拟“老化”状态：加热缓慢且不稳
    aging_temp = [20.0, 20.5, 21.2, 21.8, 22.3, 22.9, 23.5]   # 斜率约为 0.05
    
    IDEAL = 0.15 # 出厂设定的标准斜率
    
    res_healthy = DeviceDiagnosticAnalytics.calculate_device_thermal_slope_fingerprint(time_data, healthy_temp, IDEAL)
    res_aging = DeviceDiagnosticAnalytics.calculate_device_thermal_slope_fingerprint(time_data, aging_temp, IDEAL)
    
    print(f"健康设备指纹: {res_healthy}")
    print(f"老化设备指纹: {res_aging}")