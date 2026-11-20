"""第 54 章 · 自动验收。运行：python verify.py"""

import json
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)
plain = TestClient(main.plain_app)


def check_root_path_from_scope() -> str:
    """`root_path` 来自 scope（server 注入），应用只读。"""
    body = client.get("/whoami").json()
    assert body["root_path"] == "/api", body
    return f'root_path={body["root_path"]}'


def check_path_excludes_prefix() -> str:
    """`request.url.path` 不含前缀——路由匹配用的是去掉前缀的路径。"""
    body = client.get("/whoami").json()
    assert body["path"] == "/whoami", body
    return f'path={body["path"]}'


def check_base_url_has_prefix() -> str:
    """`base_url` 含前缀。"""
    body = client.get("/whoami").json()
    assert body["base_url"] == "http://testserver/api/", body
    return body["base_url"]


def check_url_for_has_prefix() -> str:
    """`url_for()` 生成的绝对 URL 含前缀。"""
    body = client.get("/whoami").json()
    assert body["url_for"] == "http://testserver/api/whoami", body
    return body["url_for"]


def check_url_for_with_path_param() -> str:
    """带路径参数时同样拼前缀。"""
    body = client.get("/items/7").json()
    assert body["url_for"] == "http://testserver/api/items/7", body
    return body["url_for"]


def check_docs_openapi_url_has_prefix() -> str:
    """`/docs` 页面里请求的是 `/api/openapi.json`，不是 `/openapi.json`。"""
    html = client.get("/docs").text
    idx = html.find("openapi.json")
    assert idx != -1, html[:200]
    context = html[max(0, idx - 40) : idx + 15]
    assert "'/api/openapi.json'" in context, context
    return context.strip().replace("\n", " ")


def check_openapi_servers_injected() -> str:
    """`openapi.json` 的 `servers` 会动态插入 root_path。"""
    body = client.get("/openapi.json").json()
    assert body["servers"] == [{"url": "/api"}], body.get("servers")
    return json.dumps(body["servers"])


def check_servers_disabled() -> str:
    """`root_path_in_servers=False` → 不注入。"""
    body = TestClient(main.no_servers_app).get("/openapi.json").json()
    assert body.get("servers") is None, body.get("servers")
    return "servers 字段缺失/为 None"


def check_plain_app_without_root_path() -> str:
    """不注入 root_path：base_url 与 url_for 都不带前缀。"""
    body = plain.get("/whoami").json()
    assert body["root_path"] == "", body
    assert body["base_url"] == "http://testserver/", body
    assert body["url_for"] == "http://testserver/whoami", body
    return "无前缀"


def check_proxy_headers_trusted() -> str:
    """信任反代 IP 时，`X-Forwarded-For` 改写 `request.client.host`。"""
    ph = TestClient(main.proxied_app, client=("127.0.0.1", 1234))
    body = ph.get("/whoami", headers={"X-Forwarded-For": "1.2.3.4"}).json()
    assert body["client"] == "1.2.3.4", body
    return f'client={body["client"]}'


def check_proxy_headers_proto() -> str:
    """`X-Forwarded-Proto: https` → `request.url.scheme == https`。"""
    ph = TestClient(main.proxied_app, client=("127.0.0.1", 1234))
    body = ph.get("/whoami", headers={"X-Forwarded-Proto": "https"}).json()
    assert body["scheme"] == "https", body
    return f'scheme={body["scheme"]}'


def check_proxy_headers_untrusted() -> str:
    """不信任的对端 IP：头被忽略，仍用自己的 client/scheme。"""
    ph = TestClient(main.proxied_app, client=("8.8.8.8", 1))
    body = ph.get(
        "/whoami",
        headers={"X-Forwarded-For": "1.2.3.4", "X-Forwarded-Proto": "https"},
    ).json()
    assert body["client"] == "8.8.8.8", body
    assert body["scheme"] == "http", body
    return f'client={body["client"]}, scheme={body["scheme"]}'


def check_forwarded_host_not_handled() -> str:
    """`X-Forwarded-Host` **不会**被 ProxyHeadersMiddleware 处理。"""
    ph = TestClient(main.proxied_app, client=("127.0.0.1", 1234))
    body = ph.get("/whoami", headers={"X-Forwarded-Host": "api.example.com"}).json()
    assert body["host"] == "testserver", body
    return "Host 仍为 testserver（要靠 Nginx `proxy_set_header Host`）"


def check_forwarded_prefix_custom_middleware() -> str:
    """`X-Forwarded-Prefix` 需自己写中间件；写了才生效。"""
    pf = TestClient(main.prefix_app)
    body = pf.get("/whoami", headers={"X-Forwarded-Prefix": "/v1"}).json()
    assert body["root_path"] == "/v1", body
    assert body["url_for"] == "http://testserver/v1/whoami", body
    return body["url_for"]


def check_fastapi_root_path_deprecated() -> str:
    """`FastAPI(root_path=...)` 已废弃——前缀应由 server 配置。"""
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        FastAPI(root_path="/api")
    messages = [str(item.message) for item in caught]
    assert any("root_path" in msg and "deprecated" in msg.lower() for msg in messages), messages
    return messages[0].split("（")[0][:60] + "..."

def check_forwarded_prefix_header_ignored_without_middleware() -> str:
    """不装那个中间件时，`X-Forwarded-Prefix` 完全不生效（Starlette 不内置）。"""
    body = plain.get("/whoami", headers={"X-Forwarded-Prefix": "/v1"}).json()
    assert body["root_path"] == "", body
    return "无中间件 → root_path 仍为空"


CHECKS = [
    ("root_path 来自 scope", check_root_path_from_scope),
    ("path 不含前缀", check_path_excludes_prefix),
    ("base_url 含前缀", check_base_url_has_prefix),
    ("url_for 含前缀", check_url_for_has_prefix),
    ("带路径参数的 url_for", check_url_for_with_path_param),
    ("/docs 的 openapi 地址", check_docs_openapi_url_has_prefix),
    ("openapi servers 注入", check_openapi_servers_injected),
    ("servers 关闭", check_servers_disabled),
    ("无前缀对照", check_plain_app_without_root_path),
    ("XFF 信任", check_proxy_headers_trusted),
    ("XFP 协议", check_proxy_headers_proto),
    ("不信任则忽略", check_proxy_headers_untrusted),
    ("XFH 不被处理", check_forwarded_host_not_handled),
    ("X-Forwarded-Prefix 自写", check_forwarded_prefix_custom_middleware),
    ("XFP 无中间件不生效", check_forwarded_prefix_header_ignored_without_middleware),
    ("root_path 参数已废弃", check_fastapi_root_path_deprecated),
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