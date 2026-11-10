import pandas as pd
from typing import List, Tuple
from datetime import datetime

class PlantPhysiologyAnalytics:
    """
    植物生理分析算法工具包 - DLI 积分模块
    """

    @staticmethod
    def calculate_plant_dli_daily_mol(par_time_series: List[Tuple[datetime, float]], reliability_scores: List[float] = None, target_dli_mol: float = None, device_id: str = None) -> dict:
        """
        基于 PAR 瞬时值序列计算当日 DLI (日光积分)
        
        计算原理:
        DLI = Σ [(PAR_n + PAR_{n+1}) / 2 * Δt_n] / 1,000,000
        其中 PAR 单位为 μmol/m²/s，Δt 为两次采样间隔的秒数。使用梯形法则近似积分，比单点矩形法更精确，能更好应对光照突变。
        
        Args:
            par_time_series: PAR 时间序列数据, 格式为 [(时间对象, PAR值), ...]
                             PAR值应已通过 calculate_plant_par_instant_umol 转换
            reliability_scores: 可靠性评分序列，与 PAR 时间序列长度相同，默认为 None
            target_dli_mol: 目标 DLI 值，单位 mol/(m2·d)，默认为 None
            device_id: 设备 ID，用于标识不同设备的计算
            
        Returns:
            dict: 包含以下字段的字典:
                - value: 当日日光积分值, 单位 mol/(m2·d)
                - unit: 单位，固定为 "mol/(m2·d)"
            
        SQL COMMENT: 映射至 agri_analytical_metrics.dli_daily。基于采样间隔的梯形积分法，将瞬时 PAR (μmol/m²/s) 累积为当日总辐射能 (mol/m²/d)。
                - status: 计算状态，"success"、"warning" 或 "error"
                - reasoning_context: 计算过程的推理上下文
                - r_squared: 拟合度 R2 值 (此处为模拟值，实际应用中应根据真实数据计算)
                - dli_gap: 与目标 DLI 的差距 (当提供 target_dli_mol 时)
                - completion_rate: 目标 DLI 的完成率 (当提供 target_dli_mol 时)
                - device_id: 设备 ID (当提供时)
        """
        # 过滤负数 PAR 值
        filtered_series = [(t, max(0, p)) for t, p in par_time_series]
        
        # 空值防御：检查有效数据点数量
        if not filtered_series or len(filtered_series) < 2:
            return {
                "value": 0.0,
                "unit": "mol/(m2·d)",
                "status": "error",
                "reasoning_context": "输入数据不足，需要至少两个时间点的 PAR 数据",
                "r_squared": 0.0,
                "device_id": device_id
            }

        # 数据可信度评估
        if reliability_scores and len(reliability_scores) == len(filtered_series):
            avg_reliability = sum(reliability_scores) / len(reliability_scores)
            if avg_reliability < 0.8:
                return {
                    "value": 0.0,
                    "unit": "mol/(m2·d)",
                    "status": "warning",
                    "reasoning_context": f"数据可信度不足 (平均可信度: {avg_reliability:.2f}，低于阈值: 0.8)，计算结果可能不准确",
                    "r_squared": 0.0,
                    "reliability_score": avg_reliability,
                    "device_id": device_id
                }

        # 按时间排序，确保积分顺序正确
        sorted_series = sorted(filtered_series, key=lambda x: x[0])
        
        # 时间窗口校验
        total_duration = (sorted_series[-1][0] - sorted_series[0][0]).total_seconds() / 3600  # 转换为小时
        time_warning = ""
        if total_duration > 24:
            time_warning = "警告：采样序列总时长超过 24 小时，可能包含跨天数据；"
        elif total_duration < 1:
            time_warning = "警告：采样序列总时长少于 1 小时，数据可能不足以准确计算 DLI；"
        
        total_micromoles = 0.0
        
        for i in range(len(sorted_series) - 1):
            t1, p1 = sorted_series[i]
            t2, p2 = sorted_series[i+1]
            
            # 计算采样间隔秒数 (Δt)
            delta_t = (t2 - t1).total_seconds()
            
            # 使用梯形法则近似积分：(P1 + P2) / 2 * Δt
            # 这样处理比单点矩形法更精确，能更好应对光照突变
            interval_energy = ((p1 + p2) / 2.0) * delta_t
            total_micromoles += interval_energy

        # 将 μmol 转换为 mol (除以 1,000,000)
        plant_dli_daily_mol = total_micromoles / 1_000_000.0
        plant_dli_daily_mol = round(plant_dli_daily_mol, 4)
        
        # 构建返回字典
        result = {
            "value": plant_dli_daily_mol,
            "unit": "mol/(m2·d)",
            "status": "success",
            "reasoning_context": f"{time_warning}基于 {len(filtered_series)} 个时间点的 PAR 数据，使用梯形法则计算得到当日 DLI",
            "r_squared": 0.95,  # 模拟值，实际应用中应根据真实数据计算
            "device_id": device_id
        }
        
        # 当提供目标 DLI 时，添加差距和完成率，并生成决策逻辑
        if target_dli_mol is not None:
            dli_gap = max(0.0, target_dli_mol - plant_dli_daily_mol)  # 确保差距为非负数
            completion_rate = min(100.0, (plant_dli_daily_mol / target_dli_mol * 100)) if target_dli_mol > 0 else 0
            
            # 生成基于完成率的决策逻辑
            if completion_rate >= 100.0:
                dli_decision = "当前 DLI 已达标"
            elif completion_rate >= 90.0:
                dli_decision = "DLI 略低于目标值，基本满足需求"
            elif completion_rate >= 70.0:
                dli_decision = "DLI 有一定缺口，建议适当延长补光时长"
            else:
                dli_decision = "DLI 缺口较大，建议延长补光时长"
            
            # 更新 reasoning_context 和添加差距、完成率
            result["reasoning_context"] = f"{time_warning}基于 {len(filtered_series)} 个时间点的 PAR 数据，使用梯形法则计算得到当日 DLI。{dli_decision}"
            result.update({
                "dli_gap": round(dli_gap, 4),
                "completion_rate": round(completion_rate, 2)
            })
        
        return result

