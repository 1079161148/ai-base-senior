# 52 请求上下文与日志 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「为什么全局变量会串、`ContextVar` 的隔离单位、`call_next` 与子 task 的关系、日志 `Filter` 怎么注入、后台任务为什么还读得到」拆开。学完这章，你要能把一条 `trace_id` 从入口贯穿到任意深度的日志。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0（本机实测） |
| 前置 | 第 50 章（中间件）、`asyncio` 基础 |
| 覆盖范围 | `ContextVar`、请求 ID、`logging.Filter`、并发隔离、后台任务 |
| 明确不覆盖 | OpenTelemetry 全链路、日志采集（ELK/Loki）、敏感信息审计 |
| 学完验收 | 能跑通 `verify.py` 11/11、能证明并发不串、能接结构化日志 |

## 0. 怎么用这份文件

**依据约定**：`` `[Tn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 为什么不能用全局变量
2 机制（第 2 节）    → ContextVar 与 task
3 API（第 3 节）     → set/reset/get、Filter
4 边界（第 4 节）    → 并发、后台任务、reset
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 结构化日志
```

## 1. 概念：上下文是「每个请求一份」

| 方案 | 隔离单位 | 问题 |
| --- | --- | --- |
| 模块级变量 | 进程 | 并发串 |
| `threading.local` | 线程 | async 单线程复用，串 |
| 函数传参 | 调用链 | 签名爆炸 |
| `ContextVar` | asyncio task / 线程 | 正确 |

实测并发两个请求：`ctx_before` = `AAA` / `BBB` 各自正确；`global_after` 两边都是 `BBB`（后到的覆盖）。

## 2. 机制：`call_next` 会创建子 task

```text
请求 → 中间件（父 task）
        trace_id_var.set("AAA")      ← 必须在下面之前
        await call_next(request)     ← 内部 task_group 创建子 task，复制当前 context
                                     路由/端点/依赖都在子 task 里，读到 "AAA"
        finally: reset(token)
```

| 关键点 | 说明 |
| --- | --- |
| `set` 在 `call_next` 前 | 子 task 复制的是**创建时刻**的 context |
| `set` 在 `call_next` 后 | 子 task 已经跑完，改不到 |
| 子 task 内 `set` | 外层看不到（单向复制）|
| `reset(token)` | 归还上一个值，避免泄漏 |

### 2.1 纯 ASGI 中间件更直接

```python
class TraceMiddleware:
    def __init__(self, app): self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            return await self.app(scope, receive, send)
        token = trace_id_var.set(scope["headers"] and ... or uuid.uuid4().hex[:12])
        try:
            await self.app(scope, receive, send)
        finally:
            trace_id_var.reset(token)
```

没有子 task，行为可预测，但拿不到 `Response` 对象（改不了 header）。

## 3. API 逐个拆解

| API | 返回 | 说明 |
| --- | --- | --- |
| `ContextVar("n", default="")` | 实例 | 模块级单例 |
| `.set(v)` | `Token` | 必须保存 |
| `.reset(token)` | `None` | 恢复 set 之前的值 |
| `.get()` | 值或 default | 无值时给 default |

### 3.1 日志注入

```python
class TraceFilter(logging.Filter):
    def filter(self, record):
        record.trace_id = trace_id_var.get() or "-"
        return True
```

必须在 `Formatter` 里写 `%(trace_id)s`，否则 `KeyError`。

实测输出：

```text
INFO [my-123] ch52: 请求开始 GET /work
INFO [my-123] ch52: 业务处理中
INFO [my-123] ch52: 请求结束 status=200
```

## 4. 边界条件

### 4.1 并发隔离（实测）

```text
A: ctx_before=AAA, ctx_after=AAA, global_after=BBB
B: ctx_before=BBB, ctx_after=BBB, global_after=BBB
```

`ContextVar` 正确；全局变量被后到的覆盖。

### 4.2 请求后 reset（实测）

`client.get("/work")` 之后再 `trace_id_var.get()` → `""`。

**不 reset 的后果**：同步调用链（比如 CLI 脚本复用同一 context）会读到上一个请求的 id。

### 4.3 后台任务（实测）

`BackgroundTasks` 里 `trace_id_var.get()` 仍是本请求的 id。原因：Starlette 在响应后执行任务时用的是同一个 context 或复制品。

**但**：后台任务失败不影响响应，异常必须自己 `try/except` 记日志。

### 4.4 `request.state` vs `ContextVar`

| 维度 | `request.state` | `ContextVar` |
| --- | --- | --- |
| 作用域 | 请求对象 | 执行上下文 |
| 能否在工具函数里拿 | 要传 `request` | 直接 `get()` |
| 能否在日志 Filter 里拿 | 不能 | 能 |
| 推荐 | 端点内传值 | 全链路 |

实测两者在同一请求内一致。

### 4.5 客户端传入的 id 要校验

`X-Request-ID` 直接进日志 = 日志注入风险（换行、超长、控制字符）。必须白名单：

