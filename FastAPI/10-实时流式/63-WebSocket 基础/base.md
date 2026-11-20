# 63 WebSocket 基础 · 完整版（base.md）

> `README.md` 给你能跑的回声与广播；本文件把「握手怎么升级、帧长什么样、多 worker 为什么广播失效、断连怎么清理」拆开。学完这章，你能判断一个「连不上/收到乱码/广播只有部分人收到」的问题出在哪。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0（本机实测） |
| 前置 | 第 62 章（SSE）、第 53 章（ASGI 中间件） |
| 覆盖范围 | `@app.websocket`、accept/receive/send、关闭码、广播、清理 |
| 明确不覆盖 | 帧级分片实现、压缩扩展、Redis pub/sub 落地、鉴权（64 章）|
| 学完验收 | 能跑通 `verify.py` 14/14、能写出广播 + 清理 |

## 0. 怎么用这份文件

**依据约定**：`` `[Wn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 握手升级、双向
2 机制（第 2 节）    → 帧与生命周期
3 API（第 3 节）     → 收发方法逐个
4 边界（第 4 节）    → 关闭码、多 worker、背压
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 管理器与心跳
```

## 1. 概念：从 HTTP 升级到双向通道

```text
客户端：GET /ws/echo
        Upgrade: websocket
        Connection: Upgrade
        Sec-WebSocket-Key: ...
服务端：101 Switching Protocols
        Sec-WebSocket-Accept: ...
──────── 之后同一条 TCP 双向收发帧 ────────
```

| 阶段 | 协议 | 能做什么 |
| --- | --- | --- |
| 握手前 | HTTP | 读 header/query（可鉴权）|
| 握手后 | WebSocket | 双向任意帧 |

## 2. 机制：帧与生命周期

### 2.1 帧类型

| 帧 | 用途 | FastAPI 方法 |
| --- | --- | --- |
| text | UTF-8 文本 | `send_text` / `receive_text` |
| binary | 任意字节 | `send_bytes` / `receive_bytes` |
| ping/pong | 协议层保活 | 一般由服务器自动处理 |
| close | 关闭 + 码 + 原因 | `close(code, reason)` |

### 2.2 生命周期

```text
握手 → accept() → while: receive → 处理 → send
                      ↓ 任一方 close / TCP 断
                 WebSocketDisconnect
                      ↓
                    finally: 清理
```

| 事件 | 服务端表现 |
| --- | --- |
| 客户端 `close(1000)` | `receive_*` 抛 `WebSocketDisconnect(1000)` |
| 客户端直接断 TCP | `WebSocketDisconnect(1006)` |
| 服务端 `close(code)` | 客户端抛 `WebSocketDisconnect(code)` |

实测：

| 场景 | 客户端看到 |
| --- | --- |
| `close(1000, "done")` | `1000 / done` |
| `close(4001, "server shutdown")` | `4001 / server shutdown` |
| 未 accept 直接 `close(1008)` | `1008 / not allowed` |

## 3. API 逐个拆解

| 方法 | 阻塞 | 说明 |
| --- | --- | --- |
| `accept(subprotocol=None)` | 否 | 必须先调 |
| `receive_text()` | 是 | 等下一帧 |
| `receive_json()` | 是 | 内部 `json.loads` |
| `send_text(str)` | 是 | 互斥写 |
| `send_json(obj)` | 是 | 内部序列化 |
| `close(code=1000, reason=None)` | 是 | 之后不能再收发 |

### 3.1 路由参数

```python
@app.websocket("/ws/room/{room_id}")
async def room(websocket: WebSocket, room_id: str) -> None:
    await websocket.accept()
```

规则与 HTTP 路径参数一致，但没有 `Path()` 校验（不会 422，需要自己判）。

### 3.2 读 header 与 query（握手阶段）

```python
token = websocket.query_params.get("token")
auth = websocket.headers.get("authorization")
cookie = websocket.cookies.get("session")
```

