"""v1 路由汇总：把本版本下所有资源的 router 收成一个。

这一层的职责只有一个——**聚合**。不放任何业务逻辑，也不直接定义接口。
好处：main.py 只需 include 这一个 router，新增资源时只改这一个文件。
"""

from __future__ import annotations

from fastapi import APIRouter

# 【作用】使用相对导入：`..` 表示当前包（v1）的父包（api）下的 v1 子包里的 items
# 等价绝对导入：from shop.api.v1 import items
# 【注意】相对导入只能在「包内模块被导入」时使用；直接 `python items.py` 运行会报
#        ImportError: attempted relative import with no known parent package
from . import items, users

# 【作用】版本前缀在这一层加：/v1
# 【注意】prefix 里不要带 `/api`，那是 main.py 的事（分层负责，便于将来换网关）
api_router = APIRouter(prefix="/v1")

# 【作用】逐个 include。注意顺序会影响匹配优先级（第 03 章 2.1）
api_router.include_router(items.router)
api_router.include_router(users.router)
