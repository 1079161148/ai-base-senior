"""第 70 章 · 自动验收。运行：python verify.py"""

import asyncio
import sys
import threading
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402


def client(strict: bool = True) -> TestClient:
    main.reset()
    return TestClient(main.app, raise_server_exceptions=strict)


def check_response_accepted() -> str:
    """响应体在任务执行前就已生成。"""
    with client() as c:
        response = c.post("/orders", params={"name": "键盘"})
    assert response.status_code == 200, response.status_code
    assert response.json()["status"] == "accepted", response.json()
    return "200 accepted"


def check_endpoint_before_tasks() -> str:
    """`EVENTS` 里端点一定排在最前。"""
    with client() as c:
        c.post("/orders", params={"name": "键盘"})
    assert main.EVENTS[0] == "endpoint", main.EVENTS
    return " → ".join(main.EVENTS)


def check_two_tasks_in_order() -> str:
    """同步任务先于异步任务（按添加顺序串行）。"""
    with client() as c:
        c.post("/orders", params={"name": "键盘"})
    assert main.EVENTS == ["endpoint", "record:键盘", "notify:键盘:email"], main.EVENTS
    return "record → notify"


def check_kwargs_passed() -> str:
    """`add_task` 支持位置与关键字参数。"""
    with client() as c:
        c.post("/orders", params={"name": "鼠标", "channel": "sms"})
    assert "notify:鼠标:sms" in main.EVENTS, main.EVENTS
    return "notify:鼠标:sms"


def check_three_tasks_ordered() -> str:
    """三个任务严格按添加顺序执行。"""
    with client() as c:
        c.post("/orders/three")
    assert main.EVENTS == ["record:t0", "record:t1", "record:t2"], main.EVENTS
    return "t0 → t1 → t2"


def check_sync_task_uses_threadpool() -> str:
    """同步任务在线程池里跑，与 `async def` 端点的事件循环线程不同。"""
    with client() as c:
        c.post("/orders/thread")
    loop_thread = main.RESULTS["loop_thread"]
    task_thread = main.RESULTS["record_thread"]
    assert loop_thread != task_thread, (loop_thread, task_thread)
    return f"loop={loop_thread} / task={task_thread}"


def check_async_task_uses_loop() -> str:
    """异步任务在当前事件循环里跑。"""
    with client() as c:
        c.post("/orders", params={"name": "键盘"})
    loop = main.RESULTS["notify_loop"]
    assert isinstance(loop, asyncio.AbstractEventLoop), loop
    return type(loop).__name__


def check_exception_does_not_break_response() -> str:
    """任务抛异常：宽松模式下客户端仍拿到 200。"""
    with client(strict=False) as c:
        response = c.post("/orders/boom")
    assert response.status_code == 200, response.status_code
    assert response.json() == {"status": "accepted"}, response.json()
    assert main.EVENTS == ["boom"], main.EVENTS
    return "200 已返回，异常在服务端"


def check_exception_raises_in_strict() -> str:
    """严格模式能暴露后台任务异常。"""
    try:
        with client() as c:
            c.post("/orders/boom")
    except RuntimeError as exc:
        assert "后台任务失败了" in str(exc), exc
        return str(exc)
    raise AssertionError("异常被吞了")


def check_dependency_add_task() -> str:
    """依赖里 `add_task` 同样生效。"""
    with client() as c:
        c.get("/audited")
    assert main.EVENTS == ["audited-endpoint", "record:from-dependency"], main.EVENTS
    return "依赖任务在端点之后"


def check_client_waits() -> str:
    """`TestClient` 会等后台任务跑完（耗时包含 120ms）。"""
    started = time.perf_counter()
    with client() as c:
        response = c.post("/orders/slow")
    elapsed = (time.perf_counter() - started) * 1000
    assert response.status_code == 200, response.status_code
    assert elapsed >= 100, elapsed
    return f"{elapsed:.0f}ms（含 120ms 任务）"


def check_state_available_in_task() -> str:
    """任务里能访问 `app.state`。"""
    with client() as c:
        first = c.post("/orders/state").json()
        second = c.post("/orders/state").json()
    assert first["counter"] == 1, first
    assert second["counter"] == 2, second
    assert main.EVENTS.count("record:state") == 2, main.EVENTS
    return "counter 1 → 2"


def check_create_task_not_awaited() -> str:
    """`asyncio.create_task` 不被等待，接口立刻返回。"""
    started = time.perf_counter()
    with client() as c:
        response = c.post("/orders/fire-and-forget")
    elapsed = (time.perf_counter() - started) * 1000
    assert response.status_code == 200, response.status_code
    assert elapsed < 100, elapsed
    assert "fire-endpoint" in main.EVENTS, main.EVENTS
    return f"{elapsed:.0f}ms，不等待"


def check_next_request_unaffected() -> str:
    """后台任务失败后，后续请求照常。"""
    with TestClient(main.app, raise_server_exceptions=False) as c:
        main.reset()
        c.post("/orders/boom")
        main.reset()
        response = c.post("/orders", params={"name": "恢复"})
    assert response.status_code == 200, response.status_code
    assert main.EVENTS == ["endpoint", "record:恢复", "notify:恢复:email"], main.EVENTS
    return "失败不影响后续"


CHECKS = [
    ("响应已生成", check_response_accepted),
    ("端点在前", check_endpoint_before_tasks),
    ("两任务顺序", check_two_tasks_in_order),
    ("kwargs 传递", check_kwargs_passed),
    ("三任务顺序", check_three_tasks_ordered),
    ("同步走线程池", check_sync_task_uses_threadpool),
    ("异步走事件循环", check_async_task_uses_loop),
    ("异常不影响响应", check_exception_does_not_break_response),
    ("异常可暴露", check_exception_raises_in_strict),
    ("依赖里挂任务", check_dependency_add_task),
    ("客户端会等待", check_client_waits),
    ("state 可用", check_state_available_in_task),
    ("create_task 不等待", check_create_task_not_awaited),
    ("失败不连累后续", check_next_request_unaffected),
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