# 26 协程 Coroutine · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把截图里的「回调之痛、协程函数、协程 VS 线程、驱动协程对象、Task、`asyncio.run`、深度总结」逐条展开，并补上协程对象内部状态、生成器协议、重复 `await`、任务引用、awaitable 三类，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测） |
| 前置 | 第 17、24–25 章（生成器、事件循环、Future） |
| 覆盖范围 | 回调模式的痛点、`async def`/`await` 语义、协程对象状态、生成器协议、协程 vs 线程、三种驱动方式、`create_task`、`asyncio.run`、awaitable 三类、常见误解 |
| 明确不覆盖 | `gather`/`TaskGroup` 细节（27 章）、`async for`/`async with`（27 章）、`uvloop` |
| 学完验收 | 能解释「调用 `async def` 不执行函数体」、能说出 awaitable 三类、能区分协程对象与 Task（见第 12 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Cn]` `` 指向第 11 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果。

**推荐顺序**：

```text
1 回调之痛（第 1 节）        → 为什么需要协程
2 协程函数（第 2 节）        → async def 语义
3 协程 VS 线程（第 3 节）    → 模型差异
4 驱动协程对象（第 4 节）    → send/run/create_task
5 Task（第 5 节）            → 被调度的协程
6 asyncio.run（第 6 节）     → 唯一入口
7 深度总结（第 7 节）        → 三类 awaitable
8 综合示例（第 8 节）
9 注意事项（第 9 节）        → 40 条错误对照
```

**与 README 的分工**：README 给结论与边界，本文件负责语义、内部状态与实测证据。冲突时以本文件为准。

## 1. 回调之痛

### 1.1 回调写法

```python
async_delay(2).add_done_callback(lambda _: print("2 秒后执行"))
```

| 问题 | 表现 | 依据 |
| --- | --- | --- |
| 金字塔嵌套 | 三步依赖就三层缩进 | `[C1]` |
| 错误处理分散 | 每层各自处理异常 | `[C1]` |
| 组合困难 | 想「等两个都完成」很别扭 | `[C1]` |
| 可读性差 | 执行顺序不直观 | `[C1]` |

### 1.2 三层嵌套长什么样

```python
# 回调风格（伪代码）
fetch_user(uid, lambda user: (
    fetch_orders(user.id, lambda orders: (
        fetch_detail(orders[0], lambda detail: print(detail))
    ))
))
```

```python
# 协程风格
async def show(uid):
    user = await fetch_user(uid)
    orders = await fetch_orders(user.id)
    detail = await fetch_detail(orders[0])
    print(detail)
```

| 对比 | 回调 | 协程 | 依据 |
| --- | --- | --- | --- |
| 控制流 | 倒置（回调里继续） | 顺序（自上而下） | `[C2]` |
| 异常 | 每层 try | 一个 try 包住 | `[C2]` |
| 局部变量 | 逐层闭包传递 | 直接可见 | `[C2]` |
| 调试 | 栈断成多段 | 接近同步栈 | `[C9]` |

### 1.3 协程解决了什么

| 能力 | 机制 | 依据 |
| --- | --- | --- |
| 顺序书写 | `await` 挂起后恢复 | `[C2]` |
| 异常冒泡 | 异常沿 `await` 链上抛 | `[C2]` |
| 局部变量存活 | 协程帧保存状态 | `[C1]` |
| 可组合 | 一个协程可 `await` 另一个 | `[C2]` |

> 注意：协程不是「更快的回调」，而是「把异步代码写成同步的样子」。它改变的是**表达方式**，底层仍然是回调与事件循环在驱动。`[C9]`

## 2. 协程函数

### 2.1 定义与调用

```python
async def work(name):
    events.append("run " + name)
    await asyncio.sleep(0.01)
    return name + ":ok"

