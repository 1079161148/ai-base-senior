"""第 39 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from typing import Annotated  # noqa: E402

from fastapi import APIRouter, Depends, FastAPI, HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def reset() -> None:
    main.AUDIT.clear()


def check_global_dependency_runs() -> str:
    """全局依赖在所有路由执行。"""
    reset()
    r = client.get("/health", headers={"X-Request-Source": "test"})
    assert r.status_code == 200, (r.status_code, r.text)
    assert main.AUDIT == ["test"], main.AUDIT
    return f"AUDIT={main.AUDIT}"


def check_global_dependency_default() -> str:
    """没传 header 时全局依赖用默认值。"""
    reset()
    client.get("/health")
    assert main.AUDIT == ["unknown"], main.AUDIT
    return "默认 unknown"


def check_decorator_dependency_blocks() -> str:
    """端点装饰器依赖：无 token → 401。"""
    reset()
    r = client.get("/public")
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.json()["detail"] == "X-Token 无效", r.json()
    return "401 拦截"


def check_decorator_dependency_passes() -> str:
    """端点装饰器依赖：有 token 放行。"""
    reset()
    r = client.get("/public", headers={"X-Token": "secret"})
    assert r.status_code == 200, r.text
    assert r.json() == {"ok": "true"}, r.json()
    return "200 放行"


def check_decorator_cannot_get_value() -> str:
    """装饰器位置拿不到返回值（只能靠参数位置）。"""
    reset()
    dec = client.get("/compare/dec").json()
    assert dec == {"receives": "nothing"}, dec
    param = client.get("/compare/param", headers={"X-Token": "secret"}).json()
    assert param == {"token": "secret"}, param
    return "dec 拿不到；param 拿到 secret"


def check_router_dependency_scope() -> str:
    """Router 依赖只作用于该组路由。"""
    reset()
    blocked = client.get("/admin/panel")
    assert blocked.status_code == 403, (blocked.status_code, blocked.text)
    ok = client.get("/admin/panel", headers={"X-Role": "admin"})
    assert ok.status_code == 200 and ok.json() == {"panel": "admin"}, ok.text
    return "无 X-Role → 403；有 → 200"


def check_router_all_routes_protected() -> str:
    """Router 下所有路由都受保护。"""
    reset()
    r = client.get("/admin/stats")
    assert r.status_code == 403, r.status_code
    return "stats 同样 403"


def check_path_prefix_does_not_imply_router() -> str:
    """路径在 /admin 下但没 include 进 router → 不受 router 依赖。"""
    reset()
    r = client.get("/admin/ops")
    assert r.status_code == 200, (r.status_code, r.text)
    return "只受全局依赖影响"


def check_global_and_router_stack() -> str:
    """全局 + Router 依赖叠加：/admin/panel 触发两条。"""
    reset()
    r = client.get("/admin/panel", headers={"X-Role": "admin", "X-Request-Source": "ops"})
    assert r.status_code == 200, r.text
    assert main.AUDIT == ["ops"], main.AUDIT
    return "全局审计 + router 鉴权都执行"


def check_openapi_has_dependency_params() -> str:
    """依赖在装饰器位置时，其参数照样进 OpenAPI。"""
    schema = client.get("/openapi.json").json()
    params = schema["paths"]["/public"]["get"].get("parameters", [])
    names = {p["name"] for p in params}
    assert {"X-Request-Source", "X-Token"} <= names, names
    return f"parameters={sorted(names)}"


def check_docs_not_blocked() -> str:
    """全局依赖不作用于 /docs 与 /openapi.json。"""
    assert client.get("/docs").status_code == 200
    assert client.get("/openapi.json").status_code == 200
    return "/docs 与 /openapi.json 不受全局依赖限制"


def check_global_dependency_failure() -> str:
    """全局依赖抛错：所有路由一起挂。

    【实测】路由注册后再 `app.router.dependencies.append(...)` **不生效**，
           必须在构造 `FastAPI(dependencies=[...])` 或注册路由前设置。
    """
    def boom() -> None:
        raise HTTPException(status_code=503, detail="维护中")

    failing = FastAPI(dependencies=[Depends(boom)])

    @failing.get("/x")
    def x() -> dict[str, str]:  # noqa: ANN202
        return {"x": "1"}

    r = TestClient(failing, raise_server_exceptions=False).get("/x")
    assert r.status_code == 503, (r.status_code, r.text)
    return "全局依赖抛 503 → 路由不可用"


def check_late_append_does_not_apply() -> str:
    """事后 append `router.dependencies` 不影响已注册路由。"""
    late = FastAPI()

    @late.get("/z")
    def z() -> dict[str, str]:  # noqa: ANN202
        return {"z": "1"}

    def boom2() -> None:
        raise HTTPException(status_code=503, detail="不该生效")

    late.router.dependencies.append(Depends(boom2))
    r = TestClient(late).get("/z")
    assert r.status_code == 200, (r.status_code, r.text)
    return "已注册路由不受事后 append 影响"


def check_cache_between_global_and_router() -> str:
    """同一依赖对象在全局与端点间共享缓存（单请求只执行一次）。"""
    probe = FastAPI()
    calls: list[int] = []

    def dep() -> None:
        calls.append(1)

    probe.router.dependencies.append(Depends(dep))

    @probe.get("/y", dependencies=[Depends(dep)])
    def y() -> dict[str, int]:  # noqa: ANN202
        return {"calls": len(calls)}

    c = TestClient(probe)
    assert c.get("/y").json() == {"calls": 1}, c.get("/y").json()
    return "同请求只执行 1 次"


CHECKS = [
    ("全局依赖执行", check_global_dependency_runs),
    ("全局依赖默认值", check_global_dependency_default),
    ("装饰器依赖拦截", check_decorator_dependency_blocks),
    ("装饰器依赖放行", check_decorator_dependency_passes),
    ("装饰器拿不到返回值", check_decorator_cannot_get_value),
    ("Router 依赖生效", check_router_dependency_scope),
    ("Router 全覆盖", check_router_all_routes_protected),
    ("路径前缀不等于 Router", check_path_prefix_does_not_imply_router),
    ("全局 + Router 叠加", check_global_and_router_stack),
    ("OpenAPI 含依赖参数", check_openapi_has_dependency_params),
    ("/docs 不受限", check_docs_not_blocked),
    ("全局依赖失败", check_global_dependency_failure),
    ("事后 append 无效", check_late_append_does_not_apply),
    ("全局与端点共享缓存", check_cache_between_global_and_router),
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