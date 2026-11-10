import pandas as pd
from typing import List, Tuple, Dict
from datetime import datetime

class NutrientFlowAnalytics:
    """
    养分流分析工具包 - 针对 NPK 传感器数据加工
    集成 MCP 语义规范，用于二级数据特征提取
    """

    @staticmethod
    def calculate_soil_nutrient_consumption_rate_mg(
        npk_time_series: List[Tuple[datetime, float]], 
        soil_volume_l: float = 10.0,
        device_id: str = None,
        batch_id: str = None,
        reliability_score: float = 1.0
    ) -> dict:
        """
        计算特定周期内土壤养分的总消耗量 (基于 NPK 负斜率累计)
        
        SQL COMMENT: 映射至 agri_analytical_metrics 字段。计算逻辑：基于 NPK 负斜率累计积分，排除施肥跳变，计算植物代谢总消耗量。
        
        计算逻辑:
        1. 识别 NPK 浓度的下降段 (即负斜率部分)。
        2. 排除由于灌溉导致的浓度骤升 (正斜率)。
        3. 消耗量 = Σ(浓度减少量) * 影响区域土壤有效容积。
        
        Args:
            npk_time_series: N/P/K 某一项的采样序列 [(时间, 浓度mg/kg), ...]
            soil_volume_l: 受传感器监测影响的土壤体积 (L)，用于将浓度转化为质量
            device_id: 设备 ID
            batch_id: 批次 ID
            reliability_score: 采样数据的置信度 (默认 1.0)
            
        Returns:
            dict: 包含 value、unit、status、reasoning_context、device_id、batch_id 的字典
        """

        # 确定状态
        status = "success"
        if reliability_score < 0.6:
            status = "warning"
        
        if not npk_time_series or len(npk_time_series) < 2:
            return {
                "value": 0.0,
                "unit": "mg",
                "status": status,
                "reasoning_context": "采样点不足，无法计算养分消耗量",
                "device_id": device_id,
                "batch_id": batch_id
            }

        # 按时间排序
        sorted_data = sorted(npk_time_series, key=lambda x: x[0])
        
        total_consumption_conc = 0.0
        valid_intervals = 0
        skipped_increments = 0
        noise_threshold = 0.1
        
        for i in range(len(sorted_data) - 1):
            val_start = sorted_data[i][1]
            val_end = sorted_data[i+1][1]
            
            # 差值 (Delta)
            diff = val_start - val_end
            
            # 关键逻辑：只有当 diff > noise_threshold 时，才认为是植物吸收或自然损耗
            # 若 diff < 0，通常是由于施肥或灌溉导致的浓度上升，不计入消耗
            if diff > noise_threshold:
                total_consumption_conc += diff
                valid_intervals += 1
            elif diff < 0:
                skipped_increments += 1
        
        # 假设土壤密度约为 1.2kg/L，将 mg/kg 转化为总 mg
        # 消耗质量 (mg) = 浓度变化(mg/kg) * 体积(L) * 密度(kg/L)
        soil_density = 1.2 
        total_mg = total_consumption_conc * soil_volume_l * soil_density
        value = round(total_mg, 2)
        
        # 异常处理：检查计算结果是否异常巨大
        if total_mg > 5000:
            status = "error"
            reasoning_context = "数据超限，请检查传感器是否发生硬件漂移"
        else:
            # 构建决策理由
            reasoning_context = f"共分析 {len(npk_time_series)} 个采样点，识别出 {valid_intervals} 段有效吸收区间，已剔除 {skipped_increments} 次施肥/灌溉导致的浓度跳变"
            
            # 添加置信度警告
            if reliability_score < 0.6:
                reasoning_context += "\n采样置信度低，消耗量计算可能存在误差"
        
        # 返回结果
        return {
            "value": value,
            "unit": "mg",
            "status": status,
            "reasoning_context": reasoning_context,
            "device_id": device_id,
            "batch_id": batch_id
        }

