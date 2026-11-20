"""第 65 章 · 大型应用拆分。

组装顺序即路由树：

    app
     └── /api/v1            (APIRouter, prefix="/api/v1")
          ├── /users         (routers/users.py)
          ├── /items         (routers/items.py)
          └── /admin         (routers/admin.py, 带鉴权依赖)
     └── /health            (直接挂在 app 上，不在 /api/v1 下)

【要点】每个模块只声明**自己那一段** prefix，外层前缀在组装处叠加，
        这样同一套 router 既能挂 `/api/v1`，也能挂 `/internal`。

启动：uvicorn main:app --reload
验收：python verify.py
"""

import routers.admin as admin_router
import routers.items as items_router
import routers.users as users_router
from fastapi import APIRouter, FastAPI

app = FastAPI(title="第 65 章 · 大型应用拆分", version="0.1.0")

# 【要点】版本化前缀只在这一处出现，改版本不用动任何模块
api = APIRouter(prefix="/api/v1")

api.include_router(users_router.router)
api.include_router(items_router.router)
api.include_router(admin_router.router)

app.include_router(api)


@app.get("/health", tags=["ops"], summary="健康检查")
def health() -> dict[str, str]:
    """【要点】探针路径不该带版本前缀，否则每次发版都要改监控"""
    return {"status": "ok"}


@app.get("/routes", tags=["ops"], summary="路由清单")
def routes() -> dict[str, list[str]]:
    """【实测坑】别遍历 `app.routes`：FastAPI 0.146 的 `include_router`
    往 `app.routes` 里塞的是 `_IncludedRouter` 包装对象（无 `.path`），
    子路由并没有被展平。要拿完整清单就查 `openapi()["paths"]`。
    """
    return {"paths": sorted(app.openapi()["paths"])}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)