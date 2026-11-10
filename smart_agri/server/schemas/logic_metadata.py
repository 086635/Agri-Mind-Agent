"""
RAG 规则元数据定义模块

定义知识图谱化元数据标准，支持版本追溯和逻辑演化追踪
"""

from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, field_validator, model_validator
from datetime import datetime
import json


class LogicMetadata(BaseModel):
    """
    RAG 规则元数据模型
    
    用于存储和管理知识图谱中逻辑规则的元数据信息
    支持版本追溯、逻辑演化和知识图谱构建
    
    必需字段：
    - version: 版本号，必须 >= 1
    - parent_id: 父逻辑ID，用于追溯版本链条（可空，表示根节点）
    - is_active: 是否为活跃版本
    - action_set_hash: 操作组合的哈希指纹
    - created_by: 创建者ID
    - confirmed_by: 确认者ID（可空，表示未经用户确认）
    
    可选字段：
    - temp_range: 温度范围
    - weather_condition: 天气条件
    - humidity_range: 湿度范围
    - light_intensity_range: 光照强度范围
    - soil_moisture_range: 土壤湿度范围
    - growth_stage: 生长阶段
    - custom_params: 自定义参数
    """
    
    # 必需字段
    version: int = Field(..., ge=1, description="版本号，必须 >= 1")
    parent_id: Optional[str] = Field(None, description="父逻辑ID，用于追溯版本链条")
    is_active: bool = Field(default=True, description="是否为活跃版本")
    action_set_hash: str = Field(..., min_length=1, description="操作组合的哈希指纹")
    created_by: str = Field(..., min_length=1, description="创建者ID")
    confirmed_by: Optional[str] = Field(None, description="确认者ID")
    
    # 置信度字段
    confidence_score: float = Field(
        default=1.0, 
        ge=0.0, 
        le=10.0, 
        description="置信度分数，范围 0.0-10.0，默认值 1.0"
    )
    
    # 可选环境参数字段
    temp_range: Optional[Dict[str, float]] = Field(
        None, 
        description="温度范围，格式: {'min': 15.0, 'max': 30.0}"
    )
    weather_condition: Optional[List[str]] = Field(
        None, 
        description="天气条件列表，如 ['sunny', 'cloudy']"
    )
    humidity_range: Optional[Dict[str, float]] = Field(
        None, 
        description="湿度范围，格式: {'min': 40.0, 'max': 80.0}"
    )
    light_intensity_range: Optional[Dict[str, float]] = Field(
        None, 
        description="光照强度范围，格式: {'min': 1000.0, 'max': 5000.0}"
    )
    soil_moisture_range: Optional[Dict[str, float]] = Field(
        None, 
        description="土壤湿度范围，格式: {'min': 20.0, 'max': 60.0}"
    )
    growth_stage: Optional[str] = Field(
        None, 
        description="生长阶段，如 'seedling', 'vegetative', 'flowering', 'fruiting'"
    )
    
    # 版本演进相关字段
    evolution_reason: Optional[str] = Field(
        None, 
        description="版本演进原因，例如：'树长大了'、'天气更热了'、'农户经验调整'"
    )
    
    # 自定义参数
    custom_params: Optional[Dict[str, Any]] = Field(
        None, 
        description="自定义参数，用于扩展特定场景的元数据"
    )
    
    # 时间戳
    created_at: Optional[datetime] = Field(
        default_factory=datetime.now, 
        description="创建时间"
    )
    updated_at: Optional[datetime] = Field(
        default_factory=datetime.now, 
        description="更新时间"
    )
    
    @field_validator('parent_id')
    @classmethod
    def validate_parent_id(cls, v: Optional[str]) -> Optional[str]:
        """验证 parent_id 格式"""
        if v is not None:
            if not v.strip():
                raise ValueError("parent_id 不能为空字符串")
            # 验证格式：应该是一个有效的ID格式（字母、数字、下划线、连字符）
            import re
            if not re.match(r'^[a-zA-Z0-9_-]+$', v):
                raise ValueError("parent_id 格式不正确，只能包含字母、数字、下划线和连字符")
        return v
    
    @field_validator('action_set_hash')
    @classmethod
    def validate_action_set_hash(cls, v: str) -> str:
        """验证 action_set_hash 格式"""
        if not v or not v.strip():
            raise ValueError("action_set_hash 不能为空")
        # 哈希值应该是十六进制字符串
        import re
        if not re.match(r'^[a-fA-F0-9]+$', v):
            raise ValueError("action_set_hash 格式不正确，应该是十六进制字符串")
        return v
    
    @field_validator('temp_range', 'humidity_range', 'light_intensity_range', 'soil_moisture_range')
    @classmethod
    def validate_range_fields(cls, v: Optional[Dict[str, float]]) -> Optional[Dict[str, float]]:
        """验证范围字段格式"""
        if v is not None:
            if 'min' not in v or 'max' not in v:
                raise ValueError("范围字段必须包含 'min' 和 'max' 键")
            if v['min'] > v['max']:
                raise ValueError("范围的最小值不能大于最大值")
        return v
    
    @model_validator(mode='after')
    def validate_version_parent_consistency(self):
        """验证版本和父ID的一致性"""
        # 如果是第一个版本（version=1），parent_id 应该为 None
        if self.version == 1 and self.parent_id is not None:
            raise ValueError("第一个版本（version=1）的 parent_id 应该为 None")
        # 如果版本大于1，parent_id 不应该为 None
        if self.version > 1 and self.parent_id is None:
            raise ValueError("版本大于1时，parent_id 不能为 None")
        return self
    
    def to_json(self) -> str:
        """转换为 JSON 字符串"""
        return self.model_dump_json()
    
    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return self.model_dump()
    
    @classmethod
    def from_json(cls, json_str: str) -> 'LogicMetadata':
        """从 JSON 字符串创建实例"""
        return cls.model_validate_json(json_str)
    
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'LogicMetadata':
        """从字典创建实例"""
        return cls.model_validate(data)


