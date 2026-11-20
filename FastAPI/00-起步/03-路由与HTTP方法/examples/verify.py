"""第 03 章 · 自动验收。运行：python verify.py

注意：本脚本会真的增删内存里的 DB，所以断言顺序是刻意安排的。
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def check_precise_before_param() -> str:
    """`/items/latest` 必须命中精确路由，而不是被 `{item_id}` 吃掉。"""
    r = client.get("/items/latest")
    assert r.status_code == 200, r.text
    assert r.json() == {"latest": "苹果"}, r.json()
    return f"200 {r.json()}"


def check_path_param_conversion() -> str:
    """`/items/1` 命中路径参数，且 item_id 被转成 int。"""
    r = client.get("/items/1")
    assert r.status_code == 200, r.text
    assert r.json()["id"] == 1 and isinstance(r.json()["id"], int), r.json()
    return f"200 {r.json()}"


def check_param_type_error() -> str:
    """`/items/abc` 是 422 而不是 404：路径匹配成功但类型转换失败。"""
    r = client.get("/items/abc")
    assert r.status_code == 422, r.status_code
    assert r.json()["detail"][0]["loc"] == ["path", "item_id"], r.json()
    return f"422 {r.json()['detail'][0]['type']}"


def check_methods() -> str:
    """四种方法都必须命中各自函数。"""
    assert client.post("/items", params={"name": "橘子"}).status_code == 201
    assert client.put("/items/2", params={"name": "葡萄"}).status_code == 200
    assert client.patch("/items/2", params={"name": "西瓜"}).status_code == 200
    assert client.patch("/items/1").json()["name"] == "苹果"  # 未传 name 保持原值
    return "POST 201 / PUT 200 / PATCH 200"


def check_405_and_allow() -> str:
    """用 GET 请求只有 POST 的路径，必须 405 且带 Allow 头。"""
    r = client.put("/items")
    assert r.status_code == 405, r.status_code
    assert r.headers.get("allow"), dict(r.headers)
    return f"405 allow={r.headers['allow']}"


def check_head_not_auto() -> str:
    """`@app.get` 不隐含 HEAD。"""
    assert client.head("/items").status_code == 405
    # 而 api_route 显式声明后可 HEAD
    assert client.head("/health").status_code == 200
    return "GET-only 路径 HEAD=405；api_route 路径 HEAD=200"


def check_204_no_body() -> str:
    """DELETE 返回 204 且响应体为空。"""
    r = client.delete("/items/2")
    assert r.status_code == 204, r.status_code
    assert r.text == "", repr(r.text)
    return "204 body=''"


def check_path_converter() -> str:
    """`:path` 转换器能跨斜杠。"""
    r = client.get("/files/a/b/c.txt")
    assert r.json() == {"path": "a/b/c.txt"}, r.json()
    return r.json()["path"]


def check_hidden_route() -> str:
    """隐藏路由可访问但不在 openapi 里。"""
    assert client.get("/internal/debug").status_code == 200
    paths = client.get("/openapi.json").json()["paths"]
    assert "/internal/debug" not in paths, sorted(paths)
    return f"可达但 openapi 无此项（共 {len(paths)} 条路径）"


def check_url_path_for() -> str:
    """反向解析：函数名 → 实际路径。"""
    assert main.app.url_path_for("get_item", item_id=9) == "/items/9"
    assert main.app.url_path_for("health") == "/health"
    return "/items/9"


def check_routes_table() -> str:
    """路由表里应包含内置文档路由 + 本章路由。"""
    paths = [getattr(r, "path", None) for r in main.app.routes]
    for expected in ("/openapi.json", "/docs", "/redoc", "/items/{item_id}", "/health"):
        assert expected in paths, (expected, paths)
    return f"{len(paths)} 条路由"


CHECKS = [
    ("精确路径优先", check_precise_before_param),
    ("路径参数类型转换", check_path_param_conversion),
    ("类型不合法返回 422", check_param_type_error),
    ("四种方法各自命中", check_methods),
    ("错误方法 405 + Allow", check_405_and_allow),
    ("HEAD 不自动支持", check_head_not_auto),
    ("204 无响应体", check_204_no_body),
    ("路径转换器 :path", check_path_converter),
    ("include_in_schema=False", check_hidden_route),
    ("url_path_for 反向解析", check_url_path_for),
    ("路由表完整性", check_routes_table),
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
