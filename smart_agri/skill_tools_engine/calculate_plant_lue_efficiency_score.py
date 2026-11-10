import pandas as pd
from datetime import datetime
from typing import List, Dict, Tuple, Any, Optional

class ResourceEfficiencyAnalytics:
    """
    资源效率分析工具包 - 聚焦降本增效指标
    集成 MCP 语义规范，用于二级数据特征提取
    """

    @staticmethod
    def calculate_plant_lue_efficiency_score(
        dli_natural_mol: float,
        dli_artificial_mol: float,
        electricity_cost_total: float,
        target_dli: float = None,
        base_electricity_rate: float = 0.05,
        input_reliability_score: float = 1.0,
        crop_type: str = "general",
        device_id: str = None,
        batch_id: str = None,
        strategy_id: str = None
    ) -> Dict[str, Any]:
        """
        计算光利用率 (LUE) 综合评分
        
        SQL COMMENT: 映射至 agri_analytical_metrics.lue_score。逻辑：综合 DLI 达成率、自然光占比与补光电能经济性，量化光资源利用效率。
        
        逻辑：
        1. 达成率因子：实际总 DLI 是否达到目标值（保障产量）。
        2. 成本因子：每提供 1 mol 人工光所花费的电费（评估是否在低价电时段补光）。
        3. 资产利用因子：自然光在总光照中的占比。
        
        Args:
            dli_natural_mol: 今日自然光积分 (mol/m²/d)
            dli_artificial_mol: 今日人工补光积分 (mol/m²/d)
            electricity_cost_total: 今日补光总电费支出 (CNY)
            target_dli: 该作物设定的每日理想 DLI 目标 (mol/m²/d)，若未提供则根据作物类型自动设置
            base_electricity_rate: 基础电价 (CNY/mol)
            input_reliability_score: 输入数据可靠性评分 (0-1)
            crop_type: 作物类型，支持 "blueberry" 和 "succulent"
            device_id: 设备ID
            batch_id: 批次ID
            strategy_id: 策略ID
            
        Returns:
            Dict[str, Any]: LUE 评分结果，包含 value、unit、status、reasoning_context、device_id、batch_id、strategy_id 字段
        """
        # 根据作物类型设置默认 target_dli
        if target_dli is None:
            if crop_type == "blueberry":
                target_dli = 15.0
            elif crop_type == "succulent":
                target_dli = 8.0
            else:
                target_dli = 15.0  # 默认值
        
        # 检查数据可信度
        if input_reliability_score < 0.6:
            return {
                "value": 0.0,
                "unit": "score",
                "status": "warning",
                "reasoning_context": "数据源可信度存疑",
                "device_id": device_id,
                "batch_id": batch_id,
                "strategy_id": strategy_id
            }
        
        total_dli = dli_natural_mol + dli_artificial_mol
        
        # 防御性检查：总光照为零的情况
        if total_dli == 0:
            return {
                "value": 0.0,
                "unit": "score",
                "status": "error",
                "reasoning_context": "总光照为零，无法计算光利用率",
                "device_id": device_id,
                "batch_id": batch_id,
                "strategy_id": strategy_id
            }
        
        # 1. 生产达标率 (如果总光照不足，效率再高也是减产，分数降低)
        attainment_factor = min(1.0, total_dli / target_dli) if target_dli > 0 else 0
        
        # 2. 自然光贡献率 (自然光是免费资产，占比越高越好)
        natural_ratio = (dli_natural_mol / total_dli) if total_dli > 0 else 0
        
        # 3. 经济效率 (每 mol 人工光的成本)
        # 全自然光处理：当没有人工补光且总光照达标时，经济因子为 1.0
        if dli_artificial_mol == 0:
            if total_dli >= target_dli:
                economic_factor = 1.0
            else:
                economic_factor = 0.0
        else:
            min_cost_per_mol = base_electricity_rate
            actual_cost_per_mol = electricity_cost_total / dli_artificial_mol
            economic_factor = min(1.0, min_cost_per_mol / actual_cost_per_mol)
        
        # 综合评分逻辑：(40% 达标率 + 30% 自然光利用 + 30% 补光经济性) * 100
        lue_score = (attainment_factor * 0.4 + natural_ratio * 0.3 + economic_factor * 0.3) * 100
        
        # 生成结构化建议
        suggestions = []
        if economic_factor < 0.7:
            suggestions.append('补光成本高于预期，建议核查补光时段是否避开峰电')
        if attainment_factor < 1.0:
            suggestions.append('总 DLI 未达标，存在减产风险')
        
        # 构建返回字典
        result = {
            "value": round(lue_score, 2),
            "unit": "score",
            "status": "success",
            "reasoning_context": {
                "factors": {
                    "total_dli": round(total_dli, 2),
                    "attainment_factor": round(attainment_factor, 2),
                    "natural_ratio": round(natural_ratio, 2),
                    "economic_factor": round(economic_factor, 2)
                },
                "suggestions": suggestions
            },
            "device_id": device_id,
            "batch_id": batch_id,
            "strategy_id": strategy_id
        }
        
        return result

