# 27 异步编程 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把截图里的「异步生成器与异步迭代器、异步上下文管理器、官方 `asyncio` 核心 API、第三方异步库、常见异步编程模式、最佳实践与注意事项」逐条展开，目标是**学一遍即可毕业**。
>
> **本章示例不联网、不写磁盘**；第三方库只做选型说明，不做网络实测。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 / Windows 实测） |
| 前置 | 第 24–26 章（事件循环、Future、协程） |
| 覆盖范围 | `async for`/`async with`、异步生成器、`gather`/`TaskGroup`/`wait`/`as_completed`、`Lock`/`Event`/`Semaphore`/`Condition`/`Queue`、`wait_for`/`timeout`、`to_thread`、限流/重试/批处理/优雅关闭、debug 模式 |
| 明确不覆盖 | 第三方库内部实现、HTTP/WebSocket 协议、`asyncio.Stream` 服务器开发 |
| 学完验收 | 能说清 `gather` 的保序与异常行为、能写出限流+超时+重试的可运行代码、能优雅关闭任务组（见第 11 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Sn]` `` 指向第 10 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果。

**推荐顺序**：

```text
1 异步迭代/上下文（第 1–2 节） → 语法层
2 asyncio 核心 API（第 3 节）   → 工具层（重点）
3 第三方库（第 4 节）           → 选型
4 编程模式（第 5 节）           → 模式层
5 最佳实践与坑（第 6 节）       → 避坑
6 综合示例（第 7 节）
7 注意事项（第 8 节）           → 41 条错误对照
```

**与 README 的分工**：README 给结论与边界，本文件负责 API 语义、模式代码与实测证据。冲突时以本文件为准。

## 1. 异步生成器与异步迭代器

### 1.1 `async for`

```python
async def agen(count):
    for index in range(count):
        yield index


async def main():
    print([item async for item in agen(3)])
```

```text
ASYNC_FOR [0, 1, 2]
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `async def` + `yield` = 异步生成器 | 可被 `async for` 消费 | `[S5]` |
| 每次 `yield` 之间可 `await` | 适合流式产出 | `[S5]` |
| 不能用普通 `for` 消费 | `TypeError` | `[S5]` |

### 1.2 自定义异步迭代器

```python
class Ticker:
    def __init__(self, count):
        self.count = count
        self.index = 0

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self.index >= self.count:
            raise StopAsyncIteration
        self.index += 1
        await asyncio.sleep(0)
        return self.index
```

| 协议 | 要求 | 依据 |
| --- | --- | --- |
| `__aiter__` | 返回迭代器对象（通常 `self`） | `[S5]` |
| `__anext__` | 协程，返回下一项 | `[S5]` |
| 结束 | 抛 `StopAsyncIteration` | `[S5]` |
| 用 `return` 结束 | 会变成运行时错误 | `[S5]` |

> 注意：`__anext__` 是**协程函数**（`async def`），忘了 `async` 会导致 `TypeError: 'coroutine' object is not an iterator` 之类的怪错。`[S5]`

### 1.3 异步生成器表达式

| 写法 | 说明 | 依据 |
| --- | --- | --- |
| `[x async for x in agen()]` | 列表推导 | `[S5]` |
| `{x async for x in agen()}` | 集合推导 | `[S5]` |
| `{k: v async for ...}` | 字典推导 | `[S5]` |
| `(x async for x in agen())` | 异步生成器表达式 | `[S5]` |

### 1.4 与同步生成器的边界

| 场景 | 用 | 依据 |
| --- | --- | --- |
| 纯计算产出 | 同步生成器 | 17 章 |
| 每步要 `await` I/O | 异步生成器 | `[S5]` |
| 消费端是同步 `for` | 同步生成器 | `[S5]` |
| 流式响应（SSE/LLM token） | 异步生成器 | `[S5]` |

> 注意：异步生成器不能「部分消费后丢弃」还不清理——需要 `aclose()`，推荐用 `async with aclosing(...)`（`contextlib.aclosing`）。`[S5]`

## 2. 异步上下文管理器

### 2.1 `async with`

```python
class AsyncResource:
    async def __aenter__(self):
        print("AENTER")
        return self

    async def __aexit__(self, *exc):
        print("AEXIT")
        return False


async with AsyncResource():
    print("ASYNC_BODY")
```

实测：

```text
AENTER
ASYNC_BODY
AEXIT
```

| 方法 | 语义 | 依据 |
| --- | --- | --- |
| `__aenter__` | 协程，进入时 `await` | `[S1]` |
| `__aexit__` | 协程，退出时 `await` | `[S1]` |
| 返回 `True` | 抑制异常 | `[S1]` |
| 返回 `False`/`None` | 不抑制 | `[S1]` |

### 2.2 与同步 `with` 的区别

