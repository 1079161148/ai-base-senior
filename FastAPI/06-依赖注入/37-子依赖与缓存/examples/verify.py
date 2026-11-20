"""第 37 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)
ALICE = {"X-User": "alice"}


def reset() -> None:
    main.CALL_LOG.clear()


def check_three_layer_chain() -> str:
    """三层依赖：正常返回。"""
    reset()
    r = client.get("/admin", params={"scope": "read", "role": "admin"}, headers=ALICE)
    assert r.status_code == 200, (r.status_code, r.text)
    body = r.json()
    assert body["user"] == "alice", body
    assert body["info"]["role"] == "admin", body
    return f'user={body["user"]}, role={body["info"]["role"]}'


def check_execution_order() -> str:
    """执行顺序：深度优先，先子后父。"""
    reset()
    r = client.get("/order", params={"scope": "read", "role": "user"}, headers=ALICE)
    assert r.status_code == 200, r.text
    assert r.json()["calls"] == ["user", "perms", "role"], r.json()
    return f'calls={r.json()["calls"]}'


def check_cache_single_call() -> str:
    """同一请求内 get_user 只执行一次（即使端点也声明了它）。"""
    reset()
    r = client.get("/admin", params={"scope": "write", "role": "admin"}, headers=ALICE)
    assert r.status_code == 200, r.text
    assert main.CALL_LOG.count("user") == 1, main.CALL_LOG
    return f"CALL_LOG={main.CALL_LOG}"


def check_use_cache_false() -> str:
    """use_cache=False：强制重算一次。"""
    reset()
    r = client.get("/nocache", headers=ALICE)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["calls"] == ["user", "user"], body
    assert body["calls"].count("user") == 2, body
    return f"calls={body['calls']}（2 次）"


def check_cache_not_across_requests() -> str:
    """缓存不跨请求。"""
    reset()
    client.get("/count", headers=ALICE)
    first = main.CALL_LOG.count("user")
    client.get("/count", headers=ALICE)
    second = main.CALL_LOG.count("user")
    assert first == 1, first
    assert second == 2, second
    return f"两次请求 user 调用 {first} → {second}"


def check_401_from_leaf() -> str:
    """最底层依赖抛 401，整棵树停止。"""
    reset()
    r = client.get("/admin", params={"scope": "read", "role": "admin"})
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.json()["detail"] == "缺少 X-User", r.json()
    assert main.CALL_LOG == ["user"], main.CALL_LOG
    return f"401，CALL_LOG={main.CALL_LOG}"


def check_404_not_found_user() -> str:
    """用户不存在 → 404，后续层不执行。"""
    reset()
    r = client.get("/admin", params={"scope": "read"}, headers={"X-User": "nobody"})
    assert r.status_code == 404, (r.status_code, r.text)
    assert main.CALL_LOG == ["user"], main.CALL_LOG
    return "404，perms/role 未执行"


def check_403_insufficient_scope() -> str:
    """中间层 403：role 不执行（bob 只有 read 权限）。"""
    reset()
    r = client.get("/admin", params={"scope": "delete", "role": "admin"}, headers={"X-User": "bob"})
    assert r.status_code == 403, (r.status_code, r.text)
    assert "缺少权限 delete" in r.json()["detail"], r.json()
    assert main.CALL_LOG == ["user", "perms"], main.CALL_LOG
    return f"403，CALL_LOG={main.CALL_LOG}"


def check_403_missing_role() -> str:
    """最上层 403：bob 不是 admin。"""
    reset()
    r = client.get("/admin", params={"scope": "read", "role": "admin"}, headers={"X-User": "bob"})
    assert r.status_code == 403, (r.status_code, r.text)
    assert "需要角色 admin" in r.json()["detail"], r.json()
    return "403 需要角色 admin"


def check_openapi_dedup_param() -> str:
    """同一参数被多层依赖声明时，OpenAPI 只出现一次。"""
    params = client.get("/openapi.json").json()["paths"]["/admin"]["get"]["parameters"]
    names = [p["name"] for p in params]
    assert names.count("X-User") == 1, names
    assert set(names) == {"X-User", "scope", "role"}, names
    return f"parameters={names}（X-User 仅一次）"


def check_cache_key_is_callable() -> str:
    """缓存按「可调用对象」区分：不同函数各自缓存。"""
    probe = FastAPI()
    seen: list[str] = []

    def dep_a() -> str:
        seen.append("a")
        return "a"

    def dep_b() -> str:
        seen.append("b")
        return "b"

    @probe.get("/x")
    def x(a: str = Depends(dep_a), b: str = Depends(dep_b), a2: str = Depends(dep_a)) -> dict[str, str]:  # noqa: ANN001
        return {"a": a, "a2": a2, "b": b}

    r = TestClient(probe).get("/x")
    assert r.json() == {"a": "a", "a2": "a", "b": "b"}, r.json()
    assert seen == ["a", "b"], seen
    return f"seen={seen}（dep_a 只跑一次）"


def check_yield_cache_hint() -> str:
    """`yield` 依赖同样按请求缓存（第 40 章展开）。"""
    probe = FastAPI()
    created: list[int] = []

    def resource() -> object:
        created.append(1)

        class Res:
            pass

        return Res()

    @probe.get("/y")
    def y(r1: object = Depends(resource), r2: object = Depends(resource)) -> dict[str, bool]:  # noqa: ANN001
        return {"same": r1 is r2}

    r = TestClient(probe).get("/y")
    assert r.json() == {"same": True}, r.json()
    assert len(created) == 1, created
    return "同一请求内是同一个对象"


CHECKS = [
    ("三层依赖", check_three_layer_chain),
    ("执行顺序", check_execution_order),
    ("缓存只执行一次", check_cache_single_call),
    ("use_cache=False", check_use_cache_false),
    ("缓存不跨请求", check_cache_not_across_requests),
    ("叶子 401", check_401_from_leaf),
    ("用户 404", check_404_not_found_user),
    ("权限 403", check_403_insufficient_scope),
    ("角色 403", check_403_missing_role),
    ("OpenAPI 参数去重", check_openapi_dedup_param),
    ("缓存 key 是可调用对象", check_cache_key_is_callable),
    ("同请求同对象", check_yield_cache_hint),
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