"""第 57 章 · 事务边界：把 commit/rollback 放进 `yield` 依赖。

【核心】一次请求 = 一个事务：
        成功 → commit；抛任何异常 → rollback；无论如何 → close。
        仓储层只 `execute`，**不 commit**。
"""

import sqlite3
import tempfile
from pathlib import Path
from typing import Iterator

DB_FILE = Path(tempfile.gettempdir()) / "fastapi_ch57.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT    NOT NULL UNIQUE,
    price INTEGER NOT NULL CHECK (price >= 0)
);

CREATE TABLE IF NOT EXISTS audit (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    note TEXT NOT NULL
);
"""

EVENTS: list[str] = []


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """建表；显式 close（`with sqlite3.connect()` 不会关连接）"""
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    """【作用】请求级事务边界

    【要点】`commit` 在 `yield` 之后、`close` 之前；
            任何异常（含 `HTTPException`）都走 `rollback`

    【注意】FastAPI 里 `yield` 依赖的收尾在**响应发送之后**执行，
            所以这里 commit 失败**改不了已发出的状态码**——
            别把可能失败的校验放到 commit 才暴露
    """
    conn = connect()
    EVENTS.append("db:begin")
    try:
        yield conn
        conn.commit()  # 只有正常返回才提交
        EVENTS.append("db:commit")
    except Exception:
        conn.rollback()
        EVENTS.append("db:rollback")
        raise
    finally:
        conn.close()
        EVENTS.append("db:close")