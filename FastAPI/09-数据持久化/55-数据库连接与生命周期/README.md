# 55 数据库连接与生命周期

## 一句话结论

连接在 `lifespan` 里建、挂 `app.state`、`finally` 里关；标准库 `sqlite3` 是阻塞的，所有调用必须包进 `asyncio.to_thread`，而连接创建时必须 `check_same_thread=False`。四个实测关键点：**`TestClient` 不用 `with` 时 lifespan 根本不执行**（`app.state.db` 不存在）；**默认 `check_same_thread=True` 换线程用直接 `ProgrammingError`**；**`:memory:` 每个连接一个独立库**（不是共享的）；**`@app.on_event` 已触发 DeprecationWarning**。

## 最小可运行案例

```python
import asyncio
import sqlite3
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator

from fastapi import FastAPI

DB_FILE = "app.db"


def connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    return conn


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    conn = connect()
    conn.execute("CREATE TABLE IF NOT EXISTS items (id INTEGER PRIMARY KEY, name TEXT)")
    conn.commit()
    app.state.db = conn
    try:
        yield
    finally:
        conn.close()


app = FastAPI(lifespan=lifespan)


@app.get("/items")
async def list_items() -> list[dict[str, Any]]:
    def work() -> list[dict[str, Any]]:
        rows = app.state.db.execute("SELECT id, name FROM items").fetchall()
        return [dict(row) for row in rows]

    return await asyncio.to_thread(work)
```

## 怎么跑

```powershell
cd "09-数据持久化\55-数据库连接与生命周期\examples"
uv sync
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] with 触发 lifespan -> opened=True
[PASS] 启动建表 -> 空表可查
[PASS] 新增 -> id=1
[PASS] 列表 -> 2 条
[PASS] 唯一冲突 → 409 -> 409 名称已存在
[PASS] 负数 → 422 -> 422
[PASS] 健康检查碰库 -> items=1
[PASS] 计数一致 -> count=3
[PASS] 关闭后连接失效 -> Cannot operate on a closed database.
[PASS] 线程亲和报错 -> SQLite objects created in a thread can only be used in that same thread...
[PASS] check_same_thread=False -> 线程池内 SELECT 1+1 = 2
[PASS] :memory: 不共享 -> no such table: t
[PASS] 无 with 无 lifespan -> opened=False, started=False
[PASS] on_event 已废弃 -> on_event is deprecated, use lifespan event handlers instead.

结果：14/14 通过
```

## 核心 API 速查

| 对象 | 用法 | 备注 |
| --- | --- | --- |
| `lifespan` | `@asynccontextmanager` + `yield` | `yield` 前启动、后清理 |
| `app.state` | 存连接/配置 | 请求里用 `app.state.db` |
| `asyncio.to_thread` | 包同步 DB 调用 | 默认线程池 |
| `check_same_thread=False` | 允许跨线程 | `to_thread` 必需 |
| `row_factory = sqlite3.Row` | 按列名取值 | `dict(row)` 转字典 |
| `executescript` | 建表脚本 | 记得 `commit()` |

| 实测行为 | 结果 |
| --- | --- |
| `with TestClient(app)` | lifespan 执行 |
| 不用 `with` | lifespan **不执行** |
| lifespan 退出后 | 连接已关闭，再用抛 `ProgrammingError` |
| 默认 `check_same_thread` | 换线程 → `ProgrammingError` |
| `check_same_thread=False` | 线程池可用 |
| `:memory:` 两连接 | 表不共享（`no such table`）|
| 唯一约束冲突 | `IntegrityError` → 手动翻译 409 |
| `@app.on_event` | `DeprecationWarning` |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 测试里 `TestClient(app)` 不加 `with` | lifespan 没跑，`app.state.db` 不存在 | `with TestClient(app) as c:` |
| 全局 `conn` 用默认 `check_same_thread` | `to_thread` 里炸 | `check_same_thread=False` |
| 端点是 `def` 却直接调 `conn.execute` | 阻塞事件循环 | `async def` + `to_thread` |
| 用 `:memory:` 想跨连接共享 | 每个连接独立 | 共享缓存 URI 或换文件 |
| 建表后不 `commit` | 表不存在 | 显式 `commit()` |
| `IntegrityError` 不捕获 | 500 | 翻译 409 |
| 健康检查只返回 `ok` | 库挂了也返回健康 | 真查一次 |
| 用 `@app.on_event` | 废弃警告 | `lifespan` |
| 连接放模块级全局 | 多进程/测试串 | `app.state` |
| 关闭连接只在 `yield` 后不做 `finally` | 启动异常时泄漏 | `try/finally` |
| 每次请求新建连接 | 慢 | 复用/连接池 |
| 忘记 `row_factory` | 只能按下标取 | `sqlite3.Row` |
| 用 f-string 拼 SQL | 注入 | 参数化 `?` |
| 长时间读事务不关 | 锁库 | 用完即提交/回滚 |

## 毕业自查

- [ ] 能写出完整的 `lifespan`（建连接 + 建表 + `finally` 关闭）
- [ ] 能解释为什么必须 `check_same_thread=False`
- [ ] 能解释为什么必须 `to_thread`
- [ ] 能解释 `TestClient` 的 `with`
- [ ] 知道 `:memory:` 不共享
- [ ] 动手题一：把 `sqlite3` 换成 `aiosqlite` 对比代码量
- [ ] 动手题二：加 `PRAGMA busy_timeout` 处理并发写

> 想看 `lifespan` 在 ASGI 层怎么被调用、`to_thread` 的线程池上限、SQLite 并发写锁、连接池取舍、18 条坑，继续读 [`base.md`](./base.md)。