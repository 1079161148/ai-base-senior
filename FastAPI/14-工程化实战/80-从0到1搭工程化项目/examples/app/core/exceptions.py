"""积木 8 · 领域异常：不依赖 FastAPI，服务层可以放心抛。

【原则】异常分两层：
        - `AppError`（这里）：业务语义，纯 Python，可被 service 抛
        - HTTP 处理器（errors.py）：把 `AppError` 翻译成状态码 + 响应体
"""

from typing import Any


class AppError(Exception):
    def __init__(
        self,
        code: str,
        message: str,
        status_code: int = 400,
        details: dict[str, Any] | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code
        self.details = details


class NotFound(AppError):
    def __init__(self, what: str, key: object) -> None:
        super().__init__("not_found", f"{what} {key} 不存在", 404)


class DuplicateTitle(AppError):
    def __init__(self, title: str) -> None:
        super().__init__("duplicate_title", f"标题已存在：{title}", 409)