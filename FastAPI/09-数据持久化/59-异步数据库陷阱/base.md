# 59 异步数据库陷阱 · 完整版（base.md）

> `README.md` 给你能跑的对比示例；本文件把「`to_thread` 到底把任务丢到哪、线程池满了会怎样、N+1 为什么会发生、SQLite 的锁为什么会互相撞」拆开。学完这章，你要能在 5 分钟内判断一个「偶发卡顿」是阻塞调用、N+1 还是锁等待。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0（本机实测） |
| 前置 | 第 55 章（连接）、第 58 章（查询） |
| 覆盖范围 | 阻塞调用、`to_thread`、线程池、N+1、`database is locked` |
| 明确不覆盖 | `asyncpg`/SQLAlchemy async 全量、连接池实现细节、分布式锁 |
| 学完验收 | 能跑通 `verify.py` 15/15、能解释 5 倍与 200 倍两个差距 |

## 0. 怎么用这份文件

**依据约定**：`` `[An]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 单线程事件循环
2 机制（第 2 节）    → to_thread 与线程池
3 API（第 3 节）     → 三种写法
4 边界（第 4 节）    → N+1、锁、池耗尽、contextvars
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 排查流程
```

## 1. 概念：一个线程服务所有请求

```text
事件循环（单线程）
 ├─ 请求 A：await DB → 挂起，切走
 ├─ 请求 B：await DB → 挂起，切走
 └─ 请求 C：time.sleep(0.2) → 线程卡住 200ms，A/B 全等着
```

| 事实 | 后果 |
| --- | --- |
| 循环只有一个线程 | 任何阻塞都全站生效 |
| `await` 是主动让出 | 不让出就一直占着 |
| 线程池是逃生舱 | `to_thread` / `def` 端点 |

实测 5 个并发 200ms：

| 写法 | 总耗时 | 结论 |
| --- | --- | --- |
| `async def` + `time.sleep` | 1012ms | 串行 |
| `async def` + `to_thread` | 210ms | 并行 |
| `def` 端点 | 256ms | 并行 |

5 倍差距来自「完全不重叠」，不是性能调优能补的。

## 2. 机制：`to_thread` 与线程池

```text
await asyncio.to_thread(fn, *args)
  → loop.run_in_executor(None, ...)
    → ThreadPoolExecutor(max_workers=min(32, cpu+4))
```

| 参数 | 值（本机） |
| --- | --- |
| `cpu_count` | 20 |
| 上限 `min(32, cpu+4)` | 24 |
| 提交 60 个任务 | 实际只起 24 个线程 |
| 其余任务 | 在队列里等 |

**关键**：线程池大小 ≠ 并发能力上限。24 个线程各自阻塞 1 秒，第 25 个请求就要等 1 秒。

### 2.1 心跳判据（实测）

| 场景 | 心跳最大间隔 |
| --- | --- |
| 阻塞 200ms | 201ms |
| `to_thread` 隔离 | 16ms（= 时钟粒度）|

**注意**：不要用「tick 数」判断。Windows 上 `asyncio.sleep(0.005)` 实际约 15.6ms，阻塞 200ms 也只少跑十几次，区分度极差；**最大间隔**才是硬证据。

## 3. API 逐个拆解

| 写法 | 代码 | 评价 |
| --- | --- | --- |
| 隔离 | `await asyncio.to_thread(work)` | 推荐 |
| 直接同步 | `def endpoint(): ...` | 推荐，最省心 |
| 异步驱动 | `await aiosqlite.connect(...)` | 可选，本质仍是线程 |
| 反例 | `async def` 里直接 `conn.execute` | 禁止 |

### 3.1 `aiosqlite` 的真相

`aiosqlite` 内部就是一个专用线程 + 队列，把同步 `sqlite3` 调用转到线程里。它解决的是「API 形态」，不是「消除线程」。

