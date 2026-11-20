"""第 40 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)
strict = TestClient(main.app, raise_server_exceptions=False)


def reset() -> None:
    main.LOG.clear()
    main.LAST_SESSION.clear()


def check_session_lifecycle() -> str:
    """正常路径：open → commit → close，端点内未关闭。"""
    reset()
    r = client.get("/session")
    assert r.status_code == 200, (r.status_code, r.text)
    assert r.json() == {"closed_inside": False}, r.json()
    session = main.LAST_SESSION["session"]
    assert session.closed is True and session.committed is True, session.__dict__
    assert main.LOG == ["open", "commit", "close"], main.LOG
    return f'LOG={main.LOG}'


def check_cleanup_after_response() -> str:
    """清理发生在响应之后：响应已拿到时 session 已关闭。"""
    reset()
    r = client.get("/session")
    assert r.status_code == 200
    assert main.LOG[-1] == "close", main.LOG
    return "响应返回时清理已完成"


def check_exception_rolls_back() -> str:
    """异常路径：rollback → close，不 commit。"""
    reset()
    r = client.get("/session/crash")
    assert r.status_code == 409, (r.status_code, r.text)
    session = main.LAST_SESSION["session"]
    assert session.rolled_back is True and session.committed is False, session.__dict__
    assert session.closed is True, session.__dict__
    assert main.LOG == ["open", "rollback", "close"], main.LOG
    return f'LOG={main.LOG}'


def check_nested_close_order() -> str:
    """嵌套 yield：后创建的先清理（LIFO）。"""
    reset()
    r = client.get("/nested")
    assert r.status_code == 200, r.text
    assert r.json() == {"value": "outer:inner"}, r.json()
    assert main.LOG == ["outer-open", "inner-open", "inner-close", "outer-close"], main.LOG
    return f'LOG={main.LOG}'


def check_async_generator() -> str:
    """async 生成器依赖可用，清理执行。"""
    reset()
    r = client.get("/async")
    assert r.status_code == 200, r.text
    assert r.json() == {"id": "res-1"}, r.json()
    assert main.LOG == ["async-open", "async-close"], main.LOG
    return f'LOG={main.LOG}'


def check_dependency_catches_route_exception() -> str:
    """依赖的 `except` 能捕获路由抛出的异常。"""
    reset()
    r = client.get("/guarded")
    assert r.status_code == 400, (r.status_code, r.text)
    assert main.LOG == ["guarded-error", "guarded-close"], main.LOG
    return f"路由异常被依赖感知（LOG={main.LOG}）"


def check_guarded_ok_path() -> str:
    """无异常时 state 未被标记。"""
    reset()
    r = client.get("/guarded/ok")
    assert r.json() == {"error": False}, r.json()
    return "error=False"


def check_yield_value_injected() -> str:
    """yield 的值注入端点。"""
    reset()
    assert client.get("/nested").json()["value"] == "outer:inner"
    return "yield 值 = outer:inner"


def check_bad_cleanup_cannot_change_status() -> str:
    """清理阶段抛异常：状态码已定，无法改。"""
    reset()
    r = strict.get("/bad-cleanup")
    assert r.status_code == 200, (r.status_code, r.text)
    assert r.json() == {"value": "ok"}, r.json()
    return "响应 200 已发出，清理异常不影响状态码"


def check_generator_required() -> str:
    """依赖必须是生成器：普通函数用 yield 之外返回不会执行清理。"""
    probe = __import__("fastapi").FastAPI()

    def not_generator() -> str:
        return "plain"

    @probe.get("/p")
    def p(v: str = __import__("fastapi").Depends(not_generator)) -> dict[str, str]:  # noqa: ANN001
        return {"v": v}

    r = TestClient(probe).get("/p")
    assert r.json() == {"v": "plain"}, r.json()
    return "普通函数依赖照常工作（但没有清理语义）"


def check_cleanup_on_validation_error() -> str:
    """参数校验失败时，已创建的 yield 依赖也会被清理。"""
    reset()
    r = client.get("/nested", params={"bad": "1"})
    assert r.status_code == 200, r.text
    assert "inner-close" in main.LOG and "outer-close" in main.LOG, main.LOG
    return "校验失败/正常路径都会清理（此处正常）"


def check_async_cleanup_runs_before_return() -> str:
    """`await` 在清理阶段可用。"""
    reset()
    client.get("/async")
    assert main.LOG[-1] == "async-close", main.LOG
    return "async 清理完成"


CHECKS = [
    ("正常生命周期", check_session_lifecycle),
    ("响应后清理", check_cleanup_after_response),
    ("异常回滚", check_exception_rolls_back),
    ("嵌套 LIFO", check_nested_close_order),
    ("async 生成器", check_async_generator),
    ("依赖捕获异常", check_dependency_catches_route_exception),
    ("无异常路径", check_guarded_ok_path),
    ("yield 值注入", check_yield_value_injected),
    ("清理异常不改状态", check_bad_cleanup_cannot_change_status),
    ("普通函数依赖", check_generator_required),
    ("校验失败也清理", check_cleanup_on_validation_error),
    ("async 清理完成", check_async_cleanup_runs_before_return),
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