| 维度 | `with` | `async with` | 依据 |
| --- | --- | --- | --- |
| 方法 | `__enter__`/`__exit__` | `__aenter__`/`__aexit__` | `[S1]` |
| 能否 `await` | ❌ | ✅ | `[S1]` |
| 混用 | `with` 异步对象 → `TypeError` | —— | `[S1]` |

### 2.3 `@asynccontextmanager`

```python
from contextlib import asynccontextmanager

@asynccontextmanager
async def session():
    print("OPEN")
    try:
        yield {"ready": True}
    finally:
        print("CLOSE")
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 必须 `try/finally` 包 `yield` | 否则异常时跳过清理 | 18 章 |
| `yield` 一次 | 两次报错 | 18 章 |
| 异常会抛到 `yield` 处 | 可捕获后决定是否抑制 | `[S1]` |

### 2.4 `AsyncExitStack`

| 用途 | 说明 | 依据 |
| --- | --- | --- |
| 动态注册多个异步清理 | 数量在运行时才定 | `[S1]` |
| `enter_async_context(cm)` | 进入并注册 | `[S1]` |
| `push_async_callback(fn)` | 注册回调 | `[S1]` |
| 退出顺序 | 后进先出 | `[S1]` |
| 同步版本 | `ExitStack`（18 章） | `[S1]` |

```python
from contextlib import AsyncExitStack

async def connect_all(targets):
    async with AsyncExitStack() as stack:
        clients = [await stack.enter_async_context(connect(t)) for t in targets]
        return clients
```

### 2.5 异常抑制

| `__aexit__` 返回 | 效果 | 依据 |
| --- | --- | --- |
| `True` | 吞掉异常 | `[S1]` |
| `False` / `None` | 继续抛出 | `[S1]` |
| 抛新异常 | 覆盖原异常 | `[S1]` |

> 注意：抑制异常在生产里很危险——上层会以为「成功了」。只在明确语义（如「文件不存在视为空」）时用，并记日志。`[S1]`

## 3. 官方 asyncio 核心 API

### 3.1 `sleep`：非阻塞等待

| 写法 | 行为 | 依据 |
| --- | --- | --- |
| `await asyncio.sleep(0)` | 让出一次，不等待 | `[S1]` |
| `await asyncio.sleep(1)` | 非阻塞等待 1s | `[S1]` |
| `time.sleep(1)` | **阻塞整个循环** | `[S1]` |

实测阻塞代价：

```text
BLOCK_IN_CORO_MS 50
```

一个 50ms 的同步调用，把同循环内只需 10ms 的任务一起拖到 50ms。

### 3.2 `create_task`：把协程包成 Task

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 立即排队，不等 `await` | 创建后 `done()` 为 `False` | `[S1]` |
| 必须保留引用 | 否则可能被 GC | `[S1]` |
| 可传 `name=` | 便于日志与调试 | `[S1]` |
| 异常不自动冒泡 | 需 `await` 或回调 | `[S1]` |

```python
task = asyncio.create_task(work("a"), name="tool-a")
```

### 3.3 `gather`：并发执行并聚合

```python
results = await asyncio.gather(fetch("search", 0.05), fetch("cache", 0.05))
```

| 特性 | 行为 | 依据 |
| --- | --- | --- |
| 返回值顺序 | **与输入顺序一致**，与完成先后无关 | `[S1]` |
| 一个任务抛异常 | 立即向上抛（默认） | `[S1]` |
| 其余任务 | **不会被取消**，继续跑 | `[S1]` |
| `return_exceptions=True` | 异常作为结果返回 | `[S1]` |
| 空参数 | 返回 `[]`（实测） | `[S1]` |

实测异常行为：

```text
GATHER_RAISE boom
GATHER_REI ['ValueError', 'ok']
GATHER_FAILED_FAST []
GATHER_OTHERS_SURVIVED ['slow-finished']
GATHER_EMPTY []
```

| 结论 | 说明 | 依据 |
| --- | --- | --- |
| 默认不取消其余 | 慢任务仍跑完（实测 `slow-finished`） | `[S1]` |
| 想「一个失败全停」 | 用 `TaskGroup` | `[S1]` |
| `return_exceptions=True` | 适合「尽力而为」的批量 | `[S1]` |

> 注意：`gather` 默认「失败也不取消别人」这一点非常反直觉——你以为抛出异常就停了，实际上其他任务还在后台跑，可能继续写数据库/发请求。需要全停就用 `TaskGroup`。`[S1]`

### 3.4 `TaskGroup`：结构化并发（3.11+）

```python
async with asyncio.TaskGroup() as group:
    group.create_task(fail(0.01))
    group.create_task(fail(0.05))
