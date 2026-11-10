"""
风险评估器模块

该模块实现风险分级判定机制：
1. 从 YAML 配置加载风险等级定义
2. 根据操作类型、目标设备、环境条件评估风险等级
3. 高风险操作挂起期间锁定设备，防止指令冲突

核心功能：
1. assess_risk(): 评估操作风险等级
2. load_config(): 从 YAML 加载配置
3. 设备互斥锁机制：高风险操作期间锁定设备
"""

import os
import yaml
import logging
import asyncio
from typing import Optional, Dict, Any, List
from pathlib import Path
from datetime import datetime

from models import RiskLevel
from services.distributed_lock import lock_manager, LockAcquireError

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class RiskAssessmentError(Exception):
    """风险评估错误"""
    pass


class DeviceLockedError(Exception):
    """设备锁定错误"""
    pass


class RiskAssessor:
    """
    风险评估器
    
    职责：
    1. 加载风险等级配置
    2. 评估操作风险等级
    3. 管理设备互斥锁
    4. 提供风险升级判断
    
    特性：
    - 支持基于操作类型的风险评估
    - 支持基于环境条件的风险升级
    - 高风险操作自动锁定设备
    - 配置热加载
    """
    
    def __init__(self, config_path: Optional[str] = None):
        """
        初始化风险评估器
        
        Args:
            config_path: 配置文件路径，默认为 server/config/risk_levels.yaml
        """
        if config_path is None:
            # 默认配置路径
            current_dir = Path(__file__).parent.parent
            config_path = current_dir / "config" / "risk_levels.yaml"
        
        self.config_path = Path(config_path)
        self.config: Dict[str, Any] = {}
        self.device_lock_config: Dict[str, Any] = {}
        
        # 设备锁映射：device_id -> lock_info
        self._device_locks: Dict[str, Dict[str, Any]] = {}
        
        # 加载配置
        self.load_config()
        
        logger.info(f"风险评估器已初始化: config_path={self.config_path}")
    
    def load_config(self) -> None:
        """
        从 YAML 文件加载配置
        
        Raises:
            RiskAssessmentError: 配置加载失败
        """
        try:
            if not self.config_path.exists():
                raise RiskAssessmentError(f"配置文件不存在: {self.config_path}")
            
            with open(self.config_path, 'r', encoding='utf-8') as f:
                self.config = yaml.safe_load(f)
            
            # 提取设备锁配置
            self.device_lock_config = self.config.get('device_lock_config', {
                'enabled': True,
                'lock_timeout': 600,
                'max_wait_time': 300,
                'retry_interval': 5
            })
            
            logger.info(
                f"配置加载成功: "
                f"risk_levels={list(self.config.keys())}, "
                f"device_lock_enabled={self.device_lock_config.get('enabled')}"
            )
            
        except Exception as e:
            logger.error(f"配置加载失败: {str(e)}")
            raise RiskAssessmentError(f"配置加载失败: {str(e)}")
    
    def assess_risk(
        self,
        action_type: str,
        target_device: Optional[str] = None,
        value: Optional[Any] = None,
        env_conditions: Optional[Dict[str, Any]] = None
    ) -> RiskLevel:
        """
        评估操作风险等级
        
        Args:
            action_type: 操作类型，如 "LIGHT_CONTROL", "IRRIGATION"
            target_device: 目标设备，如 "补光灯", "灌溉系统"
            value: 操作值，如开度、流量等
            env_conditions: 环境条件，如 {"temperature": 38, "area": 1500}
        
        Returns:
            RiskLevel: 风险等级（LOW, MEDIUM, HIGH）
        
        Raises:
            RiskAssessmentError: 风险评估失败
        """
        try:
            # 1. 获取操作类型映射的默认风险等级
            action_type_mapping = self.config.get('risk_assessment_rules', {}).get(
                'action_type_mapping', {}
            )
            
            default_risk = action_type_mapping.get(action_type)
            
            if not default_risk:
                # 使用默认风险等级
                default_risk = self.config.get('default_risk_level', 'MEDIUM')
                logger.warning(
                    f"操作类型 {action_type} 未配置风险等级，使用默认等级: {default_risk}"
                )
            
            risk_level = RiskLevel[default_risk]
            
            # 2. 检查是否需要风险升级
            if env_conditions:
                risk_level = self._check_risk_upgrade(
                    action_type=action_type,
                    current_risk=risk_level,
                    env_conditions=env_conditions
                )
            
            # 3. 记录评估结果
            logger.info(
                f"风险评估完成: action_type={action_type}, "
                f"target_device={target_device}, risk_level={risk_level.value}"
            )
            
            return risk_level
            
        except Exception as e:
            logger.error(f"风险评估失败: {str(e)}")
            # 返回中等风险作为安全默认值
            return RiskLevel.MEDIUM
    
    def _check_risk_upgrade(
        self,
        action_type: str,
        current_risk: RiskLevel,
        env_conditions: Dict[str, Any]
    ) -> RiskLevel:
        """
        检查是否需要风险升级
        
        Args:
            action_type: 操作类型
            current_risk: 当前风险等级
            env_conditions: 环境条件
        
        Returns:
            RiskLevel: 升级后的风险等级
        """
        condition_upgrades = self.config.get('risk_assessment_rules', {}).get(
            'condition_upgrades', []
        )
        
        for upgrade_rule in condition_upgrades:
            # 检查操作类型是否匹配
            if action_type not in upgrade_rule.get('action_types', []):
                continue
            
            # 检查条件是否满足
            condition = upgrade_rule.get('condition', '')
            if self._evaluate_condition(condition, env_conditions):
                # 升级风险等级
                upgrade_to = RiskLevel[upgrade_rule['upgrade_to']]
                reason = upgrade_rule.get('reason', '环境条件触发风险升级')
                
                logger.warning(
                    f"风险升级: {current_risk.value} -> {upgrade_to.value}, "
                    f"reason={reason}, condition={condition}"
                )
                
                return upgrade_to
        
        return current_risk
    
    def _evaluate_condition(
        self,
        condition: str,
        env_conditions: Dict[str, Any]
    ) -> bool:
        """
        评估条件表达式
        
        Args:
            condition: 条件表达式，如 "temperature > 35"
            env_conditions: 环境条件字典
        
        Returns:
            是否满足条件
        """
        try:
            # 简单的条件解析（支持 >, <, ==, >=, <=）
            for op in ['>=', '<=', '>', '<', '==']:
                if op in condition:
                    parts = condition.split(op)
                    if len(parts) == 2:
                        var_name = parts[0].strip()
                        threshold = float(parts[1].strip())
                        
                        actual_value = env_conditions.get(var_name)
                        if actual_value is None:
                            return False
                        
                        actual_value = float(actual_value)
                        
                        if op == '>':
                            return actual_value > threshold
                        elif op == '<':
                            return actual_value < threshold
                        elif op == '==':
                            return actual_value == threshold
                        elif op == '>=':
                            return actual_value >= threshold
                        elif op == '<=':
                            return actual_value <= threshold
            
            return False
            
        except Exception as e:
            logger.error(f"条件评估失败: condition={condition}, error={str(e)}")
            return False
    
    async def acquire_device_lock(
        self,
        device_id: str,
        owner: Optional[str] = None,
        timeout: Optional[float] = None
    ) -> str:
        """
        获取设备互斥锁
        
        Args:
            device_id: 设备ID
            owner: 锁持有者标识
            timeout: 锁超时时间（秒）
        
        Returns:
            lock_id: 锁ID
        
        Raises:
            DeviceLockedError: 设备已被锁定
        """
        if not self.device_lock_config.get('enabled', True):
            logger.debug(f"设备锁未启用，跳过锁定: device_id={device_id}")
            return ""
        
        timeout = timeout or self.device_lock_config.get('lock_timeout', 600)
        resource_key = f"device:{device_id}"
        
        try:
            lock_id = await lock_manager.acquire_lock(
                resource_key=resource_key,
                owner=owner,
                timeout=timeout
            )
            
            # 记录设备锁信息
            self._device_locks[device_id] = {
                "lock_id": lock_id,
                "owner": owner,
                "acquired_at": datetime.now().isoformat(),
                "timeout": timeout
            }
            
            logger.info(
                f"设备锁获取成功: device_id={device_id}, lock_id={lock_id}"
            )
            
            return lock_id
            
        except LockAcquireError as e:
            logger.error(f"设备锁获取失败: device_id={device_id}, error={str(e)}")
            raise DeviceLockedError(f"设备 {device_id} 已被锁定，请稍后重试")
    
    async def release_device_lock(
        self,
        device_id: str,
        lock_id: Optional[str] = None
    ) -> bool:
        """
        释放设备互斥锁
        
        Args:
            device_id: 设备ID
            lock_id: 锁ID
        
        Returns:
            是否释放成功
        """
        resource_key = f"device:{device_id}"
        
        success = await lock_manager.release_lock(resource_key, lock_id)
        
        if success:
            # 清理设备锁记录
            if device_id in self._device_locks:
                del self._device_locks[device_id]
            
            logger.info(f"设备锁释放成功: device_id={device_id}")
        
        return success
    
    def is_device_locked(self, device_id: str) -> bool:
        """
        检查设备是否被锁定
        
        Args:
            device_id: 设备ID
        
        Returns:
            是否被锁定
        """
        resource_key = f"device:{device_id}"
        lock_info = lock_manager.get_lock_info(resource_key)
        
        return lock_info is not None and not lock_info.get('is_expired', False)
    
    def get_device_lock_info(self, device_id: str) -> Optional[Dict[str, Any]]:
        """
        获取设备锁信息
        
        Args:
            device_id: 设备ID
        
        Returns:
            锁信息字典，如果未锁定则返回 None
        """
        resource_key = f"device:{device_id}"
        return lock_manager.get_lock_info(resource_key)
    
    def get_execution_policy(self, risk_level: RiskLevel) -> Dict[str, Any]:
        """
        获取风险等级对应的执行策略
        
        Args:
            risk_level: 风险等级
        
        Returns:
            执行策略字典
        """
        risk_config = self.config.get(risk_level.value, {})
        return risk_config.get('execution_policy', {
            'auto_execute': True,
            'require_confirmation': False,
            'async_review': True,
            'log_level': 'INFO'
        })
    
    def get_risk_description(self, risk_level: RiskLevel) -> str:
        """
        获取风险等级描述
        
        Args:
            risk_level: 风险等级
        
        Returns:
            风险描述
        """
        risk_config = self.config.get(risk_level.value, {})
        return risk_config.get('description', '未知风险等级')
    
    def get_all_device_locks(self) -> Dict[str, Dict[str, Any]]:
        """
        获取所有设备锁信息
        
        Returns:
            设备锁信息字典
        """
        return self._device_locks.copy()


# 全局单例
risk_assessor = RiskAssessor()
