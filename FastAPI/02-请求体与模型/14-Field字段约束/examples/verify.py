"""第 14 章 · 自动验收。运行：python verify.py"""

import sys
import warnings
from pathlib import Path
from typing import Annotated

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from pydantic import BaseModel, Field  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)

VALID = {
    "name": "钢笔",
    "price": 9.9,
    "sku": "ABC-1234",
    "tags": ["文具"],
    "note": "送人用的礼盒",
    "itemName": "礼盒装",
}


def post(payload: dict | None = None) -> object:
    return client.post("/products", json=VALID if payload is None else payload)


def first_error(r) -> dict:
    assert r.status_code == 422, (r.status_code, r.text)
    return r.json()["detail"][0]


def check_valid() -> str:
    """合法请求：默认值生效，别名出现在 external 里。"""
    r = post()
    assert r.status_code == 200, r.text
    data = r.json()
    assert data["internal"]["item_name"] == "礼盒装", data
    assert data["external"]["itemName"] == "礼盒装", data
    assert data["internal"]["tags"] == ["文具"], data
    return f'external.itemName={data["external"]["itemName"]}'


def check_min_length() -> str:
    """字符串长度约束：错误带 ctx.min_length。"""
    err = first_error(post({**VALID, "name": "笔"}))
    assert err["type"] == "string_too_short", err
    assert err["loc"] == ["body", "name"], err
    assert err["ctx"] == {"min_length": 2}, err
    return f'{err["type"]} ctx={err["ctx"]}'


def check_gt_boundary() -> str:
    """gt=0：0 被拒，0.01 通过。"""
    err = first_error(post({**VALID, "price": 0}))
    assert err["type"] == "greater_than", err
    assert err["ctx"] == {"gt": 0.0}, err
    assert post({**VALID, "price": 0.01}).status_code == 200, "0.01 应通过"
    return "0 → greater_than；0.01 → 200"


def check_le_boundary() -> str:
    """le=100000：等号通过，超一点被拒。"""
    assert post({**VALID, "price": 100000}).status_code == 200, "100000 应通过"
    err = first_error(post({**VALID, "price": 100000.01}))
    assert err["type"] == "less_than_equal", err
    return "100000 → 200；100000.01 → less_than_equal"


def check_pattern() -> str:
    """正则约束：不匹配报 string_pattern_mismatch。"""
    err = first_error(post({**VALID, "sku": "abc-1234"}))
    assert err["type"] == "string_pattern_mismatch", err
    assert err["ctx"]["pattern"] == r"^[A-Z]{3}-\d{4}$", err
    assert post({**VALID, "sku": "XYZ-0001"}).status_code == 200, "合法 sku 应通过"
    return "abc-1234 → 422；XYZ-0001 → 200"


def check_list_max_items() -> str:
    """list 上 max_length 限制元素个数，错误里带 actual_length。"""
    err = first_error(post({**VALID, "tags": ["a", "b", "c", "d"]}))
    assert err["type"] == "too_long", err
    assert err["ctx"]["max_length"] == 3 and err["ctx"]["actual_length"] == 4, err
    return f'{err["type"]} actual_length={err["ctx"]["actual_length"]}'


def check_none_skips_constraints() -> str:
    """可选字段传 null 时约束不生效；传短串仍然报错。"""
    r = post({**VALID, "note": None})
    assert r.status_code == 200, r.text
    err = first_error(post({**VALID, "note": "abc"}))
    assert err["type"] == "string_too_short", err
    return "null → 200；'abc' → string_too_short"


def check_alias_required() -> str:
    """没配 populate_by_name 时只认别名：传字段名 422，且 loc 用别名。"""

    class OnlyAlias(BaseModel):
        item_name: Annotated[str, Field(alias="itemName")]

    app = FastAPI()

    @app.post("/only-alias")
    def only_alias(x: OnlyAlias) -> dict[str, str]:
        return x.model_dump()

    c = TestClient(app)
    assert c.post("/only-alias", json={"itemName": "x"}).status_code == 200
    r = c.post("/only-alias", json={"item_name": "x"})
    assert r.status_code == 422, r.text
    err = r.json()["detail"][0]
    assert err["type"] == "missing", err
    assert err["loc"] == ["body", "itemName"], err
    return f'422 missing loc={err["loc"]}'


def check_populate_by_name() -> str:
    """populate_by_name 必须在 model_config；写在 Field 里无效。"""
    payload = dict(VALID)
    payload.pop("itemName")
    payload["item_name"] = "礼盒装"
    # main 的模型已配 populate_by_name=True → 字段名也收
    assert post(payload).status_code == 200, "model_config 版应接受字段名"

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")  # Field 里传该参数会发 DeprecationWarning

        class Wrong(BaseModel):
            item_name: Annotated[str, Field(alias="itemName", populate_by_name=True)]

    app = FastAPI()

    @app.post("/w")
    def w(x: Wrong) -> dict[str, str]:
        return x.model_dump()

    r = TestClient(app).post("/w", json={"item_name": "x"})
    assert r.status_code == 422, "Field 版应当无效（仍 422）"
    return "model_config → 200；Field 参数 → 422"


def check_openapi_schema() -> str:
    """OpenAPI：约束变成 JSON Schema 关键字，examples 出现在文档里。"""
    schema = client.get("/openapi.json").json()["components"]["schemas"]["ProductCreate"]
    props = schema["properties"]
    assert schema["required"] == ["name", "price", "sku"], schema["required"]
    assert props["name"]["minLength"] == 2 and props["name"]["maxLength"] == 20, props["name"]
    assert props["price"]["exclusiveMinimum"] == 0.0, props["price"]
    assert props["price"]["maximum"] == 100000.0, props["price"]
    assert props["tags"]["maxItems"] == 3, props["tags"]
    assert props["sku"]["examples"] == ["ABC-1234"], props["sku"]
    assert props["sku"]["pattern"] == r"^[A-Z]{3}-\d{4}$", props["sku"]
    return "minLength/maxLength/exclusiveMinimum/maxItems/examples 全部生成"


CHECKS = [
    ("合法请求", check_valid),
    ("字符串长度", check_min_length),
    ("gt 边界", check_gt_boundary),
    ("le 边界", check_le_boundary),
    ("正则", check_pattern),
    ("列表元素个数", check_list_max_items),
    ("None 跳过约束", check_none_skips_constraints),
    ("别名只认 alias", check_alias_required),
    ("populate_by_name 位置", check_populate_by_name),
    ("OpenAPI 约束映射", check_openapi_schema),
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
