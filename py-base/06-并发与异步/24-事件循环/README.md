# 24 事件循环

> 承接第 28 章：线程是「由操作系统抢占切换」，事件循环是「单线程内协作式调度」。本章是 25–27 章的地基。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 17、28 章（生成器、并发） |
| 本章目标 | 事件循环职责、`asyncio.run()`、回调调度、协作式并发、阻塞陷阱 |
| 毕业标准 | 能说清事件循环何时切换任务；能解释为什么 `time.sleep` 会卡住整个循环 |
| 编码要求 | 能运行 `examples/loop_demo.py` 并解释输出顺序 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节；「未直连核对」的链接按官方文档通行表述整理。

## 1. 概念

- 事件循环是 `asyncio` 的核心：它执行任务、处理 I/O 事件、调度回调，在**单线程**里通过协作式切换实现并发。`[R1]` `[R2]`
- `asyncio.run(coro)` 是运行顶层协程的标准入口：创建循环、跑完协程、清理并关闭；应用代码通常不应自己管理循环生命周期。`[R1]`
- `loop.call_soon(callback, *args)` 尽快排队回调，`call_later(delay, ...)` 延迟调度；`asyncio.get_running_loop()` 取当前运行中的循环。`[R2]`
- 任务只在**显式让出控制权**（`await`）时切换；因此 CPU 密集循环或阻塞调用（如 `time.sleep`、同步 HTTP）会卡住整个循环。`[R1]`
- 与第 28 章对照：线程由调度器抢占，事件循环由代码主动 `await` 让出；前者适合阻塞库，后者适合大量 I/O 等待。`[R1]`
- 调试模式与慢回调日志能帮助定位「谁阻塞了循环」。`[R2]`

## 2. 注意事项

1. **循环里绝不调用 `time.sleep()`**，用 `await asyncio.sleep()`。`[R1]`
2. **不要在 `async def` 里做同步阻塞 I/O**，用支持异步的库或 `to_thread()`。`[R2]`
3. **不要手写 `new_event_loop()` / `close()`**，优先 `asyncio.run()`。`[R1]`
4. **回调里抛出的异常不会自动冒泡到业务代码**，要显式处理。`[R2]`
5. **单线程不等于无竞态**：`await` 前后共享状态可能已被别的任务改掉。

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 阻塞代价 | 一个任务阻塞会拖住同循环内所有任务 | `[R1]` |
| CPU 密集 | 事件循环不能并行计算，应交给线程池/进程（第 28 章） | `[R1]` |
| 嵌套循环 | 已有运行中的循环时不能再 `asyncio.run()` | `[R1]` |
| 与生成器 | 历史上协程由生成器演进而来（第 17、26 章） | `[R3]` |

## 4. 最佳实践

1. **一个进程一个循环，用 `asyncio.run()` 做唯一入口**。`[R1]`
2. **I/O 全部用 awaitable 版本**，同步库用 `asyncio.to_thread()` 隔离。`[R2]`
3. **打开 `PYTHONASYNCIODEBUG=1` 或 debug 模式排查慢回调**。`[R2]`
4. **给循环内任务加超时与取消**（第 27 章）。

## 5. 最佳编码建议

- **命名表达意图、注释解释「为什么这里让出」**。`[R4]`
- **共享状态集中管理**，不在 `await` 前后散落假设（第 06 章）。
- **失败要快**：回调异常记录日志并上报（第 01 章）。
- **不硬编码超时**，走配置。

## 6. 编码示例

`examples/loop_demo.py`：

```python
"""第 24 章示例：asyncio.run 与事件循环回调。"""

import asyncio

async def main():
    """展示当前循环与 call_soon 调度 [R2]。"""
    loop = asyncio.get_running_loop()
    print("事件循环:", type(loop).__name__)
    loop.call_soon(print, "call_soon 回调已执行")
    await asyncio.sleep(0)
    print("让出控制权后继续")

asyncio.run(main())
```

运行：

```powershell
cd 'E:\ai-agent-study\py-base\06-并发与异步\24-事件循环'
python examples/loop_demo.py
```

关键输出顺序：`事件循环` → `call_soon 回调已执行` → `让出控制权后继续`——`await asyncio.sleep(0)` 主动让出，排队的回调才有机会执行。`[R1]` `[R2]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/asyncio-eventloop.html | 事件循环职责、`asyncio.run()`、阻塞陷阱、debug 模式 |
| `[R2]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/asyncio.html | `call_soon` / `call_later` / `get_running_loop` / `to_thread`、回调异常 |
| `[R3]` | PEP 官方 · 未直连核对 | https://peps.python.org/pep-0492/ | 协程与 `await` 的引入、基于生成器的历史 |
| `[R4]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | 命名约定、注释写「为什么」 |

## 8. 毕业自查清单

- [ ] 能说清事件循环在什么时候切换任务
- [ ] 能解释 `time.sleep` 为什么会卡住整个循环
- [ ] 能说出 `asyncio.run()` 为什么是推荐入口
- [ ] 能说出事件循环与多线程的适用边界
- [ ] 能运行 `examples/loop_demo.py` 并解释输出顺序

## 9. 下一章衔接

第 25 章 `Future类`：事件循环调度的是「还没完成的结果」，Future 就是这个占位符——状态、`result()`、`add_done_callback`、与 Task 的关系。