| 方案 | 线程来源 |
| --- | --- |
| `asyncio.to_thread` | 共享默认线程池 |
| `aiosqlite` | 每连接一个专用线程 |
| `asyncpg` | 真异步 socket |
| `def` 端点 | FastAPI 的线程池 |

## 4. 边界条件

### 4.1 N+1（实测）

| 写法 | SQL 条数 |
| --- | --- |
| 逐条查作者 | **201** |
| `WHERE id IN (...)` | **2** |
| `JOIN` | **1** |

三者结果**完全一致**，只差代价。用 `set_trace_callback` 数条数是最可靠的发现手段——比看代码靠猜强。

**注意**：用 `asyncio.gather` 并发跑 200 条查询并不会「修好」N+1，只会把线程池打满 + 制造锁竞争。

### 4.2 `database is locked`（实测）

```python
holder = sqlite3.connect(path, timeout=5)
holder.execute("BEGIN IMMEDIATE")
# 另一个连接同时写
waiter = sqlite3.connect(path, timeout=0)     # 立刻失败
waiter = sqlite3.connect(path, timeout=0.5)   # 等 100ms 后成功
```

| `timeout` | 结果 |
| --- | --- |
| 0 | `sqlite3.OperationalError: database is locked` |
| 0.5 | 等到持锁者提交后写入成功 |

`connect(timeout=...)` 就是 `PRAGMA busy_timeout` 的秒数。

### 4.3 线程池耗尽

24 个线程全被占（每个跑 1 秒），第 25 个请求排队 1 秒。表现和「阻塞事件循环」很像，但 CPU 空闲、日志正常。

判据：`/thread-ids` 类探针 + 观察排队延迟。

### 4.4 `contextvars` 不跨线程

`to_thread` 里默认看不到请求上下文里的 `contextvar`（第 52 章的 trace_id）。

| 需求 | 做法 |
| --- | --- |
| 线程里打日志带 trace_id | 调用前显式传参 |
| 自动传播 | `loop.run_in_executor` 前 `contextvars.copy_context()` |

实测未覆盖自动传播写法，标注为**未实测**。

### 4.5 异常传播（实测）

`to_thread` 里的异常会在 `await` 处原样抛出（`ValueError("线程里的错误")`），不会被吞。所以不需要额外包装。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `async def` 里跑同步 DB | 5 并发变 1012ms（实测）| `to_thread` | 实测 |
| `async def` 里 `requests` | 同上 | `httpx.AsyncClient` | `[A1]` |
| `async def` 里 `time.sleep` | 同上 | `asyncio.sleep` | `[A1]` |
| `def` 端点里再 `to_thread` | 套两层线程 | 直接同步 | 实测 |
| 以为 `aiosqlite` 无线程 | 每连接一线程 | 理解模型 | `[A2]` |
| 逐条查关联表 | 201 条（实测）| `IN` / `JOIN` | 实测 |
| 用 `gather` 并发修 N+1 | 池耗尽 + 锁竞争 | 批量 SQL | 实测 |
| `timeout=0` 无重试 | 偶发 locked（实测）| `busy_timeout` | 实测 |
| 多连接并发写 SQLite | 写锁排队 | 单写连接 | `[A3]` |
| 跨线程共享连接 | 串行/报错 | 每请求一个 | 第 55 章 |
| 用 tick 数判断阻塞 | Windows 粒度掩盖 | 看最大间隔 | 实测 |
| `to_thread` 里吞异常 | 静默失败 | 直接抛 | 实测 |
| 线程池里用 contextvar | 拿不到值 | 显式传参 | `[A1]` |
| 长任务占线程池 | 其他请求排队 | 限时长/加容量 | `[A1]` |
| `lifespan` 里跑重活 | 启动卡住 | 后台任务 | 第 55 章 |
| 长事务 + 慢 SQL | 锁时间放大 | 缩事务 | 第 57 章 |
| 只看平均耗时 | 偶发阻塞被掩盖 | 看 P99 | 第 71 章 |
| 不观测 SQL 条数 | N+1 到线上才发现 | `set_trace_callback` | 实测 |
| 在 `def` 端点里改造异步驱动 | 再套一层事件循环，得不偿失 | 同步/异步二选一 | `[A1]` |

