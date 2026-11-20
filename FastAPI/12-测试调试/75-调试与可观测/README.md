# 75 调试与可观测

## 一句话结论

按性价比排序就三件事：**每请求一行结构化日志**（方法/路径/状态/耗时）、**请求 ID 从入口透传到响应头与日志**、**把 `openapi()` 当契约快照**。实测：响应头带 8 位 `X-Request-ID`，客户端传 `trace-42` 会被沿用；耗时 ≥ 50ms 的请求日志升级为 `WARNING`（`/slow` 实测 102ms → WARNING），快请求是 `INFO`；异常被中间件兜住 → 500 + body 里也有 `request_id` + `LOGGER.exception` 记 ERROR。反例实测：`FastAPI(debug=True)` 会把 **3699 字节的 traceback 直接返回给客户端**，生产绝对不能开。

## 最小可运行案例

```python
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

logger = logging.getLogger("app.request")
app = FastAPI()


@app.middleware("http")
async def observe(request: Request, call_next):
    request_id = request.headers.get("x-request-id") or uuid.uuid4().hex[:8]
    started = time.perf_counter()

    try:
        response = await call_next(request)
    except Exception:
        logger.exception("request failed path=%s", request.url.path,
                         extra={"request_id": request_id})
        response = JSONResponse(
            {"detail": "internal server error", "request_id": request_id},
            status_code=500,
        )

    elapsed = (time.perf_counter() - started) * 1000
    response.headers["X-Request-ID"] = request_id
    response.headers["X-Elapsed-Ms"] = f"{elapsed:.2f}"
    logger.log(
        logging.WARNING if elapsed >= 50 else logging.INFO,
        "request method=%s path=%s status=%s elapsed_ms=%.2f",
        request.method, request.url.path, response.status_code, elapsed,
        extra={"request_id": request_id},
    )
    return response
```

## 怎么跑

```powershell
cd "12-测试调试\75-调试与可观测\examples"
uv sync
uv run python verify.py
uv run pytest -q
```

预期输出：

```text
[PASS] 请求 ID -> dbdfd26f
[PASS] ID 透传 -> trace-42
[PASS] 耗时头 -> 1.66ms
[PASS] 一行日志 -> method/path/status 齐全
[PASS] 日志关联 ID -> trace-42 出现在日志
[PASS] 慢请求 WARNING -> WARNING / request method=GET path=/slow ...
[PASS] 快请求 INFO -> INFO
[PASS] 500 带 ID -> baa8dfea
[PASS] 500 记 ERROR -> request failed method=GET path=/boom ...
[PASS] debug 泄露 traceback -> 暴露 3699 字节
[PASS] 生产隐藏细节 -> 只有通用错误信息
[PASS] 404 正常 -> 404 / not here
[PASS] 契约路径 -> 5 条
[PASS] 契约 operationId -> 5 个
[PASS] summary 齐全 -> 5 个 operation 全有
[PASS] 密码脱敏 -> password → ***

结果：16/16 通过
```

`pytest -q` 另外 10 个用例全绿（stderr 里的 traceback 是 `logger.exception` 的预期输出）。

## 核心 API 速查

| 手段 | 用法 |
| --- | --- |
| 中间件 | `@app.middleware("http")` |
| 请求 ID | `request.headers.get("x-request-id") or uuid4().hex[:8]` |
| 结构化字段 | `extra={"request_id": rid}` |
| 分级 | `logger.log(level, ...)` |
| 异常 | `logger.exception(...)` / `logger.error(..., exc_info=True)` |
| 测试日志 | `caplog.set_level(...)` |
| 契约快照 | 断言 `sorted(openapi()["paths"])` 与 `operationId` |
| 生产调试 | `debug=False`（默认）|

| 实测 | 值 |
| --- | --- |
| 自动请求 ID | 8 位 hex |
| 透传 `trace-42` | 响应头一致 |
| 快请求 | `INFO` / 1.66ms |
| `/slow` | `WARNING` / 102ms |
| `/boom` | 500 + body `request_id` == 响应头 |
| 异常日志 | `ERROR` |
| `debug=True` | body 含 `Traceback`，3699 字节 |
| `debug=False` | 无 `Traceback`、无内部文案 |
| 契约 | 5 路径 / 5 operationId |
| 密码 | 日志里 `hunter2` 不出现，`***` 出现 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 生产开 `debug=True` | 源码/traceback 泄露 | 默认关闭 |
| 日志打完整请求体 | 密码进日志 | 白名单脱敏 |
| 只打 `print` | 无级别、无关联 | `logging` |
| 日志里没有请求 ID | 无法串联 | `extra` |
| 中间件里不捕获异常 | 500 没有请求 ID | `try/except` + 兜底响应 |
| 用 `logger.error` 不带堆栈 | 查不到现场 | `logger.exception` |
| 日志写到文件 | 容器里丢失 | stdout |
| 时间用秒 | 精度不够 | 毫秒 |
| 阈值硬编码 | 环境不同 | 配置化 |
| 断言 `capsys` 文本 | 脆弱 | `caplog` |
| `caplog` 没设级别 | 捕不到 INFO | `set_level` |
| 契约变更无人知 | 前端突然坏 | 快照断言 + review |
| 只断路径不断 operationId | 改名漏检 | 两个都断 |
| `summary` 缺失 | 文档不可读 | 强制检查 |
| 中间件顺序错 | 拿不到真实耗时 | 靠外层 |
| `request.state` 未初始化就用 | AttributeError | 中间件里先赋值 |
| 日志重复输出 | 多 handler | 统一配置 |
| 只测 happy path | 500 无人管 | 补异常用例 |

## 毕业自查

- [ ] 能写请求 ID 中间件
- [ ] 能打出一行含方法/路径/状态/耗时的日志
- [ ] 能用 `caplog` 断言日志
- [ ] 能解释 `debug=True` 的风险
- [ ] 能做 openapi 契约快照
- [ ] 动手题一：把耗时阈值改成从环境变量读
- [ ] 动手题二：给日志加 `%(request_id)s` formatter

> 想看 `logging` 层级与 handler、uvicorn 日志接管、结构化 JSON 日志、trace/span、18 条坑，继续读 [`base.md`](./base.md)。