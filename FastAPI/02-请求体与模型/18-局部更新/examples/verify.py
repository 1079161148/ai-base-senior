"""第 18 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def reset() -> None:
    main._PRODUCTS[1] = {"id": 1, "name": "机械键盘", "price": 399.0, "tags": ["数码"], "note": "原装备注"}


def patch(payload: dict, product_id: int = 1) -> object:
    return client.patch(f"/products/{product_id}", json=payload)


def first_error(r) -> dict:
    assert r.status_code == 422, (r.status_code, r.text)
    return r.json()["detail"][0]


def check_only_given_field() -> str:
    """只传一个字段：其他字段原样保留。"""
    reset()
    r = patch({"name": "静音键盘"})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["updates"] == {"name": "静音键盘"}, data
    assert data["product"]["price"] == 399.0, data
    assert data["product"]["tags"] == ["数码"], data
    return f'updates={data["updates"]}，price/tags 未变'


def check_explicit_null() -> str:
    """显式传 null：保留在 updates 里，实现「清空字段」。"""
    reset()
    r = patch({"note": None})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["updates"] == {"note": None}, data
    assert data["product"]["note"] is None, data
    return 'updates={"note": None}'


def check_exclude_none_differs() -> str:
    """exclude_none 会把显式的 null 也丢掉，语义与 exclude_unset 不同。"""
    reset()
    payload = main.ProductPatch(note=None)
    assert payload.model_dump(exclude_unset=True) == {"note": None}, "exclude_unset 保留 null"
    assert payload.model_dump(exclude_none=True) == {}, "exclude_none 丢掉 null"
    return "exclude_unset→{'note': None}；exclude_none→{}"


def check_unset_not_in_updates() -> str:
    """未出现的字段不会进 updates。"""
    reset()
    data = patch({"price": 299}).json()
    assert data["fields_set"] == ["price"], data
    assert "name" not in data["updates"], data
    return 'fields_set=["price"]'


def check_empty_patch() -> str:
    """空对象：合法，updates 为空，什么都不改。"""
    reset()
    r = patch({})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["updates"] == {}, data
    assert data["product"]["name"] == "机械键盘", data
    return "空对象 200，updates={}"


def check_optional_still_validated() -> str:
    """可选字段传了值仍然校验。"""
    reset()
    err = first_error(patch({"name": "笔"}))
    assert err["type"] == "string_too_short", err
    assert err["loc"] == ["body", "name"], err

    err = first_error(patch({"price": 0}))
    assert err["type"] == "greater_than", err
    return "name='笔' → string_too_short；price=0 → greater_than"


def check_extra_forbidden() -> str:
    """拼错字段名：422，而不是静默忽略。"""
    reset()
    err = first_error(patch({"nmae": "x"}))
    assert err["type"] == "extra_forbidden", err
    assert err["loc"] == ["body", "nmae"], err
    return f'loc={err["loc"]}'


def check_unknown_product() -> str:
    """不存在的商品：404，不是 422。"""
    r = patch({"name": "x" * 3}, product_id=999)
    assert r.status_code == 404, r.status_code
    assert r.json()["detail"] == "商品 999 不存在", r.json()
    return "404"


def check_fields_set_is_readonly_snapshot() -> str:
    """model_dump 不会改变 fields_set（v2 行为），可安全多次读取。"""
    reset()
    p = main.ProductPatch(name="A1", price=1.0)
    before = set(p.model_fields_set)
    p.model_dump()
    p.model_dump(exclude_unset=True)
    assert set(p.model_fields_set) == before == {"name", "price"}, p.model_fields_set
    return f"fields_set={sorted(before)}，多次 dump 后不变"


def check_openapi_patch() -> str:
    """OpenAPI：PATCH 的 requestBody 里没有必填字段。"""
    schema = client.get("/openapi.json").json()
    body = schema["paths"]["/products/{product_id}"]["patch"]["requestBody"]
    ref = body["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
    model = schema["components"]["schemas"][ref]
    assert "required" not in model, model
    assert model["additionalProperties"] is False, model
    return "PATCH 无 required，additionalProperties=false"


CHECKS = [
    ("只更新传入字段", check_only_given_field),
    ("显式 null 置空", check_explicit_null),
    ("exclude_none 语义不同", check_exclude_none_differs),
    ("未传字段不进 updates", check_unset_not_in_updates),
    ("空对象合法", check_empty_patch),
    ("可选字段仍校验", check_optional_still_validated),
    ("多余字段被拒", check_extra_forbidden),
    ("未知商品 404", check_unknown_product),
    ("fields_set 不被 dump 改变", check_fields_set_is_readonly_snapshot),
    ("OpenAPI 无 required", check_openapi_patch),
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
