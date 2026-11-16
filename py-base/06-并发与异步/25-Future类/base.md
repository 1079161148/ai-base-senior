# 25 Future 类 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把截图里的「Future 表达的异步任务、两种状态（未完成 / 已完成：正常完成、有错误、被取消）、操作与检查状态的代码」逐条展开，并补上回调机制、Task 关系、两套 Future 的区别与桥接，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测） |
| 前置 | 第 24 章（事件循环） |
| 覆盖范围 | Future 语义、三种完成状态、状态机、`done`/`cancelled`/`result`/`exception`/`cancel`/`add_done_callback`、异常可见性、Task 继承关系、`concurrent.futures.Future` 与 `asyncio.Future` 的区别、`wrap_future`、`as_completed` |
| 明确不覆盖 | 协程语法（26 章）、`gather`/`TaskGroup` 全量（27 章）、`concurrent.futures` 执行器调优（28 章） |
| 学完验收 | 能说出 Future 与 Task 的关系、能解释异常为何必须 `result()` 才抛出、能区分两套 Future（见第 12 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Fn]` `` 指向第 11 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果。

**推荐顺序**：

```text
1 为什么需要（第 1 节）      → 占位符模型
2 两种状态（第 2 节）        → 三种完成态
3 状态 API（第 3 节）        → 操作与检查
4 异常可见性（第 4 节）      → 为什么必须 result()
5 完成回调（第 5 节）        → add_done_callback
6 与 Task 的关系（第 6 节）  → 继承与区别
7 两套 Future（第 7 节）     → 混用是事故
8 综合示例（第 8 节）
9 注意事项（第 9 节）        → 41 条错误对照
```

**与 README 的分工**：README 给结论与边界，本文件负责状态机、API 语义与实测证据。冲突时以本文件为准。

## 1. 为什么需要 Future

### 1.1 问题的形状

```python
result = slow_operation()      # 同步：调用即等待
```

| 需求 | 同步调用做不到 | 依据 |
| --- | --- | --- |
| 先发起、稍后取 | 调用即阻塞 | `[F1]` |
| 查询「完成了没」 | 没有状态概念 | `[F1]` |
| 完成后自动通知 | 只能轮询 | `[F1]` |
| 传递「未来才有」的结果 | 需要占位对象 | `[F1]` |

### 1.2 Future 的定位

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| Future 是**结果的占位符** | 现在没有值，将来会有 | `[F1]` |
| 它本身不执行任何东西 | 只是状态容器 | `[F1]` |
| 谁负责填值 | 事件循环 / 线程池 / 你手动 `set_result` | `[F1]` |
| 可以被 `await` | `asyncio.Future` 是 awaitable | `[F1]` |

> 注意：Future 常被误解成「后台任务」。它不是——它不会自己跑。真正让任务跑起来的是 `Task`（协程被调度）或线程池（函数被执行）。`[F1]`

### 1.3 三种 awaitable 的分工

| 类型 | 是什么 | 谁驱动 | 依据 |
| --- | --- | --- | --- |
| 协程对象 | 可暂停的计算 | 被 `await` / 被 Task 包装 | 26 章 |
| `Task` | 已在循环中排队的协程 | 事件循环 | `[F3]` |
| `Future` | 结果占位符 | 由外部填值 | `[F1]` |

## 2. 两种状态

### 2.1 未完成（pending）

```python
fut = loop.create_future()
print(fut.done(), fut.cancelled())
```

实测：

```text
FUT_INIT Future False False
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 新建即 pending | `done()` 为 `False` | `[F1]` |
| 未取消 | `cancelled()` 为 `False` | `[F1]` |
| 取结果会报错 | 见 3.1 | `[F1]` |

### 2.2 已完成（done）的三种结局

```text
已完成
├── 正常完成：set_result(v)      → result() 返回 v
├── 有错误：  set_exception(e)   → result() 抛 e，exception() 返回 e
└── 被取消：  cancel()           → result() 抛 CancelledError
```

实测三种：

```python
success = loop.create_future(); success.set_result("done")
failure = loop.create_future(); failure.set_exception(ValueError("tool failed"))
cancelled = loop.create_future(); cancelled.cancel()
```

```text
STATE success ok done
STATE failure error ValueError
STATE cancelled cancelled
```

