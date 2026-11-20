"""第 58 章 · 数据层：建表、索引、造 10 万行数据。

【要点】`created_at DESC, id DESC` 是本章的复合索引：
        既服务 `WHERE` 比较，也服务 `ORDER BY`，避免临时 B 树排序。
"""

import sqlite3
import tempfile
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Iterator

DB_FILE = Path(tempfile.gettempdir()) / "fastapi_ch58.db"

TOTAL_ROWS = 100_000
LEVELS = ("info", "warn", "error", "debug")

SCHEMA = """
CREATE TABLE IF NOT EXISTS events (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    created_at TEXT    NOT NULL,
    title      TEXT    NOT NULL,
    level      TEXT    NOT NULL
);

-- 【要点】排序方向写进索引，`ORDER BY created_at DESC, id DESC` 才能直接走索引
CREATE INDEX IF NOT EXISTS idx_events_created
    ON events (created_at DESC, id DESC);
"""


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


def seed(conn: sqlite3.Connection, total: int = TOTAL_ROWS) -> None:
    """【作用】造数据；`executemany` 单事务，10 万行约 0.3 秒

    【要点】不要循环 `commit()`，那是 10 万次 fsync
    """
    base = datetime(2026, 1, 1, tzinfo=timezone.utc)
    rows = [
        (
            (base + timedelta(seconds=i)).isoformat().replace("+00:00", "Z"),
            f"事件 {i:06d}",
            LEVELS[i % len(LEVELS)],
        )
        for i in range(total)
    ]
    conn.executemany("INSERT INTO events (created_at, title, level) VALUES (?, ?, ?)", rows)
    conn.commit()


def init_db() -> None:
    """【要点】已有数据就复用，避免每次启动重新灌 10 万行"""
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        if conn.execute("SELECT COUNT(*) FROM events").fetchone()[0] == 0:
            seed(conn)
    finally:
        conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()