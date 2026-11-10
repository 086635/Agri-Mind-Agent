"""
RAG 向量存储工具

该模块实现经验规则的向量化存储和检索功能
使用 ChromaDB + BAAI/bge-m3 实现真实的向量存储
"""

import asyncio
import logging
import traceback
import hashlib
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RAGVectorStore:
    """
    RAG 向量存储管理器

    职责：
    1. 将经验规则向量化存储
    2. 提供相似度检索功能
    3. 管理向量数据库的生命周期

    特性：
    - 单例模式 + 延迟加载，避免阻塞应用启动
    - 异步操作，不阻塞 FastAPI 事件循环
    - 写入锁机制，确保 ChromaDB 写入串行安全
    - 完善的异常处理，确保 Agent 稳定性
    """

    # 单例实例
    _instance: Optional['RAGVectorStore'] = None
    _initialized: bool = False

    def __new__(cls, *args, **kwargs):
        """单例模式：确保全局只有一个实例"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(
        self,
        persist_directory: str = "./chroma_db",
        collection_name: str = "farm_experience_rules"
    ):
        """
        初始化向量存储（延迟加载）

        Args:
            persist_directory: 持久化目录
            collection_name: 集合名称
        """
        # 避免重复初始化
        if RAGVectorStore._initialized:
            return

        self.persist_directory = persist_directory
        self.collection_name = collection_name

        # 延迟加载的组件（首次使用时初始化）
        self._embeddings = None
        self._vectorstore = None
        self._client = None

        # 写入锁：确保对 ChromaDB 的写入是串行安全的，避免 SQLite 锁表
        self._write_lock = asyncio.Lock()

        # 标记已初始化
        RAGVectorStore._initialized = True

        logger.info(f"RAG 向量存储管理器已创建（延迟加载模式）: collection={collection_name}")

    async def _ensure_initialized(self) -> None:
        """
        确保向量存储已初始化（延迟加载）

        首次调用时加载 Embedding 模型和初始化 ChromaDB
        """
        if self._vectorstore is not None:
            return

        try:
            logger.info("开始初始化向量存储组件...")

            # 初始化 Embedding 模型
            await self._init_embeddings()

            # 初始化 ChromaDB
            await self._init_chromadb()

            logger.info("向量存储组件初始化完成")

        except Exception as e:
            logger.error(f"向量存储初始化失败: {str(e)}\n{traceback.format_exc()}")
            raise

    async def _init_embeddings(self) -> None:
        """
        初始化 Embedding 模型

        使用 BAAI/bge-m3 模型，配置 GPU 加速
        如果 GPU 不可用，自动回退到 CPU
        """
        try:
            from langchain_huggingface import HuggingFaceEmbeddings
            import torch

            logger.info("正在加载 Embedding 模型: BAAI/bge-m3 ...")

            # 检测设备
            device = 'cuda' if torch.cuda.is_available() else 'cpu'
            logger.info(f"使用设备: {device}")

            self._embeddings = HuggingFaceEmbeddings(
                model_name="BAAI/bge-m3",
                model_kwargs={'device': device},
                encode_kwargs={'normalize_embeddings': True}  # 归一化向量，提升检索效果
            )

            logger.info(f"Embedding 模型加载成功: BAAI/bge-m3 ({device.upper()} 加速)")

        except Exception as e:
            logger.error(f"Embedding 模型加载失败: {str(e)}\n{traceback.format_exc()}")
            raise RuntimeError(f"Embedding 模型初始化失败: {str(e)}")

    async def _init_chromadb(self) -> None:
        """
        初始化 ChromaDB 向量数据库

        配置持久化存储，确保数据不丢失
        """
        try:
            import chromadb
            from langchain_community.vectorstores import Chroma

            logger.info(f"正在初始化 ChromaDB，持久化目录: {self.persist_directory}")

            # 确保持久化目录存在
            Path(self.persist_directory).mkdir(parents=True, exist_ok=True)

            # 创建 ChromaDB 客户端（持久化模式）
            self._client = chromadb.PersistentClient(path=self.persist_directory)

            # 初始化向量存储
            self._vectorstore = Chroma(
                client=self._client,
                collection_name=self.collection_name,
                embedding_function=self._embeddings
            )

            logger.info(f"ChromaDB 初始化成功: collection={self.collection_name}")

        except Exception as e:
            logger.error(f"ChromaDB 初始化失败: {str(e)}\n{traceback.format_exc()}")
            raise RuntimeError(f"ChromaDB 初始化失败: {str(e)}")

    async def add_rule(
        self,
        quantized_logic: Dict[str, Any],
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        添加规则到向量存储

        Args:
            quantized_logic: 量化后的规则
            metadata: 元数据

        Returns:
            文档ID

        Raises:
            Exception: 当向量存储写入失败时抛出异常，确保数据一致性
        """
        try:
            # 确保已初始化
            await self._ensure_initialized()

            # 构造文档内容
            content = self._build_document_content(quantized_logic)

            # 构造元数据
            doc_metadata = {
                "metric_name": quantized_logic.get("metric_name"),
                "action": quantized_logic.get("action"),
                "source": quantized_logic.get("source", "human_experience"),
                "created_at": datetime.now().isoformat(),
                "reasoning_context": quantized_logic.get("reasoning", ""),
                **(metadata or {})
            }

            # 使用写入锁确保串行安全
            async with self._write_lock:
                # LangChain Chroma 的同步方法包装为异步
                ids = await asyncio.to_thread(
                    self._vectorstore.add_texts,
                    texts=[content],
                    metadatas=[doc_metadata]
                )

            # 验证文档已成功添加
            if not ids or not ids[0]:
                raise Exception("向量存储写入失败：返回ID为空")

            logger.info(f"规则已添加到向量存储: metric={quantized_logic.get('metric_name')}, doc_id={ids[0]}")

            return ids[0]

        except Exception as e:
            logger.error(f"添加规则到向量存储失败: {str(e)}\n{traceback.format_exc()}")
            raise Exception(f"RAG 存储异常: {str(e)}")

    async def add_rules_batch(
        self,
        rules: List[Dict[str, Any]],
        metadata_list: Optional[List[Dict[str, Any]]] = None
    ) -> List[str]:
        """
        批量添加规则

        Args:
            rules: 规则列表
            metadata_list: 元数据列表

        Returns:
            文档ID列表

        Raises:
            Exception: 当向量存储写入失败时抛出异常
        """
        try:
            # 确保已初始化
            await self._ensure_initialized()

            texts = []
            metadatas = []

            for i, rule in enumerate(rules):
                content = self._build_document_content(rule)

                doc_metadata = {
                    "metric_name": rule.get("metric_name"),
                    "action": rule.get("action"),
                    "source": rule.get("source", "human_experience"),
                    "created_at": datetime.now().isoformat(),
                    "reasoning_context": rule.get("reasoning", "")
                }

                if metadata_list and i < len(metadata_list):
                    doc_metadata.update(metadata_list[i])

                texts.append(content)
                metadatas.append(doc_metadata)

            # 使用写入锁确保串行安全
            async with self._write_lock:
                # 批量添加
                ids = await asyncio.to_thread(
                    self._vectorstore.add_texts,
                    texts=texts,
                    metadatas=metadatas
                )

            # 验证所有文档都已成功添加
            if len(ids) != len(texts):
                raise Exception(f"批量写入验证失败：期望 {len(texts)} 条，实际写入 {len(ids)} 条")

            logger.info(f"批量添加 {len(texts)} 条规则到向量存储成功，doc_ids={ids}")

            return ids

        except Exception as e:
            logger.error(f"批量添加规则失败: {str(e)}\n{traceback.format_exc()}")
            raise Exception(f"RAG 批量存储异常: {str(e)}")

    async def search_similar_rules(
        self,
        query: str,
        k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        检索相似规则

        Args:
            query: 查询文本
            k: 返回结果数量
            filter_dict: 过滤条件（ChromaDB where 子句）

        Returns:
            相似规则列表
        """
        try:
            # 确保已初始化
            await self._ensure_initialized()

            # 执行相似度检索（异步包装）
            results = await asyncio.to_thread(
                self._vectorstore.similarity_search_with_score,
                query,
                k=k,
                filter=filter_dict
            )

            # 格式化结果
            similar_rules = []
            for doc, score in results:
                similar_rules.append({
                    "content": doc.page_content,
                    "metadata": doc.metadata,
                    "similarity_score": float(score)  # 确保是 Python float 类型
                })

            logger.info(f"检索到 {len(similar_rules)} 条相似规则")

            return similar_rules

        except Exception as e:
            logger.error(f"相似规则检索失败: {str(e)}\n{traceback.format_exc()}")
            # 查询失败时返回空列表，确保 Agent 不会崩溃
            return []

    def _build_document_content(self, quantized_logic: Dict[str, Any]) -> str:
        """
        构造文档内容

        Args:
            quantized_logic: 量化规则

        Returns:
            文档内容字符串
        """
        metric_name = quantized_logic.get("metric_name", "")
        condition = quantized_logic.get("condition", "")
        action = quantized_logic.get("action", "")
        value = quantized_logic.get("value", "")
        unit = quantized_logic.get("unit", "")
        reasoning = quantized_logic.get("reasoning", "")

        content = f"""
农业控制规则：
指标: {metric_name}
条件: {condition}
动作: {action}
值: {value} {unit}
理由: {reasoning}

完整规则: 当 {condition} 时，对 {metric_name} 执行 {action}，调整值为 {value} {unit}。
农户经验: {reasoning}
"""

        return content.strip()

    async def delete_rule(self, document_id: str) -> bool:
        """
        删除规则

        Args:
            document_id: 文档ID

        Returns:
            是否成功
        """
        try:
            # 确保已初始化
            await self._ensure_initialized()

            # 使用写入锁确保串行安全
            async with self._write_lock:
                # ChromaDB 删除操作
                await asyncio.to_thread(
                    self._vectorstore.delete,
                    ids=[document_id]
                )

            logger.info(f"规则已删除: {document_id}")
            return True

        except Exception as e:
            logger.error(f"删除规则失败: {str(e)}\n{traceback.format_exc()}")
            return False

    async def get_collection_stats(self) -> Dict[str, Any]:
        """
        获取集合统计信息

        Returns:
            统计信息
        """
        try:
            # 确保已初始化
            await self._ensure_initialized()

            # 获取集合信息
            collection = self._client.get_collection(self.collection_name)
            count = collection.count()

            return {
                "collection_name": self.collection_name,
                "document_count": count,
                "persist_directory": self.persist_directory,
                "embedding_model": "BAAI/bge-m3",
                "status": "healthy"
            }

        except Exception as e:
            logger.error(f"获取统计信息失败: {str(e)}\n{traceback.format_exc()}")
            return {
                "collection_name": self.collection_name,
                "document_count": 0,
                "error": str(e),
                "status": "error"
            }

    async def add_rule_with_actions(
        self,
        quantized_logic: Dict[str, Any],
        actions: List[Dict[str, Any]],
        env_params: Optional[Dict[str, Any]] = None,
        metadata: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        添加规则到向量存储（支持操作组合 Embedding）

        Args:
            quantized_logic: 量化后的规则
            actions: 操作列表
            env_params: 环境参数区间
            metadata: 元数据

        Returns:
            文档ID

        Raises:
            Exception: 当向量存储写入失败时抛出异常
        """
        try:
            # 确保已初始化
            await self._ensure_initialized()

            # 生成操作组合哈希
            action_set_hash = self._generate_action_set_hash(actions, env_params)

            # 构造文档内容（包含操作组合）
            content = self._build_document_content_with_actions(
                quantized_logic,
                actions,
                env_params
            )

            # 构造元数据
            doc_metadata = {
                "metric_name": quantized_logic.get("metric_name"),
                "action": quantized_logic.get("action"),
                "source": quantized_logic.get("source", "human_experience"),
                "created_at": datetime.now().isoformat(),
                "reasoning_context": quantized_logic.get("reasoning", ""),
                "action_set_hash": action_set_hash,
                "version": 1,
                "parent_id": None,
                "is_active": True,
                **(metadata or {})
            }

            # 添加环境参数到元数据
            if env_params:
                if 'temp_range' in env_params:
                    doc_metadata['temp_range'] = env_params['temp_range']
                if 'humidity_range' in env_params:
                    doc_metadata['humidity_range'] = env_params['humidity_range']
                if 'weather_condition' in env_params:
                    doc_metadata['weather_condition'] = env_params['weather_condition']
                if 'light_intensity_range' in env_params:
                    doc_metadata['light_intensity_range'] = env_params['light_intensity_range']
                if 'soil_moisture_range' in env_params:
                    doc_metadata['soil_moisture_range'] = env_params['soil_moisture_range']

            # 使用写入锁确保串行安全
            async with self._write_lock:
                ids = await asyncio.to_thread(
                    self._vectorstore.add_texts,
                    texts=[content],
                    metadatas=[doc_metadata]
                )

            if not ids or not ids[0]:
                raise Exception("向量存储写入失败：返回ID为空")

            logger.info(
                f"规则已添加到向量存储（含操作组合）: "
                f"metric={quantized_logic.get('metric_name')}, "
                f"doc_id={ids[0]}, "
                f"action_set_hash={action_set_hash}"
            )

            return ids[0]

        except Exception as e:
            logger.error(f"添加规则到向量存储失败: {str(e)}\n{traceback.format_exc()}")
            raise Exception(f"RAG 存储异常: {str(e)}")

    def _generate_action_set_hash(
        self,
        actions: List[Dict[str, Any]],
        env_params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        生成操作组合的哈希指纹

        Args:
            actions: 操作列表
            env_params: 环境参数区间

        Returns:
            str: 128位哈希字符串
        """
        # 提取操作关键信息并排序
        sorted_actions = []
        for action in actions:
            action_key = {
                'action_type': action.get('action_type', ''),
                'target_device': action.get('target_device', ''),
                'value': action.get('value', ''),
                'unit': action.get('unit', '')
            }
            sorted_actions.append(action_key)

        # 按操作类型和目标设备排序
        sorted_actions.sort(key=lambda x: (x['action_type'], x['target_device']))

        # 构建哈希数据
        hash_data = {
            'actions': sorted_actions,
            'env_params': env_params or {}
        }

        hash_string = json.dumps(hash_data, sort_keys=True, ensure_ascii=False)

        # 生成 128 位 MD5 哈希
        hash_object = hashlib.md5(hash_string.encode('utf-8'))
        return hash_object.hexdigest()

    def _build_document_content_with_actions(
        self,
        quantized_logic: Dict[str, Any],
        actions: List[Dict[str, Any]],
        env_params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        构造文档内容（包含操作组合）

        Args:
            quantized_logic: 量化规则
            actions: 操作列表
            env_params: 环境参数区间

        Returns:
            文档内容字符串
        """
        metric_name = quantized_logic.get("metric_name", "")
        condition = quantized_logic.get("condition", "")
        action = quantized_logic.get("action", "")
        value = quantized_logic.get("value", "")
        unit = quantized_logic.get("unit", "")
        reasoning = quantized_logic.get("reasoning", "")

        # 构建操作序列描述
        actions_desc = "\n".join([
            f"  - {act.get('action_type', '')}: {act.get('target_device', '')} = {act.get('value', '')} {act.get('unit', '')}"
            for act in actions
        ])

        # 构建环境参数描述
        env_desc = ""
        if env_params:
            env_parts = []
            if 'temp_range' in env_params:
                env_parts.append(f"温度: {env_params['temp_range']['min']}-{env_params['temp_range']['max']}°C")
            if 'humidity_range' in env_params:
                env_parts.append(f"湿度: {env_params['humidity_range']['min']}-{env_params['humidity_range']['max']}%")
            if 'weather_condition' in env_params:
                env_parts.append(f"天气: {', '.join(env_params['weather_condition'])}")
            if env_parts:
                env_desc = "\n环境参数:\n  " + ", ".join(env_parts)

        content = f"""
农业控制规则：
指标: {metric_name}
条件: {condition}
动作: {action}
值: {value} {unit}
理由: {reasoning}

操作序列:
{actions_desc}
{env_desc}

完整规则: 当 {condition} 时，对 {metric_name} 执行 {action}，调整值为 {value} {unit}。
农户经验: {reasoning}
"""

        return content.strip()

    async def search_by_action_pattern(
        self,
        actions: List[Dict[str, Any]],
        env_params: Optional[Dict[str, Any]] = None,
        k: int = 5,
        similarity_threshold: float = 0.3
    ) -> List[Dict[str, Any]]:
        """
        根据操作组合检索相似行为模式

        Args:
            actions: 操作列表
            env_params: 环境参数区间
            k: 返回结果数量
            similarity_threshold: 相似度阈值

        Returns:
            相似规则列表，包含相似度分数和匹配逻辑
        """
        try:
            # 确保已初始化
            await self._ensure_initialized()

            # 构建查询文本
            query_text = self._build_action_pattern_query(actions, env_params)

            # 执行相似度检索
            results = await asyncio.to_thread(
                self._vectorstore.similarity_search_with_score,
                query_text,
                k=k
            )

            # 格式化结果并过滤低相似度
            similar_patterns = []
            for doc, score in results:
                similarity = float(score)
                if similarity >= similarity_threshold:
                    similar_patterns.append({
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                        "similarity_score": similarity,
                        "action_set_hash": doc.metadata.get("action_set_hash"),
                        "match_level": self._get_similarity_level(similarity)
                    })

            logger.info(
                f"检索到 {len(similar_patterns)} 条相似操作模式 "
                f"(阈值={similarity_threshold})"
            )

            return similar_patterns

        except Exception as e:
            logger.error(f"操作模式检索失败: {str(e)}\n{traceback.format_exc()}")
            return []

    def _build_action_pattern_query(
        self,
        actions: List[Dict[str, Any]],
        env_params: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        构建操作模式查询文本

        Args:
            actions: 操作列表
            env_params: 环境参数区间

        Returns:
            查询文本
        """
        # 构建操作序列描述
        actions_desc = " ".join([
            f"{act.get('action_type', '')} {act.get('target_device', '')} {act.get('value', '')} {act.get('unit', '')}"
            for act in actions
        ])

        # 构建环境参数描述
        env_desc = ""
        if env_params:
            env_parts = []
            if 'temp_range' in env_params:
                env_parts.append(f"温度{env_params['temp_range']['min']}-{env_params['temp_range']['max']}°C")
            if 'humidity_range' in env_params:
                env_parts.append(f"湿度{env_params['humidity_range']['min']}-{env_params['humidity_range']['max']}%")
            if 'weather_condition' in env_params:
                env_parts.append(f"天气{', '.join(env_params['weather_condition'])}")
            if env_parts:
                env_desc = " " + " ".join(env_parts)

        return f"{actions_desc}{env_desc}"

    def _get_similarity_level(self, similarity_score: float) -> str:
        """
        根据相似度分数判断相似度级别

        Args:
            similarity_score: 相似度分数

        Returns:
            str: 相似度级别
        """
        if similarity_score < 0.3:
            return 'new'
        elif similarity_score < 0.7:
            return 'needs_confirmation'
        elif similarity_score >= 0.95:
            return 'duplicate'
        else:
            return 'similar'

    async def update_rule_version(
        self,
        logic_id: str,
        new_logic: Dict[str, Any],
        evolution_reason: Optional[str] = None,
        user_feedback: Optional[Dict[str, Any]] = None
    ) -> str:
        """
        更新规则版本

        执行 Soft Delete（旧规则 is_active=False）
        创建新版本规则（version+1, parent_id 指向旧规则）

        Args:
            logic_id: 逻辑ID
            new_logic: 新的逻辑内容
            evolution_reason: 版本演进原因（例如："树长大了"、"天气更热了"、"农户经验调整"）
            user_feedback: 用户反馈详情

        Returns:
            新版本ID
        """
        try:
            # 确保已初始化
            await self._ensure_initialized()

            # 获取旧规则
            old_rule = await self._get_rule_by_id(logic_id)
            if not old_rule:
                raise Exception(f"未找到逻辑ID: {logic_id}")

            old_metadata = old_rule['metadata']
            old_version = old_metadata.get('version', 1)

            # Soft Delete 旧规则
            await self._soft_delete_rule(logic_id)

            # 创建新版本规则
            new_metadata = {
                **old_metadata,
                "version": old_version + 1,
                "parent_id": logic_id,
                "is_active": True,
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "evolution_reason": evolution_reason,
                "user_feedback": user_feedback
            }

            # 更新逻辑内容
            new_content = self._build_document_content(new_logic)

            # 使用写入锁确保串行安全
            async with self._write_lock:
                ids = await asyncio.to_thread(
                    self._vectorstore.add_texts,
                    texts=[new_content],
                    metadatas=[new_metadata]
                )

            if not ids or not ids[0]:
                raise Exception("新版本创建失败：返回ID为空")

            logger.info(
                f"规则版本已更新: old_id={logic_id}, "
                f"new_id={ids[0]}, "
                f"version={old_version}->{old_version + 1}, "
                f"evolution_reason={evolution_reason}"
            )

            return ids[0]

        except Exception as e:
            logger.error(f"更新规则版本失败: {str(e)}\n{traceback.format_exc()}")
            raise Exception(f"版本更新异常: {str(e)}")

    async def _get_rule_by_id(self, logic_id: str) -> Optional[Dict[str, Any]]:
        """
        根据ID获取规则

        Args:
            logic_id: 逻辑ID

        Returns:
            规则详情
        """
        try:
            # 确保已初始化
            await self._ensure_initialized()

            # 从 ChromaDB 获取文档
            collection = self._client.get_collection(self.collection_name)
            result = collection.get(ids=[logic_id], include=['metadatas', 'documents'])

            if not result['ids']:
                return None

            return {
                "id": result['ids'][0],
                "content": result['documents'][0] if result['documents'] else "",
                "metadata": result['metadatas'][0] if result['metadatas'] else {}
            }

        except Exception as e:
            logger.error(f"获取规则失败: {str(e)}\n{traceback.format_exc()}")
            return None

    async def _soft_delete_rule(self, logic_id: str) -> bool:
        """
        软删除规则（标记 is_active=False）

        Args:
            logic_id: 逻辑ID

        Returns:
            是否成功
        """
        try:
            # 确保已初始化
            await self._ensure_initialized()

            # 获取旧规则
            old_rule = await self._get_rule_by_id(logic_id)
            if not old_rule:
                logger.warning(f"软删除失败：未找到规则 {logic_id}")
                return False

            # 更新元数据
            updated_metadata = {
                **old_rule['metadata'],
                "is_active": False,
                "updated_at": datetime.now().isoformat()
            }

            # 使用写入锁确保串行安全
            async with self._write_lock:
                # ChromaDB 更新操作
                collection = self._client.get_collection(self.collection_name)
                await asyncio.to_thread(
                    collection.update,
                    ids=[logic_id],
                    metadatas=[updated_metadata],
                    documents=[old_rule['content']]
                )

            logger.info(f"规则已软删除: {logic_id}")
            return True

        except Exception as e:
            logger.error(f"软删除规则失败: {str(e)}\n{traceback.format_exc()}")
            return False

    async def get_logic_history(self, logic_id: str) -> Dict[str, Any]:
        """
        获取指定逻辑的所有版本（包含演进原因）

        Args:
            logic_id: 逻辑ID

        Returns:
            包含版本历史的字典，包括演进原因链条
        """
        try:
            # 确保已初始化
            await self._ensure_initialized()

            # 获取当前规则
            current_rule = await self._get_rule_by_id(logic_id)
            if not current_rule:
                return {
                    "logic_id": logic_id,
                    "history": [],
                    "total_versions": 0,
                    "error": "未找到逻辑"
                }

            # 追溯版本链条
            history = [current_rule]
            parent_id = current_rule['metadata'].get('parent_id')

            # 向上追溯父版本
            while parent_id:
                parent_rule = await self._get_rule_by_id(parent_id)
                if parent_rule:
                    history.append(parent_rule)
                    parent_id = parent_rule['metadata'].get('parent_id')
                else:
                    break

            # 按版本号排序
            history.sort(key=lambda x: x['metadata'].get('version', 1))

            # 格式化历史记录（包含演进原因）
            formatted_history = [
                {
                    "logic_id": rule['id'],
                    "version": rule['metadata'].get('version', 1),
                    "parent_id": rule['metadata'].get('parent_id'),
                    "is_active": rule['metadata'].get('is_active', True),
                    "created_by": rule['metadata'].get('created_by', 'unknown'),
                    "created_at": rule['metadata'].get('created_at'),
                    "evolution_reason": rule['metadata'].get('evolution_reason'),
                    "user_feedback": rule['metadata'].get('user_feedback'),
                    "summary": rule['content'][:100] + "..." if len(rule['content']) > 100 else rule['content']
                }
                for rule in history
            ]

            # 构建演进原因链条
            evolution_chain = []
            for i, entry in enumerate(formatted_history):
                if entry.get('evolution_reason'):
                    evolution_chain.append({
                        "from_version": entry['version'] - 1 if entry['version'] > 1 else None,
                        "to_version": entry['version'],
                        "reason": entry['evolution_reason'],
                        "timestamp": entry['created_at']
                    })

            return {
                "current_logic_id": logic_id,
                "history": formatted_history,
                "total_versions": len(formatted_history),
                "evolution_chain": evolution_chain
            }

        except Exception as e:
            logger.error(f"获取逻辑历史失败: {str(e)}\n{traceback.format_exc()}")
            return {
                "logic_id": logic_id,
                "history": [],
                "total_versions": 0,
                "evolution_chain": [],
                "error": str(e)
            }

    async def get_evolution_history(self, logic_id: str) -> Dict[str, Any]:
        """
        获取演进历史（专门用于查询版本演进链条和原因）

        Args:
            logic_id: 逻辑ID

        Returns:
            演进历史字典，包含：
            - current_version: 当前版本号
            - evolution_timeline: 演进时间线（按时间顺序）
            - total_evolutions: 演进次数
            - latest_reason: 最新演进原因
        """
        try:
            # 获取完整历史
            history_result = await self.get_logic_history(logic_id)
            
            if history_result.get('error'):
                return {
                    "logic_id": logic_id,
                    "current_version": None,
                    "evolution_timeline": [],
                    "total_evolutions": 0,
                    "error": history_result['error']
                }

            history = history_result.get('history', [])
            evolution_chain = history_result.get('evolution_chain', [])

            # 构建演进时间线
            evolution_timeline = []
            for entry in evolution_chain:
                evolution_timeline.append({
                    "version": entry['to_version'],
                    "reason": entry['reason'],
                    "timestamp": entry['timestamp'],
                    "from_version": entry['from_version']
                })

            # 获取最新版本信息
            latest_version = max(history, key=lambda x: x['version']) if history else None

            return {
                "logic_id": logic_id,
                "current_version": latest_version['version'] if latest_version else None,
                "evolution_timeline": evolution_timeline,
                "total_evolutions": len(evolution_timeline),
                "latest_reason": latest_version.get('evolution_reason') if latest_version else None,
                "is_active": latest_version.get('is_active', True) if latest_version else None
            }

        except Exception as e:
            logger.error(f"获取演进历史失败: {str(e)}\n{traceback.format_exc()}")
            return {
                "logic_id": logic_id,
                "current_version": None,
                "evolution_timeline": [],
                "total_evolutions": 0,
                "error": str(e)
            }

    async def deprecate_old_versions(self, logic_id: str) -> Dict[str, Any]:
        """
        批量软删除指定逻辑的所有旧版本，保留最新版本

        Args:
            logic_id: 逻辑ID

        Returns:
            操作结果
        """
        try:
            # 确保已初始化
            await self._ensure_initialized()

            # 获取版本历史
            history_result = await self.get_logic_history(logic_id)
            history = history_result.get('history', [])

            if not history:
                return {
                    "success": False,
                    "message": "未找到版本历史",
                    "deprecated_count": 0
                }

            # 找到最新版本
            latest_version = max(history, key=lambda x: x['version'])
            latest_logic_id = latest_version['logic_id']

            # 软删除所有旧版本
            deprecated_count = 0
            for version_info in history:
                if version_info['logic_id'] != latest_logic_id and version_info['is_active']:
                    success = await self._soft_delete_rule(version_info['logic_id'])
                    if success:
                        deprecated_count += 1

            logger.info(
                f"已废弃旧版本: logic_id={logic_id}, "
                f"deprecated_count={deprecated_count}, "
                f"latest_version={latest_version['version']}"
            )

            return {
                "success": True,
                "message": f"已废弃 {deprecated_count} 个旧版本",
                "deprecated_count": deprecated_count,
                "latest_version": latest_version['version'],
                "latest_logic_id": latest_logic_id
            }

        except Exception as e:
            logger.error(f"废弃旧版本失败: {str(e)}\n{traceback.format_exc()}")
            return {
                "success": False,
                "message": str(e),
                "deprecated_count": 0
            }

    async def search_active_rules(
        self,
        query: str,
        k: int = 5,
        filter_dict: Optional[Dict[str, Any]] = None
    ) -> List[Dict[str, Any]]:
        """
        检索活跃规则（只返回 is_active=True 的规则）

        Args:
            query: 查询文本
            k: 返回结果数量
            filter_dict: 过滤条件

        Returns:
            活跃规则列表
        """
        try:
            # 确保已初始化
            await self._ensure_initialized()

            # 添加 is_active 过滤条件
            active_filter = {"is_active": True}
            if filter_dict:
                # 合并过滤条件（ChromaDB where 子句）
                active_filter = {"$and": [active_filter, filter_dict]}

            # 执行相似度检索
            results = await asyncio.to_thread(
                self._vectorstore.similarity_search_with_score,
                query,
                k=k,
                filter=active_filter
            )

            # 格式化结果
            active_rules = []
            for doc, score in results:
                # 再次确认 is_active 状态
                if doc.metadata.get('is_active', True):
                    active_rules.append({
                        "content": doc.page_content,
                        "metadata": doc.metadata,
                        "similarity_score": float(score)
                    })

            logger.info(f"检索到 {len(active_rules)} 条活跃规则")

            return active_rules

        except Exception as e:
            logger.error(f"活跃规则检索失败: {str(e)}\n{traceback.format_exc()}")
            return []


# 全局单例
rag_vector_store = RAGVectorStore()
