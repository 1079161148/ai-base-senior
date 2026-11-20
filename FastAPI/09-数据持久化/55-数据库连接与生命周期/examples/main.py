"""第 55 章 · 数据库连接与生命周期。

核心：连接要在 `lifespan` 里建、在关闭时释放，并挂在 `app.state` 上。
      标准库 `sqlite3` 是**阻塞**的，必须用 `asyncio.to_thread` 隔离，
      否则一个慢查询会卡住整个事件循环。
      连接创建时必须 `check_same_thread=False`，否则线程池里用会炸。

启动：uvicorn main:app --reload
验收：python verify.py
"""

import asyncio
import sqlite3
import tempfile
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any, AsyncIterator

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

# 【作用】放临时目录，进程退出前由 lifespan 删除；生产换成固定路径/外部库
DB_FILE = Path(tempfile.gettempdir()) / "fastapi_ch55.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT    NOT NULL UNIQUE,
    price INTEGER NOT NULL CHECK (price >= 0)
);
"""


def connect() -> sqlite3.Connection:
    """【要点】`check_same_thread=False` 是必须的：`to_thread` 会换线程执行

    【注意】关掉检查后，**同一个连接不能被多个线程同时写**；
            并发写要靠单写线程或加锁（`sqlite3` 自身串行化）
    """
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row  # 让查询结果能按列名取值
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    return conn


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """【作用】启动建连接/建表，关闭时释放

    【实测】不进入 `with TestClient(app)` 时这个函数**根本不会执行**
    """
    DB_FILE.unlink(missing_ok=True)
    conn = connect()
    conn.executescript(SCHEMA)
    conn.commit()
    app.state.db = conn
    app.state.db_opened = True
    app.state.started = True
    try:
        yield
    finally:
        # 【要点】关闭放 finally，保证异常启动时也不会泄漏
        conn.close()
        app.state.db_opened = False
        app.state.started = False
        DB_FILE.unlink(missing_ok=True)


app = FastAPI(title="第 55 章 · 数据库连接与生命周期", version="0.1.0", lifespan=lifespan)


class ItemIn(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    price: int = Field(ge=0)


def _list_items() -> list[dict[str, Any]]:
    """同步实现，只在线程里跑"""
    rows = app.state.db.execute("SELECT id, name, price FROM items ORDER BY id").fetchall()
    return [dict(row) for row in rows]


def _create_item(payload: ItemIn) -> dict[str, Any]:
    try:
        cursor = app.state.db.execute(
            "INSERT INTO items (name, price) VALUES (?, ?)",
            (payload.name, payload.price),
        )
        app.state.db.commit()
    except sqlite3.IntegrityError as exc:
        app.state.db.rollback()
        # 【要点】把数据库异常翻译成 HTTP 语义，不要让 500 直接冒出去
        raise HTTPException(status_code=409, detail=f"名称已存在：{payload.name}") from exc
    return {"id": cursor.lastrowid, "name": payload.name, "price": payload.price}


# ============================================================
# 端点
# ============================================================
@app.get("/items", tags=["数据库"], summary="查询列表")
async def list_items() -> list[dict[str, Any]]:
    """【要点】所有阻塞 IO 都包进 `to_thread`，事件循环才能继续处理别的请求"""
    return await asyncio.to_thread(_list_items)


@app.post("/items", tags=["数据库"], summary="新增一条", status_code=201)
async def create_item(payload: ItemIn) -> dict[str, Any]:
    return await asyncio.to_thread(_create_item, payload)


@app.get("/health", tags=["数据库"], summary="健康检查")
async def health() -> dict[str, Any]:
    """【要点】健康检查要真的碰一次库，不能只返回 `{"ok": true}`"""

    def probe() -> int:
        return app.state.db.execute("SELECT COUNT(*) FROM items").fetchone()[0]

    try:
        count = await asyncio.to_thread(probe)
    except sqlite3.Error as exc:
        raise HTTPException(status_code=503, detail=f"数据库不可用：{exc}") from exc
    return {"status": "ok", "items": count}


@app.get("/state", tags=["数据库"], summary="看连接状态")
async def state() -> dict[str, Any]:
    """【实测】lifespan 关闭后 `db_opened` 变 False，连接再用会报错"""
    return {
        "opened": getattr(app.state, "db_opened", False),
        "db_file": str(DB_FILE),
    }


@app.get("/items/count", tags=["数据库"], summary="计数（用 to_thread）")
async def count_items() -> dict[str, int]:
    def work() -> int:
        return app.state.db.execute("SELECT COUNT(*) FROM items").fetchone()[0]

    return {"count": await asyncio.to_thread(work)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)