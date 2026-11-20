"""积木 9 · 错误契约：把四种异常翻译成同一个信封。

    {"error": {"code": "...", "message": "...", "details": {...}}}
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.exceptions import AppError

logger = logging.getLogger("app.error")


def error_body(code: str, message: str, details: dict[str, Any] | None = None) -> dict[str, Any]:
    payload: dict[str, Any] = {"code": code, "message": message}
    if details:
        payload["details"] = details
    return {"error": payload}


def _code_for(status_code: int) -> str:
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
            exc.detail.get("code", _code_for(exc.status_code)),
            exc.detail.get("message", str(exc.detail)),
            exc.detail.get("details"),
        )
    else:
        body = error_body(_code_for(exc.status_code), str(exc.detail))
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
    return JSONResponse(error_body("validation_error", "请求参数不合法", {"fields": fields}), status_code=422)


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    logger.warning(
        "domain_error code=%s path=%s",
        exc.code,
        request.url.path,
        extra={"request_id": getattr(request.state, "request_id", "-")},
    )
    return JSONResponse(error_body(exc.code, exc.message, exc.details), status_code=exc.status_code)


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(error_body("internal_error", "服务内部错误，请稍后重试"), status_code=500)


def install_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(AppError, app_error_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)