from sqlalchemy import Column, BigInteger, String, Numeric, DateTime, Date, Boolean, Text, Index, UniqueConstraint, JSON, Integer, ForeignKey, Enum as SQLEnum
from sqlalchemy.orm import DeclarativeBase, relationship
from sqlalchemy.sql import func
import enum

class Base(DeclarativeBase):
    pass

class ActionStatus(str, enum.Enum):
    executed = "executed"
    pending_logic_confirmation = "pending_logic_confirmation"
    rejected = "rejected"
    executed_without_feedback = "executed_without_feedback"


class RiskLevel(str, enum.Enum):
    LOW = "LOW"
    MEDIUM = "MEDIUM"
    HIGH = "HIGH"

class RawEnvironmentalReading(Base):
    __tablename__ = 'raw_environmental_readings'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    timestamp = Column(DateTime, nullable=False, default=func.now(), index=True)
    device_id = Column(String(64), nullable=False)
    batch_id = Column(String(64))
    sensor_type = Column(String(32), nullable=False)
    raw_value = Column(Numeric(10, 4), nullable=False)
    reliability_score = Column(Numeric(5, 4), default=1.0000)
    experiment_group = Column(String(32), default='CONTROL')
    created_at = Column(DateTime, server_default=func.now())
    __table_args__ = (Index('idx_device_time', 'device_id', 'timestamp'),)

class AgriAnalyticalMetric(Base):
    __tablename__ = 'agri_analytical_metrics'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    batch_id = Column(String(64), nullable=False, index=True)
    device_id = Column(String(64), nullable=False)
    strategy_id = Column(String(64))
    record_date = Column(Date, nullable=False)
    par_val_umol = Column(Numeric(10, 2))
    dli_daily_mol = Column(Numeric(10, 2))
    carbon_sink_rate_g_hr = Column(Numeric(10, 4))
    vpd_val_kpa = Column(Numeric(10, 4))
    nutrient_consumption_rate_mg_hr = Column(Numeric(10, 2))
    current_accumulated_gdd_c = Column(Numeric(10, 2))
    lue_score_pct = Column(Numeric(5, 2))
    energy_optimization_index = Column(Numeric(10, 4))
    r_squared_val = Column(Numeric(5, 4))
    completion_rate_pct = Column(Numeric(5, 2))
    data_status = Column(String(32), default='VALID')
    __table_args__ = (
        UniqueConstraint('batch_id', 'device_id', 'record_date', name='uk_batch_device_date'),
        Index('idx_device_date', 'device_id', 'record_date'),
        {'comment': '二级数据分析表 - 农业看板核心指标'}
    )

class DeviceDigitalTwinStatus(Base):
    __tablename__ = 'device_digital_twin_status'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    device_id = Column(String(64), nullable=False, unique=True)
    rated_power_w = Column(Numeric(10, 2), nullable=False)
    runtime_total_hrs = Column(Numeric(12, 2), default=0.00)
    on_off_cycles_count = Column(BigInteger, default=0)
    duty_cycle_ratio_pct = Column(Numeric(5, 2), default=0.00)
    device_thermal_slope = Column(Numeric(10, 4))
    action_latency_ms = Column(BigInteger)
    response_consistency_r2 = Column(Numeric(5, 4))
    failure_probability_pct = Column(Numeric(5, 2), default=0.00)
    last_maintenance_date = Column(DateTime)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

class ESGValueRealization(Base):
    __tablename__ = 'esg_value_realization'
    id = Column(BigInteger, primary_key=True, autoincrement=True)
    batch_id = Column(String(64), nullable=False)
    device_id = Column(String(64), nullable=False)
    record_date = Column(Date, nullable=False)
    biomass_carbon_sequestration_g = Column(Numeric(12, 2), default=0.00)
    operational_carbon_footprint_g = Column(Numeric(12, 2), default=0.00)
    net_zero_ratio = Column(Numeric(10, 4))
    water_saved_liters = Column(Numeric(10, 2), default=0.00)
    energy_efficiency_ratio = Column(Numeric(10, 4))
    cost_reduction_amount_cny = Column(Numeric(10, 2), default=0.00)
    __table_args__ = (UniqueConstraint('batch_id', 'device_id', 'record_date', name='uk_esg_daily'),)

class PolicyRiskThreshold(Base):
    __tablename__ = 'policy_risk_thresholds'
    
    strategy_id = Column(BigInteger, primary_key=True, autoincrement=True)
    metric_name = Column(String(64), nullable=False, comment='指标名称')
    threshold_logic = Column(JSON, nullable=False, comment='JSON格式的复杂逻辑配置')
    priority = Column(Integer, nullable=False, default=1, comment='优先级')
    version = Column(Integer, nullable=False, default=1, comment='乐观锁版本号')
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now(), nullable=False)
    
    __table_args__ = (
        Index('idx_metric_priority', 'metric_name', 'priority'),
        {'comment': '策略风险阈值表'}
    )
    
    def __repr__(self):
        return f"<PolicyRiskThreshold(strategy_id={self.strategy_id}, metric_name={self.metric_name})>"

