"""第 12 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path
from typing import Annotated

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import Cookie, FastAPI, Header, Path as PathParam, Query, Request  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def check_four_locations() -> str:
    """路径 + 查询 + 头 + Cookie 同时生效。"""
    r = client.get(
        "/summary/7?q=hello",
        headers={"X-Token": "tk"},
        cookies={"sid": "s1"},
    )
    assert r.status_code == 200, r.text
    assert r.json()["typed"] == {"item_id": 7, "q": "hello", "x_token": "tk", "sid": "s1"}, r.json()
    return str(r.json()["typed"])


def check_raw_vs_typed() -> str:
    """raw 侧永远是字符串，typed 侧已转成 int。"""
    data = client.get("/summary/7").json()
    assert data["typed"]["item_id"] == 7, data
    assert data["raw"]["path_params"] == {"item_id": "7"}, data
    return f'typed={data["typed"]["item_id"]!r} / raw={data["raw"]["path_params"]!r}'


def check_openapi_in() -> str:
    """OpenAPI 的 in 有四种取值，路径参数恒为 required=true。"""
    schema = client.get("/openapi.json").json()
    params = schema["paths"]["/summary/{item_id}"]["get"]["parameters"]
    got = {(p["name"], p["in"], p["required"]) for p in params}
    expected = {
        ("item_id", "path", True),
        ("q", "query", False),
        ("x-token", "header", False),
        ("sid", "cookie", False),
    }
    assert got == expected, got
    # Request 参数不进 OpenAPI
    assert "request" not in {p["name"] for p in params}, params
    return "path/query/header/cookie 四种 in 齐全，request 未出现"


def check_same_name_four_locations() -> str:
    """四类参数同名，各取各的，不存在覆盖。"""
    r = client.get(
        "/conflict/pathval?q=queryval",
        headers={"q": "headerval"},
        cookies={"q": "cookieval"},
    )
    assert r.status_code == 200, r.text
    assert r.json() == {
        "path": "pathval",
        "query": "queryval",
        "header": "headerval",
        "cookie": "cookieval",
    }, r.json()
    return str(r.json())


def check_request_bypass() -> str:
    """Request 直取不校验：limit=abc 也 200。"""
    r = client.get("/raw?limit=abc&q=1&q=2")
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["limit_raw"] == "abc", data
    assert data["q_get"] == "2", data
    assert data["q_getlist"] == ["1", "2"], data
    return 'limit_raw="abc" / q_get="2" / getlist=["1","2"]'


def check_path_template_conflicts() -> str:
    """声明位置与路径模板冲突 → 导入期 AssertionError。"""
    messages: list[str] = []

    def build_query_on_path() -> None:
        app = FastAPI()

        @app.get("/b/{item_id}")
        def f(item_id: Annotated[int, Query()]) -> dict[str, int]:
            return {"item_id": item_id}

    def build_header_on_path() -> None:
        app = FastAPI()

        @app.get("/c/{token}")
        def f(token: Annotated[str, Header()]) -> dict[str, str]:
            return {"token": token}

    def build_default_on_path() -> None:
        app = FastAPI()

        @app.get("/d/{item_id}")
        def f(item_id: Annotated[int, PathParam()] = 1) -> dict[str, int]:
            return {"item_id": item_id}

    for name, build in (
        ("Query", build_query_on_path),
        ("Header", build_header_on_path),
        ("default", build_default_on_path),
    ):
        try:
            build()
        except AssertionError as exc:
            messages.append(f"{name}->{exc}")
        else:
            raise AssertionError(f"{name} 场景本应报错，但没有报")

    assert "Cannot use `Query` for path param" in messages[0], messages
    assert "Cannot use `Header` for path param" in messages[1], messages
    assert "Path parameters cannot have default values" in messages[2], messages
    return " | ".join(messages)


def check_ghost_path() -> str:
    """Path() 用在不存在的模板参数上：不报错，但永远 422。"""
    r = client.get("/ghost?x=1")
    assert r.status_code == 422, r.status_code
    item = r.json()["detail"][0]
    assert item["type"] == "missing", item
    assert item["loc"] == ["path", "x"], item
    return f'422 {item["type"]} loc={item["loc"]}'


def check_error_aggregation() -> str:
    """多个参数同时非法 → 一个 422 含多条错误，loc 首段标明来源。"""
    r = client.get("/aggregate/abc?limit=999", headers={"X-Token": "abc"})
    assert r.status_code == 422, r.status_code
    details = r.json()["detail"]
    # 【注意】多条错误的排列顺序是框架内部实现细节（与函数签名顺序无关），
    #       断言时只比较集合，不要绑定顺序。
    locs = {tuple(e["loc"]) for e in details}
    assert locs == {
        ("path", "item_id"),
        ("header", "x-token"),
        ("query", "limit"),
    }, locs
    types = {e["type"] for e in details}
    assert types == {"int_parsing", "string_too_short", "less_than_equal"}, types
    return f"{len(details)} 条错误，loc 覆盖 path/header/query"


def check_request_only_no_openapi() -> str:
    """只声明 Request 时，OpenAPI 里没有 parameters。"""
    app = FastAPI()

    @app.get("/e")
    def e(request: Request) -> dict[str, str]:
        return {"method": request.method}

    c = TestClient(app)
    assert c.get("/e").json() == {"method": "GET"}
    params = c.get("/openapi.json").json()["paths"]["/e"]["get"].get("parameters")
    assert params is None, params
    return "parameters 为空 → 文档上看不到参数"


def check_route_404_vs_422() -> str:
    """路由没匹配是 404；匹配了但类型转换失败是 422。"""
    assert client.get("/summary/abc").status_code == 422, "类型转换失败应 422"
    assert client.get("/summary/abc").json()["detail"][0]["loc"] == ["path", "item_id"]
    assert client.get("/no-such-route").status_code == 404, "无此路由应 404"
    return "类型失败 422（loc=path）；无路由 404"


CHECKS = [
    ("四类参数同时生效", check_four_locations),
    ("raw 与 typed 的差异", check_raw_vs_typed),
    ("OpenAPI 四种 in", check_openapi_in),
    ("同名参数互不干扰", check_same_name_four_locations),
    ("Request 直取不校验", check_request_bypass),
    ("声明位置与模板冲突", check_path_template_conflicts),
    ("幽灵路径参数永远 422", check_ghost_path),
    ("错误聚合", check_error_aggregation),
    ("只声明 Request 无 OpenAPI 参数", check_request_only_no_openapi),
    ("404 与 422 的边界", check_route_404_vs_422),
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
