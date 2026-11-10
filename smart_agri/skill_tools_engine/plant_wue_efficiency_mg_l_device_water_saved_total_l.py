from datetime import datetime, timedelta
from typing import List, Dict, Any
import numpy as np

class ResourceEfficiencyTool:
    """
    二级数据分析工具库 - 资源效率与 ESG 价值算法
    """

    @staticmethod
    def calc_device_water_saved_total_l(
        device_id: str,
        batch_id: str,
        actual_irrigation_events: List[Dict], 
        duration_hours: float,
        strategy_id: str,
        traditional_rate_l_hr: float = 10.0
    ) -> Dict[str, Any]:
        """
        算法：节水实效 (Water Saved)
        逻辑：传统固定灌溉总量 - AI 实际灌溉总量
        
        SQL COMMENT: 从表6提取实际灌溉量，对比表5中的传统灌溉阈值，计算节水量并存入表4(water_saved_liters)。
        
        Args:
            device_id: 设备唯一标识
            batch_id: 批次标识
            actual_irrigation_events: AI 触发的灌溉事件列表，含 ['volume_l', 'timestamp']
            duration_hours: 统计涵盖的总时长 (小时)
            strategy_id: 策略标识
            traditional_rate_l_hr: 传统模式下的平均小时耗水量 (L/h)
            
        Returns:
            Dict[str, Any]: 包含 device_id, batch_id, value, reliability_score, timestamp 的返回结构
        """
        try:
            # 时间窗口校验
            if duration_hours <= 0:
                return {
                    "device_id": device_id,
                    "batch_id": batch_id,
                    "value": 0.0,
                    "reliability_score": 0.0,
                    "timestamp": datetime.now().isoformat()
                }
            
            # 1. 计算传统模式下的预期耗水量 (Baseline)
            traditional_total = duration_hours * traditional_rate_l_hr
            
            # 2. 计算 AI 实际控制下的耗水量
            actual_total = sum(event.get('volume_l', 0) for event in actual_irrigation_events)
            
            # 3. 计算差值 (即节水量)
            water_saved = traditional_total - actual_total
            
            # 4. 处理负节水情况
            reliability_score = 1.0 if water_saved >= 0 else 0.5
            
            result = {
                "device_id": device_id,
                "batch_id": batch_id,
                "value": round(max(water_saved, 0.0), 2),
                "reliability_score": reliability_score,
                "timestamp": datetime.now().isoformat()
            }
            
            # 标记负节水风险
            if water_saved < 0:
                result["risk_level"] = "HIGH"
            
            return result
        except Exception as e:
            return {
                "device_id": device_id,
                "batch_id": batch_id,
                "value": 0.0,
                "reliability_score": 0.0,
                "timestamp": datetime.now().isoformat()
            }

    @staticmethod
    def calc_plant_wue_efficiency_mg_l(
        device_id: str,
        batch_id: str,
        total_nutrient_drawdown_mg: float,
        total_water_used_l: float,
        npk_reliability_avg: float,
        soil_ec_readings: List[float] = None
    ) -> Dict[str, Any]:
        """
        算法：水分利用效率 (WUE)
        逻辑：每升水转化出的养分吸收量，反映灌溉的精准度
        
        SQL COMMENT: 从表1提取NPK变化，结合灌溉量计算水分利用效率，填入表2(wue_efficiency)。
        
        Args:
            device_id: 设备唯一标识
            batch_id: 批次标识
            total_nutrient_drawdown_mg: 统计周期内 NPK 吸收总增量 (mg)
            total_water_used_l: 统计周期内总灌溉量 (L)
            npk_reliability_avg: NPK 数据可靠性平均值 (0-1)
            soil_ec_readings: 土壤电导率读数列表
            
        Returns:
            Dict[str, Any]: 包含 device_id, batch_id, value, reliability_score, timestamp 的返回结构
        """
        try:
            # 异常过滤
            if total_water_used_l <= 0 or total_nutrient_drawdown_mg < 0:
                return {
                    "device_id": device_id,
                    "batch_id": batch_id,
                    "value": 0.0,
                    "reliability_score": 0.0,
                    "timestamp": datetime.now().isoformat()
                }
            
            # 异常过滤：剔除灌溉瞬间产生的电导率剧烈波动噪声
            if soil_ec_readings:
                # 使用 numpy 矢量化处理
                ec_array = np.array(soil_ec_readings)
                if len(ec_array) > 1:
                    # 计算标准差
                    std_dev = np.std(ec_array)
                    # 过滤异常值（超过2个标准差）
                    filtered_ec = ec_array[np.abs(ec_array - np.mean(ec_array)) < 2 * std_dev]
                    # 如果过滤后数据不足，使用原始数据
                    if len(filtered_ec) < 2:
                        filtered_ec = ec_array
            
            # 交叉校验逻辑：如果 soil_ec 变化方向与养分下降方向背离，降低可靠性评分
            reliability_score = npk_reliability_avg
            if soil_ec_readings and len(soil_ec_readings) > 1:
                # 计算土壤电导率变化趋势
                ec_trend = np.mean(np.diff(soil_ec_readings))
                # 如果 EC 上升但养分下降，或者 EC 下降但养分上升，降低可靠性
                if (ec_trend > 0 and total_nutrient_drawdown_mg > 0) or (ec_trend < 0 and total_nutrient_drawdown_mg < 0):
                    reliability_score *= 0.5
            
            # 计算效率比
            wue_index = total_nutrient_drawdown_mg / total_water_used_l
            
            return {
                "device_id": device_id,
                "batch_id": batch_id,
                "value": round(wue_index, 3),
                "reliability_score": reliability_score,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "device_id": device_id,
                "batch_id": batch_id,
                "value": 0.0,
                "reliability_score": 0.0,
                "timestamp": datetime.now().isoformat()
            }

    @staticmethod
    def calc_carbon_footprint_g(
        device_id: str,
        batch_id: str,
        runtime_total: float,
        rated_power_w: float
    ) -> Dict[str, Any]:
        """
        算法：碳足迹计算
        逻辑：基于设备运行时间和额定功率计算碳足迹
        
        SQL COMMENT: 基于设备运行时间和额定功率计算碳足迹，填入表4(carbon_footprint_g)。
        
        Args:
            device_id: 设备唯一标识
            batch_id: 批次标识
            runtime_total: 设备总运行时间 (小时)
            rated_power_w: 设备额定功率 (瓦特)
            
        Returns:
            Dict[str, Any]: 包含 device_id, batch_id, value, reliability_score, timestamp 的返回结构
        """
        try:
            # 排放因子固定为：0.5703 kgCO2/kWh
            EMISSION_FACTOR = 0.5703  # kgCO2/kWh
            
            # 计算能耗 (kWh)
            energy_consumed_kwh = (rated_power_w * runtime_total) / 1000
            
            # 计算碳足迹 (g)
            carbon_footprint_g = energy_consumed_kwh * EMISSION_FACTOR * 1000
            
            # 可靠性评分
            reliability_score = 0.9 if all(x >= 0 for x in [runtime_total, rated_power_w]) else 0.5
            
            return {
                "device_id": device_id,
                "batch_id": batch_id,
                "value": round(carbon_footprint_g, 2),
                "reliability_score": reliability_score,
                "timestamp": datetime.now().isoformat()
            }
        except Exception as e:
            return {
                "device_id": device_id,
                "batch_id": batch_id,
                "value": 0.0,
                "reliability_score": 0.0,
                "timestamp": datetime.now().isoformat()
            }

