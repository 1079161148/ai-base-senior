# 72 异步测试 · 完整版（base.md）

> `README.md` 给你能跑的异步 fixture 与并发断言；本文件把「TestClient 与 AsyncClient 到底差在哪、lifespan 谁负责、超时为什么测不出来、pytest-asyncio 的事件循环怎么管」拆开。学完这章，你能判断一个「异步测试卡住 / 超时测不到 / fixture 报错」的问题出在哪。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0 / pytest 9.2.0 / pytest-asyncio 1.5.0（本机实测） |
| 前置 | 第 71 章（TestClient）、第 67 章（lifespan）、第 59 章（线程池） |
| 覆盖范围 | `AsyncClient`、`ASGITransport`、`LifespanManager`、并发断言、超时 |
| 明确不覆盖 | anyio 的 trio backend、异步数据库驱动测试、真实 IO 压测 |
| 学完验收 | 能跑通 `verify.py` 14/14 与 `pytest -q` 8 用例 |

## 0. 怎么用这份文件

**依据约定**：`` `[Vn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 两种客户端的差别
2 机制（第 2 节）    → 事件循环与 portal
3 API（第 3 节）     → AsyncClient 与 fixture
4 边界（第 4 节）    → lifespan、超时、并发、状态
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 目录与配置模板
```

## 1. 概念：同一条 ASGI 通道，两种驱动方式

```text
TestClient      → httpx.Client + 内部 portal 线程跑事件循环（同步 API）
AsyncClient     → httpx.AsyncClient + 直接 await（异步 API）
两者都走 ASGITransport，都不开端口
```

| 维度 | `TestClient` | `AsyncClient` |
| --- | --- | --- |
| 调用风格 | 同步 | `await` |
| 事件循环 | 内部新建（portal 线程）| 当前循环 |
| 能测并发吗 | 不能（同一线程串行）| 能 |
| 能测 `await` 时序吗 | 不能 | 能 |
| lifespan | `with` 自动 | 要 `LifespanManager` |
| 推荐场景 | 绝大多数接口测试 | 并发/异步依赖 |

## 2. 机制

### 2.1 `ASGITransport`（实测）

```text
str(response.request.url) == "http://test/items"
```

不开端口、不解析 DNS，`base_url` 只是个占位前缀。**没传 `base_url` 会直接报错**。

### 2.2 lifespan 责任转移（实测）

| 写法 | `/state` |
| --- | --- |
| `AsyncClient` 直接请求 | `started=False` |
| 套 `LifespanManager(app)` | `started=True` |

`TestClient` 的 `with` 会帮你跑，`AsyncClient` 不会。这是从 71 章迁移过来最容易漏的一步。

### 2.3 并发是否真并发（实测）

| 模式 | 3×100ms 总耗时 |
| --- | --- |
| `asyncio.gather` | **118ms** |
| 逐个 `await` | **325ms** |

差值约 3 倍，是「事件循环真的在并发」的直接证据。

### 2.4 超时测不出来（实测坑）

```python
AsyncClient(transport=ASGITransport(app), timeout=0.02).get("/slow?ms=200")
# → 200，耗时 215ms
```

| 手段 | 结果 |
| --- | --- |
| `AsyncClient(timeout=0.02)` | **不生效** |
| `asyncio.wait_for(coro, timeout=0.05)` | `asyncio.TimeoutError` |

**原因**：httpx 的 timeout 作用在真实传输层（socket 读写），`ASGITransport` 是纯内存调用，没有 socket 可超时。

## 3. API 逐个拆解

```python
transport = ASGITransport(app=app)
async with AsyncClient(transport=transport, base_url="http://test") as client:
    response = await client.get("/items", params={"limit": 10})
```

| 参数 | 说明 |
| --- | --- |
| `transport` | 必填，`ASGITransport(app=...)` |
| `base_url` | 必填（实测不传报错）|
| `timeout` | 对 ASGI 传输**无效** |
| `headers` / `cookies` | 与 httpx 一致 |

### 3.1 pytest 配置

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

| 配项 | 作用 |
| --- | --- |
| `asyncio_mode = "auto"` | `async def test_*` 自动跑 |
| `asyncio_default_fixture_loop_scope` | 不设会 `DeprecationWarning`（实测）|

### 3.2 异步 fixture

```python
@pytest_asyncio.fixture
async def client():
    async with LifespanManager(main.app):
        async with AsyncClient(...) as http:
            yield http
```

| 写法 | 兼容性 |
| --- | --- |
| `@pytest_asyncio.fixture` | 各版本都行 |
| `@pytest.fixture` + `auto` 模式 | 新版可行，旧版报错 |

## 4. 边界条件

### 4.1 状态隔离

`ASGITransport` 不隔离模块级全局变量。实测 `calls` 在同一 client 内累计到 2。fixture 里必须重置。

### 4.2 并发异常

```python
results = await asyncio.gather(*calls, return_exceptions=True)
```

默认任一协程抛异常会取消其余。需要全部结果时用 `return_exceptions=True`。

### 4.3 断言顺序

并发结果的**完成顺序不保证**，只保证 `gather` 返回顺序与传入顺序一致。断言集合而不是顺序。

### 4.4 什么时候不用 `AsyncClient`

