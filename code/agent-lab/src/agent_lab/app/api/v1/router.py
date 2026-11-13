"""v1 路由汇总。

main.py 只挂这一个 router，
新增模块时只改这里一行，不用动 main.py。
"""

from fastapi import APIRouter

# 同包内模块用「显式」相对导入：`.` 即当前包 agent_lab.app.api.v1
# 显式相对导入不会被判定为隐式相对导入，且不受检查器源码根配置影响
from . import auth, chat, demo, health, metrics, plans, rag, sessions, todos, traces

api_router = APIRouter()

api_router.include_router(auth.router)    # S9：登录 / 注册 / 当前用户
api_router.include_router(health.router)
api_router.include_router(todos.router)
api_router.include_router(demo.router)
api_router.include_router(chat.router)
api_router.include_router(traces.router)  # S2：Agent 每一步的可回放记录
api_router.include_router(rag.router)     # S3：文档上传与检索
api_router.include_router(sessions.router)  # S4：会话管理
api_router.include_router(plans.router)     # S6：任务计划（可暂停/编辑/恢复）
api_router.include_router(metrics.router)   # S7：指标看板 / Prometheus

# 后续阶段在这里加：
