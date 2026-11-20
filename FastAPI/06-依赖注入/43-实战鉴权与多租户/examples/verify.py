"""第 43 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)
A = {"X-Token": "tok-a"}
B = {"X-Token": "tok-b"}


def check_missing_token() -> str:
    """无 token → 401 + challenge。"""
    r = client.get("/items")
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.headers["www-authenticate"] == "Bearer", dict(r.headers)
    return "401 + WWW-Authenticate"


def check_invalid_token() -> str:
    """错误 token → 401。"""
    r = client.get("/items", headers={"X-Token": "nope"})
    assert r.status_code == 401, (r.status_code, r.text)
    assert "error=\"invalid_token\"" in r.headers["www-authenticate"], dict(r.headers)
    return "401 invalid_token"


def check_disabled_tenant() -> str:
    """租户停用 → 403（认证通过、授权失败）。"""
    r = client.get("/items", headers={"X-Token": "tok-off"})
    assert r.status_code == 403, (r.status_code, r.text)
    assert "停用" in r.json()["detail"], r.json()
    return "403 已停用"


def check_tenant_isolation_list() -> str:
    """列表按租户过滤。"""
    a = client.get("/items", headers=A).json()
    b = client.get("/items", headers=B).json()
    assert a["count"] == 2 and {i["tenant"] for i in a["items"]} == {"t-a"}, a
    assert b["count"] == 1 and b["items"][0]["tenant"] == "t-b", b
    return f'alice={a["count"]} 条, bob={b["count"]} 条'


def check_own_item_ok() -> str:
    """读自己的资源正常。"""
    r = client.get("/items/1", headers=A)
    assert r.status_code == 200, (r.status_code, r.text)
    assert r.json()["name"] == "A 租户的键盘", r.json()
    return "200 自己的商品"


def check_cross_tenant_404() -> str:
    """跨租户访问返回 404（不是 403）。"""
    r = client.get("/items/1", headers=B)
    assert r.status_code == 404, (r.status_code, r.text)
    same = client.get("/items/999", headers=B)
    assert same.status_code == 404, same.status_code
    # 文案只带客户端已知的 id，不出现「属于别人」这类信息
    assert r.json()["detail"] == "商品 1 不存在", r.json()
    assert same.json()["detail"] == "商品 999 不存在", same.json()
    assert set(r.json()) == set(same.json()), (r.json(), same.json())
    return "跨租户 404 与不存在结构一致"


def check_create_binds_tenant() -> str:
    """创建自动绑定当前租户，且忽略请求体里的 tenant。"""
    r = client.post("/items", json={"name": "新商品", "tenant": "t-b"}, headers=A)
    assert r.status_code == 201, (r.status_code, r.text)
    body = r.json()
    assert body["tenant"] == "t-a", body
    # 创建后只有 A 能看到
    assert client.get(f"/items/{body['id']}", headers=A).status_code == 200
    assert client.get(f"/items/{body['id']}", headers=B).status_code == 404
    return f'id={body["id"]} 绑定 t-a'


def check_client_tenant_header_ignored() -> str:
    """客户端 X-Tenant 不能改租户。"""
    r = client.get("/items", headers={**A, "X-Tenant": "t-b"})
    assert r.json()["tenant"] == "t-a", r.json()
    return "X-Tenant: t-b 被忽略"


def check_state_propagation() -> str:
    """依赖写入 request.state，端点可读。"""
    r = client.get("/whoami", headers=A)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["state_tenant"] == body["tenant"] == "t-a", body
    assert body["state_user"] == body["user"] == "alice", body
    return f'state_tenant={body["state_tenant"]}'


def check_role_exposed() -> str:
    """角色随上下文一起注入。"""
    body = client.get("/whoami", headers=A).json()
    assert body["role"] == "admin", body
    return "role=admin"


def check_openapi_has_token_param() -> str:
    """OpenAPI 暴露 X-Token，不暴露内部 tenant 参数。"""
    params = client.get("/openapi.json").json()["paths"]["/items"]["get"]["parameters"]
    names = [p["name"] for p in params]
    assert names == ["X-Token"], names
    return f"parameters={names}"


def check_404_detail_no_leak() -> str:
    """404 文案不泄露「存在但不属于你」。"""
    r = client.get("/items/3", headers=A)
    assert r.status_code == 404, r.status_code
    assert "不存在" in r.json()["detail"], r.json()
    assert "租户" not in r.json()["detail"], r.json()
    return "文案与不存在一致"


CHECKS = [
    ("缺 token", check_missing_token),
    ("错误 token", check_invalid_token),
    ("停用租户", check_disabled_tenant),
    ("列表隔离", check_tenant_isolation_list),
    ("自己的资源", check_own_item_ok),
    ("跨租户 404", check_cross_tenant_404),
    ("创建绑定租户", check_create_binds_tenant),
    ("忽略客户端租户", check_client_tenant_header_ignored),
    ("state 传递", check_state_propagation),
    ("角色注入", check_role_exposed),
    ("OpenAPI 参数", check_openapi_has_token_param),
    ("404 不泄露", check_404_detail_no_leak),
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