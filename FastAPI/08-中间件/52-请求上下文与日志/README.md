# 52 请求上下文与日志

## 一句话结论

`trace_id` 要贯穿「中间件 → 依赖 → 业务 → 日志 → 响应头」，靠 `contextvars.ContextVar` 而不是全局变量。实测并发两个请求：`ctx_before` 各自是 `AAA`/`BBB`，而全局变量被覆盖成同一个值。`set()` 必须在 `call_next` **之前**（`BaseHTTPMiddleware` 在 `call_next` 时创建子 task，复制的是当时的 context），请求结束要 `reset(token)` 归还（实测请求后 `get()` 回到 `""`）。

## 最小可运行案例

```python
import logging
import uuid
from contextvars import ContextVar
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Request

app = FastAPI()
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")


class TraceFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get() or "-"
        return True


handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(levelname)s [%(trace_id)s] %(message)s"))
handler.addFilter(TraceFilter())
logger = logging.getLogger("app")
logger.addHandler(handler)
logger.setLevel(logging.INFO)
logger.propagate = False


@app.middleware("http")
async def add_trace_id(request: Request, call_next: Any) -> Any:
    trace_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex[:12]
    token = trace_id_var.set(trace_id)          # 必须在 call_next 之前
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = trace_id
        return response
    finally:
        trace_id_var.reset(token)


def current_trace_id() -> str:
    return trace_id_var.get()


@app.get("/work")
def work(trace_id: Annotated[str, Depends(current_trace_id)]) -> dict[str, str]:
    logger.info("处理中")
    return {"trace_id": trace_id}
```

## 怎么跑

```powershell
cd "08-中间件\52-请求上下文与日志\examples"
uv sync
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 生成 trace_id -> trace_id=33a0e088db35
[PASS] 透传 trace_id -> X-Request-ID: my-123 透传
[PASS] state 与 contextvar 一致 -> trace_id == state == db28c4c00c95
[PASS] 请求后 reset -> 请求后 contextvar == ''
[PASS] 日志带 trace_id -> 4 行日志都带 [423973fa2e41]
[PASS] 嵌套调用可读 -> trace=6c7fd2336de1
[PASS] 后台任务上下文 -> 后台任务读到 d0d51dcad104
[PASS] 并发隔离 -> ctx=AAA/BBB，global 都被覆盖成 BBB
[PASS] 并发日志不串 -> 并发两个请求的日志各带自己的 id
[PASS] 无上下文兜底 -> 无上下文时显示 '-'
[PASS] request.state 可用 -> state-1

结果：11/11 通过
```

## 核心 API 速查

| 对象 | 用法 | 备注 |
| --- | --- | --- |
| `ContextVar("name", default="")` | 模块级单例 | 不要每次请求新建 |
| `.set(v)` | 返回 `token` | 必须保存 |
| `.reset(token)` | 归还上一个值 | `finally` 里做 |
| `.get()` | 读当前上下文 | 无值返回 `default` |
| `logging.Filter` | 注入 `record.trace_id` | format 里用 `%(trace_id)s` |

| 实测行为 | 结果 |
| --- | --- |
| 无入参 | 12 位 hex，响应头回写 |
| 带 `X-Request-ID` | 原样透传 |
| `request.state` | 与 contextvar 一致 |
| 请求结束 | contextvar 回到 `""` |
| 嵌套三层函数 | 直接 `get()` 可用 |
| `BackgroundTasks` | 仍是同一 trace_id |
| 并发两请求 | contextvar 各自正确；全局变量被覆盖 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 用模块级全局变量存 trace_id | 并发互相覆盖 | `ContextVar` |
| 在 `call_next` 之后 `set` | 端点读不到（子 task 已复制 context）| `call_next` 之前 |
| 忘记 `reset(token)` | 上下文污染后续逻辑 | `finally` 里 reset |
| 每次请求新建 `ContextVar` | 失去传播意义 | 模块级单例 |
| 日志 format 直接写 `%(trace_id)s` 但没 filter | `KeyError` | 加 `Filter` |
| 用 `threading.local` | async 下不隔离 | `contextvars` |
| 把 trace_id 拼进 f-string 日志 | 无法统一格式 | `Filter` + format |
| 在 `except` 里 `get()` 拿的是新上下文 | 值可能缺失 | 提前存局部变量 |
| 用 trace_id 当幂等键 | 语义错 | 单独 `Idempotency-Key` |
| 把用户 id 也塞进 trace_id | 泄露 | 只放随机 id |
| 日志里打印 token/密码 | 泄露 | 脱敏 |
| 客户端传的 `X-Request-ID` 不校验 | 注入日志/超长 | 长度+字符白名单 |
| 只记 access log | 缺业务上下文 | 业务日志也带 |
| 多进程下计数器做 id | 冲突 | uuid / 雪花 |
| 用 `print` 代替日志 | 无级别/无格式 | `logging` |
| 后台任务异常不记 | 静默失败 | try/except + log |

## 毕业自查

- [ ] 能写出 `ContextVar` + 中间件 + `Filter` 三件套
- [ ] 能解释为什么 `set` 必须在 `call_next` 之前
- [ ] 能证明并发下不串（用 `asyncio.gather`）
- [ ] 能解释 `reset(token)` 的必要性
- [ ] 能接结构化 JSON 日志
- [ ] 动手题一：把日志换成 `json.dumps` 结构化输出
- [ ] 动手题二：接 OpenTelemetry（`trace_id` 用 W3C 格式）

> 想看 `ContextVar` 与 task 的关系、`BaseHTTPMiddleware` 的 context 传播细节、`contextvars.copy_context()` 在后台任务里的行为、结构化日志方案、18 条坑，继续读 [`base.md`](./base.md)。