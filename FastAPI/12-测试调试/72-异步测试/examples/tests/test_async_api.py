"""第 72 章 · pytest 异步写法。

跑法：uv run pytest -q（`asyncio_mode = "auto"`，`async def test_*` 自动识别）

【要点】`LifespanManager` 负责在异步上下文里手动跑 lifespan，
        否则 `/state` 永远是 `started=False`。
"""

import asyncio
import time

import pytest
import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

import main


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=main.app)
    main.STATE.update(started=False, calls=0)
    async with LifespanManager(main.app):
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            yield http


async def test_lifespan_runs(client):
    assert (await client.get("/state")).json() == {"started": True}


async def test_list_items(client):
    response = await client.get("/items")

    assert response.status_code == 200
    assert response.json() == [{"id": 1, "name": "键盘"}]


async def test_item_not_found(client):
    response = await client.get("/items/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "item not found"


async def test_echo(client):
    response = await client.post("/echo", json={"name": "鼠标"})

    assert response.status_code == 200
    assert response.json() == {"name": "鼠标"}


async def test_echo_invalid(client):
    response = await client.post("/echo", json={"name": ""})

    assert response.status_code == 422
    assert response.json()["detail"][0]["type"] == "string_too_short"


async def test_concurrent_requests_are_actually_concurrent(client):
    """【要点】3 个 100ms 请求并发应 ≈ 100ms，而不是 300ms"""
    started = time.perf_counter()
    responses = await asyncio.gather(*[client.get("/slow", params={"ms": 100}) for _ in range(3)])
    elapsed = (time.perf_counter() - started) * 1000

    assert all(response.status_code == 200 for response in responses)
    assert elapsed < 200, elapsed


async def test_timeout_needs_wait_for(client):
    """【实测坑】`AsyncClient(timeout=...)` 对 `ASGITransport` **不生效**"""
    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(client.get("/slow", params={"ms": 200}), timeout=0.05)


async def test_calls_accumulate(client):
    await client.get("/items")
    await client.get("/items")

    assert (await client.get("/calls")).json()["calls"] == 2