| 状态 | `done()` | `cancelled()` | `result()` | `exception()` | 依据 |
| --- | --- | --- | --- | --- | --- |
| pending | False | False | 抛 `InvalidStateError` | 抛 `InvalidStateError` | `[F1]` |
| 正常完成 | True | False | 返回值 | `None` | `[F1]` |
| 异常完成 | True | False | 抛出该异常 | 返回该异常 | `[F1]` |
| 已取消 | True | True | 抛 `CancelledError` | 抛 `CancelledError` | `[F1]` |

> 注意：`done()` 为 `True` **不代表成功**——取消和异常也算 done。要判断成功，必须检查 `cancelled()` 和 `exception()`。这是最容易写错的判定顺序。`[F1]`

### 2.3 状态机

```text
        ┌──────────┐
        │ pending  │
        └────┬─────┘
             │
   ┌─────────┼──────────┬───────────┐
   │         │          │           │
set_result  set_exception  cancel   （都没有 → 永远 pending）
   │         │          │
   ▼         ▼          ▼
┌────────┐ ┌─────────┐ ┌───────────┐
│ 正常   │ │ 异常    │ │ 已取消    │
└────────┘ └─────────┘ └───────────┘
   终态不可逆
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 只能从 pending 迁移一次 | 二次设置抛 `InvalidStateError` | `[F1]` |
| 终态不可回退 | 没有 `reset()` | `[F1]` |
| 已完成后 `cancel()` 返回 `False` | 不改变状态 | `[F1]` |

## 3. 状态检查与操作 API

### 3.1 `result()`：取结果

```python
try:
    fut.result()
except asyncio.InvalidStateError as error:
    print(type(error).__name__)
```

```text
RESULT_UNFINISHED InvalidStateError
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| **不阻塞** | 未完成直接抛 `InvalidStateError` | `[F1]` |
| 与线程池 Future 不同 | 那个会阻塞等待 | `[F2]` |
| 异常完成时抛出原异常 | 实测 `EXC_RERAISED bad` | `[F1]` |
| 已取消时抛 `CancelledError` | 实测 | `[F1]` |

> 注意：`asyncio.Future.result()` **不阻塞**、不等待——这是与 `concurrent.futures.Future.result()` 最大的行为差异。想在循环里等结果，只能 `await`。`[F1]` `[F2]`

### 3.2 `exception()`：取异常

| 场景 | 返回 | 依据 |
| --- | --- | --- |
| 正常完成 | `None` | `[F1]` |
| 异常完成 | 异常对象（不抛） | `[F1]` |
| pending | `InvalidStateError` | `[F1]` |
| 已取消 | 抛 `CancelledError` | `[F1]` |

```python
print(type(fut.exception()).__name__, fut.done())
```

```text
EXC_TYPE ValueError True
```

### 3.3 `done()` 与 `cancelled()`

| 调用 | 语义 | 依据 |
| --- | --- | --- |
| `done()` | 是否已有终态（成功/异常/取消） | `[F1]` |
| `cancelled()` | 是否被取消 | `[F1]` |
| `running()`（线程池） | 是否正在执行 | `[F2]` |

### 3.4 `cancel()`：取消

```python
print(fut.cancel(), fut.cancelled(), fut.done())
```

```text
CANCEL True True True
CANCEL_RESULT CancelledError True
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| pending 时取消成功 | 返回 `True` | `[F1]` |
| 已完成时返回 `False` | 无副作用 | `[F1]` |
| `CancelledError` 继承 `BaseException` | `isinstance(e, BaseException)` 为 `True`（实测） | `[F1]` |
| 裸 `except` 会吞掉取消 | 必须 `except Exception` 而非裸捕获 | 16 章 |

> 注意：`CancelledError` 继承 `BaseException` 是刻意设计——让 `except Exception` 不误吞取消信号。写 `except:` 或 `except BaseException:` 会把取消吞掉，导致任务无法退出。`[F1]`

### 3.5 `set_result` / `set_exception`

```python
fut.set_result(42)
print(fut.done(), fut.result())
try:
    fut.set_result(1)
except asyncio.InvalidStateError as error:
    print(type(error).__name__)
