"""第 13 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def check_create_ok() -> str:
    """合法请求体：字段齐全 + 默认值生效 + 类型已转换。"""
    r = client.post("/items", json={"name": "笔", "price": 9.9})
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["received"] == {"name": "笔", "price": 9.9, "in_stock": True}, data
    assert data["price_type"] == "float", data
    return str(data["received"])


def check_missing_field() -> str:
    """缺字段：loc 是 ["body", 字段名]，共两段。"""
    r = client.post("/items", json={"name": "笔"})
    assert r.status_code == 422, r.status_code
    item = r.json()["detail"][0]
    assert item["type"] == "missing", item
    assert item["loc"] == ["body", "price"], item
    return f'422 {item["type"]} loc={item["loc"]}'


def check_empty_object() -> str:
    """空对象 {}：所有必填字段一次性报出来。"""
    r = client.post("/items", json={})
    assert r.status_code == 422, r.status_code
    locs = [e["loc"] for e in r.json()["detail"]]
    assert locs == [["body", "name"], ["body", "price"]], locs
    return f"{len(locs)} 条 missing（name/price）"


def check_no_body() -> str:
    """不发 body 或发 null：只有一条 missing，loc 只有 ["body"]。"""
    r1 = client.post("/items")
    r2 = client.post("/items", json=None)
    assert r1.status_code == r2.status_code == 422, (r1.status_code, r2.status_code)
    for r in (r1, r2):
        detail = r.json()["detail"]
        assert len(detail) == 1, detail
        assert detail[0]["type"] == "missing", detail
        assert detail[0]["loc"] == ["body"], detail
    return '422 missing loc=["body"]（单条）'


def check_lenient_coercion() -> str:
    """宽松转换：字符串数字 → 数值；int → float 自动升级。"""
    r = client.post("/items", json={"name": "笔", "price": "9.9"})
    assert r.status_code == 200, r.text
    assert r.json()["received"]["price"] == 9.9, r.json()

    r = client.post("/items", json={"name": "笔", "price": 9})
    assert r.status_code == 200, r.text
    assert r.json()["price_type"] == "float" and r.json()["received"]["price"] == 9.0, r.json()
    return '"9.9"→9.9；9→9.0(float)'


def check_no_str_coercion() -> str:
    """反向不成立：int 不会被转成 str。"""
    r = client.post("/items", json={"name": 1, "price": 1})
    assert r.status_code == 422, r.status_code
    item = r.json()["detail"][0]
    assert item["type"] == "string_type", item
    assert item["loc"] == ["body", "name"], item
    return f'422 {item["type"]}（1 不会变成 "1"）'


def check_extra_ignored_by_default() -> str:
    """默认 extra=ignore：多余字段被静默丢弃。"""
    r = client.post("/items", json={"name": "笔", "price": 1, "hack": 1})
    assert r.status_code == 200, r.text
    assert "hack" not in r.json()["received"], r.json()
    return "200 且 hack 被丢弃（不报错）"


def check_extra_forbidden() -> str:
    """extra="forbid"：多余字段 422。"""
    r = client.post("/items-strict", json={"name": "笔", "price": 1, "hack": 1})
    assert r.status_code == 422, r.status_code
    item = r.json()["detail"][0]
    assert item["type"] == "extra_forbidden", item
    assert item["loc"] == ["body", "hack"], item
    return f'422 {item["type"]} loc={item["loc"]}'


def check_content_type_trap() -> str:
    """Content-Type 不是 application/json：body 不会被解析成 JSON。"""
    raw = b'{"name":"pen","price":1}'
    r = client.post("/items", content=raw, headers={"Content-Type": "text/plain"})
    assert r.status_code == 422, r.status_code
    item = r.json()["detail"][0]
    assert item["type"] == "model_attributes_type", item
    assert item["loc"] == ["body"], item
    assert item["input"] == raw.decode(), item
    return f'422 {item["type"]}（body 仍是字符串）'


def check_optional_body() -> str:
    """整个 body 可选：不传与传 null 都是 200。"""
    for r in (client.post("/items-optional"), client.post("/items-optional", json=None)):
        assert r.status_code == 200, r.text
        assert r.json() == {"item": None}, r.json()

    ok = client.post("/items-optional", json={"name": "笔", "price": 1})
    assert ok.status_code == 200 and ok.json()["item"]["name"] == "笔", ok.text
    return "不传/null → item=None；传了 → 正常解析"


def check_openapi_request_body() -> str:
    """OpenAPI：requestBody 必填、$ref 指向组件、默认值进 schema。"""
    schema = client.get("/openapi.json").json()
    body = schema["paths"]["/items"]["post"]["requestBody"]
    assert body["required"] is True, body
    assert body["content"]["application/json"]["schema"] == {"$ref": "#/components/schemas/ItemCreate"}, body

    model = schema["components"]["schemas"]["ItemCreate"]
    assert model["required"] == ["name", "price"], model
    assert model["properties"]["in_stock"]["default"] is True, model

    # 【注意】可选请求体时 OpenAPI **省略** required 字段；OpenAPI 规范里省略默认 false
    optional = schema["paths"]["/items-optional"]["post"]["requestBody"]
    assert "required" not in optional, optional
    return "items required=true；items-optional 省略 required（等价 false）"


CHECKS = [
    ("合法请求体", check_create_ok),
    ("缺字段 loc 两段", check_missing_field),
    ("空对象聚合", check_empty_object),
    ("无 body / null", check_no_body),
    ("宽松类型转换", check_lenient_coercion),
    ("int 不转 str", check_no_str_coercion),
    ("未知字段默认丢弃", check_extra_ignored_by_default),
    ("extra=forbid", check_extra_forbidden),
    ("Content-Type 陷阱", check_content_type_trap),
    ("可选请求体", check_optional_body),
    ("OpenAPI requestBody", check_openapi_request_body),
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
