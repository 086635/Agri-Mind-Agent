import sys
import os
import asyncio
import uuid
import json
import traceback
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, BackgroundTasks, Depends, Request, HTTPException, status
from fastapi.responses import JSONResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.orm import Session
from sqlalchemy import select
import uvicorn
import httpx
from pydantic import BaseModel # 用于定义聊天请求体
from langgraph.checkpoint.memory import MemorySaver
from langchain_core.messages import HumanMessage
from dotenv import load_dotenv

# 必须在导入其他业务模块之前加载环境变量
load_dotenv(os.path.join(os.path.dirname(__file__), "..", ".env"))

# 导入配置模块
from config import settings, Environment

# 打印环境信息（脱敏）
print(f"[ENV] 运行环境: {settings.ENV.value}")
print(f"[ENV] 调试模式: {settings.DEBUG}")
print(f"[ENV] ANYTHING_LLM_API_URL: {settings.ANYTHING_LLM_API_URL or '未配置'}")
print(f"[ENV] ANYTHING_LLM_API_KEY: {settings.get_masked_api_key()}")

# 将当前文件 (main.py) 所在的目录 (server) 加入系统路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入业务模块
from agents.state import initialize_farm_state, create_learning_state
from agents.farm_graph import app as agent_app, run_experience_quantization # 避免与 FastAPI 的 app 冲突

# --- 原有导入 ---
try:
    from database import sync_engine, get_db, SessionLocal, AsyncSessionLocal
    import models
    from models import Base, RawEnvironmentalReading, AgentActionAudit, PolicyRiskThreshold, LogicGraftingLog, ActionStatus, RiskLevel
    from schemas import TelemetryPayload
    from services.buffer import buffer_manager
    from services.cleaner import auto_clean_old_data
    from services.dispatcher import dispatcher
    from services.strategy_cache import strategy_cache
    from services.strategy_query_service import strategy_query_service

    # 新增导入：经验反馈相关服务
    from services.action_chunker import action_chunker
    from services.pending_session_manager import pending_session_manager
    from services.explainability_service import explainability_service
    from services.transaction_manager import transaction_manager
    from services.distributed_lock import lock_manager
    # 新增导入：风险评估器
    from services.risk_assessor import risk_assessor, DeviceLockedError
    from schemas.experience import (
        ExecuteRequest, ExecuteResponse, ConfirmRequest,
        ConfirmLogicRequest, AdjustLogicRequest, NewLogicRequest,
        ConfirmResponse, LogicHistoryResponse, ErrorResponse
    )
    from tools.rag_vector_store import rag_vector_store
    
    # 自动建表
    Base.metadata.create_all(bind=sync_engine)
    print("[OK] 数据库连接成功")
except Exception as e:
    error_msg = f"数据库连接失败: {str(e)}"
    
    # 生产环境：直接退出
    if settings.is_production:
        print(f"[CRITICAL] {error_msg}")
        print(f"[CRITICAL] 生产环境数据库连接失败，系统退出")
        sys.exit(1)
    
    # 开发环境：使用模拟模式
    print(f"[WARN] {error_msg}，使用模拟数据")
    
    # 定义模拟的数据库相关对象
    class MockSession:
        def close(self):
            
            pass
    
    def MockSessionLocal():
        return MockSession()
    
    # 模拟其他依赖
    buffer_manager = type('MockBufferManager', (), {
        'get_and_clear_batch': lambda self: []
    })()
    
    async def auto_clean_old_data():
        print("[WARN] 模拟执行数据清理")
    
    class MockDispatcher:
        async def run_all_skills(self):
            print("[WARN] 模拟执行技能调度")
    
    dispatcher = MockDispatcher()
    
    # 重命名模拟对象
    SessionLocal = MockSessionLocal
    
    # 模拟 TelemetryPayload
    from pydantic import BaseModel
    class TelemetryPayload(BaseModel):
        device_id: str
        sensor_type: str
        value: float

# 使用 lifespan 事件处理器替代 on_event（解决弃用警告）
from contextlib import asynccontextmanager


def _task_exception_handler(task: asyncio.Task):
    """后台任务异常处理回调"""
    try:
        # 尝试获取任务结果，如果有异常则会抛出
        exc = task.exception()
        if exc:
            print(f"[TASK ERROR] 后台任务异常: {type(exc).__name__}: {str(exc)}")
            traceback.print_exception(type(exc), exc, exc.__traceback__)
    except asyncio.CancelledError:
        print(f"[TASK] 后台任务已取消: {task.get_name()}")
    except Exception as e:
        print(f"[TASK ERROR] 获取任务异常失败: {str(e)}")


# 全局关闭信号
shutdown_event = asyncio.Event()
# 最后一次刷写完成信号
flush_complete_event = asyncio.Event()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # 启动时
    print("[LIFESPAN] 启动中...")
    
    # 初始化 app.state 用于存储后台任务
    app.state.background_tasks = []
    
    # 重置关闭信号
    shutdown_event.clear()
    flush_complete_event.clear()
    
    # 创建并保存 periodic_tasks 任务
    periodic_task = asyncio.create_task(periodic_tasks(), name="periodic_tasks")
    periodic_task.add_done_callback(_task_exception_handler)
    app.state.background_tasks.append(periodic_task)
    print("[LIFESPAN] periodic_tasks 任务已启动")
    
    # 启动挂起会话管理器的清理任务
    try:
        await pending_session_manager.start_cleanup_task()
        print("[LIFESPAN] 挂起会话管理器已启动")
    except Exception as e:
        print(f"[LIFESPAN WARN] 挂起会话管理器启动失败: {str(e)}")
    
    print("[LIFESPAN] 启动完成")
    
    yield
    
    # 关闭时 - 优雅关闭流程
    print("[LIFESPAN] 正在关闭...")
    
    # 1. 触发关闭信号，通知 periodic_tasks 执行最后一次刷写
    print("[LIFESPAN] 触发关闭信号，等待最后一次数据刷写...")
    shutdown_event.set()
    
    # 2. 等待最后一次刷写完成（最多等待 10 秒）
    try:
        await asyncio.wait_for(flush_complete_event.wait(), timeout=10.0)
        print("[LIFESPAN] 最后一次数据刷写完成")
    except asyncio.TimeoutError:
        print("[LIFESPAN WARN] 等待数据刷写超时，继续关闭流程")
    
    # 3. 停止挂起会话管理器的清理任务
    try:
        await pending_session_manager.stop_cleanup_task()
        print("[LIFESPAN] 挂起会话管理器已停止")
    except Exception as e:
        print(f"[LIFESPAN WARN] 挂起会话管理器停止失败: {str(e)}")
    
    # 4. 取消所有后台任务（带超时保护）
    shutdown_timeout = 5.0  # 每个任务最多等待 5 秒
    for task in app.state.background_tasks:
        if not task.done():
            task.cancel()
            try:
                await asyncio.wait_for(task, timeout=shutdown_timeout)
            except (asyncio.CancelledError, asyncio.TimeoutError):
                pass
    
    print(f"[LIFESPAN] 已取消 {len(app.state.background_tasks)} 个后台任务")
    print("[LIFESPAN] 关闭完成")

