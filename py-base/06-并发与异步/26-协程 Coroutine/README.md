# 26 协程 Coroutine

> 承接第 25 章：Future 是「结果的占位符」，协程是「可被暂停和恢复的计算」。本章把 `async def` / `await` 讲透。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 17、24–25 章（生成器、事件循环、Future） |
| 本章目标 | 协程对象、awaitable 三类、`async def` / `await`、`create_task`、协程与生成器 |
| 毕业标准 | 能解释「调用 `async def` 不会执行函数体」；能说出 awaitable 三类 |
| 编码要求 | 能运行 `examples/coroutine_demo.py` 并解释 `协程对象` 一行 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节；「未直连核对」的链接按官方文档通行表述整理。

## 1. 概念

- `async def` 定义的函数是**协程函数**；调用它只返回**协程对象**，函数体**尚未执行**。必须 `await` 或交给事件循环调度才会运行。`[R1]` `[R2]`
- 三类 awaitable：`coroutine`（可 await 的协程对象）、`Task`（被调度的协程）、`Future`（结果的占位符，第 25 章）。`[R1]`
- `await` 只能在 `async def` 内使用；它挂起当前协程、把控制权交还事件循环，等 awaitable 完成后恢复。`[R2]`
- `asyncio.create_task(coro)` 把协程包成 Task **立即排入循环**，适合并发启动多个操作；`asyncio.run(coro)` 是顶层入口（第 24 章）。`[R1]`
- 历史：PEP 492 引入原生协程之前，协程由生成器 + `yield from` 演进而来（第 17 章）；两者语法相近但语义不同。`[R2]` `[R3]`
- 异步生成器（`async def` + `yield`）与 `async for` 由 PEP 525 定义，用于流式产出（第 27 章 Agents 流式输出）。`[R4]`

## 2. 注意事项

1. **别忘 `await`**：未 await 的协程不会执行，且会产生 `RuntimeWarning`。`[R1]`
2. **不要在同步函数里直接 `await`**，会语法错误；用 `asyncio.run()` 进入。
3. **不要在协程里阻塞**（第 24 章）。
4. **协程对象只能 await 一次**，重复 await 会报错。`[R1]`
5. **`create_task` 后的任务要保留引用**，否则可能被垃圾回收（官方有明确提醒）。`[R1]`
6. **不要手写基于生成器的旧式协程**，新代码用 `async def`。`[R2]`

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 惰性 | 调用协程函数不执行，副作用发生得更晚 | `[R1]` |
| 取消 | 取消在 `await` 点生效，CPU 密集段无法及时响应 | `[R1]` |
| 异常 | 未被 await 的 Task 异常可能只在循环结束时报告（第 25 章） | `[R1]` |
| 同步边界 | 同步库要 `to_thread()` 隔离（第 24 章） | `[R1]` |
| 类型标注 | 协程返回类型写作 `Coroutine[...]` 或 `Awaitable[T]`（第 20 章） | `[R2]` |

## 4. 最佳实践

1. **顶层唯一 `asyncio.run()`，内部全用 `await` / `create_task`**。`[R1]`
2. **需要并发才 `create_task`**，顺序依赖直接 `await`。
3. **用 `asyncio.gather` / `TaskGroup` 管理一组任务**（第 27 章）。`[R1]`
4. **给每个任务加超时与异常处理**，不静默丢结果。
5. **流式输出用异步生成器**，别一次性拼完整字符串。

## 5. 最佳编码建议

- **函数名表达意图、docstring 说明它是协程**。`[R5]`
- **注释解释「为什么这里并发 / 为什么让出」**。`[R5]`
- **显式优于隐式、失败要快**（第 01 章）。
- **不硬编码超时与并发数**。

## 6. 编码示例

`examples/coroutine_demo.py`：

```python
"""第 26 章示例：协程对象与 await。"""

import asyncio

async def fetch(name):
    """模拟一次异步工具调用 [R1]。"""
    await asyncio.sleep(0)
    return name + ":ok"

async def main():
    """展示协程对象与执行时机。"""
    coro = fetch("search")
    print("协程对象:", type(coro).__name__)
    print("结果:", await coro)

asyncio.run(main())
```

运行：

```powershell
cd 'E:\ai-agent-study\py-base\06-并发与异步\26-协程 Coroutine'
python examples/coroutine_demo.py
```

关键输出：`协程对象: coroutine` → `结果: search:ok`，说明 `fetch(...)` 本身没执行函数体，`await` 才驱动它。`[R1]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/asyncio-task.html | 协程对象、awaitable 三类、`create_task`、保留任务引用、`gather` / `TaskGroup` |
| `[R2]` | PEP 官方 · 未直连核对 | https://peps.python.org/pep-0492/ | `async def` / `await`、原生协程与生成器的区别、`Awaitable` |
| `[R3]` | PEP 官方 · 未直连核对 | https://peps.python.org/pep-0380/ | `yield from` 委托，协程实现的历史基础 |
| `[R4]` | PEP 官方 · 未直连核对 | https://peps.python.org/pep-0525/ | 异步生成器与 `async for` |
| `[R5]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | 命名约定、docstring、注释写「为什么」 |

## 8. 毕业自查清单

- [ ] 能解释为什么调用 `async def` 不会执行函数体
- [ ] 能列出三类 awaitable
- [ ] 能说出 `create_task` 与直接 `await` 的差别
- [ ] 能说出协程与生成器在历史上的关系
- [ ] 能运行 `examples/coroutine_demo.py` 并解释两行输出

## 9. 下一章衔接

第 27 章 `异步编程`：把事件循环、Future、协程组合成真实能力——并发 `gather`、超时与取消、`async with`、异步流式输出，以及 Agents 服务端的典型形态。
