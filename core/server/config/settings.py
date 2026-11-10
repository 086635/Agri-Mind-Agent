"""
环境配置管理

区分开发和生产环境的安全策略
"""

import os
import sys
from enum import Enum
from typing import Optional
from pydantic import Field
from pydantic_settings import BaseSettings


class Environment(str, Enum):
    """环境枚举"""
    DEV = "dev"
    PROD = "prod"


class Settings(BaseSettings):
    """
    应用配置

    从环境变量加载配置，支持 .env 文件
    """

    ENV: Environment = Field(
        default=Environment.DEV,
        description="运行环境：dev 或 prod"
    )

    DATABASE_URL: Optional[str] = Field(
        default=None,
        description="数据库连接URL（生产环境必填）"
    )
    ASYNC_DATABASE_URL: Optional[str] = Field(
        default=None,
        description="异步数据库连接URL（生产环境必填）"
    )

    DEBUG: bool = Field(
        default=False,
        description="调试模式"
    )

    RATE_LIMIT_ENABLED: bool = Field(
        default=True,
        description="是否启用限流"
    )
    RATE_LIMIT_PER_MINUTE: int = Field(
        default=100,
        description="每分钟请求限制"
    )

    LOG_SENSITIVE_DATA: bool = Field(
        default=False,
        description="是否在日志中记录敏感数据（仅开发环境）"
    )

    ANYTHING_LLM_API_KEY: Optional[str] = Field(
        default=None,
        description="AnythingLLM API Key"
    )
    ANYTHING_LLM_API_URL: Optional[str] = Field(
        default=None,
        description="AnythingLLM API URL"
    )

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = True
        use_enum_values = True
        extra = "ignore"

    @property
    def is_production(self) -> bool:
        """是否为生产环境"""
        return self.ENV == Environment.PROD

    @property
    def is_development(self) -> bool:
        """是否为开发环境"""
        return self.ENV == Environment.DEV

    def validate_production_config(self) -> None:
        """
        验证生产环境配置

        生产环境必须配置数据库连接，否则直接退出
        """
        if self.is_production:
            if not self.DATABASE_URL and not self.ASYNC_DATABASE_URL:
                print("[CRITICAL] 生产环境必须配置 DATABASE_URL 或 ASYNC_DATABASE_URL")
                sys.exit(1)

            if not self.ANYTHING_LLM_API_KEY:
                print("[CRITICAL] 生产环境必须配置 ANYTHING_LLM_API_KEY")
                sys.exit(1)

            print("[OK] 生产环境配置验证通过")

    def get_masked_api_key(self) -> str:
        """
        获取脱敏后的 API Key

        Returns:
            脱敏后的 API Key，如 "sk-abc...xyz"
        """
        if not self.ANYTHING_LLM_API_KEY:
            return "未配置"

        key = self.ANYTHING_LLM_API_KEY
        if len(key) <= 10:
            return "***"

        return f"{key[:7]}...{key[-3:]}"

    def get_masked_database_url(self) -> str:
        """
        获取脱敏后的数据库 URL

        Returns:
            脱敏后的数据库 URL，隐藏密码
        """
        if not self.DATABASE_URL:
            return "未配置"

        import re
        pattern = r'(postgresql(?:\+asyncpg)?://[^:]+:)([^@]+)(@.+)'
        return re.sub(pattern, r'\1***\3', self.DATABASE_URL)


settings = Settings()

settings.validate_production_config()
