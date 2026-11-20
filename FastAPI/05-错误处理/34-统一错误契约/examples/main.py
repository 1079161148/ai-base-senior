"""第 34 章 · 统一错误契约（全局兜底 + trace_id）。

核心：所有失败路径——框架 404/405、`HTTPException`、业务异常、校验错误、未捕获异常——
      都输出同一个结构：`{code, message, trace_id, details?}`，并在响应头带 `X-Trace-Id`。
      客户端只需认一种结构；排障时拿 trace_id 就能在日志里定位整条链路。

启动：uvicorn main:app --reload
验收：python verify.py
"""

import logging
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.errors")

app = FastAPI(title="第 34 章 · 统一错误契约", version="0.1.0")


# ============================================================
# 1. 统一响应构造器：唯一出口
# ============================================================
def error_response(
    request: Request,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
    headers: dict[str, str] | None = None,
) -> JSONResponse:
    """【作用】所有处理器都调用它，保证字段集合永远一致

    【注意】`trace_id` 从 `request.state` 取，取不到时兜底生成一个，
           否则「最早期」的错误（如中间件前）会缺字段
    """
    trace_id = getattr(request.state, "trace_id", None) or uuid.uuid4().hex
    content: dict[str, Any] = {
        "code": code,
        "message": message,
        "trace_id": trace_id,
    }
    if details is not None:
        content["details"] = details

    logger.warning(
        "request failed",
        extra={"trace_id": trace_id, "path": request.url.path, "code": code, "status": status_code},
    )
    merged = {**(headers or {}), "X-Trace-Id": trace_id}
    return JSONResponse(status_code=status_code, content=content, headers=merged)


# ============================================================
# 2. trace_id 中间件：生成 / 沿用 / 回写响应头
# ============================================================
@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):  # noqa: ANN001, ANN201
    """【作用】优先沿用客户端 `X-Request-Id`，否则生成 uuid4

    【实测】请求头带 `X-Request-Id: abc` → 响应头 `x-trace-id: abc`，body 里也是 abc
    【注意】中间件里必须先把 id 写进 `request.state`，处理器才读得到
    """
    trace_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
    request.state.trace_id = trace_id
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    return response


# ============================================================
# 3. 路径一：框架的 404/405（StarletteHTTPException）
# ============================================================
@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """【作用】接管「路由不存在」「方法不允许」与所有 `HTTPException`

    【实测】`GET /no-such` → 404 `{code: "NOT_FOUND", message: "Not Found", trace_id}`
    【注意】`exc.detail` 可能是 str 也可能是 dict（第 31 章），这里统一转成 message
    """
    code_by_status = {
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        409: "CONFLICT",
        429: "TOO_MANY_REQUESTS",
    }
    code = code_by_status.get(exc.status_code, f"HTTP_{exc.status_code}")
    message = exc.detail if isinstance(exc.detail, str) else "请求失败"
    details = None if isinstance(exc.detail, str) else exc.detail
    return error_response(
        request,
        status_code=exc.status_code,
        code=code,
        message=message,
        details=details,
        headers=exc.headers,
    )


# ============================================================
# 4. 路径二：业务异常
# ============================================================
class AppError(Exception):
    code = "APP_ERROR"
    status_code = 500

    def __init__(self, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.message = message
        self.extra = extra


class OrderNotFound(AppError):
    code = "ORDER_NOT_FOUND"
    status_code = 404


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """【实测】`ORDER_NOT_FOUND` 进 `code`，额外字段进 `details`"""
    return error_response(
        request,
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.extra or None,
    )


# ============================================================
# 5. 路径三：校验错误（第 33 章的结构，套进统一契约）
# ============================================================
@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """【作用】422 也走同一个外壳，`details` 放字段级错误

    【实测】`{"code": "VALIDATION_ERROR", "message": "参数不合法", "trace_id": ..., "details": [...]}`
    """
    details = [
        {
            "field": ".".join(str(part) for part in error["loc"][1:]) or "body",
            "code": error["type"],
            "message": error["msg"],
        }
        for error in exc.errors()
    ]
    return error_response(
        request,
        status_code=422,
        code="VALIDATION_ERROR",
        message="参数不合法",
        details=details,
    )


# ============================================================
# 6. 路径四：全局兜底
# ============================================================
@app.exception_handler(Exception)
async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """【作用】最后一道网：任何未捕获异常 → 500 + trace_id

    【实测】body 不含异常类型与堆栈，只有 `{code: "INTERNAL_ERROR", ...}`
    【注意】必须 `logger.exception` 记录堆栈，否则错误永久丢失
    """
    logger.exception("unhandled error", extra={"trace_id": getattr(request.state, "trace_id", None)})
    return error_response(
        request,
        status_code=500,
        code="INTERNAL_ERROR",
        message="服务器内部错误，请携带 trace_id 联系支持",
    )


# ============================================================
# 7. 端点：制造四条错误路径
# ============================================================
@app.get("/orders/{order_id}", tags=["错误路径"], summary="业务异常 404")
def get_order(order_id: int) -> dict[str, Any]:
    """【实测】走 `AppError` 处理器，`code=ORDER_NOT_FOUND`"""
    if order_id != 1:
        raise OrderNotFound(f"订单 {order_id} 不存在", order_id=order_id)
    return {"id": 1, "sku": "KB-01"}


@app.get("/manual", tags=["错误路径"], summary="HTTPException 401")
def manual() -> dict[str, str]:
    """【实测】走 `StarletteHTTPException` 处理器，`code=UNAUTHORIZED` + challenge 头"""
    raise HTTPException(
        status_code=401,
        detail="需要登录",
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.get("/echo", tags=["错误路径"], summary="校验错误 422")
def echo(age: int) -> dict[str, int]:
    """【实测】`?age=abc` → 422 `VALIDATION_ERROR` + details"""
    return {"age": age}


@app.get("/crash", tags=["错误路径"], summary="未捕获异常 500")
def crash() -> dict[str, str]:
    """【实测】500 `INTERNAL_ERROR`，`trace_id` 与日志一致"""
    raise RuntimeError("假设是数据库连接断了")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)