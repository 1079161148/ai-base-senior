"""第 72 章 · 异步测试。

同步的 `TestClient` 已经能测异步端点（它内部起 portal 线程跑事件循环）。
什么时候必须换 `httpx.AsyncClient` + `ASGITransport`？

    1. 测试本身就要 `await`（并发、异步 fixture、异步数据库）
    2. 要断言「并发真的并发」
    3. 要测异步依赖/异步生成器的副作用

【要点】`ASGITransport(app)` 不开端口，直接把请求交给 app；
        `LifespanManager` 负责在异步上下文里手动跑 lifespan。

启动：uvicorn main:app --reload
验收：python verify.py
或：  uv run pytest -q
"""

import asyncio
from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Query
from pydantic import BaseModel, Field

STATE: dict[str, Any] = {"started": False, "calls": 0}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    STATE["started"] = True
    app.state.started = True
    try:
        yield
    finally:
        STATE["started"] = False
        app.state.started = False


app = FastAPI(title="第 72 章 · 异步测试", version="0.1.0", lifespan=lifespan)

ITEMS: dict[int, dict[str, Any]] = {1: {"id": 1, "name": "键盘"}}


class Payload(BaseModel):
    name: str = Field(min_length=1)


@app.get("/state", tags=["诊断"], summary="lifespan 是否跑过")
async def read_state() -> dict[str, bool]:
    return {"started": bool(STATE["started"])}


@app.get("/calls", tags=["诊断"], summary="累计调用次数")
async def read_calls() -> dict[str, int]:
    return {"calls": STATE["calls"]}


@app.get("/items", tags=["商品"], summary="异步列表")
async def list_items(
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[dict[str, Any]]:
    STATE["calls"] += 1
    await asyncio.sleep(0)  # 强制让出一次，模拟真实 await 点
    return list(ITEMS.values())[:limit]


@app.get("/items/{item_id}", tags=["商品"], summary="异步详情")
async def read_item(item_id: int) -> dict[str, Any]:
    item = ITEMS.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="item not found")
    return item


@app.get("/slow", tags=["演示"], summary="可控耗时")
async def slow(ms: Annotated[int, Query(ge=1, le=1_000)] = 100) -> dict[str, int]:
    """【关键】并发测试的靶子：3 个 100ms 请求并发应 ≈ 100ms，串行 ≈ 300ms"""
    await asyncio.sleep(ms / 1000)
    return {"slept": ms}


@app.post("/echo", tags=["演示"], summary="回显 body")
async def echo(payload: Payload) -> Payload:
    return payload


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)