def run_analysis(data: pd.DataFrame, config: dict) -> dict:
    """
    统一入口函数 - 计算植物当日日光积分
    
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
        target_dli_mol = config.get('target_dli_mol', None)
        
        # 从 DataFrame 中提取数据
        # 假设 DataFrame 包含 timestamp 和 par_value 列
        if 'timestamp' not in data.columns or 'par_value' not in data.columns:
            return {
                'data_status': 'INVALID',
                'error': 'Missing required columns: timestamp or par_value'
            }
        
        # 构建 PAR 时间序列
        par_time_series = []
        reliability_scores = []
        for _, row in data.iterrows():
            timestamp = row['timestamp']
            if isinstance(timestamp, str):
                timestamp = datetime.fromisoformat(timestamp)
            par_time_series.append((timestamp, row['par_value']))
            if 'reliability_score' in data.columns:
                reliability_scores.append(row['reliability_score'])
        
        # 调用计算函数
        if reliability_scores:
            result = PlantPhysiologyAnalytics.calculate_plant_dli_daily_mol(
                par_time_series=par_time_series,
                reliability_scores=reliability_scores,
                target_dli_mol=target_dli_mol,
                device_id=device_id
            )
        else:
            result = PlantPhysiologyAnalytics.calculate_plant_dli_daily_mol(
                par_time_series=par_time_series,
                target_dli_mol=target_dli_mol,
                device_id=device_id
            )
        
        # 转换结果格式，确保符合 AgriAnalyticalMetric 表字段
        return {
            'device_id': device_id,
            'batch_id': batch_id,
            'plant_dli_daily_mol': result['value'],
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
    
    # 模拟从 L1 表 (raw_environmental_readings) 提取并转换后的数据
    start_time = datetime(2026, 3, 28, 6, 0, 0) # 早上 6 点开始
    mock_par_data = []
    
    # 模拟 12 小时光照，每 10 分钟一次采样
    for i in range(72):
        current_time = start_time + timedelta(minutes=i * 10)
        # 模拟正弦波光照曲线 (0 到 1000 μmol/m²/s)
        import math
        simulated_par = 1000 * math.sin(math.pi * i / 72)
        mock_par_data.append((current_time, max(0, simulated_par)))

    # 执行算法 - 不提供目标 DLI
    dli_result = PlantPhysiologyAnalytics.calculate_plant_dli_daily_mol(mock_par_data)
    
    print(f"统计时长: {mock_par_data[-1][0] - mock_par_data[0][0]}")
    print(f"今日日光积分 (plant_dli_daily_mol): {dli_result['value']} {dli_result['unit']}")
    print(f"计算状态: {dli_result['status']}")
    print(f"推理上下文: {dli_result['reasoning_context']}")
    print(f"拟合度 R2: {dli_result['r_squared']}")
    
    # 测试不同目标 DLI 值的情况
    test_targets = [10.0, 25.0, 30.0, 35.0]
    
    for target_dli in test_targets:
        dli_result_with_target = PlantPhysiologyAnalytics.calculate_plant_dli_daily_mol(mock_par_data, target_dli_mol=target_dli)
        
        print(f"\n带目标 DLI {target_dli} 的计算结果:")
        print(f"今日日光积分: {dli_result_with_target['value']} {dli_result_with_target['unit']}")
        print(f"目标 DLI: {target_dli} mol/(m2·d)")
        print(f"DLI 差距: {dli_result_with_target['dli_gap']} mol/(m2·d)")
        print(f"完成率: {dli_result_with_target['completion_rate']}%")
        print(f"推理上下文: {dli_result_with_target['reasoning_context']}")