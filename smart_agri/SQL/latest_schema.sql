-- ============================================================================
-- 智慧农业 AI 网关系统 - PostgreSQL 完整 DDL 脚本
-- 生成日期: 2026-04-15
-- 数据库: agri_ai
-- 说明: 本脚本可重复执行，包含 DROP TABLE IF EXISTS CASCADE
-- 严禁: 本文件不包含任何 INSERT 语句或敏感业务数据
-- ============================================================================

-- ============================================================================
-- 0. 清理（按依赖逆序删除）
-- ============================================================================

DROP TABLE IF EXISTS logic_grafting_logs CASCADE;
DROP TABLE IF EXISTS agent_action_audit CASCADE;
DROP TABLE IF EXISTS policy_risk_thresholds CASCADE;
DROP TABLE IF EXISTS esg_value_realization CASCADE;
DROP TABLE IF EXISTS device_digital_twin_status CASCADE;
DROP TABLE IF EXISTS agri_analytical_metrics CASCADE;
DROP TABLE IF EXISTS raw_environmental_readings CASCADE;
DROP TYPE IF EXISTS actionstatus CASCADE;

-- ============================================================================
-- 1. 枚举类型定义
-- ============================================================================

CREATE TYPE actionstatus AS ENUM (
    'executed',
    'pending_logic_confirmation',
    'rejected',
    'executed_without_feedback'
);

-- ============================================================================
-- 2. 原始环境热数据表 (L1)
-- ============================================================================

