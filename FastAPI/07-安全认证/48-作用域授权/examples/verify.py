"""第 48 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def token_for(username: str, requested: str = "") -> str:
    data = {"username": username, "password": "x", "scope": requested}
    r = client.post("/token", data=data)
    assert r.status_code == 200, (r.status_code, r.text)
    return r.json()["access_token"]


def auth(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def security_of(path: str, method: str) -> list | None:
    paths = client.get("/openapi.json").json()["paths"]
    return paths[path][method].get("security")


def check_flows_scopes() -> str:
    """`OAuth2PasswordBearer(scopes=...)` 写进 `flows.password.scopes`。"""
    flow = client.get("/openapi.json").json()["components"]["securitySchemes"][
        "OAuth2PasswordBearer"
    ]["flows"]["password"]
    assert set(flow["scopes"]) == {"items:read", "items:write", "admin"}, flow["scopes"]
    assert flow["scopes"]["items:read"] == "读取商品", flow["scopes"]
    return f'scopes={sorted(flow["scopes"])}'


def check_route_scopes_in_openapi() -> str:
    """端点声明的 scopes 出现在 `security` 数组里。"""
    assert security_of("/items", "get") == [{"OAuth2PasswordBearer": ["items:read"]}]
    assert security_of("/items", "post") == [{"OAuth2PasswordBearer": ["items:write"]}]
    assert security_of("/items", "delete") == [
        {"OAuth2PasswordBearer": ["items:read", "items:write"]}
    ], security_of("/items", "delete")
    return "GET=read, POST=write, DELETE=read+write"


def check_decorator_scopes() -> str:
    """装饰器位置的 `Security(..., scopes=[...])` 同样生效。"""
    assert security_of("/audit", "get") == [{"OAuth2PasswordBearer": ["items:read"]}]
    r = client.get("/audit", headers=auth(token_for("alice", "items:read")))
    assert r.status_code == 200, r.text
    return "装饰器位置也可带 scopes"


def check_grant_is_intersection() -> str:
    """只授予「用户拥有 ∩ 客户端请求」。"""
    r = client.post(
        "/token",
        data={"username": "alice", "password": "x", "scope": "items:read items:write admin"},
    )
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["scopes"] == ["items:read"], body
    return f'alice 请求 3 个 → 只授予 {body["scopes"]}'


def check_empty_scope_user() -> str:
    """bob 没有任何 scope → 授予空列表。"""
    body = client.post(
        "/token", data={"username": "bob", "password": "x", "scope": "items:read"}
    ).json()
    assert body["scopes"] == [], body
    r = client.get("/items", headers=auth(body["access_token"]))
    assert r.status_code == 403, (r.status_code, r.text)
    return "bob scopes=[]，访问 /items → 403"


def check_read_allowed() -> str:
    """有 items:read → 200。"""
    r = client.get("/items", headers=auth(token_for("alice", "items:read")))
    assert r.status_code == 200, (r.status_code, r.text)
    assert r.json()["user"] == "alice", r.json()
    return "200 alice"


def check_write_denied_with_challenge() -> str:
    """缺 items:write → 403 + `scope="items:write"` + `insufficient_scope`。"""
    r = client.post("/items", headers=auth(token_for("alice", "items:read")))
    assert r.status_code == 403, (r.status_code, r.text)
    assert r.json()["detail"] == "缺少 scope: items:write", r.json()
    challenge = r.headers["www-authenticate"]
    assert challenge == 'Bearer scope="items:write" error="insufficient_scope"', challenge
    return challenge


def check_multi_scope_and_semantics() -> str:
    """多个 scope 是 AND：只有一个不够。"""
    only_read = auth(token_for("alice", "items:read"))
    r = client.delete("/items", headers=only_read)
    assert r.status_code == 403, (r.status_code, r.text)
    assert r.headers["www-authenticate"] == (
        'Bearer scope="items:read items:write" error="insufficient_scope"'
    ), r.headers["www-authenticate"]

    both = auth(token_for("admin", "items:read items:write"))
    ok = client.delete("/items", headers=both)
    assert ok.status_code == 200, (ok.status_code, ok.text)
    return "只有 read → 403；read+write → 200"


def check_admin_scope() -> str:
    """admin scope 单独控制后台。"""
    assert client.get("/admin", headers=auth(token_for("alice", "items:read"))).status_code == 403
    assert client.get("/admin", headers=auth(token_for("admin", "admin"))).status_code == 200
    return "alice→403, admin→200"


def check_no_token_401() -> str:
    """没 token 仍是 401（不是 403）。"""
    r = client.get("/items")
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.headers["www-authenticate"] == "Bearer", dict(r.headers)
    return "401 在 scope 校验之前"


def check_token_carries_scopes() -> str:
    """token 的 payload 带 `scopes`，且与授予一致。"""
    token = token_for("admin", "admin items:write")
    payload = main.jwt.decode_token(token)
    assert payload["scopes"] == ["admin", "items:write"], payload
    assert payload["sub"] == "admin", payload
    return f'scopes={payload["scopes"]}'


def check_scope_str_joined() -> str:
    """`SecurityScopes.scope_str` 用空格连接（多 scope 时的 challenge）。"""
    r = client.delete("/items", headers=auth(token_for("bob")))
    assert r.status_code == 403, r.status_code
    assert 'scope="items:read items:write"' in r.headers["www-authenticate"], dict(r.headers)
    return "scope_str 以空格连接"


CHECKS = [
    ("flows scopes", check_flows_scopes),
    ("路由 security 带 scopes", check_route_scopes_in_openapi),
    ("装饰器位置", check_decorator_scopes),
    ("授予取交集", check_grant_is_intersection),
    ("空 scope 用户", check_empty_scope_user),
    ("有 read 放行", check_read_allowed),
    ("缺 write 403", check_write_denied_with_challenge),
    ("多 scope 是 AND", check_multi_scope_and_semantics),
    ("admin scope", check_admin_scope),
    ("无 token 401", check_no_token_401),
    ("token 带 scopes", check_token_carries_scopes),
    ("scope_str 空格连接", check_scope_str_joined),
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