```

实测：

```text
TG_EXCEPT_STAR 1
TG_SUCCESS [1, 2]
```

| 特性 | 行为 | 依据 |
| --- | --- | --- |
| 任一任务失败 | 取消同组其余任务 | `[S1]` |
| 错误汇总 | 抛 `ExceptionGroup` | `[S1]` |
| 捕获方式 | `except* ValueError:` | `[S7]` |
| 正常退出 | 所有任务完成后才退出 `async with` | `[S1]` |
| 自动等待 | 不需要 `gather` | `[S1]` |

| 对比 | `gather` | `TaskGroup` | 依据 |
| --- | --- | --- | --- |
| 失败时取消其余 | ❌ | ✅ | `[S1]` |
| 异常类型 | 原始异常 | `ExceptionGroup` | `[S1]` |
| 需要手动 `await` | ✅ | ❌（`async with` 边界） | `[S1]` |
| 版本 | 全版本 | 3.11+ | `[S1]` |

> 注意：`TaskGroup` 的「结构化」体现在作用域——`async with` 块退出时保证所有子任务都已结束（完成或取消）。这是比 `gather` 更安全的默认选择。`[S1]`

### 3.5 `wait`：更灵活的等待

```python
done, pending = await asyncio.wait(jobs, return_when=asyncio.FIRST_COMPLETED)
```

| 参数 | 取值 | 依据 |
| --- | --- | --- |
| `return_when` | `FIRST_COMPLETED` / `FIRST_EXCEPTION` / `ALL_COMPLETED` | `[S1]` |
| `timeout` | 超时后返回 `(done, pending)` | `[S1]` |
| 返回 | `(done_set, pending_set)` | `[S1]` |

实测：

```text
WAIT_FIRST_SPLIT 1 1
WAIT_TIMEOUT 0 1
WAIT_EMPTY_ERR Set of Tasks/Futures is empty.
WAIT_CORO_ERR Passing coroutines is forbidden, use tasks explicitly
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 只接受 Task/Future | 传协程报 `TypeError`（3.11+） | `[S1]` |
| 空集合报 `ValueError` | 实测 | `[S1]` |
| 超时返回 pending | 不自动取消 | `[S1]` |
| pending 要自己清理 | `cancel` + `gather` | `[S1]` |

> 注意：`wait` 不会帮你取消超时的任务——返回的 `pending` 还在跑。必须显式 `cancel()` 并 `await` 一次，否则任务泄漏。`[S1]`

### 3.6 `as_completed`：谁先完成先处理

```python
order = [await job for job in asyncio.as_completed(jobs)]
```

实测：

```text
AS_COMPLETED [0.01, 0.02, 0.03]
```

| 特性 | 行为 | 依据 |
| --- | --- | --- |
| 顺序 | **完成顺序**，不是输入顺序 | `[S1]` |
| 每项是 awaitable | `await` 得到结果 | `[S1]` |
| 适合 | 流式处理、尽早失败 | `[S1]` |

| 需求 | 用 | 依据 |
| --- | --- | --- |
| 结果与输入同序 | `gather` | `[S1]` |
| 谁先好先处理 | `as_completed` | `[S1]` |
| 一个失败全停 | `TaskGroup` | `[S1]` |

### 3.7 `Lock`：互斥

```python
lock = asyncio.Lock()

async with lock:
    value = shared
    await asyncio.sleep(0)
    shared = value + 1
```

实测评测：

```text
LOCK_COUNTER 5
RACE_COUNTER 1
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 无锁时 5 次自增只得到 1 | 所有协程读到同一个初值 | `[S2]` |
| 加锁后得到 5 | 读改写原子 | `[S2]` |
| `locked()` 可查询 | 实测 | `[S2]` |

> 注意：`async with lock` 只在**块内**互斥。块内如果有 `await`，别的任务会被阻塞在锁外——这通常是期望行为，但也可能造成排队延迟。`[S2]`

### 3.8 `Event`：事件通知

```python
ready = asyncio.Event()
await ready.wait()
ready.set()
```

实测：

```text
EVENT_BEFORE_SET False
EVENT_AFTER_SET woken
```

| 方法 | 作用 | 依据 |
| --- | --- | --- |
| `set()` | 置位，唤醒所有等待者 | `[S2]` |
| `clear()` | 复位 | `[S2]` |
| `is_set()` | 查询 | `[S2]` |
| `wait()` | 等待置位（协程） | `[S2]` |

| 对比 | `Event` | `Condition` | 依据 |
| --- | --- | --- | --- |
| 语义 | 一次性广播 | 带谓词的等待/通知 | `[S2]` |
| 适合 | 启动信号、关闭信号 | 生产者/消费者 | `[S2]` |

### 3.9 `Semaphore`：限制并发

```python
sem = asyncio.Semaphore(2)
async with sem:
    await call()
