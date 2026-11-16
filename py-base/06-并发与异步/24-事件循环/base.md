# 24 事件循环 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把截图里的「同步代码的问题、什么是异步、异步 VS 多线程、Python 的事件循环（`AbstractEventLoop` 类、`run_forever` 方法、`_run_once` 逻辑）」逐条展开，并补上循环生命周期、回调调度、调试模式、阻塞隔离，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 / Windows 实测） |
| 前置 | 第 17、28 章（生成器、并发直觉） |
| 覆盖范围 | 同步阻塞的代价、协作式并发定义、异步 vs 多线程七维对比、`AbstractEventLoop` API、`run_forever`/`run_until_complete`/`asyncio.run`、`call_soon`/`call_later`/`call_soon_threadsafe`、`get_running_loop`、debug 模式、`to_thread` |
| 明确不覆盖 | 协程语法细节（26 章）、`gather`/`TaskGroup`（27 章）、`uvloop` 等第三方循环、C 层 selector 实现 |
| 学完验收 | 能说清任务何时切换、能解释 `time.sleep` 为何卡死整个循环、能写出正确的入口与阻塞隔离（见第 9 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[An]` `` 指向第 8 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果。时间类输出依赖机器负载，文档给「约」值并保留原始量级。

**推荐顺序**：

```text
1 同步代码的问题（第 1 节）  → 阻塞的代价
2 什么是异步（第 2 节）      → 协作式切换
3 异步 VS 多线程（第 3 节）  → 七维对比
4 事件循环（第 4 节）        → API + 生命周期 + 调试
5 综合示例（第 5 节）
6 注意事项（第 6 节）        → 40 条错误对照
```

**与 README 的分工**：README 给结论与边界，本文件负责机制、API 穷举与实测证据。冲突时以本文件为准。

## 1. 同步代码的问题

### 1.1 一个阻塞调用拖住全部

```python
import requests

def task1():
    requests.post(...)   # 发送请求，阻塞线程直到响应
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 同步 I/O 会阻塞当前线程 | 线程在等网络/磁盘 | `[A1]` |
| 单线程里阻塞 = 全部停摆 | 没有别的执行流可切换 | `[A1]` |
| 多线程能缓解但不免费 | 每线程有栈与切换成本 | 28 章 |

实测：3 次 50ms 的「I/O」串行执行，总计约 151ms。

```text
IO_SERIAL_MS 151
```

| 时间构成 | 说明 | 依据 |
| --- | --- | --- |
| 等待 I/O | 线程处于空闲但占着 | `[A1]` |
| 无法重叠 | 第二个必须等第一个返回 | `[A1]` |

> 注意：同步代码的问题不是「慢」，而是**等待期间什么都做不了**。CPU 并没有忙，只是执行流被占住了。`[A1]`

### 1.2 三种解决思路

| 思路 | 做法 | 代价 | 依据 |
| --- | --- | --- | --- |
| 多线程 | 每个阻塞调用一个线程 | 栈内存、切换、锁 | 28 章 |
| 多进程 | 每个任务一个进程 | 启动与 IPC 开销大 | 28 章 |
| 异步 | 单线程 + 事件循环 + 非阻塞 I/O | 必须全链路 async | `[A1]` |

| 场景 | 推荐 | 依据 |
| --- | --- | --- |
| 几十个阻塞库调用 | 线程池 | 28 章 |
| 上万并发连接 | 异步 | `[A1]` |
| CPU 密集计算 | 进程 | 28 章 |
| 混合 | 异步为主 + 线程池兜底同步库 | `[A6]` |

### 1.3 为什么不能「异步 + 同步库混着用」

```python
async def handler():
    requests.get(url)      # 错：阻塞整个循环
```

实测：在协程里执行 50ms 同步调用，同循环内另一个只需 10ms 的任务被推迟到 50ms 才结束。