# --- 测试场景 --- 
if __name__ == "__main__":
    # 测试场景 1: 正常节水情况
    print("=== 测试场景 1: 正常节水情况 ===")
    ai_actions = [
        {'timestamp': '2026-03-28 08:00', 'volume_l': 2.0},
        {'timestamp': '2026-03-28 16:00', 'volume_l': 2.2}
    ]
    
    saved_water_result = ResourceEfficiencyTool.calc_device_water_saved_total_l(
        device_id="greenhouse_001",
        batch_id="batch_20260328",
        actual_irrigation_events=ai_actions, 
        duration_hours=24, 
        strategy_id="strategy_001",
        traditional_rate_l_hr=1.5
    )
    print(f"节水计算结果: {saved_water_result}")
    
    # 测试场景 2: 负节水情况
    print("\n=== 测试场景 2: 负节水情况 ===")
    excessive_ai_actions = [
        {'timestamp': '2026-03-28 08:00', 'volume_l': 20.0},
        {'timestamp': '2026-03-28 12:00', 'volume_l': 25.0},
        {'timestamp': '2026-03-28 16:00', 'volume_l': 20.0}
    ]
    
    negative_saved_water_result = ResourceEfficiencyTool.calc_device_water_saved_total_l(
        device_id="greenhouse_002",
        batch_id="batch_20260328",
        actual_irrigation_events=excessive_ai_actions, 
        duration_hours=24, 
        strategy_id="strategy_002",
        traditional_rate_l_hr=1.5
    )
    print(f"负节水计算结果: {negative_saved_water_result}")
    
    # 测试场景 3: WUE 计算
    print("\n=== 测试场景 3: WUE 计算 ===")
    soil_ec_readings = [2.5, 2.6, 2.4, 2.7, 2.5, 5.0, 2.6]  # 包含异常值
    wue_result = ResourceEfficiencyTool.calc_plant_wue_efficiency_mg_l(
        device_id="greenhouse_001",
        batch_id="batch_20260328",
        total_nutrient_drawdown_mg=450.0,
        total_water_used_l=4.2,
        npk_reliability_avg=0.85,
        soil_ec_readings=soil_ec_readings
    )
    print(f"WUE 计算结果: {wue_result}")
    
    # 测试场景 4: 碳足迹计算
    print("\n=== 测试场景 4: 碳足迹计算 ===")
    carbon_result = ResourceEfficiencyTool.calc_carbon_footprint_g(
        device_id="greenhouse_001",
        batch_id="batch_20260328",
        runtime_total=24.0,  # 运行时间（小时）
        rated_power_w=1000  # 额定功率（瓦特）
    )
    print(f"碳足迹计算结果: {carbon_result}")
    
    # 测试场景 5: 蓝莓 A/B 测试组对比
    print("\n=== 测试场景 5: 蓝莓 A/B 测试组对比 ===")
    # A 组：AI 精准灌溉
    print("\nA 组 (AI 精准灌溉):")
    ai_actions_a = [
        {'timestamp': '2026-03-28 08:00', 'volume_l': 1.5},
        {'timestamp': '2026-03-28 14:00', 'volume_l': 1.8},
        {'timestamp': '2026-03-28 20:00', 'volume_l': 1.2}
    ]
    saved_water_a = ResourceEfficiencyTool.calc_device_water_saved_total_l(
        device_id="blueberry_ai_001",
        batch_id="blueberry_test_20260328",
        actual_irrigation_events=ai_actions_a, 
        duration_hours=24, 
        strategy_id="blueberry_ai_strategy",
        traditional_rate_l_hr=2.0
    )
    wue_a = ResourceEfficiencyTool.calc_plant_wue_efficiency_mg_l(
        device_id="blueberry_ai_001",
        batch_id="blueberry_test_20260328",
        total_nutrient_drawdown_mg=520.0,
        total_water_used_l=4.5,
        npk_reliability_avg=0.9,
        soil_ec_readings=[2.2, 2.3, 2.1, 2.2, 2.3]
    )
    carbon_a = ResourceEfficiencyTool.calc_carbon_footprint_g(
        device_id="blueberry_ai_001",
        batch_id="blueberry_test_20260328",
        runtime_total=8.0,  # 运行时间（小时）
        rated_power_w=800  # 额定功率（瓦特）
    )
    print(f"  节水量: {saved_water_a['value']} L")
    print(f"  WUE 效率: {wue_a['value']} mg/L")
    print(f"  碳足迹: {carbon_a['value']} g")
    
    # B 组：传统模式
    print("\nB 组 (传统模式):")
    ai_actions_b = [
        {'timestamp': '2026-03-28 08:00', 'volume_l': 4.0},
        {'timestamp': '2026-03-28 16:00', 'volume_l': 4.0}
    ]
    saved_water_b = ResourceEfficiencyTool.calc_device_water_saved_total_l(
        device_id="blueberry_trad_001",
        batch_id="blueberry_test_20260328",
        actual_irrigation_events=ai_actions_b, 
        duration_hours=24, 
        strategy_id="blueberry_trad_strategy",
        traditional_rate_l_hr=2.0
    )
    wue_b = ResourceEfficiencyTool.calc_plant_wue_efficiency_mg_l(
        device_id="blueberry_trad_001",
        batch_id="blueberry_test_20260328",
        total_nutrient_drawdown_mg=480.0,
        total_water_used_l=8.0,
        npk_reliability_avg=0.8,
        soil_ec_readings=[2.5, 2.6, 2.4, 2.5, 2.6]
    )
    carbon_b = ResourceEfficiencyTool.calc_carbon_footprint_g(
        device_id="blueberry_trad_001",
        batch_id="blueberry_test_20260328",
        runtime_total=12.0,  # 运行时间（小时）
        rated_power_w=1000  # 额定功率（瓦特）
    )
    print(f"  节水量: {saved_water_b['value']} L")
    print(f"  WUE 效率: {wue_b['value']} mg/L")
    print(f"  碳足迹: {carbon_b['value']} g")
    
    print("\n--- 测试完成 ---")
