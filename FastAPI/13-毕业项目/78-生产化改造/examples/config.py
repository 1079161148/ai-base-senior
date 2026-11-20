"""配置外置：不再有任何硬编码的端口/令牌/库路径。

【要点】`SecretStr` 让令牌在日志、repr、`model_dump()` 里都是掩码。
        优先级：环境变量 > `.env` > 默认值（第 66 章实测）。
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="APP_",
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    env: Literal["dev", "test", "prod"] = "dev"
    db_path: str = Field(default="todos.db", description="SQLite 文件路径")
    token: SecretStr = Field(default=SecretStr("demo-token"), description="写操作令牌")
    page_size_max: int = Field(default=100, ge=1, le=1000)
    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    slow_ms: int = Field(default=50, ge=1, description="超过该耗时的请求记 WARNING")
    version: str = "1.0.0"


@lru_cache
def get_settings() -> Settings:
    """【要点】测试里改环境变量后要 `get_settings.cache_clear()`"""
    return Settings()