def run_analysis(data: pd.DataFrame, config: dict) -> dict:
    """
    统一入口函数 - 计算土壤养分消耗率
    
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
        soil_volume_l = config.get('soil_volume_l', 10.0)
        reliability_score = config.get('reliability_score', 1.0)
        
        # 从 DataFrame 中提取 NPK 数据
        # 假设 DataFrame 包含 timestamp 和 npk_concentration 列
        if 'timestamp' not in data.columns or 'npk_concentration' not in data.columns:
            return {
                'data_status': 'INVALID',
                'error': 'Missing required columns: timestamp or npk_concentration'
            }
        
        # 构建 NPK 时间序列
        npk_time_series = []
        for _, row in data.iterrows():
            timestamp = row['timestamp']
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            npk_time_series.append((timestamp, row['npk_concentration']))
        
        # 调用计算函数
        result = NutrientFlowAnalytics.calculate_soil_nutrient_consumption_rate_mg(
            npk_time_series,
            soil_volume_l=soil_volume_l,
            device_id=device_id,
            batch_id=batch_id,
            reliability_score=reliability_score
        )
        
        # 转换结果格式，确保符合 AgriAnalyticalMetric 表字段
        return {
            'device_id': device_id,
            'batch_id': batch_id,
            'soil_nutrient_consumption_rate_mg': result['value'],
            'unit': result['unit'],
            'status': result['status'],
            'reasoning_context': result['reasoning_context']
        }
    except Exception as e:
        return {
            'data_status': 'INVALID',
            'error': str(e)
        }

# --- 模拟集成场景 ---
if __name__ == "__main__":
    from datetime import timedelta
    
    # 模拟 24 小时的 N(氮) 元素数据
    # 正常情况下，氮浓度会缓慢下降
    start_time = datetime.now()
    mock_n_data = []
    
    current_val = 150.0 # 初始浓度 150 mg/kg
    for i in range(24):
        # 模拟每小时下降 0.5 mg/kg
        current_val -= 0.5
        # 模拟中间有一次扰动（如局部水分波动导致浓度小幅反弹）
        if i == 12: current_val += 2.0 
        
        mock_n_data.append((start_time + timedelta(hours=i), current_val))

    # 计算总消耗
    result = NutrientFlowAnalytics.calculate_soil_nutrient_consumption_rate_mg(
        mock_n_data, 
        soil_volume_l=15.0, # 假设是 15升 的种植盆
        device_id="sensor_001",
        batch_id="batch_2024_01"
    )
    
    print(f"--- 土壤养分消耗分析报告 ---")
    print(f"采样点数: {len(mock_n_data)}")
    print(f"土壤总氮消耗量 (soil_nutrient_consumption_rate_mg): {result['value']} {result['unit']}")
    print(f"状态: {result['status']}")
    print(f"设备 ID: {result['device_id']}")
    print(f"批次 ID: {result['batch_id']}")
    print(f"详细说明: {result['reasoning_context']}")
    
    # 测试低置信度场景
    print("\n--- 低置信度场景测试 ---")
    result_low_conf = NutrientFlowAnalytics.calculate_soil_nutrient_consumption_rate_mg(
        mock_n_data, 
        soil_volume_l=15.0,
        device_id="sensor_001",
        batch_id="batch_2024_01",
        reliability_score=0.5
    )
    print(f"消耗量: {result_low_conf['value']} {result_low_conf['unit']}")
    print(f"状态: {result_low_conf['status']}")
    print(f"详细说明: {result_low_conf['reasoning_context']}")
    
    # 测试异常巨大结果场景
    print("\n--- 异常巨大结果场景测试 ---")
    # 创建一个会产生巨大结果的测试数据
    large_data = []
    for i in range(2):
        large_data.append((start_time + timedelta(hours=i), 1000.0 if i == 0 else 0.0))
    
    result_large = NutrientFlowAnalytics.calculate_soil_nutrient_consumption_rate_mg(
        large_data, 
        soil_volume_l=15.0,
        device_id="sensor_001",
        batch_id="batch_2024_01"
    )
    print(f"消耗量: {result_large['value']} {result_large['unit']}")
    print(f"状态: {result_large['status']}")
    print(f"详细说明: {result_large['reasoning_context']}")