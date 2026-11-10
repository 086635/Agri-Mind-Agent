import json
from typing import Dict, List, Any


class AgriExperimentAnalytics:
    """
    农业 A/B Testing 实验决策工具包
    用于分析不同 NPK 水平、光照策略等对生长指标的贡献差异
    """

    @staticmethod
    def analyze_strategy_performance_gain(
        control_metrics: Dict[str, float],
        test_metrics: Dict[str, float],
        batch_id: str,
        target_indicators: List[str] = [
            "carbon_sink_rate_g_hr", "gdd_accumulated", "lue_score"
        ],
        weights: Dict[str, float] = None,
        reliability_scores: Dict[str, float] = None
    ) -> Dict[str, Any]:
        """
        SQL COMMENT: 对比不同 strategy_id 的 agri_analytical_metrics 均值。
        核心字段：winner_strategy_id。

        对比实验组与对照组的生长效率差异

        Args:
            control_metrics: 对照组(A组)的平均二级指标数据
            test_metrics: 实验组(B组)的平均二级指标数据
            batch_id: 批次ID
            target_indicators: 需要对比的关键评估指标列表
            weights: 各指标权重字典，默认值为 carbon_sink_rate_g_hr: 0.5,
                lue_score: 0.3, gdd_accumulated: 0.2
            reliability_scores: 数据置信度评分字典，用于过滤低置信度数据

        Returns:
            Dict: 包含各指标增益百分比及"最优方案"建议，
                或 status: "INVALID_DATA" 当数据置信度不足时
        """
        # 检查数据置信度
        if reliability_scores:
            # 计算平均可靠性评分
            scores = []
            for score in reliability_scores.values():
                if score is not None:
                    scores.append(score)
            if scores:
                avg_reliability = sum(scores) / len(scores)
                if avg_reliability < 0.6:
                    return {
                        "status": "INVALID_DATA",
                        "batch_id": batch_id,
                        "message": (
                            f"数据置信度不足，平均可靠性评分: {avg_reliability:.2f} < 0.6"
                        ),
                        "reasoning_context": "数据置信度不足，无法做出决策"
                    }

        # 设置默认权重
        if weights is None:
            weights = {
                "carbon_sink_rate_g_hr": 0.5,
                "lue_score": 0.3,
                "gdd_accumulated": 0.2
            }

        analysis_results = {}
        analysis_results["status"] = "VALID"
        performance_score = 0

        # 计算权重总和并归一化
        weight_sum = sum(
            weights.get(indicator, 0) for indicator in target_indicators
        )
        if weight_sum == 0:
            weight_sum = 1.0  # 避免除零错误

        for indicator in target_indicators:
            # 检查可靠性评分
            if reliability_scores:
                if reliability_scores.get(indicator, 1.0) < 0.5:
                    continue

            val_a = control_metrics.get(indicator, 0)
            val_b = test_metrics.get(indicator, 0)

            # 计算增长率 (Gain Ratio)
            if val_a != 0:
                gain_pct = ((val_b - val_a) / val_a) * 100
            else:
                gain_pct = 0.0

            analysis_results[f"{indicator}_gain_pct"] = round(gain_pct, 2)

            # 加权性能计算，使用归一化后的权重
            weight = weights.get(indicator, 1.0) / weight_sum
            performance_score += gain_pct * weight

        # 判定最优策略
        analysis_results["batch_id"] = batch_id
        analysis_results["winner_strategy_id"] = (
            "TEST_GROUP_B" if performance_score > 0 else "CONTROL_GROUP_A"
        )
        analysis_results["confidence_score"] = (
            "HIGH" if abs(performance_score) > 15 else "LOW"
        )

        # 生成决策理由
        if analysis_results["winner_strategy_id"] == "TEST_GROUP_B":
            # 找出贡献最大的指标
            max_gain = -float('inf')
            max_indicator = None
            for indicator in target_indicators:
                gain_key = f"{indicator}_gain_pct"
                if gain_key in analysis_results:
                    gain = analysis_results[gain_key]
                    if gain > max_gain:
                        max_gain = gain
                        max_indicator = indicator

            # 生成理由文本
            if max_indicator:
                # 指标名称映射
                indicator_names = {
                    "carbon_sink_rate_g_hr": "碳汇速率",
                    "gdd_accumulated": "积温",
                    "lue_score": "光利用率 (LUE)"
                }
                # 获取指标名称
                indicator_name = indicator_names.get(
                    max_indicator, max_indicator
                )
                # 构建理由文本
                reasoning = (
                    "策略 B 胜出，主因是" + indicator_name +
                    "提升了" + f"{max_gain:.2f}%"
                )
                analysis_results["reasoning_context"] = reasoning
            else:
                analysis_results["reasoning_context"] = "策略 B 胜出"
        else:
            analysis_results["reasoning_context"] = "策略 A 胜出"

        return analysis_results


