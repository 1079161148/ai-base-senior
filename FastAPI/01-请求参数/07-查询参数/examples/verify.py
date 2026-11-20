"""第 07 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def check_optional_defaults() -> str:
    """不传时取默认值。"""
    assert client.get("/search").json() == {"q": None, "limit": 10}
    return str(client.get("/search").json())


def check_override() -> str:
    """传了则覆盖默认值。"""
    r = client.get("/search", params={"q": "x", "limit": 5})
    assert r.json() == {"q": "x", "limit": 5}, r.json()
    return str(r.json())


def check_required_missing() -> str:
    """无默认值 → 必填；缺失返回 422 missing，loc 首段是 query。"""
    r = client.get("/reports")
    assert r.status_code == 422, r.status_code
    item = r.json()["detail"][0]
    assert item["type"] == "missing", item
    assert item["loc"] == ["query", "month"], item
    return f"422 {item['type']} loc={item['loc']}"


def check_required_empty_string() -> str:
    """`?month=` 算「传了」，得到空字符串而不是 422。"""
    r = client.get("/reports", params={"month": ""})
    assert r.status_code == 200, r.status_code
    assert r.json() == {"month": ""}, r.json()
    return "?month= → 200 而非 422"


def check_list_repeated_keys() -> str:
    """重复键解析成列表。"""
    r = client.get("/tags?tag=a&tag=b")
    assert r.json() == {"tag": ["a", "b"], "count": 2}, r.json()
    assert client.get("/tags").json() == {"tag": [], "count": 0}
    return str(r.json())


def check_comma_not_split() -> str:
    """逗号不会被自动拆分——本章最重要的反直觉点。"""
    r = client.get("/tags?tag=a,b")
    assert r.json() == {"tag": ["a,b"], "count": 1}, r.json()
    # 想要逗号拆分必须自己写
    assert client.get("/tags-csv?tag=a,b,c").json() == {"tag": ["a", "b", "c"]}
    return f"内置 {r.json()}；自解析 {client.get('/tags-csv?tag=a,b,c').json()}"


def check_bool() -> str:
    """bool 的六种写法 + 非法值。"""
    cases = {"true": True, "1": True, "yes": True, "0": False, "false": False}
    for raw, expected in cases.items():
        got = client.get("/flags", params={"flag": raw}).json()["flag"]
        assert got is expected, (raw, got, expected)
    assert client.get("/flags", params={"flag": "maybe"}).status_code == 422
    # 键存在但无值 → 422，不会当成 True
    assert client.get("/flags?flag").status_code == 422
    return "true/1/yes→True, 0/false→False, maybe/裸键→422"


def check_encoding() -> str:
    """中文与空格。"""
    assert client.get("/greet", params={"name": "北京"}).json()["name"] == "北京"
    assert client.get("/greet", params={"name": "hello world"}).json()["name"] == "hello world"
    return "北京 / hello world 均正确解码"


def check_openapi() -> str:
    """required 与 default 必须如实反映可选性。"""
    schema = client.get("/openapi.json").json()
    params = {p["name"]: p for p in schema["paths"]["/search"]["get"]["parameters"]}
    assert params["q"]["required"] is False, params["q"]
    assert params["limit"]["schema"]["default"] == 10, params["limit"]

    rep = schema["paths"]["/reports"]["get"]["parameters"][0]
    assert rep["required"] is True, rep

    tag = schema["paths"]["/tags"]["get"]["parameters"][0]
    assert tag["schema"]["type"] == "array", tag
    assert tag["schema"]["items"] == {"type": "string"}, tag
    return "q:required=false, limit:default=10, month:required=true, tag:array"


CHECKS = [
    ("可选参数取默认值", check_optional_defaults),
    ("传参覆盖默认值", check_override),
    ("必填缺失 422 missing", check_required_missing),
    ("空字符串算已传", check_required_empty_string),
    ("list 用重复键", check_list_repeated_keys),
    ("逗号不自动拆分", check_comma_not_split),
    ("bool 六种写法", check_bool),
    ("中文与空格编码", check_encoding),
    ("OpenAPI required/default", check_openapi),
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
