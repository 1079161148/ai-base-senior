# 72 异步测试

## 一句话结论

同步的 `TestClient` 内部已经起 portal 线程跑事件循环，所以**异步端点用 `TestClient` 也能测**。只有当测试本身需要 `await`（并发断言、异步 fixture、异步数据库）时才换 `httpx.AsyncClient` + `ASGITransport`。实测：`ASGITransport` 不开端口（URL 是 `http://test/items`）；不套 `LifespanManager` 时 lifespan **不执行**（`started=False`）；3 个 100ms 请求 `asyncio.gather` 并发 **118ms**，串行 **325ms**。最大的坑：**`AsyncClient(timeout=...)` 对 `ASGITransport` 完全不生效**（设 0.02 仍等了 215ms），要测超时只能 `asyncio.wait_for`。

## 最小可运行案例

```python
# tests/test_async_api.py
import asyncio

import pytest_asyncio
from asgi_lifespan import LifespanManager
from httpx import ASGITransport, AsyncClient

import main


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=main.app)
    async with LifespanManager(main.app):          # 手动跑 lifespan
        async with AsyncClient(transport=transport, base_url="http://test") as http:
            yield http


async def test_list(client):
    response = await client.get("/items")
    assert response.status_code == 200


async def test_concurrent(client):
    started = asyncio.get_event_loop().time()
    await asyncio.gather(*[client.get("/slow", params={"ms": 100}) for _ in range(3)])
    assert asyncio.get_event_loop().time() - started < 0.2
```

`pyproject.toml`：

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

## 怎么跑

```powershell
cd "12-测试调试\72-异步测试\examples"
uv sync
uv run python verify.py
uv run pytest -q
```

预期输出：

```text
[PASS] 列表 200 -> 200 / 1 条
[PASS] 无 LM 不跑 lifespan -> started=False
[PASS] LM 跑 lifespan -> started=True
[PASS] 并发 ≈100ms -> 118ms（串行应 300ms）
[PASS] 串行 ≈300ms -> 325ms
[PASS] query 参数 -> ms=1
[PASS] POST json -> echo 一致
[PASS] 404 -> 404 / item not found
[PASS] 422 -> 422 string_too_short
[PASS] timeout 不生效 -> timeout=0.02 仍等了 215ms
[PASS] wait_for 超时 -> asyncio.TimeoutError
[PASS] 调用累计 -> calls=2
[PASS] base_url -> http://test/items
[PASS] 与 TestClient 一致 -> 完全一致

结果：14/14 通过
```

`pytest -q` 另外 8 个用例全绿，无 warning。

## 核心 API 速查

| 组件 | 作用 |
| --- | --- |
| `httpx.AsyncClient` | 异步 HTTP 客户端 |
| `ASGITransport(app)` | 把请求直接交给 ASGI app，不开端口 |
| `base_url="http://test"` | 必填，否则拼不出绝对 URL |
| `LifespanManager(app)` | 在异步上下文里跑 lifespan |
| `asyncio.gather` | 并发发多个请求 |
| `asyncio.wait_for` | 唯一可靠的超时手段 |
| `pytest_asyncio.fixture` | 异步 fixture |
| `asyncio_mode = "auto"` | 不用逐个写 `@pytest.mark.asyncio` |

| 实测 | 值 |
| --- | --- |
| `ASGITransport` URL | `http://test/items` |
| 无 `LifespanManager` | `started=False` |
| 有 `LifespanManager` | `started=True` |
| 3×100ms 并发 | 118ms |
| 3×100ms 串行 | 325ms |
| `timeout=0.02` 对 200ms | 仍返回 200，215ms |
| `wait_for(0.05)` 对 200ms | `asyncio.TimeoutError` |
| 与 `TestClient` 结果 | 完全一致 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 以为 `AsyncClient` 更快 | 同一事件循环，没区别 | 按需选 |
| 忘了 `base_url` | `httpx` 报错 | `base_url="http://test"` |
| 忘了 `LifespanManager` | 资源是 None、lifespan 没跑 | 显式包住 |
| 用 `AsyncClient(timeout=)` 测超时 | **不生效** | `asyncio.wait_for` |
| 同步 `time.sleep` 测异步端点 | 阻塞整个循环 | `await asyncio.sleep` |
| 在 `async def test` 里用 `TestClient` | 能跑但阻塞 loop | 换 `AsyncClient` |
| 不开 `asyncio_mode` | 每个用例都要装饰器 | `auto` |
| 异步 fixture 用 `@pytest.fixture` | 旧版报错 | `pytest_asyncio.fixture` |
| 不设 `default_fixture_loop_scope` | DeprecationWarning | 显式 `"function"` |
| `gather` 里混入同步调用 | 串行执行 | 全异步 |
| 断言耗时太紧 | CI 抖动 | 留 2 倍余量 |
| 共享一个 client 跨用例 | 状态串 | fixture 作用域 `function` |
| 在 `gather` 里不处理异常 | 其余请求被取消 | `return_exceptions=True` |
| 忘了 `await` | 拿到 coroutine 对象 | 检查类型 |
| 用 `asyncio.run` 嵌套 | 循环冲突 | pytest-asyncio 管 |
| 异步生成器依赖没清理 | 泄漏 | `finally` 处理 |
| 并发写同一文件 | 竞争 | 加锁或串行 |
| 断言顺序 | 并发结果顺序不保证 | 按集合断言 |

## 毕业自查

- [ ] 能写异步 fixture + `AsyncClient`
- [ ] 能解释为什么需要 `LifespanManager`
- [ ] 能用 `gather` 证明并发
- [ ] 知道 `timeout` 不生效、要用 `wait_for`
- [ ] 知道什么时候不需要 `AsyncClient`
- [ ] 动手题一：用 `gather` 发 10 个请求，断言总耗时 < 2 倍单请求
- [ ] 动手题二：把 `timeout` 坑写成注释

> 想看 `ASGITransport` 内部、portal 线程、anyio backend、pytest-asyncio 的事件循环策略、18 条坑，继续读 [`base.md`](./base.md)。