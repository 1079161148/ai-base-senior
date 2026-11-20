"""第 56 章 · 数据层：连接与依赖（不写 SQL）。"""

import sqlite3
import tempfile
from pathlib import Path
from typing import Iterator

DB_FILE = Path(tempfile.gettempdir()) / "fastapi_ch56.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS items (
    id    INTEGER PRIMARY KEY AUTOINCREMENT,
    name  TEXT    NOT NULL UNIQUE,
    price INTEGER NOT NULL CHECK (price >= 0)
);
"""


def connect() -> sqlite3.Connection:
    """【要点】每请求一个连接：简单、无跨请求状态，代价是握手开销

    【注意】必须 `check_same_thread=False`：FastAPI 的同步依赖与同步端点
            都在线程池里跑，但不保证是同一个线程
    """
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    """建表；由 lifespan 调用一次

    【实测坑】`with sqlite3.connect(...) as conn:` **不会关闭连接**，
              只负责提交/回滚事务。Windows 上会因此占住文件（`WinError 32`），
              必须显式 `close()`
    """
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
    finally:
        conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    """【作用】请求级连接，请求结束自动关闭

    【要点】这里只负责「给连接 + 保证关闭」，**不负责事务**（第 57 章）
    """
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()