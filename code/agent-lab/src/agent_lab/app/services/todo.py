"""待办业务逻辑（直接写 SQL，不引入 ORM）。

**为什么不引入 ORM**：S0 先看清 SQL、事务、异步连接是怎么配合的；
等 S3 上 Postgres 时再换 SQLAlchemy 2.0 也不吃亏。

**本层不 import FastAPI** —— 它只知道"有一个 aiosqlite 连接"。
所以同一套函数可以直接被脚本、定时任务、或将来 Agent 的 Tool 复用，
不需要经过 HTTP。
"""

from typing import cast

import aiosqlite

from ..core.errors import ApiError
from ..core.time import from_storage, now, to_storage
from ..models.todo import TodoCreate, TodoOut, TodoUpdate

# 字段清单是常量，不来自用户输入，可以安全拼接；
# 所有「值」一律走 ? 参数化，杜绝 SQL 注入。
_COLUMNS = "id, title, done, created_at"


def _to_out(row: aiosqlite.Row) -> TodoOut:
    # 为什么要 cast：sqlite3.Row.__getitem__ 的标注是 Any（SQLite 动态类型，
    # 驱动拿不到列类型），严格模式下 reportAny 会逐字段报警。
    # cast 是「零运行时开销」的纯类型声明，真正兜底的是 TodoOut ——
    # 它是 Pydantic 模型，字段类型不符会在构造时校验报错。
    return TodoOut(
        id=cast(int, row["id"]),
        title=cast(str, row["title"]),
        # SQLite 没有布尔类型，存的是 0/1，取出必须显式转换，
        # 否则 JSON 里会出现 "done": 1 而前端类型定义是 boolean
        done=bool(cast(int, row["done"])),
        # 库里存的是字符串，先还原成 datetime 交给模型，
        # 格式问题由 core/time.py 的序列化器统一处理 —— 本文件不再拼时间字符串。
        created_at=from_storage(cast(str, row["created_at"])),
    )


async def list_todos(db: aiosqlite.Connection) -> list[TodoOut]:
    cursor = await db.execute(f"SELECT {_COLUMNS} FROM todos ORDER BY id DESC")
    rows = await cursor.fetchall()
    await cursor.close()
    return [_to_out(row) for row in rows]


async def get_todo(db: aiosqlite.Connection, todo_id: int) -> TodoOut:
    cursor = await db.execute(
        f"SELECT {_COLUMNS} FROM todos WHERE id = ?",
        (todo_id,),
    )
    row = await cursor.fetchone()
    await cursor.close()
    if row is None:
        raise ApiError(404, "TODO_NOT_FOUND", f"待办 {todo_id} 不存在")
    return _to_out(row)


async def create_todo(db: aiosqlite.Connection, payload: TodoCreate) -> TodoOut:
    # 取时间、转存储格式都走 core/time.py：
    # 库里恒为 UTC ISO 字符串，输出格式由那一个模块统一决定。
    # 这里不允许出现 isoformat / strftime —— 否则格式又会散落回业务层。
    created_at = to_storage(now())
    cursor = await db.execute(
        "INSERT INTO todos (title, done, created_at) VALUES (?, 0, ?)",
        (payload.title, created_at),
    )
    await db.commit()
    new_id = cursor.lastrowid
    await cursor.close()

    if new_id is None:  # 理论上不会发生，但类型上 lastrowid 是 int | None
        raise ApiError(500, "TODO_CREATE_FAILED", "创建待办失败")
    return await get_todo(db, new_id)


async def update_todo(
    db: aiosqlite.Connection,
    todo_id: int,
    payload: TodoUpdate,
) -> TodoOut:
    # 先查一次：不存在直接 404，避免 UPDATE 静默影响 0 行后返回一个假结果
    current = await get_todo(db, todo_id)

    title = current.title if payload.title is None else payload.title
    done = current.done if payload.done is None else payload.done

    # 与本文件其他函数保持一致：execute 返回的 Cursor 要显式关闭。
    # 不关虽然不会立刻出错（连接关闭时会一并回收），但会造成
    # 「有些函数关、有些没关」的不一致，以后排查连接/句柄问题时很难看出规律。
    # 顺带消除 reportUnusedCallResult —— 之前 execute 的返回值被直接丢弃了。
    cursor = await db.execute(
        "UPDATE todos SET title = ?, done = ? WHERE id = ?",
        (title, int(done), todo_id),
    )
    await db.commit()
    await cursor.close()
    return await get_todo(db, todo_id)


async def delete_todo(db: aiosqlite.Connection, todo_id: int) -> None:
    cursor = await db.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
    await db.commit()
    deleted = cursor.rowcount
    await cursor.close()
    # rowcount == 0 说明本来就不存在。不报错的话前端会以为删成功了
    if deleted == 0:
        raise ApiError(404, "TODO_NOT_FOUND", f"待办 {todo_id} 不存在")
