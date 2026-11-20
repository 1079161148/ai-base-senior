"""第 66 章 · 配置对象。

优先级（高 → 低）：

    环境变量  >  .env 文件  >  类默认值

【要点】`env_prefix="APP_"` 让所有变量带上命名空间，避免与系统变量
        （`PATH`、`DEBUG` 之类）撞车。
"""

from functools import lru_cache
from typing import Literal

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        env_prefix="APP_",
        extra="forbid",  # 【要点】未知的 APP_* 变量直接报错，避免拼写错静默生效
        case_sensitive=False,
    )

    env: Literal["dev", "prod"] = "dev"
    debug: bool = True
    database_url: str = "sqlite:///./app.db"
    # 【要点】`SecretStr` 的 repr / str 都是 `**********`，日志不会泄露
    secret_key: SecretStr = SecretStr("dev-only-secret")
    max_items: int = Field(default=100, ge=1, le=10_000)


@lru_cache
def get_settings() -> Settings:
    """【要点】`lru_cache` 保证全进程只有一个实例，读文件只发生一次"""
    return Settings()