**这是 64 章鉴权的基础**：握手是 HTTP，所以 HTTP 的一切都能拿到。

### 3.3 广播与管理器（实测）

```python
manager: dict[int, WebSocket] = {}

async def broadcast(payload):
    for client_id, ws in list(manager.items()):   # 快照，避免遍历中改
        try:
            await ws.send_json(payload)
        except Exception:
            manager.pop(client_id, None)
```

实测事件序列：

```text
w1 连上          → w1 收 joined id=1
w2 连上          → w1 收 joined id=2, w2 收 joined id=2
w1 发 hello      → w1/w2 都收 message from=1
w2 断开          → w1 收 left id=2
```

## 4. 边界条件

### 4.1 关闭码

| 码 | 用途 | 能否主动发 |
| --- | --- | --- |
| 1000 | 正常 | 能 |
| 1001 | 端点离开 | 能 |
| 1008 | 策略拒绝 | 能 |
| 1011 | 服务端错误 | 能 |
| 1005 | 无状态码 | **不能** |
| 1006 | 异常断开 | **不能** |
| 4000–4999 | 应用自定义 | 能 |

### 4.2 未 accept 就关闭（实测）

```python
await websocket.close(code=1008, reason="not allowed")
```

客户端 `websocket_connect` 阶段就收到 `WebSocketDisconnect(1008)`。

**这是最省资源的拒绝方式**：握手直接失败，不建立业务连接。

### 4.3 多 worker（关键限制）

| 部署 | 内存 manager 广播 |
| --- | --- |
| `--workers 1` | 全部收到 |
| `--workers 4` | 只到同进程的那批 |

**解决方案**：Redis pub/sub / NATS 等跨进程消息总线。实测未覆盖，标注为**未实测**。

### 4.4 背压

`send_json` 是 await 的。慢客户端会让 `broadcast` 循环变慢，拖累所有人。

| 对策 | 说明 |
| --- | --- |
| 每连接独立发送队列 | 慢的不阻塞快的 |
| 丢弃旧消息 | 实时性优先 |
| 限制单消息大小 | 防内存峰值 |

### 4.5 1MB 消息（实测）

一次发 1MB 文本，往返成功（1,000,006 字符）。但生产建议应用层分片，避免单帧过大。

### 4.6 有序性（实测）

同一连接连续 100 条，顺序完全一致。**跨连接不保证**：广播的到达顺序取决于各自网络。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `def` 定义 WS 端点 | 无法 `await` | `async def` | 实测 |
| 忘 `accept()` | 收发报错 | 第一行 accept | 实测 |
| 把断开当异常 | 日志噪音 | `except WebSocketDisconnect` | 实测 |
| `finally` 不清 manager | 幽灵连接 | `disconnect(id)` | 实测 |
| 后台任务不 cancel | 断连后仍发 | `finally: task.cancel()` | 实测 |
| 遍历中删除 | `RuntimeError` | `list(...)` 快照 | 实测 |
| 多 worker 内存广播 | 只到部分用户 | Redis pub/sub | `[W3]` |
| 无应用层心跳 | 空闲被断 | 定期 ping/pong | `[W2]` |
| 断开后继续 send | `RuntimeError` | 捕获/判状态 | `[W2]` |
| 关闭码 1005/1006 | 协议错误 | 1000 或 4000+ | `[W1]` |
| 文本二进制混用一端点 | 通道错乱 | 分开或带类型 | 实测 |
| WS 里做长事务 | 连接占用 | 先查后发 | 第 57 章 |
| 大消息不分片 | 内存峰值 | 分片 + `seq` | 实测 |
| 同连接并发 send | 帧交错 | 单写者/加锁 | `[W2]` |
| 前端无 `onclose` | 不重连 | 退避重连 | `[W2]` |
| 用 WS 传大文件 | 内存全量 | 分块/HTTP | `[W2]` |
| 以为 WS 有 CORS 预检 | 握手不做预检 | 校验 `Origin` 头 | `[W1]` |
| 路径参数当校验 | 不报 422，直接拿到脏值 | 手动校验 | 实测 |
| 广播与单发并发 `send` | 帧交错、客户端收到半包 | 单一写者协程串行化 | 实测 |

