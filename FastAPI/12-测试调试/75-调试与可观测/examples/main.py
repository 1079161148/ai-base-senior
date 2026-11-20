"""第 75 章 · 调试与可观测。

三条实践，按性价比排序：

    1. 每个请求一行结构化日志（方法/路径/状态/耗时/请求 ID）
    2. 请求 ID 从入口透传到响应头与日志（跨服务排障的唯一线索）
    3. `openapi()` 当契约快照：路径或 operationId 变了就该有人 review

【要点】日志里**永远不要**打印 password/token/authorization。
        本文件的 `sanitize()` 用一个最简名单演示。

启动：uvicorn main:app --reload --log-level info
验收：python verify.py
或：  uv run pytest -q
"""

import logging
import time
import uuid
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

LOGGER = logging.getLogger("app.request")
SLOW_MS = 50

SENSITIVE_KEYS = {"password", "token", "secret", "authorization"}


def sanitize(payload: dict[str, Any]) -> dict[str, Any]:
    """【要点】记录请求体前先脱敏，别把密码写进日志"""
    return {
        key: ("***" if key.lower() in SENSITIVE_KEYS else value)
        for key, value in payload.items()
    }


app = FastAPI(title="第 75 章 · 调试与可观测", version="0.1.0")


@app.middleware("http")
async def observe(request: Request, call_next):
    """【作用】请求 ID + 耗时 + 一行日志 + 异常兜底"""
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:8]
    request.state.request_id = request_id
    started = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        elapsed = (time.perf_counter() - started) * 1000
        LOGGER.exception(
            "request failed method=%s path=%s elapsed_ms=%.2f",
            request.method,
            request.url.path,
            elapsed,
            extra={"request_id": request_id},
        )
        response = JSONResponse(
            {"detail": "internal server error", "request_id": request_id},
            status_code=500,
        )

    elapsed = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Elapsed-Ms"] = f"{elapsed:.2f}"

    level = logging.WARNING if elapsed >= SLOW_MS else logging.INFO
    LOGGER.log(
        level,
        "request method=%s path=%s status=%s elapsed_ms=%.2f",
        request.method,
        request.url.path,
        response.status_code,
        elapsed,
        extra={"request_id": request_id},
    )
    return response


@app.get("/items", tags=["业务"], summary="普通接口")
def list_items(limit: int = 10) -> dict[str, Any]:
    return {"items": [{"id": index} for index in range(limit)]}


@app.get("/slow", tags=["业务"], summary="慢接口（触发 WARNING）")
def slow(ms: int = 100) -> dict[str, int]:
    time.sleep(ms / 1000)
    return {"slept": ms}


@app.post("/login", tags=["业务"], summary="登录（日志脱敏）")
def login(payload: dict[str, Any]) -> dict[str, str]:
    LOGGER.info("login payload=%s", sanitize(payload), extra={"request_id": "-"})
    return {"status": "ok"}


@app.get("/boom", tags=["演示"], summary="故意抛异常")
def boom() -> dict[str, str]:
    raise RuntimeError("内部炸了")


@app.get("/missing", tags=["演示"], summary="404")
def missing() -> dict[str, str]:
    raise HTTPException(status_code=404, detail="not here")


# ============================================================
# 反例：debug=True 会把 traceback 暴露给客户端
# ============================================================
debug_app = FastAPI(title="debug 模式", debug=True)


@debug_app.get("/boom")
def debug_boom() -> dict[str, str]:
    raise RuntimeError("debug 模式下的异常")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000, log_level="info")