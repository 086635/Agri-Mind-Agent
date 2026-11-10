"""
FarmState - 农场智能体状态定义

该模块定义了 LangGraph 工作流中使用的状态结构，支持：
- 感知-决策-冲突检测-人工干预-逻辑闭环的完整流程
- 农户操作经验量化功能
- 人工干预触发经验提取分支

重要：使用 Annotated 标记确保状态字段正确更新
"""

from typing import TypedDict, Optional, List, Dict, Any, Literal, Annotated
from operator import add
from langchain_core.messages import BaseMessage, AnyMessage
from langgraph.graph.message import add_messages
from datetime import datetime


class FarmState(TypedDict, total=False):
    """
    农场智能体状态 - 支持完整的工作流规范
    
    工作流规范：Perception → Decision → Conflict Detection → Human-in-the-loop → Logic Closure
    
    核心字段：
        messages: LangChain 消息历史，用于对话式交互
            - 使用 add_messages reducer 确保消息正确追加和更新
            - 支持消息 ID 追踪和人工干预修改
        sensor_data: 传感器数据快照
        weather_data: 天气数据快照
        comparison_report: 决策报告
    
    经验量化扩展字段：
        action_trigger: 触发源类型
        human_reasoning: 农户原始语音/文本理由
        quantized_logic: LLM 转换后的结构化 JSON 规则
        is_learning_mode: 是否处于经验捕获状态
        manual_override: 人工干预标识
        actor_id: 操作者ID（Human/Agent）
    
    冲突检测字段：
        conflict_detected: 是否检测到冲突
        conflict_details: 冲突详细信息
        conflict_resolution: 冲突解决方案
    
    审计字段：
        audit_id: 审计记录ID
        created_at: 状态创建时间
        updated_at: 状态更新时间
    
    重要说明：
        - 使用 Annotated 标记的字段会使用指定的 reducer 函数进行更新
        - messages 字段使用 add_messages reducer，支持消息追加和更新
        - 未使用 Annotated 的字段使用默认的 OverwriteReducer（全量替换）
    """
    
    # === 核心工作流字段 ===
    # messages 使用 add_messages reducer，确保消息正确追加和更新
    messages: Annotated[List[AnyMessage], add_messages]
    sensor_data: Optional[Dict[str, Any]]
    weather_data: Optional[Dict[str, Any]]
    comparison_report: Optional[str]
    
    # === 经验量化扩展字段 ===
    action_trigger: Optional[Literal["DEVICE_EVENT", "USER_INPUT"]]
    human_reasoning: Optional[str]
    quantized_logic: Optional[Dict[str, Any]]
    is_learning_mode: Optional[bool]
    manual_override: Optional[bool]
    actor_id: Optional[str]
    
    # === 冲突检测字段 ===
    conflict_detected: Optional[bool]
    conflict_details: Optional[Dict[str, Any]]
    conflict_resolution: Optional[str]
    
    # === 审计字段 ===
    audit_id: Optional[int]
    created_at: Optional[datetime]
    updated_at: Optional[datetime]
    
    # === 元数据字段 ===
    device_id: Optional[str]
    batch_id: Optional[str]
    error_message: Optional[str]


def initialize_farm_state(
    device_id: Optional[str] = None,
    batch_id: Optional[str] = None,
    action_trigger: Optional[Literal["DEVICE_EVENT", "USER_INPUT"]] = None,
    is_learning_mode: bool = False
) -> FarmState:
    """
    初始化农场状态
    
    Args:
        device_id: 设备ID
        batch_id: 批次ID
        action_trigger: 触发源类型
        is_learning_mode: 是否处于经验捕获状态
    
    Returns:
        初始化后的 FarmState 实例
    """
    now = datetime.now()
    
    return FarmState(
        messages=[],
        sensor_data=None,
        weather_data=None,
        comparison_report=None,
        action_trigger=action_trigger,
        human_reasoning=None,
        quantized_logic=None,
        is_learning_mode=is_learning_mode,
        manual_override=False,
        actor_id=None,
        conflict_detected=False,
        conflict_details=None,
        conflict_resolution=None,
        audit_id=None,
        created_at=now,
        updated_at=now,
        device_id=device_id,
        batch_id=batch_id,
        error_message=None
    )


def create_learning_state(
    human_reasoning: str,
    actor_id: str = "Human",
    device_id: Optional[str] = None,
    batch_id: Optional[str] = None
) -> FarmState:
    """
    创建经验学习状态
    
    当检测到人工干预时，使用此函数创建学习状态
    
    Args:
        human_reasoning: 农户原始语音/文本理由
        actor_id: 操作者ID（默认为 Human）
        device_id: 设备ID
        batch_id: 批次ID
    
    Returns:
        配置为学习模式的 FarmState 实例
    """
    state = initialize_farm_state(
        device_id=device_id,
        batch_id=batch_id,
        action_trigger="USER_INPUT",
        is_learning_mode=True
    )
    
    state["human_reasoning"] = human_reasoning
    state["actor_id"] = actor_id
    state["manual_override"] = True
    
    return state