coro = work("x")
print(type(coro).__name__, events)     # 调用后 events 仍为空
```

实测：

```text
CORO_TYPE coroutine True []
EVENTS_AFTER ['run x']
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `async def` 定义协程函数 | 不是普通函数 | `[C2]` |
| 调用只创建协程对象 | **函数体一行都没执行** | `[C2]` |
| 必须 `await` 或被调度 | 才会真正运行 | `[C1]` |
| 类型是 `coroutine` | `inspect.iscoroutine` 为 `True` | `[C5]` |

> 注意：这是本章第一号误解——**调用 `async def` 得到的是「待执行的计划」，不是结果**。忘了 `await` 的代码不会报错，只会「什么都没发生」，外加一条 `RuntimeWarning`。`[C2]`

### 2.2 协程对象的状态

```python
coro = work("x")
print(coro.cr_running, coro.cr_suspended, coro.cr_frame is not None)
```

实测：

```text
CORO_STATE False False True
```

| 属性 | 含义 | 依据 |
| --- | --- | --- |
| `cr_running` | 是否正在执行 | `[C5]` |
| `cr_suspended` | 是否已挂起（await 中） | `[C5]` |
| `cr_frame` | 协程帧；未开始/结束后为 `None` | `[C5]` |
| `cr_code` | 对应的 code 对象 | `[C5]` |
| `cr_await` | 当前正在等待的对象 | `[C5]` |
| `cr_origin` | 创建位置（若启用追踪） | `[C5]` |

实测帧生命周期：

```text
MANUAL_HAS_FRAME True      # 创建后就有帧
MANUAL_DRIVE value         # 手动驱动后结束
FRAME_AFTER None           # 结束后帧被释放
```

### 2.3 `await` 的语义

```python
async def outer():
    result = await inner()
    return result
```

| 行为 | 说明 | 依据 |
| --- | --- | --- |
| 挂起当前协程 | 保存帧，交还控制权 | `[C3]` |
| 等待 awaitable 完成 | 完成后恢复 | `[C3]` |
| 只能出现在 `async def` 内 | 否则语法错误 | `[C3]` |
| 只能 `await` awaitable | 否则 `TypeError` | `[C3]` |

实测错误：

```python
await 42
```

```text
AWAIT_INT_ERR object int can't be used in 'await' expression
```

### 2.4 只能 `await` 一次

```python
once = work("once")
await once
await once          # 第二次
```

```text
REUSE_ERR cannot reuse already awaited coroutine
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 协程对象是一次性的 | 运行结束即耗尽 | `[C1]` |
| 重复 `await` 报 `RuntimeError` | 实测 | `[C1]` |
| `close()` 后再 `await` 也报同样的错 | 实测 `CLOSED_AWAIT` | `[C1]` |
| `Task` 可以重复 `await` | 结果是缓存值（实测两次返回同一结果） | `[C1]` |

> 注意：「协程只能 await 一次，Task 可以多次 await」——这是协程对象与 Task 最实用的区别之一。需要复用结果时，先 `create_task`。`[C1]`

### 2.5 未 `await` 的警告

```python
work("never-awaited")
gc.collect()
```

```text
NEVER_AWAITED ["coroutine 'work' was never awaited"]
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 未 await 的协程被 GC 时告警 | `RuntimeWarning` | `[C1]` |
| 告警只在 GC 时出现 | 可能延迟、可能淹没 | `[C1]` |
| debug 模式带完整创建栈 | 定位更快（实测） | `[C6]` |

```
RuntimeWarning: coroutine 'never' was never awaited
Coroutine created at (most recent call last)
  File "...", line 272, in unawaited_detected
    never()
```

> 注意：这条警告在生产日志里经常被过滤掉，导致「代码写了但没执行」这种问题查很久。`asyncio.run(..., debug=True)` 会给出创建位置，排查必备。`[C6]`

## 3. 协程 VS 线程

### 3.1 六个维度

| 维度 | 协程 | 线程 | 依据 |
| --- | --- | --- | --- |
| 调度者 | 事件循环（用户态） | 操作系统 | `[C1]` |
| 切换时机 | 代码 `await` 处 | 任意指令（抢占） | `[C1]` |
| 切换成本 | 函数调用级 | 内核态切换 | 28 章 |
| 内存 | 每协程几 KB | 每线程数 MB 栈 | 28 章 |
| 并行 | ❌ 单线程 | ❌（GIL） | 28 章 |
| 数据竞争 | `await` 前后仍可能 | 需锁 | `[C1]` |

