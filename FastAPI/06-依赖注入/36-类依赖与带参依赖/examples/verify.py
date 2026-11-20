"""第 36 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from typing import Annotated  # noqa: E402

from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def openapi_params(path: str, method: str = "get") -> list[str]:
    schema = client.get("/openapi.json").json()
    params = schema["paths"][path][method].get("parameters", [])
    return [p["name"] for p in params]


def check_class_dependency() -> str:
    """类作依赖：`Annotated[Cls, Depends()]` 构造实例。"""
    r = client.get("/items", params={"skip": 2, "limit": 3})
    assert r.status_code == 200, (r.status_code, r.text)
    body = r.json()
    assert body["count"] == 3 and body["ids"] == [3, 4, 5], body
    return f'ids={body["ids"]}'


def check_class_init_params_in_openapi() -> str:
    """类依赖的 `__init__` 参数进 OpenAPI。"""
    names = openapi_params("/items")
    assert names == ["q", "skip", "limit"], names
    return f"parameters={names}"


def check_class_validation() -> str:
    """类依赖里校验失败 → 422。"""
    r = client.get("/items", params={"limit": 0})
    assert r.status_code == 422, (r.status_code, r.text)
    assert r.json()["detail"][0]["loc"] == ["query", "limit"], r.json()
    return "limit=0 → 422（loc=query,limit）"


def check_instance_dependency() -> str:
    """实例作依赖：只调 `__call__`，`__init__` 参数固定。"""
    r = client.get("/fixed/small")
    assert r.status_code == 200, r.text
    assert r.json() == {"size": 3}, r.json()
    names = openapi_params("/fixed/small")
    assert names == [], f"实例依赖不应解析 __init__ 参数：{names}"
    return "size 固定 3，OpenAPI 无参数"


def check_class_dependency_configurable() -> str:
    """类作依赖：`__init__` 参数可配，注入的是实例。"""
    assert openapi_params("/fixed/class") == ["size"], openapi_params("/fixed/class")
    r = client.get("/fixed/class", params={"size": 5})
    assert r.status_code == 200, (r.status_code, r.text)
    assert r.json() == {"size": 5}, r.json()
    return "?size=5 → {'size': 5}（注入实例而非 __call__ 结果）"


def check_class_vs_instance_semantics() -> str:
    """`Depends(类)` 注入实例；`Depends(实例)` 注入 `__call__` 结果。"""
    probe = FastAPI()

    class Cls:
        def __init__(self) -> None:
            self.tag = "instance-of-class"

        def __call__(self) -> dict[str, str]:
            return {"tag": "call-result"}

    obj = Cls()

    @probe.get("/cls")
    def cls_dep(value: Annotated[object, Depends(Cls)]) -> dict[str, str]:
        return {"tag": value.tag}  # type: ignore[attr-defined]

    @probe.get("/obj")
    def obj_dep(value: Annotated[dict[str, str], Depends(obj)]) -> dict[str, str]:
        return value

    c = TestClient(probe)
    assert c.get("/cls").json() == {"tag": "instance-of-class"}, c.get("/cls").json()
    assert c.get("/obj").json() == {"tag": "call-result"}, c.get("/obj").json()
    return "Cls → 实例；obj → __call__ 结果"


def check_call_signature_not_exposed() -> str:
    """`__call__` 的 Request 参数不出现，也不产生额外参数。"""
    names = openapi_params("/limited")
    assert names == [], names
    return "限流器无 query 参数"


def check_rate_limiter() -> str:
    """限流器：第 3 次 429 + Retry-After。"""
    main.limiter.reset()
    codes = [client.get("/limited").status_code for _ in range(3)]
    assert codes == [200, 200, 429], codes
    r = client.get("/limited")
    assert r.status_code == 429, r.text
    assert r.headers["retry-after"] == "60", dict(r.headers)
    assert "2 次/60s" in r.json()["detail"], r.json()
    return "200,200,429 + Retry-After=60"


def check_factory_dependency_a() -> str:
    """工厂依赖：A 端点只解析 X-Api-Key。"""
    # 【注意】Header(alias=...) 在 OpenAPI 里保留原始大小写
    assert openapi_params("/factory/a") == ["X-Api-Key"], openapi_params("/factory/a")
    bad = client.get("/factory/a", headers={"X-Api-Key": "no"})
    assert bad.status_code == 400, (bad.status_code, bad.text)
    ok = client.get("/factory/a", headers={"X-Api-Key": "ok"})
    assert ok.status_code == 200, ok.text
    return "错误 400 / 正确 200"


def check_factory_dependency_b() -> str:
    """工厂依赖：B 端点另一个头 + 另一个期望值。"""
    assert openapi_params("/factory/b") == ["X-Admin-Token"], openapi_params("/factory/b")
    r = client.get("/factory/b", headers={"X-Admin-Token": "admin"})
    assert r.status_code == 200, r.text
    assert r.json() == {"token": "admin"}, r.json()
    return "X-Admin-Token=admin 通过"


def check_factory_caps_limit() -> str:
    """工厂配置生效：max_size=5 截断 limit。"""
    r = client.get("/pages", params={"skip": 10, "limit": 100})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["size"] == 5, body
    assert body["start"] == 10 and body["page"] == 3, body
    return f'size 被截到 5，page={body["page"]}'


def check_factory_no_config_in_openapi() -> str:
    """工厂的配置值不出现在 OpenAPI（只暴露被依赖的头/query）。"""
    schema = client.get("/openapi.json").json()
    text = str(schema["paths"]["/factory/a"])
    assert "expected" not in text and "ok" not in text.replace("X-Api-Key", ""), text
    return "配置参数只留在闭包里"


def check_lambda_dependency() -> str:
    """`Depends(lambda: ...)` 也可用（无参数依赖）。"""
    probe = FastAPI()

    @probe.get("/x")
    def x(value: int = __import__("fastapi").Depends(lambda: 42)) -> dict[str, int]:  # noqa: ANN001
        return {"value": value}

    r = TestClient(probe).get("/x")
    assert r.json() == {"value": 42}, r.json()
    return "lambda 依赖返回 42"


CHECKS = [
    ("类作依赖", check_class_dependency),
    ("类参数进 OpenAPI", check_class_init_params_in_openapi),
    ("类依赖校验", check_class_validation),
    ("实例作依赖（固定）", check_instance_dependency),
    ("类作依赖（可配）", check_class_dependency_configurable),
    ("类 vs 实例语义", check_class_vs_instance_semantics),
    ("__call__ 签名不外露", check_call_signature_not_exposed),
    ("限流器 429", check_rate_limiter),
    ("工厂依赖 A", check_factory_dependency_a),
    ("工厂依赖 B", check_factory_dependency_b),
    ("工厂截断 limit", check_factory_caps_limit),
    ("配置不入 OpenAPI", check_factory_no_config_in_openapi),
    ("lambda 依赖", check_lambda_dependency),
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