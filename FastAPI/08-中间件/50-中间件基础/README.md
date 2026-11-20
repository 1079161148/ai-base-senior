# 50 中间件基础

## 一句话结论

`@app.middleware("http")` + `await call_next(request)` 把代码包在**路由之外**，所以 404、`/docs`、`/openapi.json`、422 全都会经过它——这正是全局依赖做不到的（第 39 章实测全局依赖对 404 不触发）。多个中间件是洋葱模型，且**后注册的在最外层**（实测：`outer` 最后注册，最先执行、最后退出）。

五个实测要点：

1. 完整序列：`outer:before → middle:before → inner:before → inner:after → middle:after → outer:after`。
2. 端点里只能看到各层 `before`——内层 `after` 在响应回传时才执行。
3. **`HTTPException` 不会进中间件的 `except`**（内层 `ExceptionMiddleware` 已转成响应），只有未捕获的普通异常会冒上来。
4. 异常路径会**跳过所有 `after`**（实测 `/boom` 的 503 响应没有 `X-Order`）。
5. 启动之后再 `add_middleware` → `RuntimeError: Cannot add middleware after an application has started`。

## 最小可运行案例

```python
import time
from typing import Any

from fastapi import FastAPI, Request

app = FastAPI()


@app.middleware("http")
async def add_process_time(request: Request, call_next: Any) -> Any:
    start = time.perf_counter()
    response = await call_next(request)          # 路由在这里执行
    elapsed = (time.perf_counter() - start) * 1000
    response.headers["X-Process-Time"] = f"{elapsed:.2f}ms"
    return response


@app.get("/ping")
def ping() -> dict[str, str]:
    return {"ok": "true"}
```

子类写法等价：

```python
from starlette.middleware.base import BaseHTTPMiddleware


class ServerHeader(BaseHTTPMiddleware):
    def __init__(self, app: Any, name: str = "fastapi") -> None:
        super().__init__(app)
        self.name = name

    async def dispatch(self, request: Request, call_next: Any) -> Any:
        response = await call_next(request)
        response.headers["X-Server-Name"] = self.name
        return response


app.add_middleware(ServerHeader, name="fastapi-ch50")
```

## 怎么跑

```powershell
cd "08-中间件\50-中间件基础\examples"
uv sync
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 端点看到 before -> order=['outer:before', 'middle:before', 'inner:before']
[PASS] 响应头完整序列 -> X-Order=outer:before,middle:before,inner:before,inner:after,middle:after,outer:after
[PASS] 后注册在外层 -> outer(后注册) 最先执行、最后退出
[PASS] 耗时头 -> X-Process-Time=22.144ms
[PASS] 子类中间件 -> X-Server-Name=fastapi-ch50
[PASS] 404 走中间件 -> 404 带 X-Process-Time / X-Server-Name / X-Order
[PASS] /docs 走中间件 -> /docs 带 X-Process-Time
[PASS] /openapi.json 走中间件 -> /openapi.json 带 X-Process-Time
[PASS] HTTPException 不捕获 -> 418 原样返回，无 X-Caught
[PASS] 未捕获异常兜底 -> 503 + X-Caught=1，无 X-Order（异常路径跳过 after）
[PASS] 422 走中间件 -> 422 带 X-Process-Time
[PASS] 路径重写 -> /alias 命中 /ping
[PASS] 启动后加中间件 -> RuntimeError: Cannot add middleware after an application has started
[PASS] 全局依赖不覆盖 404 -> 全局依赖只跑 1 次（404 不触发），中间件则覆盖 404

结果：14/14 通过
```

## 核心 API 速查

| 写法 | 签名 | 备注 |
| --- | --- | --- |
| 装饰器 | `@app.middleware("http")` | 等价于 `add_middleware(BaseHTTPMiddleware, dispatch=fn)` |
| 函数参数 | `(request: Request, call_next)` | `call_next` 是 async callable |
| 返回值 | 必须返回 `Response` | 忘了 return 会 500 |
| 子类 | `class X(BaseHTTPMiddleware)` + `async def dispatch` | 可带 `__init__` 配置 |

| 执行顺序事实 | 实测 |
| --- | --- |
| 后注册的在外层 | ✅ |
| 请求由外向内 | ✅ |
| 响应由内向外 | ✅ |
| 404 / `/docs` / `/openapi.json` 都经过 | ✅ |
| 422 经过 | ✅ |
| `HTTPException` 不进 `except` | ✅ |
| 异常时 `after` 全部跳过 | ✅ |
| 启动后 `add_middleware` | `RuntimeError` |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 忘记 `return response` | 500 / 空响应 | 每层都要 return |
| 以为先注册的在外层 | 顺序全反 | 后注册的在外层 |
| 在中间件里 `except Exception` 想抓 `HTTPException` | 抓不到 | 用 `@app.exception_handler` |
| 在中间件里 `await request.body()` | 下游读不到 body（流被消费）|
| 用中间件做鉴权 | `/docs` 也被拦、难覆盖测试 | 用依赖（第 44 章）|
| 在 `call_next` 之后改 `response.body` | 不生效（已开始流式发送）| 在 `call_next` 之前用依赖改 |
| 中间件里存全局变量 | 并发串数据 | `request.state` / contextvars（第 52 章）|
| 启动后才 `add_middleware` | `RuntimeError` | 模块加载期注册 |
| 中间件顺序依赖业务含义却没注释 | 排错困难 | 注释层级 |
| 中间件抛异常未处理 | 500 且无 `call_next` 清理 | 最外层兜底 |

## 毕业自查

- [ ] 能写出耗时中间件并加响应头
- [ ] 能说出洋葱顺序与注册顺序的关系
- [ ] 能解释为什么 404 也带中间件头
- [ ] 能解释 `HTTPException` 为什么不进 `except`
- [ ] 知道中间件与全局依赖的分工边界
- [ ] 动手题一：加一个「只对 `/api` 前缀生效」的中间件
- [ ] 动手题二：把 `TRACE` 换成 `contextvars`（第 52 章）

> 想看 `BaseHTTPMiddleware` 的实现代价、`call_next` 的流式语义、`request.state` 的生命周期、中间件 vs 依赖的选择树、18 条坑，继续读 [`base.md`](./base.md)。