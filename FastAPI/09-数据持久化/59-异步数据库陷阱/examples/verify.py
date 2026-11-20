"""第 59 章 · 自动验收。运行：python verify.py"""

import asyncio
import sys
import time
from pathlib import Path
from typing import Any, Awaitable, Callable

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import db  # noqa: E402
import main  # noqa: E402


def run_in_app(factory: Callable[[], Awaitable[Any]]) -> Any:
    """【作用】手动跑 lifespan，再用 ASGITransport 发真实并发请求"""

    async def runner() -> Any:
        async with main.app.router.lifespan_context(main.app):
            return await factory()

    return asyncio.run(runner())


async def timed_gather(path: str, params: dict[str, Any], n: int = 5) -> float:
    transport = httpx.ASGITransport(app=main.app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        started = time.perf_counter()
        responses = await asyncio.gather(*(client.get(path, params=params) for _ in range(n)))
        elapsed = (time.perf_counter() - started) * 1000
    assert all(r.status_code == 200 for r in responses), [r.status_code for r in responses]
    return elapsed


def check_blocking_is_serial() -> str:
    """`async def` + `time.sleep`：5 个并发请求串行 ≈ 1000ms。"""
    elapsed = run_in_app(lambda: timed_gather("/blocking", {"ms": 200}))
    assert elapsed > 800, elapsed
    return f"{elapsed:.0f}ms（≈ 5×200）"


def check_to_thread_is_parallel() -> str:
    """`to_thread` 隔离：5 个并发 ≈ 200ms。"""
    elapsed = run_in_app(lambda: timed_gather("/threaded", {"ms": 200}))
    assert elapsed < 500, elapsed
    return f"{elapsed:.0f}ms（≈ 200）"


def check_sync_def_is_parallel() -> str:
    """普通 `def` 端点：FastAPI 自动进线程池，同样并行。"""
    elapsed = run_in_app(lambda: timed_gather("/sync-def", {"ms": 200}))
    assert elapsed < 500, elapsed
    return f"{elapsed:.0f}ms"


def check_slow_sql_blocks() -> str:
    """真实慢 SQL 直接跑在事件循环里：5 个并发 ≈ 1000ms。"""
    elapsed = run_in_app(lambda: timed_gather("/db/slow", {"ms": 200, "threaded": False}))
    assert elapsed > 800, elapsed
    return f"{elapsed:.0f}ms（串行）"


def check_slow_sql_threaded() -> str:
    """同一个慢 SQL 用 `to_thread`：5 个并发 ≈ 200ms。"""
    elapsed = run_in_app(lambda: timed_gather("/db/slow", {"ms": 200, "threaded": True}))
    assert elapsed < 500, elapsed
    return f"{elapsed:.0f}ms（并行）"


def check_heartbeat_stalls() -> str:
    """心跳任务的最大间隔：阻塞 200ms → 间隔 ≈ 200ms；隔离 → 间隔 ≈ 时钟粒度。

    【要点】不能数 tick 数：Windows 上 `asyncio.sleep(0.005)` 实际约 15.6ms，
              阻塞 200ms 也只少跑十几次，区分度差。看**最大间隔**才准。
    """

    async def max_gap_ms(factory: Callable[[], Awaitable[Any]]) -> float:
        marks: list[float] = []

        async def beat() -> None:
            while True:
                marks.append(time.perf_counter())
                await asyncio.sleep(0.005)

        task = asyncio.create_task(beat())
        await asyncio.sleep(0.03)  # 先让心跳稳定跑出几个点
        try:
            await factory()
        finally:
            await asyncio.sleep(0.03)  # 阻塞后再跑几个点，闭合成间隔
            task.cancel()

        gaps = [(later - earlier) * 1000 for earlier, later in zip(marks, marks[1:])]
        assert gaps, f"心跳采样不足：{len(marks)}"
        return max(gaps)

    async def scenario() -> tuple[float, float]:
        async def run_blocking() -> None:
            main._slow_query(200)

        await max_gap_ms(lambda: asyncio.to_thread(main._slow_query, 50))  # 热身
        blocked = await max_gap_ms(run_blocking)
        threaded = await max_gap_ms(lambda: asyncio.to_thread(main._slow_query, 200))
        return blocked, threaded

    blocked, threaded = run_in_app(scenario)
    assert blocked > 150, f"阻塞时最大间隔只有 {blocked:.1f}ms"
    assert threaded < 80, f"隔离时最大间隔竟有 {threaded:.1f}ms"
    return f"阻塞最大间隔 {blocked:.0f}ms vs 隔离 {threaded:.0f}ms"


def check_n_plus_one() -> str:
    """逐条查作者：1 + 200 = 201 条 SQL。"""
    with TestClient(main.app) as c:
        body = c.get("/posts/n-plus-one").json()
    assert body["count"] == 200, body["count"]
    assert body["query_count"] == 201, body["query_count"]
    return "201 条 SQL"


def check_in_batch() -> str:
    """`IN` 批量：2 条 SQL。"""
    with TestClient(main.app) as c:
        body = c.get("/posts/in-batch").json()
    assert body["count"] == 200, body["count"]
    assert body["query_count"] == 2, body["query_count"]
    return "2 条 SQL"


def check_join() -> str:
    """`JOIN`：1 条 SQL。"""
    with TestClient(main.app) as c:
        body = c.get("/posts/joined").json()
    assert body["count"] == 200, body["count"]
    assert body["query_count"] == 1, body["query_count"]
    return "1 条 SQL"


def check_results_identical() -> str:
    """三种写法结果完全一致，只是代价差 200 倍。"""
    with TestClient(main.app) as c:
        n1 = c.get("/posts/n-plus-one").json()["sample"]
        batch = c.get("/posts/in-batch").json()["sample"]
        joined = c.get("/posts/joined").json()["sample"]
    assert n1 == batch == joined, (n1, batch, joined)
    return "sample 一致"


def check_thread_pool_limit() -> str:
    """提交 60 个阻塞任务，实际线程数不超过 `min(32, cpu+4)`。"""
    with TestClient(main.app) as c:
        body = c.get("/thread-ids", params={"count": 60}).json()
    limit = body["formula_limit"]
    assert body["unique_threads"] <= limit, body
    assert body["unique_threads"] >= int(limit * 0.8), body
    return f'{body["unique_threads"]} 线程（上限 {limit}，cpu {body["cpu_count"]}）'


def check_tasks_queue_beyond_pool() -> str:
    """任务数超过线程数 → 其余排队。"""
    with TestClient(main.app) as c:
        body = c.get("/thread-ids", params={"count": 60}).json()
    assert body["submitted"] > body["unique_threads"], body
    return f'60 个任务 / {body["unique_threads"]} 线程'


def check_locked_without_timeout() -> str:
    """`busy_timeout=0`：抢锁立刻失败。"""
    with TestClient(main.app) as c:
        body = c.get("/lock/probe", params={"busy_timeout_ms": 0}).json()
    assert body["succeeded"] is False, body
    assert body["error"] == "database is locked", body
    return body["error"]


def check_busy_timeout_waits() -> str:
    """`busy_timeout=500`：等到持锁者提交后成功。"""
    with TestClient(main.app) as c:
        body = c.get("/lock/probe", params={"busy_timeout_ms": 500}).json()
    assert body["succeeded"] is True, body
    assert body["error"] is None, body
    return "等待后写入成功"


def check_to_thread_propagates() -> str:
    """`to_thread` 里的异常会原样抛给 `await` 处，不会被吞。"""

    def boom() -> None:
        raise ValueError("线程里的错误")

    async def scenario() -> str:
        try:
            await asyncio.to_thread(boom)
        except ValueError as exc:
            return str(exc)
        raise AssertionError("异常被吞了")

    message = run_in_app(scenario)
    assert message == "线程里的错误", message
    return message


CHECKS = [
    ("阻塞串行", check_blocking_is_serial),
    ("to_thread 并行", check_to_thread_is_parallel),
    ("def 自动线程池", check_sync_def_is_parallel),
    ("慢 SQL 阻塞", check_slow_sql_blocks),
    ("慢 SQL 隔离", check_slow_sql_threaded),
    ("心跳停摆", check_heartbeat_stalls),
    ("N+1 = 201", check_n_plus_one),
    ("IN = 2", check_in_batch),
    ("JOIN = 1", check_join),
    ("结果一致", check_results_identical),
    ("线程池上限", check_thread_pool_limit),
    ("超出则排队", check_tasks_queue_beyond_pool),
    ("无 timeout 即锁", check_locked_without_timeout),
    ("busy_timeout 生效", check_busy_timeout_waits),
    ("异常不吞", check_to_thread_propagates),
]


def run() -> int:
    failures = 0
    for name, func in CHECKS:
        try:
            print(f"[PASS] {name} -> {func()}")
        except Exception as exc:  # noqa: BLE001 - 验收脚本要报告任何失败
            failures += 1
            print(f"[FAIL] {name} -> {type(exc).__name__}: {exc}")
    db.DB_FILE.unlink(missing_ok=True)
    print(f"\n结果：{len(CHECKS) - failures}/{len(CHECKS)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())