```text
BLOCK_IN_CORO_MS 50
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `async def` 里写同步阻塞 | 循环无法切换 | `[A1]` |
| 影响范围是整个循环 | 所有任务一起等 | `[A6]` |
| 正解是 `to_thread` | 把阻塞挪到线程池 | `[A2]` |

## 2. 什么是异步

### 2.1 定义

| 概念 | 含义 | 依据 |
| --- | --- | --- |
| 异步 | 发起操作后不原地等待，先去做别的 | `[A2]` |
| 协程 | 可暂停/恢复的函数，`async def` 定义 | `[A5]` |
| 事件循环 | 单线程内调度协程与回调的调度器 | `[A1]` |
| 协作式 | 任务**主动**让出，不被强制抢占 | `[A1]` |

### 2.2 只有 `await` 才让出

```python
async def only_await_yields():
    loop = asyncio.get_running_loop()
    order = []
    loop.call_soon(order.append, "callback")
    time.sleep(0)                       # 不让出
    order.append("after-time-sleep-0")
    await asyncio.sleep(0)              # 让出
    order.append("after-await")
    print(order)
```

实测输出：

```text
['after-time-sleep-0', 'callback', 'after-await']
```

| 行为 | 是否让出 | 依据 |
| --- | --- | --- |
| `time.sleep(0)` | ❌ 只是系统调用返回 | `[A1]` |
| `await asyncio.sleep(0)` | ✅ 排队到下一轮 | `[A1]` |
| 普通函数调用 | ❌ | `[A1]` |
| `await` 一个已完成的 Future | ✅ 仍会走一次调度 | `[A1]` |

> 注意：这是理解事件循环的第一把钥匙——**切换不是「时间片到了」，而是「代码执行到 `await`」**。没有 `await` 的长循环就是死循环，循环里其他任务全部饿死。`[A1]`

### 2.3 异步 ≠ 并行

实测两个各 50ms 的协程：

| 执行方式 | 耗时 | 依据 |
| --- | --- | --- |
| 串行 `await` 两次 | 约 114ms | `[A1]` |
| `gather` 并发 | 约 61ms | `[A1]` |

```text
SERIAL_MS 114 CONCURRENT_MS 61
INTERLEAVE ['start a', 'start b', 'end a', 'end b']
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 并发（concurrency） | 交替推进，同一时刻只有一个在跑 | `[A1]` |
| 并行（parallelism） | 真正同时跑，需要多核 | 28 章 |
| 异步擅长 | I/O 等待的重叠 | `[A1]` |
| 异步不擅长 | CPU 计算（不让出就没法重叠） | `[A1]` |

### 2.4 异步的三要素

| 要素 | 作用 | 依据 |
| --- | --- | --- |
| 事件循环 | 调度器 | `[A1]` |
| 协程 / Task | 可暂停的执行单元 | `[A5]` |
| 非阻塞 I/O（selector） | 让循环知道「谁好了」 | `[A3]` |

> 注意：三者缺一不可。只写 `async def` 但没有非阻塞 I/O，等于把同步代码包了一层壳，反而更慢。`[A3]`

## 3. 异步 VS 多线程

### 3.1 七维对比

| 维度 | 异步（事件循环） | 多线程 | 依据 |
| --- | --- | --- | --- |
| 运行载体 | 单线程 | 多线程 | `[A1]` |
| 切换方式 | 协作式（`await`） | 抢占式（OS 调度） | `[A1]` |
| 切换成本 | 极低（函数调用级） | 较高（内核态） | 28 章 |
| 内存占用 | 每任务几 KB | 每线程数 MB 栈 | 28 章 |
| 数据共享 | 单线程天然安全，但 `await` 处有竞态 | 需锁 | `[A1]` |
| 利用多核 | ❌ | ❌（受 GIL 限制） | 28 章 |
| 适用 | 海量 I/O 并发 | 少量阻塞库调用 | `[A1]` |
| 调试难度 | 中（需理解调度） | 高（竞态难复现） | `[A6]` |

### 3.2 同一个阻塞的两种后果

| 场景 | 后果 | 依据 |
| --- | --- | --- |
| 线程里阻塞 | 只卡住这个线程 | 28 章 |
| 循环里阻塞 | 卡住所有任务 | `[A1]` |