app = FastAPI(title="硅基商业智能物联网网关", version="1.1", lifespan=lifespan)

# ==================== 请求限流配置 ====================

if settings.RATE_LIMIT_ENABLED:
    try:
        from slowapi import Limiter
        from slowapi.util import get_remote_address
        from slowapi.middleware import SlowAPIMiddleware
        
        # 创建限流器
        limiter = Limiter(key_func=get_remote_address)
        app.state.limiter = limiter
        
        # 添加限流中间件
        app.add_middleware(SlowAPIMiddleware)
        
        print(f"[OK] 请求限流已启用: {settings.RATE_LIMIT_PER_MINUTE} 次/分钟")
    except ImportError as e:
        print(f"[WARN] slowapi 未安装或导入失败: {e}，跳过限流配置")
        limiter = None
else:
    limiter = None
    print("[INFO] 请求限流已禁用")

# ==================== 全局异常处理 ====================

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """验证错误异常处理"""
    request_id = str(uuid.uuid4())
    errors = []
    for error in exc.errors():
        errors.append({
            "field": ".".join(str(loc) for loc in error["loc"]),
            "message": error["msg"],
            "type": error["type"]
        })
    
    # 服务器端全量日志
    print(f"[{request_id}] 验证错误: {json.dumps(errors, ensure_ascii=False)}")
    print(f"[{request_id}] 请求路径: {request.method} {request.url}")
    print(f"[{request_id}] 客户端IP: {request.client.host if request.client else 'unknown'}")
    
    # 前端返回脱敏信息
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={
            "status": "error",
            "request_id": request_id,
            "msg": "请求参数验证失败",
            "errors": errors
        }
    )


@app.exception_handler(HTTPException)
async def http_exception_handler(request: Request, exc: HTTPException):
    """HTTP异常处理"""
    request_id = str(uuid.uuid4())
    
    # 服务器端全量日志
    print(f"[{request_id}] HTTP异常: {exc.status_code} - {exc.detail}")
    print(f"[{request_id}] 请求路径: {request.method} {request.url}")
    print(f"[{request_id}] 客户端IP: {request.client.host if request.client else 'unknown'}")
    
    # 前端返回脱敏信息
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "status": "error",
            "request_id": request_id,
            "msg": exc.detail
        }
    )


@app.exception_handler(Exception)
async def general_exception_handler(request: Request, exc: Exception):
    """通用异常处理"""
    request_id = str(uuid.uuid4())
    
    # 记录现场快照（服务器端全量日志）
    reasoning_context = {
        "request_id": request_id,
        "request_method": request.method,
        "request_url": str(request.url),
        "client_ip": request.client.host if request.client else "unknown",
        "timestamp": datetime.now().isoformat(),
        "environment": settings.ENV.value,
        "exception_type": type(exc).__name__,
        "exception_message": str(exc),
        "traceback": traceback.format_exc()
    }
    
    # 服务器端打印详细日志
    print(f"\n{'='*80}")
    print(f"[{request_id}] 未处理异常现场快照:")
    print(json.dumps(reasoning_context, indent=2, ensure_ascii=False))
    print(f"{'='*80}\n")
    
    # 前端返回脱敏信息（不包含敏感数据）
    response_content = {
        "status": "error",
        "request_id": request_id,
        "msg": "服务器内部错误，请稍后重试"
    }
    
    # 仅在开发环境返回详细错误信息
    if settings.is_development and settings.DEBUG:
        response_content["detail"] = str(exc)
        response_content["exception_type"] = type(exc).__name__
    
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=response_content
    )

# ==================== Qwen LLM 调用工具 ====================

QWEN_API_KEY = os.getenv("QWEN_API_KEY", "")
QWEN_API_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"


async def call_qwen(system_prompt: str, user_message: str) -> str:
    """
    调用通义千问 LLM

    Args:
        system_prompt: 系统提示词
        user_message: 用户消息

    Returns:
        AI 回复文本
    """
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {QWEN_API_KEY}"
    }
    payload = {
        "model": "qwen-plus",
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_message}
        ],
        "temperature": 0.7
    }
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(QWEN_API_URL, json=payload, headers=headers, timeout=30.0)
            if response.status_code != 200:
                print(f"[QWEN] API 调用失败: status={response.status_code}, body={response.text[:200]}")
                return "抱歉，AI 服务暂时不可用，请稍后重试。"
            result = response.json()
            content = result.get("choices", [{}])[0].get("message", {}).get("content", "")
            if not content:
                print("[QWEN] AI 返回内容为空")
                return "抱歉，AI 未返回有效内容。"
            return content
    except httpx.TimeoutException:
        print("[QWEN] 请求超时")
        return "抱歉，AI 服务响应超时，请稍后重试。"
    except Exception as e:
        print(f"[QWEN] 调用异常: {e}")
        return f"抱歉，AI 服务调用异常: {str(e)}"


# ==================== 定义请求模型 ====================
class ChatRequest(BaseModel):
    message: str
    thread_id: Optional[str] = None  # 用于多轮对话的会话ID

# --- 新增：定义经验量化请求模型 ---
class ExperienceQuantizationRequest(BaseModel):
    human_reasoning: str
    actor_id: str = "Human"
    device_id: str = None
    batch_id: str = None


class HumanInterventionRequest(BaseModel):
    """人工干预请求 - 用于触发 KnowledgeRefiner 被动式经验提取"""
    audit_id: int
    actual_delta: dict
    env_snapshot: dict = None


