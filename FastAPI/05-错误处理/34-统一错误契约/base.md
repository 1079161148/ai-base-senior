# 34 统一错误契约 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「四条错误路径怎么收敛、`trace_id` 放在哪、兜底处理器在哪一层、契约怎么测试与演进」拆开。学完这章，你要能交付一个「客户端只写一套解析、运维只看一个 id」的错误体系。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Starlette 1.10.0（本机实测） |
| 前置 | 第 31–33 章（`HTTPException`、自定义异常、校验错误） |
| 覆盖范围 | 统一结构、四条处理器、`trace_id` 中间件、兜底日志、契约测试 |
| 明确不覆盖 | 分布式追踪（OpenTelemetry）、日志采集平台、Sentry 接入 |
| 学完验收 | 能跑通 `verify.py` 11/11、能画出错误路径优先级、能说出契约演进规则 |

## 0. 怎么用这份文件

**依据约定**：`` `[Kn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 为什么要一套契约
2 机制（第 2 节）    → 四条路径在 ASGI 栈里的位置
3 API（第 3 节）     → error_response / 中间件 / 处理器
4 边界（第 4 节）    → trace 传播、敏感信息、文档、演进
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 可交付的模板
```

## 1. 概念：错误契约是「对外 API 的一部分」

| 没有契约 | 有契约 |
| --- | --- |
| 404 是 `{"detail": "..."}` | 都是 `{code, message, trace_id}` |
| 422 是 `{"detail": [...]}` | `details` 里放字段级错误 |
| 500 是纯文本 | 同结构 + `INTERNAL_ERROR` |
| 前端按端点写分支 | 按 `code` 分支 |
| 排障靠时间戳猜 | 按 `trace_id` 查日志 |

契约的价值在**边界一致**：客户端不需要知道「这个错误是框架抛的还是我抛的」。

## 2. 机制：四条路径与优先级

```text
请求
 → trace_id 中间件（最外层之一）
 → 路由匹配失败 → StarletteHTTPException(404/405)
 → 参数校验失败 → RequestValidationError
 → 路由函数 → HTTPException / 业务异常
 → 任何未捕获 Exception → Exception 处理器（ServerErrorMiddleware）
 → 都没接住 → 服务器默认 500
```

| 路径 | 处理器注册类型 | 备注 |
| --- | --- | --- |
| 框架 404/405 | `StarletteHTTPException` | `FastAPI` 的 `HTTPException` 是它的子类，一并覆盖 |
| 业务异常 | 自定义基类（如 `AppError`）| 第 32 章 |
| 校验错误 | `RequestValidationError` | 第 33 章 |
| 兜底 | `Exception` | 必须记日志 |

实测：注册 `Exception` 处理器后，`/crash` 返回 500 JSON 而不是纯文本，且不含堆栈。

## 3. API 逐个拆解

### 3.1 `error_response()`：唯一出口

| 参数 | 说明 |
| --- | --- |
| `request` | 取 `trace_id`、path |
| `status_code` | 由调用方决定 |
| `code` | 稳定机器码 |
| `message` | 用户可读文案 |
| `details` | 可选结构 |
| `headers` | 原样合并（保留 `WWW-Authenticate` 等）|

好处：字段集合只有一处定义，测试可以断言「五条路径字段一致」。

### 3.2 `trace_id` 中间件

```python
trace_id = request.headers.get("X-Request-Id") or uuid.uuid4().hex
request.state.trace_id = trace_id
response = await call_next(request)
response.headers["X-Trace-Id"] = trace_id
```

| 要点 | 说明 |
| --- | --- |
| 先写 state 再 call_next | 处理器才读得到 |
| 沿用客户端 id | 便于跨服务串联 |
| 回写响应头 | 网关/前端能记录 |
| 异常路径 | 处理器自己把 `X-Trace-Id` 写进响应（中间件在异常后拿不到 response）|

### 3.3 处理器映射

| 输入 | 输出 `code` |
| --- | --- |
| 404 | `NOT_FOUND` |
| 405 | `METHOD_NOT_ALLOWED` |
| 401 | `UNAUTHORIZED` |
| 403 | `FORBIDDEN` |
| 409 | `CONFLICT` |
| 429 | `TOO_MANY_REQUESTS` |
| 其他 4xx | `HTTP_<code>` |
| 校验失败 | `VALIDATION_ERROR` |
| 业务异常 | 异常类自带 |
| 未捕获 | `INTERNAL_ERROR` |

## 4. 边界条件

### 4.1 `HTTPException.detail` 是 dict 时

