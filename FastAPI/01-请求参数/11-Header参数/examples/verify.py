"""第 11 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def check_standard_header() -> str:
    """user_agent 自动对应 User-Agent。"""
    r = client.get("/me", headers={"User-Agent": "pytest/1.0"})
    assert r.json()["user_agent"] == "pytest/1.0", r.json()
    return r.json()["user_agent"]


def check_case_insensitive() -> str:
    """头名大小写不敏感。"""
    for raw in ("user-agent", "USER-AGENT", "User-Agent"):
        assert client.get("/me", headers={raw: "x/1"}).json()["user_agent"] == "x/1", raw
    return "三种大小写都能读到"


def check_custom_header() -> str:
    """x_token ↔ X-Token。"""
    assert client.get("/me", headers={"X-Token": "tk"}).json()["x_token"] == "tk"
    assert client.get("/me", headers={"x-token": "tk2"}).json()["x_token"] == "tk2"
    return "tk / tk2 均正确"


def check_list_header() -> str:
    """重复头解析成列表。"""
    r = client.get("/tags", headers=[("X-Tag", "a"), ("X-Tag", "b")])
    assert r.json() == {"x_tag": ["a", "b"], "count": 2}, r.json()
    return str(r.json())


def check_required_missing() -> str:
    """必填头缺失 422，loc 用连字符形式。"""
    r = client.get("/secure")
    assert r.status_code == 422, r.status_code
    item = r.json()["detail"][0]
    assert item["type"] == "missing", item
    assert item["loc"] == ["header", "x-api-key"], item
    assert client.get("/secure", headers={"X-Api-Key": "k123"}).json() == {"key_prefix": "k12***"}
    return f"422 loc={item['loc']}"


def check_no_convert() -> str:
    """convert_underscores=False 时只认下划线头，标准头读不到。"""
    r = client.get("/no-convert", headers={"user_agent": "raw/1.0"})
    assert r.json()["user_agent"] == "raw/1.0", r.json()
    r = client.get("/no-convert", headers={"User-Agent": "ua/1.0"})
    assert r.json()["user_agent"] is None, r.json()
    return "下划线头→raw/1.0；标准头→None"


def check_missing_is_none() -> str:
    """可选头缺失为 None。

    【注意】TestClient/httpx 会自动带 `User-Agent: testclient`，
           所以 `user_agent` 不会是 None——这不是框架行为，是客户端行为。
    """
    data = client.get("/me").json()
    assert data["x_token"] is None and data["accept_language"] is None, data
    assert data["user_agent"] == "testclient", data
    return f"x_token=None, accept_language=None, user_agent={data['user_agent']}（客户端默认）"


def check_openapi() -> str:
    """OpenAPI 里 in=header，名字是连字符形式。"""
    schema = client.get("/openapi.json").json()
    params = {p["name"]: p for p in schema["paths"]["/me"]["get"]["parameters"]}
    assert "user-agent" in params, sorted(params)
    assert params["user-agent"]["in"] == "header", params["user-agent"]
    assert params["user-agent"]["required"] is False, params["user-agent"]
    # 必填头在文档里 required=true
    secure = schema["paths"]["/secure"]["get"]["parameters"][0]
    assert secure["required"] is True and secure["name"] == "x-api-key", secure
    return "user-agent in=header required=false；x-api-key required=true"


def check_idempotency() -> str:
    """幂等键：第二次相同键返回 cached。"""
    first = client.post("/orders", headers={"Idempotency-Key": "k1", "X-Trace-Id": "t1"}).json()
    second = client.post("/orders", headers={"Idempotency-Key": "k1", "X-Trace-Id": "t1"}).json()
    assert first["status"] == "created", first
    assert second["status"] == "cached", second
    assert first["order_id"] == second["order_id"], (first, second)
    # 不同键 → 新订单
    third = client.post("/orders", headers={"Idempotency-Key": "k2"}).json()
    assert third["status"] == "created" and third["order_id"] != first["order_id"], third
    return f"同键 → cached {second['order_id']}；新键 → {third['order_id']}"


CHECKS = [
    ("标准头自动对应", check_standard_header),
    ("头名大小写不敏感", check_case_insensitive),
    ("自定义头", check_custom_header),
    ("重复头解析为列表", check_list_header),
    ("必填头缺失 422", check_required_missing),
    ("convert_underscores=False", check_no_convert),
    ("缺失时为 None", check_missing_is_none),
    ("OpenAPI in=header", check_openapi),
    ("幂等键走头", check_idempotency),
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
