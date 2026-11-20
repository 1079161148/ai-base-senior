"""第 41 章 · 自动验收。运行：python verify.py"""

import sys
from collections.abc import Iterator
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from typing import Annotated  # noqa: E402

from fastapi import Depends, FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def reset() -> None:
    main.REAL_CALLS.clear()
    main.app.dependency_overrides.clear()


def fake_db() -> Iterator[dict[str, str]]:
    yield {"source": "fake-db"}


def check_real_dependency() -> str:
    """默认走真实依赖。"""
    reset()
    r = client.get("/items")
    assert r.status_code == 200, (r.status_code, r.text)
    assert r.json()["source"] == "real-db", r.json()
    assert main.REAL_CALLS == ["open", "close"], main.REAL_CALLS
    return f'source=real-db, REAL_CALLS={main.REAL_CALLS}'


def check_override_function() -> str:
    """覆盖后走替身，真实依赖完全不执行。"""
    reset()
    main.app.dependency_overrides[main.get_db] = fake_db
    r = client.get("/items")
    assert r.json()["source"] == "fake-db", r.json()
    assert main.REAL_CALLS == [], main.REAL_CALLS
    reset()
    return "source=fake-db，真实依赖 0 次调用"


def check_override_nested() -> str:
    """覆盖子依赖：父依赖自动使用替身。"""
    reset()
    main.app.dependency_overrides[main.get_db] = fake_db
    r = client.get("/config")
    assert r.status_code == 200, r.text
    assert r.json()["db"] == "fake-db", r.json()
    reset()
    return "嵌套依赖也换了"


def check_clear_restores() -> str:
    """清空覆盖后恢复真实实现。"""
    reset()
    main.app.dependency_overrides[main.get_db] = fake_db
    assert client.get("/items").json()["source"] == "fake-db"
    main.app.dependency_overrides.clear()
    assert client.get("/items").json()["source"] == "real-db"
    return "clear() 后恢复 real-db"


def check_override_auth() -> str:
    """覆盖鉴权依赖，测试里免登录。"""
    reset()
    assert client.get("/me").status_code == 401

    def fake_token() -> str:
        return "test-token"

    main.app.dependency_overrides[main.require_token] = fake_token
    r = client.get("/me")
    assert r.status_code == 200 and r.json() == {"token": "test-token"}, r.text
    reset()
    return "401 → 200（token=test-token）"


def check_override_class_dependency() -> str:
    """类依赖的 key 是类对象。"""
    reset()

    class FakeClock:
        now = "1999-01-01T00:00:00"

    main.app.dependency_overrides[main.Clock] = FakeClock
    r = client.get("/now")
    assert r.json() == {"now": "1999-01-01T00:00:00"}, r.json()
    reset()
    return "Clock → FakeClock"


def check_key_is_object_not_name() -> str:
    """覆盖按对象匹配：另一个同名函数无效。"""
    reset()

    def get_db() -> dict[str, str]:  # noqa: F811 —— 故意同名
        return {"source": "impostor"}

    main.app.dependency_overrides[get_db] = lambda: {"source": "impostor"}
    r = client.get("/items")
    assert r.json()["source"] == "real-db", r.json()
    reset()
    return "同名函数作 key 不生效（对象不同）"


def check_override_does_not_change_openapi() -> str:
    """覆盖不改变 OpenAPI。"""
    reset()
    before = client.get("/openapi.json").json()
    main.app.dependency_overrides[main.get_db] = fake_db
    after = client.get("/openapi.json").json()
    reset()
    assert before == after, "覆盖不应影响 schema"
    return "schema 完全一致"


def check_override_params_still_parsed() -> str:
    """替身自己的参数照样被解析。"""
    reset()
    probe = FastAPI()

    def real(x: str = "real") -> str:
        return x

    def fake(y: Annotated[int, __import__("fastapi").Query(ge=1)] = 1) -> str:
        return f"fake-{y}"

    @probe.get("/q")
    def q(v: Annotated[str, Depends(real)]) -> dict[str, str]:  # noqa: ANN202
        return {"v": v}

    probe.dependency_overrides[real] = fake
    c = TestClient(probe)
    assert c.get("/q", params={"y": 5}).json() == {"v": "fake-5"}, c.get("/q", params={"y": 5}).json()
    assert c.get("/q", params={"y": 0}).status_code == 422
    return "替身的 y 参数生效且被校验"


def check_override_only_current_app() -> str:
    """覆盖只作用于本 app。"""
    reset()
    other = FastAPI()

    def dep() -> str:
        return "orig"

    @other.get("/d")
    def d(v: Annotated[str, Depends(dep)]) -> dict[str, str]:  # noqa: ANN202
        return {"v": v}

    main.app.dependency_overrides[main.get_db] = fake_db
    assert TestClient(other).get("/d").json() == {"v": "orig"}
    reset()
    return "其他 app 不受影响"


def check_override_yield_cleanup() -> str:
    """替身也可以不是生成器（不会被清理逻辑影响）。"""
    reset()

    def plain_fake() -> dict[str, str]:
        return {"source": "plain-fake"}

    main.app.dependency_overrides[main.get_db] = plain_fake
    r = client.get("/items")
    assert r.json()["source"] == "plain-fake", r.json()
    reset()
    return "非生成器替身可用"


CHECKS = [
    ("真实依赖", check_real_dependency),
    ("覆盖函数", check_override_function),
    ("覆盖嵌套依赖", check_override_nested),
    ("clear 恢复", check_clear_restores),
    ("覆盖鉴权", check_override_auth),
    ("覆盖类依赖", check_override_class_dependency),
    ("key 是对象", check_key_is_object_not_name),
    ("不影响 OpenAPI", check_override_does_not_change_openapi),
    ("替身参数被解析", check_override_params_still_parsed),
    ("只影响本 app", check_override_only_current_app),
    ("非生成器替身", check_override_yield_cleanup),
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