# --- 原有后台任务逻辑 (改为异步) ---
async def periodic_tasks():
    """统一管理后台定时任务（异步版本，支持优雅关闭）"""
    while True:
        try:
            # 使用 wait_for 检查关闭信号，同时支持定时执行
            try:
                await asyncio.wait_for(shutdown_event.wait(), timeout=300.0)
                # 如果收到关闭信号，执行最后一次刷写
                print("[PERIODIC] 收到关闭信号，执行最后一次数据刷写...")
                break
            except asyncio.TimeoutError:
                # 正常的 5 分钟定时触发
                pass
            
            # 使用异步数据库会话
            try:
                async with AsyncSessionLocal() as db:
                    batch_data = buffer_manager.get_and_clear_batch()
                    if batch_data:
                        db_items = [
                            RawEnvironmentalReading(
                                device_id=item["device_id"],
                                sensor_type=item["sensor_type"],
                                raw_value=item["raw_value"]
                            ) for item in batch_data
                        ]
                        db.add_all(db_items)
                        await db.commit()
                        print(f"[定时刷写] {len(db_items)} 条数据已入库。")
            except Exception as e:
                print(f"[刷写失败]: {e}")
                # 异步会话会自动回滚

            now = datetime.now()
            # 每日算法调度与清理逻辑
            if now.hour == 2 and 0 <= now.minute < 5:
                await dispatcher.run_all_skills()
            if now.hour == 3 and 0 <= now.minute < 5:
                await auto_clean_old_data()
                
        except asyncio.CancelledError:
            print("[PERIODIC] 任务被取消")
            raise
    
    # 执行最后一次刷写
    try:
        async with AsyncSessionLocal() as db:
            batch_data = buffer_manager.get_and_clear_batch()
            if batch_data:
                db_items = [
                    RawEnvironmentalReading(
                        device_id=item["device_id"],
                        sensor_type=item["sensor_type"],
                        raw_value=item["raw_value"]
                    ) for item in batch_data
                ]
                db.add_all(db_items)
                await db.commit()
                print(f"[最后刷写] {len(db_items)} 条数据已入库。")
            else:
                print("[最后刷写] 无待刷写数据")
    except Exception as e:
        print(f"[最后刷写失败]: {e}")
    finally:
        # 通知 lifespan 刷写完成
        flush_complete_event.set()
        print("[PERIODIC] 最后一次刷写完成，任务退出")

# --- 原有接口：高频数据接收 ---
if limiter:
    @app.post("/api/v1/telemetry", summary="接收高频传感器数据")
    @limiter.limit(f"{settings.RATE_LIMIT_PER_MINUTE}/minute")
    async def receive_telemetry(request: Request, payload: TelemetryPayload):
        """
        接收高频传感器数据
        
        限流：每分钟最多 100 次请求（防止故障传感器打挂系统）
        """
        buffer_manager.add_data(
            device_id=payload.device_id,
            sensor_type=payload.sensor_type,
            value=payload.value
        )
        return {"status": "success", "msg": "数据已进入内存蓄水池"}
else:
    @app.post("/api/v1/telemetry", summary="接收高频传感器数据")
    async def receive_telemetry(payload: TelemetryPayload):
        """接收高频传感器数据"""
        buffer_manager.add_data(
            device_id=payload.device_id,
            sensor_type=payload.sensor_type,
            value=payload.value
        )
        return {"status": "success", "msg": "数据已进入内存蓄水池"}

