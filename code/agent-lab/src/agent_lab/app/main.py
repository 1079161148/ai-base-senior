"""FastAPI 应用装配。

只做三件事：
1. 创建实例（含 lifespan 生命周期）
2. 挂中间件（CORS）
3. 挂路由（统一前缀）

业务逻辑一律不放这里。
"""

# collections.abc：标准库的「抽象基类」模块，定义 Iterator / Generator / AsyncGenerator 等协议。
#   这里只用于「类型标注」，运行时零开销 —— 相当于 TS 的 interface，只描述形状、不产生代码。
#   AsyncGenerator[Y, S]：Y = yield 出去的类型，S = send 传回来的类型；本文件两者都不用，故写 None, None。
from collections.abc import AsyncGenerator

# contextlib：标准库的上下文管理工具集（同模块还有 closing / suppress / ExitStack）。
#   asynccontextmanager：把一个「async def + yield」的生成器函数，包装成能被 `async with` 使用的上下文管理器，
#   等价于手写 __aenter__ / __aexit__ 的类，但代码量少一半（同步版叫 contextmanager）。
#   FastAPI 的 lifespan 参数要求的正是这种对象：
#     yield 之前 = 应用启动（建连接池、加载资源）
#     yield 之后 = 应用关闭（释放资源，保证一定执行）
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# 包内模块用「显式」相对导入：`.` 即当前包 agent_lab.app
# 注意：uvicorn 入口仍写绝对路径 agent_lab.app.main:app（从包外进入），本文件不受影响
from .api.v1.router import api_router
from .core.config import settings
from .core.db import init_db
from .core.docs import setup_docs
from .core.errors import register_exception_handlers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:  # pyright: ignore[reportUnusedParameter]
    """生命周期：yield 之前是启动，之后是关闭。

    用 lifespan 而不是 @app.on_event("startup")，
    因为 on_event 已废弃，且 lifespan 能保证关闭逻辑一定执行。

    返回类型用 AsyncGenerator 而不是 AsyncIterator：
    asynccontextmanager 要求被装饰的生成器支持 asend/athrow，
    AsyncIterator 没有这两个方法，新版类型检查器会判为弃用。

    `app` 是 FastAPI 协议要求的入参（框架按位置传入），
    本阶段暂时用不到，故用 pyright ignore 标注，而不是删掉它。
    """
    # --- 启动 ---
    # 建库建表：放在这里而不是模块导入时，是为了让「导入本模块」不产生副作用
    # （测试、脚本、CLI 都能安全 import，不会顺手建一堆文件）
    await init_db()
    # S1 起：在这里初始化 HTTP 客户端（httpx.AsyncClient）
    # S3 起：在这里建数据库连接池
    # S4 起：在这里加载记忆存储
    yield
    # --- 关闭 ---
    # 对应上面申请的资源，务必在这里释放，否则进程退出时连接会泄漏


def create_app() -> FastAPI:
    """工厂函数。

    用工厂而不是模块级直接建 app，好处是测试里能造多个独立实例：
        app = create_app()
        TestClient(app)
    """
    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        description="Agent 学习项目 · 从直连 LLM 到可上线的 Agent",
        lifespan=lifespan,
        docs_url=None,  # 关掉自带的，改由 core/docs.py 生成（要指向本地静态资源）
        redoc_url=None,  # 同样关掉，用自带中文版
        openapi_url=f"{settings.API_V1_PREFIX}/openapi.json",
        # Swagger UI 的行为参数。默认配置会让每个接口都展开成一大坨，
        # 接口一多就翻不动，这几项是最影响体验的。
        swagger_ui_parameters={
            "docExpansion": "list",  # 只列路径，点开才展开详情
            "defaultModelsExpandDepth": 0,  # 收起底部长长的 Schemas
            "displayRequestDuration": True,  # 显示每个请求耗时（调性能很有用）
            "filter": True,  # 顶部搜索框
            "persistAuthorization": True,  # 刷新页面不丢 token（S1 加鉴权后很重要）
            "tryItOutEnabled": True,  # 打开就能填参数，少点一次
        },
    )

    # --- 中间件 ---
    # 注意顺序：先 add 的后执行（洋葱模型），CORS 要尽量靠外层
    app.add_middleware(
        middleware_class=CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- 路由 ---
    # 只挂一个汇总 router，新增模块去 api/v1/router.py 里改
    app.include_router(api_router, prefix=settings.API_V1_PREFIX)

    # --- 异常 ---
    # 让业务异常与参数校验错误都输出统一格式 {code, message, detail}
    register_exception_handlers(app)

    # --- 文档 ---
    # /docs 由 FastAPI 自带；这里再挂 /scalar（颜值）和 /redoc（阅读）
    setup_docs(app, title=settings.PROJECT_NAME, openapi_url=app.openapi_url or "")

    @app.get("/", include_in_schema=False)
    async def root() -> dict[str, str]:
        return {
            "name": settings.PROJECT_NAME,
            "version": settings.VERSION,
            "docs": "/docs",
            "docs_scalar": "/scalar",
            "docs_redoc": "/redoc",
            "openapi": app.openapi_url or "",
            "health": f"{settings.API_V1_PREFIX}/health",
        }

    return app


app = create_app()
