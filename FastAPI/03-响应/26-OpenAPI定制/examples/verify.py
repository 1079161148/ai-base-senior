"""第 26 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def schema() -> dict:
    return client.get("/openapi.json").json()


def check_info_meta() -> str:
    """应用级元信息进 info 节点。"""
    info = schema()["info"]
    assert info["title"] == "商品服务 API", info
    assert info["version"] == "1.2.3", info
    assert "文档即契约" in info["description"], info
    assert info["contact"]["url"] == "https://example.com/support", info
    assert info["license"]["name"] == "MIT", info
    assert info["summary"] == "一句话概述服务", info
    return f'{info["title"]} v{info["version"]}'


def check_tags_grouping() -> str:
    """标签分组：顶层 tags 带描述，operation 上带 tag。"""
    s = schema()
    names = [tag["name"] for tag in s["tags"]]
    assert names == ["商品", "运维", "内部"], names
    assert s["tags"][0]["description"] == "商品的增删改查", s["tags"][0]
    assert s["paths"]["/items"]["post"]["tags"] == ["商品"], s["paths"]["/items"]["post"]
    return f"tags={names}"


def check_field_description() -> str:
    """字段级说明与示例进 properties。"""
    props = schema()["components"]["schemas"]["ItemIn"]["properties"]
    assert props["name"]["description"] == "商品名称", props["name"]
    assert props["name"]["examples"] == ["机械键盘"], props["name"]
    assert props["price"]["description"] == "单价（元）", props["price"]
    return 'name.examples=["机械键盘"]'


def check_model_example() -> str:
    """模型级示例通过 json_schema_extra 注入。"""
    model = schema()["components"]["schemas"]["ItemOut"]
    examples = model.get("examples") or model.get("example")
    assert examples == [{"id": 1, "name": "机械键盘", "price": "399.00"}], model
    return f"examples={examples}"


def check_query_description() -> str:
    """查询参数描述来自 Query(...)。"""
    params = schema()["paths"]["/items"]["get"]["parameters"]
    keyword = next(p for p in params if p["name"] == "keyword")
    assert keyword["description"] == "名称关键字", keyword
    assert keyword["required"] is False, keyword
    return f'keyword 描述={keyword["description"]}'


def check_response_description() -> str:
    """response_description 进 200/201 描述。"""
    resp = schema()["paths"]["/items"]["post"]["responses"]["201"]
    assert resp["description"] == "创建成功的商品", resp
    return f'201 description={resp["description"]}'


def check_custom_responses() -> str:
    """responses= 自定义状态码描述。"""
    responses = schema()["paths"]["/items"]["post"]["responses"]
    assert responses["409"]["description"] == "同名商品已存在", responses
    assert "422" in responses, responses
    return f'responses={sorted(responses)}'


def check_deprecated() -> str:
    """deprecated=True 标记。"""
    op = schema()["paths"]["/items/{item_id}"]["get"]
    assert op["deprecated"] is True, op
    v2 = schema()["paths"]["/v2/items/{item_id}"]["get"]
    assert "deprecated" not in v2, v2
    return "旧版 marked deprecated，新版没有"


def check_openapi_extra() -> str:
    """openapi_extra 原样合并。"""
    op = schema()["paths"]["/v2/items/{item_id}"]["get"]
    assert op["x-internal-owner"] == "team-goods", op
    return "x-internal-owner=team-goods"


def check_hidden_endpoint() -> str:
    """include_in_schema=False：可调用但不在文档里。"""
    s = schema()
    assert "/internal/metrics" not in s["paths"], list(s["paths"])
    r = client.get("/internal/metrics")
    assert r.status_code == 200 and r.json()["items"] >= 1, r.text
    return "不在 paths，但能访问"


def check_custom_openapi_cached() -> str:
    """自定义 openapi 函数：servers 注入且结果被缓存。"""
    s = schema()
    assert s["servers"][0]["url"] == "https://api.example.com", s.get("servers")
    # 第二次取仍是同一个对象（缓存生效）
    assert main.app.openapi_schema is not None
    assert main.app.openapi() is main.app.openapi_schema
    return "servers 已注入，schema 已缓存"


CHECKS = [
    ("info 元信息", check_info_meta),
    ("标签分组", check_tags_grouping),
    ("字段说明与示例", check_field_description),
    ("模型级示例", check_model_example),
    ("查询参数描述", check_query_description),
    ("响应描述", check_response_description),
    ("自定义 responses", check_custom_responses),
    ("deprecated", check_deprecated),
    ("openapi_extra", check_openapi_extra),
    ("隐藏端点", check_hidden_endpoint),
    ("自定义 schema 缓存", check_custom_openapi_cached),
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