### 3.2 单线程不等于无竞态

```python
async def race():
    counter = 0

    async def increase():
        nonlocal counter
        value = counter
        await asyncio.sleep(0)
        counter = value + 1

    await asyncio.gather(*(increase() for _ in range(5)))
    print(counter)      # 1，不是 5
```

实测：

```text
RACE_COUNTER 1
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `await` 是「让出点」 | 共享状态可能被改 | `[C1]` |
| 没有 `await` 的连续代码是原子的 | 循环体中间不会切 | `[C1]` |
| 需要保护时用 `asyncio.Lock` | 27 章 | `[C7]` |

> 注意：「单线程所以没竞态」是错的。只要读-改-写之间夹了 `await`，就有竞态——只是发生窗口比线程小得多。`[C1]`

### 3.3 协作式的代价与好处

| 代价 | 说明 | 依据 |
| --- | --- | --- |
| 一处阻塞全盘停 | 没有抢占来救场 | `[C1]` |
| 必须全链路 async | 混入同步库要隔离 | `[C6]` |
| 调试需理解调度 | 栈不再是单一直线 | `[C9]` |

| 好处 | 说明 | 依据 |
| --- | --- | --- |
| 高并发低成本 | 万级任务可行 | `[C1]` |
| 切换可控 | 无隐式抢占 | `[C1]` |
| 顺序可读 | 代码接近同步写法 | `[C2]` |

## 4. 驱动协程对象

### 4.1 底层：协程就是生成器协议

```python
coro = simple()          # async def simple(): return "value"
try:
    coro.send(None)
except StopIteration as stop:
    print(stop.value)    # value
```

```text
MANUAL_DRIVE value
```

带 `await` 的协程会先 `yield` 出一个值：

```python
second = with_sleep()    # await asyncio.sleep(0)
yielded = second.send(None)
print(repr(yielded))     # None
second.send(None)        # 抛 StopIteration("done")
```

```text
YIELDED None
SECOND_SEND done
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 协程复用生成器的 `send`/`throw`/`close` | 同一套协议 | `[C2]` |
| `await x` 编译成 `yield from x` 的等价物 | 挂起/恢复机制 | `[C7]` |
| 返回值通过 `StopIteration.value` 传出 | 实测 `value` | `[C2]` |

> 注意：手动 `send` 只能驱动「不等待真实 I/O」的协程。带 `await` 的协程会 `yield` 出 Future，必须由事件循环在适当时机 `send` 回去。**不要手写驱动器**。`[C1]`

### 4.2 三种驱动方式

| 方式 | 用法 | 场景 | 依据 |
| --- | --- | --- | --- |
| `asyncio.run(coro)` | 顶层入口 | 应用主函数 | `[C1]` |
| `loop.run_until_complete(coro)` | 已有循环 | 测试/嵌入 | `[C1]` |
| `asyncio.create_task(coro)` | 循环内并发 | 多任务 | `[C1]` |
| 手动 `send` | 教学/框架 | 不推荐 | `[C2]` |

```python
# 顶层
asyncio.run(main())

# 循环内并发
task = asyncio.create_task(work("a"))
```

### 4.3 旧式写法（了解即可）

```python
@types.coroutine
def legacy():
    yield from asyncio.sleep(0)
    return "legacy-ok"

async def use():
    return await legacy()
```

```text
LEGACY_AWAIT legacy-ok
```

| 写法 | 状态 | 依据 |
| --- | --- | --- |
| `@asyncio.coroutine` + `yield from` | 已移除（3.11） | `[C2]` |
| `@types.coroutine` 包装生成器 | 仍可用，框架内部用 | `[C2]` |
| `async def` + `await` | 唯一推荐 | `[C2]` |

## 5. Task

### 5.1 `create_task` 做了什么