```

```text
FUT_AFTER_RESULT True 42
SET_TWICE InvalidStateError
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 只能设一次 | 二次抛 `InvalidStateError` | `[F1]` |
| 设置后回调立即排队 | 不是立刻执行 | `[F1]` |
| 业务代码通常不该手动设 | 交给 `Task` / 库 | `[F3]` |

### 3.6 `await` 一个 Future

```python
fut = loop.create_future()
loop.call_later(0.01, fut.set_result, "later-value")
print(await fut)
```

```text
AWAIT_FUTURE later-value
```

| 行为 | 说明 | 依据 |
| --- | --- | --- |
| pending 时 `await` 挂起当前协程 | 直到被设置 | `[F1]` |
| 完成后 `await` 立即返回结果 | 不再挂起 | `[F1]` |
| 异常完成时 `await` 抛出异常 | 等价 `result()` | `[F1]` |
| 已取消时 `await` 抛 `CancelledError` | 实测 | `[F1]` |

## 4. 异常为什么必须 `result()` 才抛出

### 4.1 异步错误的存放位置

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 任务错误不会「冒泡到调用栈」 | 调用栈早已返回 | `[F1]` |
| 错误被**存进** Future | 等谁来取 | `[F1]` |
| 不取 = 静默失败 | 日志里可能只有一条 GC 告警 | `[F5]` |

```python
fut = loop.create_future()
fut.set_exception(ValueError("bad"))
# 从未调用 result() / exception() → GC 时提示 Future exception was never retrieved
```

| 现象 | 说明 | 依据 |
| --- | --- | --- |
| `Future exception was never retrieved` | 未消费异常，垃圾回收时才提示 | `[F5]` |
| 进程不退出/无输出 | 错误完全丢失 | 第 01 章 |

### 4.2 三种消费方式

| 方式 | 代码 | 依据 |
| --- | --- | --- |
| `await` | `value = await fut` | `[F1]` |
| `result()` | `value = fut.result()`（需已知完成） | `[F1]` |
| `exception()` | `err = fut.exception()` | `[F1]` |
| 回调 | `fut.add_done_callback(handler)` 里取 | `[F1]` |

```python
# 反例：只管发起，不管结果
loop.create_task(risky())

# 正例：结果和异常都要落地
task = loop.create_task(risky())
task.add_done_callback(lambda t: logger.error("task failed", exc_info=t.exception()) if t.exception() else None)
```

> 注意：「不取结果」在原型阶段看不出问题，到了生产就是「任务失败了但监控全绿」。这是异步代码最常见的静默故障来源。`[F5]`

## 5. 完成回调

### 5.1 `add_done_callback`

```python
seen = []

def on_done(f):
    seen.append(f.result())

fut2.add_done_callback(on_done)
fut2.set_result(7)
await asyncio.sleep(0)      # 必须让出一轮，回调才会执行
print(seen)
```

```text
CALLBACK_SEEN [7]
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 回调在**完成时**由 `call_soon` 排队 | 不是同步立即执行 | `[F1]` |
| 已完成的 Future 也能加回调 | 下一轮即执行 | `[F1]` |
| 回调参数是 Future 本身 | 从中取 `result()` | `[F1]` |
| `remove_done_callback` 可移除 | 返回移除数量 | `[F1]` |

### 5.2 回调异常去哪了

```python
def boom(f):
    raise ValueError("callback-boom")

fut2.add_done_callback(boom)
```

实测 stderr：

```text
Exception in callback future_basics.<locals>.boom(<Future finished result=7>)
Traceback (most recent call last):
  ...
ValueError: callback-boom
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 回调异常**不会**传播到 `await` 处 | 已脱离调用栈 | `[F1]` |
| 走循环的 `exception_handler` | 默认打印到 stderr | `[F1]` |
| 业务代码感知不到 | 必须自己 try/except | `[F1]` |

> 注意：`add_done_callback` 里抛异常 = 静默失败（只在 stderr 留痕）。生产代码里的回调必须自带 `try/except` 并上报。`[F1]`

### 5.3 `set_exception_handler` 自定义

```python
loop.set_exception_handler(lambda loop, context: print("HANDLED", context["message"]))
```

