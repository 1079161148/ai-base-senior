"""第 44 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)
KEY = {"X-API-Key": "key-alice"}
BEARER = {"Authorization": "Bearer token-1"}


def schema() -> dict:
    return client.get("/openapi.json").json()


def route_security(path: str) -> list | None:
    paths = schema()["paths"]
    operation = next(iter(paths[path].values()))
    return operation.get("security")


def check_schemes_registered() -> str:
    """`Security` 把方案登记进 `securitySchemes`（实测两个）。"""
    schemes = schema()["components"]["securitySchemes"]
    assert set(schemes) == {"APIKeyHeader", "BearerAuth"}, sorted(schemes)
    api_key = schemes["APIKeyHeader"]
    assert api_key["type"] == "apiKey", api_key
    assert api_key["in"] == "header", api_key
    assert api_key["name"] == "X-API-Key", api_key
    bearer = schemes["BearerAuth"]
    assert bearer["type"] == "http" and bearer["scheme"] == "bearer", bearer
    return f"schemes={sorted(schemes)}"


def check_scheme_name_overridable() -> str:
    """`scheme_name` 决定 securitySchemes 里的键名。"""
    schemes = schema()["components"]["securitySchemes"]
    assert "BearerAuth" in schemes, sorted(schemes)
    assert "HTTPBearer" not in schemes, sorted(schemes)
    return "scheme_name=BearerAuth（非默认类名）"


def check_route_security_ref() -> str:
    """路由的 `security` 字段引用方案名。"""
    assert route_security("/key") == [{"APIKeyHeader": []}], route_security("/key")
    assert route_security("/bearer") == [{"BearerAuth": []}], route_security("/bearer")
    return "/key → APIKeyHeader, /bearer → BearerAuth"


def check_decorator_security() -> str:
    """装饰器位置 `dependencies=[Security(...)]` 同样进 `security`。"""
    assert route_security("/audit") == [{"APIKeyHeader": []}], route_security("/audit")
    return "dependencies=[Security(...)] 也登记"


def check_depends_header_not_registered() -> str:
    """用 `Depends` + `Header` 不会被登记为 security。"""
    assert route_security("/plain") is None, route_security("/plain")
    params = schema()["paths"]["/plain"]["get"]["parameters"]
    assert [p["name"] for p in params] == ["X-API-Key"], params
    assert params[0]["in"] == "header", params[0]
    return "只是普通 header 参数，无 security、无锁图标"


def check_missing_key_is_401() -> str:
    """缺 `X-API-Key`：方案自己拒绝，返回 **401**（不是 403）。"""
    r = client.get("/key")
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.json() == {"detail": "Not authenticated"}, r.json()
    return "401 Not authenticated（纠正「403」的旧印象）"


def check_missing_bearer_is_401() -> str:
    """缺 `Authorization: Bearer`：同样 401。"""
    r = client.get("/bearer")
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.json() == {"detail": "Not authenticated"}, r.json()
    return "401 Not authenticated"


def check_wrong_scheme_rejected_before_handler() -> str:
    """`Authorization: Basic xxx` → 401，且自定义处理函数根本不被调用。"""
    r = client.get("/bearer", headers={"Authorization": "Basic token-1"})
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.json() == {"detail": "Not authenticated"}, r.json()
    return "scheme 不符 → 方案层直接 401"


def check_valid_key_injects_value() -> str:
    """正确 key → 注入返回值。"""
    r = client.get("/key", headers=KEY)
    assert r.status_code == 200 and r.json() == {"user": "alice"}, r.text
    return "user=alice"


def check_invalid_key_401_custom() -> str:
    """值错 → 自己抛的 401 + `WWW-Authenticate`。"""
    r = client.get("/key", headers={"X-API-Key": "bad"})
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.json()["detail"] == "X-API-Key 无效", r.json()
    assert r.headers["www-authenticate"] == "ApiKey", dict(r.headers)
    return "401 + WWW-Authenticate: ApiKey"


def check_or_semantics() -> str:
    """两个 `auto_error=False` 方案 → OpenAPI 里是 OR（两个 dict）。"""
    sec = route_security("/either-or")
    assert sec == [{"APIKeyHeader": []}, {"BearerAuth": []}], sec
    assert client.get("/either-or", headers=KEY).json() == {"user": "alice"}
    assert client.get("/either-or", headers=BEARER).json() == {"user": "alice"}
    r = client.get("/either-or")
    assert r.status_code == 401, r.status_code
    return "security=[{APIKeyHeader},{BearerAuth}]，任一满足即可"


def check_default_value_does_not_skip() -> str:
    """参数写 `= None` 不会让依赖变可选，无头仍 401。"""
    r = client.get("/either")
    assert r.status_code == 401, (r.status_code, r.text)
    return "默认值不跳过依赖"


def check_global_security_registered() -> str:
    """全局 `FastAPI(dependencies=[Security(...)])` 也登记到 securitySchemes。"""
    probe = TestClient(main.probe_app).get("/openapi.json").json()
    assert "APIKeyHeader" in probe["components"]["securitySchemes"]
    assert probe["paths"]["/g"]["get"]["security"] == [{"APIKeyHeader": []}]
    return "全局依赖也进 security"


def check_docs_served() -> str:
    """/docs 正常返回（Authorize 按钮需人工确认）。"""
    assert client.get("/docs").status_code == 200
    html = client.get("/docs").text
    assert "swagger-ui" in html.lower(), html[:200]
    return "/docs 200，含 swagger-ui"


CHECKS = [
    ("securitySchemes", check_schemes_registered),
    ("scheme_name", check_scheme_name_overridable),
    ("路由 security", check_route_security_ref),
    ("装饰器位置", check_decorator_security),
    ("Depends 不登记", check_depends_header_not_registered),
    ("缺 key 401", check_missing_key_is_401),
    ("缺 bearer 401", check_missing_bearer_is_401),
    ("错 scheme", check_wrong_scheme_rejected_before_handler),
    ("正确 key", check_valid_key_injects_value),
    ("错 key", check_invalid_key_401_custom),
    ("OR 语义", check_or_semantics),
    ("默认值不跳过", check_default_value_does_not_skip),
    ("全局 Security", check_global_security_registered),
    ("/docs", check_docs_served),
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