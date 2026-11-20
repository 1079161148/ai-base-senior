# 32 自定义异常与处理器

## 一句话结论

业务代码只抛业务异常（`OrderNotFound`），HTTP 映射放在 `@app.exception_handler`。异常类**越具体越优先**（实测：`Child` 命中 child 处理器，与注册顺序无关）。处理器**必须返回 `Response` 实例**——返回 dict 会 500（实测）。处理器内部再抛异常也直接 500，且不会二次进入处理器。

学完这一章，你能：把业务异常与 HTTP 解耦、写多级异常映射、给异常携带业务字段、避开「处理器返回错类型」这类事故。

## 最小可运行案例

```python
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

app = FastAPI()


class AppError(Exception):
    code = "APP_ERROR"
    status_code = 500

    def __init__(self, message: str, **extra: object) -> None:
        super().__init__(message)
        self.message = message
        self.extra = extra


class OrderNotFound(AppError):
    code = "ORDER_NOT_FOUND"
    status_code = 404


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"code": exc.code, "message": exc.message, "path": request.url.path, **exc.extra},
    )


@app.get("/orders/{order_id}")
def get_order(order_id: int) -> dict:
    if order_id != 1:
        raise OrderNotFound(f"订单 {order_id} 不存在")   # 业务层不写 404
    return {"id": 1}
```

完整版本（具体处理器覆盖父类、402 带业务字段、依赖抛错、两个反例）见 `examples/main.py`。

## 怎么跑

```powershell
cd "05-错误处理\32-自定义异常与处理器\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 具体处理器 404 -> code=ORDER_NOT_FOUND, hint 存在
[PASS] 200 正常 -> 200 KB-01
[PASS] 409 父类处理器 -> code=DUPLICATE_ORDER
[PASS] 业务字段透传 -> required=99999, balance=10000
[PASS] 余额足够 -> balance=9500
[PASS] 依赖抛业务异常 -> 403 → 带 scope 后 200
[PASS] 处理器返回 dict -> 返回 dict → 500
[PASS] 处理器内抛异常 -> 处理器内抛错 → 500（原始信息不泄露）
[PASS] 普通异常不被捕获 -> ValueError → 500，不被 AppError 处理器接住
[PASS] 处理器优先级 -> Child → child 处理器；Base → base 处理器
[PASS] add_exception_handler -> add_exception_handler 生效（418）
[PASS] 处理器读请求 -> 处理器拿到 path/query/header
[PASS] 响应结构一致 -> 状态码=[404, 409, 402]，结构一致

结果：13/13 通过
```

## 核心 API 速查

| 写法 | 作用 | 注意 |
| --- | --- | --- |
| `@app.exception_handler(X)` | 注册处理器 | 等价 `add_exception_handler(X, fn)` |
| `async def h(request, exc)` | 处理器签名 | `request` 必填，`exc` 类型要与注册的一致 |
| `return JSONResponse(...)` | 返回响应 | **必须**是 `Response` 子类 |
| `raise BusinessError()` | 业务代码抛错 | 不要 `import fastapi` 到业务层 |
| `Exception` 作注册类型 | 兜底 500 | 第 34 章 |

| 实测行为 | 结果 |
| --- | --- |
| 注册 `AppError` 与 `OrderNotFound` | 抛 `OrderNotFound` 命中更具体的那个 |
| 注册顺序反过来 | 结果不变（按 MRO 查找）|
| 处理器返回 dict | 500（被当响应对象用）|
| 处理器内部抛 `RuntimeError` | 500，body 不含 `RuntimeError` |
| 抛 `ValueError` | 不被 `AppError` 处理器捕获 → 500 |
| 处理器读 `request` | 能拿 path / query / header |
| 依赖里抛业务异常 | 同样被接管 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 处理器 `return dict` | 500，难排查 | `return JSONResponse(...)` |
| 处理器里再抛异常 | 500，原错误被掩盖 | 处理器内只做安全转换 |
| 忘记注册到 `app` | 异常照旧 500 | 装饰器挂 `app`/`router` 所属 app |
| 用 `Exception` 注册却想区分类型 | 全部 500 | 用基类 + 子类分层 |
| 业务层 `raise HTTPException` | HTTP 细节钻进业务 | 自定义异常 |
| 异常类不带 `code` | 客户端只能看文案 | 带稳定 `code` |
| 处理器里做重 IO/查库 | 错误路径变慢、可能再失败 | 只做纯转换 |
| 处理器里 `await` 未加 async | 语法错误 | `async def` |
| 子类忘记继承基类 | 不被兜底 | 统一继承 `AppError` |
| `add_exception_handler` 注册成实例方法 | 签名不匹配 500 | 传函数对象 |
| 处理器里读 body | 已消费/阻塞 | 只读 headers/path |
| 在 `finally` 抛业务异常 | 覆盖原始异常 | 只清理 |

## 毕业自查

- [ ] 能说出「业务异常不 import fastapi」的理由
- [ ] 能写基类 + 2 个子类 + 2 个处理器
- [ ] 能解释处理器优先级规则
- [ ] 能说出处理器返回值必须是 `Response`
- [ ] 能解释处理器内抛异常为什么 500
- [ ] 能在依赖里抛业务异常
- [ ] 动手题一：加 `RateLimited`（429），用异常字段带 `retry_after`
- [ ] 动手题二：把 `AppError` 换成 `dataclass`，保持行为不变

> 想看 Starlette 的处理器查找逻辑（MRO + `_lookup_exception_handler`）、`ExceptionMiddleware` 与 `ServerErrorMiddleware` 的分工、18 条坑，继续读 [`base.md`](./base.md)。