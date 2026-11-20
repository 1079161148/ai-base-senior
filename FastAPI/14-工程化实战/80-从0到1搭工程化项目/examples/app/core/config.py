"""积木 2 · 配置层：所有可变值集中在这里。

【原则】除了本文件，任何地方都不允许出现 `8000`、`demo-token`、`app.db` 这类字面量。
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
    version: str = "0.1.0"

    db_path: str = Field(default="app.db", description="SQLite 文件路径")
    token: SecretStr = Field(default=SecretStr("dev-token"), description="写操作令牌")

    api_prefix: str = "/api/v1"
    page_size_default: int = Field(default=10, ge=1, le=100)
    page_size_max: int = Field(default=100, ge=1, le=1000)

    log_level: Literal["DEBUG", "INFO", "WARNING", "ERROR"] = "INFO"
    slow_ms: int = Field(default=50, ge=1)

    @property
    def is_prod(self) -> bool:
        return self.env == "prod"


@lru_cache
def get_settings() -> Settings:
    return Settings()