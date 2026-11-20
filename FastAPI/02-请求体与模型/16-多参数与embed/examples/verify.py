"""第 16 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)

ITEM = {"sku": "A-1", "qty": 2}
ADDRESS = {"city": "北京", "street": "长安街"}


def check_mixed_ok() -> str:
    """路径 + 查询 + 头 + 单 body：全部生效，body 是裸对象。"""
    r = client.post(
        "/orders/9/items?notify=true",
        json=ITEM,
        headers={"X-Trace-Id": "t-1"},
    )
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["order_id"] == 9, data
    assert data["notify"] is True, data
    assert data["trace_id"] == "t-1", data
    assert data["item"] == {"sku": "A-1", "qty": 2}, data
    return "order_id=9 notify=True item=裸对象"


def check_mixed_body_loc() -> str:
    """混合参数的 body 错误：loc 仍从 body 开始。"""
    r = client.post("/orders/9/items", json={"sku": "A-1"})
    assert r.status_code == 422, r.status_code
    err = r.json()["detail"][0]
    assert err["loc"] == ["body", "qty"], err
    return f'loc={err["loc"]}'


def check_multi_body_wrapped() -> str:
    """两个 body 参数：必须按参数名包装。"""
    r = client.post("/shipments", json={"item": ITEM, "address": ADDRESS})
    assert r.status_code == 200, r.text
    assert r.json()["address"]["city"] == "北京", r.json()
    return "包装后 200"


def check_multi_body_unwrapped() -> str:
    """未包装：两个参数都报 missing，loc 是 body + 参数名。"""
    r = client.post("/shipments", json={**ITEM, **ADDRESS})
    assert r.status_code == 422, r.status_code
    locs = {tuple(e["loc"]) for e in r.json()["detail"]}
    assert locs == {("body", "item"), ("body", "address")}, locs
    return f'loc 集合={sorted(locs)}'


def check_multi_body_missing_one() -> str:
    """只缺一个：只报缺的那个。"""
    r = client.post("/shipments", json={"item": ITEM})
    assert r.status_code == 422, r.status_code
    detail = r.json()["detail"]
    assert len(detail) == 1, detail
    assert detail[0]["loc"] == ["body", "address"], detail
    return 'loc=["body","address"]'


def check_embed_requires_wrapper() -> str:
    """embed=True：裸对象不被接受。"""
    r = client.post("/coupons", json=ADDRESS)
    assert r.status_code == 422, r.status_code
    err = r.json()["detail"][0]
    assert err["type"] == "missing", err
    assert err["loc"] == ["body", "coupon"], err
    return f'422 missing loc={err["loc"]}'


def check_embed_ok() -> str:
    """embed=True：包装后正常。"""
    r = client.post("/coupons", json={"coupon": ADDRESS})
    assert r.status_code == 200, r.text
    assert r.json() == {"coupon": ADDRESS}, r.json()
    return "包装后 200"


def check_scalar_body_wrapped() -> str:
    """标量 body 与模型 body 共存：必须一起包装。"""
    r = client.post("/tokens/verify", json={"token": "abc", "item": ITEM})
    assert r.status_code == 200, r.text
    assert r.json() == {"token_length": 3, "item": ITEM}, r.json()

    bad = client.post("/tokens/verify", json={"token": "abc", **ITEM})
    assert bad.status_code == 422, bad.status_code
    locs = {tuple(e["loc"]) for e in bad.json()["detail"]}
    assert ("body", "item") in locs, locs
    return "包装后 200；未包装 422"


def check_body_key_is_param_name() -> str:
    """包装键名 = 函数参数名：发 {"data": ...} 不认。"""
    r = client.post("/shipments", json={"data": ITEM, "address": ADDRESS})
    assert r.status_code == 422, r.status_code
    assert r.json()["detail"][0]["loc"] == ["body", "item"], r.json()
    return '键名必须是 "item"（参数名）'


def check_openapi_body_components() -> str:
    """OpenAPI：多 body 生成 Body_* 组件，单 body 用 $ref 直连模型。"""
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    body_names = [n for n in schemas if n.startswith("Body_")]
    assert len(body_names) >= 3, body_names

    shipment = next(schemas[n] for n in body_names if "shipment" in n)
    assert shipment["required"] == ["item", "address"], shipment
    assert set(shipment["properties"]) == {"item", "address"}, shipment

    coupon = next(schemas[n] for n in body_names if "coupon" in n)
    assert coupon["required"] == ["coupon"], coupon

    # 单 body 不包装：直接用模型组件
    single = client.get("/openapi.json").json()["paths"]["/orders/{order_id}/items"]["post"]["requestBody"]
    assert single["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/OrderItemIn"}, single
    return f"Body_* 组件 {len(body_names)} 个；单 body 直连模型"


def check_get_with_body() -> str:
    """GET 带 body 技术上可行，但不是契约的一部分。"""
    app = main.app
    routes = {r.path: r.methods for r in app.routes if hasattr(r, "methods")}
    assert "POST" in routes["/orders/{order_id}/items"], routes["/orders/{order_id}/items"]
    return "订单条目只能 POST；GET 带 body 不建议"


CHECKS = [
    ("混合参数正常", check_mixed_ok),
    ("混合参数 body 错误 loc", check_mixed_body_loc),
    ("多 body 包装", check_multi_body_wrapped),
    ("多 body 未包装", check_multi_body_unwrapped),
    ("多 body 缺一个", check_multi_body_missing_one),
    ("embed 裸对象被拒", check_embed_requires_wrapper),
    ("embed 包装通过", check_embed_ok),
    ("标量 body 包装", check_scalar_body_wrapped),
    ("包装键名 = 参数名", check_body_key_is_param_name),
    ("OpenAPI Body_* 组件", check_openapi_body_components),
    ("GET 不带 body 契约", check_get_with_body),
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
