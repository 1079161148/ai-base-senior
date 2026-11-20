"""统一错误契约（与第 77 章同构，新增 `AppError` 的日志记录）。"""

import logging
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.error")


class AppError(Exception):
    """领域错误：`code` 稳定，`details` 结构化"""

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
    fields = [
        {
            "loc": ".".join(str(part) for part in error["loc"]),
            "type": error["type"],
            "msg": error["msg"],
        }
        for error in exc.errors()
    ]
    return JSONResponse(
        error_body("validation_error", "请求参数不合法", {"fields": fields}),
        status_code=422,
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    # 【要点】业务错误也记日志，否则线上只能看到 4xx，看不到业务原因
    logger.warning(
        "domain error code=%s path=%s",
        exc.code,
        request.url.path,
        extra={"request_id": getattr(request.state, "request_id", "-")},
    )
    return JSONResponse(error_body(exc.code, exc.message, exc.details), status_code=exc.status_code)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """【要点】800 只回通用文案，堆栈由中间件/日志记录（5xx 才有堆栈）"""
    return JSONResponse(
        error_body("internal_error", "服务内部错误，请稍后重试"),
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
    )


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)