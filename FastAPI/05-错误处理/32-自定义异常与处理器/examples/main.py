"""第 32 章 · 自定义异常与处理器。

核心：业务代码只抛「业务异常」（`OrderNotFound`），不关心 HTTP 状态码；
      `@app.exception_handler(X)` 把异常翻译成响应。这样业务层与 HTTP 层解耦，
      同一种异常换状态码只改一处。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, Request
from fastapi.responses import JSONResponse

app = FastAPI(title="第 32 章 · 自定义异常与处理器", version="0.1.0")


# ============================================================
# 1. 业务异常：只描述「发生了什么」，不含 HTTP 细节
# ============================================================
class AppError(Exception):
    """所有业务异常的基类。

    【为什么】业务层不该 import fastapi，也不该决定 404 还是 409；
               映射规则集中在处理器里，换协议（gRPC/CLI）时业务代码不用动。
    """

    code: str = "APP_ERROR"
    status_code: int = 500

    def __init__(self, message: str, **extra: Any) -> None:
        super().__init__(message)
        self.message = message
        self.extra = extra


class OrderNotFound(AppError):
    code = "ORDER_NOT_FOUND"
    status_code = 404


class DuplicateOrder(AppError):
    code = "DUPLICATE_ORDER"
    status_code = 409


class InsufficientBalance(AppError):
    code = "INSUFFICIENT_BALANCE"
    status_code = 402

    def __init__(self, required: int, balance: int) -> None:
        super().__init__(
            message=f"余额不足，还需 {required - balance} 分",
            required=required,
            balance=balance,
        )


class ForbiddenScope(AppError):
    code = "FORBIDDEN_SCOPE"
    status_code = 403


_ORDERS: dict[int, dict[str, Any]] = {1: {"id": 1, "sku": "KB-01", "amount": 39900}}
_BALANCE = {"alice": 10000}


# ============================================================
# 2. 处理器：异常 → 响应（一个地方翻译，全站生效）
# ============================================================
@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    """【作用】捕获所有 `AppError` 子类，统一成 `{code, message, path, ...}`

    【实测】`raise OrderNotFound("...")` → 404，body 含 `code`/`message`/`path`
    【注意】处理器必须返回 `Response` 实例；返回 dict 会 500（见反例）
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "path": request.url.path,
            **exc.extra,
        },
    )


@app.exception_handler(OrderNotFound)
async def order_not_found_handler(request: Request, exc: OrderNotFound) -> JSONResponse:
    """【作用】更具体的处理器优先于父类（实测）

    【注意】这里额外加了 `hint`；若删掉这个处理器，会命中 `AppError` 那个
    """
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "code": exc.code,
            "message": exc.message,
            "hint": "GET /orders 查看全部订单",
            "path": request.url.path,
        },
    )


# ============================================================
# 3. 业务端点：只抛业务异常
# ============================================================
@app.get("/orders/{order_id}", tags=["业务异常"], summary="订单不存在")
def get_order(order_id: int) -> dict[str, Any]:
    """【作用】抛 `OrderNotFound`，由处理器决定 404 与结构

    【实测】404 `{"code": "ORDER_NOT_FOUND", "hint": "...", ...}`
    """
    order = _ORDERS.get(order_id)
    if order is None:
        raise OrderNotFound(f"订单 {order_id} 不存在")
    return order


@app.post("/orders", status_code=201, tags=["业务异常"], summary="重复下单 409")
def create_order(sku: str) -> dict[str, Any]:
    """【实测】同名 SKU 已存在 → 409 `{"code": "DUPLICATE_ORDER", ...}`"""
    if any(order["sku"] == sku for order in _ORDERS.values()):
        raise DuplicateOrder(f"SKU {sku} 已有在途订单")
    new_id = max(_ORDERS) + 1
    _ORDERS[new_id] = {"id": new_id, "sku": sku, "amount": 0}
    return _ORDERS[new_id]


@app.post("/pay", tags=["业务异常"], summary="余额不足 402")
def pay(username: str, amount: int) -> dict[str, Any]:
    """【实测】402，body 里带 `required`/`balance` 两个业务字段"""
    balance = _BALANCE.get(username, 0)
    if amount > balance:
        raise InsufficientBalance(required=amount, balance=balance)
    _BALANCE[username] = balance - amount
    return {"username": username, "balance": _BALANCE[username]}


# ============================================================
# 4. 依赖里抛业务异常：同样被处理器接管
# ============================================================
def require_scope(scope: Annotated[str | None, Header(alias="X-Scope")] = None) -> str:
    if scope != "orders:write":
        raise ForbiddenScope("缺少 orders:write 权限")
    return scope


@app.post("/orders/secure", tags=["业务异常"], summary="依赖里抛 403")
def secure_create(
    scope: Annotated[str, Depends(require_scope)],
    sku: str,
) -> dict[str, str]:
    """【实测】缺 `X-Scope` → 403，结构与其他业务异常一致"""
    return {"scope": scope, "sku": sku}


# ============================================================
# 5. 反例：处理器返回 dict
# ============================================================
class BadHandlerError(Exception):
    pass


@app.exception_handler(BadHandlerError)
async def bad_handler(request: Request, exc: BadHandlerError) -> dict[str, str]:  # type: ignore[return-value]
    """【反例】处理器返回 dict（不是 Response）

    【实测】Starlette 直接把它当响应对象使用 → 500 `AttributeError`
    【结论】处理器必须 `return JSONResponse(...)` / `PlainTextResponse(...)`
    """
    return {"code": "BAD", "message": "处理器返回值写错了"}


@app.get("/bad-handler", tags=["反例"], summary="处理器返回 dict")
def bad_handler_route() -> dict[str, str]:
    raise BadHandlerError("触发反例")


# ============================================================
# 6. 反例：处理器自己抛异常
# ============================================================
class ExplodingError(Exception):
    pass


@app.exception_handler(ExplodingError)
async def exploding_handler(request: Request, exc: ExplodingError) -> JSONResponse:
    """【反例】处理器内部再抛异常 → 不会再被自己处理，直接 500

    【实测】500，body 为 `Internal Server Error`
    【注意】处理器里的日志/序列化失败会掩盖真实错误
    """
    raise RuntimeError("处理器内部炸了")


@app.get("/exploding", tags=["反例"], summary="处理器内抛异常")
def exploding_route() -> dict[str, str]:
    raise ExplodingError("触发")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)