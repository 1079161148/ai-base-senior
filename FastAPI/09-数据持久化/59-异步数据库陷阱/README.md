# 59 异步数据库陷阱

## 一句话结论

事件循环是**单线程**的，任何在 `async def` 里做的阻塞调用都会让整个进程停止响应。实测 5 个并发请求、每个 200ms：`async def` + `time.sleep` 总耗时 **1012ms**（完全串行），`await asyncio.to_thread(...)` 是 **210ms**，普通 `def` 端点 **256ms**；心跳任务的最大间隔从 **16ms** 拉到 **201ms**，直接证明事件循环停摆。N+1 实测 **201 条 SQL**，`IN` 批量 **2 条**，`JOIN` **1 条**，三者结果完全一致。线程池上限是 `min(32, cpu+4)`（本机 `cpu=20` → 24），60 个任务只会用到 24 个线程。

## 最小可运行案例

```python
import asyncio
import sqlite3
import time

from fastapi import FastAPI

app = FastAPI()


# 错误：阻塞事件循环
@app.get("/bad")
async def bad() -> dict[str, str]:
    conn = sqlite3.connect("app.db")
    rows = conn.execute("SELECT * FROM big_table").fetchall()  # 卡住整个进程
    return {"rows": str(len(rows))}


# 正确一：to_thread 隔离
@app.get("/good")
async def good() -> dict[str, str]:
    def work() -> int:
        conn = sqlite3.connect("app.db")
        try:
            return len(conn.execute("SELECT * FROM big_table").fetchall())
        finally:
            conn.close()

    return {"rows": str(await asyncio.to_thread(work))}


# 正确二：直接写 def，FastAPI 自动放进线程池
@app.get("/simplest")
def simplest() -> dict[str, str]:
    time.sleep(0.2)
    return {"ok": "true"}
```

## 怎么跑

```powershell
cd "09-数据持久化\59-异步数据库陷阱\examples"
uv sync
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 阻塞串行 -> 1012ms（≈ 5×200）
[PASS] to_thread 并行 -> 210ms（≈ 200）
[PASS] def 自动线程池 -> 256ms
[PASS] 慢 SQL 阻塞 -> 1019ms（串行）
[PASS] 慢 SQL 隔离 -> 208ms（并行）
[PASS] 心跳停摆 -> 阻塞最大间隔 201ms vs 隔离 16ms
[PASS] N+1 = 201 -> 201 条 SQL
[PASS] IN = 2 -> 2 条 SQL
[PASS] JOIN = 1 -> 1 条 SQL
[PASS] 结果一致 -> sample 一致
[PASS] 线程池上限 -> 24 线程（上限 24，cpu 20）
[PASS] 超出则排队 -> 60 个任务 / 24 线程
[PASS] 无 timeout 即锁 -> database is locked
[PASS] busy_timeout 生效 -> 等待后写入成功
[PASS] 异常不吞 -> 线程里的错误

结果：15/15 通过
```

## 核心 API 速查

| 写法 | 事件循环 | 并发 | 适用 |
| --- | --- | --- | --- |
| `async def` + 同步 DB | **阻塞** | 串行 | 禁止 |
| `async def` + `to_thread` | 不阻塞 | 并行 | 推荐 |
| `def` 端点 | 不阻塞（自动线程池）| 并行 | 推荐，最省心 |

| 观测手段 | 命令 |
| --- | --- |
| 数 SQL 条数 | `conn.set_trace_callback(list.append)` |
| 看线程池 | 统计 `threading.get_ident()` 去重 |
| 看事件循环是否停摆 | 心跳协程的**最大间隔** |
| 看锁等待 | `sqlite3.connect(timeout=秒)` |

| 实测 | 值 |
| --- | --- |
| 5×200ms 阻塞 | 1012ms |
| 5×200ms `to_thread` | 210ms |
| 5×200ms `def` | 256ms |
| 心跳最大间隔（阻塞/隔离）| 201ms / 16ms |
| N+1 / IN / JOIN | 201 / 2 / 1 条 |
| 线程池上限 | `min(32, cpu+4)` = 24（cpu 20）|
| 60 任务 → 唯一线程 | 24 |
| `timeout=0` 抢锁 | `database is locked` |
| `timeout=0.5` 抢锁 | 等到提交后成功 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `async def` 里直接 `sqlite3`/`psycopg2` | 全站串行，P99 暴涨 | `to_thread` 或改 `def` |
| `async def` 里 `requests.get` | 同上 | `httpx.AsyncClient` |
| `async def` 里 `time.sleep` | 同上 | `asyncio.sleep` |
| `def` 端点里再 `to_thread` | 多套一层线程 | 直接写同步代码 |
| `def` 端点里 `await` | 语法/运行错误 | 要么全同步要么全异步 |
| 用 `aiosqlite` 就以为没线程 | 它内部也是线程池 | 仍是 `to_thread` 模型 |
| 线程池被长任务占满 | 其他请求排队 | 控制单任务时长/加容量 |
| 循环里逐条查关联表 | N+1，201 条 SQL | `IN` 批量 / `JOIN` |
| N+1 用 `asyncio.gather` 并发查 | 连接暴涨、锁竞争 | 改批量 SQL |
| `timeout=0` 又无重试 | 偶发 `database is locked` | 设 `busy_timeout` |
| 多个连接同时写 SQLite | 写锁排队 | 单写连接/队列 |
| 把 `sqlite3.Connection` 跨线程共享 | 串行化或报错 | 每线程/每请求一个 |
| 在 `lifespan` 里跑重活 | 启动阻塞 | 后台任务 |
| 用 tick 数判断阻塞 | Windows 时钟粒度 15.6ms，看不出 | 看最大间隔 |
| `to_thread` 里吞异常 | 静默失败 | 直接抛，`await` 处处理 |
| 线程池里用 `contextvars` | 值不会自动传 | `copy_context().run` |
| 长事务 + 慢 SQL | 锁更久 | 缩事务 |

## 毕业自查

- [ ] 能解释为什么 `async def` 里的 `sqlite3` 会卡全站
- [ ] 能写出三种正确写法（`to_thread` / `def` / 异步驱动）
- [ ] 能手算 5 个并发 200ms 的两种总耗时
- [ ] 能用 `set_trace_callback` 抓 N+1
- [ ] 能说出线程池上限公式
- [ ] 能手写复现 `database is locked`
- [ ] 动手题一：把 N+1 端点改成 `JOIN` 并对比条数
- [ ] 动手题二：把 `busy_timeout` 设成 0，用并发写复现锁错误

> 想看在 asyncio 内部 `to_thread` 怎么调度、线程池耗尽的表现、`contextvars` 跨线程丢失、SQLite 写锁模型、18 条坑，继续读 [`base.md`](./base.md)。