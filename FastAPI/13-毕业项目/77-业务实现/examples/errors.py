"""统一错误契约。

所有错误响应长这样：

    {"error": {"code": "not_found", "message": "...", "details": {...}}}

【要点】三类错误必须都覆盖，否则客户端会遇到两种格式：
    1. `HTTPException`  —— 业务主动抛（404/401/409）
    2. `RequestValidationError` —— 422 参数校验
    3. `Exception` —— 未捕获异常（500，不暴露内部细节）
"""

from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


class AppError(Exception):
    """业务错误：带稳定 `code`，供客户端分支判断"""

    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = status.HTTP_400_BAD_REQUEST,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    if details:
        payload["details"] = details
    return {"error": payload}


def _status_to_code(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
    }.get(status_code, "error")


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    """`detail` 允许是字符串，也允许是 {"code","message"} 字典"""
    if isinstance(exc.detail, dict):
        body = error_body(
            exc.detail.get("code", _status_to_code(exc.status_code)),
            exc.detail.get("message", str(exc.detail)),
            exc.detail.get("details"),
        )
    else:
        body = error_body(_status_to_code(exc.status_code), str(exc.detail))
    return JSONResponse(body, status_code=exc.status_code, headers=getattr(exc, "headers", None))


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    """把 pydantic 的 loc/type 收敛成 `details.fields`，客户端不用解析框架结构"""
    fields = [
        {
            "loc": ".".join(str(part) for part in error["loc"]),
            "type": error["type"],
            "msg": error["msg"],
        }
        for error in exc.errors()
    ]
    # 【要点】starlette 新版把 `HTTP_422_UNPROCESSABLE_ENTITY` 标了弃用，
    #          直接写 422 避免 DeprecationWarning
    return JSONResponse(
        error_body("validation_error", "请求参数不合法", {"fields": fields}),
        status_code=422,
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(error_body(exc.code, exc.message, exc.details), status_code=exc.status_code)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """【要点】只回通用文案，堆栈进日志；绝不把 `str(exc)` 返给客户端"""
    return JSONResponse(
        error_body("internal_error", "服务内部错误，请稍后重试"),
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)