```

实测峰值：

```text
SEM_PEAK 2
RATE_LIMIT_PEAK 2
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 计数信号量 | 同时最多 N 个 | `[S2]` |
| `locked()` | 值为 0 时 `True` | `[S2]` |
| 适合 | 限流、连接池 | `[S2]` |

> 注意：`Semaphore` 只限制「同时进行的数量」，不限制「单位时间内的请求数」。要做 QPS 限流，需要令牌桶/滑动窗口，标准库没有现成实现。`[S2]`

### 3.10 `Queue`：异步队列

```python
channel = asyncio.Queue(maxsize=2)
await channel.put(item)
item = await channel.get()
channel.task_done()
await channel.join()
```

实测：

```text
QUEUE [0, 1, 2]
QUEUE_MAXSIZE 2
QUEUE_JOIN_DONE 0
```

| 方法 | 作用 | 依据 |
| --- | --- | --- |
| `put(x)` | 满时等待（协程） | `[S3]` |
| `put_nowait(x)` | 满时抛 `QueueFull` | `[S3]` |
| `get()` | 空时等待（协程） | `[S3]` |
| `get_nowait()` | 空时抛 `QueueEmpty` | `[S3]` |
| `task_done()` | 标记一项处理完 | `[S3]` |
| `join()` | 等所有项处理完 | `[S3]` |
| `qsize()` / `empty()` / `full()` | 状态查询 | `[S3]` |

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| `get` 后不 `task_done` | `join()` 永远不返回 | `[S3]` |
| `join()` 前没 `put` 完 | 提前返回 | `[S3]` |
| 忘记哨兵值 | 消费者永不退出 | `[S3]` |

### 3.11 `wait_for`：给等待加上界

```python
await asyncio.wait_for(asyncio.sleep(0.05), timeout=0.01)
```

```text
WAIT_FOR_TIMEOUT True
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 超时抛 `TimeoutError` | 并取消被等待对象 | `[S1]` |
| 3.12 起推荐 `asyncio.timeout` | 语义更清晰 | `[S1]` |
| 传 `None` | 不超时 | `[S1]` |

### 3.12 `asyncio.timeout`：结构化超时（3.11+）

```python
try:
    async with asyncio.timeout(0.01):
        await asyncio.sleep(0.05)
except TimeoutError:
    print("timeout")
```

实测：

```text
TIMEOUT_CTX TimeoutError
TIMEOUT_NOT_EXPIRED False
```

| 特性 | 说明 | 依据 |
| --- | --- | --- |
| 基于上下文管理器 | 作用域清晰 | `[S1]` |
| `.expired()` | 是否超时 | `[S1]` |
| 超时抛内置 `TimeoutError` | 3.11+ | `[S1]` |
| 可嵌套 | 取最紧的那个 | `[S1]` |

| 对比 | `wait_for` | `timeout` | 依据 |
| --- | --- | --- | --- |
| 形式 | 函数包裹 | `async with` | `[S1]` |
| 能否覆盖多步 | ❌ 单次 | ✅ 整块 | `[S1]` |
| 建议 | 兼容旧代码 | 新代码首选 | `[S1]` |

### 3.13 在异步中运行同步代码

| 方式 | 用法 | 依据 |
| --- | --- | --- |
| `asyncio.to_thread(fn, *args)` | 简洁（3.9+） | `[S1]` |
| `loop.run_in_executor(None, fn, *args)` | 可指定 executor | `[S1]` |
| 线程 → 循环 | `asyncio.run_coroutine_threadsafe(coro, loop)` | `[S1]` |
| 循环 → 线程 | 上面两种 | `[S1]` |

实测跨线程：

```text
CROSS_THREAD thread-safe
```

```python
def worker():
    future = asyncio.run_coroutine_threadsafe(asyncio.sleep(0.01, result="ok"), loop)
    print(future.result(timeout=2))
```

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| `to_thread` 跑 CPU 密集 | 仍受 GIL 限制 | 28 章 |
| 线程里直接 `await` | 语法错误 | `[S1]` |
| 线程里调 `asyncio.run` | 新建循环，状态不共享 | `[S1]` |

## 4. 第三方异步库

| 库 | 用途 | 本机状态 | 依据 |
| --- | --- | --- | --- |
| `aiohttp` | 异步 HTTP 客户端/服务端 | 未安装 | `[S8]` |
| `httpx` | 支持同步/异步双模式 | 已安装 | `[S8]` |
| `aiofiles` | 异步文件 I/O | 未安装 | `[S8]` |
| `uvloop` | 更快的事件循环 | 未安装 | `[S8]` |

> 说明：`httpx` 本机已安装（`importlib.util.find_spec('httpx')` 为真），但本章**不联网**，不做实际请求验证。选型建议：新项目优先 `httpx`（同步/异步一套 API），需要 WebSocket/服务端再考虑 `aiohttp`。

| 场景 | 推荐 | 理由 |
| --- | --- | --- |
| 只是发 HTTP 请求 | `httpx.AsyncClient` | API 统一、类型齐全 |
| 需要长连接/WebSocket | `aiohttp` | 生态成熟 |
| 读写大文件 | `aiofiles` | 避免阻塞循环 |
| 追求极致吞吐 | `uvloop` | 平台受限，收益看场景 |

| 坑 | 说明 |
| --- | --- |
| 用 `requests` 写异步代码 | 阻塞整个循环 |
| 每个请求新建 `AsyncClient` | 连接池失效、性能差 |
| 忘记 `async with client` | 连接泄漏 |

## 5. 常见异步编程模式

### 5.1 并发批处理

```python
async def batched(items, size):
    for index in range(0, len(items), size):
        yield items[index:index + size]