# --- 新增接口：AI 决策中枢对话 ---
@app.post("/api/v1/chat", summary="与农场 Agent 对话")
async def chat_with_agent(request: ChatRequest):
    """
    接收用户提问，基于传感器数据 + RAG 知识库 + Qwen LLM 生成回答

    支持多轮对话：
    - 首次对话：不传 thread_id，系统会生成新的 thread_id
    - 后续对话：传入之前的 thread_id，系统会恢复对话上下文
    """
    try:
        print(f"\n{'='*60}")
        print(f"[CHAT] 收到用户消息: {request.message}")

        # 1. 生成或使用 thread_id（多用户隔离）
        thread_id = request.thread_id or str(uuid.uuid4())
        print(f"[CHAT] thread_id: {thread_id}")

        # 2. 从 PostgreSQL 读取最新传感器数据
        sensor_rows = []
        try:
            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(RawEnvironmentalReading)
                    .order_by(RawEnvironmentalReading.timestamp.desc())
                    .limit(10)
                )
                sensor_rows = result.scalars().all()
        except Exception as e:
            print(f"[CHAT] 读取传感器数据失败: {e}")

        # 3. 构建传感器上下文文本
        sensor_context = "\n".join([f"{r.sensor_type}: {r.raw_value}" for r in sensor_rows]) if sensor_rows else "暂无传感器数据"

        # 4. 搜索 RAG 知识库
        rag_context = ""
        try:
            rag_results = await rag_vector_store.search_similar_rules(request.message, k=3)
            rag_context = "\n".join([r["content"] for r in rag_results]) if rag_results else ""
        except Exception as e:
            print(f"[CHAT] RAG 检索失败: {e}")

        # 5. 构建系统提示词
        system_prompt = f"""你是一位专业的农业智能助手。根据以下实时传感器数据和知识库信息，为农户提供专业的作物生长分析和建议。

当前传感器数据：
{sensor_context}

相关知识库信息：
{rag_context}

请基于以上信息，回答用户的问题。"""

        # 6. 调用 Qwen LLM
        answer = await call_qwen(system_prompt, request.message)

        # 7. 返回响应
        sensor_snapshot = {r.sensor_type: float(r.raw_value) for r in sensor_rows} if sensor_rows else {}

        print(f"[CHAT] 回答生成完成")
        print(f"{'='*60}\n")

        return {
            "status": "success",
            "thread_id": thread_id,
            "data": {
                "answer": answer,
                "raw_sensor_snapshot": sensor_snapshot,
                "weather_snapshot": {"condition": "晴", "temperature": "28°C"}
            }
        }
    except Exception as e:
        print(f"\n[CHAT] CRITICAL ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        print(f"{'='*60}\n")
        return {"status": "error", "msg": f"Agent 运行异常: {str(e)}"}

# --- 新增接口：农户操作经验量化 ---
@app.post("/api/v1/experience/quantize", summary="农户操作经验量化")
async def quantize_farmer_experience(request: ExperienceQuantizationRequest):
    """
    接收农户口语化理由，触发经验量化工作流
    
    工作流：
    1. intent_quantizer: 语义理由提取
    2. conflict_checker: 冲突检测
    3. logic_upsert: 规则持久化
    
    返回：
    - 量化后的结构化规则
    - 冲突检测结果
    - 持久化状态
    """
    try:
        print(f"\n{'='*60}")
        print(f"[PROBE] quantize_farmer_experience called")
        print(f"[PROBE] Request parameters:")
        print(f"  - human_reasoning: {request.human_reasoning}")
        print(f"  - actor_id: {request.actor_id}")
        print(f"  - device_id: {request.device_id}")
        print(f"  - batch_id: {request.batch_id}")
        
        # 运行经验量化工作流
        print(f"\n[PROBE] Calling run_experience_quantization...")
        result = await run_experience_quantization(
            human_reasoning=request.human_reasoning,
            actor_id=request.actor_id,
            device_id=request.device_id,
            batch_id=request.batch_id
        )
        
        print(f"\n[PROBE] run_experience_quantization completed")
        print(f"[PROBE] Result keys: {list(result.keys())}")
        print(f"[PROBE] Result detail:")
        for key in result.keys():
            value = result[key]
            if isinstance(value, list):
                print(f"  - {key}: list with {len(value)} items")
            elif isinstance(value, dict):
                print(f"  - {key}: dict with keys {list(value.keys())}")
            else:
                print(f"  - {key}: {type(value).__name__} = {value}")
        print(f"{'='*60}\n")
        
        # 检查是否有冲突
        if result.get("conflict_detected"):
            return {
                "status": "conflict",
                "msg": "检测到冲突，规则未持久化",
                "data": {
                    "quantized_logic": result.get("quantized_logic"),
                    "conflict_details": result.get("conflict_details"),
                    "resolution_suggestion": result.get("conflict_resolution")
                }
            }
        
        # 检查是否有错误
        if result.get("error_message"):
            return {
                "status": "error",
                "msg": result.get("error_message"),
                "data": result
            }
        
        # 成功
        return {
            "status": "success",
            "msg": "经验量化成功，规则已持久化到数据库和RAG",
            "data": {
                "quantized_logic": result.get("quantized_logic"),
                "audit_id": result.get("audit_id"),
                "human_reasoning": result.get("human_reasoning")
            }
        }
        
    except Exception as e:
        return {"status": "error", "msg": f"经验量化异常: {str(e)}"}


@app.post("/api/v1/experience/refine", summary="人工干预经验提取（被动式）")
async def refine_human_intervention(request: HumanInterventionRequest):
    """
    记录人工干预行为，    触发 KnowledgeRefiner 被动式经验提取
    
    使用场景：
    1. Agent 做出决策（如全开窗户降温）
    2. 人类手动覆盖决策（如只开 10% 防雨）
    3. 调用此接口记录人类实际操作
    4. 系统自动检测冲突并提取隐性知识
    
    返回：
    - 冲突检测结果
    - 知识蒸馏结果
    - 向量库存储状态
    """
    try:
        from agents.nodes.knowledge_refiner_node import knowledge_refiner_node
        from database import AsyncSessionLocal
        from models import AgentActionAudit
        from sqlalchemy import select
        
        print(f"\n{'='*60}")
        print(f"[REFINE] 人工干预经验提取")
        print(f"  - audit_id: {request.audit_id}")
        print(f"  - actual_delta: {request.actual_delta}")
        
        async with AsyncSessionLocal() as session:
            stmt = select(AgentActionAudit).where(
                AgentActionAudit.audit_id == request.audit_id
            )
            result = await session.execute(stmt)
            audit_record = result.scalar_one_or_none()
            
            if not audit_record:
                return {
                    "status": "error",
                    "msg": f"审计记录不存在: audit_id={request.audit_id}"
                }
            
            audit_record.actual_delta = request.actual_delta
            if request.env_snapshot:
                audit_record.expected_delta = {
                    **audit_record.expected_delta,
                    "_env_snapshot": request.env_snapshot
                }
            await session.commit()
            
            state = {
                "actor_id": audit_record.actor_id,
                "audit_id": audit_record.audit_id,
                "human_reasoning": audit_record.reasoning_context,
                "quantized_logic": audit_record.expected_delta,
                "actual_delta": request.actual_delta,
                "env_snapshot": request.env_snapshot or {}
            }
            
            refine_result = await knowledge_refiner_node(state)
            
            if refine_result.get("knowledge_refined"):
                return {
                    "status": "success",
                    "msg": "隐性知识已提取并存储到向量库",
                    "data": {
                        "doc_id": refine_result.get("doc_id"),
                        "distilled_knowledge": refine_result.get("distilled_knowledge"),
                        "conflict_result": refine_result.get("conflict_result")
                    }
                }
            else:
                return {
                    "status": "skipped",
                    "msg": f"经验提取跳过: {refine_result.get('refinement_skipped_reason')}",
                    "data": refine_result
                }
        
    except Exception as e:
        print(f"[REFINE] 错误: {str(e)}")
        import traceback
        traceback.print_exc()
        return {"status": "error", "msg": f"经验提取异常: {str(e)}"}


@app.get("/api/v1/rag/stats", summary="获取RAG向量库统计信息")
async def get_rag_stats():
    """
    获取 RAG 向量库统计信息
    
    返回：
    - 文档数量
    - 集合名称
    - 状态
    """
    try:
        from tools.rag_vector_store import rag_vector_store
        
        stats = await rag_vector_store.get_collection_stats()
        return {
            "status": "success",
            "data": stats
        }
    except Exception as e:
        return {"status": "error", "msg": f"获取RAG统计失败: {str(e)}"}


@app.post("/api/v1/rag/search", summary="搜索相似规则")
async def search_similar_rules(query: str, k: int = 5):
    """
    搜索相似规则
    
    Args:
        query: 查询文本
        k: 返回结果数量
    
    返回：
    - 相似规则列表
    """
    try:
        from tools.rag_vector_store import rag_vector_store
        
        rules = await rag_vector_store.search_similar_rules(query, k=k)
        return {
            "status": "success",
            "data": {
                "query": query,
                "rules": rules,
                "count": len(rules)
            }
        }
    except Exception as e:
        return {"status": "error", "msg": f"搜索失败: {str(e)}"}


# --- 新增接口：缓存监控 ---
@app.get("/api/v1/cache/stats", summary="获取缓存统计信息")
async def get_cache_stats():
    """
    获取缓存统计信息
    
    返回：
    - 总请求数
    - 命中数
    - 未命中数
    - 命中率
    - 淘汰数
    - 失效数
    - 当前缓存大小
    """
    try:
        stats = strategy_cache.get_stats()
        return {
            "status": "success",
            "data": stats
        }
    except Exception as e:
        return {"status": "error", "msg": f"获取缓存统计失败: {str(e)}"}

@app.get("/api/v1/cache/info", summary="获取缓存详细信息")
async def get_cache_info():
    """
    获取缓存详细信息
    
    返回：
    - 统计信息
    - 所有缓存条目
    """
    try:
        info = strategy_cache.get_cache_info()
        return {
            "status": "success",
            "data": info
        }
    except Exception as e:
        return {"status": "error", "msg": f"获取缓存信息失败: {str(e)}"}

@app.post("/api/v1/cache/clear-expired", summary="清理过期缓存")
async def clear_expired_cache():
    """
    清理过期缓存
    
    返回：
    - 清理的条目数
    """
    try:
        count = strategy_cache.clear_expired()
        return {
            "status": "success",
            "msg": f"已清理 {count} 个过期缓存条目",
            "data": {"cleared_count": count}
        }
    except Exception as e:
        return {"status": "error", "msg": f"清理过期缓存失败: {str(e)}"}

@app.post("/api/v1/cache/invalidate-all", summary="失效所有缓存")
async def invalidate_all_cache():
    """
    失效所有缓存
    
    用于手动触发缓存失效
    """
    try:
        strategy_cache.invalidate_all()
        return {
            "status": "success",
            "msg": "所有缓存已失效"
        }
    except Exception as e:
        return {"status": "error", "msg": f"失效缓存失败: {str(e)}"}

# --- 新增接口：策略查询（带缓存）---
@app.get("/api/v1/strategies/{strategy_id}", summary="查询单个策略")
async def get_strategy(strategy_id: int):
    """
    查询单个策略（优先从缓存）
    
    Args:
        strategy_id: 策略ID
    """
    try:
        strategy = await strategy_query_service.get_strategy_by_id(strategy_id)
        
        if strategy:
            return {
                "status": "success",
                "data": strategy
            }
        else:
            return {
                "status": "error",
                "msg": f"策略不存在: strategy_id={strategy_id}"
            }
    except Exception as e:
        return {"status": "error", "msg": f"查询策略失败: {str(e)}"}

@app.get("/api/v1/strategies/metric/{metric_name}", summary="查询指标相关策略")
async def get_strategies_by_metric(metric_name: str):
    """
    查询指标相关的所有策略（优先从缓存）
    
    Args:
        metric_name: 指标名称
    """
    try:
        strategies = await strategy_query_service.get_strategies_by_metric(metric_name)
        return {
            "status": "success",
            "data": {
                "metric_name": metric_name,
                "strategies": strategies,
                "count": len(strategies)
            }
        }
    except Exception as e:
        return {"status": "error", "msg": f"查询策略失败: {str(e)}"}

@app.get("/api/v1/strategies", summary="查询所有策略")
async def get_all_strategies():
    """
    查询所有策略（优先从缓存）
    """
    try:
        strategies = await strategy_query_service.get_all_strategies()
        return {
            "status": "success",
            "data": {
                "strategies": strategies,
                "count": len(strategies)
            }
        }
    except Exception as e:
        return {"status": "error", "msg": f"查询策略失败: {str(e)}"}

# ==================== Task 7: Feedback Hook API ====================

async def _background_analysis(
    session_id: str,
    audit_id: int,
    actions: list,
    env_snapshot: dict
):
    """
    后台分析任务（异步非阻塞）
    
    流程：
    1. 调用 RAGVectorStore 检索相似规则
    2. 调用 ExplainabilityService 生成解释
    3. 更新 PendingSessionManager
    """
    try:
        print(f"[BACKGROUND] 开始后台分析: session_id={session_id}")
        
        # 1. 检索相似规则
        # 构建查询文本
        query_text = f"操作: {json.dumps(actions, ensure_ascii=False)}"
        if env_snapshot:
            query_text += f" 环境: {json.dumps(env_snapshot, ensure_ascii=False)}"
        
        # 调用 RAG 检索
        matched_rules = await rag_vector_store.search_similar_rules(query_text, k=3)
        
        # 2. 转换为匹配逻辑格式
        matched_logics = []
        for idx, rule in enumerate(matched_rules):
            matched_logics.append({
                "logic_id": rule.get("metadata", {}).get("strategy_id", idx),
                "similarity": rule.get("score", 0.5),
                "description": rule.get("content", "")[:100],
                "actions": [rule.get("metadata", {}).get("action", "unknown")],
                "metric_name": rule.get("metadata", {}).get("metric_name"),
                "condition": rule.get("metadata", {}).get("condition")
            })
        
        # 3. 调用可解释性服务生成解释
        try:
            explanation_result = await explainability_service.analyze_and_explain_from_dict(
                current_actions=actions,
                env_snapshot=env_snapshot,
                matched_logics=matched_logics
            )
            explanation = explanation_result.explanation
        except Exception as e:
            print(f"[BACKGROUND] 可解释性服务调用失败: {str(e)}")
            explanation = f"发现您正在执行操作，正在分析中..."
        
        # 4. 更新挂起会话
        pending_session_manager.create_pending_session(
            audit_id=audit_id,
            actions=actions,
            env_snapshot=env_snapshot,
            matched_logics=matched_logics,
            explanation=explanation
        )
        
        print(f"[BACKGROUND] 后台分析完成: session_id={session_id}")
        
    except Exception as e:
        print(f"[BACKGROUND ERROR] 后台分析失败: {str(e)}")
        traceback.print_exc()


@app.post("/api/v1/experience/execute", 
          response_model=ExecuteResponse,
          summary="执行操作并挂起审查",
          status_code=status.HTTP_200_OK)
async def execute_experience(request: ExecuteRequest):
    """
    执行操作并挂起审查（Human-in-the-Loop）
    
    风险分级处理流程：
    1. LOW（低风险）：直接执行，异步审查反馈
    2. MEDIUM（中风险）：执行后审查，记录日志
    3. HIGH（高风险）：挂起等待用户确认，确认后执行
    
    流程：
    1. 评估操作风险等级
    2. 快速写入审计记录（同步，必需）
    3. 生成会话ID
    4. 根据风险等级处理：
       - LOW/MEDIUM: 后台异步任务：RAG检索 + 可解释性分析
       - HIGH: 锁定设备，等待用户确认
    5. 立即返回 pending_confirmation 状态
    
    返回：
    - status: pending_confirmation
    - session_id: 会话ID
    - audit_id: 审计记录ID
    - risk_level: 风险等级
    - analysis: 分析结果（初始为空，后台更新）
    - options: 用户选项
    """
    try:
        print(f"\n{'='*60}")
        print(f"[EXECUTE] 执行操作并挂起审查")
        print(f"  - actions: {len(request.actions)} 个操作")
        print(f"  - reasoning: {request.reasoning}")
        
        # ==================== 风险评估 ====================
        # 提取环境条件用于风险评估
        env_conditions = {}
        if request.env_snapshot.temperature is not None:
            env_conditions['temperature'] = request.env_snapshot.temperature
        if request.env_snapshot.humidity is not None:
            env_conditions['humidity'] = request.env_snapshot.humidity
        if request.env_snapshot.soil_moisture is not None:
            env_conditions['soil_moisture'] = request.env_snapshot.soil_moisture
        if request.env_snapshot.custom_params:
            env_conditions.update(request.env_snapshot.custom_params)
        
        # 评估每个操作的风险等级，取最高风险等级
        max_risk_level = RiskLevel.LOW
        device_ids = []
        
        for action in request.actions:
            # 映射操作类型
            action_type = _map_action_type(action.action, action.device)
            
            # 评估风险
            risk_level = risk_assessor.assess_risk(
                action_type=action_type,
                target_device=action.device,
                value=action.value,
                env_conditions=env_conditions
            )
            
            if risk_level.value > max_risk_level.value:
                max_risk_level = risk_level
            
            device_ids.append(action.device)
            
            print(f"[EXECUTE] 操作风险评估: device={action.device}, "
                  f"action={action.action}, risk_level={risk_level.value}")
        
        print(f"[EXECUTE] 最高风险等级: {max_risk_level.value}")
        
        # ==================== 设备锁定检查（高风险操作）====================
        if max_risk_level == RiskLevel.HIGH:
            # 检查设备是否已被锁定
            for device_id in device_ids:
                if risk_assessor.is_device_locked(device_id):
                    lock_info = risk_assessor.get_device_lock_info(device_id)
                    raise HTTPException(
                        status_code=status.HTTP_423_LOCKED,
                        detail=f"设备 {device_id} 已被锁定，当前有高风险操作正在等待确认。"
                               f"锁定者: {lock_info.get('owner', 'unknown')}"
                    )
        
        # ==================== 快速写入审计记录 ====================
        async with transaction_manager.transaction() as db:
            # 创建审计记录
            audit = AgentActionAudit(
                actor_id="Human",
                action_type="MANUAL_OPERATION",
                reasoning_context=request.reasoning,
                expected_delta={
                    "actions": [action.model_dump() for action in request.actions],
                    "env_snapshot": request.env_snapshot.model_dump(),
                    "risk_level": max_risk_level.value
                },
                status=ActionStatus.pending_logic_confirmation
            )
            db.add(audit)
            await db.flush()  # 获取 audit_id
            
            audit_id = audit.audit_id
            print(f"[EXECUTE] 审计记录已创建: audit_id={audit_id}")
        
        # 生成会话ID
        session_id = str(uuid.uuid4())
        
        # 更新审计记录的 session_id
        async with transaction_manager.transaction() as db:
            stmt = select(AgentActionAudit).where(
                AgentActionAudit.audit_id == audit_id
            )
            result = await db.execute(stmt)
            audit_record = result.scalar_one_or_none()
            
            if audit_record:
                audit_record.session_id = session_id
                print(f"[EXECUTE] 会话ID已更新: session_id={session_id}")
        
        # ==================== 根据风险等级处理 ====================
        execution_policy = risk_assessor.get_execution_policy(max_risk_level)
        
        if max_risk_level == RiskLevel.HIGH:
            # 高风险：锁定设备，等待用户确认
            print(f"[EXECUTE] 高风险操作，锁定设备并等待确认")
            
            # 锁定所有相关设备
            device_locks = {}
            try:
                for device_id in device_ids:
                    lock_id = await risk_assessor.acquire_device_lock(
                        device_id=device_id,
                        owner=f"session_{session_id}",
                        timeout=execution_policy.get('confirmation_timeout', 300)
                    )
                    device_locks[device_id] = lock_id
                    print(f"[EXECUTE] 设备已锁定: device_id={device_id}, lock_id={lock_id}")
                
            except DeviceLockedError as e:
                # 如果锁定失败，释放已获取的锁
                for dev_id, lock_id in device_locks.items():
                    await risk_assessor.release_device_lock(dev_id, lock_id)
                raise HTTPException(
                    status_code=status.HTTP_423_LOCKED,
                    detail=str(e)
                )
            
            # 启动后台分析任务
            background_task = asyncio.create_task(
                _background_analysis(
                    session_id=session_id,
                    audit_id=audit_id,
                    actions=[action.model_dump() for action in request.actions],
                    env_snapshot=request.env_snapshot.model_dump()
                ),
                name=f"background_analysis_{session_id}"
            )
            background_task.add_done_callback(_task_exception_handler)
            
            # 返回高风险确认响应
            response = ExecuteResponse(
                status="pending_confirmation",
                session_id=session_id,
                audit_id=audit_id,
                analysis={
                    "is_new_pattern": True,
                    "matched_logics": [],
                    "explanation": f"检测到高风险操作（{max_risk_level.value}），请确认后执行。"
                },
                options=["confirm_logic", "adjust_logic", "reject"]
            )
            
        else:
            # 低风险/中风险：直接执行，异步审查
            print(f"[EXECUTE] {max_risk_level.value}风险操作，执行并异步审查")
            
            # 启动后台分析任务
            background_task = asyncio.create_task(
                _background_analysis(
                    session_id=session_id,
                    audit_id=audit_id,
                    actions=[action.model_dump() for action in request.actions],
                    env_snapshot=request.env_snapshot.model_dump()
                ),
                name=f"background_analysis_{session_id}"
            )
            background_task.add_done_callback(_task_exception_handler)
            
            # 返回标准响应
            response = ExecuteResponse(
                status="pending_confirmation",
                session_id=session_id,
                audit_id=audit_id,
                analysis={
                    "is_new_pattern": True,
                    "matched_logics": [],
                    "explanation": "正在分析您的操作，请稍候..."
                },
                options=["confirm_logic", "adjust_logic", "new_logic"]
            )
        
        print(f"[EXECUTE] 返回 pending_confirmation 状态")
        print(f"{'='*60}\n")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[EXECUTE ERROR] 执行失败: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"执行操作失败: {str(e)}"
        )


