"""数据库连接与初始化。

**为什么用 aiosqlite 而不是标准库 sqlite3**：
sqlite3 是同步阻塞的，在 `async def` 里直接调用会卡住整个事件循环
—— 这正是 S0 反复强调的「异步陷阱」：单请求看着没问题，一上并发全排队。

**为什么路径用 Path(__file__) 而不是相对路径**：
`"./data/app.db"` 是相对「启动目录」解析的，从别的目录启动就会连到另一个空库，
而且**不报错**。用 __file__ 锚定，从哪启动都一样。
"""

from collections.abc import AsyncIterator
from pathlib import Path

import aiosqlite

# db.py 位于 src/agent_lab/app/core/，向上 4 层即 agent-lab/ 项目根
#   parents[0]=core  [1]=app  [2]=agent_lab  [3]=src  [4]=agent-lab
DB_PATH = Path(__file__).resolve().parents[4] / "data" / "app.db"

SCHEMA = """
CREATE TABLE IF NOT EXISTS todos (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    title      TEXT    NOT NULL,
    done       INTEGER NOT NULL DEFAULT 0,
    created_at TEXT    NOT NULL
);
"""


async def init_db() -> None:
    """建库建表。在 lifespan 启动阶段调用，保证表一定存在。"""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        await db.commit()


async def get_db() -> AsyncIterator[aiosqlite.Connection]:
    """FastAPI 依赖：每个请求一个连接，响应结束后自动 close。

    `yield` 之前的代码在请求前执行，`finally` 在响应后执行 ——
    这就是 Depends 的「携带清理逻辑」能力，等价于中间件但没有全局副作用。

    ⚠️ 教学简化：每请求建一次连接，生产环境应换成连接池（会在请求间复用）。
    """
    db = await aiosqlite.connect(DB_PATH)
    # 让查询结果支持 row["title"]，而不是只能按索引 row[0]
    db.row_factory = aiosqlite.Row
    try:
        yield db
    finally:
        await db.close()
