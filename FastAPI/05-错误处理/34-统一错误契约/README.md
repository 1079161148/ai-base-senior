# 34 统一错误契约（全局兜底 + trace_id）

## 一句话结论

四条失败路径——框架 404/405、`HTTPException`、业务异常、`RequestValidationError`——加上未捕获异常兜底，全部收敛成 `{code, message, trace_id}`（可选 `details`），响应头回写 `X-Trace-Id`。客户端只认一种结构；排障时拿 `trace_id` 在日志里串链路。实测：客户端传 `X-Request-Id` 会被沿用；不传则每次生成 32 位 uuid4；未捕获异常 → 500 且 body 不含堆栈。

学完这一章，你能：写出「所有错误长得一样」的应用、把 trace 打通到日志、避开「兜底处理器没记日志」这类盲区。

## 最小可运行案例

```python
import logging
import uuid
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()
logger = logging.getLogger("app.errors")


def error_response(request: Request, status_code: int, code: str, message: str,
                   details: Any = None, headers: dict[str, str] | None = None) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None) or uuid.uuid4().hex
    content: dict[str, Any] = {"code": code, "message": message, "trace_id": trace_id}
    if details is not None:
        content["details"] = details
    return JSONResponse(
        status_code=status_code,
        content=content,
        headers={**(headers or {}), "X-Trace-Id": trace_id},
    )


@app.middleware("http")
async def trace_id_middleware(request: Request, call_next):
    trace_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
    request.state.trace_id = trace_id
    response = await call_next(request)
    response.headers["X-Trace-Id"] = trace_id
    return response


@app.exception_handler(Exception)
async def unhandled(request: Request, exc: Exception) -> JSONResponse:
    logger.exception("unhandled error", extra={"trace_id": getattr(request.state, "trace_id", None)})
    return error_response(request, 500, "INTERNAL_ERROR", "服务器内部错误")
```

完整版本（四条路径 + 405 + 日志断言）见 `examples/main.py`。

## 怎么跑

```powershell
cd "05-错误处理\34-统一错误契约\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 路由 404 统一结构 -> 404 code=NOT_FOUND, trace_id=55a81863…
[PASS] HTTPException 统一结构 -> 401 code=UNAUTHORIZED
[PASS] 业务异常统一结构 -> details={'order_id': 99}
[PASS] 校验错误统一结构 -> code=VALIDATION_ERROR, field=age
[PASS] 未捕获 500 统一结构 -> 500 code=INTERNAL_ERROR，无堆栈泄露
[PASS] X-Trace-Id 响应头 -> header == body == 2ceb82e8…
[PASS] 沿用客户端 id -> 沿用客户端 trace_id=abc123
[PASS] trace_id 唯一 -> 3 次请求 3 个不同 id（长度 32）
[PASS] 字段集合一致 -> 5 条路径都是 {code, message, trace_id} + 可选 details
[PASS] 405 统一结构 -> 405 code=METHOD_NOT_ALLOWED
[PASS] 日志可串 trace_id -> 日志命中 1 条 trace_id=trace-for-log

结果：11/11 通过
```

> 直接 `uvicorn` 启动时，`/crash` 会在服务端日志打印完整堆栈——那是 `logger.exception` 的功劳，给运维看，不给客户端。

## 核心 API 速查

| 路径 | 注册的处理器 | 产出 `code` |
| --- | --- | --- |
| 路由不存在 / 方法不允许 | `StarletteHTTPException` | `NOT_FOUND` / `METHOD_NOT_ALLOWED` |
| `raise HTTPException(401)` | 同上 | `UNAUTHORIZED` |
| 业务异常 | `AppError` | 异常类自带 `code` |
| 参数校验失败 | `RequestValidationError` | `VALIDATION_ERROR` |
| 未捕获异常 | `Exception` | `INTERNAL_ERROR` |

| 字段 | 说明 |
| --- | --- |
| `code` | 稳定机器码，前端按它分支 |
| `message` | 可给用户看的文案 |
| `trace_id` | 32 位 hex，或沿用客户端 `X-Request-Id` |
| `details` | 可选，字段级错误/业务附加信息 |

| 实测行为 | 结果 |
| --- | --- |
| 客户端传 `X-Request-Id: abc123` | body 与响应头都用 `abc123` |
| 不传 | 每次请求新 uuid4（32 位）|
| 未捕获异常 | 500，body 无 `RuntimeError`、无原始 message |
| `HTTPException` 自带的 headers | 保留（如 `WWW-Authenticate`）|
| 405 | 也走统一结构，`Allow` 头保留 |
| 日志 | `trace_id` 可作过滤键 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 兜底处理器不记日志 | 500 无法排查 | `logger.exception` |
| 兜底处理器回显 `str(exc)` | 泄露内部信息 | 固定文案 + 日志 |
| 中间件顺序反了 | 处理器读不到 `trace_id` | 先生成再 `call_next` |
| `request.state` 用属性赋值前没初始化 | 处理器 `AttributeError` | 用 `getattr(..., None)` 兜底 |
| 各处理器字段名不一致 | 前端要写多套解析 | 统一走 `error_response()` |
| 只统一 4xx 不统一 5xx | 500 还是默认格式 | 加 `Exception` 处理器 |
| `X-Trace-Id` 只放 body | 网关日志取不到 | 头 + body 都带 |
| 沿用客户端 id 却不校验格式 | 日志注入 | 白名单字符/长度 |
| 校验错误直接 `detail` 套壳 | 结构与其他不一致 | 塞进 `details` |
| 修改 `HTTPException` 的 headers 结构 | 丢失协议头 | 合并后统一输出 |
| 处理器里再抛异常 | 又变默认 500 | 处理器内只做纯转换 |
| 以为文档会自动展示新契约 | OpenAPI 仍是默认结构 | 手动改 schema |
| 日志里打整个 body | 密码入日志 | 只打 code/path/trace_id |
| `trace_id` 不传给下游服务 | 跨服务断链 | 出站请求带上 |

## 毕业自查

- [ ] 能列出四条错误路径与对应处理器
- [ ] 能写出统一的 `error_response()`
- [ ] 能解释 `trace_id` 的生成/沿用/回写
- [ ] 能说明为什么兜底处理器必须记日志
- [ ] 能说出「字段集合一致」怎么验证
- [ ] 能说明文档不会自动同步
- [ ] 动手题一：把 `trace_id` 加进每条业务日志（不只在错误路径）
- [ ] 动手题二：给 `details` 加 `request_id`/`service` 元信息

> 想看四条路径的优先级、`ExceptionMiddleware` 与 `ServerErrorMiddleware` 的分工、trace 传播、18 条坑，继续读 [`base.md`](./base.md)。