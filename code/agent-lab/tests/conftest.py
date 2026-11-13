"""测试公共夹具。

所有测试都用内存 SQLite，绝不碰 data/app.db ——
测试污染了开发数据，下次跑起来会看到莫名其妙的待办。
"""

import aiosqlite
import pytest

from agent_lab.app.core.db import SCHEMA


@pytest.fixture
async def db() -> aiosqlite.Connection:
    conn = await aiosqlite.connect(":memory:")
    conn.row_factory = aiosqlite.Row
    await conn.executescript(SCHEMA)
    await conn.commit()
    yield conn
    await conn.close()