```python
async def main():
    started = time.perf_counter()
    first = asyncio.create_task(work("t1"))
    second = asyncio.create_task(work("t2"))
    print(first.done())
    results = await asyncio.gather(first, second)
```

实测（10ms 版）：

```text
TASK_NEW False True
CREATE_TASK ['t1:ok', 't2:ok'] 20
```

10ms 的间隔在 Windows 上受定时器分辨率影响（约 15.6ms），数字不干净。用 100ms 重测对比串行与并发：

```python
t0 = time.perf_counter()
await work("a", 0.1)
await work("b", 0.1)
print("SERIAL_100MS", ...)

t0 = time.perf_counter()
first = asyncio.create_task(work("a", 0.1))
second = asyncio.create_task(work("b", 0.1))
print("TASK_CREATED", first.done(), second.done())
print(await asyncio.gather(first, second))
print("CONCURRENT_100MS", ...)
```

```text
SERIAL_100MS 225
TASK_CREATED False False
['a', 'b']
CONCURRENT_100MS 108
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `create_task` 立即把协程包成 Task 并排队 | 不等下一个 `await` | `[C1]` |
| 返回时任务还没跑 | `done()` 为 `False`（实测） | `[C1]` |
| 串行两个 100ms ≈ 225ms | 顺序等待 | `[C1]` |
| 并发两个 100ms ≈ 108ms | 重叠等待 | `[C1]` |

> 注意：判断并发是否生效，用**足够大的间隔**（≥100ms）测，避免被系统定时器分辨率干扰。10ms 级别的测量在 Windows 上不可靠。`[C1]`

### 5.2 Task 常用属性与方法

| 成员 | 作用 | 依据 |
| --- | --- | --- |
| `done()` | 是否结束 | `[C1]` |
| `cancelled()` | 是否被取消 | `[C1]` |
| `cancel()` | 请求取消 | `[C1]` |
| `result()` | 取结果（已完成时） | `[C1]` |
| `exception()` | 取异常 | `[C1]` |
| `get_name()` / `set_name()` | 任务名 | `[C1]` |
| `add_done_callback()` | 完成回调 | `[C1]` |
| `get_coro()` | 取出协程对象 | `[C1]` |
| `uncancel()` | 减少取消计数（3.11+） | `[C1]` |
| `cancelling()` | 取消请求计数（3.11+） | `[C1]` |

### 5.3 必须保留引用

```python
background = set()

job = asyncio.create_task(tick())
background.add(job)
job.add_done_callback(background.discard)
```

```text
TASK_REF_DISCARDED 0
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 事件循环只持弱引用 | 任务可能被 GC | `[C1]` |
| 官方明确要求保留引用 | 文档有专门章节 | `[C1]` |
| 用集合保存 + `discard` 回调 | 常见写法 | `[C1]` |

> 注意：这是官方文档里的明确警告——「保存任务引用，避免任务中途消失」。长时间运行的「后台任务」如果没人引用，可能在某个 GC 时机被回收，表现为「任务莫名其妙没跑完」。`[C1]`

### 5.4 Task 可重复 `await`

```python
job = asyncio.create_task(asyncio.sleep(0.01, result=1))
print(await job)
print(await job)
```

```text
TASK_AWAIT_AGAIN 1
TASK_AWAIT_AGAIN 1
```

| 对比 | 协程对象 | Task | 依据 |
| --- | --- | --- | --- |
| 第一次 `await` | 执行 | 执行 | `[C1]` |
| 第二次 `await` | `RuntimeError` | 返回缓存结果 | `[C1]` |
| 适用 | 一次性 | 需要复用结果 | `[C1]` |

### 5.5 嵌套 `await` 链

```python
async def top():
    return await mid() + 1
```

