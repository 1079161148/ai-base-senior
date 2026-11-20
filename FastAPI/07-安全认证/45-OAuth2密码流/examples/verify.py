"""第 45 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)
FORM = {"username": "alice", "password": "alice123"}


def schema() -> dict:
    return client.get("/openapi.json").json()


def check_oauth2_scheme_shape() -> str:
    """`OAuth2PasswordBearer` → `type: oauth2` + `flows.password`。"""
    schemes = schema()["components"]["securitySchemes"]
    assert list(schemes) == ["OAuth2PasswordBearer"], sorted(schemes)
    scheme = schemes["OAuth2PasswordBearer"]
    assert scheme["type"] == "oauth2", scheme
    flow = scheme["flows"]["password"]
    assert flow["tokenUrl"] == "token", flow
    assert flow["scopes"] == {}, flow
    return f'type=oauth2, tokenUrl={flow["tokenUrl"]!r}, scopes={{}}'


def check_token_url_relative() -> str:
    """`tokenUrl` 按原样写入，相对路径不会自动补 `/`。"""
    flow = schema()["components"]["securitySchemes"]["OAuth2PasswordBearer"]["flows"]["password"]
    assert not flow["tokenUrl"].startswith("/"), flow
    return f'tokenUrl={flow["tokenUrl"]!r}（相对路径，客户端按当前 base 解析）'


def check_protected_route_security() -> str:
    """受保护端点引用该方案。"""
    sec = schema()["paths"]["/users/me"]["get"]["security"]
    assert sec == [{"OAuth2PasswordBearer": []}], sec
    return f"security={sec}"


def check_missing_token_401() -> str:
    """缺 token → 401 + `WWW-Authenticate: Bearer`。"""
    r = client.get("/users/me")
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.json() == {"detail": "Not authenticated"}, r.json()
    assert r.headers["www-authenticate"] == "Bearer", dict(r.headers)
    return "401 + WWW-Authenticate: Bearer"


def check_non_bearer_rejected() -> str:
    """`Authorization: abc`（缺 Bearer 前缀）→ 401。"""
    r = client.get("/users/me", headers={"Authorization": "abc"})
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.json()["detail"] == "Not authenticated", r.json()
    return "缺前缀被方案层拒绝"


def check_token_injected() -> str:
    """带 token → 注入去掉 `Bearer ` 之后的字符串。"""
    r = client.get("/users/me", headers={"Authorization": "Bearer abc"})
    assert r.status_code == 200 and r.json() == {"token": "abc"}, r.text
    return "token=abc（前缀已剥离）"


def check_form_login_ok() -> str:
    """表单登录成功，返回 OAuth2 规范字段。"""
    r = client.post("/token", data=FORM)
    assert r.status_code == 200, (r.status_code, r.text)
    body = r.json()
    assert body == {"access_token": "token-for-alice", "token_type": "bearer"}, body
    return f'access_token={body["access_token"]}, token_type={body["token_type"]}'


def check_json_login_422() -> str:
    """发 JSON → 422，`loc` 前缀是 `body`。"""
    r = client.post("/token", json=FORM)
    assert r.status_code == 422, (r.status_code, r.text)
    locs = [e["loc"] for e in r.json()["detail"]]
    assert ["body", "username"] in locs, locs
    return f"422, locs={locs}"


def check_wrong_password_400() -> str:
    """密码错 → 400（OAuth2 规范建议，不是 401）。"""
    r = client.post("/token", data={"username": "alice", "password": "wrong"})
    assert r.status_code == 400, (r.status_code, r.text)
    assert r.json()["detail"] == "用户名或密码错误", r.json()
    return "400 用户名或密码错误"


def check_disabled_user_400() -> str:
    """停用用户 → 400。"""
    r = client.post("/token", data={"username": "bob", "password": "bob123"})
    assert r.status_code == 400, (r.status_code, r.text)
    assert r.json()["detail"] == "用户已停用", r.json()
    return "400 用户已停用"


def check_optional_scheme() -> str:
    """`auto_error=False` → 无 token 得到 None。"""
    r = client.get("/users/me/soft")
    assert r.status_code == 200, r.text
    assert r.json() == {"anonymous": True, "token": None}, r.json()
    r2 = client.get("/users/me/soft", headers={"Authorization": "Bearer t"})
    assert r2.json() == {"anonymous": False, "token": "t"}, r2.json()
    return "无 token → None；有 token → 't'"


def check_scope_parsing() -> str:
    """表单 `scope="read write"` → `scopes=["read","write"]`（空格分隔）。"""
    body = client.post(
        "/token/debug",
        data={**FORM, "grant_type": "password", "scope": "read write", "client_id": "c1"},
    ).json()
    assert body["scopes"] == ["read", "write"], body
    assert body["grant_type"] == "password", body
    assert body["client_id"] == "c1", body
    return f'scopes={body["scopes"]}, grant_type={body["grant_type"]}'


def check_form_defaults() -> str:
    """不传的可选表单字段：`grant_type=None`、`scopes=[]`。"""
    body = client.post("/token/debug", data=FORM).json()
    assert body["grant_type"] is None, body
    assert body["scopes"] == [], body
    assert body["client_secret"] is None, body
    return "grant_type=None, scopes=[]"


def check_token_endpoint_is_form() -> str:
    """`/token` 的 OpenAPI 请求体只有 urlencoded，没有 JSON。

    【实测】请求体 schema 不是内联对象，而是 `$ref` 到
           `components.schemas.Body_login_token_post`（字段名由路径与方法拼成）
    """
    schemas = schema()
    content = schemas["paths"]["/token"]["post"]["requestBody"]["content"]
    assert list(content) == ["application/x-www-form-urlencoded"], list(content)
    ref = content["application/x-www-form-urlencoded"]["schema"]["$ref"]
    body_name = ref.split("/")[-1]
    assert body_name.startswith("Body_"), body_name
    body_schema = schemas["components"]["schemas"][body_name]
    props = body_schema["properties"]
    assert {"username", "password", "grant_type", "scope", "client_id"} <= set(props), sorted(props)
    assert body_schema["required"] == ["username", "password"], body_schema["required"]
    return f"content={list(content)}, schema={body_name}, required=username/password"


def check_docs_available() -> str:
    """/docs 可用（Authorize 面板需人工点）。"""
    assert client.get("/docs").status_code == 200
    return "/docs 200"


CHECKS = [
    ("oauth2 方案结构", check_oauth2_scheme_shape),
    ("tokenUrl 相对路径", check_token_url_relative),
    ("受保护路由 security", check_protected_route_security),
    ("缺 token 401", check_missing_token_401),
    ("缺 Bearer 前缀", check_non_bearer_rejected),
    ("token 注入", check_token_injected),
    ("表单登录", check_form_login_ok),
    ("JSON 登录 422", check_json_login_422),
    ("密码错 400", check_wrong_password_400),
    ("停用用户 400", check_disabled_user_400),
    ("可选登录", check_optional_scheme),
    ("scope 解析", check_scope_parsing),
    ("表单默认值", check_form_defaults),
    ("token 端点是 form", check_token_endpoint_is_form),
    ("/docs", check_docs_available),
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