"""第 15 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)

OK = {
    "customer": {"name": "张三", "address": {"city": "北京", "street": "长安街"}},
    "items": [{"sku": "A-1", "qty": 2, "price": 9.9}],
}


def post(payload: dict) -> object:
    return client.post("/orders", json=payload)


def first_error(r) -> dict:
    assert r.status_code == 422, (r.status_code, r.text)
    return r.json()["detail"][0]


def check_valid() -> str:
    """合法请求：递归转换 + 汇总计算。"""
    r = post(OK)
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["first_item_type"] == "OrderItem", data
    assert data["item_count"] == 1, data
    assert data["total"] == 19.8, data
    assert data["dump"]["customer"]["address"]["city"] == "北京", data
    return f'item=OrderItem total={data["total"]}'


def check_nested_missing() -> str:
    """两层嵌套缺字段：loc 五段。"""
    payload = {
        **OK,
        "customer": {"name": "张三", "address": {"city": "北京"}},
    }
    err = first_error(post(payload))
    assert err["type"] == "missing", err
    assert err["loc"] == ["body", "customer", "address", "street"], err
    return f'loc={err["loc"]}'


def check_list_index_loc() -> str:
    """列表元素缺字段：loc 里出现整数下标。"""
    err = first_error(post({**OK, "items": [{"sku": "A-1", "qty": 2}]}))
    assert err["type"] == "missing", err
    assert err["loc"] == ["body", "items", 0, "price"], err
    assert isinstance(err["loc"][2], int), err
    return f'loc={err["loc"]}（0 是整数下标）'


def check_element_constraint() -> str:
    """元素内部约束：错误定位到具体元素的具体字段。"""
    err = first_error(post({**OK, "items": [{"sku": "A-1", "qty": 0, "price": 1}]}))
    assert err["type"] == "greater_than_equal", err
    assert err["loc"] == ["body", "items", 0, "qty"], err
    assert err["ctx"] == {"ge": 1}, err
    return f'loc={err["loc"]} ctx={err["ctx"]}'


def check_element_not_object() -> str:
    """元素传字符串：错误停在元素这一层，不再往下。"""
    err = first_error(post({**OK, "items": ["A-1"]}))
    assert err["type"] == "model_attributes_type", err
    assert err["loc"] == ["body", "items", 0], err
    assert err["input"] == "A-1", err
    return f'loc={err["loc"]}'


def check_empty_list() -> str:
    """空列表违反 min_length=1，ctx 带 actual_length。"""
    err = first_error(post({**OK, "items": []}))
    assert err["type"] == "too_short", err
    assert err["loc"] == ["body", "items"], err
    assert err["ctx"]["min_length"] == 1 and err["ctx"]["actual_length"] == 0, err
    return f'too_short actual_length={err["ctx"]["actual_length"]}'


def check_inner_extra_ignored() -> str:
    """内层模型默认 ignore：外层 forbid 不会传递下去。"""
    payload = {**OK, "items": [{"sku": "A-1", "qty": 1, "price": 1, "hack": 1}]}
    r = post(payload)
    assert r.status_code == 200, r.text
    assert "hack" not in r.json()["dump"]["items"][0], r.json()
    return "200，内层 hack 被静默丢弃"


def check_outer_extra_forbidden() -> str:
    """外层 forbid 只作用于外层字段。"""
    err = first_error(post({**OK, "hack": 1}))
    assert err["type"] == "extra_forbidden", err
    assert err["loc"] == ["body", "hack"], err
    return f'loc={err["loc"]}'


def check_list_type() -> str:
    """把对象当列表传：list_type。"""
    err = first_error(post({**OK, "items": {"sku": "A-1", "qty": 1, "price": 1}}))
    assert err["type"] == "list_type", err
    assert err["loc"] == ["body", "items"], err
    return f'list_type loc={err["loc"]}'


def check_deep_aggregation() -> str:
    """多层同时出错：一个 422 里各层错误都在。"""
    payload = {**OK, "customer": {"address": {"city": "北京"}}}
    r = post(payload)
    assert r.status_code == 422, r.status_code
    locs = {tuple(e["loc"]) for e in r.json()["detail"]}
    assert locs == {
        ("body", "customer", "name"),
        ("body", "customer", "address", "street"),
    }, locs
    return f"{len(locs)} 条错误，分别定位到不同层级"


def check_openapi_refs() -> str:
    """OpenAPI：嵌套结构用 $ref，各模型独立成组件。"""
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    order = schemas["Order"]
    assert order["properties"]["customer"] == {"$ref": "#/components/schemas/Customer"}, order
    assert order["properties"]["items"]["items"] == {"$ref": "#/components/schemas/OrderItem"}, order
    assert order["properties"]["items"]["minItems"] == 1, order
    assert order["properties"]["items"]["maxItems"] == 5, order
    assert order["additionalProperties"] is False, order
    assert {"Address", "Customer", "OrderItem", "Order"} <= set(schemas), sorted(schemas)
    return "3 层 $ref 链 + minItems/maxItems + additionalProperties=false"


CHECKS = [
    ("合法嵌套请求", check_valid),
    ("嵌套缺字段 loc 五段", check_nested_missing),
    ("列表下标定位", check_list_index_loc),
    ("元素内部约束", check_element_constraint),
    ("元素不是对象", check_element_not_object),
    ("空列表", check_empty_list),
    ("内层 extra 不继承", check_inner_extra_ignored),
    ("外层 extra=forbid", check_outer_extra_forbidden),
    ("对象当列表传", check_list_type),
    ("多层错误聚合", check_deep_aggregation),
    ("OpenAPI $ref", check_openapi_refs),
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
