# 71 TestClient 基础 · 完整版（base.md）

> `README.md` 给你能跑的 fixture 与三层断言；本文件把「TestClient 为什么不走网络、lifespan 在什么时机跑、422 该断言什么、fixture 怎么组织」拆开。学完这章，你能给一个 FastAPI 服务写出既不脆弱又覆盖充分的接口测试。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0 / pytest 9.2.0（本机实测） |
| 前置 | 第 05 章（响应）、第 09 章（错误处理）、第 67 章（lifespan） |
| 覆盖范围 | `TestClient`、断言三层、fixture、重定向、cookie、异常模式 |
| 明确不覆盖 | 异步测试（72 章）、依赖覆盖（73 章）、端到端浏览器测试 |
| 学完验收 | 能跑通 `verify.py` 16/16 与 `pytest -q` 全绿 |

## 0. 怎么用这份文件

**依据约定**：`` `[Un]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 为什么快、为什么稳
2 机制（第 2 节）    → portal 线程与 lifespan 时机
3 API（第 3 节）     → 请求构造与响应断言
4 边界（第 4 节）    → 异常、重定向、cookie、状态隔离
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 目录与 fixture 模板
```

## 1. 概念：直连 ASGI，不走 TCP

```text
TestClient.get("/items")
  → httpx.Client(transport=ASGITransport(app))
  → 直接把请求 dict 交给 app(scope, receive, send)
  → 收集响应消息拼成 httpx.Response
```

| 对比 | TestClient | 真起 uvicorn |
| --- | --- | --- |
| 网络 | 无 | 有 |
| 端口 | 不需要 | 需要 |
| 速度 | 快 | 慢 |
| 能否测超时/断连 | 部分 | 完整 |

## 2. 机制

### 2.1 portal 线程与 lifespan（实测）

| 用法 | lifespan |
| --- | --- |
| `TestClient(app)` 不 `with`、发请求 | **不执行**（`started=False`）|
| `with TestClient(app)` | 进入执行 startup，退出执行 shutdown |

实测：

```text
不用 with → {"started": false}
用 with   → {"started": true}
```

**结论**：凡是有 lifespan 的应用，测试一律 `with`。

### 2.2 断言的三层

| 层 | 断言 | 实测 |
| --- | --- | --- |
| 成功 | `status_code` + 关键字段 | `201` + `{"id":2,"name":"鼠标","price":9900}` |
| 不存在 | `404` + `detail` | `item not found` |
| 非法 | `422` + `type` + `loc` | `string_too_short` / `greater_than_equal` |

### 2.3 422 的结构

```json
[
  {"type": "string_too_short", "loc": ["body", "name"], "msg": "...", "input": ""},
  {"type": "greater_than_equal", "loc": ["body", "price"], "msg": "...", "input": -1}
]
```

| 字段 | 是否适合断言 |
| --- | --- |
| `type` | ✅ 稳定 |
| `loc` | ✅ 稳定 |
| `msg` | ❌ 随 pydantic 版本变 |
| `ctx` | ⚠️ 结构可能变 |

## 3. API 逐个拆解

| 参数 | 作用 |
| --- | --- |
| `app` | 要测的 ASGI 应用 |
| `base_url` | 默认 `http://testserver` |
| `raise_server_exceptions` | 默认 `True` |
| `follow_redirects` | 默认 `True`（实测 307 → 200）|
| `cookies` | 初始 cookie |

| 请求方法 | 常用参数 |
| --- | --- |
| `get` | `params` |
| `post` | `json` / `data` / `files` / `content` |
| `put` / `patch` / `delete` | 同上 |
| `request` | 任意方法 |

### 3.1 响应对象

| 属性 | 用途 |
| --- | --- |
| `status_code` | 断言 |
| `json()` | 解析 body |
| `text` | 原始文本 |
| `headers` | 大小写不敏感 |
| `cookies` | 响应 cookie |
| `request` | 反查方法/URL（实测 `GET http://testserver/items/1`）|

### 3.2 重定向（实测）

```python
client.get("/redirect")                        # 200, url.path == "/items"
TestClient(app, follow_redirects=False).get()  # 307, location == "/items"
```

## 4. 边界条件

### 4.1 服务端异常（实测）

| 模式 | 结果 |
| --- | --- |
| 默认（严格）| `pytest.raises(RuntimeError)` |
| `raise_server_exceptions=False` | `500 Internal Server Error` |

**为什么默认严格**：否则一个 500 的接口在「只断言 `status_code < 500` 写错」时会被误判通过。

### 4.2 状态隔离

`TestClient` 之间不共享 `app.state`，但**会共享模块级全局变量**（如 `ITEMS` dict）。实测 fixture 里必须手动重置：

```python
main.ITEMS.clear()
main.ITEMS[1] = {...}
main.STATE.update(next_id=2, started=False)
```

### 4.3 cookie

| 场景 | 行为 |
| --- | --- |
| 同一 client | 自动携带（实测 `session=abc123`）|
| 不同 client | 不共享 |
| 手动设置 | `client.cookies.set("k", "v")` |