| 参数 | 含义 | 依据 |
| --- | --- | --- |
| `loop` | 当前循环 | `[F1]` |
| `context["message"]` | 描述 | `[F1]` |
| `context["exception"]` | 异常对象 | `[F1]` |
| `context["future"]` / `["task"]` | 相关对象 | `[F1]` |

## 6. Future 与 Task

### 6.1 继承关系

```python
job = asyncio.create_task(asyncio.sleep(0.01))
print(isinstance(job, asyncio.Future), [b.__name__ for b in asyncio.Task.__mro__[:3]])
```

```text
TASK_MRO True ['Task', 'Future', 'object']
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `Task` 是 `Future` 的子类 | 所以 Task 也有 `done`/`result`/`cancel` | `[F3]` |
| Task 额外负责**驱动协程** | 循环调度的是 Task | `[F3]` |
| Future 不会自己推进 | 必须外部填值 | `[F1]` |

### 6.2 对比

| 维度 | `Future` | `Task` | 依据 |
| --- | --- | --- | --- |
| 是否执行代码 | ❌ | ✅ 驱动协程 | `[F1]` `[F3]` |
| 谁创建 | `loop.create_future()` / 库 | `asyncio.create_task(coro)` | `[F1]` `[F3]` |
| 状态迁移 | 手动 `set_result` | 协程结束自动 | `[F3]` |
| `cancel()` 语义 | 标记取消 | 向协程抛 `CancelledError` | `[F3]` |
| 能否重复 `await` | ✅ | ✅（实测两次都返回结果） | `[F3]` |

### 6.3 `gather` 返回什么

```python
group = asyncio.gather(asyncio.sleep(0.01), asyncio.sleep(0.01))
print(type(group).__name__, isinstance(group, asyncio.Future))
```

```text
GATHER_TYPE _GatheringFuture True
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `gather` 返回一个 Future 子类 | `_GatheringFuture`（内部类型） | `[F3]` |
| 也可被 `await` / `cancel` | 取消会传播到子任务 | `[F3]` |
| 不要依赖具体类名 | 内部实现，会变 | `[F3]` |

## 7. 两套 Future

### 7.1 `concurrent.futures.Future`

```python
with ThreadPoolExecutor(max_workers=2) as pool:
    cf = pool.submit(pow, 2, 10)
    print(cf.done(), cf.result())
```

```text
CF_DONE True 1024
```

| 方法 | 语义 | 依据 |
| --- | --- | --- |
| `result()` | **阻塞**等待 | `[F2]` |
| `result(timeout=)` | 超时抛 `TimeoutError` | `[F2]` |
| `exception()` | 取异常（阻塞） | `[F2]` |
| `cancel()` | 未开始可取消，运行中返回 `False` | `[F2]` |
| `running()` | 是否正在执行 | `[F2]` |
| `add_done_callback` | 完成回调 | `[F2]` |

实测取消与异常：

```text
CF_CANCEL_RUNNING True
CF_EXC ValueError
```

| 现象 | 说明 | 依据 |
| --- | --- | --- |
| `cancel()` 返回 `True` | 只是「取消请求被接受」 | `[F2]` |
| 任务可能仍在跑 | 取消不保证停止 | `[F2]` |
| `exception()` 返回异常对象 | 不抛 | `[F2]` |

> 注意：`cancel()` 返回 `True` 不代表任务没执行——它表示「还没开始，已标记取消」。如果 worker 已经取走任务，`cancel()` 会返回 `False`，而且**正在执行的代码不会被打断**。`[F2]`

### 7.2 `asyncio.Future`

| 方法 | 语义 | 依据 |
| --- | --- | --- |
| `result()` | 不阻塞，未完成抛 `InvalidStateError` | `[F1]` |
| `await` | 挂起直到完成 | `[F1]` |
| `cancel()` | 标记取消 | `[F1]` |
| 线程安全 | ❌ 只能在本循环线程操作 | `[F1]` |

### 7.3 对比表

| 维度 | `concurrent.futures.Future` | `asyncio.Future` | 依据 |
| --- | --- | --- | --- |
| 所属 | 线程/进程池 | 事件循环 | `[F2]` `[F1]` |
| `result()` | 阻塞 | 不阻塞 | `[F2]` `[F1]` |
| 能否 `await` | ❌ | ✅ | `[F1]` |
| 跨线程 | ✅ | ❌ | `[F1]` |
| 取消 | 尽力而为 | 通过 `CancelledError` | `[F1]` `[F2]` |

