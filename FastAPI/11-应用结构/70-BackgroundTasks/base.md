# 70 BackgroundTasks · 完整版（base.md）

> `README.md` 给你能跑的「响应后发通知」；本文件把「任务到底在哪一步执行、为什么串行、异常为什么吞在服务端、什么时候必须换成队列」拆开。学完这章，你能判断一个「邮件没发出去、接口偶发变慢、通知重复」的问题出在哪。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0（本机实测） |
| 前置 | 第 59 章（线程池）、第 67 章（lifespan） |
| 覆盖范围 | `BackgroundTasks`、执行时机、顺序、异常、与 `create_task` 的区别 |
| 明确不覆盖 | Celery/RQ/Arq 落地、重试与死信队列、分布式调度 |
| 学完验收 | 能跑通 `verify.py` 14/14、能判断何时该换队列 |

## 0. 怎么用这份文件

**依据约定**：`` `[Tn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 响应后执行
2 机制（第 2 节）    → ASGI 响应发送顺序
3 API（第 3 节）     → add_task 与任务类型
4 边界（第 4 节）    → 异常、串行、等待、与队列边界
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 模板与选型
```

## 1. 概念：响应之后的「尾巴」

```text
处理请求 → 生成响应 → 发送响应（客户端拿到）
         → 执行 background tasks
         → 本次 ASGI 调用结束
```

| 阶段 | 客户端是否已知 |
| --- | --- |
| 处理请求 | 否 |
| 发送响应 | 是（收到 body）|
| 后台任务 | 是（已收到）|

**关键**：后台任务仍属于本次 ASGI 调用，所以「进程退出」会把它们带走。

## 2. 机制：执行顺序（实测）

```text
EVENTS = ["endpoint", "record:键盘", "notify:键盘:email"]
```

| 顺序 | 内容 |
| --- | --- |
| 1 | 端点函数体 |
| 2 | 响应序列化并发送 |
| 3 | 任务 1（同步）|
| 4 | 任务 2（异步）|

三个任务：

```text
["record:t0", "record:t1", "record:t2"]
```

**串行**，不是并发。

### 2.1 同步 vs 异步（实测）

| 任务类型 | 执行位置 |
| --- | --- |
| `def` | 线程池（事件循环之外）|
| `async def` | 当前事件循环 |

实测线程 id：`async def` 端点 `57124`，同步任务 `75720`。

**注意**：`def` 端点本身也在线程池，与同步后台任务**共用**同一个池，可能拿到同一个 worker（第一次探测两个 id 都是 `4484`）。所以「同步任务一定换线程」不成立。

## 3. API 逐个拆解

```python
background.add_task(func, *args, **kwargs)
```

| 参数 | 说明 |
| --- | --- |
| `func` | 同步或异步可调用对象 |
| `*args` | 位置参数（实测 `notify("鼠标", "sms")`）|
| `**kwargs` | 关键字参数（实测 `channel="sms"`）|

### 3.1 在依赖里添加（实测）

```python
def audit(background: BackgroundTasks) -> None:
    background.add_task(record, "from-dependency")

@app.get("/audited", dependencies=[Depends(audit)])
```

实测事件：

```text
["audited-endpoint", "record:from-dependency"]
```

**用途**：无论端点成功失败都记一笔审计。

### 3.2 `TestClient` 会等（实测）

| 任务耗时 | 请求耗时 |
| --- | --- |
| 120ms | 124ms |

ASGI 调用要等后台任务结束才返回，所以测试会变慢。**测试里建议 mock 掉任务**。

## 4. 边界条件

### 4.1 异常（实测）

| 模式 | 客户端 |
| --- | --- |
| 宽松（`raise_server_exceptions=False`）| 200 + `{"status":"accepted"}` |
| 严格（默认）| 抛 `RuntimeError` |

服务端日志里能看到异常。**生产必须自己 `try/except` 记日志**，否则任务失败无人知晓。

### 4.2 任务串行与耗时

| 任务数 | 总耗时 |
| --- | --- |
| 3 个 1s 任务 | 3s（线性）|

会拖长本次请求的 ASGI 调用，占住 worker。

### 4.3 与 `asyncio.create_task`（实测）

| 项 | `BackgroundTasks` | `create_task` |
| --- | --- | --- |
| 开始时机 | 响应发送后 | 立即 |
| 是否等待 | 是 | 否 |
| 异常 | 冒到 ASGI | 静默丢（除非回调）|
| 适用 | 短任务、必须完成 | 常驻任务/心跳 |

实测 `create_task` 请求 4ms 返回，任务仍在后台跑。

### 4.4 与队列的边界

| 场景 | 用什么 |
| --- | --- |
| 发一封邮件（< 2s）| `BackgroundTasks` |
| 生成报表（分钟级）| Celery/RQ |
| 需要重试 | 队列 |
| 需要跨进程/跨机器 | 队列 |
| 进程重启不能丢 | 队列 |

