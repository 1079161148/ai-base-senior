"""第 76 章 · 自动验收。运行：python verify.py"""

import re
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

DOCKERFILE = HERE / "Dockerfile"
DOCKERIGNORE = HERE / ".dockerignore"


def dockerfile() -> str:
    return DOCKERFILE.read_text(encoding="utf-8")


def check_healthz_ok() -> str:
    """存活探针：200 + 固定 body。"""
    main.reset()
    with TestClient(main.app) as c:
        response = c.get("/healthz")
    assert response.status_code == 200, response.status_code
    assert response.json() == {"status": "ok", "version": "1.0.0"}, response.json()
    return "200 / ok"


def check_healthz_ignores_dependency() -> str:
    """**关键**：依赖挂了，liveness 仍 200。"""
    main.reset()
    with TestClient(main.app) as c:
        main.set_db_ok(False)
        alive = c.get("/healthz")
        ready = c.get("/readyz")
    assert alive.status_code == 200, alive.status_code
    assert ready.status_code == 503, ready.status_code
    main.reset()
    return "healthz 200 / readyz 503"


def check_readyz_ok() -> str:
    """就绪探针：依赖正常 → 200。"""
    main.reset()
    with TestClient(main.app) as c:
        body = c.get("/readyz").json()
    assert body["status"] == "ready", body
    assert body["db_ok"] is True, body
    return "ready / db_ok=True"


def check_readyz_503() -> str:
    """依赖不可用 → 503 + 明确字段。"""
    main.reset()
    with TestClient(main.app) as c:
        main.set_db_ok(False)
        response = c.get("/readyz")
    main.reset()
    assert response.status_code == 503, response.status_code
    assert response.json()["db_ok"] is False, response.json()
    return "503 / db_ok=False"


def check_version_header() -> str:
    """每个响应带 `X-App-Version`。"""
    main.reset()
    with TestClient(main.app) as c:
        headers = c.get("/items").headers
    assert headers["x-app-version"] == main.APP_VERSION, headers
    return headers["x-app-version"]


def check_info() -> str:
    """运行信息可查。"""
    main.reset()
    with TestClient(main.app) as c:
        body = c.get("/info").json()
    assert body["version"] == "1.0.0", body
    assert body["port"] == main.PORT, body
    assert body["env"] in {"dev", "prod"}, body
    return f'env={body["env"]} port={body["port"]}'


def check_shutdown_runs() -> str:
    """退出时 lifespan 的 shutdown 必须执行（优雅退出）。"""
    main.reset()
    with TestClient(main.app) as c:
        assert c.get("/readyz").status_code == 200
        assert main.STATE["ready"] is True, main.STATE
    assert main.STATE["ready"] is False, main.STATE
    assert main.STATE["shutdown_done"] is True, main.STATE
    return "ready False / shutdown_done True"


def check_prod_docs_hidden() -> str:
    """生产形态：`/docs` 404。"""
    prod = TestClient(main.prod_app)
    assert prod.get("/docs").status_code == 404
    assert prod.get("/redoc").status_code == 404
    return "/docs 404"


def check_prod_schema_hidden() -> str:
    """生产形态：`/openapi.json` 404。"""
    prod = TestClient(main.prod_app)
    assert prod.get("/openapi.json").status_code == 404
    return "/openapi.json 404"


def check_prod_api_works() -> str:
    """关文档不影响业务。"""
    prod = TestClient(main.prod_app)
    response = prod.get("/items")
    assert response.status_code == 200, response.status_code
    assert response.json() == {"items": ["a"]}, response.json()
    return "200 / 业务正常"


def check_dockerfile_workers() -> str:
    """Dockerfile 用多 worker 启动。"""
    content = dockerfile()
    assert '"--workers"' in content or "--workers" in content, content
    match = re.search(r"--workers[\",\s]+(\d+)", content)
    assert match and int(match.group(1)) >= 2, content
    return f"workers={match.group(1)}"


def check_dockerfile_no_reload() -> str:
    """生产镜像不能带 `--reload`。"""
    content = dockerfile()
    cmd_lines = [line for line in content.splitlines() if line.strip().startswith("CMD")]
    assert cmd_lines, "没有 CMD"
    assert not any("--reload" in line for line in cmd_lines), cmd_lines
    return "CMD 无 --reload"


def check_dockerfile_non_root() -> str:
    """非 root 运行。"""
    content = dockerfile()
    users = re.findall(r"^USER\s+(\S+)", content, flags=re.MULTILINE)
    assert users, "缺少 USER 指令"
    assert users[-1] != "root", users
    return f"USER {users[-1]}"


def check_dockerfile_healthcheck() -> str:
    """镜像自带 HEALTHCHECK，且打的是 `/healthz`。"""
    content = dockerfile()
    assert "HEALTHCHECK" in content, "缺少 HEALTHCHECK"
    assert "/healthz" in content, "HEALTHCHECK 没打存活探针"
    return "HEALTHCHECK → /healthz"


def check_dockerfile_proxy_headers() -> str:
    """信任反向代理头。"""
    assert "--proxy-headers" in dockerfile()
    assert "--forwarded-allow-ips" in dockerfile()
    return "--proxy-headers 已配置"


def check_dockerignore_excludes_env() -> str:
    """构建上下文排除 `.env`。"""
    content = DOCKERIGNORE.read_text(encoding="utf-8")
    lines = {line.strip() for line in content.splitlines()}
    assert ".env" in lines, lines
    return ".env 已排除"


CHECKS = [
    ("healthz 200", check_healthz_ok),
    ("liveness 不查依赖", check_healthz_ignores_dependency),
    ("readyz 200", check_readyz_ok),
    ("readyz 503", check_readyz_503),
    ("版本头", check_version_header),
    ("运行信息", check_info),
    ("优雅退出", check_shutdown_runs),
    ("生产关 docs", check_prod_docs_hidden),
    ("生产关 schema", check_prod_schema_hidden),
    ("生产业务可用", check_prod_api_works),
    ("多 worker", check_dockerfile_workers),
    ("无 reload", check_dockerfile_no_reload),
    ("非 root", check_dockerfile_non_root),
    ("HEALTHCHECK", check_dockerfile_healthcheck),
    ("代理头", check_dockerfile_proxy_headers),
    (".dockerignore", check_dockerignore_excludes_env),
]


def run() -> int:
    if not DOCKERFILE.exists():
        print(f"[FAIL] 缺文件：{DOCKERFILE}")
        return 1
    if not DOCKERIGNORE.exists():
        print(f"[FAIL] 缺文件：{DOCKERIGNORE}")
        return 1
    failures = 0
    for name, func in CHECKS:
        try:
            print(f"[PASS] {name} -> {func()}")
        except Exception as exc:  # noqa: BLE001 - 验收脚本要报告任何失败
            failures += 1
            print(f"[FAIL] {name} -> {type(exc).__name__}: {exc}")
    main.reset()
    print(f"\n结果：{len(CHECKS) - failures}/{len(CHECKS)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())