```text
AWAIT_CHAIN 3
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 协程可以多层嵌套 | 每层挂起都会串起来 | `[C2]` |
| 异常沿链上抛 | 不需要逐层捕获 | `[C2]` |
| 取消也沿链传播 | `CancelledError` 向上冒 | `[C1]` |

## 6. `asyncio.run`

### 6.1 职责

| 步骤 | 说明 | 依据 |
| --- | --- | --- |
| 建循环 | `new_event_loop` | `[C1]` |
| 设为当前 | `set_event_loop` | `[C1]` |
| 包成 Task 跑 | `run_until_complete` | `[C1]` |
| 清理 | 取消剩余任务、关闭生成器与 executor、关循环 | `[C1]` |
| 返回 | 协程的 `return` 值 | `[C1]` |

### 6.2 只能是入口

| 场景 | 结果 | 依据 |
| --- | --- | --- |
| 顶层调用 | ✅ | `[C1]` |
| 协程内再调 | `RuntimeError` | `[C1]` |
| Jupyter 里调 | 同样报错（已有运行循环） | `[C1]` |

实测：

```text
NESTED_RUN_ERR asyncio.run() cannot be called from a running event loop
```

> 注意：在 async 代码里想「跑另一个协程」，直接 `await` 或 `create_task`，不要 `run`。在同步代码里想跑协程，用 `asyncio.run` 或 `asyncio.run_coroutine_threadsafe`。`[C1]`

### 6.3 嵌套场景的正确写法

| 场景 | 错误 | 正确 | 依据 |
| --- | --- | --- | --- |
| 协程内调协程 | `asyncio.run(other())` | `await other()` | `[C1]` |
| 同步函数里跑协程 | 无法直接 `await` | `asyncio.run(coro)` | `[C1]` |
| 线程里跑协程 | `asyncio.run` 会新建循环 | `run_coroutine_threadsafe` | `[C1]` |
| Notebook | `asyncio.run(main())` | `await main()` | `[C1]` |

## 7. 深度总结

### 7.1 三类 awaitable

```python
print(asyncio.isfuture(fut), asyncio.isfuture(task),
      inspect.isawaitable(fut), inspect.isawaitable(task), inspect.isawaitable(coro))
```

```text
AWAITABLE_KINDS True True True True True
```

| 类型 | 是否 awaitable | 谁产生 | 依据 |
| --- | --- | --- | --- |
| 协程对象 | ✅ | 调用 `async def` | `[C2]` |
| `Task` | ✅ | `create_task` / `ensure_future` | `[C1]` |
| `Future` | ✅ | `create_future` / 库 | `[C1]` |
| 普通值 | ❌ | —— | `[C3]` |
| 实现了 `__await__` 的对象 | ✅ | 自定义 awaitable | `[C3]` |

### 7.2 协程与生成器

```python
gen = generator()          # def generator(): yield 1
coro = coroutine()         # async def coroutine(): return 1
print(inspect.isgenerator(gen), inspect.iscoroutine(coro),
      hasattr(gen, "gi_frame"), hasattr(coro, "cr_frame"),
      inspect.isawaitable(coro), inspect.isgenerator(coro))
```

```text
GEN_VS_CORO True True True True True False
```

| 维度 | 生成器 | 协程 | 依据 |
| --- | --- | --- | --- |
| 关键字 | `yield` | `await` | `[C2]` |
| 用途 | 产出序列 | 等待异步结果 | `[C2]` |
| `for` 消费 | ✅ | ❌ | `[C2]` |
| `await` 消费 | ❌ | ✅ | `[C2]` |
| 帧属性 | `gi_frame` | `cr_frame` | `[C5]` |
| 底层 | 同一套 `send`/`throw`/`close` | 同上 | `[C7]` |

> 注意：`inspect.isgenerator(coro)` 为 `False`（实测），所以「协程就是生成器」只在**协议层面**成立，类型层面它们是两个不同对象。`[C5]`

### 7.3 十个常见误解

| 误解 | 事实 | 依据 |
| --- | --- | --- |
| 调用 `async def` 就执行了 | 只创建协程对象 | `[C2]` |
| `async def` 会自动并行 | 需 `gather`/`create_task` | `[C1]` |
| `await` 会切给「指定任务」 | 只交还循环，由循环决定 | `[C1]` |
| 协程可以多次 `await` | 只能一次 | `[C1]` |
| 单线程没有竞态 | `await` 处仍有 | `[C1]` |
| 协程提高 CPU 性能 | 只重叠等待 | `[C1]` |
| `create_task` 会立即执行完 | 只是排队 | `[C1]` |
| `asyncio.run` 可以嵌套 | 报错 | `[C1]` |
| 忘记 `await` 会报错 | 只给 RuntimeWarning | `[C1]` |
| Task 不需要引用 | 可能被 GC | `[C1]` |

## 8. 综合示例：协程惰性与 Task 并发

```python
"""第 26 章综合示例：协程惰性执行与 Task 并发。"""

