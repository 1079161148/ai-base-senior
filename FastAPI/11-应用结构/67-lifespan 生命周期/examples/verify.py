"""第 67 章 · 自动验收。运行：python verify.py"""

import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402


def fresh() -> TestClient:
    main.EVENTS.clear()
    return TestClient(main.app)


def check_no_with_no_lifespan() -> str:
    """不用 `with`：构造 `TestClient` 不触发 lifespan。"""
    main.EVENTS.clear()
    TestClient(main.app)
    assert main.EVENTS == [], main.EVENTS
    return "未触发任何事件"


def check_startup_on_enter() -> str:
    """`with` 进入时执行 startup。"""
    with fresh() as c:
        assert main.EVENTS == ["startup:begin", "startup:end"], main.EVENTS
        assert c.get("/events").json()["events"] == main.EVENTS
    return "startup:begin → startup:end"


def check_startup_order() -> str:
    """startup 内部顺序：begin 在 end 之前。"""
    with fresh():
        assert main.EVENTS.index("startup:begin") < main.EVENTS.index("startup:end")
    return "begin → end"


def check_resources_warmed() -> str:
    """启动阶段预热的资源在请求里可用。"""
    with fresh() as c:
        body = c.get("/ping").json()
    assert body["warmed"] is True, body
    assert body["rows"] == 5, body
    return f'warmed=True, rows={body["rows"]}'


def check_uptime_positive() -> str:
    """`app.state.started_at` 在启动阶段写入。"""
    with fresh() as c:
        body = c.get("/ping").json()
    assert body["uptime_ms"] >= 0, body
    return f'{body["uptime_ms"]}ms'


def check_shutdown_on_exit() -> str:
    """`with` 退出时执行 shutdown。"""
    with fresh() as c:
        c.get("/ping")
    assert "shutdown:begin" in main.EVENTS, main.EVENTS
    assert "shutdown:end" in main.EVENTS, main.EVENTS
    return " → ".join(main.EVENTS[-2:])


def check_full_sequence() -> str:
    """完整顺序：startup → 请求 → shutdown。"""
    with fresh() as c:
        c.get("/ping")
        inside = list(main.EVENTS)
    full = list(main.EVENTS)
    assert inside == ["startup:begin", "startup:end"], inside
    assert full == ["startup:begin", "startup:end", "shutdown:begin", "shutdown:end"], full
    return " → ".join(full)


def check_two_runs() -> str:
    """两次 `with` 各跑一遍，互不残留状态。"""
    with fresh() as c:
        c.get("/ping")
        first_cache = c.app.state.cache
    with TestClient(main.app) as c:
        second_cache = c.app.state.cache
        c.get("/ping")
    assert first_cache is not second_cache, "state 没重建"
    assert main.EVENTS.count("startup:begin") == 2, main.EVENTS
    assert main.EVENTS.count("shutdown:begin") == 2, main.EVENTS
    return "startup ×2 / shutdown ×2"


def check_startup_failure() -> str:
    """启动阶段抛异常：`with` 直接抛，服务起不来。"""
    main.EVENTS.clear()
    try:
        with TestClient(main.failing_app) as bad:
            bad.get("/never")
    except RuntimeError as exc:
        assert "预热失败" in str(exc), exc
        assert "failing:startup" in main.EVENTS, main.EVENTS
        return str(exc)
    raise AssertionError("居然启动成功了")


def check_startup_failure_no_shutdown() -> str:
    """启动失败时不会进入关闭阶段。"""
    main.EVENTS.clear()
    try:
        with TestClient(main.failing_app):
            pass
    except RuntimeError:
        pass
    assert main.EVENTS == ["failing:startup"], main.EVENTS
    return "只有 startup，没有 shutdown"


def check_shutdown_failure_after_response() -> str:
    """关闭阶段抛异常：响应早已正常返回。"""
    main.EVENTS.clear()
    try:
        with TestClient(main.noisy_app) as c:
            response = c.get("/ok")
            assert response.status_code == 200, response.status_code
            assert response.json() == {"ok": "true"}, response.json()
    except RuntimeError:
        pass  # 关闭异常在退出时抛，不影响已经发出的响应
    return "响应 200 已返回（异常发生在退出时）"


def check_shutdown_failure_raises_on_exit() -> str:
    """关闭阶段的异常在 `with` 退出时抛出。"""
    main.EVENTS.clear()
    try:
        with TestClient(main.noisy_app) as c:
            c.get("/ok")
    except RuntimeError as exc:
        assert "关闭时炸了" in str(exc), exc
        assert main.EVENTS == ["noisy:startup", "noisy:shutdown-raise"], main.EVENTS
        return str(exc)
    raise AssertionError("关闭异常被吞了")


def check_state_persists_across_requests() -> str:
    """`app.state` 跨请求是同一个对象。"""
    with fresh() as c:
        first = c.get("/ping").json()
        second = c.get("/ping").json()
    assert first["uptime_ms"] <= second["uptime_ms"], (first, second)
    return "两次请求共享 started_at"


def check_startup_awaits() -> str:
    """lifespan 里的 `await` 真会等（0.01s 预热）。"""
    main.EVENTS.clear()
    started = time.perf_counter()
    with TestClient(main.app):
        pass
    elapsed = (time.perf_counter() - started) * 1000
    assert elapsed >= 12, elapsed
    return f"进入耗时 {elapsed:.0f}ms（含 10ms 预热）"


CHECKS = [
    ("无 with 不触发", check_no_with_no_lifespan),
    ("进入触发 startup", check_startup_on_enter),
    ("startup 顺序", check_startup_order),
    ("资源已预热", check_resources_warmed),
    ("uptime 写入", check_uptime_positive),
    ("退出触发 shutdown", check_shutdown_on_exit),
    ("完整顺序", check_full_sequence),
    ("两次运行", check_two_runs),
    ("启动失败", check_startup_failure),
    ("失败无 shutdown", check_startup_failure_no_shutdown),
    ("关闭异常不影响响应", check_shutdown_failure_after_response),
    ("关闭异常在退出抛出", check_shutdown_failure_raises_on_exit),
    ("state 跨请求", check_state_persists_across_requests),
    ("startup 真 await", check_startup_awaits),
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