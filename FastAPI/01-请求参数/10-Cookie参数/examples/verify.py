"""第 10 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def check_missing_is_none() -> str:
    """可选 Cookie 缺失时为 None，不报错。"""
    data = client.get("/me").json()
    assert data == {"session_id": None, "theme": None}, data
    return str(data)


def check_read_cookie() -> str:
    """能读到传入的 Cookie。"""
    r = client.get("/me", cookies={"session_id": "xyz", "theme": "dark"})
    assert r.json() == {"session_id": "xyz", "theme": "dark"}, r.json()
    return str(r.json())


def check_set_cookie_header() -> str:
    """set_cookie 的关键属性必须出现在 Set-Cookie 头里。"""
    r = client.get("/login")
    header = r.headers.get("set-cookie", "")
    for part in ("session_id=", "HttpOnly", "Max-Age=3600", "Path=/", "SameSite=lax"):
        assert part in header, (part, header)
    # secure=False 时不应出现 Secure
    assert "Secure" not in header, header
    return header


def check_multiple_set_cookie() -> str:
    """多次 set_cookie → 多条 Set-Cookie 头。"""
    r = client.get("/set-many")
    headers = r.headers.get_list("set-cookie")
    assert len(headers) == 2, headers
    return f"{len(headers)} 条：{headers}"


def check_delete_cookie() -> str:
    """delete_cookie 发送 Max-Age=0。"""
    r = client.get("/logout")
    header = r.headers.get("set-cookie", "")
    assert "session_id=" in header and ("Max-Age=0" in header or "expires" in header.lower()), header
    return header


def check_case_sensitive_name() -> str:
    """Cookie 名大小写敏感。"""
    r = client.get("/me", cookies={"Session_Id": "upper"})
    assert r.json()["session_id"] is None, r.json()
    return "Session_Id 不会被 session_id 读到"


def check_value_not_decoded() -> str:
    """Cookie 值不自动 URL 解码，原样返回。"""
    r = client.get("/me", cookies={"session_id": "a%20b"})
    assert r.json()["session_id"] == "a%20b", r.json()
    return "a%20b 原样返回（未解码）"


def check_required_cookie() -> str:
    """必填 Cookie 缺失 → 422，loc 首段是 cookie。"""
    r = client.get("/must-have")
    assert r.status_code == 422, r.status_code
    item = r.json()["detail"][0]
    assert item["type"] == "missing" and item["loc"] == ["cookie", "tenant"], item
    assert client.get("/must-have", cookies={"tenant": "t1"}).json() == {"tenant": "t1"}
    return f"422 {item['type']} loc={item['loc']}"


def check_openapi_in_cookie() -> str:
    """OpenAPI 里必须标 in=cookie。"""
    schema = client.get("/openapi.json").json()
    params = {p["name"]: p for p in schema["paths"]["/me"]["get"]["parameters"]}
    assert params["session_id"]["in"] == "cookie", params["session_id"]
    assert params["session_id"]["required"] is False, params["session_id"]
    return "session_id in=cookie required=false"


CHECKS = [
    ("无 Cookie 时为 None", check_missing_is_none),
    ("读取 Cookie", check_read_cookie),
    ("set_cookie 响应头", check_set_cookie_header),
    ("多个 Cookie 多条头", check_multiple_set_cookie),
    ("delete_cookie", check_delete_cookie),
    ("Cookie 名大小写敏感", check_case_sensitive_name),
    ("Cookie 值不解码", check_value_not_decoded),
    ("必填 Cookie 422", check_required_cookie),
    ("OpenAPI in=cookie", check_openapi_in_cookie),
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
