"""积木 4 · 数据连接：一个请求一个连接、一个事务。

【原则】端点永远不写 `commit()`：正常返回由依赖提交，异常由依赖回滚。
"""

import sqlite3
from typing import Annotated, Iterator

from fastapi import Depends

from app.core.config import Settings, get_settings


def get_conn(settings: Annotated[Settings, Depends(get_settings)]) -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(settings.db_path, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


ConnDep = Annotated[sqlite3.Connection, Depends(get_conn)]