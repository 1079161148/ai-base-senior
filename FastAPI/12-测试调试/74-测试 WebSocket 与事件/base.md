# 74 测试 WebSocket 与事件 · 完整版（base.md）

> `README.md` 给你能跑的回声与关闭码断言；本文件把「`websocket_connect` 内部怎么走、Disconnect 为什么在下一次 receive 才抛、广播怎么测、依赖覆盖如何作用于 ws」拆开。学完这章，你能给实时接口写出和 HTTP 接口一样可靠的测试。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0 / pytest 9.2.0（本机实测） |
| 前置 | 第 63 章（WebSocket 基础）、第 71 章（TestClient） |
| 覆盖范围 | `websocket_connect`、收发断言、关闭语义、广播、依赖覆盖 |
| 明确不覆盖 | 真实浏览器客户端、网络断线模拟、背压、多 worker 广播 |
| 学完验收 | 能跑通 `verify.py` 14/14 与 `pytest -q` 9 用例 |

## 0. 怎么用这份文件

**依据约定**：`` `[Xn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 测试客户端也是 ASGI 直连
2 机制（第 2 节）    → 消息流与异常抛出点
3 API（第 3 节）     → 收发与关闭
4 边界（第 4 节）    → 广播、依赖覆盖、统计、房间
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ fixture 与目录
```

## 1. 概念：和 HTTP 测试同一套通道

```text
client.websocket_connect("/ws") → ASGI scope(type=websocket)
ws.send_text("hi")              → {"type": "websocket.receive", "text": "hi"}
ws.receive_text()               → 从 send 队列取出
```

| 项 | HTTP | WebSocket |
| --- | --- | --- |
| 建立 | 请求即响应 | `accept` 后双向 |
| 断言 | `status_code`/`json()` | `receive_*` 的内容 |
| 结束 | 响应完 | `close(code, reason)` |
| 异常 | `raise_server_exceptions` | `WebSocketDisconnect` |

## 2. 机制

### 2.1 异常抛在哪一步（实测）

```text
服务端 close(4001) 后：
  客户端第一次 receive  → 正常拿到之前发的 {"bye": true}
  客户端第二次 receive  → WebSocketDisconnect(4001, "server shutdown")
```

| 场景 | 抛出位置 |
| --- | --- |
| accept 后 close | `ws.receive_*()` |
| 未 accept 就 close | `client.websocket_connect()` 的 `__enter__` |
| 服务端异常退出 | 同上或下一次 receive |

**结论**：`pytest.raises` 要包在 `receive` 外面，而不是 `send` 外面。

### 2.2 消息有序（实测）

```text
发送 0,1,2 → 收到 echo: 0, echo: 1, echo: 2
```

同一连接内是 FIFO。**跨连接不保证**。

### 2.3 统计为什么会被重置（实测）

`with TestClient(app)` 进入时会跑 lifespan，本章的 lifespan 里 `STATS.clear()`。所以：

| 位置 | `active` |
| --- | --- |
| `with` 内连接中 | `["conn-1"]` |
| `with` 退出后 | `[]`（lifespan 清理 + 端点清理）|

## 3. API 逐个拆解

| 方法 | 说明 |
| --- | --- |
| `websocket_connect(url)` | 返回上下文管理器，进入即握手 |
| `send_text(str)` | 文本帧 |
| `send_json(obj)` | 自动序列化 |
| `send_bytes(b)` | 二进制帧 |
| `receive_text()` | 阻塞直到有文本帧或断开 |
| `receive_json()` | 反序列化 |
| `receive_bytes()` | 二进制 |
| `close()` | 客户端关闭 |

### 3.1 关闭语义（实测）

| 服务端写法 | 客户端表现 |
| --- | --- |
| `await websocket.accept()` 然后 `close(4001, "server shutdown")` | 先收消息，再 `4001 / server shutdown` |
| 不 accept 直接 `close(1008, "not allowed")` | `__enter__` 抛 `1008 / not allowed` |
| 依赖返回 None 后 `close(1008, "user not found")` | `receive` 抛 `1008 / user not found` |

### 3.2 依赖（实测）

```python
@app.websocket("/ws/user/{user_id}")
async def user_socket(websocket, user_id: int, db: Annotated[dict, Depends(get_db)]):
    ...
```

覆盖 `get_db` 后：

| 请求 | 结果 |
| --- | --- |
| `/ws/user/9`（假库有） | 假用户 |
| `/ws/user/1`（假库无） | `1008` |

**依赖在 `accept` 之前解析**，所以鉴权失败可以干净地拒绝。

## 4. 边界条件

### 4.1 广播测试（实测）

```text
两条连接到 /ws/room/a
w1.send("hello") → w1 收到 "[a] hello"，w2 也收到 "[a] hello"
w2.send("from2") → w1 收到 "[a] from2"
```

| 断言点 | 说明 |
| --- | --- |
| 两条都收到 | 广播生效 |
| 内容带房间前缀 | 格式正确 |
| 不同房间隔离 | a 的广播不进 b |

### 4.2 多连接写法

```python
with client.websocket_connect("/ws/room/a") as first, \
     client.websocket_connect("/ws/room/a") as second:
    ...
```