| 场景 | 用哪个 |
| --- | --- |
| 普通 CRUD 断言 | `TestClient` 就够 |
| 并发/时序 | `AsyncClient` |
| 异步 fixture 里 | `AsyncClient` |
| 异步依赖副作用 | `AsyncClient` |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 以为 `AsyncClient` 更快 | 无差别 | 按需选 | 实测 |
| 忘 `base_url` | 直接报错 | 必填 | 实测 |
| 忘 `LifespanManager` | lifespan 不跑（实测）| 显式包住 | 实测 |
| `timeout=` 测超时 | 不生效（实测）| `wait_for` | 实测 |
| `time.sleep` 在异步里 | 阻塞循环 | `await asyncio.sleep` | 第 59 章 |
| `async def` 里用 `TestClient` | 阻塞 loop | `AsyncClient` | 实测 |
| 不开 `asyncio_mode` | 每个用例写装饰器 | `auto` | `[V2]` |
| 异步 fixture 用 `pytest.fixture` | 旧版报错 | `pytest_asyncio.fixture` | `[V2]` |
| 不设 `default_fixture_loop_scope` | DeprecationWarning | 显式配置 | 实测 |
| `gather` 混同步调用 | 串行 | 全异步 | 实测 |
| 断言耗时太紧 | CI 抖动 | 留余量 | 实测 |
| 跨用例共享 client | 状态串 | `function` 作用域 | 实测 |
| `gather` 不处理异常 | 其余被取消 | `return_exceptions` | 实测 |
| 忘 `await` | 拿到 coroutine | 检查类型 | 实测 |
| `asyncio.run` 嵌套 | 循环冲突 | 交给 pytest | `[V2]` |
| 断言返回顺序 | 并发不保证 | 断集合 | 实测 |
| 异步生成器依赖不清理 | 泄漏 | `finally` | 第 67 章 |
| 并发写同一资源 | 竞争 | 加锁/串行 | 实测 |
| 异步用例里 `print` 调试 | 输出被捕获看不到 | `pytest -s` | 实测 |

## 6. 最佳实践与编码建议

### 6.1 目录

```text
examples/
├── main.py
├── pyproject.toml       # asyncio_mode / testpaths / pythonpath
├── tests/
│   └── test_async_api.py
└── verify.py            # asyncio.run 驱动的自检
```

### 6.2 fixture 模板

```python
@pytest_asyncio.fixture
async def client():
    reset_state()
    async with LifespanManager(main.app):
        async with AsyncClient(
            transport=ASGITransport(app=main.app), base_url="http://test"
        ) as http:
            yield http
```

### 6.3 选型决策

| 问题 | 答案 |
| --- | --- |
| 只是断言接口？ | `TestClient` |
| 要 `await`？ | `AsyncClient` |
| 要证明并发？ | `AsyncClient` + `gather` |
| 要测超时？ | `wait_for` |

### 6.4 检查清单

| 检查项 | 原因 |
| --- | --- |
| `base_url` | 必需 |
| `LifespanManager` | lifespan |
| `function` 作用域 fixture | 隔离 |
| `wait_for` 测超时 | 唯一可靠 |
| 耗时断言留余量 | 抗抖动 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[V1]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/async-tests/ | `AsyncClient` 测试 |
| `[V2]` | 文档 | https://pytest-asyncio.readthedocs.io/ | `asyncio_mode` 与 fixture |
| `[V3]` | 文档 | https://www.python-httpx.org/async/ | httpx 超时语义 |

> **核对状态**：`[V1]`–`[V3]` 为文档链接，**本次未逐页直连复核**；列表、lifespan 两种、并发 118ms、串行 325ms、query、POST、404、422、`timeout` 不生效、`wait_for` 超时、调用累计、`base_url`、与 `TestClient` 一致均为本机实测，`examples/verify.py` 复现 14/14 通过，`pytest -q` 8 用例全绿。anyio trio backend、异步数据库驱动、`return_exceptions` 行为、真实网络超时**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 两种客户端的差别
- [ ] 为什么 `ASGITransport` 不用端口
- [ ] 为什么 lifespan 要手动管
- [ ] 为什么 `timeout` 不生效
- [ ] 什么时候不需要 `AsyncClient`

**能写出（代码层）**：

- [ ] 异步 fixture
- [ ] `LifespanManager` 包裹
- [ ] `gather` 并发断言
- [ ] `wait_for` 超时
- [ ] `pyproject` 的 asyncio 配置

**能判断（避坑层）**：

- [ ] 看到 `started=False` → 想到 `LifespanManager`
- [ ] 看到超时测不到 → 想到 `ASGITransport`
- [ ] 看到 fixture 警告 → 想到 loop scope
- [ ] 看到状态串 → 想到 fixture 作用域
- [ ] 看到 `gather` 被取消 → 想到 `return_exceptions`

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 14/14
- [ ] `uv run pytest -q` 无 warning
- [ ] 把 `gather` 改成 `for` 循环，观察耗时变成 3 倍

## 9. 下一章衔接

第 73 章 `依赖覆盖与测试库`：`app.dependency_overrides`、假数据库、覆盖嵌套依赖、fixture 清理。

本章留下的伏笔：

1. 异步 fixture（72）→ 73 用它挂「每个用例一个干净假库」。
2. `LifespanManager`（72）→ 73 的假库初始化可以放这里。
3. 状态隔离（72）→ 73 用依赖覆盖彻底解决。