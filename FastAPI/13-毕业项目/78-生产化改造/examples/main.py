"""第 78 章 · 毕业项目（二）：生产化改造。

相对第 77 章的六处改造：

    1. 配置外置    config.py（pydantic-settings，SecretStr 令牌）
    2. 日志        logging_setup.py（一行一请求 + 请求 ID）
    3. 中间件      middleware.py（请求 ID / 耗时 / 版本头）
    4. 持久化      db.py + repo.py（SQLite + 事务边界）
    5. 依赖注入    deps.py（repo / 分页 / 过滤 / 鉴权）
    6. 错误契约    errors.py（含 `AppError` 日志）

启动：APP_DB_PATH=todos.db APP_TOKEN=<你的令牌> uvicorn main:app --reload
验收：python verify.py
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from config import get_settings
from db import init_db
from errors import install_error_handlers
from logging_setup import configure_logging
from middleware import ObserveMiddleware
from todos_router import router as todos_router

settings = get_settings()
configure_logging(settings.log_level)
logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db(settings)
    logger.info("startup env=%s db=%s", settings.env, settings.db_path)
    try:
        yield
    finally:
        logger.info("shutdown")


app = FastAPI(
    title="待办服务（生产形态）",
    version=settings.version,
    description="第 78 章毕业项目：配置、日志、事务、依赖注入全部到位",
    lifespan=lifespan,
    docs_url="/docs" if settings.env != "prod" else None,
    redoc_url=None,
)

app.add_middleware(ObserveMiddleware, version=settings.version, slow_ms=settings.slow_ms)
install_error_handlers(app)
app.include_router(todos_router, prefix="/api/v1")


@app.get("/healthz", tags=["诊断"], summary="存活探针")
def healthz() -> dict[str, str]:
    """【要点】不查数据库：库抖动不该触发容器重启"""
    return {"status": "ok", "version": settings.version}


@app.get("/boom", include_in_schema=False)
def boom() -> None:
    raise RuntimeError("内部炸了：不该出现在响应里")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)