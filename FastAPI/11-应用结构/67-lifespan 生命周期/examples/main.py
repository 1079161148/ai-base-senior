"""第 67 章 · lifespan 生命周期。

一个 `@asynccontextmanager` 同时管「启动」和「关闭」：

    @asynccontextmanager
    async def lifespan(app):
        启动代码（yield 之前）
        try:
            yield
        finally:
            关闭代码（yield 之后）

【要点】`yield` 之前的异常会让**应用启动失败**（不会有人访问到）；
        `yield` 之后的异常发生在关闭阶段，响应早已发完。

启动：uvicorn main:app --reload
验收：python verify.py
"""

import asyncio
import time
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI, Request

# 【作用】全局事件流，验收时按顺序断言
EVENTS: list[str] = []


def mark(name: str) -> None:
    EVENTS.append(name)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """【实测】`with TestClient(app)` 进入时跑前半段，退出时跑后半段"""
    mark("startup:begin")
    # 【要点】启动阶段可以做真正的 await：读文件、连数据库、预热缓存
    await asyncio.sleep(0.01)
    app.state.cache = {"warmed": True, "rows": list(range(5))}
    app.state.started_at = time.time()
    mark("startup:end")
    try:
        yield
    finally:
        # 【要点】关闭必须放 finally，否则异常退出时资源泄漏
        mark("shutdown:begin")
        app.state.cache.clear()
        await asyncio.sleep(0.005)
        mark("shutdown:end")


app = FastAPI(title="第 67 章 · lifespan 生命周期", version="0.1.0", lifespan=lifespan)


@app.get("/ping", tags=["生命周期"], summary="证明资源已预热")
def ping(request: Request) -> dict[str, Any]:
    cache = request.app.state.cache
    return {
        "warmed": cache.get("warmed", False),
        "rows": len(cache.get("rows", [])),
        "uptime_ms": round((time.time() - request.app.state.started_at) * 1000, 1),
    }


@app.get("/events", tags=["生命周期"], summary="读取事件流")
def read_events() -> dict[str, list[str]]:
    return {"events": list(EVENTS)}


@app.delete("/events", tags=["生命周期"], summary="清空事件")
def clear_events() -> dict[str, int]:
    count = len(EVENTS)
    EVENTS.clear()
    return {"cleared": count}


# ============================================================
# 反例一：启动失败
# ============================================================
@asynccontextmanager
async def failing_lifespan(app: FastAPI) -> AsyncIterator[None]:
    mark("failing:startup")
    raise RuntimeError("预热失败，服务不该起来")
    if False:  # noqa: SIM223 - 让函数仍是生成器
        yield


failing_app = FastAPI(lifespan=failing_lifespan)


@failing_app.get("/never")
def never() -> dict[str, str]:
    return {"never": "reached"}


# ============================================================
# 反例二：关闭阶段抛异常
# ============================================================
@asynccontextmanager
async def noisy_lifespan(app: FastAPI) -> AsyncIterator[None]:
    mark("noisy:startup")
    yield
    mark("noisy:shutdown-raise")
    raise RuntimeError("关闭时炸了")


noisy_app = FastAPI(lifespan=noisy_lifespan)


@noisy_app.get("/ok")
def ok() -> dict[str, str]:
    return {"ok": "true"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)