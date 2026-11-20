# 70 BackgroundTasks

## 一句话结论

`BackgroundTasks` 在**响应发送之后**执行任务：客户端先拿到 `{"status":"accepted"}`，然后才发邮件、写审计。实测任务严格按添加顺序**串行**（`record → notify`，`t0 → t1 → t2`）；同步任务跑在线程池（`async def` 端点线程 `57124` vs 任务线程 `75720`），异步任务跑在当前事件循环；任务抛 `RuntimeError` 时客户端**仍拿到 200**（宽松模式），严格模式下异常才暴露。`TestClient` 会等后台任务跑完（120ms 任务 → 请求 124ms）。它**不是队列**：进程重启任务就丢，重活请交给 Celery/RQ/Arq。

## 最小可运行案例

```python
from fastapi import BackgroundTasks, FastAPI

app = FastAPI()


def write_audit(name: str) -> None:
    # 同步任务 → 线程池
    print("audit", name)


async def send_mail(name: str) -> None:
    # 异步任务 → 事件循环
    print("mail", name)


@app.post("/orders")
def create_order(background: BackgroundTasks, name: str = "商品") -> dict[str, str]:
    background.add_task(write_audit, name)
    background.add_task(send_mail, name)
    return {"status": "accepted"}      # 客户端立刻拿到，任务随后执行
```

## 怎么跑

```powershell
cd "11-应用结构\70-BackgroundTasks\examples"
uv sync
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 响应已生成 -> 200 accepted
[PASS] 端点在前 -> endpoint → record:键盘 → notify:键盘:email
[PASS] 两任务顺序 -> record → notify
[PASS] kwargs 传递 -> notify:鼠标:sms
[PASS] 三任务顺序 -> t0 → t1 → t2
[PASS] 同步走线程池 -> loop=57124 / task=75720
[PASS] 异步走事件循环 -> ProactorEventLoop
[PASS] 异常不影响响应 -> 200 已返回，异常在服务端
[PASS] 异常可暴露 -> 后台任务失败了
[PASS] 依赖里挂任务 -> 依赖任务在端点之后
[PASS] 客户端会等待 -> 124ms（含 120ms 任务）
[PASS] state 可用 -> counter 1 → 2
[PASS] create_task 不等待 -> 4ms，不等待
[PASS] 失败不连累后续 -> 失败不影响后续

结果：14/14 通过
```

## 核心 API 速查

| API | 行为 |
| --- | --- |
| `background.add_task(fn, *args, **kwargs)` | 排队，响应后执行 |
| 同步 `def` 任务 | 线程池 |
| 异步 `async def` 任务 | 当前事件循环 |
| 多个任务 | 按添加顺序**串行** |
| 任务异常 | 不影响已发出的响应 |
| `asyncio.create_task` | **立刻**开始，不被等待 |

| 实测 | 值 |
| --- | --- |
| 任务顺序 | `record → notify` |
| 端点 vs 任务 | 端点先 |
| 同步任务线程 | 事件循环线程之外 |
| 120ms 任务 | 请求耗时 124ms（TestClient 等待）|
| 任务异常 + 宽松模式 | 200 |
| 任务异常 + 严格模式 | `RuntimeError` |
| `create_task` | 4ms 返回，不等待 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 把重活放后台任务 | 占 worker，重启就丢 | Celery/RQ/Arq |
| 以为任务并发 | 实际串行，慢任务拖后面的 | 分开任务或真队列 |
| 依赖任务成功才发通知 | 异常时任务不执行 | 用 `finally` 或独立任务 |
| 任务里用 `Request` 对象 | 请求已结束，报错 | 提前取出需要的值 |
| 任务里改响应 | 已发送，改不了 | 提前决定 |
| 异常不记录 | 静默失败 | `try/except` + 日志 |
| 用 `create_task` 当后台任务 | 不被等待、异常丢失 | `BackgroundTasks` |
| 任务里开新会话写库 | 可能拿不到连接 | 显式创建/关闭 |
| 长任务（分钟级） | 阻塞 worker | 队列 |
| `TestClient` 不等待 | 实际会等，测试变慢 | 用 mock 替换任务 |
| 期望任务跨进程 | 不共享 | 外部队列 |
| 任务里读 `request.state` | 可能已销毁 | 提前拷贝 |
| 用任务做事务提交 | 事务已结束 | 在请求内提交 |
| 多个任务顺序依赖 | 串行可用但脆弱 | 合并成一个任务 |
| 任务重试 | 无内置 | 队列 + 重试策略 |
| 任务幂等 | 未考虑 | 加唯一键 |

## 毕业自查

- [ ] 能写出 `add_task` 的端点
- [ ] 能说清任务在响应前还是后
- [ ] 能区分同步/异步任务跑在哪
- [ ] 能解释任务异常为什么不影响响应
- [ ] 知道它为什么不是队列
- [ ] 动手题一：把「发邮件」换成失败重试 3 次
- [ ] 动手题二：用 `asyncio.create_task` 做对比，观察时序

> 想看 Starlette 的 `BackgroundTask` 实现、响应发送顺序、异常传播、与队列的边界、18 条坑，继续读 [`base.md`](./base.md)。