实测对比：

```text
IO_SERIAL_MS 151          # 同步串行
IO_THREADS_MS 52          # 3 线程并发
BLOCK_DELAYED_MS 50       # 循环内阻塞，其它任务被迫等到 50ms
```

### 3.3 选型判断

| 判断项 | 选异步 | 选线程 |
| --- | --- | --- |
| 依赖库有 async 版本 | ✅ | —— |
| 依赖库只有同步版本 | `to_thread` 兜底 | ✅ 直接 |
| 并发量 > 1000 | ✅ | ❌ 线程太多 |
| 需要长时间 CPU 计算 | ❌ | ❌（用进程） |
| 团队不熟 async | ❌ 学习成本高 | ✅ |
| 依据 | `[A1]` | `[A1]` |

> 注意：不要为了「技术先进」把同步项目改成异步。改造成本包括：所有 I/O 库换 async 版、所有调用链加 `await`、测试与调试方式重学。收益只在**高并发 I/O** 场景才成立。`[A1]`

## 4. Python 的事件循环

### 4.1 三种实现

| 实现 | 平台 | 特点 | 依据 |
| --- | --- | --- | --- |
| `SelectorEventLoop` | Linux/macOS 默认 | 基于 `selectors`，支持子进程受限 | `[A3]` |
| `ProactorEventLoop` | Windows 默认（3.8+） | 基于 IOCP，支持子进程 | `[A7]` |
| `uvloop`（第三方） | Linux/macOS | 更快，非标准库 | —— |

本机实测：

```python
asyncio.run(main())     # main 内 asyncio.get_running_loop()
```

```text
LOOP_TYPE ProactorEventLoop
LOOP_DEBUG False
HAS_RUN_ONCE True
IS_RUNNING True
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| Windows 默认 Proactor | 3.8 起 | `[A7]` |
| `_run_once` 存在但是内部方法 | 非公开 API | `[A1]` |
| `get_debug()` 默认 `False` | 未开调试 | `[A6]` |

> 注意：`_run_once` 是 CPython 的内部实现细节（实测 `hasattr(loop, "_run_once")` 为 `True`），**不要调用**。理解它有助于知道「一次迭代 = 处理到期定时器 + 处理 I/O 事件 + 跑就绪回调」，但代码不应依赖。`[A1]`

### 4.2 `AbstractEventLoop` 的 API 分类

| 类别 | 方法 | 依据 |
| --- | --- | --- |
| 运行控制 | `run_forever()` `run_until_complete(future)` `stop()` `close()` `is_running()` `is_closed()` | `[A1]` |
| 回调调度 | `call_soon(cb, *args)` `call_later(delay, cb, *args)` `call_at(when, cb, *args)` `call_soon_threadsafe(...)` | `[A1]` |
| 任务 | `create_task(coro)` `create_future()` | `[A1]` |
| 线程/进程池 | `run_in_executor(executor, fn, *args)` `set_default_executor(executor)` | `[A1]` |
| 网络 | `create_server` `create_connection` `create_datagram_endpoint` | `[A1]` |
| 信号（Unix） | `add_signal_handler` `remove_signal_handler` | `[A1]` |
| 调试 | `set_debug(enabled)` `get_debug()` `slow_callback_duration` | `[A6]` |
| 异常处理 | `set_exception_handler(handler)` `default_exception_handler` | `[A1]` |
| 生命周期钩子 | `add_reader` `add_writer` `remove_reader` `remove_writer` | `[A1]` |

```python
import asyncio
import inspect

print([name for name, _ in inspect.getmembers(asyncio.AbstractEventLoop, inspect.isfunction)][:12])
```

### 4.3 `run_forever` 与 `_run_once`

```python
loop = asyncio.new_event_loop()
loop.call_later(0.02, loop.stop)
loop.run_forever()
print(loop.is_running(), loop.is_closed())
loop.close()
```

实测：

```text
RUN_FOREVER_DONE False False
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `run_forever` 一直跑直到 `stop()` | 阻塞调用 | `[A1]` |
| `stop()` 只是「本轮结束后停」 | 不立即中断 | `[A1]` |
| `run_forever` 返回后循环未关闭 | 之后要 `close()` | `[A1]` |

