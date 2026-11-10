# 智慧农业 AI 网关系统 - 数据库业务字典

## 文档信息

| 项目名称 | 智慧农业 AI 网关系统 (AIDemo) |
|---------|------------------------------|
| 数据库 | PostgreSQL 15+ / agri_ai |
| 文档版本 | V1.0 |
| 生成日期 | 2026-04-15 |
| DDL 文件 | `latest_schema.sql` |

---

## 1. 概述

### 1.1 数据库连接

| 参数 | 值 |
|------|-----|
| Host | localhost |
| Port | 5432 |
| Database | agri_ai |
| User | postgres |
| Async Driver | asyncpg |
| Sync Driver | psycopg2 |

### 1.2 表清单

| # | 表名 | 数据层次 | 说明 |
|---|------|---------|------|
| 1 | `raw_environmental_readings` | L1 | 原始环境热数据 |
| 2 | `agri_analytical_metrics` | L2 | 二级数据分析指标 |
| 3 | `device_digital_twin_status` | L3 | 设备数字孪生状态 |
| 4 | `esg_value_realization` | L4 | ESG 价值核算 |
| 5 | `policy_risk_thresholds` | 策略层 | 策略风险阈值 |
| 6 | `agent_action_audit` | 审计层 | 动作审计记录 |
| 7 | `logic_grafting_logs` | 日志层 | 逻辑嫁接日志 |

### 1.3 单位命名规范

| 后缀 | 物理单位 | 中文 |
|------|---------|------|
| `_c` | ℃ | 摄氏度 |
| `_pct` | % | 百分比 |
| `_kpa` | kPa | 千帕 |
| `_umol` | μmol/(m²·s) | 微摩尔每平方米每秒 |
| `_mol` | mol/(m²·d) | 摩尔每平方米每天 |
| `_g` | g | 克 |
| `_g_hr` | g/hr | 克每小时 |
| `_mg_hr` | mg/hr | 毫克每小时 |
| `_l` | L | 升 |
| `_ms` | ms | 毫秒 |
| `_hrs` | h | 小时 |
| `_w` | W | 瓦特 |
| `_cny` | CNY | 人民币 |

---

## 2. 表字段业务字典

### 2.1 raw_environmental_readings (原始环境热数据表)

> L1 层传感器原始数据，高频写入

| 字段名 | 数据类型 | 可空 | 默认值 | 中文业务含义 | 单位 |
|--------|---------|------|--------|-------------|------|
| `id` | BIGSERIAL | NO | AUTO | 主键 ID | - |
| `timestamp` | TIMESTAMP | NO | NOW() | 采样时间戳 | - |
| `device_id` | VARCHAR(64) | NO | - | 传感器设备唯一标识 | - |
| `batch_id` | VARCHAR(64) | YES | - | 数据批次 ID，用于批量追溯 | - |
| `sensor_type` | VARCHAR(32) | NO | - | 传感器类型：air_temp/air_humidity/light_lux/soil_moisture/co2_ppm/soil_npk | - |
| `raw_value` | NUMERIC(10,4) | NO | - | 原始采样值 | 依 sensor_type 而定 |
| `reliability_score` | NUMERIC(5,4) | YES | 1.0000 | 数据可靠性评分 (0~1)，1.0=完全可信 | - |
| `experiment_group` | VARCHAR(32) | YES | 'CONTROL' | 实验分组：CONTROL/EXPERIMENTAL | - |
| `created_at` | TIMESTAMP | NO | NOW() | 记录创建时间 | - |

**索引：**

| 索引名 | 字段 | 类型 |
|--------|------|------|
| `idx_device_time` | (device_id, timestamp) | 复合索引 |
| `idx_raw_timestamp` | (timestamp) | 单列索引 |

---

### 2.2 agri_analytical_metrics (二级数据分析表)

> L2 层分析指标数据，农业看板核心数据源

