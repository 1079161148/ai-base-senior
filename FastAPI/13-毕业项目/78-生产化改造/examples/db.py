"""SQLite 连接与事务边界。

【要点】事务放在**依赖**里，端点不写 `commit()`：
        - 正常返回 → commit
        - 抛任何异常（含 `HTTPException` / `AppError`）→ rollback

这样「先写一半再报错」不会留下脏数据。
"""

import sqlite3
from typing import Annotated, Iterator

from fastapi import Depends

from config import Settings, get_settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS todos (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    done        INTEGER NOT NULL DEFAULT 0,
    priority    TEXT    NOT NULL,
    created_at  TEXT    NOT NULL
);
"""


def init_db(settings: Settings) -> None:
    with sqlite3.connect(settings.db_path) as conn:
        conn.executescript(SCHEMA)


def get_conn(
    settings: Annotated[Settings, Depends(get_settings)],
) -> Iterator[sqlite3.Connection]:
    """【要点】一个请求一个连接、一个事务"""
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        # 事务回滚后必须继续抛，交给异常处理器生成响应
        conn.rollback()
        raise
    finally:
        conn.close()


ConnDep = Annotated[sqlite3.Connection, Depends(get_conn)]