一次迭代的典型工作（`_run_once` 语义）：

```text
1 计算下次超时：取最近的定时器
2 等待 I/O 事件（或超时）
3 把到期的定时器回调放入就绪队列
4 依次执行就绪回调（每个回调就是一个 Handle）
5 检查是否有 stop 请求
```

| 步骤 | 关键点 | 依据 |
| --- | --- | --- |
| 2 | 没有就绪任务时就阻塞在 selector 上 | `[A3]` |
| 4 | 一个回调执行期间**不会**切换 | `[A1]` |
| 4 | 回调里抛异常走 `exception_handler` | `[A1]` |

> 注意：`run_forever` 期间如果没有任何定时器和 I/O，循环会一直阻塞在 selector 上——不会空转烧 CPU，但也说明「没有事件就没有进展」。`[A3]`

### 4.4 循环生命周期

| 阶段 | 做法 | 依据 |
| --- | --- | --- |
| 创建 | `asyncio.new_event_loop()` | `[A1]` |
| 设为当前线程的循环 | `asyncio.set_event_loop(loop)` | `[A1]` |
| 跑一个协程 | `loop.run_until_complete(coro)` | `[A1]` |
| 跑到底 | `loop.run_forever()` | `[A1]` |
| 停止 | `loop.stop()` | `[A1]` |
| 关闭 | `loop.close()` | `[A1]` |
| 推荐 | `asyncio.run(coro)` 一把梭 | `[A8]` |

实测 `run_until_complete`：

```text
RUN_UNTIL x
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `run_until_complete` 返回协程结果 | 实测返回 `"x"` | `[A1]` |
| 关闭后再用会 `RuntimeError` | 循环不可复用 | `[A1]` |
| 线程与循环绑定 | 一个循环通常只在一个线程跑 | `[A1]` |

### 4.5 `asyncio.run` 到底做了什么

```text
1. 创建一个新事件循环
2. 把它设为当前线程的循环
3. run_until_complete(main_task)
4. 结束时：取消剩余任务 → 关闭异步生成器 → 关闭默认 executor → 关闭循环
```

| 步骤 | 说明 | 依据 |
| --- | --- | --- |
| 1–2 | 自动管理，不用手写 | `[A8]` |
| 3 | 顶层协程包成 Task 再跑 | `[A8]` |
| 4 | 清理顺序固定，避免资源泄漏 | `[A8]` |
| 返回值 | 就是协程的 `return` 值 | `[A8]` |

实测返回值：

```text
RUN_RETURN ret
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 一个线程同时只能有一个运行中的循环 | 嵌套 `run` 报错 | `[A8]` |
| `asyncio.run` 结束后不留当前循环 | 3.12 实测导致 `get_event_loop` 报错 | `[A1]` |

嵌套实测：

```text
NESTED_RUN_ERR asyncio.run() cannot be called from a running event loop
```

> 注意：Jupyter / IPython 里已经在跑循环，直接 `asyncio.run()` 会报这个错。正确做法是在 notebook 里直接 `await coro`，或 `await asyncio.create_task(...)`。`[A8]`

### 4.6 `get_running_loop` 与 `get_event_loop`

| 函数 | 在协程内 | 在同步代码里 | 依据 |
| --- | --- | --- | --- |
| `get_running_loop()` | 返回运行中的循环 | `RuntimeError: no running event loop` | `[A1]` |
| `get_event_loop()` | 返回运行中的循环 | 3.12 起 `RuntimeError`（不再自动创建） | `[A1]` |

实测：

```text
RUNNING_LOOP True
OUTSIDE_RUNNING_ERR no running event loop
SET_LOOP_THEN_GET True
NO_LOOP_ERR There is no current event loop in thread 'Ma...
```

