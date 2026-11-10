from typing import Dict, List, Optional

class SensorDiagnosticAnalytics:
    """
    传感器诊断与置信度评估工具包
    用于一级热数据(L1)的物理逻辑校验，防止 Agent 幻觉执行
    """

    @staticmethod
    def verify_soil_npk_cross_reliability_score(
        soil_ec_raw_ms_cm: float,
        soil_npk_raw_group: Dict[str, float],
        base_reliability_score: float = 1.0,
        divergence_threshold: float = 0.4
    ) -> float:
        """
        通过 EC 与 NPK 的物理关联性进行交叉校验
        
        算法逻辑:
        1. 土壤 N/P/K 离子是 EC(电导率) 的主要贡献者。
        2. 逻辑 A: 如果 EC 保持平稳(或极低)，但 NPK 读数剧烈波动或极高，判定 NPK 传感器漂移。
        3. 逻辑 B: 如果 EC 大幅下降，但 NPK 依然显示高浓度，判定 NPK 传感器存在“挂壁”或“结晶”现象。
        
        Args:
            soil_ec_raw_ms_cm (float): L1表实时 EC 值 (mS/cm)
            soil_npk_raw_group (dict): L1表实时 NPK 值 {'n': x, 'p': y, 'k': z}
            base_reliability_score (float): 硬件驱动上报的原始置信度
            divergence_threshold (float): 允许的最大逻辑偏离度
            
        Returns:
            float: 修正后的 reliability_score (0.0 - 1.0)
        """
        # 计算 NPK 总和指数
        npk_sum = sum(soil_npk_raw_group.values())
        
        # 物理常识校准：EC 与 NPK 通常成正相关
        # 我们定义一个简易的“离子-电导”比率（实际环境需根据土壤类型微调系数）
        # 这里假设 1mS/cm 对应约 500-1000 mg/kg 的总养分
        expected_min_ec = npk_sum / 2000.0 
        
        # 判定是否存在逻辑冲突
        # 如果当前 EC 远低于 NPK 理论支撑的最低 EC，则存在重大逻辑漂移
        if soil_ec_raw_ms_cm < expected_min_ec * (1 - divergence_threshold):
            # 严重不一致，根据偏差程度惩罚置信度
            penalty = (expected_min_ec - soil_ec_raw_ms_cm) / expected_min_ec
            reliability_score = base_reliability_score * (1.0 - penalty)
        else:
            # 逻辑自洽，维持或缓慢恢复置信度
            reliability_score = min(1.0, base_reliability_score + 0.05)
            
        # 结果截断与格式化
        return max(0.0, round(reliability_score, 2))

# --- 模拟 OpenClaw 数据网关检测场景 ---
if __name__ == "__main__":
    # 场景 A: 正常工况
    ec_normal = 1.2
    npk_normal = {'n': 120, 'p': 60, 'k': 150} # 总和 330
    score_a = SensorDiagnosticAnalytics.verify_soil_npk_cross_reliability_score(ec_normal, npk_normal)
    
    # 场景 B: 故障工况 - NPK 读数极高，但 EC 极低（怀疑 NPK 传感器探头结晶或电路漂移）
    ec_fault = 0.1 
    npk_fault = {'n': 800, 'p': 400, 'k': 600} # 总和 1800，理论 EC 不应低于 0.9
    score_b = SensorDiagnosticAnalytics.verify_soil_npk_cross_reliability_score(ec_fault, npk_fault)
    
    print(f"正常传感器置信度: {score_a}") # 输出 1.0
    print(f"漂移传感器置信度: {score_b}") # 输出 0.11 (大幅扣分)