### 7.4 桥接：`asyncio.wrap_future`

```python
with ThreadPoolExecutor(max_workers=1) as pool:
    cf = pool.submit(pow, 2, 8)
    print(await asyncio.wrap_future(cf))
```

```text
WRAP_FUTURE 256
```

| API | 方向 | 依据 |
| --- | --- | --- |
| `asyncio.wrap_future(cf)` | 线程池 Future → asyncio Future | `[F1]` |
| `asyncio.run_coroutine_threadsafe(coro, loop)` | 线程 → 循环（返回 `concurrent.futures.Future`） | `[F1]` |
| `loop.run_in_executor(...)` | 循环 → 线程池（返回 asyncio Future） | `[F1]` |

> 注意：两套 Future **不能互相 `await`/`result()` 混用**。跨边界一律用 `wrap_future` / `run_coroutine_threadsafe` / `run_in_executor` 这三个官方桥。`[F1]`

## 8. 综合示例：Future 三种结局判定

```python
"""第 25 章综合示例：正确判定 Future 的三种结局。"""

import asyncio


async def main() -> None:
    loop = asyncio.get_running_loop()

    success = loop.create_future()
    success.set_result("done")

    failure = loop.create_future()
    failure.set_exception(ValueError("tool failed"))

    cancelled = loop.create_future()
    cancelled.cancel()

    for name, future in (("success", success), ("failure", failure), ("cancelled", cancelled)):
        if future.cancelled():
            print("STATE", name, "cancelled")
        elif future.exception() is not None:
            print("STATE", name, "error", type(future.exception()).__name__)
        else:
            print("STATE", name, "ok", future.result())


asyncio.run(main())
```

本机实测输出：

```text
STATE success ok done
STATE failure error ValueError
STATE cancelled cancelled
```

**判定顺序为什么重要**：

| 顺序 | 结果 | 依据 |
| --- | --- | --- |
| 先 `cancelled()` | 避免对已取消 Future 调 `exception()` | `[F1]` |
| 再 `exception()` | 区分异常完成 | `[F1]` |
| 最后 `result()` | 只剩正常完成 | `[F1]` |
| 反过来先 `result()` | 异常/取消会直接抛出 | `[F1]` |

> 注意：如果先 `result()`，遇到异常完成会抛异常、遇到取消会抛 `CancelledError`，后面的分支永远走不到。所以判定顺序必须是「取消 → 异常 → 正常」。`[F1]`