import asyncio
import time


async def tool(name: str, delay: float) -> str:
    await asyncio.sleep(delay)
    return name + ":ok"


async def main() -> None:
    idle = tool("idle", 0.01)
    print("NOT_STARTED", idle.cr_running, idle.cr_frame is not None)
    print("IDLE_RESULT", await idle)

    started = time.perf_counter()
    tasks = [asyncio.create_task(tool(name, 0.03)) for name in ("a", "b", "c")]
    print("TASKS", await asyncio.gather(*tasks), int((time.perf_counter() - started) * 1000))


asyncio.run(main())
```

本机实测输出：

```text
NOT_STARTED False True
IDLE_RESULT idle:ok
TASKS ['a:ok', 'b:ok', 'c:ok'] 30
```

**逐段说明**：

| 代码 | 用到的机制 | 依据 |
| --- | --- | --- |
| `tool("idle", 0.01)` | 只创建协程对象 | `[C2]` |
| `cr_running False` | 未在运行 | `[C5]` |
| `cr_frame is not None` | 帧已创建但未执行 | `[C5]` |
| `await idle` | 此刻才执行 | `[C2]` |
| `create_task` ×3 | 立刻排队，三任务重叠 | `[C1]` |
| 总耗时 ≈ 30ms | 三个 30ms 任务并行 | `[C1]` |

> 注意：`TASKS` 一行耗时约 30ms 说明三个 30ms 任务确实重叠了（如果是串行会是 90ms）。这是判断「并发是否生效」的正确方式——**看总耗时是否接近单个任务，而不是看总耗时是否变小到 1/3**。`[C1]`

## 9. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 调用 `async def` 却没 `await` | 什么都没发生 + RuntimeWarning | `await` 或 `create_task` | `[C2]` |
| 在同步函数里 `await` | `SyntaxError` | 包成 `async def` 或 `asyncio.run` | `[C3]` |
| 重复 `await` 协程对象 | `RuntimeError: cannot reuse already awaited coroutine` | 先 `create_task` | `[C1]` |
| `await` 一个数字 | `TypeError: object int can't be used in 'await' expression` | 只 await awaitable | `[C3]` |
| 以为 `create_task` 同步执行 | 任务还没跑 | 用 `await` 等或 `gather` | `[C1]` |
| `create_task` 后不保留引用 | 任务可能被 GC | 集合持有 | `[C1]` |
| 协程里 `time.sleep` | 整个循环卡住 | `await asyncio.sleep` | `[C1]` |
| 协程里同步 I/O | 卡住 | `to_thread` | `[C6]` |
| 用 `asyncio.run` 当普通函数调用 | 每个调用新建循环 | 一次入口 | `[C1]` |
| 嵌套 `asyncio.run` | `RuntimeError` | `await` | `[C1]` |
| 在 Jupyter 里 `asyncio.run` | 报错 | `await main()` | `[C1]` |
| 以为单线程无竞态 | 计数丢失（实测 1/5） | `asyncio.Lock` | `[C7]` |
| 用 `while True` 中间无 `await` | 循环饿死 | 定期 `await` | `[C1]` |
| 用 `yield` 写协程 | 那是生成器 | `async def` + `await` | `[C2]` |
| 用 `@asyncio.coroutine` | 3.11 已移除 | `async def` | `[C2]` |
| 手动 `send` 驱动带 I/O 的协程 | 卡住/状态错乱 | 交给循环 | `[C2]` |
| 把协程对象存进列表后忘了跑 | 从未执行 | `create_task` / `gather` | `[C1]` |
| 用 `asyncio.ensure_future` 到处包 | 语义模糊 | `create_task` | `[C1]` |
| `Task.result()` 在未完成时调 | `InvalidStateError` | 先 `await` | `[C1]` |
| 取消后不 `await` 任务 | 取消可能未生效 | `await` 捕获 `CancelledError` | `[C1]` |
| 裸 `except:` 包 `await` | 吞掉取消 | `except Exception` | 16 章 |
| 在 `finally` 里 `await` 长任务 | 取消被延迟 | 处理取消分支 | `[C1]` |
| 协程里用同步 `Lock` | 可能死锁 | `asyncio.Lock` | `[C7]` |
| 协程里用线程 `Event` | 阻塞循环 | `asyncio.Event` | `[C7]` |
| 协程里 `input()` | 阻塞 | 不要交互 | `[C1]` |
| 用协程做 CPU 密集 | 无加速 | 进程池 | 28 章 |
| 忽略 `RuntimeWarning: never awaited` | 功能缺失 | 开 debug 定位 | `[C6]` |
| 以为 `async def` 函数有独立线程 | 同一线程 | 理解单线程模型 | `[C1]` |
| 在 `__init__` 里跑协程 | 构造期无循环 | 显式 `await` 方法 | `[C1]` |
| 用 `get_event_loop` 在协程外取循环 | 3.12 报错 | `get_running_loop` | `[C1]` |
| 把 Task 传给多线程 | 非线程安全 | `run_coroutine_threadsafe` | `[C1]` |
| 用 `async with` 但资源非异步 | `TypeError` | 同步用 `with` | 27 章 |
| 用 `async for` 消费普通生成器 | `TypeError` | 普通 `for` | 27 章 |
| 协程里 `print` 大量输出 | 慢 | 用日志 | `[C4]` |
| 协程里做重计算不分段 | 饿死其他任务 | 分段 `await` | `[C1]` |
| 异常未捕获就结束 Task | 只进 `exception_handler` | `await` 或回调处理 | `[C1]` |
| 认为 `await` 是「等待固定时间」 | 是等待完成 | 用 `sleep` 计时 | `[C1]` |
| 用 `asyncio.sleep(0)` 做定时 | 只是让出一轮 | 用真实延迟 | `[C1]` |
| 任务异常被 `gather` 吞 | 需检查返回值 | `return_exceptions` 或 try | 27 章 |
| 用协程替代线程池处理阻塞库 | 仍阻塞 | `to_thread` | `[C6]` |