实测：`detail` 为 str 时进 `message`；为 dict 时进 `details`，`message` 用通用文案。这样契约字段类型稳定。

### 4.2 协议头保留（实测）

401 的 `WWW-Authenticate: Bearer`、405 的 `Allow: GET` 都在统一响应里保留。别在包装时丢掉 `exc.headers`。

### 4.3 trace_id 的来源与安全

| 风险 | 处理 |
| --- | --- |
| 客户端传超长/含换行 | 校验 `^[A-Za-z0-9_-]{8,64}$`，不合法就重新生成 |
| 客户端伪造 | 不影响安全，只影响排查；如需可信，用网关注入 |
| 日志注入 | 同上，白名单字符 |

本章示例只做了「沿用」，**未做格式校验**，生产要补。

### 4.4 跨服务传播

出站 HTTP 请求要带上 `X-Request-Id`，否则链路断在第一个调用。**未实测**（需要第二个服务）。

### 4.5 文档

OpenAPI 不会因为处理器变化而更新错误结构（第 33 章实测）。三种处理：

| 方案 | 成本 |
| --- | --- |
| 手动改 `app.openapi()` 注入统一错误 schema | 中 |
| 每个端点写 `responses={4xx: ...}` | 高（重复）|
| 接受不同步 + README 说明 | 低（易误导） |

### 4.6 兜底处理器的边界

| 情况 | 结果 |
| --- | --- |
| 处理器自身抛异常 | 服务器默认 500（同第 32 章）|
| 流式响应已开始 | 无法改状态码，只能断开 |
| 后台任务异常 | 不经过这里（第 31 章）|
| `BaseException`（如 `KeyboardInterrupt`）| 不经过这里 |

### 4.7 契约演进

| 变更 | 兼容性 |
| --- | --- |
| 新增 `details` 字段 | 兼容（可选）|
| 给 `details` 加字段 | 兼容 |
| 改 `code` 值 | **破坏**，要版本化 |
| 改字段名 | 破坏 |
| 改状态码语义 | 破坏 |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 兜底不记日志 | 500 无从排查 | `logger.exception` | 实测 |
| 回显 `str(exc)` | 泄露内部信息 | 固定文案 | `[K3]` |
| 中间件里先 `call_next` 再写 state | 处理器读不到 | 先 state 后调用 | 实测 |
| 各处理器字段不同 | 前端多套解析 | 统一 `error_response` | 实测 |
| 丢 `exc.headers` | 401 challenge 丢失 | 合并 headers | 实测 |
| 只统一 4xx | 500 格式不一致 | 加 `Exception` | 实测 |
| `trace_id` 只在 body | 网关取不到 | 头 + body | `[K2]` |
| 沿用客户端 id 不校验 | 日志注入 | 白名单正则 | `[K3]` |
| 日志打整个 body | 密码入日志 | 只打 code/path/trace | `[K3]` |
| 校验错误套 `detail` | 结构不一致 | 放进 `details` | 第 33 章 |
| 处理器里再抛异常 | 默认 500 | 纯转换 | 第 32 章 |
| 以为文档自动更新 | OpenAPI 仍旧 | 手动改 schema | 第 33 章 |
| `trace_id` 不传下游 | 跨服务断链 | 出站带头 | `[K2]` |
| 用时间戳当 trace_id | 并发重复 | uuid4/雪花 | `[K2]` |
| 兜底处理器里 `await` 外部服务 | 错误响应更慢/再失败 | 只记录 | `[K3]` |
| 契约只在 README 写 | 实现漂移 | 契约测试 | 第 71 章 |
| 每个端点自己拼错误 | 又回到不一致 | 统一构造器 | 实测 |
| 给 500 加 `Retry-After` | 误导客户端重试 | 只在 429/503 用 | `[K1]` |
| 契约里加 `stack`/`exception` 字段 | 泄露内部结构 | 只进服务端日志 | `[K3]` |

## 6. 最佳实践与编码建议

### 6.1 可交付模板

