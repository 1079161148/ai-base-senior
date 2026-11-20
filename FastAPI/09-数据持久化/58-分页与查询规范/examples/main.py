"""第 58 章 · 分页与查询规范。

核心：`LIMIT/OFFSET` 的分页成本是 O(offset)——翻到第 5000 页要先扫 10 万行。
      游标（keyset）分页把「跳过」变成「定位」，靠 `(created_at, id)` 复合索引
      做到每页成本恒定。代价是只能顺序翻页、不能跳页。

启动：uvicorn main:app --reload
验收：python verify.py
"""

import statistics
import sqlite3
import time
from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncIterator

from fastapi import Depends, FastAPI, HTTPException, Query
from pydantic import BaseModel

from db import TOTAL_ROWS, connect, init_db, get_db

# ============================================================
# 查询语句集中在一处，便于 EXPLAIN 与复用
# ============================================================
OFFSET_SQL = """
SELECT id, created_at, title, level
FROM events
ORDER BY created_at DESC, id DESC
LIMIT ? OFFSET ?
"""

KEYSET_SQL = """
SELECT id, created_at, title, level
FROM events
WHERE (created_at, id) < (?, ?)
ORDER BY created_at DESC, id DESC
LIMIT ?
"""

KEYSET_FIRST_SQL = """
SELECT id, created_at, title, level
FROM events
ORDER BY created_at DESC, id DESC
LIMIT ?
"""

# 【对照】按无索引的 `level` 排序 → 必然走临时 B 树
SORT_BY_UNINDEXED_SQL = "SELECT id FROM events ORDER BY level LIMIT ?"

SORT_BY_INDEXED_SQL = """
SELECT id, created_at, title, level
FROM events
ORDER BY created_at DESC, id DESC
LIMIT ?
"""


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="第 58 章 · 分页与查询规范", version="0.1.0", lifespan=lifespan)


class Event(BaseModel):
    id: int
    created_at: str
    title: str
    level: str


class OffsetPage(BaseModel):
    items: list[Event]
    total: int
    offset: int
    limit: int
    has_more: bool


class CursorPage(BaseModel):
    items: list[Event]
    next_cursor: str | None
    has_more: bool


def encode_cursor(created_at: str, event_id: int) -> str:
    """【要点】游标必须包含**排序键的全部字段**，否则同时间戳会跳过/重复

    【注意】生产应 base64 + 签名，防止客户端篡改导致越权读取
    """
    return f"{created_at}|{event_id}"


def decode_cursor(cursor: str) -> tuple[str, int]:
    try:
        created_at, raw_id = cursor.rsplit("|", 1)
        return created_at, int(raw_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="游标格式错误") from exc


DbDep = Annotated[sqlite3.Connection, Depends(get_db)]


# ============================================================
# 1. 偏移分页：能跳页，深页慢
# ============================================================
@app.get("/events", response_model=OffsetPage, tags=["分页"], summary="偏移分页")
def list_by_offset(
    conn: DbDep,
    limit: Annotated[int, Query(ge=1, le=100, description="每页条数，上限 100")] = 20,
    offset: Annotated[int, Query(ge=0, description="跳过多少条")] = 0,
) -> OffsetPage:
    """【实测】`offset=99980` 要先扫过 99980 行，耗时随 offset 线性增长"""
    rows = conn.execute(OFFSET_SQL, (limit, offset)).fetchall()
    total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    return OffsetPage(
        items=[Event(**dict(row)) for row in rows],
        total=int(total),
        offset=offset,
        limit=limit,
        has_more=offset + len(rows) < int(total),
    )


# ============================================================
# 2. 游标分页：深页恒定，只能顺序翻
# ============================================================
@app.get("/events/cursor", response_model=CursorPage, tags=["分页"], summary="游标分页")
def list_by_cursor(
    conn: DbDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    cursor: Annotated[str | None, Query(description="上一页返回的 next_cursor")] = None,
) -> CursorPage:
    """【实测】首页走 `LIMIT`，翻页走 `WHERE (created_at, id) < (?, ?)`

    【要点】多取 1 条判断 `has_more`，省一次 `COUNT(*)`
    """
    if cursor is None:
        rows = conn.execute(KEYSET_FIRST_SQL, (limit + 1,)).fetchall()
    else:
        created_at, event_id = decode_cursor(cursor)
        rows = conn.execute(KEYSET_SQL, (created_at, event_id, limit + 1)).fetchall()

    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = encode_cursor(page[-1]["created_at"], page[-1]["id"]) if has_more and page else None
    return CursorPage(
        items=[Event(**dict(row)) for row in page],
        next_cursor=next_cursor,
        has_more=has_more,
    )


# ============================================================
# 3. EXPLAIN 探针：让「走没走索引」可验证
# ============================================================
@app.get("/events/explain", tags=["诊断"], summary="看执行计划")
def explain(
    conn: DbDep,
    mode: Annotated[str, Query(pattern="^(indexed|unindexed|offset)$")] = "indexed",
) -> dict[str, list[dict[str, Any]]]:
    """【实测】`indexed` → `SEARCH events USING INDEX`；
    `unindexed` → `SCAN events` + `USE TEMP B-TREE FOR ORDER BY`
    """
    if mode == "unindexed":
        sql, params = SORT_BY_UNINDEXED_SQL, (10,)
    elif mode == "offset":
        sql, params = OFFSET_SQL, (10, 90_000)
    else:
        sql, params = SORT_BY_INDEXED_SQL, (10,)

    rows = conn.execute(f"EXPLAIN QUERY PLAN {sql}", params).fetchall()
    return {"plan": [dict(row) for row in rows]}


# ============================================================
# 4. 基准：首页 vs 深页、偏移 vs 游标、COUNT(*)
# ============================================================
def _median_ms(conn: sqlite3.Connection, sql: str, params: tuple[Any, ...], runs: int = 5) -> float:
    samples: list[float] = []
    for _ in range(runs):
        started = time.perf_counter()
        conn.execute(sql, params).fetchall()
        samples.append((time.perf_counter() - started) * 1000)
    return round(statistics.median(samples), 3)


@app.get("/events/benchmark", tags=["诊断"], summary="耗时对比（中位数）")
def benchmark(conn: DbDep) -> dict[str, Any]:
    """【实测】10 万行下，深页 `OFFSET` 比首页慢一个数量级以上，游标恒定"""
    deep_offset = 99_000
    deep = conn.execute(
        "SELECT created_at, id FROM events ORDER BY created_at DESC, id DESC LIMIT 1 OFFSET ?",
        (deep_offset,),
    ).fetchone()

    return {
        "rows": TOTAL_ROWS,
        "offset_first_ms": _median_ms(conn, OFFSET_SQL, (20, 0)),
        "offset_deep_ms": _median_ms(conn, OFFSET_SQL, (20, deep_offset)),
        "keyset_first_ms": _median_ms(conn, KEYSET_FIRST_SQL, (20,)),
        "keyset_deep_ms": _median_ms(conn, KEYSET_SQL, (deep["created_at"], deep["id"], 20)),
        "count_ms": _median_ms(conn, "SELECT COUNT(*) FROM events", ()),
        "deep_cursor_sample": encode_cursor(deep["created_at"], deep["id"]),
    }


@app.get("/events/stats", tags=["诊断"], summary="行数与索引清单")
def stats(conn: DbDep) -> dict[str, Any]:
    total = conn.execute("SELECT COUNT(*) FROM events").fetchone()[0]
    indexes = [
        row["name"]
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name = 'events'"
        ).fetchall()
    ]
    return {"rows": int(total), "indexes": indexes}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)