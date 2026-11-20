"""第 33 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


VALID_USER = {
    "username": "alice",
    "age": 30,
    "email": "alice@example.com",
    "address": {"city": "北京", "zipcode": "100000"},
}


def first_error(response) -> dict:  # noqa: ANN001
    errors = response.json()["errors"]
    assert errors, response.json()
    return errors[0]


def check_default_422_structure() -> str:
    """默认结构（独立 app）：detail 是 list，每条含 type/loc/msg/input。

    【实测】FastAPI 0.146 的错误条目**没有** `url` 字段
           （旧版 Pydantic 文档里常见 `url`，别照着写断言）
    """
    probe = FastAPI()

    class Item(BaseModel):
        name: str
        qty: int

    @probe.post("/items")
    def create(item: Item) -> dict[str, str]:  # noqa: ANN202
        return {"name": item.name}

    r = TestClient(probe).post("/items", json={"name": "x", "qty": "abc"})
    assert r.status_code == 422, (r.status_code, r.text)
    error = r.json()["detail"][0]
    assert error["loc"] == ["body", "qty"], error
    assert error["type"] == "int_parsing", error
    assert set(error) == {"type", "loc", "msg", "input"}, error
    return f'默认 keys={sorted(error)}, type={error["type"]}'


def check_custom_structure() -> str:
    """自定义处理器：code/message/errors/path。"""
    r = client.post("/users", json={**VALID_USER, "age": 10})
    assert r.status_code == 422, (r.status_code, r.text)
    body = r.json()
    assert body["code"] == "VALIDATION_ERROR", body
    assert body["message"] == "请求参数校验失败", body
    assert body["path"] == "/users", body
    assert isinstance(body["errors"], list) and body["errors"], body
    return f'code={body["code"]}, errors={len(body["errors"])}'


def check_field_and_source() -> str:
    """loc 前缀被拆成 source，字段名去掉前缀。"""
    r = client.post("/users", json={**VALID_USER, "age": 10})
    err = first_error(r)
    assert err["field"] == "age", err
    assert err["source"] == "body", err
    return f'field={err["field"]}, source={err["source"]}'


def check_translated_message() -> str:
    """中文文案 + 约束值（ctx）。"""
    r = client.post("/users", json={**VALID_USER, "age": 10})
    assert first_error(r)["message"] == "数值太小（最小 18）", first_error(r)

    short = client.post("/users", json={**VALID_USER, "username": "ab"})
    assert first_error(short)["message"] == "长度不足（至少 3 个字符）", first_error(short)

    long_name = client.post("/users", json={**VALID_USER, "username": "a" * 30})
    assert "最多 20 个字符" in first_error(long_name)["message"], first_error(long_name)
    return "数值/长度文案都带 ctx"


def check_missing_field() -> str:
    """缺必填字段：field + 中文提示。"""
    payload = dict(VALID_USER)
    payload.pop("email")
    r = client.post("/users", json=payload)
    assert r.status_code == 422, r.text
    err = first_error(r)
    assert err["field"] == "email", err
    assert err["message"] == "必填字段缺失", err
    assert err["type"] == "missing", err
    return "email → 必填字段缺失"


def check_nested_field_path() -> str:
    """嵌套模型：field 是点号路径。"""
    payload = {**VALID_USER, "address": {"city": "京", "zipcode": "100000"}}
    r = client.post("/users", json=payload)
    err = first_error(r)
    assert err["field"] == "address.city", err
    return f'field={err["field"]}'


def check_multiple_errors() -> str:
    """多个字段同时错：errors 有多条。"""
    payload = {
        "username": "ab",
        "age": 5,
        "email": "not-an-email",
        "address": {"city": "京", "zipcode": "abc"},
    }
    r = client.post("/users", json=payload)
    assert r.status_code == 422, r.text
    fields = {err["field"] for err in r.json()["errors"]}
    assert {"username", "age", "email", "address.city", "address.zipcode"} <= fields, fields
    return f"5 条错误：{sorted(fields)}"


def check_json_invalid() -> str:
    """非法 JSON：type=json_invalid。"""
    r = client.post(
        "/users",
        content=b"{not json",
        headers={"Content-Type": "application/json"},
    )
    assert r.status_code == 422, (r.status_code, r.text)
    err = first_error(r)
    assert err["type"] == "json_invalid", err
    assert err["message"] == "请求体不是合法 JSON", err
    return f'type={err["type"]}'


def check_query_source() -> str:
    """查询参数错误：source=query。"""
    r = client.get("/search", params={"q": "a"})
    assert r.status_code == 422, r.text
    err = first_error(r)
    assert err["source"] == "query", err
    assert err["field"] == "q", err
    return f'field={err["field"]}, source={err["source"]}'


def check_path_source() -> str:
    """路径参数错误：source=path。"""
    r = client.get("/items/0")
    assert r.status_code == 422, r.text
    err = first_error(r)
    assert err["source"] == "path", err
    assert err["field"] == "item_id", err
    return f'field={err["field"]}, source={err["source"]}'


def check_pydantic_ctx() -> str:
    """直接看 exc.errors() 里的 ctx（不经过自定义结构）。"""
    probe = FastAPI()

    class Item(BaseModel):
        qty: int

    @probe.post("/i")
    def create(item: Item) -> dict[str, int]:  # noqa: ANN202
        return {"qty": item.qty}

    r = TestClient(probe).post("/i", json={"qty": "abc"})
    error = r.json()["detail"][0]
    assert error["type"] == "int_parsing", error
    assert error["loc"] == ["body", "qty"], error
    return "int_parsing 无 ctx，但 type/loc 足够定位"


def check_valid_payload_passes() -> str:
    """合法请求不受影响。"""
    r = client.post("/users", json=VALID_USER)
    assert r.status_code == 200, (r.status_code, r.text)
    assert r.json() == {"username": "alice", "city": "北京"}, r.json()
    ok = client.get("/search", params={"q": "键盘", "page": 2})
    assert ok.status_code == 200 and ok.json()["q"] == "键盘", ok.text
    return "body/query 合法路径都 200"


def check_422_not_400() -> str:
    """默认状态码仍是 422（不是 400）。"""
    r = client.get("/search", params={"q": ""})
    assert r.status_code == 422, (r.status_code, r.text)
    return "状态码 422"


def check_openapi_still_default() -> str:
    """文档不会跟着处理器变：422 仍指向 HTTPValidationError。

    【实测】自定义处理器只改运行时响应，OpenAPI 里还是框架默认的 422 结构
    【结论】要让文档与实现一致，得手动改 `openapi()`
    """
    schema = client.get("/openapi.json").json()
    responses = schema["paths"]["/search"]["get"]["responses"]
    assert "422" in responses, sorted(responses)
    ref = responses["422"]["content"]["application/json"]["schema"]["$ref"]
    assert ref.endswith("HTTPValidationError"), ref
    return f"422 仍引用 {ref.split('/')[-1]}（需手动同步文档）"


CHECKS = [
    ("默认 422 结构", check_default_422_structure),
    ("自定义结构", check_custom_structure),
    ("field/source 拆分", check_field_and_source),
    ("中文文案 + ctx", check_translated_message),
    ("缺字段", check_missing_field),
    ("嵌套路径", check_nested_field_path),
    ("多条错误", check_multiple_errors),
    ("非法 JSON", check_json_invalid),
    ("query 来源", check_query_source),
    ("path 来源", check_path_source),
    ("Pydantic ctx", check_pydantic_ctx),
    ("合法请求", check_valid_payload_passes),
    ("状态码 422", check_422_not_400),
    ("OpenAPI 仍默认", check_openapi_still_default),
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