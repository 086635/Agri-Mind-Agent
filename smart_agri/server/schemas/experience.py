"""
经验反馈接口的 Pydantic 模型定义

使用 Pydantic v2 Strict Mode 进行严格类型验证
"""

from pydantic import BaseModel, Field, ConfigDict, field_validator, model_validator
from typing import List, Dict, Any, Optional, Literal
from datetime import datetime


# ==================== 基础模型 ====================

class ActionItem(BaseModel):
    """操作项模型"""
    model_config = ConfigDict(strict=True, extra='forbid')

    device: str = Field(
        ...,
        min_length=1,
        max_length=64,
        description="设备ID，如 window_01, fan_01"
    )
    action: str = Field(
        ...,
        min_length=1,
        max_length=128,
        description="操作类型，如 open, start, adjust"
    )
    value: float = Field(
        ...,
        ge=0,
        le=100,
        description="操作值，通常为百分比"
    )
    unit: str = Field(
        ...,
        min_length=1,
        max_length=32,
        description="单位，如 pct, degree, liter"
    )

    @field_validator('device', 'action', 'unit')
    @classmethod
    def validate_not_empty(cls, v: str) -> str:
        """验证字段非空"""
        if not v or not v.strip():
            raise ValueError('字段不能为空或仅包含空格')
        return v.strip()


class EnvSnapshot(BaseModel):
    """环境快照模型"""
    model_config = ConfigDict(strict=True, extra='forbid')

    temperature: Optional[float] = Field(
        None,
        ge=-50,
        le=60,
        description="温度（摄氏度）"
    )
    humidity: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="湿度（百分比）"
    )
    weather: Optional[str] = Field(
        None,
        max_length=64,
        description="天气状况，如 晴转多云"
    )
    soil_moisture: Optional[float] = Field(
        None,
        ge=0,
        le=100,
        description="土壤湿度（百分比）"
    )
    light_intensity: Optional[float] = Field(
        None,
        ge=0,
        description="光照强度（lux）"
    )
    custom_params: Optional[Dict[str, Any]] = Field(
        None,
        description="自定义环境参数"
    )


class MatchedLogicItem(BaseModel):
    """匹配的历史逻辑项"""
    model_config = ConfigDict(strict=True, extra='forbid')

    logic_id: int = Field(..., ge=1, description="逻辑ID")
    similarity: float = Field(..., ge=0, le=1, description="相似度分数")
    description: str = Field(..., min_length=1, description="逻辑描述")
    actions: List[str] = Field(..., min_length=1, description="动作列表")
    metric_name: Optional[str] = Field(None, description="指标名称")
    condition: Optional[str] = Field(None, description="触发条件")


# ==================== Execute 接口模型 ====================

class ExecuteRequest(BaseModel):
    """执行操作请求模型"""
    model_config = ConfigDict(strict=True, extra='forbid')

    actions: List[ActionItem] = Field(
        ...,
        min_length=1,
        max_length=10,
        description="操作列表，最多10个操作"
    )
    reasoning: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="操作理由"
    )
    env_snapshot: EnvSnapshot = Field(
        ...,
        description="环境快照"
    )

    @field_validator('reasoning')
    @classmethod
    def validate_reasoning(cls, v: str) -> str:
        """验证理由非空"""
        if not v or not v.strip():
            raise ValueError('操作理由不能为空或仅包含空格')
        return v.strip()


class AnalysisResult(BaseModel):
    """分析结果模型"""
    model_config = ConfigDict(strict=True, extra='forbid')

    is_new_pattern: bool = Field(..., description="是否为新模式")
    matched_logics: List[MatchedLogicItem] = Field(
        default_factory=list,
        description="匹配的历史逻辑列表"
    )
    explanation: str = Field(..., description="解释文案")


class ExecuteResponse(BaseModel):
    """执行操作响应模型"""
    model_config = ConfigDict(strict=True, extra='forbid')

    status: Literal["pending_confirmation"] = Field(
        "pending_confirmation",
        description="状态：待确认"
    )
    session_id: str = Field(..., description="会话ID")
    audit_id: int = Field(..., description="审计记录ID")
    analysis: AnalysisResult = Field(..., description="分析结果")
    options: List[str] = Field(
        default=["confirm_logic", "adjust_logic", "new_logic"],
        description="用户选项"
    )


