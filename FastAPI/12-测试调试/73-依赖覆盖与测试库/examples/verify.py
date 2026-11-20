"""第 73 章 · 自动验收。运行：python verify.py"""

import sys
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

SCHEMA_PATHS = {"/users", "/users/{user_id}", "/me", "/config"}


def reset() -> None:
    main.app.dependency_overrides.clear()
    main.REAL_DB["users"] = {1: {"id": 1, "name": "真实用户"}, 2: {"id": 2, "name": "另一个"}}
    main.REAL_DB["next_id"] = 3


def fake() -> dict[str, Any]:
    return {"users": {9: {"id": 9, "name": "假用户"}}, "next_id": 10}


@contextmanager
def overrides(**mapping: Any) -> Iterator[TestClient]:
    """【作用】模拟 pytest fixture：进则覆盖，出则清理"""
    with TestClient(main.app) as client:
        try:
            for name, fake_impl in mapping.items():
                main.app.dependency_overrides[getattr(main, name)] = fake_impl
            yield client
        finally:
            main.app.dependency_overrides.clear()


def check_real_data() -> str:
    """无覆盖：读到真实库。"""
    reset()
    with overrides() as c:
        body = c.get("/users").json()
    assert len(body) == 2, body
    return "2 条真实用户"


def check_fake_db() -> str:
    """覆盖 `get_db`：读到假库。"""
    reset()
    with overrides(get_db=fake) as c:
        body = c.get("/users").json()
    assert body == [{"id": 9, "name": "假用户"}], body
    return "1 条假用户"


def check_fake_detail() -> str:
    """假库里的 id 有、真实 id 没有。"""
    reset()
    with overrides(get_db=fake) as c:
        hit = c.get("/users/9")
        miss = c.get("/users/1")
    assert hit.status_code == 200, hit.status_code
    assert miss.status_code == 404, miss.status_code
    return "9 → 200 / 1 → 404"


def check_real_db_untouched() -> str:
    """假库里的写操作不污染真实库。"""
    reset()
    with overrides(get_db=fake) as c:
        created = c.post("/users", json={"name": "新用户"}).json()
    assert created == {"id": 10, "name": "新用户"}, created
    assert sorted(main.REAL_DB["users"]) == [1, 2], main.REAL_DB
    return "假库 id=10，真实库仍 [1,2]"


def check_auth_required_originally() -> str:
    """无覆盖：`/me` 401。"""
    reset()
    with overrides() as c:
        assert c.get("/me").status_code == 401
        ok = c.get("/me", headers={"X-Token": main.ADMIN_TOKEN})
    assert ok.json() == {"user": "admin"}, ok.json()
    return "401 → 带令牌 200"


def check_auth_bypassed() -> str:
    """覆盖 `get_current_user`：不带令牌也过。"""
    reset()
    with overrides(get_current_user=lambda: "tester") as c:
        body = c.get("/me").json()
    assert body == {"user": "tester"}, body
    return "user=tester"


def check_settings_overridden() -> str:
    """覆盖 `get_settings`：`max_items` 立刻生效。"""
    reset()
    with overrides(get_db=fake, get_settings=lambda: main.Settings(max_items=1)) as c:
        config = c.get("/config").json()
        users = c.get("/users").json()
    assert config["max_items"] == 1, config
    assert len(users) == 1, users
    return "max_items=1，列表被截断到 1"


def check_nested_dependency_follows() -> str:
    """**关键**：只覆盖 `get_db`，`get_repo` 这个嵌套依赖自动跟着换。"""
    reset()
    with overrides(get_db=fake) as c:
        body = c.get("/users").json()
    assert body == [{"id": 9, "name": "假用户"}], body
    assert "get_repo" not in {func.__name__ for func in main.app.dependency_overrides}
    return "get_repo 未覆盖，仍用假库"


def check_schema_unaffected() -> str:
    """覆盖不改 `openapi()`。"""
    reset()
    before = set(TestClient(main.app).get("/openapi.json").json()["paths"])
    with overrides(get_db=fake, get_current_user=lambda: "x") as c:
        during = set(c.get("/openapi.json").json()["paths"])
    assert before == during == SCHEMA_PATHS, (before, during)
    return f"{len(during)} 条路径不变"


def check_clear_restores() -> str:
    """`clear()` 后恢复真实行为。"""
    reset()
    with overrides(get_db=fake) as c:
        c.get("/users")
    with TestClient(main.app) as c:
        assert len(c.get("/users").json()) == 2
        assert c.get("/me").status_code == 401
    return "恢复 2 条 + 401"


def check_overrides_is_dict_of_functions() -> str:
    """`dependency_overrides` 的 key 是**函数对象**。"""
    reset()
    with overrides(get_db=fake, get_settings=lambda: main.Settings(max_items=5)):
        keys = list(main.app.dependency_overrides)
        assert keys == [main.get_db, main.get_settings], keys
        assert isinstance(main.app.dependency_overrides, dict)
    return "get_db / get_settings"


def check_lambda_is_enough() -> str:
    """替身可以就是个 lambda。"""
    reset()
    with overrides(get_db=lambda: fake()) as c:
        assert c.get("/users/9").status_code == 200
    return "lambda 可用"


def check_422_still_real() -> str:
    """数据层是假的，参数校验是真的。"""
    reset()
    with overrides(get_db=fake) as c:
        response = c.post("/users", json={"name": ""})
    assert response.status_code == 422, response.status_code
    assert response.json()["detail"][0]["type"] == "string_too_short", response.json()
    return "422 string_too_short"


def check_404_still_real() -> str:
    """路由层 404 不受影响。"""
    reset()
    with overrides(get_db=fake) as c:
        assert c.get("/nope").status_code == 404
        assert c.get("/users/9").status_code == 200
    return "不存在路由仍 404"


def check_fixture_cleanup() -> str:
    """fixture 风格：异常路径也要清理。"""
    reset()
    try:
        with overrides(get_db=fake) as c:
            c.get("/users")
            raise RuntimeError("用例中途失败")
    except RuntimeError:
        pass
    assert main.app.dependency_overrides == {}, main.app.dependency_overrides
    with TestClient(main.app) as c:
        assert len(c.get("/users").json()) == 2
    return "异常后仍清理干净"


CHECKS = [
    ("真实数据", check_real_data),
    ("假库数据", check_fake_db),
    ("假库详情", check_fake_detail),
    ("真实库不污染", check_real_db_untouched),
    ("原始鉴权", check_auth_required_originally),
    ("绕过鉴权", check_auth_bypassed),
    ("覆盖配置", check_settings_overridden),
    ("嵌套依赖跟随", check_nested_dependency_follows),
    ("schema 不变", check_schema_unaffected),
    ("清理后恢复", check_clear_restores),
    ("key 是函数对象", check_overrides_is_dict_of_functions),
    ("lambda 替身", check_lambda_is_enough),
    ("422 仍生效", check_422_still_real),
    ("404 仍生效", check_404_still_real),
    ("异常也清理", check_fixture_cleanup),
]


def run() -> int:
    reset()
    failures = 0
    for name, func in CHECKS:
        try:
            print(f"[PASS] {name} -> {func()}")
        except Exception as exc:  # noqa: BLE001 - 验收脚本要报告任何失败
            failures += 1
            print(f"[FAIL] {name} -> {type(exc).__name__}: {exc}")
    reset()
    print(f"\n结果：{len(CHECKS) - failures}/{len(CHECKS)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())