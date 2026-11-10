"""
LangGraph 工作流拓扑 - 农户操作经验量化

该模块实现完整的 LangGraph 工作流，遵循架构规范：
1. 所有节点函数使用 async def
2. 节点只调用外部服务，不包含业务逻辑
3. 每个节点都有完善的 try-except 错误处理
4. 工作流：Perception → Decision → Conflict Detection → Human-in-the-loop → Logic Closure → KnowledgeRefiner

工作流节点：
- intent_quantizer_node: 语义理由提取节点
- conflict_checker_node: 冲突检测节点
- logic_upsert_node: 规则持久化节点
- knowledge_refiner_node: 经验提取节点（KnowledgeRefiner）

状态更新规范：
- 所有节点必须返回增量更新的字典（如 {"comparison_report": "..."}）
- 严禁直接修改 state 对象
- 严禁返回全量替换的 state
- 返回值将被 LangGraph 自动合并到现有 state 中
"""

import logging
from typing import Literal, Dict, Any
from datetime import datetime
import json

from langgraph.graph import StateGraph, END

from agents.state import FarmState
from agents.nodes.knowledge_refiner_node import (
    knowledge_refiner_node,
    should_refine_knowledge
)
from services.experience_quantizer import experience_quantizer
from services.conflict_checker import conflict_checker
from services.logic_upsert import logic_upsert_service
from database import AsyncSessionLocal

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


def _log_state_transition(
    node_name: str,
    state_before: Dict[str, Any],
    state_update: Dict[str, Any],
    is_error: bool = False
) -> None:
    """
    记录状态转换日志
    
    Args:
        node_name: 节点名称
        state_before: 节点执行前的状态（关键键）
        state_update: 节点返回的状态更新
        is_error: 是否为错误状态
    """
    # 提取关键状态键
    keys_before = set(state_before.keys())
    keys_update = set(state_update.keys())
    keys_new = keys_update - keys_before
    
    logger.info(f"[{node_name}] 状态转换日志:")
    logger.info(f"  - 更新前状态键: {sorted(keys_before)}")
    logger.info(f"  - 返回更新键: {sorted(keys_update)}")
    logger.info(f"  - 新增键: {sorted(keys_new) if keys_new else '无'}")
    
    if is_error:
        logger.error(f"  - 状态: 错误")
    else:
        logger.info(f"  - 状态: 成功")
    
    # 记录具体更新内容（敏感信息脱敏）
    safe_update = {}
    for key, value in state_update.items():
        if key in ['human_reasoning', 'quantized_logic']:
            # 脱敏处理：只记录长度或类型
            safe_update[key] = f"<{type(value).__name__}, len={len(str(value)) if value else 0}>"
        else:
            safe_update[key] = value
    
    logger.info(f"  - 更新内容: {json.dumps(safe_update, ensure_ascii=False, default=str)}")


def _validate_state_update(node_name: str, update: Dict[str, Any]) -> bool:
    """
    验证状态更新是否符合 LangGraph 规范
    
    Args:
        node_name: 节点名称
        update: 节点返回的状态更新字典
    
    Returns:
        是否符合规范
    """
    if not isinstance(update, dict):
        logger.error(f"[{node_name}] 状态更新验证失败: 返回值不是字典类型")
        return False
    
    # 检查是否为空更新
    if not update:
        logger.warning(f"[{node_name}] 状态更新为空字典")
        return True
    
    # 检查是否包含非法键（如 'state' 键，表示可能的全量替换）
    if 'state' in update:
        logger.error(f"[{node_name}] 状态更新验证失败: 包含非法键 'state'，可能试图全量替换")
        return False
    
    logger.info(f"[{node_name}] 状态更新验证通过: 返回增量更新字典")
    return True


# ============================================================================
# 节点函数定义
# ============================================================================