async for chunk in batched(list(range(5)), 2):
    ...
```

实测：

```text
BATCHED [[0, 1], [2, 3], [4]]
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 分批控制峰值 | 避免一次起太多任务 | `[S1]` |
| 批内并发、批间串行 | 简单可靠 | `[S1]` |
| 用 `Semaphore` 亦可 | 更细粒度 | `[S2]` |

### 5.2 限速器

```python
sem = asyncio.Semaphore(2)

async def call():
    async with sem:
        await request()
```

实测峰值 2。

| 方式 | 语义 | 依据 |
| --- | --- | --- |
| `Semaphore(n)` | 同时最多 n 个 | `[S2]` |
| 令牌桶 | 单位时间 n 个 | 需自实现 |
| 队列 + 固定 worker 数 | 稳定吞吐 | `[S3]` |

### 5.3 重试（指数退避）

```python
delay = 0.001
for index in range(3):
    try:
        return await flaky()
    except RuntimeError:
        if index == 2:
            raise
        await asyncio.sleep(delay)
        delay *= 2
```

实测：

```text
BACKOFF_RESULT ok [1, 2, 3]
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 上限次数 | 必须有限 | 第 01 章 |
| 退避 + 抖动 | 避免雪崩 | `[S1]` |
| 只重试可恢复错误 | 不要重试 4xx | `[S1]` |
| 记录每次尝试 | 可观测 | `[S6]` |

### 5.4 优雅关闭

```python
jobs = [asyncio.create_task(long_job(str(i))) for i in range(3)]
await asyncio.sleep(0.01)
for job in jobs:
    job.cancel()
await asyncio.gather(*jobs, return_exceptions=True)
```

实测：

```text
GRACEFUL_SHUTDOWN ['0', '1', '2']
SHUTDOWN True
```

| 步骤 | 说明 | 依据 |
| --- | --- | --- |
| 1 标记停止接收新任务 | 关闭入口 | `[S1]` |
| 2 `cancel()` 所有在飞任务 | 触发取消 | `[S1]` |
| 3 `await` 收尾 | 确保取消生效 | `[S1]` |
| 4 关闭资源 | `async with` / `aclose` | `[S1]` |

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| 只 `cancel` 不 `await` | 任务可能未结束 | `[S1]` |
| `gather(return_exceptions=True)` 吞掉取消 | 要区分取消与失败 | `[S1]` |
| 取消在 CPU 密集段无效 | 只在 `await` 点生效 | `[S1]` |

### 5.5 `shield`：保护关键任务不被取消

```python
outer = asyncio.create_task(wrapper())   # wrapper 内 await asyncio.shield(inner)
outer.cancel()
```

实测：

```text
SHIELD_OUTER_CANCELLED True
SHIELD_INNER protected
```

| 语义 | 说明 | 依据 |
| --- | --- | --- |
| 外层取消 | 不影响内层 | `[S1]` |
| 内层继续跑 | 可稍后取结果 | `[S1]` |
| 风险 | 泄漏未收集的任务 | `[S1]` |

> 注意：`shield` 只能保护「被 shield 的那个 awaitable」，外层协程本身仍被取消。常用于「提交后必须完成」的写操作，但要确保有人等待内层结果。`[S1]`

### 5.6 超时熔断

| 层级 | 做法 | 依据 |
| --- | --- | --- |
| 单次调用 | `asyncio.timeout(x)` | `[S1]` |
| 整批 | `wait_for(gather(...), x)` | `[S1]` |
| 连续失败 | 计数 + 短路（熔断器） | 需自实现 |

## 6. 最佳实践与注意事项

### 6.1 不要在协程中调用同步阻塞函数

实测：

```text
BLOCK_IN_CORO_MS 50
```

| 反例 | 后果 | 依据 |
| --- | --- | --- |
| `time.sleep` | 卡住循环 | `[S1]` |
| `requests.get` | 卡住循环 | `[S8]` |
| `open().read()` 大文件 | 卡住循环 | `[S1]` |
| `subprocess.run` | 卡住循环 | `[S1]` |

正解：`await asyncio.to_thread(fn)`、换 async 库、`create_subprocess_exec`。

### 6.2 始终使用 `asyncio.run` 作为入口

| 反例 | 问题 | 依据 |
| --- | --- | --- |
| 手写 `new_event_loop` | 清理不全 | `[S1]` |
| 全局单例循环 | 生命周期失控 | `[S1]` |
| 嵌套 `run` | `RuntimeError` | `[S1]` |

### 6.3 小心协程对象未被 `await`

实测 debug 模式会给出完整创建栈：

```text
RuntimeWarning: coroutine 'never' was never awaited
Coroutine created at (most recent call last)
```

| 手段 | 作用 | 依据 |
| --- | --- | --- |
| `asyncio.run(..., debug=True)` | 完整回溯 | `[S6]` |
| `PYTHONASYNCIODEBUG=1` | 全局 | `[S6]` |
| 静态检查 | 未 await 的可疑调用 | 20 章 |

### 6.4 `gather` 异常处理

| 场景 | 行为 | 依据 |
| --- | --- | --- |
| 默认 | 第一个异常立即上抛，其余继续跑 | `[S1]` |
| `return_exceptions=True` | 异常作为结果 | `[S1]` |
| 需要全停 | 用 `TaskGroup` | `[S1]` |

```python
results = await asyncio.gather(*tasks, return_exceptions=True)
for item in results:
    if isinstance(item, Exception):
        logger.error("task failed", exc_info=item)
