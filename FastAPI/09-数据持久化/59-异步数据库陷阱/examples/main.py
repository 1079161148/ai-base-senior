"""第 59 章 · 异步数据库陷阱。

核心：事件循环是**单线程**的。任何在 `async def` 里做的阻塞调用
      （`sqlite3` 查询、`requests`、`time.sleep`、文件读）都会让整个进程
      停止响应。正确做法只有两条：
      1) `async def` + `await asyncio.to_thread(...)` 包裹阻塞调用
      2) 直接写 `def`（普通函数），FastAPI 自动放进线程池

启动：uvicorn main:app --reload
验收：python verify.py
"""

import asyncio
import os
import sqlite3
import threading
import time
from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncIterator

from fastapi import Depends, FastAPI, Query

from db import AUTHOR_COUNT, POST_COUNT, connect, init_db, get_db

# 【依据】asyncio 默认线程池上限：min(32, cpu_count + 4)
THREAD_POOL_LIMIT = min(32, (os.cpu_count() or 1) + 4)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    init_db()
    yield


app = FastAPI(title="第 59 章 · 异步数据库陷阱", version="0.1.0", lifespan=lifespan)


# ============================================================
# 1. 阻塞 vs 隔离：并发 5 个请求看总耗时
# ============================================================
@app.get("/blocking", tags=["阻塞"], summary="async def 里 time.sleep（错误）")
async def blocking(ms: Annotated[int, Query(ge=1, le=2000)] = 200) -> dict[str, Any]:
    """【实测】5 个并发请求串行执行，总耗时 ≈ 5 × ms"""
    time.sleep(ms / 1000)
    return {"mode": "blocking", "ms": ms}


@app.get("/threaded", tags=["阻塞"], summary="to_thread 隔离（正确）")
async def threaded(ms: Annotated[int, Query(ge=1, le=2000)] = 200) -> dict[str, Any]:
    """【实测】5 个并发请求并行，总耗时 ≈ ms"""
    await asyncio.to_thread(time.sleep, ms / 1000)
    return {"mode": "threaded", "ms": ms}


@app.get("/sync-def", tags=["阻塞"], summary="普通 def（FastAPI 自动进线程池）")
def sync_def(ms: Annotated[int, Query(ge=1, le=2000)] = 200) -> dict[str, Any]:
    """【要点】写 `def` 就够了，FastAPI 会把它丢进线程池——不用手写 `to_thread`"""
    time.sleep(ms / 1000)
    return {"mode": "sync-def", "ms": ms}


# ============================================================
# 2. 真实数据库慢查询：用自定义函数模拟
# ============================================================
def _slow_query(ms: int) -> None:
    """【作用】注册 `sleep_ms` 函数，让 SQL 真的慢——模拟「慢查询阻塞事件循环」"""
    conn = connect()
    try:
        conn.create_function("sleep_ms", 1, lambda value: time.sleep(value / 1000) or 1)
        conn.execute("SELECT sleep_ms(?)", (ms,)).fetchone()
    finally:
        conn.close()


@app.get("/db/slow", tags=["阻塞"], summary="慢 SQL：阻塞 vs 隔离")
async def db_slow(
    ms: Annotated[int, Query(ge=1, le=2000)] = 200,
    threaded: bool = False,
) -> dict[str, Any]:
    """【实测】`threaded=false` 时 5 个并发共 ~1000ms；`true` 时共 ~200ms"""
    if threaded:
        await asyncio.to_thread(_slow_query, ms)
    else:
        _slow_query(ms)  # 【反例】直接在事件循环里跑阻塞 IO
    return {"ms": ms, "threaded": threaded}


# ============================================================
# 3. N+1 vs 批量 vs JOIN
# ============================================================
def _run_counted(fn: Any) -> tuple[Any, int]:
    """【作用】用 `set_trace_callback` 数出真实执行的 SQL 条数"""
    conn = connect()
    statements: list[str] = []
    try:
        conn.set_trace_callback(statements.append)
        result = fn(conn)
    finally:
        conn.set_trace_callback(None)
        conn.close()
    return result, len(statements)