async def intent_quantizer_node(state: FarmState) -> dict:
    """
    语义理由提取节点
    
    职责：
    1. 接收农户口语化理由
    2. 调用经验量化服务
    3. 返回量化后的规则（增量更新字典）
    
    注意：
    - 该节点只调用服务，不包含业务逻辑
    - 必须返回增量更新的字典，而不是全量替换 state
    - LangGraph 会自动将返回值合并到现有 state 中
    """
    print(f"\n{'='*80}")
    print(f"--- [Graph Runtime] Entering Node: intent_quantizer_node ---")
    print(f"{'='*80}")
    
    # 记录进入节点时的状态键
    state_keys_on_entry = list(state.keys())
    logger.info(f"[intent_quantizer_node] 节点入口 - 当前状态键: {state_keys_on_entry}")
    
    try:
        logger.info("[intent_quantizer_node] 开始语义理由提取")
        
        # 获取农户原始理由
        human_reasoning = state.get("human_reasoning")
        
        if not human_reasoning:
            logger.error("[intent_quantizer_node] 缺少农户原始理由")
            # 增量更新：只返回错误信息
            result = {
                "error_message": "缺少农户原始理由",
                "updated_at": datetime.now()
            }
            # 记录状态转换
            _log_state_transition("intent_quantizer_node", state, result, is_error=True)
            # 验证返回格式
            _validate_state_update("intent_quantizer_node", result)
            print(f"\n--- [Graph Runtime] Exiting Node: intent_quantizer_node ---")
            print(f"返回数据: {result}")
            print(f"{'='*80}\n")
            return result
        
        # 调用经验量化服务
        context = {
            "device_id": state.get("device_id"),
            "batch_id": state.get("batch_id"),
            "actor_id": state.get("actor_id")
        }
        
        quantized_logic = await experience_quantizer.quantify_experience(
            human_reasoning=human_reasoning,
            context=context
        )
        
        logger.info(f"[intent_quantizer_node] 语义理由提取成功: {quantized_logic.get('metric_name')}")
        
        # 增量更新：只返回量化后的规则和时间戳
        # 不包含原始理由（已存在于 state 中）
        result = {
            "quantized_logic": quantized_logic,
            "updated_at": datetime.now()
        }
        
        # 记录状态转换（更新前 -> 更新后）
        _log_state_transition("intent_quantizer_node", state, result)
        # 验证返回格式符合 LangGraph 规范
        _validate_state_update("intent_quantizer_node", result)
        
        print(f"\n--- [Graph Runtime] Exiting Node: intent_quantizer_node ---")
        print(f"返回数据: {result}")
        print(f"{'='*80}\n")
        return result
        
    except Exception as e:
        logger.error(f"[intent_quantizer_node] 节点执行异常: {str(e)}")
        # 增量更新：返回错误信息
        result = {
            "error_message": f"语义理由提取失败: {str(e)}",
            "conflict_detected": True,
            "conflict_details": {"error": str(e)},
            "updated_at": datetime.now()
        }
        # 记录状态转换
        _log_state_transition("intent_quantizer_node", state, result, is_error=True)
        # 验证返回格式
        _validate_state_update("intent_quantizer_node", result)
        
        print(f"\n--- [Graph Runtime] Exiting Node: intent_quantizer_node (异常) ---")
        print(f"返回数据: {result}")
        print(f"{'='*80}\n")
        return result


async def conflict_checker_node(state: FarmState) -> dict:
    """
    冲突检测节点
    
    职责：
    1. 接收量化后的规则
    2. 调用冲突检测服务
    3. 返回冲突检测结果（增量更新字典）
    
    注意：
    - 该节点只调用服务，不包含业务逻辑
    - 必须返回增量更新的字典，而不是全量替换 state
    - LangGraph 会自动将返回值合并到现有 state 中
    """
    print(f"\n{'='*80}")
    print(f"--- [Graph Runtime] Entering Node: conflict_checker_node ---")
    print(f"{'='*80}")
    
    # 记录进入节点时的状态键
    state_keys_on_entry = list(state.keys())
    logger.info(f"[conflict_checker_node] 节点入口 - 当前状态键: {state_keys_on_entry}")
    
    try:
        logger.info("[conflict_checker_node] 开始冲突检测")
        
        # 获取量化规则
        quantized_logic = state.get("quantized_logic")
        
        if not quantized_logic:
            logger.error("[conflict_checker_node] 缺少量化规则")
            # 增量更新：只返回错误信息和冲突标记
            result = {
                "error_message": "缺少量化规则",
                "conflict_detected": True,
                "updated_at": datetime.now()
            }
            # 记录状态转换
            _log_state_transition("conflict_checker_node", state, result, is_error=True)
            # 验证返回格式
            _validate_state_update("conflict_checker_node", result)
            
            print(f"\n--- [Graph Runtime] Exiting Node: conflict_checker_node ---")
            print(f"返回数据: {result}")
            print(f"{'='*80}\n")
            return result
        
        # 使用数据库会话进行冲突检测（支持行级锁）
        async with AsyncSessionLocal() as session:
            conflict_result = await conflict_checker.check_conflict(
                quantized_logic=quantized_logic,
                session=session
            )
            
            # 如果没有冲突，继续；否则返回冲突信息
            has_conflict = conflict_result.get("has_conflict", False)
            
            if has_conflict:
                logger.warning(f"[conflict_checker_node] 检测到冲突: {conflict_result.get('conflict_type')}")
                
                # 增量更新：返回冲突检测结果
                result = {
                    "conflict_detected": True,
                    "conflict_details": conflict_result,
                    "conflict_resolution": conflict_result.get("resolution_suggestion"),
                    "updated_at": datetime.now()
                }
                
                # 记录状态转换（有冲突）
                _log_state_transition("conflict_checker_node", state, result, is_error=True)
                # 验证返回格式
                _validate_state_update("conflict_checker_node", result)
                
                print(f"\n--- [Graph Runtime] Exiting Node: conflict_checker_node ---")
                print(f"返回数据: {result}")
                print(f"{'='*80}\n")
                return result
            else:
                logger.info("[conflict_checker_node] 无冲突，规则安全")
                
                # 增量更新：返回无冲突标记
                result = {
                    "conflict_detected": False,
                    "conflict_details": {},
                    "updated_at": datetime.now()
                }
                
                # 记录状态转换（无冲突）
                _log_state_transition("conflict_checker_node", state, result)
                # 验证返回格式
                _validate_state_update("conflict_checker_node", result)
                
                print(f"\n--- [Graph Runtime] Exiting Node: conflict_checker_node ---")
                print(f"返回数据: {result}")
                print(f"{'='*80}\n")
                return result
        
    except Exception as e:
        logger.error(f"[conflict_checker_node] 节点执行异常: {str(e)}")
        # 增量更新：返回错误信息
        result = {
            "error_message": f"冲突检测失败: {str(e)}",
            "conflict_detected": True,
            "conflict_details": {"error": str(e)},
            "updated_at": datetime.now()
        }
        # 记录状态转换
        _log_state_transition("conflict_checker_node", state, result, is_error=True)
        # 验证返回格式
        _validate_state_update("conflict_checker_node", result)
        
        print(f"\n--- [Graph Runtime] Exiting Node: conflict_checker_node (异常) ---")
        print(f"返回数据: {result}")
        print(f"{'='*80}\n")
        return result