| 写法 | 结论 | 依据 |
| --- | --- | --- |
| `asyncio.get_running_loop()` | ✅ 首选，语义明确 | `[A1]` |
| `asyncio.get_event_loop()` | ⚠️ 3.12 行为已变，避免 | `[A1]` |
| `asyncio.set_event_loop(loop)` 后 `get_event_loop()` | 返回设置的循环（实测） | `[A1]` |

> 注意：这是 3.12 的真实行为变化——**没有当前循环时 `get_event_loop()` 直接抛 `RuntimeError`**，不再像旧版本那样「创建一个并给 DeprecationWarning」。老代码里靠它隐式拿循环的写法会直接崩。`[A1]`

### 4.7 回调调度

| 方法 | 语义 | 依据 |
| --- | --- | --- |
| `call_soon(cb, *args)` | 下一轮就绪队列尾部执行（FIFO） | `[A1]` |
| `call_later(delay, cb, *args)` | `delay` 秒后执行 | `[A1]` |
| `call_at(when, cb, *args)` | 在指定时刻执行（基于 `loop.time()`） | `[A1]` |
| `call_soon_threadsafe(cb, *args)` | 从**其他线程**安全投递 | `[A1]` |

实测顺序：

```text
CALL_ORDER ['sync', 'soon', 'later-20ms']
```

| 现象 | 原因 | 依据 |
| --- | --- | --- |
| `sync` 最先 | 同步代码直到 `await` 才停 | `[A1]` |
| `soon` 次之 | `call_soon` 排在下一轮 | `[A1]` |
| `later-20ms` 最后 | 定时器未到期 | `[A1]` |

跨线程投递实测：

```python
def worker():
    time.sleep(0.01)
    loop.call_soon_threadsafe(order.append, "from-thread")
```

```text
THREADSAFE ['from-thread']
```

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| 在别的线程直接 `call_soon` | 非线程安全，可能崩 | `[A1]` |
| `call_soon` 里做重活 | 阻塞整个循环 | `[A1]` |
| 回调异常 | 走 `exception_handler`，不冒泡到 `await` | `[A1]` |

### 4.8 调试模式

| 开关 | 作用 | 依据 |
| --- | --- | --- |
| `asyncio.run(coro, debug=True)` | 本次运行开调试 | `[A8]` |
| `loop.set_debug(True)` | 运行中开 | `[A6]` |
| `PYTHONASYNCIODEBUG=1` | 环境变量全局开 | `[A6]` |
| `loop.slow_callback_duration` | 慢回调阈值（默认 0.1s） | `[A6]` |

实测：把阈值调到 5ms，然后执行 50ms 同步阻塞。

```python
loop.set_debug(True)
loop.slow_callback_duration = 0.005
time.sleep(0.05)
```

stderr 会打印：

```text
Executing <Task ...> took 0.050 seconds
```

| 调试能力 | 说明 | 依据 |
| --- | --- | --- |
| 慢回调告警 | 定位「谁阻塞了循环」 | `[A6]` |
| 未 await 协程的创建栈 | debug 下带完整回溯 | `[A6]` |
| 未消费的 Future 异常 | 提示 `Future exception was never retrieved` | `[A6]` |

> 注意：debug 模式有额外开销，只在排查期开。生产用采样/APM，不要长期开 `PYTHONASYNCIODEBUG=1`。`[A6]`

### 4.9 阻塞隔离

| 方式 | 用法 | 依据 |
| --- | --- | --- |
| `asyncio.to_thread(fn, *args)` | 简洁，3.9+ | `[A2]` |
| `loop.run_in_executor(None, fn, *args)` | 显式，可换 executor | `[A1]` |
| 专用线程池 | `ThreadPoolExecutor` 控制并发 | 28 章 |

实测：

