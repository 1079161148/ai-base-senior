"""第 59 章 · 数据层：关联表 + 锁探针表。

【要点】`authors` / `posts` 是为了演示 N+1：
        200 条 posts，逐条查作者 = 1 + 200 条 SQL。
"""

import sqlite3
import tempfile
from pathlib import Path
from typing import Iterator

DB_FILE = Path(tempfile.gettempdir()) / "fastapi_ch59.db"

AUTHOR_COUNT = 20
POST_COUNT = 200

SCHEMA = """
CREATE TABLE IF NOT EXISTS authors (
    id   INTEGER PRIMARY KEY,
    name TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS posts (
    id        INTEGER PRIMARY KEY,
    author_id INTEGER NOT NULL REFERENCES authors(id),
    title     TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS lock_probe (
    id   INTEGER PRIMARY KEY AUTOINCREMENT,
    note TEXT NOT NULL
);
"""


def connect(timeout: float = 5.0) -> sqlite3.Connection:
    """【要点】`timeout` 就是 `busy_timeout`：抢锁时最多等这么多秒

    【注意】设成 0 时，锁被占用立刻抛 `database is locked`，不会重试
    """
    conn = sqlite3.connect(DB_FILE, check_same_thread=False, timeout=timeout)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def seed(conn: sqlite3.Connection) -> None:
    authors = [(i, f"作者 {i:02d}") for i in range(1, AUTHOR_COUNT + 1)]
    posts = [(i, (i - 1) % AUTHOR_COUNT + 1, f"文章 {i:03d}") for i in range(1, POST_COUNT + 1)]
    conn.executemany("INSERT INTO authors (id, name) VALUES (?, ?)", authors)
    conn.executemany("INSERT INTO posts (id, author_id, title) VALUES (?, ?, ?)", posts)
    conn.commit()


def init_db() -> None:
    conn = connect()
    try:
        conn.executescript(SCHEMA)
        conn.commit()
        if conn.execute("SELECT COUNT(*) FROM posts").fetchone()[0] == 0:
            seed(conn)
    finally:
        conn.close()


def get_db() -> Iterator[sqlite3.Connection]:
    conn = connect()
    try:
        yield conn
    finally:
        conn.close()