def _map_action_type(action: str, device: str) -> str:
    """
    映射操作类型到标准风险类型
    
    Args:
        action: 操作名称
        device: 设备名称
    
    Returns:
        标准操作类型
    """
    action_lower = action.lower()
    device_lower = device.lower()
    
    # 补光灯
    if 'light' in device_lower or '补光' in device_lower or '灯' in device_lower:
        return 'LIGHT_CONTROL'
    
    # 风扇
    if 'fan' in device_lower or '风扇' in device_lower:
        return 'FAN_CONTROL'
    
    # 灌溉
    if 'irrigat' in device_lower or '灌溉' in device_lower or '水' in device_lower:
        return 'IRRIGATION'
    
    # 通风窗
    if 'window' in device_lower or 'vent' in device_lower or '窗' in device_lower or '通风' in device_lower:
        return 'WINDOW_CONTROL'
    
    # 施肥
    if 'fertil' in device_lower or '施肥' in device_lower or '肥' in device_lower:
        return 'FERTILIZATION'
    
    # 农药喷洒
    if 'pesticide' in device_lower or 'spray' in device_lower or '农药' in device_lower or '喷洒' in device_lower:
        return 'PESTICIDE_SPRAY'
    
    # 默认返回操作名称大写
    return action_upper if (action_upper := action.upper()) else 'UNKNOWN'


