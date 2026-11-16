# 28 多线程与多进程

> 按认知顺序先于 24–27 章：先建立「并发」直觉，再看事件循环与协程。Agents 里并发调用多个工具/模型是性能核心。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 16、18 章（异常、上下文管理器） |
| 本章目标 | GIL、I/O 密集 vs CPU 密集、`threading` / `multiprocessing` / `concurrent.futures`、竞态与锁 |
| 毕业标准 | 能解释 GIL 下线程为何仍对 I/O 有用；能说出三种方案的取舍 |
| 编码要求 | 能运行 `examples/concurrency_demo.py` 并解释结果为何保序 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节；「未直连核对」的链接按官方文档通行表述整理。

## 1. 概念

- **GIL**：CPython 的全局解释器锁使同一时刻只有一个线程执行 Python 字节码；因此线程**不能**并行跑 CPU 密集任务，但 I/O 等待时会释放 GIL，线程对 I/O 密集仍有效。`[R1]` `[R2]`
- `threading` 提供底层线程与 `Lock`；`multiprocessing` 用独立进程绕开 GIL，适合 CPU 密集，但序列化与进程间通信成本高。`[R1]`
- `concurrent.futures` 提供高层 `ThreadPoolExecutor` / `ProcessPoolExecutor`；`Executor.map()` **按输入顺序返回结果**。`[R3]`
- `with ThreadPoolExecutor(...) as pool:` 会正常关闭并等待任务完成（第 18 章上下文管理器）。`[R3]`
- 共享可变状态需要锁；**最好一开始就避免共享**（第 06 章作用域）。`[R1]`
- `queue.Queue` 是线程安全的生产者-消费者通道。`[R1]`
- 并发任务里的异常不会自动冒泡到主线程，需从 `Future.result()` 取回（第 25 章）。`[R3]`

## 2. 注意事项

1. **CPU 密集中不要用线程**，换进程或原生扩展。`[R1]`
2. **不要在无锁情况下改共享容器**。`[R1]`
3. **`ProcessPoolExecutor` 的任务与结果必须可 pickle**。`[R1]`
4. **不要手工管理线程生命周期**，用 `with` + executor。`[R3]`
5. **线程数不是越多越好**，I/O 型按并发上限设 `max_workers`。
6. **子线程异常要显式收集**，别静默丢失（第 01 章）。`[R3]`

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| GIL 适用范围 | 只约束 CPython 字节码执行；C 扩展/系统 I/O 可释放 | `[R2]` |
| 进程成本 | 启动、内存、序列化开销大，小任务不划算 | `[R1]` |
| 异常传播 | 需 `Future.result()` 或回调显式取回 | `[R3]` |
| 与 asyncio | 事件循环是单线程协作式并发，见第 24–27 章 | `[R4]` |
| 调试 | 竞态难复现，日志要有任务标识（第 32 章） | `[R1]` |

## 4. 最佳实践

1. **I/O 密集用 `ThreadPoolExecutor`，CPU 密集用 `ProcessPoolExecutor`**。`[R1]` `[R3]`
2. **优先传值、返回结果**，不共享可变状态。`[R1]`
3. **用 `with` 管理 executor**，保证关闭。`[R3]`
4. **给并发上限设边界**，避免打爆下游服务。
5. **失败要快**：收集并上报每个任务的异常。`[R3]`

## 5. 最佳编码建议

- **任务函数保持纯**（输入决定输出），便于测试与并行。
- **注释解释「为什么用线程/进程」**。`[R5]`
- **命名表达意图、不硬编码并发数**，走配置。
- **日志不打印敏感数据**（第 01 章）。

## 6. 编码示例

`examples/concurrency_demo.py`（无真实 I/O、无副作用）：

```python
"""第 28 章示例：ThreadPoolExecutor 并行执行 I/O 型任务。"""

import concurrent.futures

def fetch(name):
    """模拟一次工具调用（无真实 I/O）[R3]。"""
    return name + ":ok"

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    results = list(pool.map(fetch, ["search", "cache", "translate"]))

print("结果:", results)
```

运行：

```powershell
cd 'E:\ai-agent-study\py-base\06-并发与异步\28-多线程与多进程'
python examples/concurrency_demo.py
```

关键输出：`结果: ['search:ok', 'cache:ok', 'translate:ok']`——`Executor.map` 保序，与完成先后无关。`[R3]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/threading.html | 线程、`Lock`、GIL 对 CPU 密集的影响、`queue` 配合 |
| `[R2]` | python.org · 未直连核对 | https://docs.python.org/3.12/glossary.html | GIL 术语定义 |
| `[R3]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/concurrent.futures.html | `Executor`、`map` 保序、`Future.result()`、`with` 关闭语义 |
| `[R4]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/asyncio.html | 事件循环属于协作式并发，与线程模型不同 |
| `[R5]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | 命名约定、注释写「为什么」 |

## 8. 毕业自查清单

- [ ] 能解释 GIL 下线程为何对 I/O 密集仍有效
- [ ] 能说出线程 / 进程 / 协程三种方案的适用边界
- [ ] 能说出 `Executor.map` 的保序特性
- [ ] 能说出并发任务异常该如何收集
- [ ] 能运行 `examples/concurrency_demo.py` 并解释输出

## 9. 下一章衔接

第 24 章 `事件循环`：从「多线程并发」切到「单线程协作式并发」——事件循环如何调度任务，随后 25 Future、26 协程、27 异步编程。
