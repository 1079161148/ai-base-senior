"""配置模块：集中管理所有环境相关参数。

本章用手写 dataclass + os.getenv 演示思路，第 66 章会换成 pydantic-settings。
为什么现在就拆出来：配置一旦散落在各模块的 os.getenv 里，换环境就要全局搜索。
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field


@dataclass(frozen=True)
class Settings:
    """只读配置对象。

    【为什么】用 frozen dataclass：配置在启动时确定，运行期不该被改。
    【注意】模块级单例（下面的 settings）在多进程下每个 worker 各一份，
           但配置本来就是只读的，所以没有一致性问题。
    """

    app_name: str = "shop"
    app_version: str = "0.1.0"
    env: str = field(default_factory=lambda: os.getenv("APP_ENV", "dev"))
    api_prefix: str = "/api"
    api_version_prefix: str = "/v1"
    debug: bool = field(default_factory=lambda: os.getenv("APP_DEBUG", "0") == "1")


# 【作用】全项目共用同一个配置实例
# 【注意】不要在函数里 `Settings()`——每次都会重新读环境变量，测试时难以替换
settings = Settings()
