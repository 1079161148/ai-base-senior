"""第 76 章 · 部署与交付。

生产交付的四件事：

    1. 探针：`/healthz`（活着）+ `/readyz`（能干活）
    2. 进程：`--workers N`、`--proxy-headers`、不开 `--reload`
    3. 容器：非 root、`HEALTHCHECK`、日志到 stdout
    4. 退出：收到 SIGTERM 后跑完 lifespan 的 shutdown

【要点】liveness 与 readiness 必须分开：
        - `/healthz` 只证明进程活着，**不查依赖**（查了会引起误重启）
        - `/readyz` 检查依赖，失败返回 503（让它从负载均衡摘掉）

启动（开发）：uvicorn main:app --reload
启动（生产）：uvicorn main:app --host 0.0.0.0 --port 8000 --workers 4
验收：python verify.py
或：  uv run pytest -q
"""

import os
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Response, status

APP_ENV = os.getenv("APP_ENV", "dev")
APP_VERSION = "1.0.0"
PORT = int(os.getenv("PORT", "8000"))

STATE: dict[str, Any] = {"ready": False, "db_ok": True, "shutdown_done": False}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """【要点】初始化失败要让 `ready` 保持 False，探针才会把流量挡在外面"""
    STATE["ready"] = False
    STATE["db_ok"] = True
    STATE["shutdown_done"] = False
    await _connect()
    STATE["ready"] = True
    try:
        yield
    finally:
        # 【要点】SIGTERM 后这里必须能快速跑完，否则会被 SIGKILL
        STATE["ready"] = False
        STATE["db_ok"] = False
        STATE["shutdown_done"] = True


async def _connect() -> None:
    """真实项目里是建连接池；这里只标记已就绪"""


app = FastAPI(
    title="第 76 章 · 部署与交付",
    version=APP_VERSION,
    lifespan=lifespan,
    # 【要点】生产关文档，减少扫描面
    docs_url=None if APP_ENV == "prod" else "/docs",
    redoc_url=None if APP_ENV == "prod" else "/redoc",
)


@app.middleware("http")
async def version_header(request, call_next):
    response = await call_next(request)
    response.headers["X-App-Version"] = APP_VERSION
    return response


@app.get("/healthz", tags=["探针"], summary="存活探针（不查依赖）")
def healthz() -> dict[str, str]:
    """只要进程还能响应就返回 200。查依赖会让数据库抖动引发全量重启。"""
    return {"status": "ok", "version": APP_VERSION}


@app.get("/readyz", tags=["探针"], summary="就绪探针（查依赖）")
def readyz(response: Response) -> dict[str, Any]:
    """依赖不可用时返回 503，让负载均衡把实例摘掉。"""
    if not (STATE["ready"] and STATE["db_ok"]):
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return {"status": "not ready", "ready": False, "db_ok": STATE["db_ok"]}
    return {"status": "ready", "ready": True, "db_ok": True}


@app.get("/info", tags=["诊断"], summary="运行信息")
def info() -> dict[str, Any]:
    return {"env": APP_ENV, "version": APP_VERSION, "port": PORT}


@app.get("/items", tags=["业务"], summary="业务接口")
def list_items() -> dict[str, list[str]]:
    return {"items": ["a", "b"]}


# ============================================================
# 生产形态的对照 App（关闭文档）
# ============================================================
prod_app = FastAPI(
    title="生产形态",
    version=APP_VERSION,
    openapi_url=None,
    docs_url=None,
    redoc_url=None,
)


@prod_app.get("/items")
def prod_items() -> dict[str, list[str]]:
    return {"items": ["a"]}


def set_db_ok(value: bool) -> None:
    STATE["db_ok"] = value


def reset() -> None:
    STATE.update(ready=False, db_ok=True, shutdown_done=False)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=PORT)