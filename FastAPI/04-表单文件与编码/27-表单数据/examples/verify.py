"""第 27 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path
from typing import Annotated

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, Form  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def first_error(response) -> dict:  # noqa: ANN001
    detail = response.json()["detail"]
    assert isinstance(detail, list) and detail, detail
    return detail[0]


def check_form_login_ok() -> str:
    """标准表单登录：200 且字段都取到。"""
    r = client.post(
        "/login",
        data={"username": "alice", "password": "secret123", "remember": "true"},
    )
    assert r.status_code == 200, (r.status_code, r.text)
    assert r.json() == {"username": "alice", "authenticated": True, "remember": True}, r.json()
    return "username=alice, authenticated=True"


def check_form_content_type() -> str:
    """data= 发送时 Content-Type 是 x-www-form-urlencoded。"""
    r = client.post("/login", data={"username": "alice", "password": "secret123"})
    assert r.status_code == 200, r.text
    # TestClient 的请求侧头不可直接读，改由 OpenAPI 的 requestBody 反证
    body = client.get("/openapi.json").json()["paths"]["/login"]["post"]["requestBody"]
    keys = list(body["content"])
    assert "application/x-www-form-urlencoded" in keys, keys
    assert "application/json" not in keys, keys
    return f"requestBody.content={keys}"


def check_default_value() -> str:
    """可选表单字段缺省时用默认值，不报 422。"""
    r = client.post("/login", data={"username": "bob", "password": "secret123"})
    assert r.status_code == 200, r.text
    assert r.json()["remember"] is False, r.json()
    assert r.json()["authenticated"] is False, "bob 不在用户表"
    return "remember 默认 False"


def check_missing_field_422() -> str:
    """缺必填表单字段 → 422，loc 指向 body.username。"""
    r = client.post("/login", data={"password": "secret123"})
    assert r.status_code == 422, (r.status_code, r.text)
    err = first_error(r)
    assert err["loc"] == ["body", "username"], err
    assert err["type"] == "missing", err
    return f'loc={err["loc"]}'


def check_min_length_422() -> str:
    """Form 约束生效：密码太短 422。"""
    r = client.post("/login", data={"username": "alice", "password": "123"})
    assert r.status_code == 422, (r.status_code, r.text)
    err = first_error(r)
    assert err["type"] == "string_too_short", err
    assert err["loc"] == ["body", "password"], err
    return f'type={err["type"]}'


def check_int_conversion() -> str:
    """表单值是字符串，int 字段自动转换。"""
    r = client.post("/signup", data={"username": "alice", "age": "30"})
    assert r.status_code == 200, r.text
    assert r.json()["age"] == 30 and isinstance(r.json()["age"], int), r.json()
    assert r.json()["score"] == 60.0, r.json()
    return "age='30' → 30 (int)，score 默认 60.0"


def check_int_parse_error() -> str:
    """无法转换 → 422，type=int_parsing。"""
    r = client.post("/signup", data={"username": "alice", "age": "abc"})
    assert r.status_code == 422, (r.status_code, r.text)
    err = first_error(r)
    assert err["type"] == "int_parsing", err
    return f'type={err["type"]}'


def check_range_422() -> str:
    """数值范围约束生效。"""
    r = client.post("/signup", data={"username": "alice", "age": "17"})
    assert r.status_code == 422, r.text
    err = first_error(r)
    assert err["type"] == "greater_than_equal", err
    return f'type={err["type"]}'


def check_alias() -> str:
    """Form(alias=...) 用外部字段名，内部参数名不变。"""
    ok = client.post("/signup/alias", data={"user-name": "alice"})
    assert ok.status_code == 200, ok.text
    assert ok.json() == {"username": "alice"}, ok.json()

    bad = client.post("/signup/alias", data={"username": "alice"})
    assert bad.status_code == 422, bad.text
    assert first_error(bad)["type"] == "missing", first_error(bad)
    return "只认 user-name；username 报 missing"


def check_form_plus_query() -> str:
    """Form 取 body，Query 取 URL 查询串。"""
    r = client.post("/search?page=2", data={"keyword": "键盘"})
    assert r.status_code == 200, r.text
    assert r.json() == {"keyword": "键盘", "page": 2}, r.json()
    return "keyword=键盘, page=2"


def check_json_body_rejected() -> str:
    """用 JSON 发到表单端点 → 422（字段取不到）。"""
    r = client.post("/login", json={"username": "alice", "password": "secret123"})
    assert r.status_code == 422, (r.status_code, r.text)
    types = {item["type"] for item in r.json()["detail"]}
    assert types == {"missing"}, types
    return "JSON 体不被当表单解析 → missing"


def check_form_and_body_coexist() -> str:
    """Form 与 JSON 模型同时声明：不报错，但模型被塞进表单、实际不可用。"""
    probe = FastAPI()

    class Item(BaseModel):
        name: str

    @probe.post("/conflict")
    def conflict(item: Item, username: Annotated[str, Form()]):  # noqa: ANN202
        return {}

    t = TestClient(probe)

    # 表单里没有 item 键 → missing
    r = t.post("/conflict", data={"username": "a", "name": "x"})
    assert r.status_code == 422, (r.status_code, r.text)
    assert r.json()["detail"][0]["type"] == "missing", r.json()["detail"][0]

    # 即便把 JSON 文本塞进 item，也只是字符串，无法转成对象
    r2 = t.post("/conflict", data={"username": "a", "item": '{"name":"x"}'})
    assert r2.status_code == 422, (r2.status_code, r2.text)
    err = r2.json()["detail"][0]
    assert err["loc"] == ["body", "item"], err
    assert err["type"] == "model_attributes_type", err

    body = t.get("/openapi.json").json()["paths"]["/conflict"]["post"]["requestBody"]
    assert "application/x-www-form-urlencoded" in body["content"], body
    return "定义期不报错；模型变成表单字段 item，实际传不进去"


CHECKS = [
    ("表单登录成功", check_form_login_ok),
    ("OpenAPI 表单体", check_form_content_type),
    ("默认值", check_default_value),
    ("缺字段 422", check_missing_field_422),
    ("长度约束 422", check_min_length_422),
    ("int 自动转换", check_int_conversion),
    ("转换失败 int_parsing", check_int_parse_error),
    ("范围约束 422", check_range_422),
    ("字段别名", check_alias),
    ("Form + Query 混用", check_form_plus_query),
    ("JSON 体不被接受", check_json_body_rejected),
    ("Form 与 Body 共存", check_form_and_body_coexist),
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