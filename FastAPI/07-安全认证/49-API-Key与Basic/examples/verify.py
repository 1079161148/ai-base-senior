"""第 49 章 · 自动验收。运行：python verify.py"""

import base64
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import Security  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def basic(username: str, password: str) -> dict[str, str]:
    raw = base64.b64encode(f"{username}:{password}".encode()).decode()
    return {"Authorization": f"Basic {raw}"}


def check_four_schemes() -> str:
    """四种方案的 `securitySchemes` 字段。"""
    schemes = client.get("/openapi.json").json()["components"]["securitySchemes"]
    assert set(schemes) == {"APIKeyHeader", "APIKeyQuery", "APIKeyCookie", "BasicAuth"}, sorted(schemes)
    assert schemes["APIKeyHeader"]["in"] == "header"
    assert schemes["APIKeyHeader"]["name"] == "X-API-Key"
    assert schemes["APIKeyQuery"]["in"] == "query"
    assert schemes["APIKeyQuery"]["name"] == "api_key"
    assert schemes["APIKeyCookie"]["in"] == "cookie"
    assert schemes["BasicAuth"] == {"type": "http", "scheme": "basic"}, schemes["BasicAuth"]
    return f"schemes={sorted(schemes)}"


def check_header_key_ok() -> str:
    """有效 header key → 200。"""
    r = client.get("/machine/ping", headers={"X-API-Key": "key-service-a"})
    assert r.status_code == 200 and r.json() == {"owner": "service-a"}, r.text
    return "owner=service-a"


def check_key_rotation() -> str:
    """轮换期旧 key 仍可用。"""
    r = client.get("/machine/ping", headers={"X-API-Key": "key-service-a-old"})
    assert r.json() == {"owner": "service-a"}, r.json()
    return "旧 key → 同一 owner（可无缝轮换）"


def check_missing_key_401() -> str:
    """缺 key → 401 + `WWW-Authenticate: APIKey`（注意大写 APIKey）。"""
    r = client.get("/machine/ping")
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.json() == {"detail": "Not authenticated"}, r.json()
    assert r.headers["www-authenticate"] == "APIKey", dict(r.headers)
    return "401 + WWW-Authenticate: APIKey"


def check_invalid_key_401() -> str:
    """无效 key → 401（自己抛，带 ApiKey 头）。"""
    r = client.get("/machine/ping", headers={"X-API-Key": "zzz"})
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.json()["detail"] == "X-API-Key 无效", r.json()
    return "401 X-API-Key 无效"


def check_query_key() -> str:
    """query 位置取 key（不推荐，但可用）。"""
    assert client.get("/machine/query").status_code == 401
    r = client.get("/machine/query", params={"api_key": "key-service-b"})
    assert r.status_code == 200 and r.json() == {"owner": "service-b"}, r.text
    return "?api_key=... → service-b"


def check_cookie_key() -> str:
    """cookie 位置取 key。"""
    r = client.get("/machine/cookie", cookies={"session_key": "key-service-a"})
    assert r.status_code == 200 and r.json() == {"owner": "service-a"}, r.text
    assert client.get("/machine/cookie").status_code == 401
    return "cookie session_key 生效"


def check_basic_missing() -> str:
    """Basic 缺凭证 → 401 + `Basic realm="ch49-demo"`。"""
    r = client.get("/basic/me")
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.headers["www-authenticate"] == 'Basic realm="ch49-demo"', dict(r.headers)
    return '401 Basic realm="ch49-demo"'


def check_basic_ok() -> str:
    """Basic 正确 → 200。"""
    r = client.get("/basic/me", headers=basic("alice", "alice123"))
    assert r.status_code == 200 and r.json() == {"user": "alice"}, r.text
    return "user=alice"


def check_basic_wrong() -> str:
    """Basic 密码错 → 401。"""
    r = client.get("/basic/me", headers=basic("alice", "nope"))
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.json()["detail"] == "用户名或密码错误", r.json()
    return "401"


def check_basic_not_plaintext() -> str:
    """Basic 只是 base64，不是加密（可解出明文）。"""
    header = basic("alice", "alice123")["Authorization"]
    decoded = base64.b64decode(header.split(" ", 1)[1]).decode()
    assert decoded == "alice:alice123", decoded
    return "base64 可逆 → 必须走 HTTPS"


def check_security_auto_error_typeerror() -> str:
    """`Security(scheme, auto_error=False)` 直接 TypeError（常见误写）。"""
    error = ""
    try:
        Security(main.api_key_header, auto_error=False)
    except TypeError as exc:
        error = str(exc)
    assert "auto_error" in error, error
    return f"TypeError: {error}"


def check_or_combination() -> str:
    """API Key 与 Basic 二选一。"""
    key = client.get("/any/whoami", headers={"X-API-Key": "key-service-a"})
    assert key.json() == {"identity": "service:service-a"}, key.json()
    user = client.get("/any/whoami", headers=basic("alice", "alice123"))
    assert user.json() == {"identity": "user:alice"}, user.json()
    none = client.get("/any/whoami")
    assert none.status_code == 401, none.status_code
    return "key→service:service-a, basic→user:alice, 无→401"


def check_compare_digest_used() -> str:
    """实现里用的是 `secrets.compare_digest`（源码断言）。"""
    source = Path(__file__).with_name("main.py").read_text(encoding="utf-8")
    assert "secrets.compare_digest" in source, "必须用 compare_digest"
    assert "credentials.password ==" not in source, "不要用 == 比密码"
    return "main.py 使用 compare_digest"


CHECKS = [
    ("四种方案", check_four_schemes),
    ("header key", check_header_key_ok),
    ("key 轮换", check_key_rotation),
    ("缺 key 401", check_missing_key_401),
    ("无效 key", check_invalid_key_401),
    ("query key", check_query_key),
    ("cookie key", check_cookie_key),
    ("Basic 缺凭证", check_basic_missing),
    ("Basic 正确", check_basic_ok),
    ("Basic 错误", check_basic_wrong),
    ("Basic 非加密", check_basic_not_plaintext),
    ("Security auto_error", check_security_auto_error_typeerror),
    ("OR 组合", check_or_combination),
    ("compare_digest", check_compare_digest_used),
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