CREATE TABLE raw_environmental_readings (
    id                  BIGSERIAL       PRIMARY KEY,
    timestamp           TIMESTAMP       NOT NULL DEFAULT NOW(),
    device_id           VARCHAR(64)     NOT NULL,
    batch_id            VARCHAR(64),
    sensor_type         VARCHAR(32)     NOT NULL,
    raw_value           NUMERIC(10,4)   NOT NULL,
    reliability_score   NUMERIC(5,4)    DEFAULT 1.0000,
    experiment_group    VARCHAR(32)     DEFAULT 'CONTROL',
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_device_time ON raw_environmental_readings(device_id, timestamp);
CREATE INDEX idx_raw_timestamp ON raw_environmental_readings(timestamp);

-- ============================================================================
-- 3. 二级数据分析表 (L2)
-- ============================================================================

CREATE TABLE agri_analytical_metrics (
    id                                  BIGSERIAL       PRIMARY KEY,
    batch_id                            VARCHAR(64)     NOT NULL,
    device_id                           VARCHAR(64)     NOT NULL,
    strategy_id                         VARCHAR(64),
    record_date                         DATE            NOT NULL,
    par_val_umol                        NUMERIC(10,2),
    dli_daily_mol                       NUMERIC(10,2),
    carbon_sink_rate_g_hr               NUMERIC(10,4),
    vpd_val_kpa                         NUMERIC(10,4),
    nutrient_consumption_rate_mg_hr     NUMERIC(10,2),
    current_accumulated_gdd_c           NUMERIC(10,2),
    lue_score_pct                       NUMERIC(5,2),
    energy_optimization_index           NUMERIC(10,4),
    r_squared_val                       NUMERIC(5,4),
    completion_rate_pct                 NUMERIC(5,2),
    data_status                         VARCHAR(32)     DEFAULT 'VALID',
    CONSTRAINT uk_batch_device_date UNIQUE (batch_id, device_id, record_date)
);

CREATE INDEX idx_device_date ON agri_analytical_metrics(device_id, record_date);
CREATE INDEX idx_batch_id ON agri_analytical_metrics(batch_id);

-- ============================================================================
-- 4. 设备数字孪生表 (L3)
-- ============================================================================

CREATE TABLE device_digital_twin_status (
    id                          BIGSERIAL       PRIMARY KEY,
    device_id                   VARCHAR(64)     NOT NULL UNIQUE,
    rated_power_w               NUMERIC(10,2)   NOT NULL,
    runtime_total_hrs           NUMERIC(12,2)   DEFAULT 0.00,
    on_off_cycles_count         BIGINT          DEFAULT 0,
    duty_cycle_ratio_pct        NUMERIC(5,2)    DEFAULT 0.00,
    device_thermal_slope        NUMERIC(10,4),
    action_latency_ms           BIGINT,
    response_consistency_r2     NUMERIC(5,4),
    failure_probability_pct     NUMERIC(5,2)    DEFAULT 0.00,
    last_maintenance_date       TIMESTAMP,
    updated_at                  TIMESTAMP       NOT NULL DEFAULT NOW()
);

-- ============================================================================
-- 5. ESG 价值核算表 (L4)
-- ============================================================================

CREATE TABLE esg_value_realization (
    id                                  BIGSERIAL       PRIMARY KEY,
    batch_id                            VARCHAR(64)     NOT NULL,
    device_id                           VARCHAR(64)     NOT NULL,
    record_date                         DATE            NOT NULL,
    biomass_carbon_sequestration_g      NUMERIC(12,2)   DEFAULT 0.00,
    operational_carbon_footprint_g      NUMERIC(12,2)   DEFAULT 0.00,
    net_zero_ratio                      NUMERIC(10,4),
    water_saved_liters                  NUMERIC(10,2)   DEFAULT 0.00,
    energy_efficiency_ratio             NUMERIC(10,4),
    cost_reduction_amount_cny           NUMERIC(10,2)   DEFAULT 0.00,
    CONSTRAINT uk_esg_daily UNIQUE (batch_id, device_id, record_date)
);

-- ============================================================================
-- 6. 策略风险阈值表 (策略层)
-- ============================================================================

CREATE TABLE policy_risk_thresholds (
    strategy_id         BIGSERIAL       PRIMARY KEY,
    metric_name         VARCHAR(64)     NOT NULL,
    threshold_logic     JSONB           NOT NULL,
    priority            INTEGER         NOT NULL DEFAULT 1,
    version             INTEGER         NOT NULL DEFAULT 1,
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW(),
    updated_at          TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_metric_priority ON policy_risk_thresholds(metric_name, priority);

-- ============================================================================
-- 7. 动作审计表 (审计层)
-- ============================================================================

CREATE TABLE agent_action_audit (
    audit_id                BIGSERIAL       PRIMARY KEY,
    actor_id                VARCHAR(64)     NOT NULL,
    action_type             VARCHAR(128)    NOT NULL,
    reasoning_context       TEXT            NOT NULL,
    expected_delta          JSONB,
    actual_delta            JSONB,
    skill_invoked           VARCHAR(128),
    execution_status        VARCHAR(32)     DEFAULT 'Pending',
    is_experience_source    BOOLEAN         DEFAULT FALSE,
    status                  actionstatus    NOT NULL DEFAULT 'executed',
    session_id              VARCHAR(64),
    action_set_hash         VARCHAR(128),
    matched_logic_id        BIGINT          REFERENCES policy_risk_thresholds(strategy_id),
    user_feedback           JSONB,
    env_snapshot_ref        JSONB,
    created_at              TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_actor_created ON agent_action_audit(actor_id, created_at);
CREATE INDEX idx_action_type ON agent_action_audit(action_type);
CREATE INDEX idx_experience_source ON agent_action_audit(is_experience_source);
CREATE INDEX idx_status ON agent_action_audit(status);
CREATE INDEX idx_session_id ON agent_action_audit(session_id);
CREATE INDEX idx_action_set_hash ON agent_action_audit(action_set_hash);
CREATE INDEX idx_matched_logic_id ON agent_action_audit(matched_logic_id);

-- ============================================================================
-- 8. 逻辑嫁接日志表 (日志层)
-- ============================================================================

CREATE TABLE logic_grafting_logs (
    log_id              BIGSERIAL       PRIMARY KEY,
    session_id          VARCHAR(64)     NOT NULL,
    feedback_type       VARCHAR(32)     NOT NULL,
    selected_logic_id   BIGINT          REFERENCES policy_risk_thresholds(strategy_id),
    new_reasoning       TEXT,
    confidence_score    NUMERIC(5,2),
    created_at          TIMESTAMP       NOT NULL DEFAULT NOW()
);

CREATE INDEX idx_grafting_session_id ON logic_grafting_logs(session_id);
CREATE INDEX idx_grafting_feedback_type ON logic_grafting_logs(feedback_type);
CREATE INDEX idx_grafting_created_at ON logic_grafting_logs(created_at);
CREATE INDEX idx_grafting_selected_logic ON logic_grafting_logs(selected_logic_id);

-- ============================================================================
-- DDL 脚本结束
-- ============================================================================

-- ==================== 系统设置相关表 ====================

CREATE TABLE IF NOT EXISTS system_service_status (
    id BIGSERIAL PRIMARY KEY,
    service_name VARCHAR(64) NOT NULL UNIQUE,
    service_display VARCHAR(64) NOT NULL,
    port INTEGER NOT NULL,
    latency_ms INTEGER DEFAULT 0,
    status VARCHAR(16) DEFAULT 'online',
    status_color VARCHAR(16) DEFAULT '#10b981',
    last_sync VARCHAR(32),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS system_user_profile (
    id BIGSERIAL PRIMARY KEY,
    user_id VARCHAR(64) UNIQUE DEFAULT 'default_user',
    name VARCHAR(64) NOT NULL,
    role VARCHAR(32) NOT NULL,
    avatar_letter VARCHAR(4),
    last_login_time VARCHAR(64),
    last_login_device VARCHAR(64),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS operation_logic_records (
    id BIGSERIAL PRIMARY KEY,
    logic_id VARCHAR(64) UNIQUE NOT NULL,
    input_text TEXT NOT NULL,
    operation_logic TEXT,
    create_time VARCHAR(64),
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE TABLE IF NOT EXISTS chat_message_records (
    id BIGSERIAL PRIMARY KEY,
    message_id VARCHAR(64) UNIQUE NOT NULL,
    role VARCHAR(16) NOT NULL,
    content TEXT NOT NULL,
    session_id VARCHAR(64),
    feedback VARCHAR(16),
    chat_mode VARCHAR(16),
    created_at TIMESTAMP DEFAULT NOW() NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_chat_session_id ON chat_message_records(session_id);
