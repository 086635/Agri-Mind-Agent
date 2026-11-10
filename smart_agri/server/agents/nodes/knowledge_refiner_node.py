"""
KnowledgeRefiner LangGraph 节点

该模块实现经验提取节点，负责：
1. 监控 agent_action_audit 表中的人工干预行为
2. 通过冲突检测识别高价值经验点
3. 通过 LLM 提取隐性知识
4. 将量化经验存储至 RAGVectorStore

特性：
- 异步非阻塞执行（asyncio.create_task）
- 去重逻辑（相似度自检）
- 详细日志记录
- 错误处理不中断主流程
"""

import os
import json
import logging
import asyncio
from typing import Dict, Any, Optional, Literal
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

DEDUP_SIMILARITY_THRESHOLD = float(os.getenv("DEDUP_SIMILARITY_THRESHOLD", "0.95"))


async def knowledge_refiner_node(state: Dict[str, Any]) -> Dict[str, Any]:
    """
    KnowledgeRefiner 节点 - 经验提取节点
    
    职责：
    1. 检测人工干预（actor_id == 'Human'）
    2. 调用冲突检测服务
    3. 调用知识蒸馏服务
    4. 持久化到 RAG 向量库
    5. 更新审计记录
    
    注意：
    - 该节点使用异步非阻塞执行
    - 错误不会中断主流程
    - 返回增量更新字典
    """
    print(f"\n{'='*80}")
    print(f"--- [Graph Runtime] Entering Node: knowledge_refiner_node ---")
    print(f"{'='*80}")
    
    logger.info("[knowledge_refiner_node] 开始经验提取流程")
    
    try:
        actor_id = state.get("actor_id", "")
        
        if actor_id != "Human":
            logger.info(f"[knowledge_refiner_node] 非人工干预 (actor_id={actor_id})，跳过经验提取")
            result = {
                "knowledge_refined": False,
                "refinement_skipped_reason": "non_human_actor",
                "updated_at": datetime.now().isoformat()
            }
            print(f"\n--- [Graph Runtime] Exiting Node: knowledge_refiner_node (跳过) ---")
            return result
        
        audit_id = state.get("audit_id")
        if not audit_id:
            logger.warning("[knowledge_refiner_node] 缺少 audit_id，跳过经验提取")
            result = {
                "knowledge_refined": False,
                "refinement_skipped_reason": "missing_audit_id",
                "updated_at": datetime.now().isoformat()
            }
            return result
        
        reasoning_context = state.get("human_reasoning", "")
        expected_delta = state.get("quantized_logic", {})
        actual_delta = state.get("actual_delta", {})
        env_snapshot = state.get("env_snapshot", {})
        
        if not actual_delta:
            logger.warning("[knowledge_refiner_node] 缺少 actual_delta，跳过经验提取")
            result = {
                "knowledge_refined": False,
                "refinement_skipped_reason": "missing_actual_delta",
                "updated_at": datetime.now().isoformat()
            }
            return result
        
        from services.conflict_detector import conflict_detector
        from services.knowledge_distiller import knowledge_distiller
        from tools.rag_vector_store import rag_vector_store
        
        logger.info("[knowledge_refiner_node] 步骤 1: 冲突检测")
        
        conflict_result = await conflict_detector.detect_conflict(
            agent_reasoning=reasoning_context,
            agent_expected_action=expected_delta,
            human_actual_action=actual_delta,
            env_snapshot=env_snapshot
        )
        
        if not conflict_result.get("is_high_value_experience"):
            logger.info("[knowledge_refiner_node] 非高价值经验点，跳过蒸馏")
            result = {
                "knowledge_refined": False,
                "refinement_skipped_reason": "not_high_value_experience",
                "conflict_result": conflict_result,
                "updated_at": datetime.now().isoformat()
            }
            return result
        
        logger.info("[knowledge_refiner_node] 步骤 2: 知识蒸馏")
        
        distilled_knowledge = await knowledge_distiller.distill_from_conflict_result(conflict_result)
        
        if not distilled_knowledge:
            logger.warning("[knowledge_refiner_node] 知识蒸馏失败，跳过存储")
            result = {
                "knowledge_refined": False,
                "refinement_skipped_reason": "distillation_failed",
                "conflict_result": conflict_result,
                "updated_at": datetime.now().isoformat()
            }
            return result
        
        confidence = distilled_knowledge.get("confidence_score", 0.5)
        if confidence < 0.5:
            logger.warning(f"[knowledge_refiner_node] 低置信度 ({confidence})，标记为待审核")
            distilled_knowledge["needs_review"] = True
        
        logger.info("[knowledge_refiner_node] 步骤 3: 去重检查")
        
        query_text = f"{distilled_knowledge.get('condition', '')} {distilled_knowledge.get('action', '')}"
        similar_rules = await rag_vector_store.search_similar_rules(query_text, k=3)
        
        for rule in similar_rules:
            similarity = rule.get("similarity_score", 0)
            if similarity > DEDUP_SIMILARITY_THRESHOLD:
                logger.info(f"[knowledge_refiner_node] 去重跳过: 相似度 {similarity:.3f} > 阈值 {DEDUP_SIMILARITY_THRESHOLD}")
                result = {
                    "knowledge_refined": False,
                    "refinement_skipped_reason": "duplicate",
                    "similarity_score": similarity,
                    "conflict_result": conflict_result,
                    "distilled_knowledge": distilled_knowledge,
                    "updated_at": datetime.now().isoformat()
                }
                return result
        
        logger.info("[knowledge_refiner_node] 步骤 4: 写入向量库")
        
        metadata = {
            "audit_ref": str(audit_id),
            "actor_id": actor_id,
            "conflict_type": conflict_result.get("conflict_type"),
            "confidence_score": confidence
        }
        
        doc_id = await rag_vector_store.add_rule(
            quantized_logic=distilled_knowledge,
            metadata=metadata
        )
        
        logger.info(f"[knowledge_refiner_node] ✅ 经验已存储: doc_id={doc_id}")
        
        logger.info("[knowledge_refiner_node] 步骤 5: 更新审计记录")
        
        await _mark_audit_as_experience_source(audit_id)
        
        result = {
            "knowledge_refined": True,
            "doc_id": doc_id,
            "conflict_result": conflict_result,
            "distilled_knowledge": distilled_knowledge,
            "updated_at": datetime.now().isoformat()
        }
        
        print(f"\n--- [Graph Runtime] Exiting Node: knowledge_refiner_node (成功) ---")
        print(f"返回数据: knowledge_refined=True, doc_id={doc_id}")
        print(f"{'='*80}\n")
        
        return result
        
    except Exception as e:
        logger.error(f"[knowledge_refiner_node] 节点执行异常: {str(e)}")
        
        result = {
            "knowledge_refined": False,
            "refinement_error": str(e),
            "updated_at": datetime.now().isoformat()
        }
        
        print(f"\n--- [Graph Runtime] Exiting Node: knowledge_refiner_node (异常) ---")
        print(f"返回数据: {result}")
        print(f"{'='*80}\n")
        
        return result