```text
TO_THREAD thread-done 51
RUN_IN_EXECUTOR 1024
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `to_thread` 不阻塞循环 | 返回协程，等线程完成 | `[A2]` |
| 默认线程池有上限 | `min(32, cpu+4)` 级别 | 28 章 |
| 线程池里有 GIL | 只适合阻塞 I/O，不适合 CPU | 28 章 |

> 注意：`to_thread` 不是万能药——它把阻塞挪到线程，但如果任务本身是 CPU 密集，仍然受 GIL 限制，应该用进程池。`[A2]`

## 5. 综合示例：单线程并发处理

```python
"""第 24 章综合示例：事件循环内的并发与回调。"""

import asyncio
import time


async def fetch(name: str, delay: float) -> str:
    await asyncio.sleep(delay)
    return name + ":ok"


async def main() -> None:
    loop = asyncio.get_running_loop()
    order: list[str] = []
    loop.call_soon(order.append, "scheduled")

    started = time.perf_counter()
    results = await asyncio.gather(fetch("search", 0.05), fetch("cache", 0.05))
    elapsed = int((time.perf_counter() - started) * 1000)

    print("RESULTS", results)
    print("ELAPSED_MS", elapsed)
    print("ORDER", order)


asyncio.run(main())
```

本机实测输出：

```text
RESULTS ['search:ok', 'cache:ok']
ELAPSED_MS 58
ORDER ['scheduled']
```

**逐段说明**：

| 代码 | 用到的机制 | 依据 |
| --- | --- | --- |
| `get_running_loop()` | 取当前循环 | `[A1]` |
| `call_soon` | 排队回调 | `[A1]` |
| `asyncio.gather` | 并发启动两个协程 | `[A1]` |
| `ELAPSED_MS ≈ 58` | 两个 50ms 重叠，不是 100ms | `[A1]` |
| `run` | 顶层入口 | `[A8]` |

> 注意：`ELAPSED_MS` 会随机器波动（实测 58–65ms）。**判断并发是否生效，看它是否接近单个任务耗时，而不是接近两倍**。`[A1]`

## 6. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 协程里 `time.sleep()` | 整个循环卡住 | `await asyncio.sleep()` | `[A1]` |
| 协程里 `requests.get` | 整个循环卡住 | `await httpx.AsyncClient()` 或 `to_thread` | `[A2]` |
| 协程里跑重 CPU 循环 | 所有任务饿死 | 进程池 | 28 章 |
| 手写 `new_event_loop` + `close` | 泄漏/未清理任务 | `asyncio.run` | `[A8]` |
| 嵌套 `asyncio.run` | `RuntimeError: cannot be called from a running event loop` | 直接 `await` | `[A8]` |
| 3.12 里靠 `get_event_loop()` 拿循环 | `RuntimeError: no current event loop` | `get_running_loop()` | `[A1]` |
| 在同步函数里 `get_running_loop` | `RuntimeError: no running event loop` | 先进入 `asyncio.run` | `[A1]` |
| 其他线程直接 `call_soon` | 偶发崩溃/不执行 | `call_soon_threadsafe` | `[A1]` |
| `call_soon` 里做重活 | 慢回调告警 | 拆成 Task | `[A6]` |
| 回调里抛异常期待被上层捕获 | 异常只进日志 | 回调内 try/except | `[A1]` |
| `run_forever` 后忘记 `close` | 资源未释放 | `try/finally: loop.close()` | `[A1]` |
| 以为 `stop()` 立即中断 | 当前回调跑完才停 | 别假设即时 | `[A1]` |
| 在已关闭循环上再跑 | `RuntimeError: Event loop is closed` | 新建循环 | `[A1]` |
| 一个循环跑在两个线程 | 未定义行为 | 一个循环一个线程 | `[A1]` |
| 用 `_run_once` / `_ready` 等私有属性 | 版本升级即崩 | 只用公开 API | `[A1]` |
| 生产开 `PYTHONASYNCIODEBUG=1` | 明显变慢 | 只在排查期开 | `[A6]` |
| 依赖 Windows 默认 `SelectorEventLoop` | 实际是 Proactor | 用 `type(loop).__name__` 判 | `[A7]` |
| 在 Proactor 上做 Unix 信号处理 | 不支持 | 换平台/换实现 | `[A7]` |
| `to_thread` 里跑 CPU 密集 | 仍被 GIL 卡 | 进程池 | 28 章 |
| `to_thread` 开太多 | 线程池耗尽 | 控制并发/用专用池 | `[A2]` |
| 以为 `await` 会切给「指定任务」 | 只交还循环，由循环决定 | 理解调度不可控 | `[A1]` |
| 以为 `asyncio.sleep(0)` 能跑满 CPU | 只是让出一轮 | 别当忙等用 | `[A1]` |
| 在 `finally` 里 `await` 清理 | 取消时可能再抛 | 用 `shield` 或接受取消 | `[A1]` |
| 用 `asyncio.run` 跑多个独立脚本段 | 每段都要新循环 | 每进程一次 | `[A8]` |
| 循环内 `input()` | 阻塞 | 交互式程序别用异步 | `[A1]` |
| 循环内 `print` 大量输出 | 慢但可接受 | 生产用日志 | `[A6]` |
| 忽略 `Future exception was never retrieved` | 静默丢错 | 消费结果 | 25 章 |
| 把 `asyncio` 当线程池用 | 没有并行 | 看任务类型选方案 | `[A1]` |
| 循环里同步写文件 | 阻塞 | `to_thread` 或 `aiofiles` | 27 章 |
| 循环里同步读大文件 | 阻塞 | 同上 | 27 章 |
| 用 `select` 自己轮询 | 重复造轮子 | 交给循环 | `[A3]` |
| 手动 `add_reader` 并忘记移除 | fd 泄漏 | 成对调用 | `[A1]` |
| 以为任务会自动取消 | 只有 `run` 结束才取消剩余 | 显式 `cancel` | `[A8]` |
| 在 `__del__` 里操作循环 | 循环可能已关闭 | 显式清理 | `[A1]` |
| 用 `time.time()` 做循环内计时 | 受系统时钟调整影响 | `time.perf_counter()` | `[A4]` |
| 在回调里 `await` | 语法错误（回调是普通函数） | 包成 Task | `[A1]` |
| 把阻塞库包在 `async def` 里就以为异步了 | 仍然阻塞 | 必须 `to_thread`/换库 | `[A2]` |
| 循环内调用 `subprocess.run` | 阻塞 | `asyncio.create_subprocess_exec` | `[A1]` |
| 以为 `loop.time()` 是墙钟时间 | 它是单调时钟 | 展示/日志用 `time.time()` | `[A1]` |
| 多进程里共享一个循环 | 不可能 | 每进程独立 | `[A7]` |

## 7. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 唯一入口 `asyncio.run()` | 应用层不手管循环 | `[A8]` |
| 只调 `get_running_loop()` | 语义明确 | `[A1]` |
| I/O 全用 awaitable 版本 | 否则阻塞 | `[A2]` |
| 同步库用 `to_thread` | 隔离阻塞 | `[A2]` |
| 长任务分段 `await` | 给其他任务机会 | `[A1]` |
| 关闭 debug 于生产 | 有开销 | `[A6]` |
| 回调内自带 try/except | 异常不冒泡 | `[A1]` |
| 跨线程用 `call_soon_threadsafe` | 线程安全 | `[A1]` |
| 计时用 `perf_counter` | 单调 | `[A4]` |
| 退出时取消并等待任务 | 避免「任务被销毁」告警 | `[A8]` |

**风格示范**：

```python
"""worker 模块：在事件循环里安全地调用同步依赖。

为什么用 to_thread：下游 SDK 只有同步版本，直接调用会阻塞整个循环。
"""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")


