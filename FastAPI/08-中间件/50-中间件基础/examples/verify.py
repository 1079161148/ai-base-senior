"""第 50 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)
SAFE = TestClient(main.app, raise_server_exceptions=False)


def check_order_body() -> str:
    """端点里只看到各层 before。"""
    body = client.get("/ping").json()
    assert body["order"] == ["outer:before", "middle:before", "inner:before"], body["order"]
    return f'order={body["order"]}'


def check_order_header() -> str:
    """响应头拿到完整洋葱序列。"""
    order = client.get("/ping").headers["x-order"].split(",")
    assert order == [
        "outer:before",
        "middle:before",
        "inner:before",
        "inner:after",
        "middle:after",
        "outer:after",
    ], order
    return f"X-Order={','.join(order)}"


def check_later_registered_is_outer() -> str:
    """后注册的在最外层（实测，与不少教程的写法相反）。"""
    order = client.get("/ping").headers["x-order"].split(",")
    assert order[0] == "outer:before", order
    assert order[-1] == "outer:after", order
    assert order.index("middle:before") < order.index("inner:before"), order
    return "outer(后注册) 最先执行、最后退出"


def check_process_time_header() -> str:
    """耗时头存在且带单位。"""
    value = client.get("/slow").headers["x-process-time"]
    assert value.endswith("ms"), value
    return f"X-Process-Time={value}"


def check_server_header() -> str:
    """`BaseHTTPMiddleware` 子类生效。"""
    assert client.get("/ping").headers["x-server-name"] == "fastapi-ch50"
    return "X-Server-Name=fastapi-ch50"


def check_404_passes_middleware() -> str:
    """404 也走中间件（这是与全局依赖的关键差异）。"""
    r = client.get("/nope")
    assert r.status_code == 404, r.status_code
    for header in ("x-process-time", "x-server-name", "x-order"):
        assert header in r.headers, (header, dict(r.headers))
    return "404 带 X-Process-Time / X-Server-Name / X-Order"


def check_docs_passes_middleware() -> str:
    """/docs 也走中间件。"""
    r = client.get("/docs")
    assert r.status_code == 200
    assert "x-process-time" in r.headers, dict(r.headers)
    return "/docs 带 X-Process-Time"


def check_openapi_passes_middleware() -> str:
    """/openapi.json 也走中间件。"""
    r = client.get("/openapi.json")
    assert r.status_code == 200
    assert "x-process-time" in r.headers
    return "/openapi.json 带 X-Process-Time"


def check_http_exception_not_caught() -> str:
    """`HTTPException` 不进中间件的 `except`。"""
    r = client.get("/http-error")
    assert r.status_code == 418, (r.status_code, r.text)
    assert r.json() == {"detail": "我是茶壶"}, r.json()
    assert "x-caught" not in r.headers, dict(r.headers)
    return "418 原样返回，无 X-Caught"


def check_uncaught_exception_caught() -> str:
    """未捕获异常 → 中间件兜底 503；且外层 after 未执行（无 X-Order）。"""
    r = SAFE.get("/boom")
    assert r.status_code == 503, (r.status_code, r.text)
    assert r.json()["detail"] == "被中间件捕获：数据库连接失败", r.json()
    assert r.headers["x-caught"] == "1", dict(r.headers)
    assert "x-order" not in r.headers, dict(r.headers)
    return "503 + X-Caught=1，无 X-Order（异常路径跳过 after）"


def check_422_passes_middleware() -> str:
    """校验失败 422 也走中间件。"""
    r = client.get("/need-header")
    assert r.status_code == 422, (r.status_code, r.text)
    assert "x-process-time" in r.headers
    return "422 带 X-Process-Time"


def check_path_rewrite() -> str:
    """改 `scope["path"]` 会改变路由命中（`/alias` → `/ping`）。"""
    r = client.get("/alias")
    assert r.status_code == 200, (r.status_code, r.text)
    assert r.json()["order"] == ["outer:before", "middle:before", "inner:before"], r.json()
    return "/alias 命中 /ping"


def check_add_middleware_after_start() -> str:
    """启动后再 `add_middleware` → RuntimeError。"""
    late = FastAPI()

    @late.get("/x")
    def x() -> dict[str, str]:
        return {"x": "1"}

    TestClient(late).get("/x")  # 触发中间件栈构建

    class Noop(BaseHTTPMiddleware):
        async def dispatch(self, request, call_next):  # noqa: ANN001, ANN201
            return await call_next(request)

    error = ""
    try:
        late.add_middleware(Noop)
    except RuntimeError as exc:
        error = str(exc)
    assert "has started" in error, error
    return f"RuntimeError: {error}"


def check_global_dep_does_not_cover_404() -> str:
    """对比：全局依赖对 404 不生效，中间件生效。"""
    hits: list[str] = []

    def probe() -> None:
        hits.append("probe")

    other = FastAPI(dependencies=[Depends(probe)])

    @other.get("/ok")
    def ok() -> dict[str, str]:
        return {"ok": "1"}

    c = TestClient(other)
    assert c.get("/ok").status_code == 200
    assert hits == ["probe"], hits
    assert c.get("/nope").status_code == 404
    assert hits == ["probe"], hits
    return "全局依赖只跑 1 次（404 不触发），中间件则覆盖 404"


CHECKS = [
    ("端点看到 before", check_order_body),
    ("响应头完整序列", check_order_header),
    ("后注册在外层", check_later_registered_is_outer),
    ("耗时头", check_process_time_header),
    ("子类中间件", check_server_header),
    ("404 走中间件", check_404_passes_middleware),
    ("/docs 走中间件", check_docs_passes_middleware),
    ("/openapi.json 走中间件", check_openapi_passes_middleware),
    ("HTTPException 不捕获", check_http_exception_not_caught),
    ("未捕获异常兜底", check_uncaught_exception_caught),
    ("422 走中间件", check_422_passes_middleware),
    ("路径重写", check_path_rewrite),
    ("启动后加中间件", check_add_middleware_after_start),
    ("全局依赖不覆盖 404", check_global_dep_does_not_cover_404),
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