## 10. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 顶层一个 `asyncio.run` | 内部全 `await` | `[C1]` |
| 需要并发才 `create_task` | 顺序依赖直接 `await` | `[C1]` |
| 保存 Task 引用 | 官方要求 | `[C1]` |
| 需要复用结果用 Task | 协程只能 await 一次 | `[C1]` |
| 批量任务用 `gather`/`TaskGroup` | 别散落 | 27 章 |
| `await` 前后审慎对待共享状态 | 竞态窗口 | `[C1]` |
| 同步库一律 `to_thread` | 隔离阻塞 | `[C6]` |
| 打开 debug 排查未 await | 创建栈 | `[C6]` |
| 协程函数加 `-> T` 注解 | 可读性 | `[C4]` |
| 文档字符串写明并发语义 | 调用方须知 | `[C4]` |

**风格示范**：

```python
"""tools 模块：并发调用多个工具。

为什么用 create_task 而不是直接 await：三者互不依赖，需要重叠等待。
"""

from __future__ import annotations

import asyncio
import logging
from typing import Any

logger = logging.getLogger(__name__)


async def collect(names: list[str], call: Any, *, timeout: float = 10.0) -> list[Any]:
    """并发执行并返回与输入同序的结果。"""
    tasks = [asyncio.create_task(call(name)) for name in names]
    try:
        return await asyncio.wait_for(asyncio.gather(*tasks), timeout=timeout)
    except BaseException:
        for task in tasks:
            task.cancel()
        raise
```

