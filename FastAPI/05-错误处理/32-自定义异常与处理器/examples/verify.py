"""第 32 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, Request  # noqa: E402
from fastapi.responses import JSONResponse  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)
strict = TestClient(main.app, raise_server_exceptions=False)


def check_order_not_found() -> str:
    """具体处理器接管：404 + hint。"""
    r = client.get("/orders/99")
    assert r.status_code == 404, (r.status_code, r.text)
    body = r.json()
    assert body["code"] == "ORDER_NOT_FOUND", body
    assert body["hint"].startswith("GET /orders"), body
    assert body["path"] == "/orders/99", body
    return f'code={body["code"]}, hint 存在'


def check_200_ok() -> str:
    """正常路径不受处理器影响。"""
    r = client.get("/orders/1")
    assert r.status_code == 200, r.text
    assert r.json()["sku"] == "KB-01", r.json()
    return "200 KB-01"


def check_conflict() -> str:
    """409 走父类处理器。"""
    r = client.post("/orders", params={"sku": "KB-01"})
    assert r.status_code == 409, (r.status_code, r.text)
    body = r.json()
    assert body["code"] == "DUPLICATE_ORDER", body
    assert "path" in body, body
    return f'code={body["code"]}'


def check_extra_fields() -> str:
    """402 带业务字段（required/balance）。"""
    r = client.post("/pay", params={"username": "alice", "amount": 99999})
    assert r.status_code == 402, (r.status_code, r.text)
    body = r.json()
    assert body["code"] == "INSUFFICIENT_BALANCE", body
    assert body["required"] == 99999 and body["balance"] == 10000, body
    assert "还需 89999 分" in body["message"], body
    return f'required={body["required"]}, balance={body["balance"]}'


def check_pay_ok() -> str:
    """余额足够则正常扣款。"""
    r = client.post("/pay", params={"username": "alice", "amount": 500})
    assert r.status_code == 200, r.text
    assert r.json()["balance"] == 9500, r.json()
    return "balance=9500"


def check_dependency_exception() -> str:
    """依赖里抛业务异常：同样被接管。"""
    r = client.post("/orders/secure", params={"sku": "X"})
    assert r.status_code == 403, (r.status_code, r.text)
    assert r.json()["code"] == "FORBIDDEN_SCOPE", r.json()
    ok = client.post(
        "/orders/secure",
        params={"sku": "X"},
        headers={"X-Scope": "orders:write"},
    )
    assert ok.status_code == 200, ok.text
    return "403 → 带 scope 后 200"


def check_bad_handler_return() -> str:
    """反例：处理器返回 dict → 500。"""
    r = strict.get("/bad-handler")
    assert r.status_code == 500, (r.status_code, r.text)
    return f"返回 dict → {r.status_code}"


def check_handler_raising() -> str:
    """反例：处理器内部抛异常 → 500。"""
    r = strict.get("/exploding")
    assert r.status_code == 500, (r.status_code, r.text)
    assert "RuntimeError" not in r.text, r.text
    return "处理器内抛错 → 500（原始信息不泄露）"


def check_unhandled_not_caught_by_app_error() -> str:
    """普通异常不会被业务异常处理器捕获。"""
    probe = FastAPI()

    @probe.exception_handler(main.AppError)
    async def handler(request: Request, exc: main.AppError) -> JSONResponse:  # noqa: ANN202
        return JSONResponse(status_code=418, content={"code": "caught"})

    @probe.get("/x")
    def x() -> dict[str, str]:  # noqa: ANN202
        raise ValueError("不是业务异常")

    r = TestClient(probe, raise_server_exceptions=False).get("/x")
    assert r.status_code == 500, (r.status_code, r.text)
    return "ValueError → 500，不被 AppError 处理器接住"


def check_handler_resolution_priority() -> str:
    """异常类越具体越优先；注册顺序不影响。"""

    class Base(Exception):
        pass

    class Child(Base):
        pass

    probe = FastAPI()

    @probe.exception_handler(Child)
    async def child_handler(request: Request, exc: Child) -> JSONResponse:
        return JSONResponse(status_code=400, content={"who": "child"})

    @probe.exception_handler(Base)
    async def base_handler(request: Request, exc: Base) -> JSONResponse:
        return JSONResponse(status_code=400, content={"who": "base"})

    @probe.get("/child")
    def raise_child() -> None:
        raise Child()

    @probe.get("/base")
    def raise_base() -> None:
        raise Base()

    c = TestClient(probe)
    assert c.get("/child").json() == {"who": "child"}, c.get("/child").json()
    assert c.get("/base").json() == {"who": "base"}, c.get("/base").json()
    return "Child → child 处理器；Base → base 处理器"


def check_exception_handler_decorator_registers() -> str:
    """装饰器等价于 add_exception_handler。"""
    probe = FastAPI()

    class Boom(Exception):
        pass

    @probe.get("/boom")
    def boom() -> None:
        raise Boom()

    async def handler(request: Request, exc: Boom) -> JSONResponse:
        return JSONResponse(status_code=418, content={"code": "teapot"})

    probe.add_exception_handler(Boom, handler)
    r = TestClient(probe).get("/boom")
    assert r.status_code == 418, (r.status_code, r.text)
    assert r.json() == {"code": "teapot"}, r.json()
    return "add_exception_handler 生效（418）"


def check_handler_can_read_request() -> str:
    """处理器可读取请求信息（路径、头、查询串）。"""
    probe = FastAPI()

    class Trace(Exception):
        pass

    @probe.exception_handler(Trace)
    async def handler(request: Request, exc: Trace) -> JSONResponse:
        return JSONResponse(
            status_code=400,
            content={
                "path": request.url.path,
                "q": request.query_params.get("q"),
                "ua": request.headers.get("user-agent", ""),
            },
        )

    @probe.get("/trace")
    def trace() -> None:
        raise Trace()

    r = TestClient(probe).get("/trace?q=hello", headers={"User-Agent": "verify/1.0"})
    body = r.json()
    assert body["path"] == "/trace", body
    assert body["q"] == "hello", body
    assert body["ua"] == "verify/1.0", body
    return "处理器拿到 path/query/header"


def check_response_structure_consistent() -> str:
    """所有业务异常的响应结构字段一致（code/message/path）。"""
    responses = [
        client.get("/orders/99"),
        client.post("/orders", params={"sku": "KB-01"}),
        client.post("/pay", params={"username": "alice", "amount": 999999}),
    ]
    codes = [r.status_code for r in responses]
    assert codes == [404, 409, 402], codes
    for r in responses:
        assert {"code", "message", "path"} <= set(r.json()), r.json()
    return f"状态码={codes}，结构一致"


CHECKS = [
    ("具体处理器 404", check_order_not_found),
    ("200 正常", check_200_ok),
    ("409 父类处理器", check_conflict),
    ("业务字段透传", check_extra_fields),
    ("余额足够", check_pay_ok),
    ("依赖抛业务异常", check_dependency_exception),
    ("处理器返回 dict", check_bad_handler_return),
    ("处理器内抛异常", check_handler_raising),
    ("普通异常不被捕获", check_unhandled_not_caught_by_app_error),
    ("处理器优先级", check_handler_resolution_priority),
    ("add_exception_handler", check_exception_handler_decorator_registers),
    ("处理器读请求", check_handler_can_read_request),
    ("响应结构一致", check_response_structure_consistent),
]


def run() -> int:
    failures = 0
    for name, func in CHECKS:
        try:
            print(f"[PASS] {name} -> {func()}")
        except AssertionError as exc:
            failures += 1
            print(f"[FAIL] {name} -> {exc}")
    print(f"\n结果：{len(CHECKS) - failures}/{len(CHECKS)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())