def run_analysis(data: pd.DataFrame, config: dict) -> dict:
    """
    统一入口函数 - 计算植物光利用率
    
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
        target_dli = config.get('target_dli', None)
        base_electricity_rate = config.get('base_electricity_rate', 0.05)
        input_reliability_score = config.get('input_reliability_score', 1.0)
        crop_type = config.get('crop_type', 'general')
        
        # 从 DataFrame 中提取数据
        # 假设 DataFrame 包含 dli_natural_mol, dli_artificial_mol, electricity_cost_total 列
        if 'dli_natural_mol' not in data.columns or 'dli_artificial_mol' not in data.columns or 'electricity_cost_total' not in data.columns:
            return {
                'data_status': 'INVALID',
                'error': 'Missing required columns: dli_natural_mol, dli_artificial_mol, or electricity_cost_total'
            }
        
        # 提取数据值
        dli_natural_mol = data['dli_natural_mol'].sum()
        dli_artificial_mol = data['dli_artificial_mol'].sum()
        electricity_cost_total = data['electricity_cost_total'].sum()
        
        # 调用计算函数
        result = ResourceEfficiencyAnalytics.calculate_plant_lue_efficiency_score(
            dli_natural_mol=dli_natural_mol,
            dli_artificial_mol=dli_artificial_mol,
            electricity_cost_total=electricity_cost_total,
            target_dli=target_dli,
            base_electricity_rate=base_electricity_rate,
            input_reliability_score=input_reliability_score,
            crop_type=crop_type,
            device_id=device_id,
            batch_id=batch_id,
            strategy_id=strategy_id
        )
        
        # 转换结果格式，确保符合 AgriAnalyticalMetric 表字段
        return {
            'device_id': device_id,
            'batch_id': batch_id,
            'strategy_id': strategy_id,
            'plant_lue_efficiency_score': result['value'],
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
    # 场景：今天阴天，自然光只有 5 mol。Agent 在凌晨低价电补充了 10 mol。
    # 假设总电费 0.6 元。
    result = ResourceEfficiencyAnalytics.calculate_plant_lue_efficiency_score(
        dli_natural_mol=5.2,
        dli_artificial_mol=10.1,
        electricity_cost_total=0.6,
        target_dli=15.0,
        device_id="DEV-001",
        batch_id="BATCH-20260329",
        strategy_id="STRAT-001"
    )
    
    print(f"今日光利用率综合评分 (plant_lue_efficiency_score): {result['value']} {result['unit']}")
    print(f"状态: {result['status']}")
    print("计算上下文:")
    print(f"  总DLI: {result['reasoning_context']['factors']['total_dli']}")
    print(f"  达标率: {result['reasoning_context']['factors']['attainment_factor']}")
    print(f"  自然光占比: {result['reasoning_context']['factors']['natural_ratio']}")
    print(f"  经济因子: {result['reasoning_context']['factors']['economic_factor']}")
    if result['reasoning_context']['suggestions']:
        print("建议:")
        for suggestion in result['reasoning_context']['suggestions']:
            print(f"  - {suggestion}")
    print(f"设备ID: {result['device_id']}")
    print(f"批次ID: {result['batch_id']}")
    print(f"策略ID: {result['strategy_id']}")