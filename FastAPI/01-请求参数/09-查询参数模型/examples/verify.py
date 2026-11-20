"""第 09 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)

# 【为什么定义在模块级】对比「不加 Query()」时模型会变成请求体。
# 注意本文件不使用 `from __future__ import annotations`，避免局部注解变字符串。
_forgot_query_app = FastAPI()


@_forgot_query_app.get("/forgot")
def _forgot_query(filters: main.ArticleFilter) -> dict[str, object]:  # 故意漏掉 Annotated[..., Query()]
    return filters.model_dump()


def check_defaults() -> str:
    """不传任何参数，全部取默认值。"""
    data = client.get("/articles").json()
    assert data == {
        "q": None,
        "tag": [],
        "limit": 20,
        "offset": 0,
        "order_by": "created",
    }, data
    return str(data)


def check_expanded_params() -> str:
    """模型的每个字段都是独立查询参数，可单独覆盖。"""
    r = client.get("/articles", params={"q": "py", "limit": 5, "offset": 10})
    data = r.json()
    assert data["q"] == "py" and data["limit"] == 5 and data["offset"] == 10, data
    return f"q={data['q']} limit={data['limit']} offset={data['offset']}"


def check_field_validation() -> str:
    """Field 的约束生效，loc 首段是 query、第二段是字段名。"""
    r = client.get("/articles", params={"limit": 0})
    assert r.status_code == 422, r.status_code
    item = r.json()["detail"][0]
    assert item["type"] == "greater_than_equal", item
    assert item["loc"] == ["query", "limit"], item

    r = client.get("/articles", params={"limit": 101})
    assert r.json()["detail"][0]["type"] == "less_than_equal"

    r = client.get("/articles", params={"q": ""})
    assert r.json()["detail"][0]["type"] == "string_too_short"
    return f"limit=0 → {item['type']} loc={item['loc']}"


def check_list_field() -> str:
    """模型里的 list 字段同样用重复键。"""
    r = client.get("/articles?tag=a&tag=b")
    assert r.json()["tag"] == ["a", "b"], r.json()
    # 逗号仍不拆分
    assert client.get("/articles?tag=a,b").json()["tag"] == ["a,b"]
    return str(r.json()["tag"])


def check_field_alias() -> str:
    """字段 alias：查询键用 order-by。"""
    assert client.get("/articles", params={"order-by": "views"}).json()["order_by"] == "views"
    return "order-by=views → order_by=views"


def check_alias_silent_fail() -> str:
    """用错键名（下划线）静默用默认值。"""
    r = client.get("/articles", params={"order_by": "views"})
    assert r.status_code == 200
    assert r.json()["order_by"] == "created", r.json()
    return f"order_by=views → 200 但得到默认值 {r.json()['order_by']}"


def check_nested_not_supported() -> str:
    """嵌套模型不可用：直接传子字段会 422 model_attributes_type。"""
    r = client.get("/wrong", params={"range": "x"})
    assert r.status_code == 422, r.status_code
    item = r.json()["detail"][0]
    assert item["type"] == "model_attributes_type", item
    assert item["loc"] == ["query", "range"], item
    return f"{item['type']} loc={item['loc']}"


def check_openapi_expanded() -> str:
    """OpenAPI 里必须展开成独立参数，不能是 $ref。"""
    schema = client.get("/openapi.json").json()
    params = schema["paths"]["/articles"]["get"]["parameters"]
    names = sorted(p["name"] for p in params)
    assert names == ["limit", "offset", "order-by", "q", "tag"], names
    for p in params:
        assert "$ref" not in p.get("schema", {}), p
        assert p["in"] == "query", p
    # 不应出现 requestBody
    assert "requestBody" not in schema["paths"]["/articles"]["get"], "不应有 requestBody"
    return f"展开 {len(params)} 个 query 参数：{names}"


def check_missing_query_means_body() -> str:
    """不写 Query() → 模型被当成请求体，GET 请求直接 422 missing body。"""
    schema = _forgot_query_app.openapi()
    op = schema["paths"]["/forgot"]["get"]
    assert "requestBody" in op, sorted(op)
    assert "parameters" not in op or not op["parameters"], op
    # 【实测】即使模型字段全有默认值，body 本身仍是必填 → GET 无 body 直接 422
    r = TestClient(_forgot_query_app).get("/forgot")
    assert r.status_code == 422, (r.status_code, r.text)
    item = r.json()["detail"][0]
    assert item["type"] == "missing", item
    assert item["loc"] == ["body"], item
    return f"漏写 Query() → OpenAPI 有 requestBody；GET → 422 {item['type']} loc={item['loc']}"


CHECK_LIST = [
    ("不传时全用默认值", check_defaults),
    ("展开成独立参数", check_expanded_params),
    ("字段级校验生效", check_field_validation),
    ("数组字段用重复键", check_list_field),
    ("字段 alias 生效", check_field_alias),
    ("用错字段名静默失败", check_alias_silent_fail),
    ("嵌套模型不可用", check_nested_not_supported),
    ("OpenAPI 展开无 $ref", check_openapi_expanded),
    ("不写 Query() 变成请求体", check_missing_query_means_body),
]


def run() -> int:
    failures = 0
    for name, func in CHECK_LIST:
        try:
            print(f"[PASS] {name} -> {func()}")
        except AssertionError as exc:
            failures += 1
            print(f"[FAIL] {name} -> {exc}")
    print(f"\n结果：{len(CHECK_LIST) - failures}/{len(CHECK_LIST)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())
