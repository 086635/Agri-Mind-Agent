import pandas as pd
from datetime import datetime, timedelta
from typing import List, Dict

class ResourceEfficiencyTool:
    """
    二级数据分析工具库 - 资源效率与 ESG 价值算法
    """

    @staticmethod
    def calculate_plant_wue_efficiency_mg_l(
        total_nutrient_drawdown_mg: float,
        total_water_used_l: float,
        device_id: str = None,
        batch_id: str = None,
        reliability_score: float = 1.0
    ) -> dict:
        """
        算法：水分利用效率 (WUE)
        逻辑：每升水转化出的养分吸收量，反映灌溉的精准度
        
        SQL COMMENT: 映射至 esg_value_realization 字段。计算逻辑：养分吸收总量 (mg) / 灌溉总量 (L)。用于量化精准灌溉的资源转化效率。
        
        Args:
            total_nutrient_drawdown_mg: 统计周期内 NPK 吸收总增量 (mg)
            total_water_used_l: 统计周期内总灌溉量 (L)
            device_id: 设备 ID，用于标识不同设备的计算
            batch_id: 作物批次 ID
            reliability_score: 源自 NPK 传感器的置信度 (默认 1.0)
            
        Returns:
            dict: 包含 value、unit、status、reasoning_context、device_id、batch_id 的字典
        """

        # 确定状态
        status = "success"
        if reliability_score < 0.7:
            status = "warning"
        
        # 物理边界与异常检测
        if total_nutrient_drawdown_mg < 0:
            return {
                "value": 0.0,
                "unit": "mg/L",
                "status": status,
                "reasoning_context": "数据异常：检测到养分负向波动，疑似传感器漂移",
                "device_id": device_id,
                "batch_id": batch_id
            }
        
        if total_water_used_l <= 0:
            return {
                "value": 0.0,
                "unit": "mg/L",
                "status": status,
                "reasoning_context": "总灌溉量为 0，无法计算水分利用效率",
                "device_id": device_id,
                "batch_id": batch_id
            }
        
        if total_water_used_l < 0.1:
            return {
                "value": 0.0,
                "unit": "mg/L",
                "status": status,
                "reasoning_context": "采样量不足以进行效率评估",
                "device_id": device_id,
                "batch_id": batch_id
            }
            
        # 计算效率比
        wue_index = total_nutrient_drawdown_mg / total_water_used_l
        value = round(wue_index, 3)
        
        # 生成决策理由
        reasoning_context = f"基于总养分吸收 {total_nutrient_drawdown_mg} mg 和总灌溉量 {total_water_used_l} L，计算得出水分利用效率"
        
        # 添加数据质量警告
        if reliability_score < 0.7:
            reasoning_context += "\n由于养分传感器置信度低，WUE 评估结果仅供参考"
        
        # 添加决策反馈
        if value < 50:
            reasoning_context += "\n水分利用效率极低，建议检查灌溉 Skill 是否存在渗漏或死区"
        elif value > 150:
            reasoning_context += "\n系统表现出卓越的精准灌溉能力，可作为降本增效案例导出"
        elif value > 100:
            reasoning_context += "，水分利用效率高，灌溉精准"
        elif value > 50:
            reasoning_context += "，水分利用效率中等，建议优化灌溉策略"
        else:
            reasoning_context += "，水分利用效率低，需要大幅优化灌溉策略"
        
        # 返回结果
        return {
            "value": value,
            "unit": "mg/L",
            "status": status,
            "reasoning_context": reasoning_context,
            "device_id": device_id,
            "batch_id": batch_id
        }