| 字段名 | 数据类型 | 可空 | 默认值 | 中文业务含义 | 单位 |
|--------|---------|------|--------|-------------|------|
| `id` | BIGSERIAL | NO | AUTO | 主键 ID | - |
| `batch_id` | VARCHAR(64) | NO | - | 数据批次 ID | - |
| `device_id` | VARCHAR(64) | NO | - | 设备 ID | - |
| `strategy_id` | VARCHAR(64) | YES | - | 关联的策略 ID | - |
| `record_date` | DATE | NO | - | 记录日期 | - |
| `par_val_umol` | NUMERIC(10,2) | YES | - | 瞬时光合有效辐射 | μmol/(m²·s) |
| `dli_daily_mol` | NUMERIC(10,2) | YES | - | 日光积分 | mol/(m²·d) |
| `carbon_sink_rate_g_hr` | NUMERIC(10,4) | YES | - | 光合碳汇速率 | g/hr |
| `vpd_val_kpa` | NUMERIC(10,4) | YES | - | 蒸气压亏缺 | kPa |
| `nutrient_consumption_rate_mg_hr` | NUMERIC(10,2) | YES | - | 土壤养分消耗率 | mg/hr |
| `current_accumulated_gdd_c` | NUMERIC(10,2) | YES | - | 当前累计有效积温 | ℃·d |
| `lue_score_pct` | NUMERIC(5,2) | YES | - | 光利用率评分 | % |
| `energy_optimization_index` | NUMERIC(10,4) | YES | - | 能耗优化指数 (delta/kJ) | - |
| `r_squared_val` | NUMERIC(5,4) | YES | - | R² 拟合度 (设备指纹) | - |
| `completion_rate_pct` | NUMERIC(5,2) | YES | - | 目标完成率 | % |
| `data_status` | VARCHAR(32) | YES | 'VALID' | 数据状态：VALID/INVALID/PENDING | - |

**约束：**

| 约束名 | 字段 | 类型 |
|--------|------|------|
| `uk_batch_device_date` | (batch_id, device_id, record_date) | 唯一约束 |

**索引：**

| 索引名 | 字段 | 类型 |
|--------|------|------|
| `idx_device_date` | (device_id, record_date) | 复合索引 |
| `idx_batch_id` | (batch_id) | 单列索引 |

---

### 2.3 device_digital_twin_status (设备数字孪生表)

> L3 层设备状态和健康诊断数据

| 字段名 | 数据类型 | 可空 | 默认值 | 中文业务含义 | 单位 |
|--------|---------|------|--------|-------------|------|
| `id` | BIGSERIAL | NO | AUTO | 主键 ID | - |
| `device_id` | VARCHAR(64) | NO | UNIQUE | 设备唯一标识 | - |
| `rated_power_w` | NUMERIC(10,2) | NO | - | 额定功率 | W |
| `runtime_total_hrs` | NUMERIC(12,2) | YES | 0.00 | 累计运行时间 | h |
| `on_off_cycles_count` | BIGINT | YES | 0 | 启停次数 | 次 |
| `duty_cycle_ratio_pct` | NUMERIC(5,2) | YES | 0.00 | 占空比 | % |
| `device_thermal_slope` | NUMERIC(10,4) | YES | - | 热力响应斜率 (故障预测) | - |
| `action_latency_ms` | BIGINT | YES | - | 指令响应延迟 | ms |
| `response_consistency_r2` | NUMERIC(5,4) | YES | - | 响应一致性 R² | - |
| `failure_probability_pct` | NUMERIC(5,2) | YES | 0.00 | 故障概率 | % |
| `last_maintenance_date` | TIMESTAMP | YES | - | 上次维护日期 | - |
| `updated_at` | TIMESTAMP | NO | NOW() | 更新时间 | - |

---

### 2.4 esg_value_realization (ESG 价值核算表)

> L4 层 ESG 价值实现数据

| 字段名 | 数据类型 | 可空 | 默认值 | 中文业务含义 | 单位 |
|--------|---------|------|--------|-------------|------|
| `id` | BIGSERIAL | NO | AUTO | 主键 ID | - |
| `batch_id` | VARCHAR(64) | NO | - | 数据批次 ID | - |
| `device_id` | VARCHAR(64) | NO | - | 设备 ID | - |
| `record_date` | DATE | NO | - | 记录日期 | - |
| `biomass_carbon_sequestration_g` | NUMERIC(12,2) | YES | 0.00 | 生物质固碳量 | g |
| `operational_carbon_footprint_g` | NUMERIC(12,2) | YES | 0.00 | 运营碳足迹 | g |
| `net_zero_ratio` | NUMERIC(10,4) | YES | - | 碳平衡率 (>1 碳负排放, =1 碳中和, <1 碳正排放) | - |
| `water_saved_liters` | NUMERIC(10,2) | YES | 0.00 | 节水量 | L |
| `energy_efficiency_ratio` | NUMERIC(10,4) | YES | - | 能效比 (AI控制较传统控制的节省比例) | - |
| `cost_reduction_amount_cny` | NUMERIC(10,2) | YES | 0.00 | 成本节省金额 | CNY |

**约束：**

| 约束名 | 字段 | 类型 |
|--------|------|------|
| `uk_esg_daily` | (batch_id, device_id, record_date) | 唯一约束 |

