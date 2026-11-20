"""第 71 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402


def reset() -> None:
    main.ITEMS.clear()
    main.ITEMS[1] = {"id": 1, "name": "键盘", "price": 19900}
    main.STATE.update(next_id=2, started=False)


def client(**kwargs) -> TestClient:
    reset()
    return TestClient(main.app, **kwargs)


def check_create_201() -> str:
    """成功路径：201 + 精确 body。"""
    with client() as c:
        response = c.post("/items", json={"name": "鼠标", "price": 9900})
    assert response.status_code == 201, response.status_code
    assert response.json() == {"id": 2, "name": "鼠标", "price": 9900}, response.json()
    return "201 / id=2"


def check_list_200() -> str:
    """列表：200 + 条数。"""
    with client() as c:
        response = c.get("/items")
    assert response.status_code == 200, response.status_code
    assert len(response.json()) == 1, response.json()
    return "200 / 1 条"


def check_read_200() -> str:
    """详情：200 + 字段。"""
    with client() as c:
        body = c.get("/items/1").json()
    assert body["name"] == "键盘", body
    return body["name"]


def check_404_detail() -> str:
    """不存在：404 + detail 文案。"""
    with client() as c:
        response = c.get("/items/999")
    assert response.status_code == 404, response.status_code
    assert response.json()["detail"] == "item not found", response.json()
    return "404 / item not found"


def check_422_body_errors() -> str:
    """body 非法：422 + 两个错误的 type/loc。"""
    with client() as c:
        response = c.post("/items", json={"name": "", "price": -1})
    assert response.status_code == 422, response.status_code
    errors = response.json()["detail"]
    types = {error["type"] for error in errors}
    locs = {tuple(error["loc"]) for error in errors}
    assert types == {"string_too_short", "greater_than_equal"}, types
    assert locs == {("body", "name"), ("body", "price")}, locs
    return "string_too_short + greater_than_equal"


def check_422_query_range() -> str:
    """query 越界：422 greater_than_equal。"""
    with client() as c:
        response = c.get("/items", params={"limit": 0})
    assert response.status_code == 422, response.status_code
    assert response.json()["detail"][0]["loc"] == ["query", "limit"], response.json()
    return "limit=0 → 422"


def check_422_query_type() -> str:
    """query 类型错：422 int_parsing。"""
    with client() as c:
        response = c.get("/items", params={"limit": "abc"})
    assert response.status_code == 422, response.status_code
    assert response.json()["detail"][0]["type"] == "int_parsing", response.json()
    return "limit=abc → int_parsing"


def check_content_type() -> str:
    """响应头：application/json。"""
    with client() as c:
        response = c.get("/items")
    assert response.headers["content-type"] == "application/json", response.headers
    return response.headers["content-type"]


def check_redirect_followed() -> str:
    """默认跟随 307 → 200。"""
    with client() as c:
        response = c.get("/redirect")
    assert response.status_code == 200, response.status_code
    assert response.url.path == "/items", response.url
    return "307 → 200"


def check_redirect_not_followed() -> str:
    """`follow_redirects=False` → 307 + location。"""
    with client(follow_redirects=False) as c:
        response = c.get("/redirect")
    assert response.status_code == 307, response.status_code
    assert response.headers["location"] == "/items", response.headers
    return "307 / location=/items"


def check_cookie_persists() -> str:
    """cookie 在同一个 client 内保持。"""
    with client() as c:
        c.cookies.set("session", "abc123")
        body = c.get("/cookie/read").json()
    assert body == {"session": "abc123"}, body
    return "session=abc123"


def check_lifespan_not_run() -> str:
    """不用 `with`：lifespan 未执行。"""
    c = client()
    body = c.get("/state").json()
    assert body == {"started": False}, body
    return "started=False"


def check_lifespan_runs() -> str:
    """`with` 内：lifespan 已执行。"""
    with client() as c:
        body = c.get("/state").json()
    assert body == {"started": True}, body
    return "started=True"


def check_strict_raises() -> str:
    """默认把服务端异常抛出。"""
    try:
        with client() as c:
            c.get("/boom")
    except RuntimeError as exc:
        assert "故意炸了" in str(exc), exc
        return str(exc)
    raise AssertionError("异常被吞了")


def check_lenient_500() -> str:
    """宽松模式：500 可断言。"""
    with client(raise_server_exceptions=False) as c:
        response = c.get("/boom")
    assert response.status_code == 500, response.status_code
    return "500 Internal Server Error"


def check_request_echo() -> str:
    """`response.request` 能反查方法与完整 URL。"""
    with client() as c:
        response = c.get("/items/1")
    assert response.request.method == "GET", response.request.method
    assert str(response.request.url) == "http://testserver/items/1", response.request.url
    return "GET http://testserver/items/1"


CHECKS = [
    ("创建 201", check_create_201),
    ("列表 200", check_list_200),
    ("详情 200", check_read_200),
    ("404 detail", check_404_detail),
    ("422 body", check_422_body_errors),
    ("422 query 范围", check_422_query_range),
    ("422 query 类型", check_422_query_type),
    ("content-type", check_content_type),
    ("跟随重定向", check_redirect_followed),
    ("不跟随重定向", check_redirect_not_followed),
    ("cookie 保持", check_cookie_persists),
    ("无 with 不跑 lifespan", check_lifespan_not_run),
    ("with 跑 lifespan", check_lifespan_runs),
    ("严格模式抛异常", check_strict_raises),
    ("宽松模式 500", check_lenient_500),
    ("request 反查", check_request_echo),
]


def run() -> int:
    failures = 0
    for name, func in CHECKS:
        try:
            print(f"[PASS] {name} -> {func()}")
        except Exception as exc:  # noqa: BLE001 - 验收脚本要报告任何失败
            failures += 1
            print(f"[FAIL] {name} -> {type(exc).__name__}: {exc}")
    print(f"\n结果：{len(CHECKS) - failures}/{len(CHECKS)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())