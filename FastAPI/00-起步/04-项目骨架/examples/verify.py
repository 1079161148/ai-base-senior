"""第 04 章 · 自动验收。运行：python verify.py

验证的是「骨架」而不是接口本身：三层前缀、tags 叠加、工厂函数、包导入。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 【作用】把 examples 目录加入 sys.path，才能 `import shop`
sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

from shop.main import app, create_app  # noqa: E402

client = TestClient(app)


def check_import() -> str:
    """包能被导入，说明目录结构 + __init__.py 正确。"""
    import shop
    import shop.api.v1.router  # noqa: F401

    return f"shop.__version__={shop.__version__}"


def check_three_level_prefix() -> str:
    """三层前缀叠加：/api + /v1 + /items = /api/v1/items。"""
    assert client.get("/api/v1/items").status_code == 200
    assert client.get("/api/v1/items/1").status_code == 200
    assert client.get("/api/v1/users").status_code == 200
    return "/api/v1/items | /api/v1/items/1 | /api/v1/users 均 200"


def check_prefix_is_not_partial() -> str:
    """少了任意一层前缀都必须是 404，证明前缀是拼接而不是任选其一。"""
    for path in ("/v1/items", "/api/items", "/items"):
        r = client.get(path)
        assert r.status_code == 404, (path, r.status_code)
    return "/v1/items /api/items /items 均 404"


def check_health_not_versioned() -> str:
    """/health 挂在根路径，不在 /api/v1 下。"""
    assert client.get("/health").status_code == 200
    assert client.get("/api/v1/health").status_code == 404
    return client.get("/health").json()


def check_tags_merged() -> str:
    """子 router 的 tags 会保留，不会被父级覆盖。"""
    schema = client.get("/openapi.json").json()
    tags = {}
    for path, item in schema["paths"].items():
        for op in item.values():
            tags[path] = op.get("tags")
    assert tags["/api/v1/items"] == ["商品"], tags["/api/v1/items"]
    assert tags["/api/v1/users"] == ["用户"], tags["/api/v1/users"]
    assert tags["/health"] == ["运维"], tags["/health"]
    return f"items={tags['/api/v1/items']} users={tags['/api/v1/users']} health={tags['/health']}"


def check_empty_path_vs_slash() -> str:
    """`@router.get("")` 拼出 /api/v1/items（无尾斜杠）。"""
    assert client.get("/api/v1/items").status_code == 200
    # 带尾斜杠会 307 重定向到无尾斜杠版本
    r = client.get("/api/v1/items/", follow_redirects=False)
    assert r.status_code == 307, r.status_code
    return f"/api/v1/items 200；带尾斜杠 307 -> {r.headers.get('location')}"


def check_precise_path_still_first() -> str:
    """精确路径 /latest 依然优先（第 03 章规则在子 router 内同样生效）。"""
    r = client.get("/api/v1/items/latest")
    assert r.json() == {"latest": "苹果"}, r.json()
    return r.json()


def check_factory_isolation() -> str:
    """工厂函数每次返回新实例，互不影响。"""
    a = create_app()
    b = create_app()
    assert a is not b
    assert a.routes is not b.routes
    return f"create_app() 返回不同实例：{id(a) != id(b)}，路由数 {len(a.routes)}/{len(b.routes)}"


def check_openapi_paths() -> str:
    """OpenAPI 里的路径必须是完整拼接后的。"""
    paths = sorted(client.get("/openapi.json").json()["paths"])
    expected = [
        "/api/v1/items",
        "/api/v1/items/latest",
        "/api/v1/items/{item_id}",
        "/api/v1/users",
        "/api/v1/users/{user_id}",
        "/health",
    ]
    assert paths == expected, paths
    return f"{len(paths)} 条：{paths}"


def check_config_singleton() -> str:
    """配置是模块级单例，重复导入拿到同一个对象。"""
    from shop.core.config import settings
    from shop.core.config import settings as again

    assert settings is again
    assert settings.api_prefix == "/api"
    return f"env={settings.env} api_prefix={settings.api_prefix} debug={settings.debug}"


CHECKS = [
    ("包可导入", check_import),
    ("三层前缀叠加", check_three_level_prefix),
    ("前缀缺一层即 404", check_prefix_is_not_partial),
    ("/health 不版本化", check_health_not_versioned),
    ("tags 随子 router 保留", check_tags_merged),
    ("空前缀 + 尾斜杠 307", check_empty_path_vs_slash),
    ("精确路径仍优先", check_precise_path_still_first),
    ("工厂函数隔离", check_factory_isolation),
    ("OpenAPI 路径完整", check_openapi_paths),
    ("配置单例", check_config_singleton),
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
