"""全局配置。

所有可变的东西（模型名、单价、超时、跨域白名单）都放这里，
业务代码只 import settings，不要读 os.environ。
"""

from functools import lru_cache
from typing import ClassVar, Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # model_config 是 Pydantic 的「类级配置」，不是实例字段。
    # ClassVar 明确告诉类型检查器「它不属于模型的字段」，
    # 不加注解会触发 basedpyright 的「未注解类属性」告警（因为本类没加 @final）。
    # 类型必须与基类完全一致（ClassVar 是不变的，写窄了会被判为不兼容覆写）：
    # BaseSettings.model_config 声明为 ClassVar[SettingsConfigDict]，这里照抄。
    model_config: ClassVar[SettingsConfigDict] = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # --- 应用 ---
    PROJECT_NAME: str = "agent-lab"
    VERSION: str = "0.1.0"
    DEBUG: bool = False

    # --- 路由 ---
    # 所有业务接口统一挂在这个前缀下，方便以后做版本并存
    API_V1_PREFIX: str = "/api/v1"

    # --- 跨域 ---
    # 必须是具体地址。浏览器不允许 allow_origins=["*"] 与 allow_credentials=True 同时生效
    CORS_ORIGINS: list[str] = [
        "http://localhost:5173",
        "http://127.0.0.1:5173",
    ]

    # --- 时间 ---
    # 对外 JSON 里时间用哪个时区显示：
    #   True  = UTC（推荐）。时刻唯一，跨时区、多服务器部署都不会错。
    #   False = 服务器本地时区。Swagger 里看着顺眼，但依赖部署机器的 tz 配置。
    # 注意：这只影响「输出格式」，数据库里永远存 UTC。
    # 想改成本地时间：在 .env 里写 TIME_OUTPUT_UTC=false
    TIME_OUTPUT_UTC: bool = True

    # 时间的序列化格式：
    #   iso   = 2026-11-08T23:10:33+08:00   （国际标准，任何语言都能解析，推荐）
    #   human = 2026-11-08 23:10:33         （给人看舒服，但非标准）
    #
    # 只有调试期建议用 human：去掉 T 和时区后，浏览器只能按本地时区猜，
    # 跨时区用户会看到错误时间。上线前请改回 iso。
    TIME_FORMAT: Literal["iso", "human"] = "iso"


@lru_cache
def get_settings() -> Settings:
    """缓存实例，整个进程只解析一次环境变量。"""
    return Settings()


settings = get_settings()
