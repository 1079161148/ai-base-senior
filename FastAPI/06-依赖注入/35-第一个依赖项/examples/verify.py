"""第 35 章 · 自动验收。运行：python verify.py"""

import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def check_defaults() -> str:
    """不传参：依赖的默认值生效。"""
    r = client.get("/items")
    assert r.status_code == 200, (r.status_code, r.text)
    body = r.json()
    assert body["params"] == {"q": None, "skip": 0, "limit": 10}, body
    assert body["count"] == 10, body
    return f'默认 params={body["params"]}'


def check_params_applied() -> str:
    """传参被依赖接收并按分页计算。"""
    r = client.get("/items", params={"skip": 5, "limit": 3})
    body = r.json()
    assert body["params"] == {"q": None, "skip": 5, "limit": 3}, body
    assert body["count"] == 3 and body["first"] == 6, body
    return f'skip=5 limit=3 → first={body["first"]}'


def check_validation_in_dependency() -> str:
    """依赖里的校验失败 → 422，loc 指向 query 而非依赖名。"""
    r = client.get("/items", params={"limit": 200})
    assert r.status_code == 422, (r.status_code, r.text)
    err = r.json()["detail"][0]
    assert err["loc"] == ["query", "limit"], err
    assert err["type"] == "less_than_equal", err
    return f'422 loc={err["loc"]}'


def check_reused_across_endpoints() -> str:
    """同一依赖被两个端点复用。"""
    r = client.get("/users", params={"limit": 1})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["params"]["limit"] == 1, body
    assert body["users"] == ["alice"], body
    return "另一个端点自动获得 q/skip/limit"


def check_dependency_raises() -> str:
    """依赖抛 401：路由不执行。"""
    r = client.get("/secure")
    assert r.status_code == 401, (r.status_code, r.text)
    body = r.json()
    assert body["detail"] == "依赖要求登录", body
    assert "route_ran" not in body, body
    return "401 且路由未执行"


def check_dependency_passes_value() -> str:
    """依赖返回值注入端点。"""
    r = client.get("/secure", headers={"X-Token": "secret"})
    assert r.status_code == 200, r.text
    assert r.json() == {"token": "secret", "route_ran": "true"}, r.json()
    return "token 注入成功"


def check_request_in_dependency() -> str:
    """依赖可以独吞 `Request`。"""
    r = client.get("/client", headers={"User-Agent": "verify/35"})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["ua"] == "verify/35", body
    assert body["path"] == "/client" and body["method"] == "GET", body
    return f'ua={body["ua"]}, path={body["path"]}'


def check_openapi_params_from_dependency() -> str:
    """OpenAPI：参数来自依赖，且带 description。"""
    schema = client.get("/openapi.json").json()
    params = schema["paths"]["/items"]["get"]["parameters"]
    names = [p["name"] for p in params]
    assert names == ["q", "skip", "limit"], names
    assert all(p["in"] == "query" for p in params), params
    descs = {p["name"]: p.get("description") for p in params}
    assert descs["limit"] == "每页条数", descs
    return f"parameters={names}，description 保留"


def check_openapi_no_extra_body() -> str:
    """OpenAPI：依赖不产生 requestBody。"""
    schema = client.get("/openapi.json").json()
    assert "requestBody" not in schema["paths"]["/items"]["get"], schema["paths"]["/items"]["get"]
    return "GET /items 无 requestBody"


def check_async_dependency() -> str:
    """依赖可以是 async def。"""
    assert inspect.iscoroutinefunction(main.common_parameters), main.common_parameters
    assert inspect.iscoroutinefunction(main.client_info), main.client_info
    return "common_parameters / client_info 均为 async"


def check_path_and_dependency() -> str:
    """路径参数与依赖共存。"""
    r = client.get("/items/7", params={"limit": 2})
    assert r.status_code == 200, r.text
    assert r.json()["item_id"] == 7, r.json()
    assert r.json()["params"]["limit"] == 2, r.json()
    return "item_id=7 + limit=2"


def check_depends_object_reusable() -> str:
    """`Depends(...)` 实例可跨函数复用，且不缓存跨请求结果。"""
    probe = FastAPI()
    calls: list[int] = []

    def dep() -> int:
        calls.append(1)
        return len(calls)

    Dep = __import__("fastapi").Depends(dep)

    @probe.get("/a")
    def a(value: int = Dep) -> dict[str, int]:  # noqa: ANN001
        return {"value": value}

    @probe.get("/b")
    def b(value: int = Dep) -> dict[str, int]:  # noqa: ANN001
        return {"value": value}

    c = TestClient(probe)
    assert c.get("/a").json() == {"value": 1}, c.get("/a").json()
    assert c.get("/b").json() == {"value": 2}, c.get("/b").json()
    return f"两次请求各调用一次（累计 {len(calls)}）"


CHECKS = [
    ("默认值", check_defaults),
    ("传参生效", check_params_applied),
    ("依赖内校验", check_validation_in_dependency),
    ("跨端点复用", check_reused_across_endpoints),
    ("依赖抛 401", check_dependency_raises),
    ("返回值注入", check_dependency_passes_value),
    ("依赖读 Request", check_request_in_dependency),
    ("OpenAPI 参数来源", check_openapi_params_from_dependency),
    ("无 requestBody", check_openapi_no_extra_body),
    ("async 依赖", check_async_dependency),
    ("路径参数共存", check_path_and_dependency),
    ("Depends 复用", check_depends_object_reusable),
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