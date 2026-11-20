"""第 17 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)

OK = {
    "order_id": "123e4567-e89b-12d3-a456-426614174000",
    "amount": "19.99",
    "created_at": "2026-01-02T03:04:05",
    "ship_date": "2026-01-05",
    "callback": "https://example.com/hook",
    "channel": "app",
    "kind": "wholesale",
}


def post(payload: dict | None = None) -> object:
    return client.post("/payments", json=OK if payload is None else payload)


def first_error(r) -> dict:
    assert r.status_code == 422, (r.status_code, r.text)
    return r.json()["detail"][0]


def check_valid_types() -> str:
    """合法请求：每个特殊类型都转成了对应的 Python 类型。"""
    r = post()
    assert r.status_code == 200, r.text
    types = r.json()["types"]
    assert types == {
        "order_id": "UUID",
        "amount": "Decimal",
        "created_at": "datetime",
        "callback": "HttpUrl",
        "channel": "Channel",
    }, types
    assert r.json()["amount_exact"] == "19.99", r.json()
    return str(types)


def check_uuid_invalid() -> str:
    """UUID 非法字符串：uuid_parsing。"""
    err = first_error(post({**OK, "order_id": "not-a-uuid"}))
    assert err["type"] == "uuid_parsing", err
    assert err["loc"] == ["body", "order_id"], err
    return f'{err["type"]}：{err["ctx"]["error"]}'


def check_decimal_places() -> str:
    """小数位超限：decimal_max_places。"""
    err = first_error(post({**OK, "amount": "1.999"}))
    assert err["type"] == "decimal_max_places", err
    assert err["ctx"] == {"decimal_places": 2}, err
    return f'{err["type"]} ctx={err["ctx"]}'


def check_decimal_digits() -> str:
    """总位数超限：decimal_max_digits。"""
    err = first_error(post({**OK, "amount": "1234567.89"}))
    assert err["type"] == "decimal_max_digits", err
    assert err["ctx"] == {"max_digits": 8}, err
    return f'{err["type"]} ctx={err["ctx"]}'


def check_datetime_invalid() -> str:
    """非法时间：datetime_from_date_parsing。"""
    err = first_error(post({**OK, "created_at": "2026-13-45"}))
    assert err["type"] == "datetime_from_date_parsing", err
    assert err["loc"] == ["body", "created_at"], err
    return err["ctx"]["error"]


def check_date_invalid() -> str:
    """不存在的日期（2 月 30 日）：date_from_datetime_parsing。"""
    err = first_error(post({**OK, "ship_date": "2026-02-30"}))
    assert err["type"] == "date_from_datetime_parsing", err
    return err["ctx"]["error"]


def check_enum_invalid() -> str:
    """枚举非法值：enum + ctx.expected 列出可选值。"""
    err = first_error(post({**OK, "channel": "miniapp"}))
    assert err["type"] == "enum", err
    assert err["ctx"] == {"expected": "'web' or 'app'"}, err
    return f'{err["type"]} expected={err["ctx"]["expected"]}'


def check_literal_invalid() -> str:
    """Literal 非法值：literal_error。"""
    err = first_error(post({**OK, "kind": "vip"}))
    assert err["type"] == "literal_error", err
    assert err["ctx"] == {"expected": "'retail' or 'wholesale'"}, err
    return f'{err["type"]} expected={err["ctx"]["expected"]}'


def check_url_invalid() -> str:
    """URL 非法：url_parsing（相对地址也会被拒）。"""
    err = first_error(post({**OK, "callback": "not-a-url"}))
    assert err["type"] == "url_parsing", err
    assert err["ctx"]["error"] == "relative URL without a base", err
    return err["ctx"]["error"]


def check_decimal_accepts_number() -> str:
    """JSON 数字也能进 Decimal，但浮点字面量仍有精度风险。"""
    r = post({**OK, "amount": 19.99})
    assert r.status_code == 200, r.text
    assert r.json()["amount_exact"] == "19.99", r.json()
    return "数字 19.99 → Decimal('19.99')"


def check_serialization_modes() -> str:
    """json 模式：Decimal/UUID/datetime 全部变成字符串。"""
    r = post()
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["dump_json"]["amount"] == "19.99", data["dump_json"]
    assert data["dump_json"]["order_id"] == OK["order_id"], data["dump_json"]
    assert isinstance(data["dump_json"]["created_at"], str), data["dump_json"]
    assert data["amount_exact"] == "19.99", data
    return 'json 模式：amount="19.99"（字符串）'


def check_annotation_affects_encoding() -> str:
    """返回注解决定 Decimal 的线上形态（实测）。"""
    from decimal import Decimal

    from fastapi import FastAPI
    from pydantic import BaseModel

    class M(BaseModel):
        amount: Decimal

    app = FastAPI()

    @app.get("/no-annotation")
    def no_annotation():
        return M(amount=Decimal("19.99")).model_dump()

    @app.get("/with-annotation")
    def with_annotation() -> dict[str, object]:
        return M(amount=Decimal("19.99")).model_dump()

    c = TestClient(app)
    # 无返回注解：走 jsonable_encoder → JSON 数字
    assert c.get("/no-annotation").json()["amount"] == 19.99, c.get("/no-annotation").text
    # 有返回注解：走 Pydantic 响应模型 → 字符串
    assert c.get("/with-annotation").json()["amount"] == "19.99", c.get("/with-annotation").text
    return "无注解→19.99(number)；有注解→\"19.99\"(string)"


def check_openapi_formats() -> str:
    """OpenAPI：format/约束/枚举都写进 schema。"""
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    props = schemas["PaymentCreate"]["properties"]
    assert props["order_id"]["format"] == "uuid", props["order_id"]
    assert props["created_at"]["format"] == "date-time", props["created_at"]
    assert props["callback"]["anyOf"][0]["format"] == "uri", props["callback"]
    assert props["channel"] == {"$ref": "#/components/schemas/Channel", "default": "web"}, props["channel"]
    assert props["kind"]["enum"] == ["retail", "wholesale"], props["kind"]
    assert schemas["Channel"]["enum"] == ["web", "app"], schemas["Channel"]
    # Decimal 的 schema 是 anyOf(number, string)
    kinds = {item.get("type") for item in props["amount"]["anyOf"]}
    assert kinds == {"number", "string"}, props["amount"]
    return "uuid/date-time/uri/enum/anyOf 全部生成"


CHECKS = [
    ("特殊类型转换", check_valid_types),
    ("UUID 非法", check_uuid_invalid),
    ("小数位超限", check_decimal_places),
    ("总位数超限", check_decimal_digits),
    ("时间非法", check_datetime_invalid),
    ("日期非法", check_date_invalid),
    ("枚举非法", check_enum_invalid),
    ("Literal 非法", check_literal_invalid),
    ("URL 非法", check_url_invalid),
    ("数字金额", check_decimal_accepts_number),
    ("两种序列化模式", check_serialization_modes),
    ("返回注解影响编码", check_annotation_affects_encoding),
    ("OpenAPI format", check_openapi_formats),
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
