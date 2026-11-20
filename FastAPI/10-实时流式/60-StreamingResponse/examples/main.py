"""第 60 章 · StreamingResponse。

核心：普通 `Response` 要在返回前**拼好整个 body**，`StreamingResponse` 则把
      「生成器」交给 ASGI，边产边发。代价是：
      - 没有 `Content-Length`（分块传输）
      - 响应一旦开始，状态码和头就改不了了
      - 生成器里抛异常只能截断，不能变 500

启动：uvicorn main:app --reload
验收：python verify.py
"""

import asyncio
from typing import AsyncIterator, Iterator

from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse

app = FastAPI(title="第 60 章 · StreamingResponse", version="0.1.0")

# 【作用】观测生成器生命周期：什么时候开始、什么时候关闭
EVENTS: list[str] = []

CHUNK_SIZE = 64 * 1024  # 64KB，常见的磁盘/网络块大小


# ============================================================
# 1. 同步生成器：Starlette 会丢进线程池迭代
# ============================================================
def csv_rows(total: int) -> Iterator[str]:
    yield "id,name,price\n"
    for i in range(total):
        yield f"{i},商品{i:04d},{i * 10}\n"


@app.get("/download/csv", tags=["流式"], summary="CSV 边生成边下载")
def download_csv(
    rows: int = Query(1_000, ge=1, le=200_000),
) -> StreamingResponse:
    """【实测】无 `Content-Length`，头里带 `Content-Disposition` 触发下载"""
    return StreamingResponse(
        csv_rows(rows),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="items.csv"'},
    )


def csv_rows_batched(total: int, batch: int = 1000) -> Iterator[str]:
    """【要点】攒够 `batch` 行再 yield 一次

    【实测】同步生成器每 yield 一次要走一趟线程池（约 0.37ms）：
            20 万行逐行 yield = 74 秒；每 1000 行一次 = 0.4 秒
    """
    yield "id,name,price\n"
    buffer: list[str] = []
    for i in range(total):
        buffer.append(f"{i},商品{i:04d},{i * 10}\n")
        if len(buffer) >= batch:
            yield "".join(buffer)
            buffer.clear()
    if buffer:
        yield "".join(buffer)


@app.get("/download/csv-batched", tags=["流式"], summary="批量 yield 的 CSV")
def download_csv_batched(
    rows: int = Query(200_000, ge=1, le=200_000),
    batch: int = Query(1_000, ge=1, le=10_000),
) -> StreamingResponse:
    """【对照】同样 20 万行，只产出 200 块，总耗时从 74 秒降到 0.4 秒"""
    return StreamingResponse(
        csv_rows_batched(rows, batch),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="items.csv"'},
    )


@app.get("/download/binary", tags=["流式"], summary="二进制流")
def download_binary(size: int = Query(1_000_000, ge=1, le=50_000_000)) -> StreamingResponse:
    """【要点】`bytes` 生成器直接发；分块大小自己定，别一次 yield 整个文件"""

    def chunks() -> Iterator[bytes]:
        remaining = size
        while remaining > 0:
            block = min(CHUNK_SIZE, remaining)
            yield b"\x00" * block
            remaining -= block

    return StreamingResponse(
        chunks(),
        media_type="application/octet-stream",
        headers={"Content-Disposition": 'attachment; filename="blob.bin"'},
    )


# ============================================================
# 2. 异步生成器：每块之间有 await，客户端能立刻收到
# ============================================================
@app.get("/stream/slow", tags=["流式"], summary="分块慢速推送")
async def stream_slow(
    chunks: int = Query(5, ge=1, le=20),
    delay_ms: int = Query(50, ge=0, le=1000),
) -> StreamingResponse:
    """【实测】`iter_raw()` 能观察到**逐块到达**，而不是等全部结束"""

    async def gen() -> AsyncIterator[str]:
        for index in range(chunks):
            yield f"chunk-{index}\n"
            await asyncio.sleep(delay_ms / 1000)

    return StreamingResponse(gen(), media_type="text/plain")


# ============================================================
# 3. 生命周期与清理
# ============================================================
async def tracked_gen() -> AsyncIterator[str]:
    """【作用】记录生成器的开始/产出/关闭，用于验证 `finally` 一定执行"""
    EVENTS.append("gen:start")
    try:
        for index in range(3):
            EVENTS.append(f"gen:yield:{index}")
            yield f"chunk-{index}\n"
            await asyncio.sleep(0.01)
    finally:
        EVENTS.append("gen:close")


@app.get("/stream/tracked", tags=["生命周期"], summary="观察生成器清理")
def stream_tracked() -> StreamingResponse:
    return StreamingResponse(tracked_gen(), media_type="text/plain")


@app.get("/events", tags=["生命周期"], summary="读取生成器事件")
def read_events() -> dict[str, list[str]]:
    return {"events": list(EVENTS)}


@app.delete("/events", tags=["生命周期"], summary="清空事件")
def clear_events() -> dict[str, int]:
    count = len(EVENTS)
    EVENTS.clear()
    return {"cleared": count}


# ============================================================
# 4. 中途异常：状态码已经发出去了
# ============================================================
async def broken_gen() -> AsyncIterator[str]:
    yield "part-1\n"
    yield "part-2\n"
    raise RuntimeError("第 3 块之前炸了")


@app.get("/stream/broken", tags=["边界"], summary="中途抛异常")
def stream_broken() -> StreamingResponse:
    """【实测】客户端收到 200 + 前两块，然后连接被截断；日志里才有异常"""
    return StreamingResponse(broken_gen(), media_type="text/plain")


@app.get("/stream/str-and-bytes", tags=["边界"], summary="str 与 bytes 混用")
def stream_mixed() -> StreamingResponse:
    """【实测】混用可以：`str` 会被 UTF-8 编码，`bytes` 原样发出"""

    async def gen() -> AsyncIterator[str | bytes]:
        yield "中文\n"
        yield b"raw-bytes\n"

    return StreamingResponse(gen(), media_type="text/plain")


# ============================================================
# 5. 头信息探针
# ============================================================
@app.get("/stream/headers", tags=["诊断"], summary="看流式响应的头")
def stream_headers() -> StreamingResponse:
    """【实测】没有 `Content-Length`；`Transfer-Encoding` 由服务器决定"""

    async def gen() -> AsyncIterator[str]:
        yield "hello\n"

    return StreamingResponse(gen(), media_type="text/plain")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)