**必须嵌套在同一个 `with` 语句里**（逗号分隔），分开写会先关掉第一个。

### 4.3 路由参数命名

```python
@app.websocket("/ws/room/{room_name}")
async def room(websocket: WebSocket, room_name: str):   # 名字必须一致
```

**实测坑**：写成 `{room}` 但函数参数叫 `room_name`，请求直接 `WebSocketDisconnect`，**没有 422 提示**。

### 4.4 无内置超时

`ws.receive_*()` 会一直阻塞。测试里若服务端不回声，用例会挂住。生产代码要加心跳/超时。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 装 `websockets` 才能测 | 不需要 | `TestClient` | 实测 |
| `raises` 包 `send_text` | 异常在 receive 抛 | 包 `receive_*` | 实测 |
| 期望 close 立即抛 | 要等下一次 receive | 先 receive | 实测 |
| 只在 `__exit__` 断 code | 拿不到 | 在 receive 处捕获 | 实测 |
| 忘 `accept` | 连不上 | 显式 accept | 实测 |
| 路由参数名与函数参数不一致 | 直接 close 无提示 | 名字对齐 | 实测 |
| 多个连接分开 `with` | 第一个已关 | 逗号嵌套 | 实测 |
| 不重置广播管理器 | 跨用例串 | fixture `reset()` | 实测 |
| 断言广播到达顺序 | 不保证 | 断内容 | 实测 |
| 依赖里 `accept` | 顺序混乱 | 端点里 accept | 第 64 章 |
| 用 `async with` | 不是异步上下文 | `with` | 实测 |
| `receive_*` 无超时 | 用例挂住 | 心跳/`wait_for` | 实测 |
| `def` 端点写 ws | 类型错误 | `async def` | 第 63 章 |
| 覆盖后不清理 | 污染后续 | `finally: clear()` | 第 73 章 |
| 统计断言跨 `with` | lifespan 重置 | 在 with 内断言 | 实测 |
| 断言 `active` 的连接名 | 顺序依赖 | 断集合/长度 | 实测 |
| 测二进制用 `receive_text` | 类型错误 | `receive_bytes` | 第 63 章 |
| 忘了服务端 `try/except` | 断开时抛到日志 | 捕获 Disconnect | 第 63 章 |
| 广播只测一条连接 | 漏发/漏订阅测不出 | 至少两条连接 | 实测 |

## 6. 最佳实践与编码建议

### 6.1 目录

```text
examples/
├── main.py
├── pyproject.toml
├── tests/
│   └── test_websocket.py
└── verify.py
```

### 6.2 fixture 模板

```python
@pytest.fixture
def client():
    main.reset()
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture
def fake_db():
    main.app.dependency_overrides[main.get_db] = lambda: {9: {"id": 9, "name": "假用户"}}
    yield
    main.app.dependency_overrides.clear()
```

### 6.3 断言矩阵

| 维度 | 至少一个 |
| --- | --- |
| 正常收发 | ✅ |
| JSON 结构 | ✅ |
| 主动关闭码 | ✅ |
| 拒绝连接 | ✅ |
| 广播 | ✅ |
| 依赖覆盖 | ✅ |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[X1]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/testing-websockets/ | WebSocket 测试 |
| `[X2]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/testing-events/ | lifespan 测试 |
| `[X3]` | 文档 | https://www.starlette.io/websockets/ | `WebSocket` 对象 |

> **核对状态**：`[X1]`–`[X3]` 为文档链接，**本次未逐页直连复核**；文本回声、消息有序、JSON 往返、关闭码 4001、拒绝 1008、广播双连接、双向广播、真实依赖、未知用户、覆盖依赖、覆盖隐藏真实、清理恢复、连接统计、房间隔离均为本机实测，`examples/verify.py` 复现 14/14 通过，`pytest -q` 9 用例全绿。真实浏览器客户端、网络断线、背压、多 worker 广播**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] `websocket_connect` 走什么通道
- [ ] `WebSocketDisconnect` 在哪一步抛
- [ ] 为什么统计会被 lifespan 重置
- [ ] 依赖在 accept 前还是后解析
- [ ] 为什么路由参数名必须一致

**能写出（代码层）**：

- [ ] 回声测试
- [ ] 关闭码断言
- [ ] 双连接广播
- [ ] 依赖覆盖
- [ ] fixture 重置

**能判断（避坑层）**：

- [ ] 看到用例挂住 → 想到无超时
- [ ] 看到 `__enter__` 抛 → 想到未 accept
- [ ] 看到广播串房 → 想到房间 key
- [ ] 看到参数名不一致 → 想到静默 close
- [ ] 看到覆盖串状态 → 想到 `clear`

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 14/14
- [ ] `uv run pytest -q` 全绿
- [ ] 故意删掉 `accept`，观察失败形态

## 9. 下一章衔接

第 75 章 `调试与可观测`：日志配置、请求 ID、`openapi` 快照、`debug=True` 的 traceback。

本章留下的伏笔：

1. ws 测试排错靠日志（74）→ 75 讲日志格式与请求 ID。
2. 覆盖后难定位（73、74）→ 75 讲「一条命令看全貌」。
3. 关闭码断言（74）→ 75 的 500 与 traceback 也是「可观测」的一部分。