# 27 异步编程

> 模块 06 收尾：事件循环（24）→ Future（25）→ 协程（26）已齐，本章把它们组装成可落地的异步服务端能力。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 24–26、28 章 |
| 本章目标 | `gather` / `TaskGroup`、超时与取消、`async with`、异步生成器、阻塞隔离 |
| 毕业标准 | 能说出 `gather` 的保序与异常行为；能解释同步阻塞库怎么隔离 |
| 编码要求 | 能运行 `examples/async_demo.py` 并解释结果顺序 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节；「未直连核对」的链接按官方文档通行表述整理。**示例不联网、不写磁盘。**

## 1. 概念

- `asyncio.gather(*aws)` 并发运行多个 awaitable，**按输入顺序**返回结果列表；默认某个任务抛异常会立即传播（其余任务不取消），`return_exceptions=True` 则把异常当结果返回。`[R1]`
- `asyncio.TaskGroup`（3.11+）是结构化的并发入口：任一任务失败会取消同组其余任务，并用 `ExceptionGroup` 汇总错误。`[R1]`
- 超时与取消：`asyncio.timeout(...)` / `wait_for(...)` 给等待设上界；`CancelledError` 在 `await` 点生效（第 25 章）。`[R1]`
- `async with` 使用异步上下文管理器（`__aenter__` / `__aexit__`），`async for` 消费异步生成器（第 18、17、26 章）。`[R2]` `[R3]`
- 同步阻塞库用 `asyncio.to_thread()` 或 `run_in_executor()` 隔离，避免拖住整个循环（第 24 章）。`[R2]`
- Agents 服务端典型形态：并发调用多个工具 → 汇总结果 → 以流式输出回传客户端；**接口协议（HTTP / SSE / WebSocket）本身不在本教程范围内**（第 01 章边界）。

## 2. 注意事项

1. **循环内禁止同步阻塞 I/O**（第 24 章）。`[R2]`
2. **`gather` 默认不取消其余任务**，需要「一个失败全停」用 `TaskGroup`。`[R1]`
3. **每个任务的结果/异常都要消费**（第 25 章）。
4. **超时要给每个外部调用设**，不能只设总时长。
5. **不要在异步代码里用同步 `Lock`**，用 `asyncio.Lock`。`[R2]`
6. **异常信息不要直接返回最终用户**（第 01 章）。

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 并发上限 | `gather` 一次起太多任务会打爆下游，用 `Semaphore` 限流 | `[R2]` |
| 取消传播 | `TaskGroup` 的取消是组内行为，跨组要显式处理 | `[R1]` |
| 混合同步库 | `to_thread` 有线程切换成本，小任务未必划算 | `[R2]` |
| 流式输出 | 异步生成器要配合 `async with` 保证资源释放 | `[R3]` |
| 与线程模型 | 事件循环是单线程协作式，与第 28 章互补 | `[R2]` |

## 4. 最佳实践

1. **并发 I/O 用 `gather` / `TaskGroup`，别手工 `create_task` 后散着 await**。`[R1]`
2. **给外部调用加超时 + 重试上限 + 明确异常类型**（第 16 章）。
3. **用 `Semaphore` 限制并发**，保护下游服务。
4. **流式响应用异步生成器**，边产出边发送。
5. **失败要快且明确**，异常带任务标识，不静默吞掉（第 01 章）。

## 5. 最佳编码建议

- **协程函数名表达意图、docstring 说明并发与超时策略**。`[R4]`
- **注释解释「为什么用 TaskGroup 而不是 gather」**。`[R4]`
- **配置外置**：超时、并发上限、模型名不硬编码（第 01 章）。
- **显式优于隐式、不做预留抽象**（第 01 章）。

## 6. 编码示例

`examples/async_demo.py`：

```python
"""第 27 章示例：gather 并发执行多个协程。"""

import asyncio

async def fetch(name, delay):
    """模拟不同耗时的工具调用 [R1]。"""
    await asyncio.sleep(delay)
    return name + ":ok"

async def main():
    """并发取回结果，按输入顺序汇总。"""
    results = await asyncio.gather(
        fetch("search", 0.02),
        fetch("cache", 0.01),
    )
    print("结果:", results)

asyncio.run(main())
```

运行：

```powershell
cd 'E:\ai-agent-study\py-base\06-并发与异步\27-异步编程'
python examples/async_demo.py
```

关键输出：`结果: ['search:ok', 'cache:ok']`——`cache` 更快完成，但 `gather` 仍按输入顺序返回。`[R1]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/asyncio-task.html | `gather` 保序与异常语义、`TaskGroup` / `ExceptionGroup`、`timeout`、`create_task` |
| `[R2]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/asyncio.html | `to_thread`、`Semaphore`、`Lock`、异步上下文管理器 |
| `[R3]` | PEP 官方 · 未直连核对 | https://peps.python.org/pep-0525/ | 异步生成器与 `async for` |
| `[R4]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | 命名、docstring、注释写「为什么」 |

## 8. 毕业自查清单

- [ ] 能说出 `gather` 的保序与默认异常行为
- [ ] 能说出 `TaskGroup` 与 `gather` 的取舍
- [ ] 能说出同步阻塞库的两种隔离方式
- [ ] 能说出流式输出为什么需要异步生成器 + `async with`
- [ ] 能运行 `examples/async_demo.py` 并解释结果顺序

## 9. 下一章衔接

第 29 章 `构建发布`：并发与异步主线结束，进入工程化收尾——打包、发布、项目管理工具、monorepo 与断点调试。
