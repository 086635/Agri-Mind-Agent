"""
策略缓存管理器

该模块实现策略查询的缓存机制，优化性能，减少数据库压力
支持异步操作、自动过期、缓存失效等功能
"""

import json
import logging
import asyncio
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from collections import OrderedDict
import threading

logger = logging.getLogger(__name__)


class StrategyCacheManager:
    """
    策略缓存管理器
    
    功能：
    1. 内存缓存策略数据
    2. 支持TTL过期机制（默认5分钟）
    3. 支持LRU淘汰策略
    4. 线程安全
    5. 缓存监控和统计
    
    缓存键设计：
    - 单个策略：strategy:{strategy_id}
    - 指标策略列表：metric:{metric_name}
    - 所有策略列表：all_strategies
    
    缓存值：
    - JSON字符串格式的策略规则
    """
    
    def __init__(self, max_size: int = 1000, default_ttl: int = 300):
        """
        初始化缓存管理器
        
        Args:
            max_size: 最大缓存条目数
            default_ttl: 默认过期时间（秒），默认5分钟
        """
        self.max_size = max_size
        self.default_ttl = default_ttl
        
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._lock = threading.RLock()
        
        self._stats = {
            "hits": 0,
            "misses": 0,
            "evictions": 0,
            "invalidations": 0,
            "total_requests": 0
        }
        
        logger.info(f"策略缓存管理器初始化完成: max_size={max_size}, default_ttl={default_ttl}s")
    
    def _generate_key(self, key_type: str, identifier: str = None) -> str:
        """
        生成缓存键
        
        Args:
            key_type: 键类型（strategy, metric, all）
            identifier: 标识符
        
        Returns:
            缓存键
        """
        if key_type == "strategy":
            return f"strategy:{identifier}"
        elif key_type == "metric":
            return f"metric:{identifier}"
        elif key_type == "all":
            return "all_strategies"
        else:
            return f"unknown:{identifier}"
    
    def _is_expired(self, cache_entry: Dict[str, Any]) -> bool:
        """
        检查缓存条目是否过期
        
        Args:
            cache_entry: 缓存条目
        
        Returns:
            是否过期
        """
        expires_at = cache_entry.get("expires_at")
        if not expires_at:
            return True
        
        return datetime.now() > expires_at
    
    def get(self, key_type: str, identifier: str = None) -> Optional[Any]:
        """
        从缓存获取数据
        
        Args:
            key_type: 键类型
            identifier: 标识符
        
        Returns:
            缓存数据，如果不存在或过期则返回None
        """
        with self._lock:
            self._stats["total_requests"] += 1
            
            key = self._generate_key(key_type, identifier)
            
            if key not in self._cache:
                self._stats["misses"] += 1
                logger.debug(f"缓存未命中: {key}")
                return None
            
            cache_entry = self._cache[key]
            
            if self._is_expired(cache_entry):
                del self._cache[key]
                self._stats["misses"] += 1
                logger.debug(f"缓存已过期: {key}")
                return None
            
            self._cache.move_to_end(key)
            
            self._stats["hits"] += 1
            hit_rate = self._stats["hits"] / self._stats["total_requests"] * 100
            logger.debug(f"缓存命中: {key}, 当前命中率: {hit_rate:.2f}%")
            
            return cache_entry["data"]
    
    def set(
        self,
        key_type: str,
        data: Any,
        identifier: str = None,
        ttl: int = None
    ) -> bool:
        """
        设置缓存数据
        
        Args:
            key_type: 键类型
            data: 缓存数据
            identifier: 标识符
            ttl: 过期时间（秒），不指定则使用默认值
        
        Returns:
            是否成功
        """
        with self._lock:
            key = self._generate_key(key_type, identifier)
            
            if len(self._cache) >= self.max_size:
                oldest_key = next(iter(self._cache))
                del self._cache[oldest_key]
                self._stats["evictions"] += 1
                logger.debug(f"缓存已满，淘汰最旧条目: {oldest_key}")
            
            expires_at = datetime.now() + timedelta(seconds=ttl or self.default_ttl)
            
            self._cache[key] = {
                "data": data,
                "expires_at": expires_at,
                "created_at": datetime.now()
            }
            
            self._cache.move_to_end(key)
            
            logger.debug(f"缓存已设置: {key}, 过期时间: {expires_at}")
            return True
    
    def delete(self, key_type: str, identifier: str = None) -> bool:
        """
        删除缓存条目
        
        Args:
            key_type: 键类型
            identifier: 标识符
        
        Returns:
            是否成功
        """
        with self._lock:
            key = self._generate_key(key_type, identifier)
            
            if key in self._cache:
                del self._cache[key]
                self._stats["invalidations"] += 1
                logger.debug(f"缓存已删除: {key}")
                return True
            
            return False
    
    def invalidate_strategy(self, strategy_id: int) -> bool:
        """
        失效单个策略缓存
        
        Args:
            strategy_id: 策略ID
        
        Returns:
            是否成功
        """
        logger.info(f"失效策略缓存: strategy_id={strategy_id}")
        return self.delete("strategy", str(strategy_id))
    
    def invalidate_metric(self, metric_name: str) -> bool:
        """
        失效指标相关的所有缓存
        
        Args:
            metric_name: 指标名称
        
        Returns:
            是否成功
        """
        logger.info(f"失效指标缓存: metric_name={metric_name}")
        
        with self._lock:
            keys_to_delete = [
                key for key in self._cache
                if key.startswith(f"metric:{metric_name}")
            ]
            
            for key in keys_to_delete:
                del self._cache[key]
                self._stats["invalidations"] += 1
            
            if keys_to_delete:
                logger.info(f"已失效 {len(keys_to_delete)} 个指标缓存")
            
            return True
    
    def invalidate_all(self) -> bool:
        """
        失效所有缓存
        
        Returns:
            是否成功
        """
        with self._lock:
            count = len(self._cache)
            self._cache.clear()
            self._stats["invalidations"] += count
            logger.info(f"已失效所有缓存: {count} 个条目")
            return True
    
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息
        
        Returns:
            统计信息字典
        """
        with self._lock:
            total_requests = self._stats["total_requests"]
            hit_rate = (
                self._stats["hits"] / total_requests * 100
                if total_requests > 0
                else 0
            )
            
            return {
                "total_requests": total_requests,
                "hits": self._stats["hits"],
                "misses": self._stats["misses"],
                "hit_rate": f"{hit_rate:.2f}%",
                "evictions": self._stats["evictions"],
                "invalidations": self._stats["invalidations"],
                "current_size": len(self._cache),
                "max_size": self.max_size,
                "default_ttl": self.default_ttl
            }
    
    def clear_expired(self) -> int:
        """
        清理过期缓存
        
        Returns:
            清理的条目数
        """
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if self._is_expired(entry)
            ]
            
            for key in expired_keys:
                del self._cache[key]
            
            if expired_keys:
                logger.info(f"清理过期缓存: {len(expired_keys)} 个条目")
            
            return len(expired_keys)
    
    def get_cache_info(self) -> Dict[str, Any]:
        """
        获取缓存详细信息
        
        Returns:
            缓存信息字典
        """
        with self._lock:
            cache_items = []
            
            for key, entry in self._cache.items():
                cache_items.append({
                    "key": key,
                    "created_at": entry["created_at"].isoformat(),
                    "expires_at": entry["expires_at"].isoformat(),
                    "is_expired": self._is_expired(entry)
                })
            
            return {
                "stats": self.get_stats(),
                "items": cache_items
            }


strategy_cache = StrategyCacheManager(max_size=1000, default_ttl=300)
