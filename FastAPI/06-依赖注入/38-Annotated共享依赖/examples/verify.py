"""第 38 章 · 自动验收。运行：python verify.py"""

import sys
import types
import typing
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from typing import Annotated  # noqa: E402

from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def openapi_params(path: str) -> list[str]:
    schema = client.get("/openapi.json").json()
    return [p["name"] for p in schema["paths"][path]["get"].get("parameters", [])]


def check_alias_expands_to_params() -> str:
    """别名展开成分页参数。"""
    r = client.get("/items", params={"skip": 2, "limit": 4})
    assert r.status_code == 200, (r.status_code, r.text)
    assert r.json()["count"] == 4, r.json()
    assert openapi_params("/items") == ["q", "skip", "limit"], openapi_params("/items")
    return "别名 → q/skip/limit"


def check_alias_reused() -> str:
    """两个端点共用同一别名。"""
    a = openapi_params("/items")
    b = openapi_params("/users")
    assert a == b == ["q", "skip", "limit"], (a, b)
    return "两个端点参数一致"


def check_is_type_alias_type() -> str:
    """`type X = ...` 生成 TypeAliasType（不是普通对象）。"""
    assert isinstance(main.CommonsDep, types.GenericAlias) is False
    assert type(main.CommonsDep).__name__ == "TypeAliasType", type(main.CommonsDep).__name__
    assert main.CommonsDep.__value__ is not None
    return f"CommonsDep 类型 = {type(main.CommonsDep).__name__}"


def check_alias_value_contains_depends() -> str:
    """别名的 `__value__` 是 `Annotated[T, Depends(...)]`。"""
    origin = typing.get_origin(main.CommonsDep.__value__)
    assert origin is Annotated, origin
    args = typing.get_args(main.CommonsDep.__value__)
    assert args[0] is main.CommonQueryParams, args[0]
    assert len(args) >= 2 and type(args[1]).__name__ == "Depends", args[1]
    return "value = Annotated[CommonQueryParams, Depends(...)]"


def check_runtime_type_is_dict() -> str:
    """运行时端点拿到的仍是真实对象/值。"""
    r = client.get("/me", params={"detail": "true"}, headers={"X-User": "alice"})
    assert r.status_code == 200, r.text
    assert r.json() == {"name": "alice", "role": "admin"}, r.json()
    return "UserDep → dict"


def check_user_401() -> str:
    """UserDep 缺头 → 401。"""
    r = client.get("/me")
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.headers["www-authenticate"] == "Bearer", dict(r.headers)
    return "401 + challenge"


def check_nested_alias() -> str:
    """AdminDep 内部复用 get_user，403 由 require_admin 抛。"""
    r = client.get("/admin", headers={"X-User": "bob"})
    assert r.status_code == 403, (r.status_code, r.text)
    ok = client.get("/admin", headers={"X-User": "alice"})
    assert ok.status_code == 200 and ok.json() == {"admin": "alice"}, ok.text
    return "bob→403, alice→200"


def check_alias_plus_own_param() -> str:
    """别名与自己的参数共存。"""
    r = client.get("/me", headers={"X-User": "alice"})
    assert r.json() == {"name": "alice"}, r.json()
    params = openapi_params("/me")
    # 【注意】顺序是「query 在前、header 在后」，不要按源码顺序断言
    assert set(params) == {"X-User", "detail"}, params
    return f"parameters={params}"


def check_depends_on_alias_fails() -> str:
    """`Depends(别名)` 不可用：别名不是可调用对象。"""
    probe = FastAPI()
    error = ""

    try:

        @probe.get("/bad")
        def bad(value: Annotated[object, Depends(main.CommonsDep)]) -> dict[str, str]:  # noqa: ANN202
            return {}

        TestClient(probe).get("/bad")

    except Exception as exc:  # noqa: BLE001
        error = f"{type(exc).__name__}: {str(exc)[:50]}"
    assert error, "Depends(别名) 应当失败"
    return error


def check_equivalent_to_inline() -> str:
    """别名与内联写法产生同样的 OpenAPI 与行为。"""
    probe = FastAPI()

    from fastapi import Query

    def dep(
        n: Annotated[int, Query(ge=1, le=5)] = 1,
    ) -> int:
        return n

    type DepAlias = Annotated[int, Depends(dep)]

    @probe.get("/alias")
    def alias_route(value: DepAlias) -> dict[str, int]:
        return {"v": value}

    @probe.get("/inline")
    def inline_route(value: Annotated[int, Depends(dep)]) -> dict[str, int]:
        return {"v": value}

    c = TestClient(probe)
    schema = c.get("/openapi.json").json()
    pa = schema["paths"]["/alias"]["get"]["parameters"]
    pi = schema["paths"]["/inline"]["get"]["parameters"]
    assert pa == pi, (pa, pi)
    assert c.get("/alias", params={"n": 3}).json() == {"v": 3}
    return "别名与内联 OpenAPI 完全一致"


def check_alias_in_module_scope_importable() -> str:
    """别名可在模块间 import 复用（这里验证可被引用）。"""
    from main import CommonsDep as Imported

    assert Imported is main.CommonsDep, (Imported, main.CommonsDep)
    return "from main import CommonsDep 可用"


CHECKS = [
    ("别名展开参数", check_alias_expands_to_params),
    ("别名复用", check_alias_reused),
    ("TypeAliasType", check_is_type_alias_type),
    ("__value__ 结构", check_alias_value_contains_depends),
    ("运行时真实类型", check_runtime_type_is_dict),
    ("401", check_user_401),
    ("嵌套别名", check_nested_alias),
    ("别名 + 自有参数", check_alias_plus_own_param),
    ("Depends(别名) 失败", check_depends_on_alias_fails),
    ("与内联等价", check_equivalent_to_inline),
    ("跨模块引用", check_alias_in_module_scope_importable),
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