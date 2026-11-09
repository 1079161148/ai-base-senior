"""统一异常与错误响应格式。

**为什么要做这件事**：
FastAPI 默认的 422 校验错误长这样：
    {"detail": [{"loc": ["body","title"], "msg": "String should have at least 1 character", ...}]}

而 404 长这样：
    {"detail": "Not Found"}

前端要写两套解析逻辑。统一成
    {"code": "...", "message": "...", "detail": ...}
之后，前端只需要看 `code`。
"""

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger(__name__)

# 常见状态码 → 语义化 code。
# 前端可以只认字符串，不必关心数字；数字留给 HTTP 协议本身。
_HTTP_CODES: dict[int, str] = {
    400: "BAD_REQUEST",
    401: "UNAUTHORIZED",
    403: "FORBIDDEN",
    404: "NOT_FOUND",
    405: "METHOD_NOT_ALLOWED",
    408: "REQUEST_TIMEOUT",
    409: "CONFLICT",
    413: "PAYLOAD_TOO_LARGE",
    422: "VALIDATION_ERROR",
    429: "TOO_MANY_REQUESTS",
}


def _http_code(status_code: int) -> str:
    return _HTTP_CODES.get(status_code, f"HTTP_{status_code}")


class ApiError(Exception):
    """业务异常。

    用法：业务层直接 `raise ApiError(404, "TODO_NOT_FOUND", "...")`，
    不需要 import FastAPI 的 HTTPException —— 业务代码不依赖 Web 框架。
    """

    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def error_body(code: str, message: str, detail: Any = None) -> dict[str, Any]:
    return {"code": code, "message": message, "detail": detail}


def register_exception_handlers(app: FastAPI) -> None:
    """把异常转成统一 JSON。在 create_app 里调用一次。"""

    @app.exception_handler(ApiError)
    async def handle_api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(exc.code, exc.message),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(_: Request, exc: StarletteHTTPException) -> JSONResponse:
        """兜住框架层抛出的 HTTPException。

        不注册这个 handler 的话，下面这些会绕过统一格式：
            访问不存在的路由   → {"detail": "Not Found"}
            方法不允许         → {"detail": "Method Not Allowed"}
            raise HTTPException → {"detail": "..."}
        前端就得为「业务错误」和「框架错误」各写一套解析。

        注意：FastAPI 的 HTTPException 继承自 Starlette 的同名类，
        注册父类即可同时覆盖两者，不需要写两次。
        """
        message = exc.detail if isinstance(exc.detail, str) else _http_code(exc.status_code)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(_http_code(exc.status_code), message),
            # 401 的 WWW-Authenticate、413 的 Retry-After 等协议头必须原样透传
            headers=getattr(exc, "headers", None),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        """最后一道防线：任何没被上面接住的异常，统一变成 500。

        两个关键点：
        1. **绝不能把堆栈/异常信息返回给客户端** —— 会泄露表名、路径、内部结构
        2. **必须记日志** —— 否则线上 500 就成了"用户说报错了，但我们什么都查不到"
        """
        logger.exception("未捕获异常: %s", exc)
        return JSONResponse(
            status_code=500,
            content=error_body("INTERNAL_ERROR", "服务器内部错误，请稍后重试"),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        # jsonable_encoder：exc.errors() 里可能含 ValueError 等非 JSON 原生类型，直接塞会 500
        return JSONResponse(
            status_code=422,
            content=error_body("VALIDATION_ERROR", "请求参数不合法", jsonable_encoder(exc.errors())),
        )