@app.post("/api/v1/experience/confirm",
          response_model=ConfirmResponse,
          summary="反馈确认",
          status_code=status.HTTP_200_OK)
async def confirm_experience(request: ConfirmRequest):
    """
    反馈确认（Human-in-the-Loop）
    
    支持三种反馈类型：
    1. confirm_logic: 确认现有逻辑
    2. adjust_logic: 微调现有逻辑
    3. new_logic: 新建逻辑
    
    高风险操作确认后：
    - 释放设备锁
    - 执行操作
    
    返回：
    - status: success
    - audit_id: 审计记录ID
    - logic_updated: 逻辑是否更新
    - new_version: 新版本号
    - message: 消息
    """
    try:
        print(f"\n{'='*60}")
        print(f"[CONFIRM] 反馈确认")
        print(f"  - session_id: {request.session_id}")
        print(f"  - feedback_type: {request.feedback_type}")
        
        # 1. 恢复挂起会话
        session_data = pending_session_manager.resume_session(request.session_id)
        
        if not session_data:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会话不存在或已过期: session_id={request.session_id}"
            )
        
        if session_data.is_expired:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"会话已过期: session_id={request.session_id}"
            )
        
        # 2. 提交反馈
        feedback_type = request.feedback_type
        
        # 检查是否为拒绝操作
        if feedback_type == "reject":
            # 拒绝操作，释放设备锁
            await _release_device_locks_for_session(request.session_id, session_data)
            
            return ConfirmResponse(
                status="success",
                audit_id=session_data.audit_id,
                logic_updated=False,
                new_version=None,
                message="操作已拒绝，设备锁已释放"
            )
        
        if feedback_type == "confirm_logic":
            result = await pending_session_manager.submit_feedback(
                session_id=request.session_id,
                feedback_type=pending_session_manager.FeedbackType.CONFIRM_LOGIC,
                selected_logic_id=request.selected_logic_id
            )
            
        elif feedback_type == "adjust_logic":
            result = await pending_session_manager.submit_feedback(
                session_id=request.session_id,
                feedback_type=pending_session_manager.FeedbackType.ADJUST_LOGIC,
                selected_logic_id=request.selected_logic_id,
                adjustments=request.adjustments
            )
            
        elif feedback_type == "new_logic":
            result = await pending_session_manager.submit_feedback(
                session_id=request.session_id,
                feedback_type=pending_session_manager.FeedbackType.NEW_LOGIC,
                new_reasoning=request.new_reasoning
            )
        
        # 3. 检查结果
        if not result.get("success"):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=result.get("error", "反馈提交失败")
            )
        
        # 4. 释放设备锁（高风险操作确认后）
        await _release_device_locks_for_session(request.session_id, session_data)
        
        # 5. 返回响应
        response = ConfirmResponse(
            status="success",
            audit_id=result.get("audit_id"),
            logic_updated=True,
            new_version=1,
            message=result.get("message", "反馈已提交，设备锁已释放")
        )
        
        print(f"[CONFIRM] 反馈提交成功: audit_id={response.audit_id}")
        print(f"{'='*60}\n")
        
        return response
        
    except HTTPException:
        raise
    except Exception as e:
        print(f"[CONFIRM ERROR] 反馈提交失败: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"反馈提交失败: {str(e)}"
        )