## 6. 最佳实践与编码建议

### 6.1 管理器模板

```python
class Manager:
    def __init__(self) -> None:
        self.active: dict[int, WebSocket] = {}
        self.next_id = 0

    async def connect(self, ws: WebSocket) -> int:
        await ws.accept()
        self.next_id += 1
        self.active[self.next_id] = ws
        return self.next_id

    def disconnect(self, cid: int) -> None:
        self.active.pop(cid, None)

    async def broadcast(self, payload: dict) -> None:
        for cid, ws in list(self.active.items()):
            try:
                await ws.send_json(payload)
            except Exception:
                self.disconnect(cid)
```

### 6.2 心跳

| 方式 | 说明 |
| --- | --- |
| 协议层 ping/pong | 服务器自动，但应用拿不到 |
| 应用层 `{"type":"ping"}` | 可控、可观测 |
| 服务端定时 `tick` | 客户端据此判断存活 |

实测交错序列：

```text
tick1 → pong → tick2 → tick3
```

### 6.3 检查清单

| 检查项 | 原因 |
| --- | --- |
| `async def` | 必须 await |
| `accept()` 第一行 | 否则报错 |
| `try/finally` | 清理 |
| `list()` 快照 | 遍历安全 |
| 心跳间隔 20~30s | 防中间设备断 |
| 关闭码合规 | 1005/1006 不可发 |
| 多 worker 用总线 | 广播覆盖 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[W1]` | 规范 | https://www.rfc-editor.org/rfc/rfc6455 | 握手与帧、关闭码 |
| `[W2]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/websockets/ | FastAPI WebSocket |
| `[W3]` | 文档 | https://www.starlette.io/websockets/ | Starlette WebSocket |

> **核对状态**：`[W1]`–`[W3]` 为规范/文档链接，**本次未逐页直连复核**；文本/JSON/二进制往返、服务端与自定义关闭码、未 accept 拒绝、心跳交错、广播分发与离开事件、连接统计、客户端断开清理、1MB 消息、100 条有序、三连接并发均为本机实测，`examples/verify.py` 复现 14/14 通过。多 worker 广播、Redis pub/sub、背压、真实浏览器重连、CORS `Origin` 校验**未实测**（文档中标为推导/经验值）。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 握手是 HTTP，升级后是帧
- [ ] `accept()` 之前能拿到 header/query
- [ ] `WebSocketDisconnect` 是正常路径
- [ ] 1008 与 4001 的区别
- [ ] 多 worker 为什么广播失效

**能写出（代码层）**：

- [ ] 回声端点
- [ ] JSON 协议端点
- [ ] 管理器 + 广播
- [ ] 心跳
- [ ] `try/finally` 清理

**能判断（避坑层）**：

- [ ] 看到 `def` 端点 → 指出错
- [ ] 看到忘 accept → 指出错
- [ ] 看到遍历中删除 → 指出 `list()` 快照
- [ ] 看到后台任务未 cancel → 指出泄漏
- [ ] 看到多 worker 内存广播 → 指出只覆盖部分

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 14/14
- [ ] 浏览器 `new WebSocket` 连上看到回声
- [ ] 两个标签页同时连 `/ws/broadcast` 验证广播

## 9. 下一章衔接

第 64 章 `WebSocket 鉴权`：首帧鉴权、query 参数、header、cookie、超时关闭、断连清理与资源释放。

本章留下的伏笔：

1. 握手阶段能拿 HTTP 信息（63）→ 64 用它鉴权。
2. 关闭码 1008（63）→ 64 用来表达「未登录」。
3. 清理 `finally`（63）→ 64 要确保鉴权失败也清理。