## 9. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 以为 `done()` 就是成功 | 异常/取消也是 `True` | 查 `exception()` / `cancelled()` | `[F1]` |
| 对 pending Future 调 `result()` | `InvalidStateError` | 先 `await` 或判 `done()` | `[F1]` |
| 对 pending Future 调 `exception()` | `InvalidStateError` | 同上 | `[F1]` |
| 用 `asyncio.Future.result()` 等结果 | 不是阻塞，直接报错 | `await` | `[F1]` |
| 在循环里用线程池 Future 的 `result()` | 阻塞整个循环 | `await wrap_future(cf)` | `[F1]` `[F2]` |
| 在线程里 `await` asyncio Future | 语法/运行错误 | `run_coroutine_threadsafe` | `[F1]` |
| 混用两套 Future 的方法 | 行为不一致 | 用桥接函数 | `[F1]` |
| 二次 `set_result` | `InvalidStateError` | 只设一次 | `[F1]` |
| 业务代码手动 `set_result` | 状态机混乱 | 交给 Task/库 | `[F3]` |
| 不消费 `result()` / `exception()` | 静默失败 | 必须落地 | `[F5]` |
| 只 `add_done_callback` 不看异常 | 错误进 stderr | 回调内取 `exception()` | `[F1]` |
| 回调里抛异常 | 不冒泡，只打日志 | 回调内 try/except | `[F1]` |
| 裸 `except:` 捕获 `CancelledError` | 任务无法取消 | `except Exception` | 16 章 |
| 以为 `cancel()` 会立即停 | 取消在 `await` 点生效 | 接受协作式取消 | `[F3]` |
| 以为 `cf.cancel()` 返回 True 就没执行 | 可能已在跑 | 用 `running()` 判 | `[F2]` |
| 已完成后 `cancel()` 期待成功 | 返回 `False` | 判 `done()` | `[F1]` |
| 用 `Future` 当后台任务 | 永远不会执行 | `create_task` | `[F3]` |
| `await` 未完成的 Future 无限等待 | 挂住 | 加 `wait_for` / `timeout` | `[F1]` |
| 忘记给等待加超时 | 生产卡死 | 超时 + 取消 | 27 章 |
| 在 `finally` 里 `await` 取消中的 Future | 又抛 `CancelledError` | 小心处理 | `[F3]` |
| 依赖 `_GatheringFuture` 类型名 | 内部实现 | 只当 `Future` 用 | `[F3]` |
| 用 `asyncio.isfuture` 判线程池 Future | `False` | 判 `concurrent.futures.Future` | `[F1]` |
| 把 Future 传给多线程共享 | 非线程安全 | 只在本循环线程用 | `[F1]` |
| 在 `__del__` 里设结果 | 时机不可控 | 显式完成 | `[F1]` |
| 用 Future 做「事件」 | 语义错 | 用 `asyncio.Event` | 27 章 |
| 多次 `await` 同一个协程对象 | `RuntimeError` | 用 Task（可重复 await） | 26 章 |
| 多次 `await` 同一个 Task | 合法（实测返回同一结果） | 可复用 | `[F3]` |
| 异常被包装成 `CancelledError` 后误判 | 日志丢失原因 | 区分取消与失败 | `[F1]` |
| 用 `exception()` 后不记日志 | 错误不可见 | 记录 traceback | `[F5]` |
| 认为 `Future` 有返回值类型检查 | 运行时不校验 | 类型标注 + 校验 | 20 章 |
| 用 `set_exception(None)` | `TypeError` | 传异常实例 | `[F1]` |
| 用 `set_result` 设异常 | 类型混乱 | `set_exception` | `[F1]` |
| `add_done_callback` 里做重活 | 阻塞循环 | 转成 Task | `[F1]` |
| 忽略 `Future exception was never retrieved` | 错误丢失 | 消费结果 | `[F5]` |
| 循环关闭后操作 Future | `RuntimeError` | 生命周期内完成 | `[F1]` |
| 在子线程里 `add_done_callback` | 非线程安全 | `call_soon_threadsafe` | `[F1]` |
| 用 `as_completed` 期待输入顺序 | 是完成顺序 | 要保序用 `gather` | `[F2]` |
| `as_completed` 后不取结果 | 异常丢失 | 逐个 `result()` | `[F2]` |
| 线程池 `max_workers` 过小 | 任务排队超时 | 按 I/O 并发设 | 28 章 |
| 进程池 Future 传不可 pickle 结果 | `PicklingError` | 返回可序列化数据 | 28 章 |
| 以为 Future 能跨进程 | 不可能 | 用 IPC | 28 章 |

## 10. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 业务代码只 `await`，少碰 `set_result` | 状态由 Task 管 | `[F3]` |
| 每个任务都消费结果 | 否则静默失败 | `[F5]` |
| 判定顺序：取消 → 异常 → 正常 | 实测验证 | `[F1]` |
| 等待必带超时 | 防卡死 | 27 章 |
| 跨边界用官方桥接 | `wrap_future` 等 | `[F1]` |
| 回调内自带 try/except | 不冒泡 | `[F1]` |
| 用 `add_done_callback` 只做轻量通知 | 重活转 Task | `[F1]` |
| 用 `gather`/`TaskGroup` 管批量 | 别手工散落 | 27 章 |
| 日志带任务标识 | 便于排查 | `[F4]` |
| 不要把 Future 当事件总线 | 用 `Event`/`Queue` | 27 章 |

**风格示范**：

```python
"""tasks 模块：安全地收集并发结果。

为什么判定顺序是 取消 → 异常 → 结果：先取 result() 会在失败分支抛异常。
"""

from __future__ import annotations

import asyncio
import logging

logger = logging.getLogger(__name__)


def describe(future: asyncio.Future) -> str:
    """把 Future 的终态转成一行可读描述。"""
    if not future.done():
        return "pending"
    if future.cancelled():
        return "cancelled"
    error = future.exception()
    if error is not None:
        logger.error("future failed", exc_info=error)
        return f"error:{type(error).__name__}"
    return f"ok:{future.result()}"
```