## 6. 最佳实践与编码建议

### 6.1 选型

| 场景 | 推荐 |
| --- | --- |
| SQLite / 同步驱动 | `def` 端点 或 `to_thread` |
| PostgreSQL 高并发 | `asyncpg` / SQLAlchemy async |
| 需要事务对象跨多次调用 | `def` 端点 + `yield` 依赖 |
| 混合（部分异步）| 统一 `to_thread`，别混两套 |

### 6.2 排查流程

```text
1 偶发卡顿
   → 心跳最大间隔很大？→ 有阻塞调用
2 阻塞在哪
   → 搜 async def 里的 sqlite3/requests/time.sleep
3 SQL 变慢
   → set_trace_callback 数条数 → N+1？
4 报 database is locked
   → 看 timeout / 并发写 / 事务长度
5 延迟高但 CPU 空闲
   → 线程池耗尽
```

### 6.3 代码约定

| 约定 | 理由 |
| --- | --- |
| `async def` 只放 `await` | 杜绝阻塞 |
| 同步 DB 一律 `def` 端点 | 让框架管线程 |
| 仓储方法保持同步 | 迟早要在线程里跑 |
| 不在仓储里 `commit` | 事务边界在依赖（第 57 章）|

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[A1]` | 官方文档 | https://docs.python.org/3/library/asyncio-task.html#asyncio.to_thread | `to_thread` |
| `[A2]` | 文档 | https://aiosqlite.omnilib.dev/en/stable/ | aiosqlite 模型 |
| `[A3]` | 文档 | https://www.sqlite.org/lockingv3.html | SQLite 锁 |

> **核对状态**：`[A1]`–`[A3]` 为官方文档链接，**本次未逐页直连复核**；5 并发耗时（阻塞/`to_thread`/`def`）、慢 SQL 两种模式、心跳最大间隔、N+1/IN/JOIN 条数与结果一致、线程池上限与唯一线程数、`database is locked` 与 `busy_timeout`、异常传播均为本机实测，`examples/verify.py` 复现 15/15 通过。`contextvars` 自动传播、线程池耗尽、`asyncpg`、MySQL 锁**未实测**；耗时为单机中位数，**绝对值随机器变化，量级关系可参考**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 为什么单线程事件循环怕阻塞
- [ ] `to_thread` 把任务交给谁
- [ ] 线程池上限公式与「并发上限」的区别
- [ ] N+1 的成因
- [ ] `database is locked` 的触发条件

**能写出（代码层）**：

- [ ] `to_thread` 版本
- [ ] `def` 版本
- [ ] `set_trace_callback` 计数
- [ ] `IN` / `JOIN` 改写
- [ ] `busy_timeout` 配置

**能判断（避坑层）**：

- [ ] 看到 `async def` + `sqlite3` → 指出阻塞
- [ ] 看到循环查库 → 指出 N+1
- [ ] 看到 `timeout=0` → 指出锁风险
- [ ] 看到 `gather` 跑 N 条 SQL → 指出池耗尽
- [ ] 看到 tick 数判阻塞 → 指出时钟粒度

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 15/15
- [ ] 手工把 `/blocking` 改成 `def`，看耗时降到 1/5
- [ ] `curl "/posts/n-plus-one"` 看 `query_count=201`

## 9. 下一章衔接

第 60 章 `StreamingResponse`：用生成器边查边发、`yield` 分块、`bytes` 与 `str` 的差别、客户端断开后的清理、为什么流式响应不能开 GZip。

本章留下的伏笔：

1. 分页要一次性 `fetchall()`（58）→ 60 改成边查边发。
2. 阻塞调用（59）→ 60 的生成器里同样不能阻塞。
3. 事务边界（57）→ 60 的长连接流要避免长事务。