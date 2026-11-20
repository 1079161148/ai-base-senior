"""第 68 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
import subapp  # noqa: E402


def check_api_still_works() -> str:
    """挂了 `/` 兜底后，`/api/*` 仍然优先匹配。"""
    with TestClient(main.app) as c:
        response = c.get("/api/items")
    assert response.status_code == 200, response.status_code
    assert response.json() == {"items": ["a", "b", "c"]}, response.json()
    return "200 / 3 条"


def check_css_mime() -> str:
    """CSS 的 `Content-Type` 是 `text/css`。"""
    with TestClient(main.app) as c:
        response = c.get("/static/app.css")
    assert response.status_code == 200, response.status_code
    assert response.headers["content-type"] == "text/css; charset=utf-8", response.headers
    return response.headers["content-type"]


def check_js_mime() -> str:
    """JS 的 `Content-Type` 是 `text/javascript`。"""
    with TestClient(main.app) as c:
        response = c.get("/static/app.js")
    assert response.status_code == 200, response.status_code
    assert response.headers["content-type"] == "text/javascript; charset=utf-8", response.headers
    return response.headers["content-type"]


def check_json_static() -> str:
    """JSON 静态文件按 `application/json` 返回。"""
    with TestClient(main.app) as c:
        response = c.get("/static/data.json")
    assert response.status_code == 200, response.status_code
    assert response.headers["content-type"] == "application/json", response.headers
    assert response.json()["chapter"] == 68, response.json()
    return "application/json / chapter=68"


def check_missing_static_404() -> str:
    """不存在的静态文件 → 404。"""
    with TestClient(main.app) as c:
        assert c.get("/static/nope.txt").status_code == 404
    return "404"


def check_root_serves_index() -> str:
    """`html=True` 让 `/` 返回 `index.html`。"""
    with TestClient(main.app) as c:
        response = c.get("/")
    assert response.status_code == 200, response.status_code
    assert response.headers["content-type"].startswith("text/html"), response.headers
    assert "这是 index.html" in response.text, response.text[:80]
    return "200 / text/html"


def check_spa_deep_route_404() -> str:
    """**实测**：`html=True` **不做** SPA 深路径兜底，`/some/route` 仍是 404。"""
    with TestClient(main.app) as c:
        assert c.get("/some/route").status_code == 404
    return "深路径 404（需自写 fallback）"


def check_traversal_blocked() -> str:
    """目录穿越 `../` 被拦截。"""
    with TestClient(main.app) as c:
        response = c.get("/static/../main.py")
    assert response.status_code == 404, response.status_code
    assert "require" not in response.text[:100], response.text[:100]
    return "404，未泄露源码"


def check_sub_app_endpoint() -> str:
    """子应用端点可达。"""
    with TestClient(main.app) as c:
        response = c.get("/sub/hello")
    assert response.status_code == 200, response.status_code
    assert response.json()["who"] == "sub-app", response.json()
    return "who=sub-app"


def check_sub_app_root_path() -> str:
    """子应用看到 `root_path="/sub"`，主应用看到 `""`。"""
    with TestClient(main.app) as c:
        sub = c.get("/sub/hello").json()
        parent = c.get("/api/whoami").json()
    assert sub["root_path"] == "/sub", sub
    assert parent["root_path"] == "", parent
    return 'sub "/sub"，main ""'


def check_sub_app_docs() -> str:
    """子应用有独立的 `/sub/docs` 与 `/sub/openapi.json`。"""
    with TestClient(main.app) as c:
        assert c.get("/sub/docs").status_code == 200
        schema = c.get("/sub/openapi.json").json()
    assert "/hello" in schema["paths"], schema["paths"].keys()
    return "/sub/docs + /sub/openapi.json"


def check_parent_docs_unaffected() -> str:
    """主应用 `/docs` 仍正常。"""
    with TestClient(main.app) as c:
        assert c.get("/docs").status_code == 200
        assert c.get("/openapi.json").status_code == 200
    return "200"


def check_sub_app_not_in_parent_schema() -> str:
    """子应用的路径**不**出现在主应用 `openapi()` 里。"""
    with TestClient(main.app) as c:
        paths = c.get("/openapi.json").json()["paths"]
    assert "/sub/hello" not in paths, paths.keys()
    assert "/api/items" in paths, paths.keys()
    return "主 schema 无 /sub/hello"


def check_static_not_in_schema() -> str:
    """静态挂载不进 OpenAPI。"""
    with TestClient(main.app) as c:
        paths = c.get("/openapi.json").json()["paths"]
    assert not any(path.startswith("/static") for path in paths), paths.keys()
    return "无 /static/* 条目"


def check_sub_app_lifespan_not_cascaded() -> str:
    """**实测坑**：挂载不触发子应用 lifespan，`state.marker` 不存在。"""
    main.APP_EVENTS.clear()
    with TestClient(main.app) as c:
        body = c.get("/sub/hello").json()
        events = c.get("/sub/events").json()["events"]
        main_events = c.get("/events").json()["events"]
    assert body["marker"] == "missing", body
    assert events == [], events
    assert main_events == ["app:startup"], main_events
    return "子应用 marker=missing，事件为空"


def check_sub_app_lifespan_when_direct() -> str:
    """直接 `TestClient(sub_app)` 时，子应用 lifespan 正常执行。"""
    subapp.SUB_EVENTS.clear()
    with TestClient(subapp.sub_app) as c:
        body = c.get("/hello").json()
        assert body["marker"] == "sub-app", body
    assert subapp.SUB_EVENTS == ["sub:startup", "sub:shutdown"], subapp.SUB_EVENTS
    return " → ".join(subapp.SUB_EVENTS)


CHECKS = [
    ("API 优先", check_api_still_works),
    ("CSS MIME", check_css_mime),
    ("JS MIME", check_js_mime),
    ("JSON 静态", check_json_static),
    ("缺失 404", check_missing_static_404),
    ("/ 返回 index", check_root_serves_index),
    ("深路径 404", check_spa_deep_route_404),
    ("目录穿越", check_traversal_blocked),
    ("子应用端点", check_sub_app_endpoint),
    ("root_path", check_sub_app_root_path),
    ("子应用文档", check_sub_app_docs),
    ("主应用文档", check_parent_docs_unaffected),
    ("子应用不进主 schema", check_sub_app_not_in_parent_schema),
    ("静态不进 schema", check_static_not_in_schema),
    ("子应用 lifespan 不级联", check_sub_app_lifespan_not_cascaded),
    ("直接跑子应用", check_sub_app_lifespan_when_direct),
]


def run() -> int:
    failures = 0
    for name, func in CHECKS:
        try:
            print(f"[PASS] {name} -> {func()}")
        except Exception as exc:  # noqa: BLE001 - 验收脚本要报告任何失败
            failures += 1
            print(f"[FAIL] {name} -> {type(exc).__name__}: {exc}")
    print(f"\n结果：{len(CHECKS) - failures}/{len(CHECKS)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())