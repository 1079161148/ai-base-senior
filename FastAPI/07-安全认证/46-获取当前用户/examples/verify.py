"""第 46 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)
H = {"Authorization": "Bearer token-alice"}


def reset() -> None:
    main.CALLS.clear()


def check_login_returns_token() -> str:
    """登录返回本章映射表里的 token。"""
    r = client.post("/token", data={"username": "alice", "password": "alice123"})
    assert r.status_code == 200, (r.status_code, r.text)
    assert r.json() == {"access_token": "token-alice", "token_type": "bearer"}, r.json()
    return f'access_token={r.json()["access_token"]}'


def check_me_ok() -> str:
    """有效 token → 用户信息，且**不含**哈希字段。"""
    r = client.get("/users/me", headers=H)
    assert r.status_code == 200, (r.status_code, r.text)
    body = r.json()
    assert body == {
        "username": "alice",
        "email": "alice@example.com",
        "full_name": "Alice Chen",
    }, body
    assert "hashed_password" not in body, body
    return f"keys={sorted(body)}"


def check_no_token_401() -> str:
    """缺 token → 401（方案层）。"""
    r = client.get("/users/me")
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.json() == {"detail": "Not authenticated"}, r.json()
    assert r.headers["www-authenticate"] == "Bearer", dict(r.headers)
    return "401 Not authenticated"


def check_bad_token_401() -> str:
    """token 查不到 → 401 + `error="invalid_token"`（不是 404）。"""
    r = client.get("/users/me", headers={"Authorization": "Bearer nope"})
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.json()["detail"] == "无效的 token", r.json()
    assert r.headers["www-authenticate"] == 'Bearer error="invalid_token"', dict(r.headers)
    return "401 无效的 token（不暴露用户是否存在）"


def check_disabled_user_400() -> str:
    """停用用户 → 400 Inactive user。"""
    r = client.get("/users/me", headers={"Authorization": "Bearer token-bob"})
    assert r.status_code == 400, (r.status_code, r.text)
    assert r.json()["detail"] == "Inactive user", r.json()
    return "400 Inactive user"


def check_wrong_password() -> str:
    """密码错 → 400（不区分用户名不存在）。"""
    r = client.post("/token", data={"username": "alice", "password": "x"})
    assert r.status_code == 400, r.status_code
    r2 = client.post("/token", data={"username": "ghost", "password": "x"})
    assert r2.json() == r.json(), (r.json(), r2.json())
    return "两种失败同文案（防枚举）"


def check_dependency_chain_cached() -> str:
    """依赖链同请求各执行一次。"""
    reset()
    r = client.get("/users/me/name", headers=H)
    assert r.status_code == 200, r.text
    assert r.json()["calls"] == ["get_current_user", "get_current_active_user"], r.json()
    return f'calls={r.json()["calls"]}'


def check_response_model_filters() -> str:
    """不加 `response_model` 时 `model_dump()` 含 `hashed_password`（反例）。"""
    reset()
    r = client.get("/users/me/raw", headers=H)
    assert r.status_code == 200, r.text
    fields = r.json()["dumped_fields"]
    assert "hashed_password" in fields, fields
    return f"dumped_fields={fields}（反例：必须用 response_model）"


def check_internal_model_not_in_schema() -> str:
    """内部 `User` 模型不进 `components.schemas`，只有 `UserOut`。"""
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    assert "UserOut" in schemas, sorted(schemas)
    assert "User" not in schemas, sorted(schemas)
    assert "hashed_password" not in schemas["UserOut"]["properties"], schemas["UserOut"]
    return f"schemas={sorted(schemas)}"


def check_security_ref() -> str:
    """受保护端点引用 oauth2 方案。"""
    sec = client.get("/openapi.json").json()["paths"]["/users/me"]["get"]["security"]
    assert sec == [{"OAuth2PasswordBearer": []}], sec
    return f"security={sec}"


def check_optional_user_greet() -> str:
    """可选登录：匿名与登录都 200。"""
    anon = client.get("/greet")
    assert anon.json() == {"message": "你好，游客"}, anon.json()
    auth = client.get("/greet", headers=H)
    assert auth.json() == {"message": "你好，Alice Chen"}, auth.json()
    return "匿名→游客；登录→Alice Chen"


def check_cache_not_across_requests() -> str:
    """依赖缓存不跨请求：两次请求 → 每组各一次。"""
    reset()
    client.get("/users/me", headers=H)
    client.get("/users/me", headers=H)
    assert main.CALLS == [
        "get_current_user",
        "get_current_active_user",
        "get_current_user",
        "get_current_active_user",
    ], main.CALLS
    return f"CALLS={main.CALLS}（两次请求各一次）"


CHECKS = [
    ("登录发 token", check_login_returns_token),
    ("当前用户", check_me_ok),
    ("缺 token 401", check_no_token_401),
    ("无效 token 401", check_bad_token_401),
    ("停用用户 400", check_disabled_user_400),
    ("密码错 400", check_wrong_password),
    ("依赖链缓存", check_dependency_chain_cached),
    ("response_model 过滤", check_response_model_filters),
    ("内部模型不进 schema", check_internal_model_not_in_schema),
    ("security 引用", check_security_ref),
    ("可选用户", check_optional_user_greet),
    ("缓存不跨请求", check_cache_not_across_requests),
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