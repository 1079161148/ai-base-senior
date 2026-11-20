"""第 51 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)
star = TestClient(main.star_app)
GOOD = {"Origin": "http://localhost:3000"}
EVIL = {"Origin": "http://evil.com"}


def preflight(method: str = "POST", headers: dict[str, str] | None = None) -> dict[str, str]:
    base = {**GOOD, "Access-Control-Request-Method": method}
    return {**base, **(headers or {})}


def check_allowed_origin_headers() -> str:
    """允许的 origin → 回声 + credentials + expose。"""
    r = client.get("/data", headers=GOOD)
    assert r.status_code == 200, r.status_code
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000", dict(r.headers)
    assert r.headers["access-control-allow-credentials"] == "true", dict(r.headers)
    assert r.headers["access-control-expose-headers"] == "X-Total", dict(r.headers)
    return "ACAO=echo, credentials=true, expose=X-Total"


def check_vary_origin() -> str:
    """`Vary: Origin` 必须在（否则 CDN 会把一个 origin 的头缓存给另一个）。"""
    ok = client.get("/data", headers=GOOD)
    evil = client.get("/data", headers=EVIL)
    assert ok.headers["vary"] == "Origin", dict(ok.headers)
    assert evil.headers["vary"] == "Origin", dict(evil.headers)
    return "两个响应的 Vary 都是 Origin"


def check_disallowed_origin_still_200() -> str:
    """不允许的 origin：仍是 200，只是**没有** CORS 头（由浏览器拦）。"""
    r = client.get("/data", headers=EVIL)
    assert r.status_code == 200, r.status_code
    assert "access-control-allow-origin" not in r.headers, dict(r.headers)
    assert r.json() == {"items": [1, 2, 3]}, r.json()
    return "200 但无 ACAO（服务端不拒绝，浏览器拒绝）"


def check_no_origin_no_cors_header() -> str:
    """没有 `Origin` 头（同源/服务端调用）→ 不加 CORS 头。"""
    r = client.get("/data")
    assert r.status_code == 200
    assert "access-control-allow-origin" not in r.headers, dict(r.headers)
    return "无 Origin → 无 CORS 头"


def check_preflight_ok() -> str:
    """预检 200 + methods/headers/max-age。"""
    r = client.options("/data", headers=preflight("POST", {"Access-Control-Request-Headers": "X-Token"}))
    assert r.status_code == 200, (r.status_code, r.text)
    assert r.headers["access-control-allow-methods"] == "GET, POST", dict(r.headers)
    assert r.headers["access-control-max-age"] == "600", dict(r.headers)
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000"
    return "200, methods=GET, POST, max-age=600"


def check_preflight_allow_headers_includes_default_safelist() -> str:
    """`allow_headers` 会并上 Accept/Accept-Language/Content-Language/Content-Type。"""
    r = client.options(
        "/data", headers=preflight("POST", {"Access-Control-Request-Headers": "X-Token"})
    )
    allowed = r.headers["access-control-allow-headers"]
    for name in ("Accept", "Accept-Language", "Content-Language", "Content-Type", "X-Token"):
        assert name in allowed, (name, allowed)
    return f"allow-headers={allowed}"


def check_preflight_disallowed_origin() -> str:
    """预检不允许的 origin → 400 `Disallowed CORS origin`。"""
    r = client.options(
        "/data",
        headers={"Origin": "http://evil.com", "Access-Control-Request-Method": "POST"},
    )
    assert r.status_code == 400, (r.status_code, r.text)
    assert r.text == "Disallowed CORS origin", r.text
    return "400 Disallowed CORS origin"


def check_preflight_disallowed_method() -> str:
    """预检不允许的 method → 400。"""
    r = client.options("/data", headers=preflight("DELETE"))
    assert r.status_code == 400, (r.status_code, r.text)
    assert r.text == "Disallowed CORS method", r.text
    return "400 Disallowed CORS method"


def check_preflight_disallowed_header() -> str:
    """预检不允许的 header → 400。"""
    r = client.options(
        "/data", headers=preflight("GET", {"Access-Control-Request-Headers": "X-Not-Allowed"})
    )
    assert r.status_code == 400, (r.status_code, r.text)
    assert r.text == "Disallowed CORS headers", r.text
    return "400 Disallowed CORS headers"


def check_404_has_cors_headers() -> str:
    """CORS 是中间件 → 404 也带 ACAO（对比：CORS 不是路由级）。"""
    r = client.get("/nope", headers=GOOD)
    assert r.status_code == 404, r.status_code
    assert r.headers["access-control-allow-origin"] == "http://localhost:3000", dict(r.headers)
    return "404 也带 ACAO"


def check_credentials_with_star_echoes_origin() -> str:
    """`allow_origins=["*"]` + credentials → 回声**具体 origin**，不是 `*`。"""
    r = star.get("/data", headers={"Origin": "http://any.com"})
    assert r.headers["access-control-allow-origin"] == "http://any.com", dict(r.headers)
    assert r.headers["access-control-allow-credentials"] == "true"
    return "ACAO=http://any.com（不是 *）"


def check_cors_is_not_auth() -> str:
    """CORS 不阻止服务端返回数据：非浏览器客户端带任意 Origin 也能读。"""
    r = client.get("/data", headers=EVIL)
    assert r.json()["items"] == [1, 2, 3], r.json()
    return "数据照样返回——CORS 只约束浏览器"


def check_expose_headers_only_listed() -> str:
    """`expose_headers` 只暴露列出的头（其它自定义头浏览器读不到）。"""
    r = client.get("/data", headers=GOOD)
    exposed = r.headers["access-control-expose-headers"]
    assert exposed == "X-Total", exposed
    assert "X-Secret" not in exposed
    return f"expose={exposed}"


def check_star_app_allows_any_origin() -> str:
    """`*` 模式下任意 origin 都放行。"""
    for origin in ("http://a.com", "https://b.org:8443"):
        r = star.get("/data", headers={"Origin": origin})
        assert r.headers["access-control-allow-origin"] == origin, (origin, dict(r.headers))
    return "任意 origin 回声"


CHECKS = [
    ("允许的 origin", check_allowed_origin_headers),
    ("Vary: Origin", check_vary_origin),
    ("非法 origin 仍 200", check_disallowed_origin_still_200),
    ("无 Origin 无头", check_no_origin_no_cors_header),
    ("预检通过", check_preflight_ok),
    ("预检默认头白名单", check_preflight_allow_headers_includes_default_safelist),
    ("预检非法 origin", check_preflight_disallowed_origin),
    ("预检非法 method", check_preflight_disallowed_method),
    ("预检非法 header", check_preflight_disallowed_header),
    ("404 也带 CORS", check_404_has_cors_headers),
    ("* + credentials", check_credentials_with_star_echoes_origin),
    ("CORS 不是鉴权", check_cors_is_not_auth),
    ("expose 白名单", check_expose_headers_only_listed),
    ("星号模式", check_star_app_allows_any_origin),
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