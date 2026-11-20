"""第 01 章 · 自动验收脚本。

用 TestClient 直接调用 ASGI 应用，不需要真正启动 uvicorn、不占端口。
运行：python verify.py
全部通过时退出码为 0，任意一条失败抛 AssertionError。
"""

from __future__ import annotations

import sys
from pathlib import Path

# 【为什么】把当前目录加入 sys.path，保证 `import main` 能找到同目录的 main.py，
# 无论你从哪个工作目录执行这个脚本。
sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402  被验收的应用

client = TestClient(main.app)


def check_root() -> str:
    """GET / 必须返回 200 且结构完全一致。"""
    response = client.get("/")
    assert response.status_code == 200, response.text
    assert response.json() == {"message": "Hello FastAPI"}, response.json()
    # 【注意】FastAPI 会自动加 Content-Type，这是它替你做的第一件事
    assert response.headers["content-type"].startswith("application/json")
    return f"200 {response.json()}"


def check_health() -> str:
    """GET /health 必须返回 200。"""
    response = client.get("/health")
    assert response.status_code == 200, response.text
    assert response.json() == {"status": "ok"}, response.json()
    return f"200 {response.json()}"


def check_openapi() -> str:
    """OpenAPI 文档必须包含两个路径，且 title/version 与 app 一致。"""
    response = client.get("/openapi.json")
    assert response.status_code == 200, response.text
    schema = response.json()
    assert schema["info"]["title"] == "第 01 章 · 第一个接口", schema["info"]
    assert schema["info"]["version"] == "0.1.0", schema["info"]
    assert set(schema["paths"]) == {"/", "/health"}, schema["paths"]
    return f"paths={sorted(schema['paths'])}"


def check_docs() -> str:
    """Swagger UI 与 ReDoc 页面必须可访问。"""
    for path in ("/docs", "/redoc"):
        response = client.get(path)
        assert response.status_code == 200, f"{path} -> {response.status_code}"
    return "/docs 200, /redoc 200"


def check_404() -> str:
    """未注册的路径必须返回 404，且是 JSON 而不是 HTML 报错页。"""
    response = client.get("/not-exist")
    assert response.status_code == 404, response.status_code
    assert response.json() == {"detail": "Not Found"}, response.json()
    return f"404 {response.json()}"


def check_method_not_allowed() -> str:
    """已注册路径用错方法必须返回 405，而不是 404。"""
    response = client.post("/")
    assert response.status_code == 405, response.status_code
    return f"405 {response.json()}"


CHECKS = [
    ("GET / 返回固定 JSON", check_root),
    ("GET /health 健康检查", check_health),
    ("/openapi.json 结构正确", check_openapi),
    ("/docs 与 /redoc 可访问", check_docs),
    ("未知路径返回 404", check_404),
    ("错误方法返回 405", check_method_not_allowed),
]


def main_entry() -> int:
    failures = 0
    for name, func in CHECKS:
        try:
            detail = func()
            print(f"[PASS] {name} -> {detail}")
        except AssertionError as exc:
            failures += 1
            print(f"[FAIL] {name} -> {exc}")
    print(f"\n结果：{len(CHECKS) - failures}/{len(CHECKS)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main_entry())
