# 25 Future类

> 承接第 24 章：事件循环调度的是「还没完成的结果」。Future 就是这个占位符，也是 Task 的基类概念。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 24、28 章（事件循环、并发） |
| 本章目标 | Future 状态、`result()` / `exception()` / `done()`、完成回调、Task 与 Future |
| 毕业标准 | 能说出 Future 与 Task 的关系；能解释为什么异常要通过 `result()` 才会重新抛出 |
| 编码要求 | 能运行 `examples/future_demo.py` 并解释 `是否完成` 与 `异常` 两行 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节；「未直连核对」的链接按官方文档通行表述整理。

## 1. 概念

- `concurrent.futures.Future` 表示**异步操作的最终结果**：可查询状态、取结果、取异常、注册完成回调。`[R1]`
- 常用方法：`done()`、`result()`（未完成则阻塞等待）、`exception()`、`cancel()`、`add_done_callback()`。`[R1]`
- 关键点：**任务里抛出的异常存在 Future 里，调用 `result()` 时才重新抛出**；不取结果就永远看不到错误（静默失败，第 01 章禁止）。`[R1]`
- `asyncio.Future` 是事件循环侧的 awaitable 版本；`asyncio.Task` 是 `Future` 的子类，负责在循环里驱动协程。`[R2]` `[R3]`
- 三种 awaitable：协程对象、`Task`、`Future`——它们都能被 `await`（第 26 章）。`[R2]`
- 线程池 executor 的 `submit()` 返回的就是 `concurrent.futures.Future`，与 `asyncio` 的 Future 不是同一个类，不要混用方法。`[R1]` `[R2]`

## 2. 注意事项

1. **一定要消费 `result()` 或 `exception()`**，否则异常被吞。`[R1]`
2. **不要混用两类 Future**：`asyncio.Future` 不能在线程代码里 `.result()` 阻塞等待。`[R2]`
3. **`add_done_callback` 里的异常不会冒泡到主流程**，要自己记录。`[R1]`
4. **不要手写 Future 状态机**，用 `create_task` / `gather`（第 27 章）。`[R3]`
5. **取消不等于立即停止**，任务需要在 `await` 点响应取消。`[R3]`

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 异常可见性 | 不取结果 = 静默失败，日志里也看不到 | `[R1]` |
| 阻塞 | 线程池 Future 的 `result()` 会阻塞当前线程，事件循环里禁用 | `[R1]` `[R2]` |
| 取消语义 | `CancelledError` 继承 `BaseException`（3.8+），别被裸 `except` 吞掉 | `[R3]` |
| 跨框架 | `asyncio.wrap_future` 可桥接两类 Future | `[R2]` |

## 4. 最佳实践

1. **统一用高层 API**：`asyncio.gather` / `TaskGroup`（第 27 章）。`[R3]`
2. **每个任务的结果/异常都要被消费**，并写日志。
3. **给等待设超时**，不要无限阻塞。`[R1]`
4. **失败要快且明确**，异常信息带任务标识（第 01 章）。

## 5. 最佳编码建议

- **命名表达意图**：`search_future`，不用 `f1`。`[R4]`
- **注释解释「为什么在这里阻塞取结果」**。`[R4]`
- **不硬编码超时、不吞异常**（第 01 章）。
- **不做预留抽象**（第 01 章）。

## 6. 编码示例

`examples/future_demo.py`：

```python
"""第 25 章示例：Future 的结果与状态。"""

import concurrent.futures

def fetch(name):
    """模拟一次工具调用 [R1]。"""
    return name + ":ok"

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    future = pool.submit(fetch, "search")
    print("结果:", future.result())
    print("是否完成:", future.done())
    print("异常:", future.exception())
```

运行：

```powershell
cd 'E:\ai-agent-study\py-base\06-并发与异步\25-Future类'
python examples/future_demo.py
```

关键输出：`结果: search:ok`、`是否完成: True`、`异常: None`——`result()` 会等待完成，异常则通过 `exception()` 读取。`[R1]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/concurrent.futures.html | `Future` 状态、`result()` / `exception()` / `done()` / `cancel()` / `add_done_callback()`、`submit()` |
| `[R2]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/asyncio-future.html | `asyncio.Future` 是 awaitable、与线程池 Future 的区别、`wrap_future` |
| `[R3]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/asyncio-task.html | `Task` 继承 `Future`、`create_task`、`CancelledError`、取消与 `TaskGroup` |
| `[R4]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | 命名约定、注释写「为什么」 |

## 8. 毕业自查清单

- [ ] 能说出 Future 与 Task 的关系
- [ ] 能解释异常为什么必须 `result()` 才会重新抛出
- [ ] 能说出两类 Future 的区别
- [ ] 能说出取消操作为什么不是立即停止
- [ ] 能运行 `examples/future_demo.py` 并解释三行输出

## 9. 下一章衔接

第 26 章 `协程 Coroutine`：`async def` 得到协程对象，它本身还不会执行；只有交给事件循环包成 Task 才跑起来。下一章把 awaitable 三者串起来。