# --- 高浓度 NPK 策略与标准策略对比测试场景 ---
if __name__ == "__main__":
    # 模拟从数据库 agri_analytical_metrics 提取的二级聚合数据
    # 标准策略组：标准 NPK 水平
    standard_strategy_metrics = {
        "carbon_sink_rate_g_hr": 1.25,
        "gdd_accumulated": 450.0,
        "lue_score": 0.78
    }

    # 高浓度 NPK 策略组：NPK 提升 30% 的实验水平
    high_npk_strategy_metrics = {
        "carbon_sink_rate_g_hr": 1.55,  # 碳汇显著提升
        "gdd_accumulated": 462.0,       # 积温略有增加
        "lue_score": 0.85               # 光利用率明显提升
    }

    # 模拟数据置信度评分
    reliability_scores = {
        "carbon_sink_rate_g_hr": 0.85,
        "gdd_accumulated": 0.90,
        "lue_score": 0.88
    }

    # 执行对比算法
    report = AgriExperimentAnalytics.analyze_strategy_performance_gain(
        control_metrics=standard_strategy_metrics,
        test_metrics=high_npk_strategy_metrics,
        batch_id="batch_20260329",
        reliability_scores=reliability_scores
    )

    # 构建完整的结构化 JSON 报告
    full_report = {
        "experiment_name": "高浓度 NPK 策略 vs 标准策略对比实验",
        "experiment_id": "EXP-NPK-2026-03-29",
        "test_strategy": "高浓度 NPK 策略",
        "control_strategy": "标准策略",
        "metrics": {
            "standard_strategy": standard_strategy_metrics,
            "high_npk_strategy": high_npk_strategy_metrics
        },
        "analysis_results": report,
        "timestamp": "2026-03-29T12:00:00Z",
        "recommendation": (
            "采用高浓度 NPK 策略"
            if report.get("winner_strategy_id") == "TEST_GROUP_B"
            else "保持标准策略"
        )
    }

    # 输出 JSON 格式报告
    print(json.dumps(full_report, ensure_ascii=False, indent=2))


# --- MCP 接口对接说明 ---
"""
MCP (Model Context Protocol) 接口对接说明：

1. 此模块可作为 MCP 工具函数集成到 Trae 技能系统中
2. 对接方式：
   - 在 MCP 配置文件中注册此工具函数
   - 输入参数：
     {
       "control_metrics": 标准策略的指标数据,
       "test_metrics": 高浓度 NPK 策略的指标数据,
       "batch_id": "批次ID",
       "target_indicators": [
           "carbon_sink_rate_g_hr", "gdd_accumulated", "lue_score"
       ],
       "weights": {
           "carbon_sink_rate_g_hr": 0.5,
           "lue_score": 0.3,
           "gdd_accumulated": 0.2
       },
       "reliability_scores": {
           "carbon_sink_rate_g_hr": 0.85,
           "gdd_accumulated": 0.90,
           "lue_score": 0.88
       }
     }
   - 输出：结构化 JSON 报告，可直接返回给调用方

3. 数据来源：
   - 可从数据库 agri_analytical_metrics 表获取实时聚合数据
   - 也可通过传感器实时采集数据进行计算

4. 扩展建议：
   - 可根据实际需求调整目标指标列表
   - 可添加更复杂的权重计算模型
   - 可集成统计显著性检验以提高决策可靠性

5. 函数调用示例：
   - 使用 `analyze_strategy_performance_gain` 函数
   - 必须提供 `batch_id` 参数
   - `weights` 和 `reliability_scores` 为可选参数
"""
