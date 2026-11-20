"""第 50 章 · 中间件基础。

核心：`@app.middleware("http")` + `await call_next(request)` 把「请求前/请求后」
      两段代码包在**路由之外**。多个中间件是**洋葱模型**，且 **后注册的在最外层**
      （实测：先执行的那个是最后注册的）。因为它包在路由之外，所以连 **404 和
      `/docs` 也会被处理**——这正是全局依赖做不到的（第 39 章实测）。

启动：uvicorn main:app --reload
验收：python verify.py
"""

import time
from typing import Annotated, Any

from fastapi import FastAPI, Header, HTTPException, Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware

app = FastAPI(title="第 50 章 · 中间件基础", version="0.1.0")

# 【作用】记录每个请求经过的中间件，供端点与响应头读取
# 【注意】生产不要用全局 list 存请求数据（并发会串），这里只为演示
TRACE: list[str] = []


def _trace(request: Request, item: str) -> None:
    """把一条记录同时写进 request.state 与全局 TRACE"""
    if not hasattr(request.state, "order"):
        request.state.order = []
    request.state.order.append(item)
    TRACE.append(item)


# ============================================================
# 1. 第一个注册 → 最内层（紧贴路由）
# ============================================================
@app.middleware("http")
async def m_inner(request: Request, call_next: Any) -> Any:
    _trace(request, "inner:before")
    response = await call_next(request)
    _trace(request, "inner:after")
    return response


# ============================================================
# 2. 第二个注册 → 中间层
# ============================================================
@app.middleware("http")
async def m_middle(request: Request, call_next: Any) -> Any:
    """【实测】`call_next` 之后能改 header，但改不了 body（body 已在流式发送）"""
    _trace(request, "middle:before")
    start = time.perf_counter()
    response = await call_next(request)
    elapsed_ms = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time"] = f"{elapsed_ms:.3f}ms"
    _trace(request, "middle:after")
    return response


# ============================================================
# 3. 第三个注册 → 外层：负责拼完整洋葱序列
# ============================================================
@app.middleware("http")
async def m_outer(request: Request, call_next: Any) -> Any:
    """【实测】`X-Order` 是 `outer:before,middle:before,inner:before,
    inner:after,middle:after,outer:after`——请求由外向内、响应由内向外
    """
    if not hasattr(request.state, "order"):
        request.state.order = []
    _trace(request, "outer:before")
    response = await call_next(request)
    _trace(request, "outer:after")
    response.headers["X-Order"] = ",".join(request.state.order)
    return response


# ============================================================
# 4. 异常兜底（注册得更晚 → 更外层）
# ============================================================
@app.middleware("http")
async def catch_errors(request: Request, call_next: Any) -> Any:
    """【实测】路由里抛的 `HTTPException` **不会**进这里（内层已转成响应），
    只有未捕获的普通异常会冒上来
    """
    try:
        return await call_next(request)
    except RuntimeError as exc:
        return JSONResponse(
            status_code=503,
            content={"detail": f"被中间件捕获：{exc}"},
            headers={"X-Caught": "1"},
        )


# ============================================================
# 5. 子类写法（`BaseHTTPMiddleware`）——最后注册 → 真正最外层
# ============================================================
class ServerHeaderMiddleware(BaseHTTPMiddleware):
    """【作用】给所有响应打 `X-Server-Name`

    【注意】`async def dispatch(request, call_next)` 是固定签名
    """

    def __init__(self, app: Any, server_name: str = "ch50") -> None:
        super().__init__(app)
        self.server_name = server_name

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers["X-Server-Name"] = self.server_name
        return response


app.add_middleware(ServerHeaderMiddleware, server_name="fastapi-ch50")


# ============================================================
# 6. 改 `scope["path"]` 影响路由匹配（进阶，慎用）
# ============================================================
@app.middleware("http")
async def rewrite_alias(request: Request, call_next: Any) -> Any:
    """【实测】路由匹配发生在内层，所以在这里改 `scope["path"]` 会改变命中结果

    【警告】生产用重写路由/网关，别在中间件里改路径——可读性极差且难调试
    """
    if request.scope["path"] == "/alias":
        request.scope["path"] = "/ping"
        request.scope["raw_path"] = b"/ping"
    return await call_next(request)


# ============================================================
# 端点
# ============================================================
@app.get("/ping", tags=["中间件"], summary="看中间件执行顺序")
def ping(request: Request) -> dict[str, Any]:
    """【实测】端点里只能看到各层的 `before`（内层 `after` 还没执行）"""
    return {"order": request.state.order, "trace": list(TRACE)}


@app.get("/slow", tags=["中间件"], summary="耗时接口")
def slow() -> dict[str, str]:
    time.sleep(0.02)
    return {"ok": "true"}


@app.get("/http-error", tags=["中间件"], summary="HTTPException 不进中间件")
def http_error() -> dict[str, str]:
    """【实测】中间件的 `except` 抓不到它，最终响应就是 418"""
    raise HTTPException(status_code=418, detail="我是茶壶")


@app.get("/boom", tags=["中间件"], summary="未捕获异常被中间件接住")
def boom() -> dict[str, str]:
    """【实测】`RuntimeError` 冒到最外层的 `catch_errors` → 503 + `X-Caught`"""
    raise RuntimeError("数据库连接失败")


@app.get("/need-header", tags=["中间件"], summary="422 也带中间件头")
def need_header(x_token: Annotated[str, Header()]) -> dict[str, str]:
    return {"token": x_token}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)