"""积木 12 · 装配层：`create_app()` 工厂 + lifespan。

【原则】工厂函数让「同一份代码不同配置」变成可能：
        测试传 `Settings(db_path=tmp, env="test")`，生产读环境变量。
        模块级 `app` 只留给 `uvicorn app.main:app` 用。
"""

import logging
from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from app.api.v1.router import router as v1_router
from app.core.config import Settings, get_settings
from app.core.errors import install_error_handlers
from app.core.logging import configure_logging
from app.core.middleware import ObserveMiddleware
from app.db.migrate import applied_versions, migrate

logger = logging.getLogger("app.main")


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging(settings.log_level)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        new = migrate(settings)
        logger.info(
            "startup env=%s db=%s migrated=%s versions=%s",
            settings.env,
            settings.db_path,
            new,
            applied_versions(settings),
        )
        try:
            yield
        finally:
            logger.info("shutdown")

    application = FastAPI(
        title="工程化脚手架",
        version=settings.version,
        description="第 80 章：12 块积木搭出来的项目骨架",
        lifespan=lifespan,
        # 生产不暴露文档：内部结构不对外
        docs_url=None if settings.is_prod else "/docs",
        redoc_url=None,
    )
    application.state.settings = settings
    # 【关键】依赖链里的 `Depends(get_settings)` 用的是模块级单例，
    #          必须把工厂传入的 settings 覆盖进去，否则测试传参不生效
    application.dependency_overrides[get_settings] = lambda: settings
    application.add_middleware(ObserveMiddleware, version=settings.version, slow_ms=settings.slow_ms)
    install_error_handlers(application)
    application.include_router(v1_router, prefix=settings.api_prefix)

    @application.get("/healthz", tags=["诊断"], summary="存活探针")
    def healthz() -> dict[str, str]:
        """不查库：库抖动不该触发重启"""
        return {"status": "ok", "version": settings.version}

    return application


app = create_app()