async def call_sync(fn: Callable[[], T], *, timeout: float = 30.0) -> T:
    """把同步调用隔离到线程池，并加超时。"""
    return await asyncio.wait_for(asyncio.to_thread(fn), timeout=timeout)
```

**边界**：

- 事件循环不负责「让代码变快」，它只负责「让等待重叠」。
- 单线程意味着任何一处阻塞都是全局故障，必须靠 review + debug 模式兜住。
- 定时器精度受操作系统影响（Windows 约 15ms 量级），不要用 `sleep(0.001)` 做精确控制。

## 8. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[A1]` | python.org | https://docs.python.org/3.12/library/asyncio-eventloop.html | `AbstractEventLoop` API、`run_forever`、`call_soon`/`call_later`/`call_soon_threadsafe`、`run_in_executor`、`get_event_loop` |
| `[A2]` | python.org | https://docs.python.org/3.12/library/asyncio.html | `asyncio` 顶层 API、`to_thread`、阻塞隔离 |
| `[A3]` | python.org | https://docs.python.org/3.12/library/selectors.html | selector 与 I/O 多路复用、循环等待事件 |
| `[A4]` | PEP 官方 | https://peps.python.org/pep-0008/ | 命名、注释写「为什么」 |
| `[A5]` | PEP 官方 | https://peps.python.org/pep-0492/ | 协程与 `await` 的引入 |
| `[A6]` | python.org | https://docs.python.org/3.12/library/asyncio-dev.html | debug 模式、慢回调、未 await 检测 |
| `[A7]` | python.org | https://docs.python.org/3.12/library/asyncio-platforms.html | Windows Proactor / Unix Selector 差异 |
| `[A8]` | python.org | https://docs.python.org/3.12/library/asyncio-runner.html | `asyncio.run` 语义与清理顺序 |

