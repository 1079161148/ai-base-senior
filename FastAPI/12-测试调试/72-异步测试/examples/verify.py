"""第 72 章 · 自动验收。运行：python verify.py"""

import asyncio
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

import httpx  # noqa: E402
from asgi_lifespan import LifespanManager  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from httpx import ASGITransport, AsyncClient  # noqa: E402

import main  # noqa: E402


def reset() -> None:
    main.STATE.update(started=False, calls=0)


def transport() -> ASGITransport:
    return ASGITransport(app=main.app)


async def check_items_200() -> str:
    """基础请求：200 + body。"""
    reset()
    async with AsyncClient(transport=transport(), base_url="http://test") as c:
        response = await c.get("/items")
    assert response.status_code == 200, response.status_code
    assert response.json() == [{"id": 1, "name": "键盘"}], response.json()
    return "200 / 1 条"


async def check_lifespan_not_run() -> str:
    """不套 `LifespanManager`：lifespan 不执行。"""
    reset()
    async with AsyncClient(transport=transport(), base_url="http://test") as c:
        body = (await c.get("/state")).json()
    assert body == {"started": False}, body
    return "started=False"


async def check_lifespan_with_manager() -> str:
    """`LifespanManager` 之后：lifespan 执行。"""
    reset()
    async with LifespanManager(main.app):
        async with AsyncClient(transport=transport(), base_url="http://test") as c:
            body = (await c.get("/state")).json()
    assert body == {"started": True}, body
    return "started=True"


async def check_concurrent() -> str:
    """3 个 100ms 请求并发 ≈ 100ms。"""
    reset()
    async with AsyncClient(transport=transport(), base_url="http://test") as c:
        started = time.perf_counter()
        responses = await asyncio.gather(*[c.get("/slow", params={"ms": 100}) for _ in range(3)])
        elapsed = (time.perf_counter() - started) * 1000
    assert all(response.status_code == 200 for response in responses)
    assert elapsed < 200, elapsed
    return f"{elapsed:.0f}ms（串行应 300ms）"


async def check_serial() -> str:
    """3 个 100ms 请求串行 ≈ 300ms。"""
    reset()
    async with AsyncClient(transport=transport(), base_url="http://test") as c:
        started = time.perf_counter()
        for _ in range(3):
            await c.get("/slow", params={"ms": 100})
        elapsed = (time.perf_counter() - started) * 1000
    assert elapsed > 250, elapsed
    return f"{elapsed:.0f}ms"


async def check_query_params() -> str:
    """`params=` 生效。"""
    reset()
    async with AsyncClient(transport=transport(), base_url="http://test") as c:
        response = await c.get("/slow", params={"ms": 1})
    assert response.json() == {"slept": 1}, response.json()
    return "ms=1"


async def check_post_json() -> str:
    """`json=` 发送与回显。"""
    reset()
    async with AsyncClient(transport=transport(), base_url="http://test") as c:
        response = await c.post("/echo", json={"name": "鼠标"})
    assert response.status_code == 200, response.status_code
    assert response.json() == {"name": "鼠标"}, response.json()
    return "echo 一致"


async def check_404() -> str:
    """404 + detail。"""
    reset()
    async with AsyncClient(transport=transport(), base_url="http://test") as c:
        response = await c.get("/items/999")
    assert response.status_code == 404, response.status_code
    assert response.json()["detail"] == "item not found", response.json()
    return "404 / item not found"


async def check_422() -> str:
    """422 + `string_too_short`。"""
    reset()
    async with AsyncClient(transport=transport(), base_url="http://test") as c:
        response = await c.post("/echo", json={"name": ""})
    assert response.status_code == 422, response.status_code
    assert response.json()["detail"][0]["type"] == "string_too_short", response.json()
    return "422 string_too_short"


async def check_timeout_ignored() -> str:
    """**实测坑**：`AsyncClient(timeout=...)` 对 `ASGITransport` 不生效。"""
    reset()
    async with AsyncClient(transport=transport(), base_url="http://test", timeout=0.02) as c:
        started = time.perf_counter()
        response = await c.get("/slow", params={"ms": 200})
        elapsed = (time.perf_counter() - started) * 1000
    assert response.status_code == 200, response.status_code
    assert elapsed > 150, elapsed
    return f"timeout=0.02 仍等了 {elapsed:.0f}ms"


async def check_wait_for_timeout() -> str:
    """测超时要 `asyncio.wait_for`。"""
    reset()
    async with AsyncClient(transport=transport(), base_url="http://test") as c:
        try:
            await asyncio.wait_for(c.get("/slow", params={"ms": 200}), timeout=0.05)
        except asyncio.TimeoutError:
            return "asyncio.TimeoutError"
    raise AssertionError("wait_for 没超时")


async def check_calls_accumulate() -> str:
    """同一个 client 多次请求共享服务端状态。"""
    reset()
    async with AsyncClient(transport=transport(), base_url="http://test") as c:
        await c.get("/items")
        await c.get("/items")
        body = (await c.get("/calls")).json()
    assert body["calls"] == 2, body
    return "calls=2"


async def check_base_url() -> str:
    """`ASGITransport` 不开端口，URL 仍是测试域名。"""
    reset()
    async with AsyncClient(transport=transport(), base_url="http://test") as c:
        response = await c.get("/items")
    assert str(response.request.url) == "http://test/items", response.request.url
    return "http://test/items"


async def check_same_result_as_testclient() -> str:
    """`AsyncClient` 与 `TestClient` 结果一致。"""
    reset()
    async with AsyncClient(transport=transport(), base_url="http://test") as c:
        async_body = (await c.get("/items")).json()
    reset()
    sync_body = TestClient(main.app).get("/items").json()
    assert async_body == sync_body, (async_body, sync_body)
    return "完全一致"


CHECKS: list[tuple[str, Any]] = [
    ("列表 200", check_items_200),
    ("无 LM 不跑 lifespan", check_lifespan_not_run),
    ("LM 跑 lifespan", check_lifespan_with_manager),
    ("并发 ≈100ms", check_concurrent),
    ("串行 ≈300ms", check_serial),
    ("query 参数", check_query_params),
    ("POST json", check_post_json),
    ("404", check_404),
    ("422", check_422),
    ("timeout 不生效", check_timeout_ignored),
    ("wait_for 超时", check_wait_for_timeout),
    ("调用累计", check_calls_accumulate),
    ("base_url", check_base_url),
    ("与 TestClient 一致", check_same_result_as_testclient),
]


async def run_async() -> int:
    failures = 0
    for name, func in CHECKS:
        try:
            result = await func()
            print(f"[PASS] {name} -> {result}")
        except Exception as exc:  # noqa: BLE001 - 验收脚本要报告任何失败
            failures += 1
            print(f"[FAIL] {name} -> {type(exc).__name__}: {exc}")
    print(f"\n结果：{len(CHECKS) - failures}/{len(CHECKS)} 通过")
    return 1 if failures else 0


def run() -> int:
    return asyncio.run(run_async())


if __name__ == "__main__":
    raise SystemExit(run())