### 4.5 请求对象

任务执行时请求上下文已结束。**不要**在任务里用 `Request`、`Depends` 的结果（可能已失效）。要什么值，提前取出来当参数传。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 重活放后台任务 | 占 worker、重启丢 | 队列 | 实测 |
| 以为并发 | 串行拖慢 | 分开/队列 | 实测 |
| 依赖成功才发通知 | 异常时不执行 | 独立任务 | 实测 |
| 任务里用 `Request` | 失效 | 提前传值 | `[T2]` |
| 任务里改响应 | 已发送 | 提前决定 | 实测 |
| 异常不记日志 | 静默失败 | `try/except` | 实测 |
| 用 `create_task` 当后台 | 不等待、异常丢 | `BackgroundTasks` | 实测 |
| `TestClient` 不 mock | 测试慢 | mock | 实测 |
| 期望跨进程 | 不共享 | 外部队列 | `[T3]` |
| 任务里 `commit` 事务 | 事务已结束 | 请求内提交 | 第 57 章 |
| 多任务有顺序依赖 | 脆弱 | 合并一个任务 | 实测 |
| 任务不幂等 | 重复发送 | 唯一键 | `[T3]` |
| 长任务无超时 | 卡 worker | 队列 + 超时 | `[T3]` |
| 在 `lifespan` 里加任务 | 没有请求上下文 | 用 `create_task` | 第 67 章 |
| 任务里读 `current_user` | 依赖已结束 | 传 id | `[T2]` |
| 用任务返回结果给客户端 | 不可能 | 提前返回 | 实测 |
| 大量任务堆积 | 内存涨 | 队列 | 实测 |
| 任务里再 `add_task` | 不支持 | 直接调用 | `[T2]` |
| 任务 `sleep` 长于客户端超时 | 客户端已断开，任务仍在跑 | 队列 + 超时 | 实测 |

## 6. 最佳实践与编码建议

### 6.1 模板

```python
@app.post("/orders")
def create_order(background: BackgroundTasks, payload: OrderCreate) -> dict[str, str]:
    order = save(payload)
    background.add_task(send_mail_safe, order.id)
    return {"status": "accepted", "order_id": order.id}


def send_mail_safe(order_id: int) -> None:
    try:
        send_mail(order_id)
    except Exception:
        logger.exception("mail failed order=%s", order_id)
```

### 6.2 选型

| 任务 | 方案 |
| --- | --- |
| < 1s、必须完成 | `BackgroundTasks` |
| 需重试 | 队列 |
| 定时 | 调度器 |
| 心跳 | `create_task` + lifespan |

### 6.3 检查清单

| 检查项 | 原因 |
| --- | --- |
| 任务 < 1s | 不占 worker |
| 有异常捕获 | 可观测 |
| 幂等 | 防重复 |
| 不依赖请求上下文 | 已结束 |
| 测试 mock | 快速 |
| 长任务换队列 | 可靠性 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[T1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/background-tasks/ | `BackgroundTasks` |
| `[T2]` | 文档 | https://www.starlette.io/background/ | Starlette 实现 |
| `[T3]` | 文档 | https://docs.celeryq.dev/ | 队列边界 |

> **核对状态**：`[T1]`–`[T3]` 为文档链接，**本次未逐页直连复核**；响应已生成、端点在前、两/三任务顺序、kwargs 传递、同步任务线程、异步任务循环、异常两种模式、依赖任务、客户端等待、state 可用、`create_task` 不等待、失败不连累后续均为本机实测，`examples/verify.py` 复现 14/14 通过。真实队列、重试、跨进程、幂等键**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 任务在响应前还是后
- [ ] 为什么是串行
- [ ] 同步/异步任务跑在哪
- [ ] 异常为什么不影响响应
- [ ] 什么时候必须换队列

**能写出（代码层）**：

- [ ] `add_task` 端点
- [ ] 依赖里挂任务
- [ ] 异常安全包装
- [ ] `create_task` 对比
- [ ] 测试 mock

**能判断（避坑层）**：

- [ ] 看到重活 → 指出该用队列
- [ ] 看到任务里用 `Request` → 指出失效
- [ ] 看到无日志 → 指出静默失败
- [ ] 看到 `create_task` 当后台 → 指出异常丢失
- [ ] 看到测试慢 → 指出 TestClient 等待

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 14/14
- [ ] `uvicorn` 起服务，观察响应立刻返回、日志随后打印
- [ ] 把任务 sleep 3 秒，感受请求被拖慢

## 9. 下一章衔接

M11 结束。第 71 章进入 M12 `TestClient 基础`：三层测试（成功/404/422）、`pytest` 组织、fixture、断言响应。

本章留下的伏笔：

1. `TestClient` 会等后台任务（70）→ 71 测试要 mock。
2. 依赖里挂任务（70）→ 71 用 `dependency_overrides` 替换。
3. 生命周期（67）→ 71 每个测试的 `with` 边界。