> **核对状态**：`[A4]` 与本章 `README.md` 已核对来源一致；其余按 `docs.python.org/3.12` 官方结构整理，**本次未逐页直连复核**。文中「实测」为本机 Python 3.12.8 / Windows 运行结果；耗时数据随机器波动。

## 9. 毕业自查清单

**能说清（概念层）**：

- [ ] 事件循环在什么时刻切换任务
- [ ] 为什么 `time.sleep` 会卡住整个循环
- [ ] 为什么 `time.sleep(0)` 不让出、`await asyncio.sleep(0)` 让出
- [ ] 异步与并行的区别
- [ ] 异步与多线程的七维差异
- [ ] `asyncio.run` 的四个步骤
- [ ] `get_event_loop` 在 3.12 为什么不能随便用
- [ ] Windows 默认是哪种循环实现
- [ ] `call_soon` / `call_later` / `call_soon_threadsafe` 的区别

**能写出（代码层）**：

- [ ] 一个 `asyncio.run(main())` 入口
- [ ] 两个协程并发（`gather`）并对比串行耗时
- [ ] `call_soon` + `await` 观察执行顺序
- [ ] `to_thread` 隔离同步 I/O
- [ ] debug 模式 + `slow_callback_duration` 定位阻塞
- [ ] 跨线程 `call_soon_threadsafe`
- [ ] 手动 `new_event_loop` + `run_until_complete` + `close`

**能判断（避坑层）**：

- [ ] 看到协程里 `requests.get` 能指出阻塞
- [ ] 看到嵌套 `asyncio.run` 能指出报错原因
- [ ] 看到 `get_event_loop()` 能指出 3.12 行为变化
- [ ] 看到回调里抛异常能指出不会冒泡
- [ ] 看到 `_run_once` 能指出是私有 API
- [ ] 看到 CPU 密集任务塞进协程能指出该用进程

**能跑通（验收层）**：

- [ ] 运行 `examples/loop_demo.py` 并解释三行顺序
- [ ] 把第 5 节示例存成文件运行，输出与文档一致
- [ ] 用 debug 模式复现一次慢回调告警
- [ ] 用 `to_thread` 把阻塞调用挪出循环

## 10. 下一章衔接

第 25 章 `Future类`：循环调度的是「还没完成的结果」——Future 就是这个占位符。下一章讲它的三种完成状态、`result()` 为什么才会抛异常、以及它和 `Task` 的继承关系。

本章留下的伏笔：

1. `await` 的对象可以是协程、`Task`、`Future`，第 25 章解释后者。
2. `call_soon` 与 `add_done_callback` 是同一套回调机制，第 25 章会用到。
3. 循环内阻塞的隔离方案（`to_thread`）与第 28 章的线程池是同一件事。