# ==================== Confirm 接口模型 ====================

class ConfirmLogicRequest(BaseModel):
    """确认逻辑请求模型"""
    model_config = ConfigDict(strict=True, extra='forbid')

    session_id: str = Field(..., min_length=1, max_length=64, description="会话ID")
    feedback_type: Literal["confirm_logic"] = Field(
        "confirm_logic",
        description="反馈类型：确认逻辑"
    )
    selected_logic_id: int = Field(..., ge=1, description="选择的逻辑ID")


class AdjustLogicRequest(BaseModel):
    """调整逻辑请求模型"""
    model_config = ConfigDict(strict=True, extra='forbid')

    session_id: str = Field(..., min_length=1, max_length=64, description="会话ID")
    feedback_type: Literal["adjust_logic"] = Field(
        "adjust_logic",
        description="反馈类型：调整逻辑"
    )
    selected_logic_id: int = Field(..., ge=1, description="选择的逻辑ID")
    adjustments: Dict[str, Any] = Field(
        ...,
        description="调整参数"
    )

    @field_validator('adjustments')
    @classmethod
    def validate_adjustments(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        """验证调整参数非空"""
        if not v:
            raise ValueError('调整参数不能为空')
        return v


class NewLogicRequest(BaseModel):
    """新建逻辑请求模型"""
    model_config = ConfigDict(strict=True, extra='forbid')

    session_id: str = Field(..., min_length=1, max_length=64, description="会话ID")
    feedback_type: Literal["new_logic"] = Field(
        "new_logic",
        description="反馈类型：新建逻辑"
    )
    new_reasoning: str = Field(
        ...,
        min_length=1,
        max_length=500,
        description="新的推理描述"
    )

    @field_validator('new_reasoning')
    @classmethod
    def validate_new_reasoning(cls, v: str) -> str:
        """验证新推理非空"""
        if not v or not v.strip():
            raise ValueError('新推理描述不能为空或仅包含空格')
        return v.strip()


# 使用 Union 类型支持三种请求
ConfirmRequest = ConfirmLogicRequest | AdjustLogicRequest | NewLogicRequest


class ConfirmResponse(BaseModel):
    """确认反馈响应模型"""
    model_config = ConfigDict(strict=True, extra='forbid')

    status: Literal["success"] = Field("success", description="状态：成功")
    audit_id: int = Field(..., description="审计记录ID")
    logic_updated: bool = Field(..., description="逻辑是否更新")
    new_version: Optional[int] = Field(None, description="新版本号")
    message: str = Field(..., description="消息")


# ==================== History 接口模型 ====================

class LogicVersion(BaseModel):
    """逻辑版本模型"""
    model_config = ConfigDict(strict=True, extra='forbid')

    version: int = Field(..., ge=1, description="版本号")
    created_at: str = Field(..., description="创建时间")
    is_active: bool = Field(..., description="是否为当前活跃版本")
    parent_id: Optional[str] = Field(None, description="父版本ID")
    reasoning: Optional[str] = Field(None, description="推理描述")
    threshold_logic: Optional[Dict[str, Any]] = Field(None, description="阈值逻辑")


class LogicHistoryResponse(BaseModel):
    """逻辑历史响应模型"""
    model_config = ConfigDict(strict=True, extra='forbid')

    logic_id: int = Field(..., description="逻辑ID")
    current_version: int = Field(..., ge=1, description="当前版本号")
    history: List[LogicVersion] = Field(..., description="版本历史列表")


# ==================== 错误响应模型 ====================

class ErrorResponse(BaseModel):
    """错误响应模型"""
    model_config = ConfigDict(strict=True, extra='forbid')

    status: Literal["error"] = Field("error", description="状态：错误")
    request_id: str = Field(..., description="请求ID，用于追踪")
    msg: str = Field(..., description="错误消息")
    errors: Optional[List[Dict[str, Any]]] = Field(None, description="详细错误列表")
    detail: Optional[str] = Field(None, description="详细错误信息（仅调试模式）")