---

### 2.5 policy_risk_thresholds (策略风险阈值表)

> 存储动态调整的控制策略阈值，支持行级锁和乐观锁

| 字段名 | 数据类型 | 可空 | 默认值 | 中文业务含义 | 单位 |
|--------|---------|------|--------|-------------|------|
| `strategy_id` | BIGSERIAL | NO | AUTO | 策略主键 ID | - |
| `metric_name` | VARCHAR(64) | NO | - | 指标名称，如 soil_water_avg_pct, air_temp_min_safety | - |
| `threshold_logic` | JSONB | NO | - | JSON 格式的复杂逻辑配置 (见 §3.1) | - |
| `priority` | INTEGER | NO | 1 | 优先级，数值越大优先级越高 | - |
| `version` | INTEGER | NO | 1 | 乐观锁版本号，每次更新自动递增 | - |
| `created_at` | TIMESTAMP | NO | NOW() | 创建时间 | - |
| `updated_at` | TIMESTAMP | NO | NOW() | 更新时间 | - |

**索引：**

| 索引名 | 字段 | 类型 |
|--------|------|------|
| `idx_metric_priority` | (metric_name, priority) | 复合索引 |

---

### 2.6 agent_action_audit (动作审计表)

> 记录所有人工和智能体的操作干预，支持 HITL 工作流

| 字段名 | 数据类型 | 可空 | 默认值 | 中文业务含义 | 单位 |
|--------|---------|------|--------|-------------|------|
| `audit_id` | BIGSERIAL | NO | AUTO | 审计主键 ID | - |
| `actor_id` | VARCHAR(64) | NO | - | 操作者 ID，区分 Human/Agent | - |
| `action_type` | VARCHAR(128) | NO | - | 操作类型，如 MANUAL_IRRIGATION, THRESHOLD_OVERRIDE | - |
| `reasoning_context` | TEXT | NO | - | 操作理由，必填，记录农民的经验描述 | - |
| `expected_delta` | JSONB | YES | - | 预期变化，JSON 格式 (见 §3.2) | - |
| `actual_delta` | JSONB | YES | - | 实际变化，JSON 格式 (见 §3.2) | - |
| `skill_invoked` | VARCHAR(128) | YES | - | 调用的 Skill 接口名称 | - |
| `execution_status` | VARCHAR(32) | YES | 'Pending' | 队列状态：Pending/Success/Failed | - |
| `is_experience_source` | BOOLEAN | YES | FALSE | 标记该记录是否被提取为知识 | - |
| `status` | actionstatus | NO | 'executed' | 动作状态 (见 §4.1) | - |
| `session_id` | VARCHAR(64) | YES | - | 会话 ID，用于事务中断和断点续传 | - |
| `action_set_hash` | VARCHAR(128) | YES | - | 操作组合的哈希指纹 (十六进制) | - |
| `matched_logic_id` | BIGINT | YES | - | 匹配的 RAG 规则 ID (FK → policy_risk_thresholds.strategy_id) | - |
| `user_feedback` | JSONB | YES | - | 用户反馈详情 (见 §3.3) | - |
| `env_snapshot_ref` | JSONB | YES | - | 执行动作时的关键传感器瞬时值快照 (见 §3.4) | - |
| `created_at` | TIMESTAMP | NO | NOW() | 创建时间 | - |

**外键：**

| 字段 | 引用 |
|------|------|
| `matched_logic_id` | `policy_risk_thresholds.strategy_id` |

**索引：**

| 索引名 | 字段 | 类型 |
|--------|------|------|
| `idx_actor_created` | (actor_id, created_at) | 复合索引 |
| `idx_action_type` | (action_type) | 单列索引 |
| `idx_experience_source` | (is_experience_source) | 单列索引 |
| `idx_status` | (status) | 单列索引 |
| `idx_session_id` | (session_id) | 单列索引 |
| `idx_action_set_hash` | (action_set_hash) | 单列索引 |
| `idx_matched_logic_id` | (matched_logic_id) | 单列索引 |

---

### 2.7 logic_grafting_logs (逻辑嫁接日志表)

> 记录用户反馈行为和经验提取过程

