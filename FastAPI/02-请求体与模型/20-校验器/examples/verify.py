"""第 20 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)

OK = {
    "email": "User@Example.COM",
    "password": "abc12345",
    "confirm": "abc12345",
    "start": "2026-03-01",
    "end": "2026-03-05",
    "guests": 2,
    "note": "",
}


def post(payload: dict | None = None) -> object:
    return client.post("/bookings", json=OK if payload is None else payload)


def first_error(r) -> dict:
    assert r.status_code == 422, (r.status_code, r.text)
    return r.json()["detail"][0]


def check_valid_and_transform() -> str:
    """合法请求：邮箱转小写、空 note 转 None、响应剔除密码。"""
    r = post()
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["email_normalized"] == "user@example.com", data
    assert data["booking"]["note"] is None, data
    assert "password" not in data["booking"], data
    assert "confirm" not in data["booking"], data
    return f'email={data["email_normalized"]}，note=None'


def check_field_validator_loc() -> str:
    """字段校验器抛错：loc 指向该字段。"""
    err = first_error(post({**OK, "email": "not-an-email"}))
    assert err["type"] == "value_error", err
    assert err["loc"] == ["body", "email"], err
    assert err["msg"] == "Value error, 邮箱必须包含 @", err
    return f'{err["type"]} loc={err["loc"]}'


def check_two_rules_one_validator() -> str:
    """同一个校验器里的多条规则：第一条命中即返回。"""
    err = first_error(post({**OK, "password": "abc123", "confirm": "abc123"}))
    assert err["msg"] == "Value error, 密码至少 8 位", err

    err = first_error(post({**OK, "password": "12345678", "confirm": "12345678"}))
    assert err["msg"] == "Value error, 密码不能全是数字", err
    return "短密码 → 至少 8 位；全数字 → 不能全数字"


def check_model_validator_loc() -> str:
    """模型校验器抛错：loc 是 ["body"]，不是字段。"""
    err = first_error(post({**OK, "confirm": "different1"}))
    assert err["type"] == "value_error", err
    assert err["loc"] == ["body"], err
    assert err["msg"] == "Value error, 两次输入的密码不一致", err
    return f'loc={err["loc"]}（整个模型）'


def check_cross_field_dates() -> str:
    """跨字段日期规则：end < start 被拒。"""
    err = first_error(post({**OK, "start": "2026-03-05", "end": "2026-03-01"}))
    assert err["msg"] == "Value error, 结束日期不能早于开始日期", err
    assert err["loc"] == ["body"], err
    return "end<start → value_error loc=['body']"


def check_field_before_validator_runs_on_raw() -> str:
    """mode=before：拿到原始值（空串被转 None），不经过类型转换。"""
    r = post({**OK, "note": "   "})
    assert r.status_code == 200, r.text
    assert r.json()["booking"]["note"] is None, r.json()

    r = post({**OK, "note": "  需要安静房间  "})
    assert r.status_code == 200, r.text
    assert r.json()["booking"]["note"] == "需要安静房间", r.json()
    return '空白→None；带内容→strip 后保留'


def check_field_constraint_runs_before_validator() -> str:
    """Field 约束先于 after 校验器：太短直接 string_too_short。"""
    err = first_error(post({**OK, "email": "a@b"}))
    assert err["type"] == "string_too_short", err
    assert err["loc"] == ["body", "email"], err
    return "email='a@b' → string_too_short（还没走到 @ 检查）"


def check_multiple_errors_aggregate() -> str:
    """多个字段同时出错：一次返回多条。"""
    payload = {**OK, "guests": 99, "email": "bad"}
    r = post(payload)
    assert r.status_code == 422, r.status_code
    locs = {tuple(e["loc"]) for e in r.json()["detail"]}
    assert ("body", "guests") in locs, locs
    assert ("body", "email") in locs, locs
    return f"{len(locs)} 条错误同时返回"


def check_inherited_validators() -> str:
    """子类继承校验器，只覆盖 Field 约束。"""
    assert main.BookingCreate in main.VipBookingCreate.__mro__
    r = client.post("/vip-bookings", json={**OK, "guests": 20})
    assert r.status_code == 200, r.text
    assert r.json()["guests"] == 20, r.json()

    err = first_error(client.post("/vip-bookings", json={**OK, "guests": 21}))
    assert err["type"] == "less_than_equal", err

    # 【注意】用 8 位无 @ 的字符串：先过 min_length=5，再触发继承来的 @ 校验
    err = first_error(client.post("/vip-bookings", json={**OK, "guests": 20, "email": "bademail"}))
    assert err["msg"] == "Value error, 邮箱必须包含 @", "继承来的校验器仍生效"
    return "VIP 放宽到 20，邮箱校验器仍继承"


def check_openapi_unchanged_shape() -> str:
    """校验器不进 OpenAPI：schema 里看不到跨字段规则。"""
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    model = schemas["BookingCreate"]
    assert set(model["properties"]) == {"email", "password", "confirm", "start", "end", "guests", "note"}, model
    assert "两次输入的密码不一致" not in str(model), "校验器规则不会出现在 schema 里"
    return "schema 只有字段，无跨字段规则"


CHECKS = [
    ("合法请求与值变形", check_valid_and_transform),
    ("字段校验器 loc", check_field_validator_loc),
    ("一个校验器多条规则", check_two_rules_one_validator),
    ("模型校验器 loc", check_model_validator_loc),
    ("跨字段日期规则", check_cross_field_dates),
    ("before 校验器拿原始值", check_field_before_validator_runs_on_raw),
    ("Field 约束先执行", check_field_constraint_runs_before_validator),
    ("多错误聚合", check_multiple_errors_aggregate),
    ("校验器被继承", check_inherited_validators),
    ("OpenAPI 不含规则", check_openapi_unchanged_shape),
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
