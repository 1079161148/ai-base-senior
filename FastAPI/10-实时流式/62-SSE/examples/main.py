"""第 62 章 · SSE（Server-Sent Events）。

核心：SSE 就是「按格式写的纯文本流」：

    event: token        ← 可选，事件名，默认 message
    id: 3               ← 可选，浏览器记录为 lastEventId
    retry: 3000         ← 可选，断线后重连间隔（毫秒）
    data: {"a":1}       ← 必需，可多行
                        ← 空行表示事件结束

浏览器用 `EventSource` 自动重连，并把最后收到的 `id` 放进 `Last-Event-ID` 头。

启动：uvicorn main:app --reload
验收：python verify.py
"""

import asyncio
import json
from typing import Any, AsyncIterator

from fastapi import FastAPI, Query, Request
from fastapi.responses import StreamingResponse

app = FastAPI(title="第 62 章 · SSE", version="0.1.0")

SSE_HEADERS = {
    # 【要点】这三行缺一不可：不缓存、不缓冲、保持连接
    "Cache-Control": "no-cache",
    "X-Accel-Buffering": "no",
    "Connection": "keep-alive",
}


def sse_event(data: str, event: str | None = None, event_id: int | None = None) -> str:
    """【要点】事件以**空行**结束；`data` 可多行，客户端用 `\\n` 拼接"""
    lines: list[str] = []
    if event:
        lines.append(f"event: {event}")
    if event_id is not None:
        lines.append(f"id: {event_id}")
    for line in data.split("\n"):
        lines.append(f"data: {line}")
    return "\n".join(lines) + "\n\n"


# ============================================================
# 1. 打字机效果：逐 token 推送
# ============================================================
@app.get("/sse/chat", tags=["SSE"], summary="打字机：逐 token")
def chat(
    text: str = Query("你好，世界", max_length=200),
    delay_ms: int = Query(40, ge=0, le=1000),
) -> StreamingResponse:
    """【实测】`text/event-stream`，逐条到达，无 `Content-Length`"""

    async def gen() -> AsyncIterator[str]:
        for index, char in enumerate(text):
            yield sse_event(json.dumps({"index": index, "text": char}, ensure_ascii=False))
            if delay_ms:
                await asyncio.sleep(delay_ms / 1000)
        yield sse_event(json.dumps({"done": True}), event="done")

    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


# ============================================================
# 2. 自定义事件名
# ============================================================
@app.get("/sse/typed", tags=["SSE"], summary="自定义 event 名")
def typed() -> StreamingResponse:
    """【实测】客户端按 `event` 字段分流：`token` / `done` / `error`"""

    async def gen() -> AsyncIterator[str]:
        for index, char in enumerate("SSE"):
            yield sse_event(json.dumps({"text": char}), event="token", event_id=index + 1)
            await asyncio.sleep(0.02)
        yield sse_event(json.dumps({"ok": True}), event="done")

    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


# ============================================================
# 3. 断线续传：Last-Event-ID
# ============================================================
@app.get("/sse/events", tags=["SSE"], summary="带 id，支持断点续传")
def events(
    request: Request,
    total: int = Query(10, ge=1, le=100),
) -> StreamingResponse:
    """【要点】浏览器重连时自动带 `Last-Event-ID`，服务端据此跳过已发送的

    【实测】`Last-Event-ID: 3` → 从 `id=4` 开始
    """
    raw = request.headers.get("last-event-id")
    start = int(raw) + 1 if raw and raw.isdigit() else 1

    async def gen() -> AsyncIterator[str]:
        for sequence in range(start, total + 1):
            yield sse_event(
                json.dumps({"seq": sequence}, ensure_ascii=False),
                event_id=sequence,
            )
            await asyncio.sleep(0.01)

    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


# ============================================================
# 4. 心跳与多行 data
# ============================================================
@app.get("/sse/heartbeat", tags=["SSE"], summary="注释行心跳")
def heartbeat(beats: int = Query(2, ge=1, le=10)) -> StreamingResponse:
    """【要点】以 `:` 开头的行是注释，客户端**不会**产生事件，适合保活"""

    async def gen() -> AsyncIterator[str]:
        for index in range(beats):
            yield ": ping\n\n"  # 注释行，客户端忽略
            yield sse_event(json.dumps({"beat": index + 1}))
            await asyncio.sleep(0.02)

    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@app.get("/sse/multiline", tags=["SSE"], summary="多行 data")
def multiline() -> StreamingResponse:
    """【实测】多个 `data:` 行会被客户端拼成 `第一行\\n第二行`"""

    async def gen() -> AsyncIterator[str]:
        yield sse_event("第一行\n第二行")

    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


# ============================================================
# 5. 重连间隔与错误事件
# ============================================================
@app.get("/sse/retry", tags=["SSE"], summary="设置重连间隔")
def retry_probe() -> StreamingResponse:
    """【实测】`retry: 3000` 是**独立字段行**，不属于任何事件"""

    async def gen() -> AsyncIterator[str]:
        yield "retry: 3000\n\n"
        yield sse_event(json.dumps({"ok": True}, ensure_ascii=False))
        yield sse_event(
            json.dumps({"reason": "索引不可用"}, ensure_ascii=False), event="error"
        )

    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@app.get("/sse/broken", tags=["边界"], summary="中途抛异常")
def broken() -> StreamingResponse:
    """【实测】200 + 部分事件后连接断开；浏览器会按 `retry` 自动重连"""

    async def gen() -> AsyncIterator[str]:
        yield sse_event(json.dumps({"seq": 1}), event_id=1)
        yield sse_event(json.dumps({"seq": 2}), event_id=2)
        raise RuntimeError("第 3 条之前崩了")

    return StreamingResponse(gen(), media_type="text/event-stream", headers=SSE_HEADERS)


@app.get("/config", tags=["诊断"], summary="本章参数")
def config() -> dict[str, Any]:
    return {"media_type": "text/event-stream", "headers": SSE_HEADERS}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)