import pandas as pd
import math
from datetime import datetime

class PlantPhysiologyAnalytics:
    """
    植物生理分析算法工具包
    集成 MCP 语义规范，用于二级数据特征提取
    """

    @staticmethod
    def calculate_plant_par_instant_umol(
        air_lux_lx: float, 
        light_source: str = "sunlight",
        reliability_score: float = 1.0,
        device_id: str = None,
        batch_id: str = None,
        strategy_id: str = None
    ) -> dict:
        """
        将环境光照强度 (Lux) 推算为光合有效辐射 (PAR)
        
        SQL COMMENT: 映射至 agri_analytical_metrics.par_val。计算逻辑：将空气 Lux 转换为光合有效辐射 (PAR)，单位 μmol/(m²·s)。
        
        计算逻辑:
        1. 针对日光 (Sunlight): PAR ≈ Lux / 54 (基于 McCree 曲线的经验系数)
        2. 针对典型 LED 生长灯: PAR ≈ Lux / 65 (取决于具体光谱，此处取通用值)
        
        Args:
            air_lux_lx (float): 原始环境光照强度，单位 Lux
            light_source (str): 光源类型 ["sunlight", "led", "fluorescent"]
            reliability_score (float): 源自一级传感器的置信度 (默认 1.0)
            device_id (str): 设备 ID (可选)
            batch_id (str): 批次 ID (可选)
            strategy_id (str): 策略 ID (可选)
            
        Returns:
            dict: 包含 value、unit、status、reasoning_context、device_id、batch_id、strategy_id 的字典
        """

        # 转换系数配置 (不同光源的 PPFD 转换系数)
        conversion_factors = {
            "sunlight": 54.0,
            "led": 65.0,
            "fluorescent": 74.0
        }
        
        # 获取系数，若光源未知则默认使用日光系数
        factor = conversion_factors.get(light_source.lower(), 54.0)
        
        # 处理负值光照强度
        if air_lux_lx < 0:
            value = 0.0
        else:
            # 核心推算公式
            plant_par_instant_umol = air_lux_lx / factor
            value = round(plant_par_instant_umol, 2)
        
        # 确定状态
        status = "success"
        if reliability_score < 0.6:
            status = "warning"
        if air_lux_lx > 150000:
            status = "error"
        
        # 构建 reasoning_context
        reasoning_context = f"基于 {light_source} 系数 {factor} 转换"
        
        # 添加数据质量警告
        if reliability_score < 0.6:
            reasoning_context += "\n底层传感器采样质量存疑"
        
        # 添加物理边界警告
        if air_lux_lx > 150000:
            reasoning_context += "\n光照强度异常，疑似传感器过载或损坏"
        
        # 返回结果
        return {
            "value": value,
            "unit": "μmol/(m²·s)",
            "status": status,
            "reasoning_context": reasoning_context,
            "device_id": device_id,
            "batch_id": batch_id,
            "strategy_id": strategy_id
        }

def run_analysis(data: pd.DataFrame, config: dict) -> dict:
    """
    统一入口函数 - 计算植物瞬时光合有效辐射
    
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
        strategy_id = config.get('strategy_id', 'unknown')
        light_source = config.get('light_source', 'sunlight')
        reliability_score = config.get('reliability_score', 1.0)
        
        # 从 DataFrame 中提取数据
        # 假设 DataFrame 包含 air_lux_lx 列
        if 'air_lux_lx' not in data.columns:
            return {
                'data_status': 'INVALID',
                'error': 'Missing required column: air_lux_lx'
            }
        
        # 提取最新的光照强度数据
        latest_data = data.iloc[-1]
        air_lux_lx = latest_data['air_lux_lx']
        
        # 调用计算函数
        result = PlantPhysiologyAnalytics.calculate_plant_par_instant_umol(
            air_lux_lx=air_lux_lx,
            light_source=light_source,
            reliability_score=reliability_score,
            device_id=device_id,
            batch_id=batch_id,
            strategy_id=strategy_id
        )
        
        # 转换结果格式，确保符合 AgriAnalyticalMetric 表字段
        return {
            'device_id': device_id,
            'batch_id': batch_id,
            'strategy_id': strategy_id,
            'plant_par_instant_umol': result['value'],
            'unit': result['unit'],
            'status': result['status'],
            'reasoning_context': result['reasoning_context']
        }
    except Exception as e:
        return {
            'data_status': 'INVALID',
            'error': str(e)
        }

# 模拟接入数据流调用
if __name__ == "__main__":
    # 示例：中午强光下的传感器读数 54000 Lux
    raw_lux = 54000.0
    result = PlantPhysiologyAnalytics.calculate_plant_par_instant_umol(
        raw_lux, 
        "sunlight",
        device_id="sensor_001",
        batch_id="batch_2024_01",
        strategy_id="strategy_001"
    )
    
    print(f"原始采样 (air_lux_lx): {raw_lux} lx")
    print(f"推算特征 (plant_par_instant_umol): {result['value']} umol/(m2·s)")
    print(f"状态: {result['status']}")
    print(f"设备 ID: {result['device_id']}")
    print(f"批次 ID: {result['batch_id']}")
    print(f"策略 ID: {result['strategy_id']}")
    print(f"详细说明: {result['reasoning_context']}")
    
    # 测试低置信度场景
    print("\n--- 低置信度场景测试 ---")
    result_low_conf = PlantPhysiologyAnalytics.calculate_plant_par_instant_umol(
        raw_lux, 
        "sunlight",
        reliability_score=0.5,
        device_id="sensor_001",
        batch_id="batch_2024_01",
        strategy_id="strategy_001"
    )
    print(f"PAR 值: {result_low_conf['value']} umol/(m2·s)")
    print(f"状态: {result_low_conf['status']}")
    print(f"详细说明: {result_low_conf['reasoning_context']}")
    
    # 测试光照强度异常场景
    print("\n--- 光照强度异常场景测试 ---")
    result_high_lux = PlantPhysiologyAnalytics.calculate_plant_par_instant_umol(
        200000.0, 
        "sunlight",
        device_id="sensor_001",
        batch_id="batch_2024_01",
        strategy_id="strategy_001"
    )
    print(f"PAR 值: {result_high_lux['value']} umol/(m2·s)")
    print(f"状态: {result_high_lux['status']}")
    print(f"详细说明: {result_high_lux['reasoning_context']}")