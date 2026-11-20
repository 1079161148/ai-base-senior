"""第 61 章 · JSON Lines 流（NDJSON）。

核心：一个 JSON 数组必须**整体**解析，客户端要等最后一个 `]` 才能处理第一条。
      JSON Lines 每行一个独立 JSON 对象，客户端来一行处理一行。

对比：
      JSON 数组  `[{"id":1},{"id":2}]`        → 1 行、一次性
      JSON Lines `{"id":1}\\n{"id":2}\\n`      → N 行、逐条

启动：uvicorn main:app --reload
验收：python verify.py
"""

import asyncio
import json
from typing import AsyncIterator, Any

from fastapi import FastAPI, Query
from fastapi.responses import StreamingResponse

app = FastAPI(title="第 61 章 · JSON Lines 流", version="0.1.0")

TOTAL_RESULTS = 200

# 【要点】社区事实标准是 `application/x-ndjson`；
#         FastAPI 官方教程用 `application/jsonl`，两者都能用，选一个别混
MEDIA_TYPE = "application/jsonl"


def make_results(total: int) -> list[dict[str, Any]]:
    return [
        {
            "id": index,
            "title": f"结果 {index:03d}",
            "score": round(1 - index / (total + 1), 4),
        }
        for index in range(1, total + 1)
    ]


def to_line(item: dict[str, Any]) -> str:
    """【要点】`ensure_ascii=False` 让中文原样输出，体积小一半

    【注意】行内不能有裸换行——`json.dumps` 会把 `\\n` 转义成 `\\\\n`，天然安全
    """
    return json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n"


# ============================================================
# 1. 对照组：普通 JSON 数组
# ============================================================
@app.get("/search/json", tags=["对比"], summary="普通 JSON 数组（一次性）")
def search_json(limit: int = Query(20, ge=1, le=TOTAL_RESULTS)) -> list[dict[str, Any]]:
    """【实测】整个 body 只有 1 行，客户端必须等全部收完才能解析"""
    return make_results(limit)


# ============================================================
# 2. JSON Lines：逐行推送
# ============================================================
@app.get("/search/jsonl", tags=["JSONL"], summary="逐行推送")
def search_jsonl(
    limit: int = Query(20, ge=1, le=TOTAL_RESULTS),
    delay_ms: int = Query(0, ge=0, le=1000, description="每行之间的间隔，用于观察流式"),
) -> StreamingResponse:
    """【实测】`Content-Type: application/jsonl`，无 `Content-Length`"""

    async def gen() -> AsyncIterator[str]:
        for item in make_results(limit):
            yield to_line(item)
            if delay_ms:
                await asyncio.sleep(delay_ms / 1000)

    return StreamingResponse(gen(), media_type=MEDIA_TYPE)


# ============================================================
# 3. 中途出错：状态码改不了，只能发一行错误
# ============================================================
@app.get("/search/jsonl/broken", tags=["边界"], summary="中途抛异常")
def search_jsonl_broken(limit: int = Query(5, ge=1, le=10)) -> StreamingResponse:
    """【实测】客户端拿到 200 + 部分行，然后连接截断"""

    async def gen() -> AsyncIterator[str]:
        for item in make_results(limit):
            if item["id"] > 3:
                raise RuntimeError("索引在第 4 条之后崩了")
            yield to_line(item)

    return StreamingResponse(gen(), media_type=MEDIA_TYPE)


@app.get("/search/jsonl/error-line", tags=["边界"], summary="用一行表达错误")
def search_jsonl_error_line(limit: int = Query(5, ge=1, le=10)) -> StreamingResponse:
    """【推荐】错误也当成一条记录发出去，客户端按 `error` 字段分流"""

    async def gen() -> AsyncIterator[str]:
        for item in make_results(limit):
            if item["id"] > 3:
                yield to_line({"error": "索引在第 4 条之后不可用", "code": "INDEX_DOWN"})
                return
            yield to_line(item)

    return StreamingResponse(gen(), media_type=MEDIA_TYPE)


# ============================================================
# 4. 探针
# ============================================================
@app.get("/search/jsonl/headers", tags=["诊断"], summary="看响应头")
def headers_probe() -> StreamingResponse:
    async def gen() -> AsyncIterator[str]:
        yield to_line({"ok": True})

    return StreamingResponse(
        gen(),
        media_type=MEDIA_TYPE,
        headers={"X-Accel-Buffering": "no", "Cache-Control": "no-cache"},
    )


@app.get("/config", tags=["诊断"], summary="本章参数")
def config() -> dict[str, Any]:
    return {"total_results": TOTAL_RESULTS, "media_type": MEDIA_TYPE}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)