import pandas as pd
from typing import List, Optional
from datetime import datetime
import statistics

class PlantPhysiologyAnalytics:
    """
    植物生理分析算法工具包
    集成 MCP 语义规范，用于二级数据特征提取与量化经验资产
    """

    @staticmethod
    def calculate_plant_gdd_daily_c(
        air_temp_samples: List[float], 
        plant_base_temp_c: float = 10.0,
        reliability_scores: List[float] = None,
        sample_timestamps: List[datetime] = None,
        harvest_target_gdd: float = None,
        current_accumulated_gdd: float = 0.0,
        device_id: str = None,
        batch_id: str = None
    ) -> dict:
        """
        计算当日有效积温 (GDD - Growing Degree Days)
        
        SQL COMMENT: 映射至 agri_analytical_metrics.gdd_daily。基于采样均温与基准温差值的积温算法，用于预测作物采收期与发育阶段。
        
        算法逻辑:
        GDD = max(T_avg - T_base, 0)
        其中 T_avg 为当日 24 小时采样点的算术平均值。
        T_base 为植物生长的生物学下限温度（如蓝莓通常为 7.2°C 或 10°C）。
        
        Args:
            air_temp_samples (List[float]): 当日 L1 热数据表中的空气温度采样列表 (env_temp_c)
            plant_base_temp_c (float): 该作物周期的基准生长温度阈值，默认 10.0°C
            reliability_scores (List[float], optional): 采样数据的可靠性评分列表，默认 None
            sample_timestamps (List[datetime], optional): 采样时间戳列表，默认 None
            harvest_target_gdd (float, optional): 收获目标积温，默认 None
            current_accumulated_gdd (float, optional): 当前累计积温，默认 0.0
            device_id (str, optional): 设备 ID，默认 None
            batch_id (str, optional): 批次 ID，默认 None
            
        Returns:
            dict: 包含以下字段的字典：
                - value: 当日贡献的有效积温值
                - unit: 单位，固定为 "℃·d"
                - status: 计算状态
                - reasoning_context: 计算过程说明
                - device_id: 设备 ID
                - batch_id: 批次 ID
        """
        if not air_temp_samples:
            return {
                "value": 0.0,
                "unit": "℃·d",
                "status": "error",
                "reasoning_context": "No temperature samples provided",
                "device_id": device_id,
                "batch_id": batch_id
            }
        
        # 1. 热限拦截：过滤掉物理不可能的温度
        total_samples = len(air_temp_samples)
        filtered_by_temperature = [temp for temp in air_temp_samples if -20.0 <= temp <= 55.0]
        temp_filtered_count = len(filtered_by_temperature)
        
        # 2. 过滤低可靠性采样点
        if reliability_scores and len(reliability_scores) == total_samples:
            # 先过滤温度，再过滤可靠性
            filtered_temps = [temp for temp, score in zip(filtered_by_temperature, reliability_scores[:temp_filtered_count]) if score >= 0.5]
            valid_count = len(filtered_temps)
            valid_ratio = valid_count / total_samples if total_samples > 0 else 0
        else:
            filtered_temps = filtered_by_temperature
            valid_count = len(filtered_temps)
            valid_ratio = valid_count / total_samples if total_samples > 0 else 0
        
        # 2. 检查有效采样点占比
        status = "success"
        reasoning_parts = []
        
        # 3. 时间跨度检查
        if sample_timestamps and len(sample_timestamps) > 1:
            time_diff = (sample_timestamps[-1] - sample_timestamps[0]).total_seconds() / 3600  # 转换为小时
            if time_diff < 20:
                status = "warning"
                reasoning_parts.append(f"Time span warning: Sample time span is only {time_diff:.1f} hours, less than 20 hours")
        
        if valid_ratio < 0.7:
            status = "warning"
            reasoning_parts.append(f"Low reliability warning: Only {valid_count}/{total_samples} ({valid_ratio:.1%}) samples are reliable")
        
        # 4. 记录温度过滤情况
        if temp_filtered_count < total_samples:
            filtered_count = total_samples - temp_filtered_count
            reasoning_parts.append(f"Temperature filter applied: Removed {filtered_count} out-of-range samples (<-20°C or >55°C)")
        
        # 3. 计算当日均温 (T_avg)
        if filtered_temps:
            avg_temp = statistics.mean(filtered_temps)
            reasoning_parts.append(f"Calculated average temperature: {avg_temp:.2f}°C from {valid_count} valid samples")
        else:
            avg_temp = 0.0
            reasoning_parts.append("No valid temperature samples after filtering")
        
        # 4. 计算有效积温 (GDD)
        # 低于基准温度的部分不计入热量积累，避免负值干扰
        gdd_daily = max(avg_temp - plant_base_temp_c, 0.0)
        rounded_gdd = round(gdd_daily, 2)
        
        reasoning_parts.append(f"Subtracted base temperature: {plant_base_temp_c}°C, applied max(0) to get GDD")
        
        # 5. 计算发育进度和阶段描述
        if harvest_target_gdd and harvest_target_gdd > 0:
            # 计算当前累计积温（包括今日贡献）
            total_gdd_with_current = current_accumulated_gdd + rounded_gdd
            
            # 计算发育进度百分比
            progress_percentage = min((total_gdd_with_current / harvest_target_gdd) * 100, 100.0)
            
            # 生成发育阶段描述
            if progress_percentage < 30:
                stage_description = "当前处于营养生长初期"
            elif progress_percentage < 60:
                stage_description = "当前处于花期预测窗口"
            elif progress_percentage < 90:
                stage_description = "当前处于果实发育期"
            elif progress_percentage < 100:
                stage_description = f"距离采收还需约 {round(harvest_target_gdd - total_gdd_with_current, 2)} 积温"
            else:
                stage_description = "已达到采收目标积温"
            
            reasoning_parts.append(f"发育进度: {progress_percentage:.1f}%，{stage_description}")
        
        reasoning_context = "; ".join(reasoning_parts)
        
        return {
            "value": rounded_gdd,
            "unit": "℃·d",
            "status": status,
            "reasoning_context": reasoning_context,
            "device_id": device_id,
            "batch_id": batch_id
        }

    @staticmethod
    def update_plant_gdd_accumulated(
        current_total_gdd: float, 
        new_daily_gdd: float
    ) -> float:
        """
        更新作物周期的总积温累计
        
        用于更新 agri_analytical_metrics 表中的 gdd_accumulated 字段
        """
        return round(current_total_gdd + new_daily_gdd, 2)