| 字段名 | 数据类型 | 可空 | 默认值 | 中文业务含义 | 单位 |
|--------|---------|------|--------|-------------|------|
| `log_id` | BIGSERIAL | NO | AUTO | 日志主键 ID | - |
| `session_id` | VARCHAR(64) | NO | - | 会话 ID，关联审计记录 | - |
| `feedback_type` | VARCHAR(32) | NO | - | 反馈类型：confirm_logic/adjust_logic/new_logic | - |
| `selected_logic_id` | BIGINT | YES | - | 用户选择的逻辑 ID (FK → policy_risk_thresholds.strategy_id) | - |
| `new_reasoning` | TEXT | YES | - | 用户提供的新的推理描述 | - |
| `confidence_score` | NUMERIC(5,2) | YES | - | 用户确认逻辑时的坚决程度 (0~100)，用于 RLHF | - |
| `created_at` | TIMESTAMP | NO | NOW() | 创建时间 | - |

**外键：**

| 字段 | 引用 |
|------|------|
| `selected_logic_id` | `policy_risk_thresholds.strategy_id` |

**索引：**

| 索引名 | 字段 | 类型 |
|--------|------|------|
| `idx_grafting_session_id` | (session_id) | 单列索引 |
| `idx_grafting_feedback_type` | (feedback_type) | 单列索引 |
| `idx_grafting_created_at` | (created_at) | 单列索引 |
| `idx_grafting_selected_logic` | (selected_logic_id) | 单列索引 |

---

## 3. JSONB 字段规格说明

### 3.1 threshold_logic (policy_risk_thresholds)

> 策略风险阈值的复杂逻辑配置