class AgentActionAudit(Base):
    __tablename__ = 'agent_action_audit'
    
    audit_id = Column(BigInteger, primary_key=True, autoincrement=True)
    actor_id = Column(String(64), nullable=False, comment='操作者ID')
    action_type = Column(String(128), nullable=False, comment='操作类型')
    reasoning_context = Column(Text, nullable=False, comment='操作理由')
    expected_delta = Column(JSON, nullable=True, comment='预期变化')
    actual_delta = Column(JSON, nullable=True, comment='实际变化')
    skill_invoked = Column(String(128), nullable=True, comment='调用的 Skill 接口')
    execution_status = Column(String(32), default='Pending', comment='队列状态')
    is_experience_source = Column(Boolean, default=False, comment='是否被提取为知识')
    
    status = Column(
        SQLEnum(ActionStatus), 
        default=ActionStatus.executed, 
        nullable=False,
        comment='动作状态'
    )
    session_id = Column(String(64), nullable=True, index=True, comment='会话ID')
    action_set_hash = Column(String(128), nullable=True, index=True, comment='操作组合哈希指纹')
    matched_logic_id = Column(BigInteger, ForeignKey('policy_risk_thresholds.strategy_id'), nullable=True)
    user_feedback = Column(JSON, nullable=True, comment='用户反馈详情')
    env_snapshot_ref = Column(JSON, nullable=True, comment='环境快照')
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    matched_logic = relationship("PolicyRiskThreshold", foreign_keys=[matched_logic_id])
    
    __table_args__ = (
        Index('idx_actor_created', 'actor_id', 'created_at'),
        Index('idx_action_type', 'action_type'),
        Index('idx_status', 'status'),
        {'comment': '动作审计表'}
    )
    
    def __repr__(self):
        return f"<AgentActionAudit(audit_id={self.audit_id}, actor_id={self.actor_id})>"

class LogicGraftingLog(Base):
    __tablename__ = 'logic_grafting_logs'
    
    log_id = Column(BigInteger, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True, comment='会话ID')
    feedback_type = Column(String(32), nullable=False, comment='反馈类型')
    selected_logic_id = Column(BigInteger, ForeignKey('policy_risk_thresholds.strategy_id'), nullable=True)
    new_reasoning = Column(Text, nullable=True, comment='新的推理描述')
    confidence_score = Column(Numeric(5, 2), nullable=True, comment='置信度分数')
    created_at = Column(DateTime, server_default=func.now(), nullable=False)
    
    selected_logic = relationship("PolicyRiskThreshold", foreign_keys=[selected_logic_id])
    
    __table_args__ = (
        Index('idx_grafting_session_id', 'session_id'),
        Index('idx_grafting_feedback_type', 'feedback_type'),
        {'comment': '逻辑嫁接日志表'}
    )
    
    def __repr__(self):
        return f"<LogicGraftingLog(log_id={self.log_id}, session_id={self.session_id})>"


# ==================== 系统设置相关表 ====================

class SystemServiceStatus(Base):
    """微服务健康状态表"""
    __tablename__ = 'system_service_status'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    service_name = Column(String(64), nullable=False, unique=True, comment='服务名称')
    service_display = Column(String(64), nullable=False, comment='显示名称')
    port = Column(Integer, nullable=False, comment='服务端口')
    latency_ms = Column(Integer, default=0, comment='延迟（毫秒）')
    status = Column(String(16), default='online', comment='状态: online/offline/warning')
    status_color = Column(String(16), default='#10b981', comment='状态颜色')
    last_sync = Column(String(32), comment='最后同步时间')
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<SystemServiceStatus(service_name={self.service_name}, status={self.status})>"


class SystemUserProfile(Base):
    """系统用户档案表"""
    __tablename__ = 'system_user_profile'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    user_id = Column(String(64), unique=True, default='default_user', comment='用户ID')
    name = Column(String(64), nullable=False, comment='用户姓名')
    role = Column(String(32), nullable=False, comment='角色')
    avatar_letter = Column(String(4), comment='头像字母')
    last_login_time = Column(String(64), comment='上次登录时间')
    last_login_device = Column(String(64), comment='上次登录设备')
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    def __repr__(self):
        return f"<SystemUserProfile(name={self.name}, role={self.role})>"


class OperationLogicRecord(Base):
    """操作逻辑记录表（替代本地OperationLogicStorage）"""
    __tablename__ = 'operation_logic_records'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    logic_id = Column(String(64), unique=True, nullable=False, comment='逻辑记录唯一ID')
    input_text = Column(Text, nullable=False, comment='用户输入内容')
    operation_logic = Column(Text, comment='AI生成的操作逻辑')
    create_time = Column(String(64), comment='创建时间')
    created_at = Column(DateTime, server_default=func.now())

    def __repr__(self):
        return f"<OperationLogicRecord(logic_id={self.logic_id}, input_text={self.input_text[:20]})>"


class ChatMessageRecord(Base):
    """聊天记录表"""
    __tablename__ = 'chat_message_records'

    id = Column(BigInteger, primary_key=True, autoincrement=True)
    message_id = Column(String(64), unique=True, nullable=False, comment='消息唯一ID')
    role = Column(String(16), nullable=False, comment='角色: user/ai/system')
    content = Column(Text, nullable=False, comment='消息内容')
    session_id = Column(String(64), nullable=True, index=True, comment='会话ID')
    feedback = Column(String(16), nullable=True, comment='用户反馈: positive/negative')
    chat_mode = Column(String(16), nullable=True, comment='聊天模式: expert农艺/device设备')
    created_at = Column(DateTime, server_default=func.now(), nullable=False)

    def __repr__(self):
        return f"<ChatMessageRecord(message_id={self.message_id}, role={self.role}, content={self.content[:30]})>"
