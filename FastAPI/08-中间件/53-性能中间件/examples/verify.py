"""第 53 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)
GZIP = {"Accept-Encoding": "gzip"}


def host_client(base: str, app=main.host_app) -> TestClient:
    return TestClient(app, base_url=base, follow_redirects=False)


def check_small_not_compressed() -> str:
    """小于 `minimum_size=500` → 不压。"""
    r = client.get("/small", headers=GZIP)
    assert "content-encoding" not in r.headers, dict(r.headers)
    return "无 Content-Encoding"


def check_big_compressed() -> str:
    """超过阈值 → 压，且原长度远大于传输长度。"""
    r = client.get("/big", headers=GZIP)
    assert r.headers["content-encoding"] == "gzip", dict(r.headers)
    compressed = int(r.headers["content-length"])
    plain = len(r.text)
    assert compressed < plain // 10, (compressed, plain)
    return f"{plain}B → {compressed}B"


def check_identity_not_compressed() -> str:
    """客户端声明 `identity` → 不压。"""
    r = client.get("/big", headers={"Accept-Encoding": "identity"})
    assert "content-encoding" not in r.headers, dict(r.headers)
    # 【注意】中文是 3 字节/字，`content-length` 是字节数，不等于 `len(text)`
    assert int(r.headers["content-length"]) == 3200, dict(r.headers)
    assert len(r.text) == 1600, len(r.text)
    return "identity → 3200 字节原样（1600 字符）"


def check_vary_accept_encoding() -> str:
    """压缩响应带 `Vary: Accept-Encoding`（否则缓存会串）。"""
    r = client.get("/big", headers=GZIP)
    assert r.headers["vary"] == "Accept-Encoding", dict(r.headers)
    return "Vary: Accept-Encoding"


def check_json_compressed() -> str:
    """`application/json` 会压。"""
    r = client.get("/big-json", headers=GZIP)
    assert r.headers["content-encoding"] == "gzip", dict(r.headers)
    return "JSON → gzip"


def check_text_csv_compressed() -> str:
    """`text/*` 一律压。"""
    r = client.get("/csv", headers=GZIP)
    assert r.headers["content-encoding"] == "gzip", dict(r.headers)
    return "text/csv → gzip"


def check_image_not_compressed() -> str:
    """`image/png` 不压（已压缩格式，再压无收益）。"""
    r = client.get("/png", headers=GZIP)
    assert "content-encoding" not in r.headers, dict(r.headers)
    return "image/png 保持原样"


def check_octet_stream_compressed() -> str:
    """`application/octet-stream` **会**压——别以为「二进制就不压」。"""
    r = client.get("/octet", headers=GZIP)
    assert r.headers["content-encoding"] == "gzip", dict(r.headers)
    return "octet-stream → gzip（反直觉）"


def check_already_encoded_not_double_compressed() -> str:
    """响应已声明 `Content-Encoding` → 不再压。"""
    r = client.get("/already-encoded", headers=GZIP)
    assert r.headers["content-encoding"] == "gzip", dict(r.headers)
    assert int(r.headers["content-length"]) == 10, dict(r.headers)
    return "保持原 10 字节，未二次压缩"


def check_content_length_removed_semantics() -> str:
    """压缩后 `Content-Length` 是**压缩后**的字节数，不是原文长度。"""
    r = client.get("/big", headers=GZIP)
    assert int(r.headers["content-length"]) < len(r.text), dict(r.headers)
    assert int(r.headers["content-length"]) == 82, dict(r.headers)
    return "Content-Length=82（原文 1600）"


def check_trusted_host_ok() -> str:
    """白名单内的 Host → 200。"""
    r = host_client("http://example.com").get("/ping")
    assert r.status_code == 200, (r.status_code, r.text)
    return "example.com → 200"


def check_trusted_host_rejected() -> str:
    """不在白名单 → 400 `Invalid host header`。"""
    r = host_client("http://evil.com").get("/ping")
    assert r.status_code == 400, (r.status_code, r.text)
    assert r.text == "Invalid host header", r.text
    return "evil.com → 400"


def check_trusted_host_rejects_default_testserver() -> str:
    """`TestClient` 默认 `testserver` 也会被拒——这是最容易忽略的一点。"""
    r = TestClient(main.host_app).get("/ping")
    assert r.status_code == 400, (r.status_code, r.text)
    return "testserver → 400（测试要显式 base_url）"


def check_wildcard_host() -> str:
    """`*.example.com` 通配生效。"""
    r = host_client("http://api.example.com").get("/ping")
    assert r.status_code == 200, (r.status_code, r.text)
    return "api.example.com → 200"


def check_www_redirect_not_effective() -> str:
    """`www_redirect=True` 实测**没有** 301，仍按白名单判定（含则 200，不含则 400）。"""
    in_list = host_client("http://www.example.com", main.redirect_app).get("/ping")
    assert in_list.status_code == 200, (in_list.status_code, in_list.headers.get("location"))
    not_in_list = host_client("http://www.example.com", main.redirect2_app).get("/ping")
    assert not_in_list.status_code == 400, (not_in_list.status_code, not_in_list.text)
    return "白名单含 www → 200；不含 → 400（无 301）"


CHECKS = [
    ("小响应不压", check_small_not_compressed),
    ("大响应压", check_big_compressed),
    ("identity 不压", check_identity_not_compressed),
    ("Vary: Accept-Encoding", check_vary_accept_encoding),
    ("JSON 压", check_json_compressed),
    ("text/csv 压", check_text_csv_compressed),
    ("image/png 不压", check_image_not_compressed),
    ("octet-stream 压", check_octet_stream_compressed),
    ("已编码不重复压", check_already_encoded_not_double_compressed),
    ("Content-Length 语义", check_content_length_removed_semantics),
    ("Host 允许", check_trusted_host_ok),
    ("Host 拒绝", check_trusted_host_rejected),
    ("testserver 被拒", check_trusted_host_rejects_default_testserver),
    ("通配 Host", check_wildcard_host),
    ("www_redirect 实测", check_www_redirect_not_effective),
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