```

### 6.5 使用 debug 模式

| 检测项 | 说明 | 依据 |
| --- | --- | --- |
| 慢回调 | 超过 `slow_callback_duration` 告警 | `[S6]` |
| 未 await 协程 | 带创建栈 | `[S6]` |
| 未取结果的 Future | `Future exception was never retrieved` | `[S6]` |
| 耗时 I/O | 记录执行时间 | `[S6]` |

### 6.6 避免全局事件循环

| 反例 | 问题 | 依据 |
| --- | --- | --- |
| 模块级 `loop = asyncio.get_event_loop()` | 3.12 直接报错 | `[S1]` |
| 全局单例循环复用 | 跨线程不安全 | `[S1]` |
| 库内部自己 `run` | 与调用方循环冲突 | `[S1]` |

## 7. 综合示例：限流 + 超时 + 重试

```python
"""第 27 章综合示例：并发调用 + 限流 + 超时 + 重试。"""

import asyncio


async def main() -> None:
    sem = asyncio.Semaphore(2)
    attempts = {"search": 0, "cache": 0}

    async def call(name: str) -> str:
        async with sem:
            attempts[name] += 1
            if attempts[name] < 2:
                raise RuntimeError("transient")
            await asyncio.sleep(0.01)
            return name + ":ok"

    async def with_retry(name: str, tries: int = 3) -> str:
        for index in range(tries):
            try:
                async with asyncio.timeout(0.5):
                    return await call(name)
            except (RuntimeError, TimeoutError):
                if index == tries - 1:
                    raise
                await asyncio.sleep(0.001)

    results = await asyncio.gather(*(with_retry(name) for name in ("search", "cache")))
    print("RESULTS", results, "ATTEMPTS", attempts)