**边界**：

- 协程不提供并行，只提供并发。
- 协程对象是一次性的，`Task` 是「已排队的协程 + 结果缓存」。
- 取消必须在 `await` 点才能生效，CPU 密集段无法中断。

## 11. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[C1]` | python.org | https://docs.python.org/3.12/library/asyncio-task.html | 协程与 Task、`create_task`、保留引用、重复 await、取消、`asyncio.run` |
| `[C2]` | PEP 官方 | https://peps.python.org/pep-0492/ | `async def`/`await` 语义、与生成器的关系 |
| `[C3]` | python.org | https://docs.python.org/3.12/reference/compound_stmts.html#coroutines | `await` 语法与表达式的限制 |
| `[C4]` | PEP 官方 | https://peps.python.org/pep-0008/ | 命名、docstring、注释写「为什么」 |
| `[C5]` | python.org | https://docs.python.org/3.12/library/inspect.html | `iscoroutine`、`cr_frame`/`gi_frame`、`iscoroutinefunction` |
| `[C6]` | python.org | https://docs.python.org/3.12/library/asyncio-dev.html | debug 模式、未 await 协程的创建栈、阻塞隔离 |
| `[C7]` | python.org | https://docs.python.org/3.12/library/asyncio-sync.html | `asyncio.Lock`/`Event` 等同步原语 |
| `[C8]` | PEP 官方 | https://peps.python.org/pep-0380/ | `yield from` 委托机制（协程实现基础） |
| `[C9]` | PEP 官方 | https://peps.python.org/pep-3156/ | asyncio 设计：协程、回调与循环 |

> **核对状态**：`[C4]` 与本章 `README.md` 已核对来源一致；其余按 `docs.python.org/3.12` 官方结构整理，**本次未逐页直连复核**。文中「实测」为本机 Python 3.12.8 运行结果。

## 12. 毕业自查清单

**能说清（概念层）**：

- [ ] 为什么调用 `async def` 不执行函数体
- [ ] 协程对象与 Task 的三个区别
- [ ] awaitable 三类
- [ ] 协程与生成器的关系（协议 vs 类型）
- [ ] 协程与线程的六个维度差异
- [ ] 单线程为什么仍可能竞态
- [ ] `create_task` 为什么必须保留引用
- [ ] `asyncio.run` 为什么不能嵌套

**能写出（代码层）**：

- [ ] 一个 `async def` + `await` 的完整示例
- [ ] `create_task` 并发 + `gather` 收集
- [ ] 任务引用集合 + `discard` 回调
- [ ] `asyncio.run(main())` 入口
- [ ] 用 `inspect` 判断协程/生成器
- [ ] debug 模式复现「never awaited」告警

**能判断（避坑层）**：

- [ ] 看到忘记 `await` 能指出问题
- [ ] 看到重复 `await` 能指出应先 `create_task`
- [ ] 看到 `create_task` 不保存引用能指出 GC 风险
- [ ] 看到单线程共享计数能指出竞态
- [ ] 看到嵌套 `asyncio.run` 能指出报错
- [ ] 看到 `@asyncio.coroutine` 能指出已移除

**能跑通（验收层）**：

- [ ] 运行 `examples/coroutine_demo.py` 并解释两行输出
- [ ] 把第 8 节示例存成文件运行，输出与文档一致
- [ ] 在 REPL 手动 `send` 驱动一个无 I/O 协程
- [ ] 复现一次 `RuntimeWarning: never awaited`

## 13. 下一章衔接

第 27 章 `异步编程`：协程能写了，接下来组装成真实能力——`gather`/`TaskGroup`、超时取消、异步生成器与异步上下文管理器、限流重试优雅关闭。

本章留下的伏笔：

1. `create_task` 的引用管理，在第 27 章会用 `TaskGroup` 自动化。
2. `await` 处的竞态，第 27 章用 `asyncio.Lock` 解决。
3. 未 await 的检测依赖 debug 模式，第 27 章会作为最佳实践展开。