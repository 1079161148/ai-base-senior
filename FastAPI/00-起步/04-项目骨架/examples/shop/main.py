"""应用入口：只做「装配」，不写业务。

启动（在 examples 目录下）：
    uvicorn shop.main:app --reload

三层前缀叠加结果：
    main.py 的 /api  +  router.py 的 /v1  +  items.py 的 /items  =  /api/v1/items
"""

from __future__ import annotations

from fastapi import FastAPI

from .api.v1.router import api_router
from .core.config import settings


def create_app() -> FastAPI:
    """应用工厂。

    【为什么用工厂函数】测试时可以传入不同配置、单独构造一个干净实例，
           避免多个测试共享同一个 app 的全局状态（第 73 章会用上）。
    【注意】工厂函数本身不是 ASGI 应用，必须调用后拿到返回值；
           若想直接 `uvicorn shop.main:create_app --factory`，也可以。
    """
    application = FastAPI(
        title=f"{settings.app_name} API",
        version=settings.app_version,
        debug=settings.debug,
        # 【作用】文档地址带上版本前缀，避免与前端静态资源抢占 /docs
        docs_url="/docs",
        openapi_url="/openapi.json",
    )

    # 【作用】把聚合好的 v1 路由挂到 /api 下
    # 【注意】prefix 不能以 `/` 结尾；tags 会与子 router 的 tags 叠加
    application.include_router(api_router, prefix=settings.api_prefix)

    @application.get("/health", tags=["运维"], summary="健康检查")
    def health() -> dict[str, str]:
        """健康检查放在 main.py：它不属于任何业务资源，且永远不该被版本化。"""
        return {"status": "ok", "env": settings.env}

    return application


# 【作用】模块级单例，供 uvicorn 以 "shop.main:app" 字符串定位
# 【注意】必须是模块级；写在函数里会报 Could not import module
app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