async def logic_upsert_node(state: FarmState) -> dict:
    """
    规则持久化节点
    
    职责：
    1. 接收量化规则
    2. 调用规则持久化服务
    3. 返回持久化结果（增量更新字典）
    
    注意：
    - 该节点只调用服务，不包含业务逻辑
    - 必须返回增量更新的字典，而不是全量替换 state
    - LangGraph 会自动将返回值合并到现有 state 中
    """
    print(f"\n{'='*80}")
    print(f"--- [Graph Runtime] Entering Node: logic_upsert_node ---")
    print(f"{'='*80}")
    
    # 记录进入节点时的状态键
    state_keys_on_entry = list(state.keys())
    logger.info(f"[logic_upsert_node] 节点入口 - 当前状态键: {state_keys_on_entry}")
    
    try:
        logger.info("[logic_upsert_node] 开始规则持久化")
        
        # 获取量化规则和原始理由
        quantized_logic = state.get("quantized_logic")
        human_reasoning = state.get("human_reasoning")
        actor_id = state.get("actor_id", "Human")
        device_id = state.get("device_id")
        batch_id = state.get("batch_id")
        
        if not quantized_logic:
            logger.error("[logic_upsert_node] 缺少量化规则")
            # 增量更新：只返回错误信息
            result = {
                "error_message": "缺少量化规则",
                "updated_at": datetime.now()
            }
            # 记录状态转换
            _log_state_transition("logic_upsert_node", state, result, is_error=True)
            # 验证返回格式
            _validate_state_update("logic_upsert_node", result)
            
            print(f"\n--- [Graph Runtime] Exiting Node: logic_upsert_node ---")
            print(f"返回数据: {result}")
            print(f"{'='*80}\n")
            return result
        
        # 调用规则持久化服务
        upsert_result = await logic_upsert_service.upsert_logic(
            quantized_logic=quantized_logic,
            human_reasoning=human_reasoning,
            actor_id=actor_id,
            device_id=device_id,
            batch_id=batch_id
        )
        
        if upsert_result.get("success"):
            logger.info(f"[logic_upsert_node] 规则持久化成功: policy_id={upsert_result.get('policy_id')}")
            
            # 增量更新：只返回审计ID和时间戳
            # 不包含 quantized_logic（已存在于 state 中）
            result = {
                "audit_id": upsert_result.get("audit_id"),
                "updated_at": datetime.now()
            }
            
            # 记录状态转换（成功）
            _log_state_transition("logic_upsert_node", state, result)
            # 验证返回格式
            _validate_state_update("logic_upsert_node", result)
            
            print(f"\n--- [Graph Runtime] Exiting Node: logic_upsert_node ---")
            print(f"返回数据: {result}")
            print(f"{'='*80}\n")
            return result
        else:
            logger.error(f"[logic_upsert_node] 规则持久化失败: {upsert_result.get('message')}")
            
            # 增量更新：返回错误信息
            result = {
                "error_message": upsert_result.get("message"),
                "updated_at": datetime.now()
            }
            # 记录状态转换
            _log_state_transition("logic_upsert_node", state, result, is_error=True)
            # 验证返回格式
            _validate_state_update("logic_upsert_node", result)
            
            print(f"\n--- [Graph Runtime] Exiting Node: logic_upsert_node ---")
            print(f"返回数据: {result}")
            print(f"{'='*80}\n")
            return result
        
    except Exception as e:
        logger.error(f"[logic_upsert_node] 节点执行异常: {str(e)}")
        # 增量更新：返回错误信息
        result = {
            "error_message": f"规则持久化失败: {str(e)}",
            "updated_at": datetime.now()
        }
        # 记录状态转换
        _log_state_transition("logic_upsert_node", state, result, is_error=True)
        # 验证返回格式
        _validate_state_update("logic_upsert_node", result)
        
        print(f"\n--- [Graph Runtime] Exiting Node: logic_upsert_node (异常) ---")
        print(f"返回数据: {result}")
        print(f"{'='*80}\n")
        return result


