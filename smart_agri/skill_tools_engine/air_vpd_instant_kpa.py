import math

class EnvironmentalPhysiologyTool:
    """
    二级数据分析工具库 - 环境生理学算法
    """

    @staticmethod
    def calculate_air_vpd_realtime_kpa(air_temp_c: float, air_humidity_pct: float, reliability_score: float = 1.0) -> dict:
        """
        算法：瞬时蒸气压亏缺 (VPD) 计算
        逻辑：基于 Tetens 公式计算饱和蒸气压，结合相对湿度推导亏缺值。
        
        计算公式：
        VPsat = 0.61078 * exp((17.27 * T) / (T + 237.3))
        VPD = VPsat * (1 - RH / 100)
        
        Args:
            air_temp_c (float): L1 传感器采集的环境温度 (°C)
            air_humidity_pct (float): L1 传感器采集的相对湿度 (%)
            reliability_score (float): 传感器数据的可靠性分数 (0.0-1.0)，默认 1.0
            
        Returns:
            dict: 包含以下字段的字典：
                - value: VPD 值 (kPa)
                - unit: 单位，固定为 "kPa"
                - reasoning_context: 基于 VPD 值的生理状态描述
                - reliability_score: 输入的可靠性分数
            
            VPD 值的生理意义：
            - < 0.4: 湿度过大，易滋生病菌，蒸腾停滞。
            - 0.8 - 1.2: 黄金生长区间。
            - > 1.6: 蒸腾过快，植物可能关闭气孔自保。
        """
        # 1. 置信度过滤
        if reliability_score < 0.5:
            return {
                "value": None,
                "unit": "kPa",
                "reasoning_context": "传感器数据可靠性分数过低 (< 0.5)，停止计算",
                "reliability_score": reliability_score
            }
        
        # 2. 异常情况处理
        if air_temp_c < 0:
            return {
                "value": None,
                "unit": "kPa",
                "reasoning_context": f"温度值异常: {air_temp_c}°C，温度不能为负数",
                "reliability_score": reliability_score
            }
        
        if air_humidity_pct < 0:
            return {
                "value": None,
                "unit": "kPa",
                "reasoning_context": f"湿度值异常: {air_humidity_pct}%，湿度不能为负数",
                "reliability_score": reliability_score
            }
        
        if air_humidity_pct >= 100.0:
            return {
                "value": 0.0,
                "unit": "kPa",
                "reasoning_context": "湿度为 100%，VPD 必然为 0，湿度过大，易滋生病菌，蒸腾停滞",
                "reliability_score": reliability_score
            }
        
        # 3. 计算饱和蒸气压 VPsat (单位: kPa)
        # Tetens 公式常数：a=0.61078, b=17.27, c=237.3
        vp_sat = 0.61078 * math.exp((17.27 * air_temp_c) / (air_temp_c + 237.3))
        
        # 4. 计算实际蒸气压亏缺量
        vpd = vp_sat * (1.0 - (air_humidity_pct / 100.0))
        vpd = round(vpd, 4)
        
        # 5. 生成生理状态描述
        if vpd < 0.4:
            reasoning_context = f"VPD 值为 {vpd} kPa，湿度过大，易滋生病菌，蒸腾停滞"
        elif 0.8 <= vpd <= 1.2:
            reasoning_context = f"VPD 值为 {vpd} kPa，处于黄金生长区间"
        elif vpd > 1.6:
            reasoning_context = f"VPD 值为 {vpd} kPa，蒸腾过快，植物可能关闭气孔自保"
        else:
            reasoning_context = f"VPD 值为 {vpd} kPa，处于正常范围"
        
        # 6. 返回结构化结果
        return {
            "value": vpd,
            "unit": "kPa",
            "reasoning_context": reasoning_context,
            "reliability_score": reliability_score
        }

# --- 模拟主动式智能体决策上下文 ---
if __name__ == "__main__":
    # 案例 1：典型温暖干旱环境
    temp_1, humi_1 = 30.0, 40.0
    vpd_1 = EnvironmentalPhysiologyTool.calculate_air_vpd_realtime_kpa(temp_1, humi_1)
    
    # 案例 2：高温高湿环境
    temp_2, humi_2 = 30.0, 85.0
    vpd_2 = EnvironmentalPhysiologyTool.calculate_air_vpd_realtime_kpa(temp_2, humi_2)
    
    # 案例 3：极端高湿环境
    temp_3, humi_3 = 25.0, 100.0
    vpd_3 = EnvironmentalPhysiologyTool.calculate_air_vpd_realtime_kpa(temp_3, humi_3)
    
    # 案例 4：传感器故障场景
    temp_4, humi_4 = 25.0, 60.0
    vpd_4 = EnvironmentalPhysiologyTool.calculate_air_vpd_realtime_kpa(temp_4, humi_4, reliability_score=0.2)
    
    # 案例 5：脏数据场景（负数湿度）
    temp_5, humi_5 = 25.0, -10.0
    vpd_5 = EnvironmentalPhysiologyTool.calculate_air_vpd_realtime_kpa(temp_5, humi_5)
    
    print(f"--- 实时 VPD 诊断报告 ---")
    print(f"场景 1 [干热]: {temp_1}°C, {humi_1}% -> VPD: {vpd_1['value']} kPa ({vpd_1['reasoning_context']})")
    print(f"场景 2 [湿热]: {temp_2}°C, {humi_2}% -> VPD: {vpd_2['value']} kPa ({vpd_2['reasoning_context']})")
    print(f"场景 3 [极端高湿]: {temp_3}°C, {humi_3}% -> VPD: {vpd_3['value']} kPa ({vpd_3['reasoning_context']})")
    print(f"场景 4 [传感器故障]: {temp_4}°C, {humi_4}% -> VPD: {vpd_4['value']} kPa ({vpd_4['reasoning_context']})")
    print(f"场景 5 [脏数据]: {temp_5}°C, {humi_5}% -> VPD: {vpd_5['value']} kPa ({vpd_5['reasoning_context']})")