async def _release_device_locks_for_session(session_id: str, session_data: Any) -> None:
    """
    释放会话相关的设备锁
    
    Args:
        session_id: 会话ID
        session_data: 会话数据
    """
    try:
        # 从会话数据中提取设备ID列表
        actions = session_data.actions if hasattr(session_data, 'actions') else []
        
        if not actions:
            return
        
        device_ids = set()
        for action in actions:
            if isinstance(action, dict):
                device_id = action.get('device')
            else:
                device_id = getattr(action, 'device', None)
            
            if device_id:
                device_ids.add(device_id)
        
        # 释放设备锁
        for device_id in device_ids:
            if risk_assessor.is_device_locked(device_id):
                lock_info = risk_assessor.get_device_lock_info(device_id)
                # 验证锁的owner是否匹配当前session
                if lock_info and f"session_{session_id}" == lock_info.get('owner'):
                    await risk_assessor.release_device_lock(device_id)
                    print(f"[CONFIRM] 设备锁已释放: device_id={device_id}")
                    
    except Exception as e:
        print(f"[CONFIRM WARN] 释放设备锁失败: {str(e)}")


@app.get("/api/v1/logic/{logic_id}/history",
         response_model=LogicHistoryResponse,
         summary="查询逻辑版本历史",
         status_code=status.HTTP_200_OK)