# ============================================================================
# 条件边定义
# ============================================================================

def should_continue(state: FarmState) -> Literal["logic_upsert", "end"]:
    """
    条件边：判断是否继续持久化
    
    如果检测到冲突，终止流程；否则继续持久化
    """
    conflict_detected = state.get("conflict_detected", False)
    
    if conflict_detected:
        logger.info("[条件边] 检测到冲突，终止流程")
        return "end"
    else:
        logger.info("[条件边] 无冲突，继续持久化")
        return "logic_upsert"


def detect_human_actor(state: FarmState) -> Literal["experience_extraction", "normal_flow"]:
    """
    条件边：检测是否为人工干预
    
    如果 actor_id 为 "Human"，触发经验提取分支
    """
    actor_id = state.get("actor_id", "")
    manual_override = state.get("manual_override", False)
    
    if actor_id == "Human" or manual_override:
        logger.info("[条件边] 检测到人工干预，触发经验提取分支")
        return "experience_extraction"
    else:
        logger.info("[条件边] 正常流程")
        return "normal_flow"


# ============================================================================
# 工作流构建
# ============================================================================

def build_experience_quantization_graph():
    """
    构建经验量化工作流图
    
    工作流拓扑：
    START -> intent_quantizer -> conflict_checker -> logic_upsert -> knowledge_refiner -> END
                                              |
                                              +-> END (如果检测到冲突)
    
    KnowledgeRefiner 分支：
    - logic_upsert 后添加 knowledge_refiner 节点
    - 使用 should_refine_knowledge 条件边判断是否触发经验提取
    """
    workflow = StateGraph(FarmState)
    
    workflow.add_node("intent_quantizer", intent_quantizer_node)
    workflow.add_node("conflict_checker", conflict_checker_node)
    workflow.add_node("logic_upsert", logic_upsert_node)
    workflow.add_node("knowledge_refiner", knowledge_refiner_node)
    
    workflow.set_entry_point("intent_quantizer")
    
    workflow.add_edge("intent_quantizer", "conflict_checker")
    
    workflow.add_conditional_edges(
        "conflict_checker",
        should_continue,
        {
            "logic_upsert": "logic_upsert",
            "end": END
        }
    )
    
    workflow.add_edge("logic_upsert", "knowledge_refiner")
    
    workflow.add_conditional_edges(
        "knowledge_refiner",
        should_refine_knowledge,
        {
            "refine": "knowledge_refiner",
            "end": END
        }
    )
    
    workflow.add_edge("knowledge_refiner", END)
    
    app = workflow.compile()
    
    logger.info("经验量化工作流图构建完成（含 KnowledgeRefiner 节点）")
    
    return app


# 创建全局应用实例
app = build_experience_quantization_graph()


# ============================================================================
# 辅助函数
# ============================================================================

async def run_experience_quantization(
    human_reasoning: str,
    actor_id: str = "Human",
    device_id: str = None,
    batch_id: str = None
) -> dict:
    """
    运行经验量化工作流
    
    Args:
        human_reasoning: 农户原始理由
        actor_id: 操作者ID
        device_id: 设备ID
        batch_id: 批次ID
    
    Returns:
        工作流执行结果
    """
    from agents.state import create_learning_state
    
    # 创建学习状态
    initial_state = create_learning_state(
        human_reasoning=human_reasoning,
        actor_id=actor_id,
        device_id=device_id,
        batch_id=batch_id
    )
    
    # 运行工作流
    config = {"configurable": {"thread_id": f"exp_{datetime.now().timestamp()}"}}
    result = await app.ainvoke(initial_state, config=config)
    
    return result


# ============================================================================
# 导出
# ============================================================================

__all__ = [
    "app",
    "run_experience_quantization",
    "intent_quantizer_node",
    "conflict_checker_node",
    "logic_upsert_node",
    "knowledge_refiner_node",
    "should_refine_knowledge"
]