class LogicHistoryEntry(BaseModel):
    """
    逻辑历史条目模型
    
    用于表示版本链条中的一个节点
    """
    logic_id: str = Field(..., description="逻辑ID")
    version: int = Field(..., description="版本号")
    parent_id: Optional[str] = Field(None, description="父逻辑ID")
    is_active: bool = Field(..., description="是否活跃")
    created_by: str = Field(..., description="创建者")
    created_at: datetime = Field(..., description="创建时间")
    evolution_reason: Optional[str] = Field(None, description="版本演进原因")
    summary: Optional[str] = Field(None, description="变更摘要")


class LogicHistory(BaseModel):
    """
    逻辑历史链条模型
    
    用于表示完整的版本演化历史
    """
    current_logic_id: str = Field(..., description="当前逻辑ID")
    history: List[LogicHistoryEntry] = Field(default_factory=list, description="历史条目列表")
    total_versions: int = Field(..., description="总版本数")
    
    def get_oldest_version(self) -> Optional[LogicHistoryEntry]:
        """获取最老版本（根节点）"""
        if not self.history:
            return None
        return min(self.history, key=lambda x: x.version)
    
    def get_latest_version(self) -> Optional[LogicHistoryEntry]:
        """获取最新版本"""
        if not self.history:
            return None
        return max(self.history, key=lambda x: x.version)
    
    def get_active_versions(self) -> List[LogicHistoryEntry]:
        """获取所有活跃版本"""
        return [entry for entry in self.history if entry.is_active]