```python
# errors/contract.py
import logging
import re
import uuid

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("app.errors")
_TRACE_RE = re.compile(r"^[A-Za-z0-9_-]{8,64}$")
_CODES = {401: "UNAUTHORIZED", 403: "FORBIDDEN", 404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED",
          409: "CONFLICT", 429: "TOO_MANY_REQUESTS"}


def error_response(request: Request, status_code: int, code: str, message: str,
                   details: object = None, headers: dict[str, str] | None = None) -> JSONResponse:
    trace_id = getattr(request.state, "trace_id", None) or uuid.uuid4().hex
    body: dict[str, object] = {"code": code, "message": message, "trace_id": trace_id}
    if details is not None:
        body["details"] = details
    logger.warning("request failed", extra={"trace_id": trace_id, "code": code,
                                            "status": status_code, "path": request.url.path})
    return JSONResponse(status_code=status_code, content=body,
                        headers={**(headers or {}), "X-Trace-Id": trace_id})


def install_error_contract(app: FastAPI) -> None:
    @app.middleware("http")
    async def trace_id_middleware(request: Request, call_next):  # noqa: ANN001, ANN201
        incoming = request.headers.get("X-Request-Id", "")
        request.state.trace_id = incoming if _TRACE_RE.match(incoming) else uuid.uuid4().hex
        response = await call_next(request)
        response.headers["X-Trace-Id"] = request.state.trace_id
        return response

    @app.exception_handler(StarletteHTTPException)
    async def on_http(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        code = _CODES.get(exc.status_code, f"HTTP_{exc.status_code}")
        if isinstance(exc.detail, str):
            return error_response(request, exc.status_code, code, exc.detail, headers=exc.headers)
        return error_response(request, exc.status_code, code, "请求失败",
                              details=exc.detail, headers=exc.headers)

    @app.exception_handler(Exception)
    async def on_unhandled(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("unhandled error", extra={"trace_id": getattr(request.state, "trace_id", None)})
        return error_response(request, 500, "INTERNAL_ERROR", "服务器内部错误，请携带 trace_id 联系支持")
```

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 唯一构造器 | 字段集合只有一处 |
| `code` 常量化 | 便于前端枚举 |
| `trace_id` 校验格式 | 防注入 |
| 兜底必记日志 | 带 trace_id |
| 日志只记元信息 | 不打 body |
| 契约测试 | 五条路径字段一致 |
| 文档显式声明 | 或明确不声明 |

### 6.3 选型速查

| 需求 | 做法 |
| --- | --- |
| 小项目 | 只用 `HTTPException`（第 31 章）|
| 业务复杂 | 加自定义异常（第 32 章）|
| 前端要字段级 | 加校验处理器（第 33 章）|
| 对外 API | 统一契约 + trace_id（本章）|
| 多服务 | 加 OpenTelemetry（未覆盖）|

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[K1]` | 规范 | https://www.rfc-editor.org/rfc/rfc9110#section-15 | 状态码头要求 |
| `[K2]` | 参考 | https://www.w3.org/TR/trace-context/ | trace 传播约定 |
| `[K3]` | 安全指南 | https://owasp.org/www-community/Improper_Error_Handling | 错误信息泄露 |

> **核对状态**：`[K1]`–`[K3]` 为规范/参考/安全链接，**本次未逐页直连复核**；四条路径统一、`trace_id` 沿用/生成/回写、协议头保留、500 无堆栈、405 统一、日志可串 trace_id 均为本机实测，`examples/verify.py` 复现 11/11 通过。跨服务传播、OpenTelemetry、文档注入**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 四条错误路径与优先级
- [ ] 为什么要有唯一构造器
- [ ] `trace_id` 的三个来源与回写位置
- [ ] 兜底处理器在哪一层、能接住什么
- [ ] 契约演进哪些是破坏性变更

**能写出（代码层）**：

- [ ] `error_response()` 统一构造
- [ ] trace_id 中间件（含格式校验）
- [ ] 四个处理器
- [ ] 兜底日志
- [ ] 五条路径字段一致性测试

**能判断（避坑层）**：

- [ ] 看到兜底不记日志 → 指出无法排查
- [ ] 看到回显异常 → 指出泄露
- [ ] 看到丢 `exc.headers` → 指出协议头丢失
- [ ] 看到 trace_id 不校验 → 指出注入
- [ ] 看到文档未同步 → 指出契约不一致

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 11/11
- [ ] `curl -i` 看 `X-Trace-Id`
- [ ] 用同一 `X-Request-Id` 调多次，看日志串联

## 9. 下一章衔接

M05 结束（31–34）。下一模块 M06 `依赖注入`（35–43，9 章，官方重点）：`Depends` 起步、类依赖、子依赖与缓存、`Annotated` 别名、装饰器与全局依赖、`yield` 依赖、`dependency_overrides`、分页与鉴权实战。

本章留下的伏笔：

1. 依赖里抛异常如何影响契约 → 第 35 章起反复出现。
2. `trace_id` 进日志体系 → 第 50 章。
3. 契约测试 → 第 71 章。
4. 依赖覆盖做测试 → 第 41 章。