**边界**：

- Future 只是状态容器，不要指望它执行逻辑。
- `asyncio.Future` 与 `concurrent.futures.Future` 的方法同名但语义不同，混用是事故高发区。
- 取消是协作式的：协程不 `await` 就收不到 `CancelledError`。

## 11. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[F1]` | python.org | https://docs.python.org/3.12/library/asyncio-future.html | `Future` 状态、`result`/`exception`/`cancel`/`add_done_callback`、`wrap_future`、`InvalidStateError` |
| `[F2]` | python.org | https://docs.python.org/3.12/library/concurrent.futures.html | 线程池 Future 的阻塞语义、`cancel`、`running`、`as_completed` |
| `[F3]` | python.org | https://docs.python.org/3.12/library/asyncio-task.html | `Task` 继承 `Future`、`create_task`、取消语义、`gather` |
| `[F4]` | PEP 官方 | https://peps.python.org/pep-0008/ | 命名、注释写「为什么」 |
| `[F5]` | python.org | https://docs.python.org/3.12/library/asyncio-dev.html | `Future exception was never retrieved`、未消费异常 |
| `[F6]` | python.org | https://docs.python.org/3.12/library/asyncio-eventloop.html | `create_future`、`call_soon`、`set_exception_handler` |
| `[F7]` | python.org | https://docs.python.org/3.12/library/threading.html | 线程池与循环的边界 |
| `[F8]` | PEP 官方 | https://peps.python.org/pep-3156/ | `asyncio` 设计中的 Future/协程模型 |

> **核对状态**：`[F4]` 与本章 `README.md` 已核对来源一致；其余按 `docs.python.org/3.12` 官方结构整理，**本次未逐页直连复核**。文中「实测」为本机 Python 3.12.8 运行结果。

## 12. 毕业自查清单

**能说清（概念层）**：

- [ ] Future 与 Task 的关系（继承）
- [ ] `done()` 为什么不等于成功
- [ ] `CancelledError` 为什么继承 `BaseException`
- [ ] 异常为什么必须 `result()` / `await` 才会抛出
- [ ] `asyncio.Future.result()` 与线程池 `Future.result()` 的差别
- [ ] `add_done_callback` 的异常去哪了
- [ ] `wrap_future` 解决什么问题
- [ ] `as_completed` 与 `gather` 的顺序差异

**能写出（代码层）**：

- [ ] 三种结局的判定（取消 → 异常 → 正常）
- [ ] `create_future` + `call_later(set_result)` + `await`
- [ ] `add_done_callback` 收集结果并记日志
- [ ] 线程池 `submit` + `result(timeout)`
- [ ] `await asyncio.wrap_future(cf)`
- [ ] `asyncio.run_coroutine_threadsafe` 从线程投递

**能判断（避坑层）**：

- [ ] 看到 pending 上 `result()` 能指出 `InvalidStateError`
- [ ] 看到 `done()` 当成功标志能指出错
- [ ] 看到裸 `except:` 能指出吞掉取消
- [ ] 看到循环里线程池 `result()` 能指出阻塞
- [ ] 看到 `cancel()` 返回 True 能指出不保证停止
- [ ] 看到两套 Future 混用能指出桥接方式

**能跑通（验收层）**：

- [ ] 运行 `examples/future_demo.py` 并解释三行输出
- [ ] 把第 8 节示例存成文件运行，输出与文档一致
- [ ] 在 REPL 复现 `InvalidStateError`
- [ ] 用 `add_done_callback` 观察回调在下一轮执行

## 13. 下一章衔接

第 26 章 `协程 Coroutine`：Future 是「结果的占位符」，协程是「可暂停的计算」。下一章讲 `async def` 为什么调用不执行、awaitable 三类如何统一、`create_task` 与 `await` 的差别。

本章留下的伏笔：

1. `Task` 是 `Future` 子类——第 26 章会用它解释「为什么 Task 可以重复 await，协程不行」。
2. `add_done_callback` 与第 24 章的 `call_soon` 是同一套调度。
3. `CancelledError` 的处理方式决定第 27 章优雅关闭能不能写对。