```python
if incoming and re.fullmatch(r"[A-Za-z0-9-]{1,64}", incoming):
    trace_id = incoming
```

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 用全局变量存 trace_id | 并发串（实测）| `ContextVar` | 实测 |
| `set` 在 `call_next` 之后 | 端点读不到 | 之前 set | 实测 |
| 忘 `reset(token)` | 上下文泄漏 | `finally` reset | 实测 |
| 每次请求新建 `ContextVar` | 不传播 | 模块级单例 | `[T1]` |
| `Formatter` 用 `%(trace_id)s` 但无 Filter | `KeyError` | 加 Filter | `[T2]` |
| 用 `threading.local` | async 下串 | `contextvars` | `[T1]` |
| 客户端 id 不校验 | 日志注入 | 正则白名单 | `[T3]` |
| 日志打 token/密码 | 泄露 | 脱敏 | `[T3]` |
| 用 `print` | 无级别/格式 | `logging` | `[T2]` |
| 后台任务异常不记 | 静默失败 | try/except + log | 实测 |
| 多进程用自增 id | 冲突 | uuid/雪花 | `[T3]` |
| trace_id 当幂等键 | 语义错 | 独立幂等键 | `[T3]` |
| 只在 access log 里记 | 缺业务上下文 | 业务日志也带 | `[T2]` |
| `reset` 传错 token | 恢复到错误值 | 保存 `set` 的返回值 | `[T1]` |
| 子 task 里 `set` 想回传 | 外层看不到 | 用返回值/队列 | `[T1]` |
| 日志里 `f"{trace_id}"` 拼接 | 格式不一 | formatter 统一 | `[T2]` |
| 忘记设置 logger 的 `propagate` | 重复输出 | 显式设置 | `[T2]` |
| 只测单请求 | 并发问题漏测 | `asyncio.gather` | 第 71 章 |
| 拿 trace_id 当日志去重键 | 同请求多条日志被误合并 | 另加序号/时间戳 | `[T2]` |

## 6. 最佳实践与编码建议

### 6.1 结构化日志

```python
import json
import logging


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        return json.dumps(
            {
                "ts": self.formatTime(record, "%Y-%m-%dT%H:%M:%S%z"),
                "level": record.levelname,
                "trace_id": getattr(record, "trace_id", "-"),
                "logger": record.name,
                "msg": record.getMessage(),
            },
            ensure_ascii=False,
        )
```

| 建议 | 说明 |
| --- | --- |
| 字段固定 | 便于采集 |
| `trace_id` 必有 | 串联 |
| 时间用 ISO8601 | 时区明确 |
| 不打业务敏感值 | 规则 |

### 6.2 接入 W3C traceparent

如果要接 OpenTelemetry，用 `traceparent` 头而不是自造 `X-Request-ID`：

```text
traceparent: 00-<trace-id:32hex>-<span-id:16hex>-01
```

本章只做自造 id，接 OTel 需要额外依赖，未实现。

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[T1]` | 文档 | https://docs.python.org/3/library/contextvars.html | `ContextVar` 语义 |
| `[T2]` | 文档 | https://docs.python.org/3/library/logging.html#logging.Filter | Filter 与 format |
| `[T3]` | 指南 | https://cheatsheetseries.owasp.org/cheatsheets/Logging_Cheat_Sheet.html | 日志安全 |

> **核对状态**：`[T1]`–`[T3]` 为官方文档/指南链接，**本次未逐页直连复核**；生成/透传、state 一致、请求后 reset、日志带 id、嵌套可读、后台任务、并发隔离与日志不串、兜底 `-` 均为本机实测，`examples/verify.py` 复现 11/11 通过。OTel 接入、多进程、日志采集**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 全局变量为什么在 async 下会串
- [ ] `ContextVar` 的隔离单位
- [ ] `set` 为什么必须在 `call_next` 之前
- [ ] `reset(token)` 的作用
- [ ] `request.state` 与 `ContextVar` 的分工

**能写出（代码层）**：

- [ ] 中间件生成/透传 id
- [ ] `TraceFilter` + formatter
- [ ] 依赖里 `get()`
- [ ] `finally: reset(token)`
- [ ] 并发验证脚本

**能判断（避坑层）**：

- [ ] 看到全局变量 → 指出并发串
- [ ] 看到 `set` 在 `call_next` 后 → 指出读不到
- [ ] 看到 `%(trace_id)s` 无 Filter → 指出 KeyError
- [ ] 看到客户端 id 直用 → 指出注入
- [ ] 看到 `threading.local` → 指出 async 失效

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 11/11
- [ ] `curl -i -H "X-Request-ID: abc" /work`
- [ ] 看服务端日志里的 `[abc]`

## 9. 下一章衔接

第 53 章 `性能中间件`：`GZipMiddleware` 的 `minimum_size` 与压缩比、`TrustedHostMiddleware` 的 Host 白名单与 `www_redirect`，以及「压缩对已压缩内容无益」「Host 校验挡不住 IP 直连」这类边界。

本章留下的伏笔：

1. 中间件顺序（50）→ GZip 要在最外层之一。
2. `Vary` 头（51）→ 压缩也要 `Vary: Accept-Encoding`。
3. 日志里的 `trace_id`（52）在 53 章的请求里继续用。