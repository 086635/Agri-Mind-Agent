# 🌾 智慧农业 AI 网关系统

<div align="center">

[![Python](https://img.shields.io/badge/Python-3.10%2B-blue?logo=python&logoColor=white)](https://www.python.org/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.109.0-009688?logo=fastapi&logoColor=white)](https://fastapi.tiangolo.com/)
[![LangGraph](https://img.shields.io/badge/LangGraph-0.0.28-FF6B6B?logo=langchain&logoColor=white)](https://github.com/langchain-ai/langgraph)
[![PostgreSQL](https://img.shields.io/badge/PostgreSQL-15%2B-336791?logo=postgresql&logoColor=white)](https://www.postgresql.org/)
[![License](https://img.shields.io/badge/License-MIT-green.svg)](LICENSE)

**基于 LangGraph 的 Human-in-the-Loop 经验学习引擎**

[快速开始](#-快速开始) · [架构设计](#-架构设计) · [API 文档](#-api-文档) · [部署指南](#-部署指南)

</div>

---

## 📋 目录

- [项目概述](#-项目概述)
- [核心特性](#-核心特性)
- [技术架构](#-技术架构)
- [快速开始](#-快速开始)
- [环境配置](#-环境配置)
- [核心模块](#-核心模块)
- [API 文档](#-api-文档)
- [数据库设计](#-数据库设计)
- [部署指南](#-部署指南)
- [安全策略](#-安全策略)
- [开发指南](#-开发指南)

---

## 🌟 项目概述

本项目是一个**智慧农业 AI 网关系统**，实现了完整的 **Human-in-the-Loop (HITL)** 经验学习引擎。系统通过 LangGraph 构建工作流拓扑，遵循"感知 → 决策 → 冲突检测 → 人工干预 → 逻辑闭环"的架构规范，能够将农户的口语化操作经验转化为可复用的结构化规则。

### 核心价值

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        HITL 经验学习闭环                                 │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                         │
│   农户操作 ──> 意图识别 ──> 风险评估 ──> 执行/挂起 ──> 用户反馈          │
│       │                                                      │          │
│       │                                                      ▼          │
│       │            ┌──────────────────────────────────────────┐        │
│       │            │           置信度演进引擎                  │        │
│       │            │  ┌─────────────────────────────────────┐ │        │
│       │            │  │ 显式确认: +1.0                      │ │        │
│       │            │  │ 隐式确认: +0.2 (2小时无反悔)        │ │        │
│       │            │  │ 纠正反馈: 旧-0.5, 新继承50%         │ │        │
│       │            │  │ 时间衰减: e^(-λt)                   │ │        │
│       │            │  └─────────────────────────────────────┘ │        │
│       │            └──────────────────────────────────────────┘        │
│       │                              │                                  │
│       └──────────────────────────────┴──────────> 知识库迭代升级        │
│                                                                         │
└─────────────────────────────────────────────────────────────────────────┘
```

---

## ✨ 核心特性

### 1. 意图指纹引擎 (ActionChunker)

- **环境参数 Bucketing**：温度 2°C 一档、湿度 10% 一档，提高指纹鲁棒性
- **时间窗口聚合**：15-30 分钟窗口内的操作自动聚合
- **相似度去重**：0.95+ 相似度自动去重，0.3-0.7 需用户确认

### 2. 风险分级机制 (RiskAssessor)

| 风险等级 | 操作类型 | 执行策略 |
|---------|---------|---------|
| **LOW** | 补光灯开关、风扇开关 | 直接执行，异步审查 |
| **MEDIUM** | 灌溉操作、通风窗调节 | 执行后审查，记录日志 |
| **HIGH** | 大面积施肥、农药喷洒 | 挂起等待确认，设备锁定 |

### 3. Redis 持久化会话

- **服务重启恢复**：挂起会话存储在 Redis，30 分钟 TTL
- **幂等性保证**：session_id 由 audit_id 派生
- **连接池管理**：异步 Redis 连接池，支持高并发

### 4. 动态置信度演进

```python
# 置信度演进算法
Final_Score = Sum(Weights) × e^(-λt)

# 权重变化规则
显式确认: confidence += 1.0
隐式确认: confidence += 0.2  # 2小时无反悔
纠正反馈: old_confidence -= 0.5, new_confidence = old × 0.5
```

### 5. RAG 版本控制

- **Soft Delete**：旧规则标记 `is_active=False`
- **版本链追溯**：通过 `parent_id` 构建完整版本树
- **演进原因记录**：记录每次版本变化的原因

---

## 🏗️ 技术架构

### 系统架构图

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                              智慧农业 AI 网关                                │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         API 层 (FastAPI)                              │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │  │
│  │  │ /chat       │  │ /telemetry  │  │ /experience │  │ /logic      │  │  │
│  │  │ 对话接口    │  │ 遥测数据    │  │ 经验反馈    │  │ 规则管理    │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                     LangGraph 工作流引擎                              │  │
│  │                                                                       │  │
│  │  START ──> intent_quantizer ──> conflict_checker ──> logic_upsert    │  │
│  │                                    │                                  │  │
│  │                                    ▼                                  │  │
│  │                              knowledge_refiner                        │  │
│  │                                    │                                  │  │
│  │                                    ▼                                  │  │
│  │                                   END                                 │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                          服务层 (Services)                            │  │
│  │                                                                       │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │  │
│  │  │ActionChunker│  │RiskAssessor │  │ConfidenceMgr│  │RedisSession │  │  │
│  │  │意图指纹     │  │风险评估     │  │置信度管理   │  │会话存储     │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │  │
│  │                                                                       │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │  │
│  │  │Explainability│ │PendingSession│ │DistributedLock│ │TransactionMgr│  │
│  │  │对比分析     │  │挂起会话     │  │分布式锁     │  │事务管理     │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                    │                                        │
│  ┌──────────────────────────────────────────────────────────────────────┐  │
│  │                         数据层 (Data Layer)                           │  │
│  │                                                                       │  │
│  │  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐  │  │
│  │  │ PostgreSQL  │  │   Redis     │  │  ChromaDB   │  │ AnythingLLM │  │  │
│  │  │ 关系数据库  │  │  缓存/会话  │  │  向量存储   │  │   LLM 服务  │  │  │
│  │  └─────────────┘  └─────────────┘  └─────────────┘  └─────────────┘  │  │
│  └──────────────────────────────────────────────────────────────────────┘  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### 技术栈

| 层级 | 技术 | 版本 | 说明 |
|------|------|------|------|
| **API 层** | FastAPI | 0.109.0 | 高性能异步 Web 框架 |
| **工作流引擎** | LangGraph | 0.0.28 | 状态机工作流编排 |
| **LLM 集成** | LangChain | 0.1.6 | LLM 应用开发框架 |
| **关系数据库** | PostgreSQL | 15+ | 主数据存储 |
| **ORM** | SQLAlchemy | 2.0.25 | 异步 ORM 支持 |
| **缓存** | Redis | 5.0.1 | 会话存储、分布式锁 |
| **向量数据库** | ChromaDB | 0.4.22 | RAG 向量检索 |
| **数据验证** | Pydantic | 2.5.3 | 数据模型验证 |

---

## 🚀 快速开始

### 前置条件

- Python 3.10+
- PostgreSQL 15+
- Redis 7+
- 8GB+ 内存（用于 BGE-M3 向量模型）

### 安装步骤

```bash
# 1. 克隆项目
git clone <repository-url>
cd aidemo/server

# 2. 创建虚拟环境
python -m venv venv
source venv/bin/activate  # Linux/Mac
# 或
.\venv\Scripts\activate  # Windows

# 3. 安装依赖
pip install -r requirements.txt

# 4. 配置环境变量
cp .env.example .env
# 编辑 .env 文件，填入实际配置

# 5. 初始化数据库
python -c "from models import Base; from database import sync_engine; Base.metadata.create_all(sync_engine)"

# 6. 启动服务
python main.py
# 或
uvicorn main:app --host 0.0.0.0 --port 7000 --reload
```

### 验证安装

```bash
# 健康检查
curl http://localhost:7000/ping

# 预期响应
{"status": "pong"}
```

---

## ⚙️ 环境配置

### 环境变量说明

```bash
# ==================== 环境配置 ====================
# 运行环境：dev（开发）或 prod（生产）
ENV=dev

# ==================== 数据库配置 ====================
# PostgreSQL 连接 URL（生产环境必填）
DATABASE_URL=postgresql+asyncpg://user:password@localhost:5432/agri_ai

# ==================== Redis 配置 ====================
# Redis 连接 URL
REDIS_URL=redis://localhost:6379/0

# 挂起会话超时时间（秒）
PENDING_SESSION_TIMEOUT=1800

# ==================== 向量数据库配置 ====================
# ChromaDB 持久化目录
CHROMA_PERSIST_DIRECTORY=./chroma_db

# ChromaDB 集合名称
CHROMA_COLLECTION_NAME=farm_experience_rules

# ==================== LLM 服务配置 ====================
# AnythingLLM API URL
ANYTHING_LLM_API_URL=http://localhost:3001/api/v1

# AnythingLLM API Key（生产环境必填）
ANYTHING_LLM_API_KEY=your-api-key-here

# ==================== Bucketing 配置 ====================
# 温度桶大小（°C）
TEMP_BUCKET_SIZE=2

# 湿度桶大小（%）
HUMIDITY_BUCKET_SIZE=10

# 光照强度桶大小（lux）
LIGHT_BUCKET_SIZE=500

# 土壤湿度桶大小（%）
SOIL_MOISTURE_BUCKET_SIZE=10

# ==================== 时间窗口配置 ====================
# 操作聚合窗口（分钟）
ACTION_CHUNK_WINDOW_MINUTES=20

# 环境稳态阈值（分钟）
ENV_STABILITY_THRESHOLD_MINUTES=15

# ==================== 应用配置 ====================
# 日志级别
LOG_LEVEL=INFO

# 调试模式（仅开发环境）
DEBUG=false
```

### 环境区分策略

| 配置项 | 开发环境 | 生产环境 |
|--------|---------|---------|
| 数据库连接失败 | 使用模拟模式 | 直接退出 (sys.exit(1)) |
| API Key 验证 | 可选 | 必须配置 |
| 日志敏感数据 | 可记录 | 脱敏处理 |
| 错误详情返回 | 完整堆栈 | 仅 request_id |

---

## 📦 核心模块

### 目录结构

```
server/
├── agents/                     # LangGraph 智能体
│   ├── state.py               # FarmState 状态定义
│   ├── farm_graph.py          # 工作流拓扑
│   └── nodes/                 # 工作流节点
│       └── knowledge_refiner_node.py
│
├── services/                   # 业务服务层
│   ├── action_chunker.py      # 意图指纹引擎
│   ├── risk_assessor.py       # 风险评估器
│   ├── confidence_manager.py  # 置信度管理器
│   ├── redis_session_store.py # Redis 会话存储
│   ├── pending_session_manager.py  # 挂起会话管理
│   ├── explainability_service.py   # 对比分析引擎
│   ├── distributed_lock.py    # 分布式锁
│   ├── transaction_manager.py # 事务管理器
│   ├── buffer.py              # 数据缓冲管理
│   ├── cleaner.py             # 数据清理服务
│   └── dispatcher.py          # 技能调度器
│
├── tools/                      # 工具层
│   ├── rag_vector_store.py    # RAG 向量存储
│   ├── api_tools.py           # API 工具
│   └── query_tools.py         # 查询工具
│
├── schemas/                    # 数据模型
│   ├── experience.py          # 经验反馈模型
│   └── logic_metadata.py      # 逻辑元数据
│
├── config/                     # 配置管理
│   ├── settings.py            # 环境配置
│   └── risk_levels.yaml       # 风险等级配置
│
├── migrations/                 # 数据库迁移
│   ├── migration_monthly_partition.py
│   └── migration_index_optimization.py
│
├── tests/                      # 测试文件
│   ├── test_action_chunker_bucketing.py
│   ├── test_redis_session.py
│   └── test_environment_config.py
│
├── models.py                   # 数据库模型
├── database.py                 # 数据库配置
├── main.py                     # FastAPI 应用入口
└── requirements.txt            # 依赖列表
```

### 核心模块说明

#### 1. ActionChunker (意图指纹引擎)

```python
from services.action_chunker import action_chunker

# 添加操作到缓冲区
await action_chunker.add_action(
    actor_id="farmer_001",
    action={
        'action_type': 'IRRIGATION',
        'target_device': 'valve_01',
        'value': 50,
        'unit': 'L'
    },
    env_snapshot={
        'temp': 25.3,      # 会被 Bucketing 为 24°C
        'humidity': 55,    # 会被 Bucketing 为 50%
        'weather': 'sunny'
    }
)

# 生成意图指纹
action_set_hash = await action_chunker.generate_action_set_hash("farmer_001")
```

#### 2. RiskAssessor (风险评估器)

```python
from services.risk_assessor import risk_assessor
from models import RiskLevel

# 评估操作风险
risk_level = risk_assessor.assess_risk(
    action_type="FERTILIZATION",
    target_device="施肥系统",
    value=100,
    env_conditions={"temperature": 38, "area": 1500}
)
# 返回 RiskLevel.HIGH

# 高风险操作锁定设备
lock_id = await risk_assessor.acquire_device_lock(
    device_id="fertilizer_01",
    owner="session_123",
    timeout=600
)
```

#### 3. ConfidenceManager (置信度管理器)

```python
from services.confidence_manager import confidence_manager, FeedbackType

# 显式确认：+1.0
result = await confidence_manager.update_confidence(
    logic_id=123,
    feedback_type=FeedbackType.CONFIRM_LOGIC
)

# 隐式确认：+0.2（2小时无反悔）
result = await confidence_manager.apply_implicit_confirm(
    logic_id=123,
    action_time=datetime.now() - timedelta(hours=3)
)

# 纠正反馈：旧-0.5，新继承50%
result = await confidence_manager.apply_correct_feedback(
    old_logic_id=123,
    new_logic_id=456
)
```

#### 4. RAGVectorStore (向量存储)

```python
from tools.rag_vector_store import rag_vector_store

# 添加规则
doc_id = await rag_vector_store.add_rule(
    quantized_logic={
        "metric_name": "soil_water_avg_pct",
        "condition": "weather_forecast == 'rain'",
        "action": "decrease_threshold",
        "value": 5.0
    },
    metadata={"priority": 7}
)

# 检索相似规则
results = await rag_vector_store.search_similar_rules(
    query="雨季灌溉策略",
    n_results=5
)

# 更新规则版本（Soft Delete + 新版本）
new_id = await rag_vector_store.update_rule_version(
    logic_id="old_id",
    new_logic={...},
    evolution_reason="树长大了，需要更多水分"
)
```

---

## 📚 API 文档

### 核心 API 接口

#### 1. POST /api/v1/experience/execute

执行操作并创建挂起会话（高风险操作）

**请求体**:
```json
{
  "actions": [
    {
      "action_type": "FERTILIZATION",
      "device": "fertilizer_01",
      "value": 100,
      "unit": "kg"
    }
  ],
  "env_snapshot": {
    "temp": 28.5,
    "humidity": 60,
    "weather": "sunny"
  },
  "actor_id": "farmer_001"
}
```

**响应**:
```json
{
  "status": "pending_confirmation",
  "session_id": "pending:audit_123",
  "action_set_hash": "a1b2c3d4e5f6...",
  "risk_level": "HIGH",
  "matched_logic": {
    "id": "logic_456",
    "similarity": 0.85,
    "content": "高温天气施肥建议..."
  }
}
```

#### 2. POST /api/v1/experience/confirm

提交用户反馈确认

**请求体**:
```json
{
  "session_id": "pending:audit_123",
  "feedback_type": "confirm_logic",
  "selected_logic_id": 456
}
```

**响应**:
```json
{
  "status": "success",
  "message": "逻辑已确认",
  "confidence_update": {
    "old_confidence": 2.5,
    "new_confidence": 3.5,
    "change_type": "explicit_confirm"
  }
}
```

#### 3. GET /api/v1/logic/{logic_id}/history

获取规则版本历史

**响应**:
```json
{
  "logic_id": "logic_456",
  "current_version": 3,
  "evolution_timeline": [
    {
      "version": 1,
      "created_at": "2025-01-15T10:00:00",
      "evolution_reason": null
    },
    {
      "version": 2,
      "created_at": "2025-02-20T14:30:00",
      "evolution_reason": "天气更热了"
    },
    {
      "version": 3,
      "created_at": "2025-03-25T09:15:00",
      "evolution_reason": "树长大了"
    }
  ],
  "total_evolutions": 2
}
```

#### 4. POST /api/v1/chat

与农场 Agent 对话

**请求体**:
```json
{
  "message": "今天天气怎么样？需要灌溉吗？",
  "thread_id": "optional-thread-id"
}
```

**响应**:
```json
{
  "status": "success",
  "thread_id": "uuid-thread-id",
  "data": {
    "answer": "根据当前天气和土壤湿度分析...",
    "sensor_data": {...},
    "comparison_report": "..."
  }
}
```

---

## 🗄️ 数据库设计

### 核心表结构

#### AgentActionAudit (动作审计表)

```sql
CREATE TABLE agent_action_audit (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(64),                    -- 挂起会话ID
    action_set_hash VARCHAR(32),               -- 操作组合哈希指纹
    matched_logic_id INTEGER,                  -- 匹配的逻辑ID
    status VARCHAR(32) DEFAULT 'executed',     -- 状态机
    env_snapshot_ref JSON,                     -- 环境快照（知识蒸馏）
    version INTEGER DEFAULT 0,                 -- 乐观锁版本号
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_audit_session ON agent_action_audit(session_id);
CREATE INDEX idx_audit_hash ON agent_action_audit(action_set_hash);
```

#### LogicGraftingLog (逻辑嫁接日志)

```sql
CREATE TABLE logic_grafting_logs (
    id BIGSERIAL PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    feedback_type VARCHAR(32) NOT NULL,        -- confirm_logic/adjust_logic/new_logic
    selected_logic_id INTEGER,
    new_reasoning TEXT,
    confidence_score NUMERIC(5, 2),             -- 置信度分数（RLHF）
    created_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_log_session ON logic_grafting_logs(session_id);
```

#### PolicyRiskThreshold (策略风险阈值表)

```sql
CREATE TABLE policy_risk_thresholds (
    strategy_id BIGSERIAL PRIMARY KEY,
    metric_name VARCHAR(64) NOT NULL,
    threshold_logic JSON NOT NULL,             -- 包含 confidence_score
    priority INTEGER DEFAULT 1,
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

CREATE INDEX idx_metric_priority ON policy_risk_thresholds(metric_name, priority DESC);
```

### 状态机定义

```
┌─────────────────────────────────────────────────────────────────┐
│                    ActionStatus 状态机                          │
├─────────────────────────────────────────────────────────────────┤
│                                                                 │
│  ┌──────────┐     执行成功      ┌──────────────────────┐       │
│  │ pending  │ ───────────────> │ executed             │       │
│  └──────────┘                  └──────────────────────┘       │
│       │                                                        │
│       │ 高风险操作挂起                                         │
│       ▼                                                        │
│  ┌──────────────────────────┐                                 │
│  │ pending_logic_confirmation│                                │
│  └──────────────────────────┘                                 │
│       │                                                        │
│       ├─ 用户确认 ──> executed                                 │
│       ├─ 用户拒绝 ──> rejected                                │
│       └─ 超时无反馈 ──> executed_without_feedback              │
│                                                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚢 部署指南

### Docker 部署

```dockerfile
# Dockerfile
FROM python:3.10-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y \
    gcc \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

# 安装 Python 依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制应用代码
COPY . .

# 暴露端口
EXPOSE 7000

# 启动命令
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "7000"]
```

```yaml
# docker-compose.yml
version: '3.8'

services:
  api:
    build: .
    ports:
      - "7000:7000"
    environment:
      - ENV=prod
      - DATABASE_URL=postgresql+asyncpg://postgres:password@db:5432/agri_ai
      - REDIS_URL=redis://redis:6379/0
      - ANYTHING_LLM_API_KEY=${ANYTHING_LLM_API_KEY}
    depends_on:
      - db
      - redis
    restart: always

  db:
    image: postgres:15
    environment:
      - POSTGRES_USER=postgres
      - POSTGRES_PASSWORD=password
      - POSTGRES_DB=agri_ai
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: always

  redis:
    image: redis:7-alpine
    volumes:
      - redis_data:/data
    restart: always

volumes:
  postgres_data:
  redis_data:
```

### 生产环境检查清单

- [ ] 配置 `ENV=prod`
- [ ] 配置 `DATABASE_URL`
- [ ] 配置 `ANYTHING_LLM_API_KEY`
- [ ] 配置 `REDIS_URL`
- [ ] 执行数据库迁移
- [ ] 配置 HTTPS 证书
- [ ] 配置请求限流
- [ ] 配置日志收集
- [ ] 配置监控告警

---

## 🔒 安全策略

### API Key 安全

```python
# ❌ 禁止硬编码 API Key
API_KEY = "sk-xxxxx"  # 错误！

# ✅ 使用环境变量
API_KEY = os.getenv("ANYTHING_LLM_API_KEY")
```

### 日志脱敏

```python
# 所有日志输出都会自动脱敏敏感信息
print(f"[ENV] API_KEY: {settings.get_masked_api_key()}")
# 输出: [ENV] API_KEY: sk-abc...xyz

print(f"[ENV] DATABASE_URL: {settings.get_masked_database_url()}")
# 输出: [ENV] DATABASE_URL: postgresql://user:***@localhost:5432/agri_ai
```

### 生产环境安全策略

1. **数据库连接失败直接退出**：生产环境下数据库连接失败会触发 `sys.exit(1)`
2. **请求限流**：默认每分钟 100 次请求限制
3. **错误信息脱敏**：生产环境只返回 `request_id`，不返回完整堆栈
4. **环境区分**：严格区分 `dev` 和 `prod` 环境配置

---

## 👨‍💻 开发指南

### 代码规范

1. **节点函数规范**：
   - 必须使用 `async def`
   - 只调用外部服务，不包含业务逻辑
   - 必须有 `try-except` 错误处理
   - 返回增量更新字典，不返回全量 state

2. **服务层规范**：
   - 业务逻辑封装在服务层
   - 使用依赖注入管理数据库会话
   - 异步操作使用 `asyncio.to_thread` 避免阻塞

3. **数据模型规范**：
   - 使用 Pydantic V2 进行数据验证
   - Enum 序列化使用 `use_enum_values = True`

### 测试

```bash
# 运行所有测试
pytest server/tests/ -v

# 运行特定测试
pytest server/tests/test_action_chunker_bucketing.py -v

# 运行覆盖率测试
pytest server/tests/ --cov=server --cov-report=html
```

### 提交规范

```
feat: 新功能
fix: 修复 bug
docs: 文档更新
refactor: 重构
test: 测试相关
chore: 构建/工具相关
```

---

## 📄 License

MIT License

---

## 🤝 贡献指南

欢迎提交 Issue 和 Pull Request！

1. Fork 本仓库
2. 创建特性分支 (`git checkout -b feature/AmazingFeature`)
3. 提交更改 (`git commit -m 'feat: Add some AmazingFeature'`)
4. 推送到分支 (`git push origin feature/AmazingFeature`)
5. 创建 Pull Request

---

<div align="center">

**⭐ 如果这个项目对你有帮助，请给一个 Star！⭐**

Made with ❤️ by Smart Agriculture Team

</div>
