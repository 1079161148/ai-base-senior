"""v1 路由汇总。

main.py 只挂这一个 router，
新增模块时只改这里一行，不用动 main.py。
"""

from fastapi import APIRouter

# 同包内模块用「显式」相对导入：`.` 即当前包 agent_lab.app.api.v1
# 显式相对导入不会被判定为隐式相对导入，且不受检查器源码根配置影响
from . import demo, health, todos

api_router = APIRouter()

api_router.include_router(health.router)
api_router.include_router(todos.router)
api_router.include_router(demo.router)

# 后续阶段在这里加：
# api_router.include_router(chat.router)    # S1
# api_router.include_router(agent.router)   # S2
# api_router.include_router(rag.router)     # S3
