"""可观测中间件：请求 ID + 耗时 + 一行日志 + 版本头。"""

import logging
import time
import uuid
from typing import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

logger = logging.getLogger("app.request")


class ObserveMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, *, version: str, slow_ms: int) -> None:
        super().__init__(app)
        self.version = version
        self.slow_ms = slow_ms

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:8]
        request.state.request_id = request_id
        started = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception:
            elapsed = (time.perf_counter() - started) * 1000
            logger.exception(
                "request failed method=%s path=%s elapsed_ms=%.2f",
                request.method,
                request.url.path,
                elapsed,
                extra={"request_id": request_id},
            )
            raise

        elapsed = (time.perf_counter() - started) * 1000
        response.headers["X-Request-ID"] = request_id
        response.headers["X-Elapsed-Ms"] = f"{elapsed:.2f}"
        response.headers["X-App-Version"] = self.version

        level = logging.WARNING if elapsed >= self.slow_ms else logging.INFO
        logger.log(
            level,
            "request method=%s path=%s status=%s elapsed_ms=%.2f",
            request.method,
            request.url.path,
            response.status_code,
            elapsed,
            extra={"request_id": request_id},
        )
        return response