def run_analysis(data: pd.DataFrame, config: dict) -> dict:
    """
    统一入口函数 - 计算植物水分利用效率
    
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
        reliability_score = config.get('reliability_score', 1.0)
        
        # 从 DataFrame 中提取数据
        # 假设 DataFrame 包含 nutrient_drawdown 和 water_used 列
        if 'nutrient_drawdown' not in data.columns or 'water_used' not in data.columns:
            return {
                'data_status': 'INVALID',
                'error': 'Missing required columns: nutrient_drawdown or water_used'
            }
        
        # 计算总养分吸收和总灌溉量
        total_nutrient_drawdown_mg = data['nutrient_drawdown'].sum()
        total_water_used_l = data['water_used'].sum()
        
        # 调用计算函数
        result = ResourceEfficiencyTool.calculate_plant_wue_efficiency_mg_l(
            total_nutrient_drawdown_mg=total_nutrient_drawdown_mg,
            total_water_used_l=total_water_used_l,
            device_id=device_id,
            batch_id=batch_id,
            reliability_score=reliability_score
        )
        
        # 转换结果格式，确保符合 AgriAnalyticalMetric 表字段
        return {
            'device_id': device_id,
            'batch_id': batch_id,
            'plant_wue_efficiency_mg_l': result['value'],
            'unit': result['unit'],
            'status': result['status'],
            'reasoning_context': result['reasoning_context']
        }
    except Exception as e:
        return {
            'data_status': 'INVALID',
            'error': str(e)
        }

# --- 模拟 ESG 价值计算上下文 ---
if __name__ == "__main__":
    # 假设通过 L2 表查询到昨日 NPK 浓度下降折合植物吸收了 450mg
    # AI 仅仅在土壤湿度低于阈值时触发了 2 次灌溉，每次 2L
    total_water = 4.2
    total_nutrient = 450.0
    
    # 测试正常场景
    wue = ResourceEfficiencyTool.calculate_plant_wue_efficiency_mg_l(
        total_nutrient_drawdown_mg=total_nutrient,
        total_water_used_l=total_water,
        device_id="device_001",
        batch_id="batch_2024_01"
    )
    
    print(f"--- 资源效率月报预览 (24h) ---")
    print(f"AI 实际耗水: {total_water} L")
    print(f"核心指标 (plant_wue_efficiency_mg_l): {wue['value']} {wue['unit']}")
    print(f"状态: {wue['status']}")
    print(f"设备 ID: {wue['device_id']}")
    print(f"批次 ID: {wue['batch_id']}")
    print(f"决策理由: {wue['reasoning_context']}")
    print(f"架构关联: 该数据将填入 esg_value_realization 表。")
    
    # 测试低置信度场景
    print("\n--- 低置信度场景测试 ---")
    wue_low_conf = ResourceEfficiencyTool.calculate_plant_wue_efficiency_mg_l(
        total_nutrient_drawdown_mg=total_nutrient,
        total_water_used_l=total_water,
        device_id="device_001",
        batch_id="batch_2024_01",
        reliability_score=0.5
    )
    print(f"WUE 值: {wue_low_conf['value']} {wue_low_conf['unit']}")
    print(f"状态: {wue_low_conf['status']}")
    print(f"决策理由: {wue_low_conf['reasoning_context']}")
    
    # 测试养分负向波动场景
    print("\n--- 养分负向波动场景测试 ---")
    wue_negative_nutrient = ResourceEfficiencyTool.calculate_plant_wue_efficiency_mg_l(
        total_nutrient_drawdown_mg=-100.0,
        total_water_used_l=total_water,
        device_id="device_001",
        batch_id="batch_2024_01"
    )
    print(f"WUE 值: {wue_negative_nutrient['value']} {wue_negative_nutrient['unit']}")
    print(f"状态: {wue_negative_nutrient['status']}")
    print(f"决策理由: {wue_negative_nutrient['reasoning_context']}")
    
    # 测试极微小灌溉场景
    print("\n--- 极微小灌溉场景测试 ---")
    wue_small_water = ResourceEfficiencyTool.calculate_plant_wue_efficiency_mg_l(
        total_nutrient_drawdown_mg=total_nutrient,
        total_water_used_l=0.05,
        device_id="device_001",
        batch_id="batch_2024_01"
    )
    print(f"WUE 值: {wue_small_water['value']} {wue_small_water['unit']}")
    print(f"状态: {wue_small_water['status']}")
    print(f"决策理由: {wue_small_water['reasoning_context']}")