def run_analysis(data: pd.DataFrame, config: dict) -> dict:
    """
    统一入口函数 - 计算植物当日有效积温
    
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
        plant_base_temp_c = config.get('plant_base_temp_c', 10.0)
        harvest_target_gdd = config.get('harvest_target_gdd', None)
        current_accumulated_gdd = config.get('current_accumulated_gdd', 0.0)
        
        # 从 DataFrame 中提取数据
        # 假设 DataFrame 包含 air_temp 列
        if 'air_temp' not in data.columns:
            return {
                'data_status': 'INVALID',
                'error': 'Missing required column: air_temp'
            }
        
        # 提取温度数据
        air_temp_samples = data['air_temp'].tolist()
        
        # 提取可靠性分数（如果存在）
        reliability_scores = None
        if 'reliability_score' in data.columns:
            reliability_scores = data['reliability_score'].tolist()
        
        # 提取时间戳（如果存在）
        sample_timestamps = None
        if 'timestamp' in data.columns:
            sample_timestamps = []
            for ts in data['timestamp']:
                if isinstance(ts, str):
                    sample_timestamps.append(datetime.fromisoformat(ts))
                else:
                    sample_timestamps.append(ts)
        
        # 调用计算函数
        result = PlantPhysiologyAnalytics.calculate_plant_gdd_daily_c(
            air_temp_samples=air_temp_samples,
            plant_base_temp_c=plant_base_temp_c,
            reliability_scores=reliability_scores,
            sample_timestamps=sample_timestamps,
            harvest_target_gdd=harvest_target_gdd,
            current_accumulated_gdd=current_accumulated_gdd,
            device_id=device_id,
            batch_id=batch_id
        )
        
        # 转换结果格式，确保符合 AgriAnalyticalMetric 表字段
        return {
            'device_id': device_id,
            'batch_id': batch_id,
            'plant_gdd_daily_c': result['value'],
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
    # 模拟从 L1 raw_environmental_readings 提取的当日温度序列
    mock_l1_temp_data = [12.5, 15.0, 18.2, 22.1, 20.5, 14.8, 11.2, 10.5]
    
    # 设定蓝莓的基准温度 (假设为 10°C)
    BASE_TEMP = 10.0
    
    print("=== 测试场景 1: 无可靠性分数 ===")
    # 执行算法 - 无可靠性分数
    daily_contribution = PlantPhysiologyAnalytics.calculate_plant_gdd_daily_c(
        mock_l1_temp_data, 
        BASE_TEMP,
        device_id="sensor_001",
        batch_id="batch_20260329"
    )
    
    print(f"当日均温推算: {statistics.mean(mock_l1_temp_data):.2f}°C")
    print(f"当日有效积温贡献 (plant_gdd_daily_c): {daily_contribution['value']} {daily_contribution['unit']}")
    print(f"计算状态: {daily_contribution['status']}")
    print(f"计算过程: {daily_contribution['reasoning_context']}")
    print(f"设备 ID: {daily_contribution['device_id']}")
    print(f"批次 ID: {daily_contribution['batch_id']}")
    
    print("\n=== 测试场景 2: 高可靠性分数 ===")
    # 执行算法 - 高可靠性分数
    high_reliability = [0.9, 0.8, 0.95, 0.85, 0.9, 0.88, 0.92, 0.87]
    daily_contribution_high = PlantPhysiologyAnalytics.calculate_plant_gdd_daily_c(
        mock_l1_temp_data, 
        BASE_TEMP,
        reliability_scores=high_reliability,
        device_id="sensor_001",
        batch_id="batch_20260329"
    )
    
    print(f"当日有效积温贡献 (plant_gdd_daily_c): {daily_contribution_high['value']} {daily_contribution_high['unit']}")
    print(f"计算状态: {daily_contribution_high['status']}")
    print(f"计算过程: {daily_contribution_high['reasoning_context']}")
    
    print("\n=== 测试场景 3: 低可靠性分数 (触发警告) ===")
    # 执行算法 - 低可靠性分数
    low_reliability = [0.3, 0.4, 0.2, 0.6, 0.7, 0.3, 0.4, 0.5]  # 只有 3 个有效点
    daily_contribution_low = PlantPhysiologyAnalytics.calculate_plant_gdd_daily_c(
        mock_l1_temp_data, 
        BASE_TEMP,
        reliability_scores=low_reliability,
        device_id="sensor_001",
        batch_id="batch_20260329"
    )
    
    print(f"当日有效积温贡献 (plant_gdd_daily_c): {daily_contribution_low['value']} {daily_contribution_low['unit']}")
    print(f"计算状态: {daily_contribution_low['status']}")
    print(f"计算过程: {daily_contribution_low['reasoning_context']}")
    
    print("\n=== 测试场景 4: 热限拦截 (包含异常温度) ===")
    # 包含异常温度的测试数据
    temp_with_outliers = [12.5, 15.0, 60.0, 22.1, -25.0, 14.8, 11.2, 10.5]  # 包含 60°C 和 -25°C 的异常值
    daily_contribution_outliers = PlantPhysiologyAnalytics.calculate_plant_gdd_daily_c(
        temp_with_outliers, 
        BASE_TEMP,
        device_id="sensor_001",
        batch_id="batch_20260329"
    )
    
    print(f"原始温度数据: {temp_with_outliers}")
    print(f"当日有效积温贡献 (plant_gdd_daily_c): {daily_contribution_outliers['value']} {daily_contribution_outliers['unit']}")
    print(f"计算状态: {daily_contribution_outliers['status']}")
    print(f"计算过程: {daily_contribution_outliers['reasoning_context']}")
    
    print("\n=== 测试场景 5: 时间跨度检查 (不足 20 小时) ===")
    # 生成不足 20 小时的时间戳
    import datetime
    start_time = datetime.datetime(2026, 3, 29, 0, 0, 0)
    short_time_span = [
        start_time,
        start_time + datetime.timedelta(hours=5),
        start_time + datetime.timedelta(hours=10),
        start_time + datetime.timedelta(hours=15)  # 总跨度 15 小时
    ]
    daily_contribution_short_time = PlantPhysiologyAnalytics.calculate_plant_gdd_daily_c(
        mock_l1_temp_data, 
        BASE_TEMP,
        sample_timestamps=short_time_span,
        device_id="sensor_001",
        batch_id="batch_20260329"
    )
    
    print(f"时间跨度: {short_time_span[-1] - short_time_span[0]}")
    print(f"当日有效积温贡献 (plant_gdd_daily_c): {daily_contribution_short_time['value']} {daily_contribution_short_time['unit']}")
    print(f"计算状态: {daily_contribution_short_time['status']}")
    print(f"计算过程: {daily_contribution_short_time['reasoning_context']}")
    
    print("\n=== 测试场景 6: 空列表防御 ===")
    # 测试空列表输入
    daily_contribution_empty = PlantPhysiologyAnalytics.calculate_plant_gdd_daily_c(
        [], 
        BASE_TEMP,
        device_id="sensor_001",
        batch_id="batch_20260329"
    )
    
    print(f"当日有效积温贡献 (plant_gdd_daily_c): {daily_contribution_empty['value']} {daily_contribution_empty['unit']}")
    print(f"计算状态: {daily_contribution_empty['status']}")
    print(f"计算过程: {daily_contribution_empty['reasoning_context']}")
    
    # 模拟数据库累计操作
    previous_gdd = 450.25 # 从数据库读取的昨日累计值
    new_total = PlantPhysiologyAnalytics.update_plant_gdd_accumulated(previous_gdd, daily_contribution['value'])
    print(f"\n作物周期总积温更新 (gdd_accumulated): {new_total} ℃·d")