asyncio.run(main())
```

本机实测输出：

```text
RESULTS ['search:ok', 'cache:ok'] ATTEMPTS {'search': 2, 'cache': 2}
```

**逐段说明**：

| 代码 | 用到的机制 | 依据 |
| --- | --- | --- |
| `Semaphore(2)` | 并发上限 | `[S2]` |
| `asyncio.timeout(0.5)` | 单次超时 | `[S1]` |
| `for index in range(tries)` | 重试上限 | 第 01 章 |
| `gather` | 并发两个调用 | `[S1]` |
| `attempts` | 可观测性 | `[S6]` |

> 注意：这个示例里 `attempts` 是共享可变状态，靠 `Semaphore` 与事件循环的单线程模型保证不冲突；如果换成 `TaskGroup` + 更高并发，仍要注意 `await` 前后的读改写竞态。`[S2]`

## 8. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 协程里 `time.sleep` | 整个循环卡住 | `await asyncio.sleep` | `[S1]` |
| 协程里 `requests` | 卡住 | `httpx.AsyncClient` / `to_thread` | `[S8]` |
| 协程里同步读大文件 | 卡住 | `to_thread` / `aiofiles` | `[S1]` |
| `gather` 以为失败会取消其余 | 其余继续跑 | 用 `TaskGroup` | `[S1]` |
| `gather` 不检查 `return_exceptions` 结果 | 异常丢失 | 逐个判 `Exception` | `[S1]` |
| `wait` 传协程 | `TypeError` | 先 `create_task` | `[S1]` |
| `wait` 传空集合 | `ValueError` | 先判空 | `[S1]` |
| `wait` 超时后不取消 pending | 任务泄漏 | `cancel` + `await` | `[S1]` |
| `as_completed` 当保序 | 完成顺序 | 要保序用 `gather` | `[S1]` |
| `TaskGroup` 用 `except ValueError` | 捕获不到 | `except* ValueError` | `[S7]` |
| `TaskGroup` 里任务数巨大 | 内存/下游压力 | 分批 + `Semaphore` | `[S1]` |
| 只设总超时 | 单个调用卡住整批 | 每个调用都设 | `[S1]` |
| `timeout` 里做清理 `await` | 又超时 | 清理用 `shield` | `[S1]` |
| 用 `Semaphore` 当 QPS 限流 | 只限并发 | 令牌桶/滑动窗口 | `[S2]` |
| 忘 `task_done()` | `join()` 卡住 | 每 `get` 后调用 | `[S3]` |
| 队列消费者无退出条件 | 永不结束 | 哨兵值/关闭信号 | `[S3]` |
| `Queue(maxsize=0)` 以为有界 | 无界，可能 OOM | 显式设上限 | `[S3]` |
| 无锁修改共享计数 | 结果小于预期（实测 1/5） | `asyncio.Lock` | `[S2]` |
| 用同步 `Lock` | 阻塞/报错 | `asyncio.Lock` | `[S2]` |
| 用同步 `Event` | 阻塞循环 | `asyncio.Event` | `[S2]` |
| `async with` 用在同步对象 | `TypeError` | `with` | `[S1]` |
| `async for` 消费普通生成器 | `TypeError` | `for` | `[S5]` |
| 异步生成器不 `aclose` | 资源泄漏 | `async with aclosing` | `[S5]` |
| `__anext__` 写成普通 `def` | 类型错误 | `async def` | `[S5]` |
| 用 `return` 结束 `__anext__` | 运行错误 | `raise StopAsyncIteration` | `[S5]` |
| `asynccontextmanager` 无 `try/finally` | 异常时跳过清理 | 必须包 | 18 章 |
| `__aexit__` 返回 `True` 抑制异常 | 上层误以为成功 | 记日志 + 谨慎 | `[S1]` |
| `shield` 后不收集内层结果 | 任务泄漏 | 保存引用并 `await` | `[S1]` |
| `cancel` 后不 `await` | 取消未生效 | `await` + 捕获 | `[S1]` |
| 裸 `except:` 吞 `CancelledError` | 无法关闭 | `except Exception` | 16 章 |
| 用 `gather(return_exceptions=True)` 当错误处理 | 异常被静默 | 逐个判断 | `[S1]` |
| `create_task` 不保引用 | 任务消失 | 集合持有 | `[S1]` |
| 嵌套 `asyncio.run` | `RuntimeError` | `await` | `[S1]` |
| 循环里跑 CPU 密集 | 饿死 | 进程池 | 28 章 |
| `to_thread` 里跑 CPU 密集 | 受 GIL | 进程池 | 28 章 |
| 生产开 `PYTHONASYNCIODEBUG` | 变慢 | 仅排查期 | `[S6]` |
| 不设超时的外部调用 | 卡死 | 全链路超时 | `[S1]` |
| 重试不设上限 | 无限重试 | 次数 + 退避 | 第 01 章 |
| 重试不可恢复错误 | 放大故障 | 只重试 5xx/超时 | `[S1]` |
| 日志打印完整响应体 | 泄露 + 膨胀 | 脱敏 + 截断 | 第 01 章 |
| 优雅关闭不等待在飞任务 | 数据丢失 | `cancel` + `gather` | `[S1]` |

## 9. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 并发 I/O 用 `gather`/`TaskGroup` | 别手工散落 | `[S1]` |
| 需要全停用 `TaskGroup` | 结构化 | `[S1]` |
| 批量必限流 | `Semaphore` | `[S2]` |
| 每个外部调用都设超时 | 防雪崩 | `[S1]` |
| 重试有上限 + 退避 | 可恢复错误才重试 | 第 01 章 |
| 流式输出用异步生成器 | 边产出边发送 | `[S5]` |
| 资源用 `async with` | 保证释放 | `[S1]` |
| 关闭流程显式化 | 取消 + 等待 + 释放 | `[S1]` |
| 排查开 debug | 慢回调/未 await | `[S6]` |
| 共享状态集中 + 加锁 | 避免 `await` 竞态 | `[S2]` |

**风格示范**：

```python
"""batch 模块：受控并发的批量调用。

为什么用 Semaphore + TaskGroup：既要限制下游压力，又要失败即停。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable, Iterable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def run_all(
    items: Iterable[str],
    call: Callable[[str], Awaitable[T]],
    *,
    limit: int = 5,
    timeout: float = 10.0,
) -> list[T]:
    """并发执行，任一失败即取消其余并抛出。"""
    sem = asyncio.Semaphore(limit)
    results: list[T] = []

    async def guarded(item: str) -> None:
        async with sem:
            async with asyncio.timeout(timeout):
                results.append(await call(item))

    async with asyncio.TaskGroup() as group:
        for item in items:
            group.create_task(guarded(item))
    logger.info("run_all done", extra={"count": len(results)})
    return results
```

**边界**：

- 标准库没有 QPS 限流器，需要自实现或第三方库。
- `asyncio.timeout` 依赖 3.11+，低版本用 `wait_for`。
- 异步不是万能的：CPU 密集、阻塞库、交互式输入都要另想办法。

## 10. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[S1]` | python.org | https://docs.python.org/3.12/library/asyncio-task.html | `gather`/`TaskGroup`/`wait`/`as_completed`、`timeout`/`wait_for`、`shield`、取消、`to_thread`、`asyncio.run` |
| `[S2]` | python.org | https://docs.python.org/3.12/library/asyncio-sync.html | `Lock`/`Event`/`Semaphore`/`Condition` |
| `[S3]` | python.org | https://docs.python.org/3.12/library/asyncio-queue.html | `Queue`、`task_done`/`join`、`maxsize` |
| `[S4]` | PEP 官方 | https://peps.python.org/pep-0008/ | 命名、注释写「为什么」 |
| `[S5]` | PEP 官方 | https://peps.python.org/pep-0525/ | 异步生成器与 `async for` |
| `[S6]` | python.org | https://docs.python.org/3.12/library/asyncio-dev.html | debug 模式、慢回调、未 await 检测 |
| `[S7]` | PEP 官方 | https://peps.python.org/pep-0654/ | `ExceptionGroup` 与 `except*` |
| `[S8]` | python.org | https://docs.python.org/3.12/library/asyncio-streams.html | 流式 I/O 与第三方客户端的定位 |

> **核对状态**：`[S4]` 与本章 `README.md` 已核对来源一致；其余按 `docs.python.org/3.12` 官方结构整理，**本次未逐页直连复核**。文中「实测」为本机 Python 3.12.8 运行结果；第三方库只做选型说明，**未联网实测**。

## 11. 毕业自查清单

**能说清（概念层）**：

- [ ] `gather` 的保序与默认异常行为
- [ ] `gather` 失败时不取消其余任务意味着什么
- [ ] `TaskGroup` 为什么更安全
- [ ] `wait` 的三种 `return_when`
- [ ] `as_completed` 与 `gather` 的顺序差异
- [ ] `Semaphore` 与 QPS 限流的区别
- [ ] `asyncio.timeout` 与 `wait_for` 的取舍
- [ ] 同步阻塞库的三种隔离方式
- [ ] 优雅关闭的四步

**能写出（代码层）**：

- [ ] 异步生成器 + `async for`
- [ ] 自定义 `__aiter__`/`__anext__`
- [ ] `async with` 自定义资源 + `asynccontextmanager`
- [ ] `TaskGroup` + `except*`
- [ ] `Semaphore` 限流的批量调用
- [ ] 带退避的重试
- [ ] `cancel` + `gather(return_exceptions=True)` 优雅关闭
- [ ] `asyncio.timeout` 包住整块逻辑

**能判断（避坑层）**：

- [ ] 看到协程里同步 I/O 能指出阻塞
- [ ] 看到 `gather` 当「失败全停」能指出错
- [ ] 看到 `wait` 传协程能指出 `TypeError`
- [ ] 看到 `wait` 超时不清理能指出泄漏
- [ ] 看到 `Semaphore` 当 QPS 限流能指出区别
- [ ] 看到 `Queue.get` 不 `task_done` 能指出 `join` 卡死
- [ ] 看到 `__aexit__` 返回 `True` 能指出抑制风险

**能跑通（验收层）**：

- [ ] 运行 `examples/async_demo.py` 并解释保序
- [ ] 把第 7 节示例存成文件运行，输出与文档一致
- [ ] 复现一次 `RACE_COUNTER 1` 并加锁修好
- [ ] 用 debug 模式复现一次慢回调告警

## 12. 下一章衔接

第 28 章 `多线程与多进程`：并发的另一半——GIL、线程/进程/协程三方对比、`threading` 同步原语、`ThreadPoolExecutor`/`ProcessPoolExecutor`、何时用哪种。

本章留下的伏笔：

1. `to_thread` 与 `run_in_executor` 背后就是线程池，第 28 章展开。
2. `Semaphore` 的线程版 `threading.Semaphore` 语义相同但实现不同。
3. 「CPU 密集用进程」在第 28 章有实测数据支撑。