"""第 24 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def check_injected_headers() -> str:
    """注入 Response 设的头会真的发出去。"""
    r = client.get("/headers/basic")
    assert r.status_code == 200, r.text
    assert r.headers["x-request-id"] == "req-abc-123", dict(r.headers)
    assert r.headers["x-ratelimit-remaining"] == "99", dict(r.headers)
    return f'X-Request-Id={r.headers["x-request-id"]}'


def check_header_case_insensitive() -> str:
    """头名大小写不敏感。"""
    h = client.get("/headers/basic").headers
    assert h["X-Request-ID"] == h["x-request-id"] == "req-abc-123"
    return "大小写三种写法都能取到"


def check_jsonresponse_headers() -> str:
    """JSONResponse 自定义头 + 绕过响应模型。"""
    r = client.get("/headers/direct")
    assert r.headers["x-cache"] == "HIT", dict(r.headers)
    assert r.headers["x-edge"] == "sh-01", dict(r.headers)
    assert r.json()["extra"] == "不会被过滤", "JSONResponse 不走响应模型"
    return "自定义头 + 字段未被过滤"


def check_media_type() -> str:
    """PlainTextResponse 的媒体类型。"""
    r = client.get("/headers/text")
    assert r.headers["content-type"].startswith("text/plain"), r.headers["content-type"]
    assert "charset=utf-8" in r.headers["content-type"], r.headers["content-type"]
    assert r.text == "ok"
    return f'content-type={r.headers["content-type"]}'


def check_set_cookie() -> str:
    """set_cookie 生成的 Set-Cookie 头。"""
    r = client.post("/headers/login")
    cookie = r.headers["set-cookie"]
    assert "session=token-123" in cookie, cookie
    assert "HttpOnly" in cookie, cookie
    assert "Max-Age=3600" in cookie, cookie
    assert "SameSite=lax" in cookie, cookie
    return f"Set-Cookie 含 HttpOnly/Max-Age/SameSite"


def check_multiple_set_cookie() -> str:
    """多个 Set-Cookie：Starlette 用多行头，客户端 headers 合并成一行。"""
    r = client.post("/headers/multi-cookie")
    raw = r.headers.get_list("set-cookie") if hasattr(r.headers, "get_list") else None
    merged = r.headers["set-cookie"]
    assert "a=1" in merged and "b=2" in merged, merged
    return f"两条 Set-Cookie{'（get_list 可用）' if raw else ''}"


def check_openapi_headers_doc() -> str:
    """OpenAPI 里的响应头文档。"""
    schema = client.get("/openapi.json").json()
    resp = schema["paths"]["/headers/documented"]["get"]["responses"]["200"]
    assert "X-RateLimit-Remaining" in resp["headers"], resp
    desc = resp["headers"]["X-RateLimit-Remaining"]["description"]
    assert desc == "剩余配额", desc
    return f"文档声明了 X-RateLimit-Remaining"


def check_doc_headers_not_sent() -> str:
    """文档里声明的头不会真的发送。"""
    r = client.get("/headers/documented")
    assert "x-ratelimit-remaining" not in {k.lower() for k in r.headers}, dict(r.headers)
    return "文档有、实际无（需自己 set）"


def check_unicode_header_value() -> str:
    """头值含中文：Starlette 用 latin-1 编码，会失败。"""
    from fastapi import FastAPI, Response

    probe = FastAPI()

    @probe.get("/cn")
    def cn(response: Response):  # noqa: ANN202
        response.headers["X-Note"] = "中文"
        return {"ok": True}

    c = TestClient(probe, raise_server_exceptions=False)
    r = c.get("/cn")
    if r.status_code == 500:
        return "500（latin-1 编码失败）—— 头值必须纯 ASCII"
    return f"未报错，实际值={r.headers.get('x-note')!r}"


def check_content_length_recalculated() -> str:
    """手改 Content-Length 会被框架覆盖。"""
    from fastapi import FastAPI, Response

    probe = FastAPI()

    @probe.get("/cl")
    def cl(response: Response):  # noqa: ANN202
        response.headers["Content-Length"] = "999"
        return {"a": 1}

    r = TestClient(probe).get("/cl")
    actual = r.headers["content-length"]
    assert actual != "999", "框架会按实际 body 重算 Content-Length"
    return f"声明 999 → 实际头 {actual!r}（多值合并，别手改）"


CHECKS = [
    ("注入 Response 加头", check_injected_headers),
    ("头名大小写不敏感", check_header_case_insensitive),
    ("JSONResponse 带头", check_jsonresponse_headers),
    ("媒体类型", check_media_type),
    ("Set-Cookie", check_set_cookie),
    ("多个 Set-Cookie", check_multiple_set_cookie),
    ("OpenAPI 头文档", check_openapi_headers_doc),
    ("文档头不会真发", check_doc_headers_not_sent),
    ("中文头值", check_unicode_header_value),
    ("Content-Length 被重算", check_content_length_recalculated),
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