async def _mark_audit_as_experience_source(audit_id: int) -> bool:
    """
    标记审计记录为经验来源
    
    Args:
        audit_id: 审计记录 ID
    
    Returns:
        是否成功
    """
    try:
        from database import AsyncSessionLocal
        from models import AgentActionAudit
        from sqlalchemy import update
        
        async with AsyncSessionLocal() as session:
            stmt = (
                update(AgentActionAudit)
                .where(AgentActionAudit.audit_id == audit_id)
                .values(is_experience_source=True)
            )
            await session.execute(stmt)
            await session.commit()
        
        logger.info(f"[knowledge_refiner_node] 审计记录已标记: audit_id={audit_id}")
        return True
        
    except Exception as e:
        logger.error(f"[knowledge_refiner_node] 标记审计记录失败: {str(e)}")
        return False


async def refine_knowledge_background(state: Dict[str, Any]) -> None:
    """
    后台异步执行经验提取（非阻塞）
    
    使用 asyncio.create_task 在后台执行，
    不阻塞主控制链路的响应速度
    
    Args:
        state: 工作流状态
    """
    try:
        logger.info("[KnowledgeRefiner] 启动后台经验提取任务")
        result = await knowledge_refiner_node(state)
        
        if result.get("knowledge_refined"):
            logger.info(f"[KnowledgeRefiner] 后台经验提取成功: doc_id={result.get('doc_id')}")
        else:
            logger.info(f"[KnowledgeRefiner] 后台经验提取跳过: {result.get('refinement_skipped_reason')}")
            
    except Exception as e:
        logger.error(f"[KnowledgeRefiner] 后台经验提取异常: {str(e)}")


def should_refine_knowledge(state: Dict[str, Any]) -> Literal["refine", "end"]:
    """
    条件边：判断是否触发经验提取
    
    Args:
        state: 工作流状态
    
    Returns:
        "refine" 或 "end"
    """
    actor_id = state.get("actor_id", "")
    manual_override = state.get("manual_override", False)
    has_actual_delta = bool(state.get("actual_delta"))
    
    if (actor_id == "Human" or manual_override) and has_actual_delta:
        logger.info("[条件边] 检测到人工干预，触发经验提取")
        return "refine"
    else:
        logger.info("[条件边] 无需经验提取")
        return "end"


__all__ = [
    "knowledge_refiner_node",
    "refine_knowledge_background",
    "should_refine_knowledge"
]
