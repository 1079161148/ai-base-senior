"""第 65 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
import store  # noqa: E402
from dependencies import ADMIN_TOKEN  # noqa: E402

ADMIN = {"X-Admin-Token": ADMIN_TOKEN}
EXPECTED_PATHS = {
    "/health",
    "/routes",
    "/api/v1/users",
    "/api/v1/users/count",
    "/api/v1/users/stats",
    "/api/v1/users/{user_id}",
    "/api/v1/items",
    "/api/v1/items/{item_id}",
    "/api/v1/admin/stats",
    "/api/v1/admin/legacy",
}


def client() -> TestClient:
    store.reset()
    return TestClient(main.app)


def check_route_tree() -> str:
    """三个模块组装后，`openapi()["paths"]` 恰好 10 条。"""
    with client() as c:
        paths = set(c.get("/routes").json()["paths"])
    assert paths == EXPECTED_PATHS, paths ^ EXPECTED_PATHS
    return f"{len(paths)} 条路径"


def check_prefix_stacking() -> str:
    """`/api/v1`（外层）+ `/users`（模块）→ `/api/v1/users`。"""
    with client() as c:
        assert c.get("/api/v1/users").status_code == 200
        assert c.get("/api/v1/users").json()[0] == {"id": 1, "name": "user1"}
        assert c.get("/users").status_code == 404
    return "/api/v1/users 可用，/users 404"


def check_health_outside_prefix() -> str:
    """探针路径不挂在版本前缀下。"""
    with client() as c:
        assert c.get("/health").status_code == 200
        assert c.get("/api/v1/health").status_code == 404
    return "/health 200，/api/v1/health 404"


def check_static_before_param() -> str:
    """`/users/count` 定义在 `/{user_id}` 之前 → 正常返回。"""
    with client() as c:
        response = c.get("/api/v1/users/count")
    assert response.status_code == 200, response.status_code
    assert response.json() == {"count": 5}, response.json()
    return "200 / count=5"


def check_static_after_param() -> str:
    """`/users/stats` 定义在 `/{user_id}` 之后 → 被参数路由抢走，422。"""
    with client() as c:
        response = c.get("/api/v1/users/stats")
    assert response.status_code == 422, response.status_code
    detail = response.json()["detail"][0]
    assert detail["type"] == "int_parsing", detail
    assert detail["loc"] == ["path", "user_id"], detail
    assert detail["input"] == "stats", detail
    return "422 int_parsing（被 {user_id} 抢走）"


def check_param_route() -> str:
    """参数路由：存在 200，不存在 404。"""
    with client() as c:
        assert c.get("/api/v1/users/3").json() == {"id": 3, "name": "user3"}
        missing = c.get("/api/v1/users/99")
    assert missing.status_code == 404, missing.status_code
    assert missing.json()["detail"] == "user not found", missing.json()
    return "3 → 200，99 → 404"


def check_router_dependency_blocks() -> str:
    """router 级依赖：无 token 一律 403。"""
    with client() as c:
        stats = c.get("/api/v1/admin/stats")
        debug = c.get("/api/v1/admin/debug")
        legacy = c.get("/api/v1/admin/legacy")
    for response in (stats, debug, legacy):
        assert response.status_code == 403, response.status_code
        assert response.json()["detail"] == "admin token required", response.json()
    return "三个端点全部 403"


def check_router_dependency_allows() -> str:
    """带正确 token → 全部放行。"""
    with client() as c:
        stats = c.get("/api/v1/admin/stats", headers=ADMIN)
        debug = c.get("/api/v1/admin/debug", headers=ADMIN)
    assert stats.status_code == 200, stats.status_code
    assert stats.json() == {"users": 5, "items": 3}, stats.json()
    assert debug.json() == {"users": 5, "items": 3}, debug.json()
    return "users=5, items=3"


def check_hidden_endpoint_still_guarded() -> str:
    """`include_in_schema=False` 只影响文档，不影响鉴权。"""
    with client() as c:
        assert c.get("/api/v1/admin/debug").status_code == 403
        assert c.get("/api/v1/admin/debug", headers=ADMIN).status_code == 200
        schema = c.get("/openapi.json").json()
    assert "/api/v1/admin/debug" not in schema["paths"], schema["paths"].keys()
    return "文档隐藏，鉴权仍生效"


def check_tags_applied() -> str:
    """每个模块的 `tags` 落到 operation 上。"""
    with client() as c:
        paths = c.get("/openapi.json").json()["paths"]

    def tags_of(path: str) -> list[str]:
        operation = next(iter(paths[path].values()))
        return operation["tags"]

    assert tags_of("/api/v1/users") == ["users"], tags_of("/api/v1/users")
    assert tags_of("/api/v1/items") == ["items"], tags_of("/api/v1/items")
    assert tags_of("/api/v1/admin/stats") == ["admin"], tags_of("/api/v1/admin/stats")
    assert tags_of("/health") == ["ops"], tags_of("/health")
    return "users / items / admin / ops"


def check_router_responses_documented() -> str:
    """router 级 `responses` 出现在该模块所有端点文档里。"""
    with client() as c:
        paths = c.get("/openapi.json").json()["paths"]
    item_responses = list(paths["/api/v1/items/{item_id}"]["get"]["responses"])
    list_responses = list(paths["/api/v1/items"]["get"]["responses"])
    assert "404" in item_responses, item_responses
    assert "404" in list_responses, list_responses
    return "items 两个端点都有 404"


def check_deprecated_flag() -> str:
    """`deprecated=True` 进文档，端点仍可调用。"""
    with client() as c:
        schema = c.get("/openapi.json").json()
        call = c.get("/api/v1/admin/legacy", headers=ADMIN)
    assert schema["paths"]["/api/v1/admin/legacy"]["get"]["deprecated"] is True
    assert call.status_code == 200, call.status_code
    return "deprecated=True 且仍返回 200"


def check_dependency_403_not_documented() -> str:
    """router 级依赖抛的 403 不会自动出现在文档里（只有 200/422）。"""
    with client() as c:
        responses = list(c.get("/openapi.json").json()["paths"]["/api/v1/admin/stats"]["get"]["responses"])
    assert "403" not in responses, responses
    assert responses == ["200", "422"], responses
    return "文档只有 200/422（403 需手写）"


def check_app_routes_not_flattened() -> str:
    """【实测坑】`include_router` 不把子路由展平进 `app.routes`。"""
    paths = main.app.openapi()["paths"]
    flat = [route for route in main.app.routes if getattr(route, "path", None)]
    assert len(paths) == 10, len(paths)
    assert len(flat) < len(paths), (len(flat), len(paths))
    wrappers = [route for route in main.app.routes if getattr(route, "path", None) is None]
    assert wrappers, "没有包装对象"
    return f"openapi 10 条 / app.routes 仅 {len(flat)} 条带 path"


CHECKS = [
    ("路由树", check_route_tree),
    ("前缀叠加", check_prefix_stacking),
    ("探针不在前缀下", check_health_outside_prefix),
    ("静态路径在前", check_static_before_param),
    ("静态路径在后", check_static_after_param),
    ("参数路由", check_param_route),
    ("router 依赖拦截", check_router_dependency_blocks),
    ("router 依赖放行", check_router_dependency_allows),
    ("隐藏仍鉴权", check_hidden_endpoint_still_guarded),
    ("tags 生效", check_tags_applied),
    ("router responses", check_router_responses_documented),
    ("deprecated", check_deprecated_flag),
    ("403 不进文档", check_dependency_403_not_documented),
    ("app.routes 未展平", check_app_routes_not_flattened),
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