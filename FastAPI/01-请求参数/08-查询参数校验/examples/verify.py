"""第 08 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def check_required_missing() -> str:
    """无默认值 → 必填，缺失 422 missing。"""
    r = client.get("/articles", params={"q": "abc"})
    assert r.status_code == 200, r.text
    r = client.get("/articles")
    assert r.status_code == 422, r.status_code
    item = r.json()["detail"][0]
    assert item["type"] == "missing" and item["loc"] == ["query", "q"], item
    return f"422 {item['type']} loc={item['loc']}"


def check_min_length() -> str:
    """min_length=1 让空串被拒（对比第 07 章不校验时 200）。"""
    r = client.get("/articles", params={"q": ""})
    assert r.status_code == 422, r.status_code
    item = r.json()["detail"][0]
    assert item["type"] == "string_too_short", item
    return f"空串 -> {item['type']}"


def check_option_range() -> str:
    """limit 有默认值 → 可选；但有 ge/le 约束。"""
    assert client.get("/articles", params={"q": "a"}).json()["limit"] == 20
    assert client.get("/articles", params={"q": "a", "limit": 0}).status_code == 422
    assert client.get("/articles", params={"q": "a", "limit": 101}).status_code == 422
    types = {
        p: client.get("/articles", params={"q": "a", "limit": v}).json()["detail"][0]["type"]
        for p, v in (("low", 0), ("high", 101))
    }
    assert types == {"low": "greater_than_equal", "high": "less_than_equal"}, types
    return f"{types}"


def check_alias_works() -> str:
    """alias 生效：用 page-size 能改值。"""
    r = client.get("/orders", params={"page-size": 30})
    assert r.json()["page_size"] == 30, r.json()
    return "page-size=30 → 30"


def check_alias_silent_fail() -> str:
    """用错别名（下划线）→ 不报错，静默用默认值。这是本章最重要的坑。"""
    r = client.get("/orders", params={"page_size": 30})
    assert r.status_code == 200, r.status_code
    assert r.json()["page_size"] == 10, r.json()
    return f"page_size=30 → 200 但得到默认值 {r.json()['page_size']}（不报错）"


def check_deprecated_in_schema() -> str:
    """deprecated 与 alias 都要进 OpenAPI。"""
    schema = client.get("/openapi.json").json()
    params = {p["name"]: p for p in schema["paths"]["/orders"]["get"]["parameters"]}
    assert "page-size" in params, sorted(params)
    assert params["old-flag"]["schema"]["deprecated"] is True, params["old-flag"]
    return f"name=page-size, old-flag deprecated=True"


def check_hidden_param() -> str:
    """隐藏参数可用，但 parameters 键可能整个消失。"""
    assert client.get("/debug/echo", params={"value": "v", "_internal": "x"}).json()["internal_used"] is True
    schema = client.get("/openapi.json").json()
    names = [p["name"] for p in schema["paths"]["/debug/echo"]["get"]["parameters"]]
    assert "_internal" not in names, names
    assert "value" in names, names
    return f"文档参数={names}（_internal 已隐藏）"


def check_array_element_validation() -> str:
    """两层约束要分清：Query(max_length) 限数组长度，元素约束要写在元素类型上。"""
    # 1) 数组长度超限：loc 只有两段，type=too_long
    too_many = {"tag": [f"t{i}" for i in range(11)]}
    r = client.get("/tags", params=too_many)
    assert r.status_code == 422, r.text
    item = r.json()["detail"][0]
    assert item["type"] == "too_long", item
    assert item["loc"] == ["query", "tag"], item

    # 2) 元素类型错误：loc 带索引
    r = client.get("/tags", params={"ids": "a"})
    assert r.status_code == 422, r.status_code
    loc = r.json()["detail"][0]["loc"]
    assert loc[:2] == ["query", "ids"] and len(loc) == 3, loc

    # 3) 元素长度约束（写在 list[Annotated[...]] 上）：loc 也带索引
    r = client.get("/tags", params={"codes": "x"})
    assert r.status_code == 422, r.status_code
    code_item = r.json()["detail"][0]
    assert code_item["type"] == "string_too_short", code_item
    assert len(code_item["loc"]) == 3, code_item

    ok = client.get("/tags?tag=a&tag=bb&ids=1&ids=2&codes=ab").json()
    assert ok["ids"] == [1, 2] and ok["tag"] == ["a", "bb"] and ok["codes"] == ["ab"], ok
    return f"数组超限 loc={item['loc']}；元素错误 loc={loc}；合法 {ok['tag']}"


def check_optional_with_constraint() -> str:
    """可选 + 约束：不传跳过校验，传了才校验。"""
    assert client.get("/optional").json() == {"q": None}
    assert client.get("/optional", params={"q": "ab"}).status_code == 422
    assert client.get("/optional", params={"q": "abc"}).json() == {"q": "abc"}
    return "不传 → None；ab → 422；abc → 200"


def check_schema_constraints() -> str:
    """约束必须进 OpenAPI。"""
    schema = client.get("/openapi.json").json()
    params = {p["name"]: p for p in schema["paths"]["/articles"]["get"]["parameters"]}
    assert params["limit"]["schema"]["minimum"] == 1, params["limit"]
    assert params["limit"]["schema"]["maximum"] == 100, params["limit"]
    assert params["q"]["schema"]["minLength"] == 1, params["q"]
    assert "pattern" in params["q"]["schema"], params["q"]
    assert params["q"]["required"] is True, params["q"]
    return "q: minLength+pattern+required；limit: minimum/maximum"


CHECKS = [
    ("必填缺失 missing", check_required_missing),
    ("min_length 拒空串", check_min_length),
    ("可选 + 范围约束", check_option_range),
    ("别名生效", check_alias_works),
    ("别名写错静默失败", check_alias_silent_fail),
    ("deprecated 进文档", check_deprecated_in_schema),
    ("隐藏参数", check_hidden_param),
    ("数组逐项校验", check_array_element_validation),
    ("可选 + 约束", check_optional_with_constraint),
    ("约束进 schema", check_schema_constraints),
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
