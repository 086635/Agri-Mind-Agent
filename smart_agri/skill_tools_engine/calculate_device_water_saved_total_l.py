from datetime import datetime, timedelta
from typing import List, Dict
import pandas as pd

class ResourceEfficiencyTool:
    """
    二级数据分析工具库 - 资源效率与 ESG 价值算法
    """

    @staticmethod
    def calculate_device_water_saved_total_l(
        actual_irrigation_events: List[Dict], 
        duration_hours: float,
        traditional_rate_l_hr: float = 10.0,
        threshold_high: float = 0.5,
        threshold_mid: float = 0.2,
        device_id: str = None
    ) -> dict:
        """
        算法：节水实效 (Water Saved)
        逻辑：传统固定灌溉总量 - AI 实际灌溉总量
        
        Args:
            actual_irrigation_events: AI 触发的灌溉事件列表，含 ['volume_l']
            duration_hours: 统计涵盖的总时长 (小时)
            traditional_rate_l_hr: 传统模式下的平均小时耗水量 (L/h)
            threshold_high: 节水效果显著的阈值 (默认 0.5)
            threshold_mid: 节水效果良好的阈值 (默认 0.2)
            device_id: 设备 ID，用于标识不同设备的计算
            
        Returns:
            dict: 包含节水量、状态、决策理由和动作反馈的字典
        
        SQL COMMENT:
        该指标用于评估 AI 灌溉策略的节水实效，通过对比传统定时灌溉与 AI 按需驱动的耗水差异，
        量化节水效果。
        数据去向：esg_value_realization.water_saved_liters
        属于 OpenClaw 架构中的 L4 价值实现层指标，为 ESG 价值评估提供数据支撑。
        
        成本节省关联：
        该算法通过 water_saved_liters 进一步支撑 cost_reduction_amount 的计算，
        公式为：节省的水量 × 当地水费 = 成本节省。
        """
        # 1. 数据防御与鲁棒性
        if duration_hours <= 0:
            return {
                "value": 0.0,
                "unit": "L",
                "status": "error",
                "reasoning_context": f"统计时长必须为正数: {duration_hours}",
                "actual_delta": 0.0,
                "device_id": device_id
            }

        if traditional_rate_l_hr <= 0:
            return {
                "value": 0.0,
                "unit": "L",
                "status": "error",
                "reasoning_context": f"传统模式耗水率必须为正数: {traditional_rate_l_hr}",
                "actual_delta": 0.0,
                "device_id": device_id
            }

        if actual_irrigation_events is None or not isinstance(actual_irrigation_events, list):
            return {
                "value": 0.0,
                "unit": "L",
                "status": "error",
                "reasoning_context": "灌溉事件列表必须为非空列表",
                "actual_delta": 0.0,
                "device_id": device_id
            }

        # 2. 计算传统模式下的预期耗水量 (Baseline)
        traditional_total = duration_hours * traditional_rate_l_hr
        
        # 3. 计算 AI 实际控制下的耗水量
        actual_total = sum(event.get('volume_l', 0) for event in actual_irrigation_events)
        
        # 4. 计算差值 (即节水量)
        water_saved = traditional_total - actual_total
        water_saved = max(water_saved, 0.0)
        
        # 5. 生成决策理由和状态
        if actual_total > traditional_total:
            # AI 费水情况
            status = "warning"
            reasoning_context = f"设备 {device_id} 传统模式下预期耗水 {traditional_total:.2f} L，AI 实际耗水 {actual_total:.2f} L，AI 比传统模式多消耗 {actual_total - traditional_total:.2f} L"
            reasoning_context += "，建议检查策略阈值或传感器校准"
        else:
            # AI 节水情况
            status = "success"
            reasoning_context = f"设备 {device_id} 传统模式下预期耗水 {traditional_total:.2f} L，AI 实际耗水 {actual_total:.2f} L，节省 {water_saved:.2f} L"
            
            # 使用动态阈值进行评价
            # 注：这些阈值未来应从 policy_risk_thresholds 表中动态加载
            if water_saved > traditional_total * threshold_high:
                reasoning_context += "，节水效果显著"
            elif water_saved > traditional_total * threshold_mid:
                reasoning_context += "，节水效果良好"
            else:
                reasoning_context += "，节水效果一般，建议进一步优化"
        
        return {
            "value": round(water_saved, 2),
            "unit": "L",
            "status": status,
            "reasoning_context": reasoning_context,
            "actual_delta": water_saved,
            "device_id": device_id
        }

# --- 模拟 ESG 价值计算上下文 ---
if __name__ == "__main__":
    # 模拟过去 24 小时的数据
    # AI 仅仅在土壤湿度低于阈值时触发了 2 次灌溉，每次 2L
    ai_actions = [
        {'timestamp': '2026-03-28 08:00', 'volume_l': 2.0},
        {'timestamp': '2026-03-28 16:00', 'volume_l': 2.2}
    ]
    
    # 假设该温室如果采用传统模式，每小时平均滴灌 1.5L
    saved_water = ResourceEfficiencyTool.calculate_device_water_saved_total_l(
        ai_actions, 
        duration_hours=24, 
        traditional_rate_l_hr=1.5,
        device_id="device_001"
    )
    
    print(f"--- 资源效率月报预览 (24h) ---")
print(f"传统预期耗水: 36.0 L")
print(f"AI 实际耗水: 4.2 L")
print(f"核心指标 (device_water_saved_total_l): {saved_water['value']} L")
print(f"决策理由: {saved_water['reasoning_context']}")
print(f"架构关联: 该数据将填入 esg_value_realization 表。")


def run_analysis(data: pd.DataFrame, config: dict) -> dict:
    """
    插件式架构统一入口函数
    
    Args:
        data: 包含过去 24 小时传感器数据的 Pandas DataFrame
        config: 包含设备 ID、策略阈值等配置
        
    Returns:
        dict: 包含计算结果的字典，Key 对应 AgriAnalyticalMetric 数据库表中的字段名
    """
    try:
        # 从 config 中提取参数
        device_id = config.get('device_id', None)
        duration_hours = config.get('duration_hours', 24.0)
        traditional_rate_l_hr = config.get('traditional_rate_l_hr', 10.0)
        threshold_high = config.get('threshold_high', 0.5)
        threshold_mid = config.get('threshold_mid', 0.2)
        
        # 从 data 中提取灌溉事件
        actual_irrigation_events = []
        if 'irrigation_events' in data.columns:
            for _, row in data.iterrows():
                if isinstance(row['irrigation_events'], dict) and 'volume_l' in row['irrigation_events']:
                    actual_irrigation_events.append(row['irrigation_events'])
        elif 'volume_l' in data.columns:
            for _, row in data.iterrows():
                if pd.notna(row['volume_l']):
                    actual_irrigation_events.append({'volume_l': row['volume_l']})
        
        # 调用核心算法
        result = ResourceEfficiencyTool.calculate_device_water_saved_total_l(
            actual_irrigation_events=actual_irrigation_events,
            duration_hours=duration_hours,
            traditional_rate_l_hr=traditional_rate_l_hr,
            threshold_high=threshold_high,
            threshold_mid=threshold_mid,
            device_id=device_id
        )
        
        # 转换为符合 AgriAnalyticalMetric 表字段的返回格式
        return {
            'water_saved_liters': result['value'],
            'device_id': device_id,
            'status': result['status'],
            'reasoning_context': result['reasoning_context']
        }
    except Exception as e:
        # 异常处理
        return {
            'data_status': 'INVALID',
            'error_message': str(e)
        }