class LogicMetadataValidator:
    """
    元数据验证器
    
    提供静态方法用于验证元数据的完整性和正确性
    """
    
    @staticmethod
    def validate_required_fields(metadata: Dict[str, Any]) -> bool:
        """
        验证必需字段是否存在
        
        Args:
            metadata: 元数据字典
            
        Returns:
            bool: 验证是否通过
            
        Raises:
            ValueError: 当必需字段缺失时
        """
        required_fields = ['version', 'action_set_hash', 'created_by']
        missing_fields = [field for field in required_fields if field not in metadata]
        
        if missing_fields:
            raise ValueError(f"缺少必需字段: {', '.join(missing_fields)}")
        
        return True
    
    @staticmethod
    def validate_version(metadata: Dict[str, Any]) -> bool:
        """
        验证版本号是否有效
        
        Args:
            metadata: 元数据字典
            
        Returns:
            bool: 验证是否通过
            
        Raises:
            ValueError: 当版本号无效时
        """
        version = metadata.get('version')
        
        if version is None:
            raise ValueError("缺少 version 字段")
        
        if not isinstance(version, int):
            raise ValueError("version 必须是整数")
        
        if version < 1:
            raise ValueError("version 必须 >= 1")
        
        return True
    
    @staticmethod
    def validate_parent_id_format(metadata: Dict[str, Any]) -> bool:
        """
        验证 parent_id 格式是否正确
        
        Args:
            metadata: 元数据字典
            
        Returns:
            bool: 验证是否通过
            
        Raises:
            ValueError: 当 parent_id 格式不正确时
        """
        parent_id = metadata.get('parent_id')
        
        if parent_id is not None:
            if not isinstance(parent_id, str):
                raise ValueError("parent_id 必须是字符串")
            
            if not parent_id.strip():
                raise ValueError("parent_id 不能为空字符串")
            
            import re
            if not re.match(r'^[a-zA-Z0-9_-]+$', parent_id):
                raise ValueError("parent_id 格式不正确，只能包含字母、数字、下划线和连字符")
        
        return True
    
    @staticmethod
    def validate_all(metadata: Dict[str, Any]) -> bool:
        """
        执行所有验证
        
        Args:
            metadata: 元数据字典
            
        Returns:
            bool: 验证是否通过
        """
        LogicMetadataValidator.validate_required_fields(metadata)
        LogicMetadataValidator.validate_version(metadata)
        LogicMetadataValidator.validate_parent_id_format(metadata)
        
        return True


class LogicVersionTracker:
    """
    逻辑版本追溯接口规范
    
    定义版本追溯的标准接口，具体实现需要注入数据库访问层
    """
    
    @staticmethod
    def get_logic_history(logic_id: str, db_session) -> LogicHistory:
        """
        获取逻辑的完整版本链条
        
        Args:
            logic_id: 逻辑ID
            db_session: 数据库会话
            
        Returns:
            LogicHistory: 包含完整版本历史的对象
            
        实现说明：
        1. 从当前 logic_id 开始，向上追溯所有父节点
        2. 构建完整的版本链条
        3. 返回 LogicHistory 对象
        """
        # 此方法需要具体实现
        # 这里提供接口规范和伪代码
        raise NotImplementedError("此方法需要在具体实现中完成")
    
    @staticmethod
    def get_latest_version(logic_id: str, db_session) -> Optional[LogicMetadata]:
        """
        获取逻辑的最新活跃版本
        
        Args:
            logic_id: 逻辑ID
            db_session: 数据库会话
            
        Returns:
            Optional[LogicMetadata]: 最新活跃版本的元数据，如果不存在则返回 None
            
        实现说明：
        1. 查询所有活跃版本的逻辑
        2. 返回版本号最大的那个
        """
        # 此方法需要具体实现
        # 这里提供接口规范和伪代码
        raise NotImplementedError("此方法需要在具体实现中完成")
    
    @staticmethod
    def get_children_versions(logic_id: str, db_session) -> List[LogicMetadata]:
        """
        获取指定逻辑的所有子版本
        
        Args:
            logic_id: 逻辑ID
            db_session: 数据库会话
            
        Returns:
            List[LogicMetadata]: 子版本列表
            
        实现说明：
        1. 查询所有 parent_id 等于指定 logic_id 的记录
        2. 返回元数据列表
        """
        # 此方法需要具体实现
        # 这里提供接口规范和伪代码
        raise NotImplementedError("此方法需要在具体实现中完成")


# 导出所有公共类和函数
__all__ = [
    'LogicMetadata',
    'LogicHistoryEntry',
    'LogicHistory',
    'LogicMetadataValidator',
    'LogicVersionTracker',
]
