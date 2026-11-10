"""
规则持久化服务层

该模块实现量化规则的数据库和RAG同步写入逻辑
支持事务管理和并发控制
"""

import logging
from typing import Dict, Any, Optional
from datetime import datetime
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from models import PolicyRiskThreshold, AgentActionAudit
from database import AsyncSessionLocal
from tools.rag_vector_store import rag_vector_store
from services.strategy_cache import strategy_cache

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class LogicUpsertService:
    """
    规则持久化服务
    
    职责：
    1. 将量化规则同步写入数据库（PolicyRiskThreshold）
    2. 将量化规则同步写入RAG向量存储
    3. 记录审计日志（AgentActionAudit）
    4. 使用事务确保数据一致性
    """
    
    def __init__(self):
        """初始化规则持久化服务"""
        pass
    
    async def upsert_logic(
        self,
        quantized_logic: Dict[str, Any],
        human_reasoning: str,
        actor_id: str = "Human",
        device_id: Optional[str] = None,
        batch_id: Optional[str] = None,
        session: Optional[AsyncSession] = None
    ) -> Dict[str, Any]:
        """
        持久化规则（数据库 + RAG）
        
        使用事务确保数据一致性：
        - 数据库写入和 RAG 写入必须同时成功或同时失败
        - 如果 RAG 写入失败，数据库事务会自动回滚
        
        Args:
            quantized_logic: 量化后的规则
            human_reasoning: 农户原始理由
            actor_id: 操作者ID
            device_id: 设备ID
            batch_id: 批次ID
            session: 数据库会话（可选，用于外部事务控制）
        
        Returns:
            持久化结果：
            {
                "success": bool,
                "policy_id": int,
                "audit_id": int,
                "rag_document_id": str,
                "message": str
            }
        
        Raises:
            Exception: 持久化失败时抛出异常，包含详细错误信息
        """
        try:
            logger.info(f"开始持久化规则: metric={quantized_logic.get('metric_name')}, actor={actor_id}")
            
            # 如果没有提供会话，创建新会话并管理事务
            if not session:
                async with AsyncSessionLocal() as session:
                    try:
                        result = await self._execute_upsert(
                            quantized_logic,
                            human_reasoning,
                            actor_id,
                            device_id,
                            batch_id,
                            session
                        )
                        # 只有所有操作都成功才提交事务
                        await session.commit()
                        logger.info(f"规则持久化事务已提交: policy_id={result.get('policy_id')}")
                        return result
                    except Exception as e:
                        # 异常时自动回滚（async with 会处理）
                        logger.error(f"规则持久化失败，事务已回滚: {str(e)}")
                        raise
            else:
                # 使用外部会话（由调用方管理事务）
                # 注意：调用方需要处理异常和回滚
                return await self._execute_upsert(
                    quantized_logic,
                    human_reasoning,
                    actor_id,
                    device_id,
                    batch_id,
                    session
                )
                
        except Exception as e:
            logger.error(f"规则持久化服务异常: {str(e)}", exc_info=True)
            raise Exception(f"规则持久化服务异常: {str(e)}")
    
    async def _execute_upsert(
        self,
        quantized_logic: Dict[str, Any],
        human_reasoning: str,
        actor_id: str,
        device_id: Optional[str],
        batch_id: Optional[str],
        session: AsyncSession
    ) -> Dict[str, Any]:
        """
        执行持久化操作（内部方法）
        """
        # 1. 写入数据库（PolicyRiskThreshold）
        policy_id = await self._upsert_to_database(
            quantized_logic,
            session
        )
        
        # 2. 写入RAG向量存储
        rag_document_id = await self._upsert_to_rag(
            quantized_logic,
            device_id,
            batch_id
        )
        
        # 3. 记录审计日志
        audit_id = await self._create_audit_log(
            actor_id,
            quantized_logic,
            human_reasoning,
            device_id,
            batch_id,
            session
        )
        
        logger.info(f"规则持久化成功: policy_id={policy_id}, audit_id={audit_id}")
        
        return {
            "success": True,
            "policy_id": policy_id,
            "audit_id": audit_id,
            "rag_document_id": rag_document_id,
            "message": "规则已成功持久化到数据库和RAG"
        }
    
    async def _upsert_to_database(
        self,
        quantized_logic: Dict[str, Any],
        session: AsyncSession
    ) -> int:
        """
        写入数据库
        
        Args:
            quantized_logic: 量化规则
            session: 数据库会话
        
        Returns:
            策略ID
        """
        try:
            metric_name = quantized_logic.get("metric_name")
            priority = quantized_logic.get("priority", 1)
            
            # 检查是否已存在相同指标和优先级的策略
            query = select(PolicyRiskThreshold).where(
                PolicyRiskThreshold.metric_name == metric_name,
                PolicyRiskThreshold.priority == priority
            ).with_for_update()
            
            result = await session.execute(query)
            existing_policy = result.scalar_one_or_none()
            
            if existing_policy:
                # 更新现有策略
                existing_policy.threshold_logic = quantized_logic
                existing_policy.updated_at = datetime.now()
                await session.flush()
                
                # 失效缓存
                strategy_cache.invalidate_strategy(existing_policy.strategy_id)
                strategy_cache.invalidate_metric(metric_name)
                strategy_cache.delete("all")
                
                logger.info(f"更新现有策略并失效缓存: strategy_id={existing_policy.strategy_id}, metric_name={metric_name}")
                return existing_policy.strategy_id
            else:
                # 创建新策略
                new_policy = PolicyRiskThreshold(
                    metric_name=metric_name,
                    threshold_logic=quantized_logic,
                    priority=priority
                )
                session.add(new_policy)
                await session.flush()
                
                # 失效缓存
                strategy_cache.invalidate_metric(metric_name)
                strategy_cache.delete("all")
                
                logger.info(f"创建新策略并失效缓存: strategy_id={new_policy.strategy_id}, metric_name={metric_name}")
                return new_policy.strategy_id
                
        except Exception as e:
            logger.error(f"数据库写入失败: {str(e)}")
            raise
    
    async def _upsert_to_rag(
        self,
        quantized_logic: Dict[str, Any],
        device_id: Optional[str],
        batch_id: Optional[str]
    ) -> str:
        """
        写入RAG向量存储
        
        Args:
            quantized_logic: 量化规则
            device_id: 设备ID
            batch_id: 批次ID
        
        Returns:
            文档ID
        
        Raises:
            Exception: RAG 写入失败时抛出异常
        """
        try:
            metadata = {}
            if device_id:
                metadata["device_id"] = device_id
            if batch_id:
                metadata["batch_id"] = batch_id
            
            document_id = await rag_vector_store.add_rule(quantized_logic, metadata)
            
            logger.info(f"RAG写入成功: document_id={document_id}, metric={quantized_logic.get('metric_name')}")
            
            return document_id
            
        except Exception as e:
            logger.error(f"RAG写入失败: {str(e)}", exc_info=True)
            # RAG 是核心功能，写入失败必须抛出异常
            raise Exception(f"RAG 向量存储写入失败: {str(e)}")
    
    async def _create_audit_log(
        self,
        actor_id: str,
        quantized_logic: Dict[str, Any],
        human_reasoning: str,
        device_id: Optional[str],
        batch_id: Optional[str],
        session: AsyncSession
    ) -> int:
        """
        创建审计日志
        
        Args:
            actor_id: 操作者ID
            quantized_logic: 量化规则
            human_reasoning: 农户原始理由
            device_id: 设备ID
            batch_id: 批次ID
            session: 数据库会话
        
        Returns:
            审计ID
        """
        try:
            # 构造预期变化
            expected_delta = {
                "metric_name": quantized_logic.get("metric_name"),
                "action": quantized_logic.get("action"),
                "value": quantized_logic.get("value"),
                "unit": quantized_logic.get("unit")
            }
            
            audit = AgentActionAudit(
                actor_id=actor_id,
                action_type="EXPERIENCE_QUANTIZATION",
                reasoning_context=human_reasoning,
                expected_delta=expected_delta,
                actual_delta=None  # 实际变化需要后续执行后更新
            )
            
            session.add(audit)
            await session.flush()
            
            logger.info(f"审计日志已创建: audit_id={audit.audit_id}")
            
            return audit.audit_id
            
        except Exception as e:
            logger.error(f"审计日志创建失败: {str(e)}")
            raise
    
    async def update_audit_actual_delta(
        self,
        audit_id: int,
        actual_delta: Dict[str, Any],
        session: Optional[AsyncSession] = None
    ) -> bool:
        """
        更新审计日志的实际变化
        
        Args:
            audit_id: 审计ID
            actual_delta: 实际变化
            session: 数据库会话
        
        Returns:
            是否成功
        
        Raises:
            Exception: 更新失败时抛出异常
        """
        try:
            if not session:
                async with AsyncSessionLocal() as session:
                    return await self._update_audit(audit_id, actual_delta, session)
            else:
                return await self._update_audit(audit_id, actual_delta, session)
                
        except Exception as e:
            logger.error(f"更新审计日志失败: audit_id={audit_id}, error={str(e)}", exc_info=True)
            raise Exception(f"审计日志更新失败: {str(e)}")
    
    async def _update_audit(
        self,
        audit_id: int,
        actual_delta: Dict[str, Any],
        session: AsyncSession
    ) -> bool:
        """
        内部方法：更新审计日志
        """
        query = select(AgentActionAudit).where(
            AgentActionAudit.audit_id == audit_id
        )
        
        result = await session.execute(query)
        audit = result.scalar_one_or_none()
        
        if audit:
            audit.actual_delta = actual_delta
            await session.flush()
            return True
        
        return False


# 全局单例
logic_upsert_service = LogicUpsertService()