```json
{
    "condition": "weather_forecast == 'rain'",
    "action": "increase_threshold",
    "value": 5.0,
    "unit": "pct",
    "reasoning": "雨天需增加灌溉阈值防止积水",
    "risk_level": "MEDIUM",
    "target_device": "灌溉系统",
    "auto_execute": true,
    "async_review": true,
    "duration_minutes": 15
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `condition` | string | YES | 触发条件表达式 |
| `action` | string | YES | 执行动作标识 |
| `value` | number | YES | 阈值调整数值 |
| `unit` | string | YES | 数值单位 |
| `reasoning` | string | NO | 决策理由 |
| `risk_level` | string | NO | 风险等级：LOW/MEDIUM/HIGH |
| `target_device` | string | NO | 目标设备名称 |
| `auto_execute` | boolean | NO | 是否自动执行 |
| `async_review` | boolean | NO | 是否异步审查 |
| `duration_minutes` | number | NO | 持续时间 (分钟) |

### 3.2 expected_delta / actual_delta (agent_action_audit)

> 操作的预期变化和实际变化

```json
{
    "temperature": -3.0,
    "humidity": -5.0,
    "soil_moisture": 8.0,
    "co2_ppm": -120.0,
    "light_lux": 0
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `temperature` | number | NO | 温度变化量 (℃) |
| `humidity` | number | NO | 湿度变化量 (%) |
| `soil_moisture` | number | NO | 土壤湿度变化量 (%) |
| `co2_ppm` | number | NO | CO2 浓度变化量 (ppm) |
| `light_lux` | number | NO | 光照变化量 (lux) |

### 3.3 user_feedback (agent_action_audit)

> 用户反馈详情

```json
{
    "feedback_type": "confirm_logic",
    "selected_logic_id": 1,
    "confidence": 95,
    "adjustments": null
}
```

**确认逻辑 (confirm_logic)：**

```json
{
    "feedback_type": "confirm_logic",
    "selected_logic_id": 1,
    "confidence": 95
}
```

**调整逻辑 (adjust_logic)：**

```json
{
    "feedback_type": "adjust_logic",
    "selected_logic_id": 2,
    "confidence": 70,
    "adjustments": {
        "threshold_value": 28.0,
        "duration_minutes": 20
    }
}
```

**新建逻辑 (new_logic)：**

```json
{
    "feedback_type": "new_logic",
    "confidence": 80,
    "new_reasoning": "夏季高温时需要更频繁的通风"
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `feedback_type` | string | YES | 反馈类型：confirm_logic/adjust_logic/new_logic |
| `selected_logic_id` | number | NO | 选择的逻辑 ID (confirm/adjust 时必填) |
| `confidence` | number | NO | 确认坚决程度 (0~100) |
| `adjustments` | object | NO | 调整参数 (adjust_logic 时必填) |
| `new_reasoning` | string | NO | 新推理描述 (new_logic 时必填) |

### 3.4 env_snapshot_ref (agent_action_audit)

> 执行动作时的关键传感器瞬时值快照，用于知识蒸馏

```json
{
    "temperature": 30.5,
    "humidity": 75.0,
    "light_intensity": 45000.0,
    "soil_moisture": 35.0,
    "weather": "晴转多云",
    "co2_ppm": 520.0,
    "custom_params": {
        "wind_speed": 2.5,
        "rain_probability": 0.3
    }
}
```

| 字段 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `temperature` | number | NO | 温度 (℃) |
| `humidity` | number | NO | 湿度 (%) |
| `light_intensity` | number | NO | 光照强度 (lux) |
| `soil_moisture` | number | NO | 土壤湿度 (%) |
| `weather` | string | NO | 天气状况 |
| `co2_ppm` | number | NO | CO2 浓度 (ppm) |
| `custom_params` | object | NO | 自定义环境参数 |

---

## 4. 枚举类型说明

### 4.1 actionstatus

```sql
CREATE TYPE actionstatus AS ENUM (
    'executed',
    'pending_logic_confirmation',
    'rejected',
    'executed_without_feedback'
);
```

| 值 | 中文 | 说明 |
|----|------|------|
| `executed` | 已执行 | 正常完成状态 |
| `pending_logic_confirmation` | 待逻辑确认 | 等待用户确认或调整 (HIGH 风险操作挂起) |
| `rejected` | 已拒绝 | 用户拒绝执行 |
| `executed_without_feedback` | 已执行无反馈 | 执行后未收到用户反馈 (超时自动转换) |

**状态转换路径：**

```
pending_logic_confirmation → executed (用户确认)
pending_logic_confirmation → rejected (用户拒绝)
pending_logic_confirmation → executed_without_feedback (超时)
executed → executed_without_feedback (2小时无反馈)
```

---

## 5. 开发注意事项 (代码一致性检查)

### 5.1 SQLAlchemy JSON vs PostgreSQL JSONB

| 位置 | models.py 定义 | DDL 实际类型 | 建议 |
|------|---------------|-------------|------|
| `policy_risk_thresholds.threshold_logic` | `Column(JSON)` | `JSONB` | **已修正**：DDL 中使用 JSONB，models.py 建议同步修改为 `Column(JSONB)` |
| `agent_action_audit.expected_delta` | `Column(JSON)` | `JSONB` | **已修正**：同上 |
| `agent_action_audit.actual_delta` | `Column(JSON)` | `JSONB` | **已修正**：同上 |
| `agent_action_audit.user_feedback` | `Column(JSON)` | `JSONB` | **已修正**：同上 |
| `agent_action_audit.env_snapshot_ref` | `Column(JSON)` | `JSONB` | **已修正**：同上 |

**修复建议：** 在 `models.py` 中将 `JSON` 替换为 `JSONB`：

```python
# 修改前
from sqlalchemy import ..., JSON, ...
threshold_logic = Column(JSON, nullable=False)

# 修改后
from sqlalchemy.dialects.postgresql import JSONB
threshold_logic = Column(JSONB, nullable=False)
```

### 5.2 Numeric 精度一致性

| 位置 | models.py | DDL | 一致性 |
|------|-----------|-----|--------|
| `raw_value` | Numeric(10,4) | NUMERIC(10,4) | ✅ 一致 |
| `reliability_score` | Numeric(5,4) | NUMERIC(5,4) | ✅ 一致 |
| `par_val_umol` | Numeric(10,2) | NUMERIC(10,2) | ✅ 一致 |
| `rated_power_w` | Numeric(10,2) | NUMERIC(10,2) | ✅ 一致 |

### 5.3 Enum 类型处理

| 位置 | models.py | DDL | 说明 |
|------|-----------|-----|------|
| `agent_action_audit.status` | `SQLEnum(ActionStatus)` | `actionstatus` | SQLAlchemy 默认创建原生 ENUM TYPE，与 DDL 一致 ✅ |

### 5.4 String 长度一致性

| 位置 | models.py | DDL | 一致性 |
|------|-----------|-----|--------|
| `device_id` | String(64) | VARCHAR(64) | ✅ 一致 |
| `sensor_type` | String(32) | VARCHAR(32) | ✅ 一致 |
| `metric_name` | String(64) | VARCHAR(64) | ✅ 一致 |
| `action_type` | String(128) | VARCHAR(128) | ✅ 一致 |

### 5.5 缺失索引提醒

| 位置 | 说明 |
|------|------|
| `raw_environmental_readings.timestamp` | models.py 中 `index=True` 已定义单列索引，DDL 中已补充 `idx_raw_timestamp` |
| `agri_analytical_metrics.batch_id` | models.py 中 `index=True` 已定义，DDL 中已创建 `idx_batch_id` |

---

## 6. 外键关系图

```
policy_risk_thresholds
    │  strategy_id (PK)
    │
    ├──< agent_action_audit.matched_logic_id (FK)
    │
    └──< logic_grafting_logs.selected_logic_id (FK)
```
