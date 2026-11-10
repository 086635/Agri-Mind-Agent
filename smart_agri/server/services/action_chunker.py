"""
操作序列意图指纹服务

该模块实现操作序列的时间窗口聚合和意图指纹生成
支持环境稳态判定和操作组合去重
"""

import asyncio
import hashlib
import json
import logging
import os
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime, timedelta
from collections import defaultdict

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ActionChunker:
    """
    操作序列意图指纹管理器

    职责：
    1. 时间窗口聚合操作序列
    2. 环境稳态判定
    3. 生成操作组合哈希指纹
    4. 支持相似度阈值配置

    特性：
    - 时间窗口可配置（通过环境变量 ACTION_CHUNK_WINDOW_MINUTES）
    - 支持环境参数区间哈希化
    - 支持并发安全（使用 asyncio.Lock）
    """

    # 相似度阈值配置
    SIMILARITY_THRESHOLD_LOW = 0.3  # 新组合
    SIMILARITY_THRESHOLD_MEDIUM = 0.7  # 需要确认
    SIMILARITY_THRESHOLD_HIGH = 0.95  # 去重

    def __init__(
        self,
        chunk_window_minutes: Optional[float] = None,
        env_stability_threshold_minutes: Optional[float] = None
    ):
        """
        初始化操作序列管理器

        Args:
            chunk_window_minutes: 时间窗口（分钟），默认从环境变量读取或 20 分钟
            env_stability_threshold_minutes: 环境稳态判定阈值（分钟），默认从环境变量读取或 15 分钟
        """
        # 从环境变量读取配置，或使用默认值
        self.chunk_window_minutes = chunk_window_minutes or float(
            os.getenv('ACTION_CHUNK_WINDOW_MINUTES', '20')
        )
        self.env_stability_threshold_minutes = env_stability_threshold_minutes or float(
            os.getenv('ENV_STABILITY_THRESHOLD_MINUTES', '15')
        )

        # Bucketing 配置：从环境变量读取桶大小
        self.temp_bucket_size = float(os.getenv('TEMP_BUCKET_SIZE', '2'))
        self.humidity_bucket_size = float(os.getenv('HUMIDITY_BUCKET_SIZE', '10'))
        self.light_bucket_size = float(os.getenv('LIGHT_BUCKET_SIZE', '500'))
        self.soil_moisture_bucket_size = float(os.getenv('SOIL_MOISTURE_BUCKET_SIZE', '10'))

        # 操作缓冲区：按 actor_id 分组
        self._action_buffer: Dict[str, List[Dict[str, Any]]] = defaultdict(list)

        # 环境快照缓冲区：按 actor_id 分组
        self._env_snapshot_buffer: Dict[str, Dict[str, Any]] = {}

        # 并发锁
        self._lock = asyncio.Lock()

        logger.info(
            f"ActionChunker 初始化完成: "
            f"chunk_window={self.chunk_window_minutes}min, "
            f"env_stability_threshold={self.env_stability_threshold_minutes}min, "
            f"bucket_sizes=[temp={self.temp_bucket_size}°C, humidity={self.humidity_bucket_size}%, "
            f"light={self.light_bucket_size}lux, soil={self.soil_moisture_bucket_size}%]"
        )

    async def add_action(
        self,
        actor_id: str,
        action: Dict[str, Any],
        env_snapshot: Optional[Dict[str, Any]] = None
    ) -> Optional[str]:
        """
        添加操作到缓冲区

        Args:
            actor_id: 操作者ID
            action: 操作详情，包含 action_type, target_device, value 等
            env_snapshot: 环境快照，包含 temp, humidity, weather 等

        Returns:
            Optional[str]: 如果触发 ActionSet 生成，返回 action_set_hash；否则返回 None
        """
        async with self._lock:
            # 添加时间戳
            action['timestamp'] = datetime.now().isoformat()
            action['actor_id'] = actor_id

            # 更新环境快照
            if env_snapshot:
                self._env_snapshot_buffer[actor_id] = env_snapshot

            # 添加到缓冲区
            self._action_buffer[actor_id].append(action)

            logger.info(f"操作已添加到缓冲区: actor={actor_id}, action_type={action.get('action_type')}")

            # 检查是否需要生成 ActionSet
            action_set_hash = await self._check_and_generate_action_set(actor_id)

            return action_set_hash

    async def _check_and_generate_action_set(self, actor_id: str) -> Optional[str]:
        """
        检查并生成 ActionSet

        Args:
            actor_id: 操作者ID

        Returns:
            Optional[str]: 如果生成 ActionSet，返回 action_set_hash；否则返回 None
        """
        actions = self._action_buffer.get(actor_id, [])
        if not actions:
            return None

        # 检查时间窗口
        first_action_time = datetime.fromisoformat(actions[0]['timestamp'])
        last_action_time = datetime.fromisoformat(actions[-1]['timestamp'])
        time_diff = (last_action_time - first_action_time).total_seconds() / 60

        # 如果超过时间窗口，生成 ActionSet
        if time_diff >= self.chunk_window_minutes:
            action_set_hash = await self.generate_action_set_hash(actor_id)
            return action_set_hash

        return None

    async def generate_action_set_hash(
        self,
        actor_id: str,
        include_env_params: bool = True
    ) -> str:
        """
        生成操作组合的哈希指纹

        将操作组合按键值对排序后字符串化，并将核心环境参数区间一并哈希化

        Args:
            actor_id: 操作者ID
            include_env_params: 是否包含环境参数

        Returns:
            str: 128位哈希字符串
        """
        async with self._lock:
            actions = self._action_buffer.get(actor_id, [])
            env_snapshot = self._env_snapshot_buffer.get(actor_id, {})

            if not actions:
                logger.warning(f"操作缓冲区为空，无法生成哈希: actor={actor_id}")
                return ""

            # 1. 提取操作关键信息并排序
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

            # 2. 提取环境参数并应用 Bucketing
            env_params = {}
            if include_env_params and env_snapshot:
                # 使用 Bucketing 后的参数
                bucketed_env = self.bucketize_env_params(env_snapshot)

                # 温度桶
                if 'temp_bucket' in bucketed_env:
                    env_params['temp_bucket'] = bucketed_env['temp_bucket']

                # 湿度桶
                if 'humidity_bucket' in bucketed_env:
                    env_params['humidity_bucket'] = bucketed_env['humidity_bucket']

                # 天气条件（保持原值）
                if 'weather' in bucketed_env:
                    env_params['weather'] = bucketed_env['weather']

                # 光照强度桶
                if 'light_bucket' in bucketed_env:
                    env_params['light_bucket'] = bucketed_env['light_bucket']

                # 土壤湿度桶
                if 'soil_moisture_bucket' in bucketed_env:
                    env_params['soil_moisture_bucket'] = bucketed_env['soil_moisture_bucket']

            # 3. 构建哈希字符串
            hash_data = {
                'actions': sorted_actions,
                'env_params': env_params
            }

            hash_string = json.dumps(hash_data, sort_keys=True, ensure_ascii=False)

            # 4. 生成 128 位 MD5 哈希
            hash_object = hashlib.md5(hash_string.encode('utf-8'))
            action_set_hash = hash_object.hexdigest()

            logger.info(
                f"生成 ActionSet 哈希: actor={actor_id}, "
                f"hash={action_set_hash}, "
                f"actions_count={len(sorted_actions)}, "
                f"bucketed_env={env_params}"
            )

            # 5. 清空缓冲区
            self._action_buffer[actor_id] = []
            # 保留环境快照用于后续操作

            return action_set_hash

    async def is_env_stable(
        self,
        actor_id: str,
        current_env: Dict[str, Any]
    ) -> bool:
        """
        判断环境是否处于稳态

        连续操作间隔不超过阈值都算作同一个 ActionSet

        Args:
            actor_id: 操作者ID
            current_env: 当前环境快照

        Returns:
            bool: 环境是否稳定
        """
        async with self._lock:
            last_env = self._env_snapshot_buffer.get(actor_id)

            if not last_env:
                return True

            # 计算环境参数变化
            temp_diff = abs(current_env.get('temp', 0) - last_env.get('temp', 0))
            humidity_diff = abs(current_env.get('humidity', 0) - last_env.get('humidity', 0))

            # 判断是否在稳态范围内
            is_stable = (
                temp_diff <= 3.0 and  # 温度变化 ≤ 3°C
                humidity_diff <= 15.0  # 湿度变化 ≤ 15%
            )

            logger.debug(
                f"环境稳态判定: actor={actor_id}, "
                f"is_stable={is_stable}, "
                f"temp_diff={temp_diff:.2f}°C, "
                f"humidity_diff={humidity_diff:.2f}%"
            )

            return is_stable

    async def get_action_buffer(
        self,
        actor_id: str
    ) -> List[Dict[str, Any]]:
        """
        获取操作缓冲区内容

        Args:
            actor_id: 操作者ID

        Returns:
            List[Dict[str, Any]]: 操作列表
        """
        async with self._lock:
            return self._action_buffer.get(actor_id, []).copy()

    async def clear_action_buffer(self, actor_id: str) -> None:
        """
        清空操作缓冲区

        Args:
            actor_id: 操作者ID
        """
        async with self._lock:
            self._action_buffer[actor_id] = []
            logger.info(f"操作缓冲区已清空: actor={actor_id}")

    async def get_env_snapshot(self, actor_id: str) -> Optional[Dict[str, Any]]:
        """
        获取环境快照

        Args:
            actor_id: 操作者ID

        Returns:
            Optional[Dict[str, Any]]: 环境快照
        """
        async with self._lock:
            return self._env_snapshot_buffer.get(actor_id)

    def get_similarity_level(self, similarity_score: float) -> str:
        """
        根据相似度分数判断相似度级别

        Args:
            similarity_score: 相似度分数 (0.0 - 1.0)

        Returns:
            str: 相似度级别 ('new', 'needs_confirmation', 'duplicate')
        """
        if similarity_score < self.SIMILARITY_THRESHOLD_LOW:
            return 'new'
        elif similarity_score < self.SIMILARITY_THRESHOLD_MEDIUM:
            return 'needs_confirmation'
        elif similarity_score >= self.SIMILARITY_THRESHOLD_HIGH:
            return 'duplicate'
        else:
            return 'similar'

    def bucketize_env_params(self, env_snapshot: Dict[str, Any]) -> Dict[str, Any]:
        """
        对环境参数进行 Bucketing（区间归一化）

        将连续的环境参数值映射到离散的桶中，提高意图指纹的鲁棒性。
        例如：25.3°C 和 25.7°C 都映射到 24°C 桶（2°C 一档）

        Args:
            env_snapshot: 环境快照，包含 temp, humidity, weather, light_intensity, soil_moisture 等

        Returns:
            Dict[str, Any]: Bucketing 后的环境参数
                {
                    'temp_bucket': 24,        # 温度桶下界（°C）
                    'humidity_bucket': 50,    # 湿度桶下界（%）
                    'weather': 'sunny',       # 天气（保持原值）
                    'light_bucket': 1000,     # 光照强度桶下界（lux）
                    'soil_moisture_bucket': 40  # 土壤湿度桶下界（%）
                }
        """
        bucketed = {}

        # 温度 Bucketing：2°C 一档
        if 'temp' in env_snapshot:
            temp = env_snapshot['temp']
            bucketed['temp_bucket'] = int(temp // self.temp_bucket_size * self.temp_bucket_size)

        # 湿度 Bucketing：10% 一档
        if 'humidity' in env_snapshot:
            humidity = env_snapshot['humidity']
            bucketed['humidity_bucket'] = int(humidity // self.humidity_bucket_size * self.humidity_bucket_size)

        # 天气：保持原值（离散值）
        if 'weather' in env_snapshot:
            bucketed['weather'] = env_snapshot['weather']

        # 光照强度 Bucketing：500 lux 一档
        if 'light_intensity' in env_snapshot:
            light = env_snapshot['light_intensity']
            bucketed['light_bucket'] = int(light // self.light_bucket_size * self.light_bucket_size)

        # 土壤湿度 Bucketing：10% 一档
        if 'soil_moisture' in env_snapshot:
            soil_moisture = env_snapshot['soil_moisture']
            bucketed['soil_moisture_bucket'] = int(
                soil_moisture // self.soil_moisture_bucket_size * self.soil_moisture_bucket_size
            )

        logger.debug(
            f"环境参数 Bucketing: 原始={env_snapshot} -> 桶值={bucketed}"
        )

        return bucketed

    async def should_deduplicate(
        self,
        similarity_score: float
    ) -> bool:
        """
        判断是否应该去重

        Args:
            similarity_score: 相似度分数

        Returns:
            bool: 是否应该去重
        """
        return similarity_score >= self.SIMILARITY_THRESHOLD_HIGH

    async def needs_user_confirmation(
        self,
        similarity_score: float
    ) -> bool:
        """
        判断是否需要用户确认

        Args:
            similarity_score: 相似度分数

        Returns:
            bool: 是否需要用户确认
        """
        return (
            self.SIMILARITY_THRESHOLD_LOW <= similarity_score < self.SIMILARITY_THRESHOLD_MEDIUM
        )

    async def extract_env_params_from_actions(
        self,
        actions: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """
        从操作序列中提取环境参数区间

        Args:
            actions: 操作列表

        Returns:
            Dict[str, Any]: 环境参数区间
        """
        env_params = {}

        # 提取所有环境参数
        temps = []
        humidities = []
        weathers = set()
        light_intensities = []
        soil_moistures = []

        for action in actions:
            env = action.get('env_snapshot', {})
            if 'temp' in env:
                temps.append(env['temp'])
            if 'humidity' in env:
                humidities.append(env['humidity'])
            if 'weather' in env:
                weathers.add(env['weather'])
            if 'light_intensity' in env:
                light_intensities.append(env['light_intensity'])
            if 'soil_moisture' in env:
                soil_moistures.append(env['soil_moisture'])

        # 构建区间
        if temps:
            env_params['temp_range'] = {
                'min': min(temps),
                'max': max(temps)
            }

        if humidities:
            env_params['humidity_range'] = {
                'min': min(humidities),
                'max': max(humidities)
            }

        if weathers:
            env_params['weather_condition'] = list(weathers)

        if light_intensities:
            env_params['light_intensity_range'] = {
                'min': min(light_intensities),
                'max': max(light_intensities)
            }

        if soil_moistures:
            env_params['soil_moisture_range'] = {
                'min': min(soil_moistures),
                'max': max(soil_moistures)
            }

        return env_params

    async def get_stats(self) -> Dict[str, Any]:
        """
        获取统计信息

        Returns:
            Dict[str, Any]: 统计信息
        """
        async with self._lock:
            total_actors = len(self._action_buffer)
            total_actions = sum(len(actions) for actions in self._action_buffer.values())

            return {
                'chunk_window_minutes': self.chunk_window_minutes,
                'env_stability_threshold_minutes': self.env_stability_threshold_minutes,
                'bucket_sizes': {
                    'temp': self.temp_bucket_size,
                    'humidity': self.humidity_bucket_size,
                    'light': self.light_bucket_size,
                    'soil_moisture': self.soil_moisture_bucket_size
                },
                'similarity_thresholds': {
                    'low': self.SIMILARITY_THRESHOLD_LOW,
                    'medium': self.SIMILARITY_THRESHOLD_MEDIUM,
                    'high': self.SIMILARITY_THRESHOLD_HIGH
                },
                'buffer_stats': {
                    'total_actors': total_actors,
                    'total_actions': total_actions,
                    'actors_with_env_snapshot': len(self._env_snapshot_buffer)
                }
            }


# 全局单例
action_chunker = ActionChunker()