@app.get("/posts/n-plus-one", tags=["N+1"], summary="逐条查作者（1+N）")
async def posts_n_plus_one() -> dict[str, Any]:
    """【实测】1 条查 posts + 200 条查作者 = **201 条 SQL**"""

    def work(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        posts = conn.execute("SELECT id, author_id, title FROM posts ORDER BY id").fetchall()
        rows = []
        for post in posts:
            author = conn.execute(
                "SELECT name FROM authors WHERE id = ?", (post["author_id"],)
            ).fetchone()
            rows.append({**dict(post), "author": author["name"] if author else None})
        return rows

    rows, count = await asyncio.to_thread(_run_counted, work)
    return {"count": len(rows), "query_count": count, "sample": rows[0]}


@app.get("/posts/in-batch", tags=["N+1"], summary="IN 批量（2 条）")
async def posts_in_batch() -> dict[str, Any]:
    """【实测】posts + `WHERE id IN (...)` = **2 条 SQL**"""

    def work(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        posts = conn.execute("SELECT id, author_id, title FROM posts ORDER BY id").fetchall()
        author_ids = sorted({post["author_id"] for post in posts})
        placeholders = ",".join("?" * len(author_ids))
        authors = {
            row["id"]: row["name"]
            for row in conn.execute(
                f"SELECT id, name FROM authors WHERE id IN ({placeholders})", author_ids
            ).fetchall()
        }
        return [{**dict(post), "author": authors.get(post["author_id"])} for post in posts]

    rows, count = await asyncio.to_thread(_run_counted, work)
    return {"count": len(rows), "query_count": count, "sample": rows[0]}


@app.get("/posts/joined", tags=["N+1"], summary="JOIN（1 条）")
async def posts_joined() -> dict[str, Any]:
    """【实测】单条 JOIN = **1 条 SQL**，通常最优"""

    def work(conn: sqlite3.Connection) -> list[dict[str, Any]]:
        return [
            dict(row)
            for row in conn.execute(
                """
                SELECT p.id, p.author_id, p.title, a.name AS author
                FROM posts AS p
                JOIN authors AS a ON a.id = p.author_id
                ORDER BY p.id
                """
            ).fetchall()
        ]

    rows, count = await asyncio.to_thread(_run_counted, work)
    return {"count": len(rows), "query_count": count, "sample": rows[0]}


# ============================================================
# 4. 线程池有多大
# ============================================================
@app.get("/thread-ids", tags=["线程池"], summary="观察线程池实际并发数")
async def thread_ids(count: Annotated[int, Query(ge=1, le=200)] = 60) -> dict[str, Any]:
    """【实测】不同线程数 ≤ `min(32, cpu+4)`，超出部分排队"""

    def work() -> int:
        time.sleep(0.03)
        return threading.get_ident()

    idents = await asyncio.gather(*(asyncio.to_thread(work) for _ in range(count)))
    return {
        "submitted": count,
        "unique_threads": len(set(idents)),
        "formula_limit": THREAD_POOL_LIMIT,
        "cpu_count": os.cpu_count(),
    }


# ============================================================
# 5. database is locked
# ============================================================
@app.get("/lock/probe", tags=["锁"], summary="抢写：busy_timeout 的作用")
def lock_probe(
    busy_timeout_ms: Annotated[int, Query(ge=0, le=5000)] = 0,
) -> dict[str, Any]:
    """【实测】`busy_timeout=0` 时第二个连接立刻 `database is locked`；
    设成 500ms 时会等到第一个提交后成功
    """
    holder = connect(timeout=5.0)
    waiter = connect(timeout=busy_timeout_ms / 1000)
    errors: list[str] = []

    try:
        holder.execute("BEGIN IMMEDIATE")
        holder.execute("INSERT INTO lock_probe (note) VALUES ('held')")

        def try_write() -> None:
            try:
                waiter.execute("BEGIN IMMEDIATE")
                waiter.execute("INSERT INTO lock_probe (note) VALUES ('waited')")
                waiter.commit()
            except sqlite3.OperationalError as exc:
                errors.append(str(exc))

        thread = threading.Thread(target=try_write)
        thread.start()
        time.sleep(0.1)  # 让第二个连接真的撞上锁
        holder.commit()  # 提交后释放锁
        thread.join()
    finally:
        holder.close()
        waiter.close()

    return {
        "busy_timeout_ms": busy_timeout_ms,
        "succeeded": not errors,
        "error": errors[0] if errors else None,
    }


@app.get("/config", tags=["线程池"], summary="本章关键参数")
def config() -> dict[str, Any]:
    return {
        "authors": AUTHOR_COUNT,
        "posts": POST_COUNT,
        "thread_pool_limit": THREAD_POOL_LIMIT,
        "cpu_count": os.cpu_count(),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)