### 4.4 文件上传

```python
client.post("/upload", files={"file": ("a.txt", b"hello", "text/plain")})
```

实测未覆盖，标注为**文档约定**。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 只测 200 | 错误路径裸奔 | 补 404/422 | 实测 |
| 断言 `msg` 全文 | 升级就红 | 断 `type`+`loc` | 实测 |
| 断言整个错误体 | 多字段就红 | 取所需键 | 实测 |
| 不用 `with` | lifespan 不跑（实测）| `with TestClient` | 实测 |
| 共享全局数据 | 顺序依赖 | fixture 重置 | 实测 |
| 关掉 `raise_server_exceptions` 当默认 | 500 也算过 | 保持严格 | 实测 |
| URL 手拼 query | 特殊字符未转义 | `params=` | 实测 |
| 对真实服务测试 | 慢、不稳 | `TestClient` | 实测 |
| 断言时间戳/随机值 | 抖动 | 断形状/类型 | 实测 |
| 一用例测十接口 | 难定位 | 一接口一用例 | 实测 |
| 缺 `pythonpath` | `ModuleNotFoundError` | `pyproject` 配置 | 实测 |
| 测试不还原全局 | 污染后续 | `yield` 后清理 | 实测 |
| 两处 pytest 配置 | 打架 | 只留一处 | `[U2]` |
| 精确断 `content-type` 带 charset | 版本差异 | 先实测再断 | 实测 |
| 断言日志文本 | 脆弱 | `caplog` | `[U2]` |
| 依赖真实数据库 | 慢 | 覆盖依赖 | 第 73 章 |
| 只跑一次不看覆盖率 | 盲区 | 覆盖率报告 | `[U3]` |
| 用 `print` 调试测试 | 噪音 | `-s` / `caplog` | `[U2]` |
| 用 `response.text` 断言中文 | 编码差异导致误判 | 用 `response.json()` | 实测 |

## 6. 最佳实践与编码建议

### 6.1 目录

```text
examples/
├── main.py
├── pyproject.toml        # [tool.pytest.ini_options]
├── tests/
│   └── test_api.py
└── verify.py             # 不依赖 pytest 的自检
```

### 6.2 fixture 模板

```python
@pytest.fixture
def client():
    reset_state()
    with TestClient(main.app) as test_client:
        yield test_client
```

### 6.3 命名

| 前缀 | 含义 |
| --- | --- |
| `test_create_*` | 成功路径 |
| `test_*_not_found` | 404 |
| `test_*_invalid_*` | 422 |

### 6.4 检查清单

| 检查项 | 原因 |
| --- | --- |
| `with TestClient` | lifespan |
| 三层断言齐 | 覆盖 |
| 断 `type`/`loc` | 稳定 |
| fixture 重置 | 隔离 |
| 参数化边界 | 省代码 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[U1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/testing/ | `TestClient` |
| `[U2]` | 文档 | https://docs.pytest.org/en/stable/ | pytest |
| `[U3]` | 文档 | https://coverage.readthedocs.io/ | 覆盖率 |

> **核对状态**：`[U1]`–`[U3]` 为文档链接，**本次未逐页直连复核**；201 body、列表、详情、404 detail、422 两类错误 type/loc、query 范围与类型、content-type、重定向两种模式、cookie 保持、lifespan 两种时机、严格/宽松异常、`response.request` 均为本机实测，`examples/verify.py` 复现 16/16 通过，`pytest -q` 14 个用例全绿。文件上传、`caplog`、覆盖率、并发测试**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] TestClient 为什么不走网络
- [ ] lifespan 什么时候执行
- [ ] 422 该断言哪两个字段
- [ ] `raise_server_exceptions` 的意义
- [ ] 全局状态为什么会串

**能写出（代码层）**：

- [ ] fixture + `with TestClient`
- [ ] 三层断言
- [ ] 参数化
- [ ] 重定向两种写法
- [ ] cookie 设置与读取

**能判断（避坑层）**：

- [ ] 看到断 `msg` → 指出脆弱
- [ ] 看到不用 `with` → 指出 lifespan
- [ ] 看到 500 通过 → 指出严格模式
- [ ] 看到顺序依赖 → 指出 fixture 重置
- [ ] 看到手拼 query → 指出 `params`

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 16/16
- [ ] `uv run pytest -q` 输出 14 passed
- [ ] 故意改坏一个端点，两种跑法都红

## 9. 下一章衔接

第 72 章 `异步测试`：`httpx.AsyncClient` + `ASGITransport`、`pytest-asyncio`、异步 fixture、并发请求断言。

本章留下的伏笔：

1. `TestClient` 是同步的（71）→ 72 讲为什么异步端点也能用它、什么时候必须换 `AsyncClient`。
2. lifespan 时机（71）→ 72 的异步测试里要 `LifespanManager`。
3. fixture（71）→ 72 的异步 fixture 写法不同。