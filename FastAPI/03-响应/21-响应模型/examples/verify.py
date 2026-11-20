"""第 21 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)

NEW_USER = {"username": "alice", "password": "secret1", "email": "alice@example.com"}


def create() -> dict:
    r = client.post("/users", json=NEW_USER)
    assert r.status_code == 200, r.text
    return r.json()


def check_whitelist_filter() -> str:
    """响应模型是白名单：多余的敏感字段被丢弃。"""
    data = create()
    assert set(data) == {"username", "email", "nickname"}, data
    assert "password" not in data, data
    assert "hashed_password" not in data, data
    assert "internal_note" not in data, data
    assert "debug" not in data, data
    return f"响应键={sorted(data)}"


def check_openapi_uses_out_schema() -> str:
    """OpenAPI：POST 的 200 响应引用 UserOut，而非 UserIn。"""
    schema = client.get("/openapi.json").json()
    ok = schema["paths"]["/users"]["post"]["responses"]["200"]
    ref = ok["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("/UserOut"), ref

    model = schema["components"]["schemas"]["UserOut"]
    assert set(model["properties"]) == {"username", "email", "nickname"}, model
    # 【注意】只能查 properties，不能查 str(model)：docstring 会进 description
    assert "password" not in model["properties"], model
    return f"200 → {ref.split('/')[-1]}"


def check_response_model_exclude() -> str:
    """response_model_exclude：在出参模型上再减字段。"""
    create()
    data = client.get("/users/1/slim").json()
    assert set(data) == {"username", "nickname"}, data
    return f"排除 email 后={sorted(data)}"


def check_response_model_exclude_unset() -> str:
    """response_model_exclude_unset：没赋值的字段不输出。"""
    create()
    data = client.get("/users/1/partial").json()
    assert data == {"username": "alice"}, data
    return f'只输出已设置字段={data}'


def check_exclude_unset_still_validates() -> str:
    """exclude_unset 不影响校验：必填字段缺失照样 500。"""
    create()
    strict = TestClient(main.app, raise_server_exceptions=False)
    r = strict.get("/users/1/force-strict")
    assert r.status_code == 500, (r.status_code, r.text)
    return "必填字段缺失 → 500（exclude_unset 不能免除校验）"


def check_list_response() -> str:
    """list[UserOut]：列表逐元素过滤。"""
    create()
    rows = client.get("/users").json()
    assert isinstance(rows, list) and rows, rows
    assert set(rows[0]) == {"username", "email", "nickname"}, rows[0]
    return f"{len(rows)} 条，元素键={sorted(rows[0])}"


def check_param_overrides_annotation() -> str:
    """response_model 参数优先于函数返回注解。"""
    create()
    data = client.get("/users/1/priority").json()
    assert data == {"username": "alice"}, data
    return "返回注解 UserOut 被 response_model=TinyOut 覆盖"


def check_from_attributes() -> str:
    """from_attributes=True：从普通对象读字段，Decimal 输出为字符串。"""
    data = client.get("/orders/7").json()
    assert data == {"id": 7, "amount": "19.90", "note": None}, data
    assert "secret_token" not in data, data
    return f'id={data["id"]} amount={data["amount"]!r}'


def check_validation_error_is_500() -> str:
    """响应模型校验失败 → 500（不是 422）。"""
    c = TestClient(main.app, raise_server_exceptions=False)
    r = c.get("/broken")
    assert r.status_code == 500, (r.status_code, r.text)
    assert r.text == "Internal Server Error", r.text
    return "500 Internal Server Error"


def check_openapi_components_count() -> str:
    """入参/出参是两个独立组件，字段集合不同。"""
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    assert set(schemas["UserIn"]["properties"]) == {"username", "password", "email", "nickname"}, schemas["UserIn"]
    assert set(schemas["UserOut"]["properties"]) == {"username", "email", "nickname"}, schemas["UserOut"]
    return "UserIn 4 字段 / UserOut 3 字段"


CHECKS = [
    ("白名单过滤", check_whitelist_filter),
    ("OpenAPI 用出参模型", check_openapi_uses_out_schema),
    ("response_model_exclude", check_response_model_exclude),
    ("response_model_exclude_unset", check_response_model_exclude_unset),
    ("exclude_unset 不免除校验", check_exclude_unset_still_validates),
    ("列表响应", check_list_response),
    ("参数优先于注解", check_param_overrides_annotation),
    ("from_attributes", check_from_attributes),
    ("响应校验失败 500", check_validation_error_is_500),
    ("入出参是两个组件", check_openapi_components_count),
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