async def get_logic_history(logic_id: int):
    """
    查询逻辑版本历史
    
    返回：
    - logic_id: 逻辑ID
    - current_version: 当前版本号
    - history: 版本历史列表
    """
    try:
        print(f"\n{'='*60}")
        print(f"[HISTORY] 查询逻辑版本历史: logic_id={logic_id}")
        
        async with transaction_manager.transaction() as db:
            # 查询逻辑记录
            stmt = select(PolicyRiskThreshold).where(
                PolicyRiskThreshold.strategy_id == logic_id
            )
            result = await db.execute(stmt)
            logic = result.scalar_one_or_none()
            
            if not logic:
                raise HTTPException(
                    status_code=status.HTTP_404_NOT_FOUND,
                    detail=f"逻辑不存在: logic_id={logic_id}"
                )
            
            # 查询相关的逻辑嫁接日志
            grafting_stmt = select(LogicGraftingLog).where(
                LogicGraftingLog.selected_logic_id == logic_id
            ).order_by(LogicGraftingLog.created_at.desc())
            
            grafting_result = await db.execute(grafting_stmt)
            grafting_logs = grafting_result.scalars().all()
            
            # 构建版本历史
            history = []
            
            # 添加当前版本
            history.append({
                "version": 1,
                "created_at": logic.created_at.isoformat() if logic.created_at else datetime.now().isoformat(),
                "is_active": True,
                "parent_id": None,
                "reasoning": logic.threshold_logic.get("reasoning") if logic.threshold_logic else None,
                "threshold_logic": logic.threshold_logic
            })
            
            # 添加历史版本（从嫁接日志）
            for idx, log in enumerate(grafting_logs, start=2):
                history.append({
                    "version": idx,
                    "created_at": log.created_at.isoformat() if log.created_at else datetime.now().isoformat(),
                    "is_active": False,
                    "parent_id": f"{logic_id}_v{idx-1}",
                    "reasoning": log.new_reasoning
                })
            
            response = LogicHistoryResponse(
                logic_id=logic_id,
                current_version=1,
                history=history
            )
            
            print(f"[HISTORY] 查询成功: {len(history)} 个版本")
            print(f"{'='*60}\n")
            
            return response
            
    except HTTPException:
        raise
    except Exception as e:
        print(f"[HISTORY ERROR] 查询失败: {str(e)}")
        traceback.print_exc()
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"查询逻辑历史失败: {str(e)}"
        )

# ==================== Task 8: 一致性保障监控接口 ====================

@app.get("/api/v1/locks/status", summary="获取锁状态")
async def get_lock_status():
    """
    获取分布式锁状态
    
    返回：
    - 活跃锁数量
    - 锁详情
    """
    try:
        locks = lock_manager.get_all_locks()
        return {
            "status": "success",
            "data": {
                "active_locks": len(locks),
                "locks": locks
            }
        }
    except Exception as e:
        return {"status": "error", "msg": f"获取锁状态失败: {str(e)}"}


@app.get("/api/v1/sessions/status", summary="获取挂起会话状态")
async def get_sessions_status():
    """
    获取挂起会话状态
    
    返回：
    - 总会话数
    - 待处理会话数
    """
    try:
        total_count = pending_session_manager.get_session_count()
        pending_count = pending_session_manager.get_pending_session_count()
        
        return {
            "status": "success",
            "data": {
                "total_sessions": total_count,
                "pending_sessions": pending_count
            }
        }
    except Exception as e:
        return {"status": "error", "msg": f"获取会话状态失败: {str(e)}"}


@app.get("/api/v1/device-locks/status", summary="获取设备锁状态")
async def get_device_locks_status():
    """
    获取设备锁状态
    
    返回：
    - 活跃设备锁数量
    - 设备锁详情
    - 风险评估器配置
    """
    try:
        device_locks = risk_assessor.get_all_device_locks()
        
        return {
            "status": "success",
            "data": {
                "active_device_locks": len(device_locks),
                "device_locks": device_locks,
                "lock_config": risk_assessor.device_lock_config
            }
        }
    except Exception as e:
        return {"status": "error", "msg": f"获取设备锁状态失败: {str(e)}"}


@app.get("/api/v1/device-locks/{device_id}", summary="查询单个设备锁状态")
async def get_device_lock_status(device_id: str):
    """
    查询单个设备锁状态
    
    Args:
        device_id: 设备ID
    
    返回：
    - 是否被锁定
    - 锁详情
    """
    try:
        is_locked = risk_assessor.is_device_locked(device_id)
        lock_info = risk_assessor.get_device_lock_info(device_id)
        
        return {
            "status": "success",
            "data": {
                "device_id": device_id,
                "is_locked": is_locked,
                "lock_info": lock_info
            }
        }
    except Exception as e:
        return {"status": "error", "msg": f"查询设备锁状态失败: {str(e)}"}


@app.get("/api/v1/risk-assessment/config", summary="获取风险评估配置")
async def get_risk_assessment_config():
    """
    获取风险评估配置
    
    返回：
    - 风险等级定义
    - 执行策略
    - 风险升级规则
    """
    try:
        return {
            "status": "success",
            "data": {
                "risk_levels": {
                    "LOW": risk_assessor.config.get('LOW', {}),
                    "MEDIUM": risk_assessor.config.get('MEDIUM', {}),
                    "HIGH": risk_assessor.config.get('HIGH', {})
                },
                "default_risk_level": risk_assessor.config.get('default_risk_level'),
                "risk_assessment_rules": risk_assessor.config.get('risk_assessment_rules', {}),
                "device_lock_config": risk_assessor.device_lock_config
            }
        }
    except Exception as e:
        return {"status": "error", "msg": f"获取风险评估配置失败: {str(e)}"}


@app.get("/api/v1/health", summary="健康检查")
async def health_check():
    """
    系统健康检查
    
    返回：
    - 数据库连接状态
    - 锁管理器状态
    - 会话管理器状态
    """
    try:
        # 检查数据库连接
        db_status = "healthy"
        try:
            async with AsyncSessionLocal() as db:
                await db.execute(text("SELECT 1"))
        except Exception as e:
            db_status = f"unhealthy: {str(e)}"
        
        # 检查锁管理器
        lock_health = await lock_manager.health_check()
        
        # 检查会话管理器
        session_count = pending_session_manager.get_session_count()
        
        return {
            "status": "healthy",
            "data": {
                "database": db_status,
                "lock_manager": lock_health,
                "session_manager": {
                    "total_sessions": session_count
                },
                "timestamp": datetime.now().isoformat()
            }
        }
    except Exception as e:
        return {
            "status": "unhealthy",
            "msg": str(e),
            "timestamp": datetime.now().isoformat()
        }

if __name__ == "__main__":
    uvicorn.run("main:app", host="0.0.0.0", port=7000, reload=True)