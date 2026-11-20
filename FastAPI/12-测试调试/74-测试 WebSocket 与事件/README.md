# 74 测试 WebSocket 与事件

## 一句话结论

`TestClient.websocket_connect()` 走 ASGI 直连，**不需要 `websockets` 库**。实测：文本/JSON 往返正常；消息严格有序（`0 → 1 → 2`）；服务端 `close(4001, "server shutdown")` 后客户端 `receive_*` 抛 `WebSocketDisconnect`，`.code`/`.reason` 可直接断言；不 `accept` 直接 `close(1008)` → 连接建立就失败；广播对同房间两条连接都生效；**WebSocket 端点同样能用 `Depends`，`dependency_overrides` 一样生效**（覆盖 `get_db` 后假用户出现、真实 id 变 `1008`）。

## 最小可运行案例

```python
# main.py
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()


@app.websocket("/ws/echo")
async def echo(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            text = await websocket.receive_text()
            await websocket.send_text(f"echo: {text}")
    except WebSocketDisconnect:
        pass


@app.websocket("/ws/close")
async def close_now(websocket: WebSocket) -> None:
    await websocket.accept()
    await websocket.send_json({"bye": True})
    await websocket.close(code=4001, reason="server shutdown")
```

```python
# tests/test_websocket.py
import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import main


@pytest.fixture
def client():
    with TestClient(main.app) as test_client:
        yield test_client


def test_echo(client):
    with client.websocket_connect("/ws/echo") as ws:
        ws.send_text("hi")
        assert ws.receive_text() == "echo: hi"


def test_close_code(client):
    with client.websocket_connect("/ws/close") as ws:
        assert ws.receive_json() == {"bye": True}
        with pytest.raises(WebSocketDisconnect) as excinfo:
            ws.receive_json()

    assert excinfo.value.code == 4001
    assert excinfo.value.reason == "server shutdown"
```

## 怎么跑

```powershell
cd "12-测试调试\74-测试 WebSocket 与事件\examples"
uv sync
uv run python verify.py
uv run pytest -q
```

预期输出：

```text
[PASS] 文本回声 -> echo: hi
[PASS] 消息有序 -> 0 → 1 → 2
[PASS] JSON 往返 -> 结构原样返回
[PASS] 服务端关闭码 -> 4001 / server shutdown
[PASS] 拒绝连接 -> 1008 / not allowed
[PASS] 广播 -> 两条连接都收到
[PASS] 双向广播 -> 双向广播
[PASS] 真实依赖 -> 真实用户
[PASS] 未知用户 -> 1008 / user not found
[PASS] 覆盖依赖 -> 假用户
[PASS] 覆盖隐藏真实 -> 真实 id 1 → 1008
[PASS] 清理后恢复 -> 恢复真实用户
[PASS] 连接统计 -> active 1 → 0，closed=1
[PASS] 房间隔离 -> a / b 隔离

结果：14/14 通过
```

`pytest -q` 另外 9 个用例全绿。

## 核心 API 速查

| 写法 | 作用 |
| --- | --- |
| `with client.websocket_connect("/ws") as ws:` | 建立连接 |
| `ws.send_text/ send_json/ send_bytes` | 发送 |
| `ws.receive_text/ receive_json/ receive_bytes` | 接收（阻塞）|
| `ws.close()` | 客户端关闭 |
| `WebSocketDisconnect.code / .reason` | 断言关闭语义 |
| `WebSocketDisconnect` 在 `__enter__` 抛出 | 服务端未 accept 就 close |

| 实测 | 值 |
| --- | --- |
| 文本回声 | `echo: hi` |
| 3 条消息 | `echo: 0/1/2` 严格有序 |
| JSON | `{"received": {...}, "type": "json"}` |
| 服务端 close | `4001 / server shutdown` |
| 未 accept 直接 close | `1008 / not allowed` |
| 广播 | 两条连接都收到 `[a] hello` |
| 覆盖 `get_db` | `/ws/user/9` → 假用户 |
| 覆盖后真实 id | `1008` |
| 断开统计 | `active` 1 → 0，`closed=1` |
| 房间隔离 | a / b 互不串 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 装 `websockets` 才能测 | 不需要 | `TestClient` 够 |
| 用 `pytest.raises` 包 `send_text` | 异常在 `receive` 时抛 | 包 `receive_*` |
| 期望 `close` 立即抛 | 要等下一次 `receive` | 先 receive 再断言 |
| 只在 `__exit__` 断言 code | 拿不到异常 | 在 `receive` 处捕获 |
| 忘记 `accept` | 客户端连不上 | 显式 `accept` |
| 路由参数名与函数参数不一致 | 直接 close，无报错 | 名字对齐 |
| 多个连接串行 `with` | 第二个连接时第一个已关 | 嵌套 `with` |
| 不重置广播管理器 | 跨用例串 | fixture 里 `reset()` |
| 断言广播顺序 | 不保证 | 断内容 |
| 依赖里做 `accept` | 顺序混乱 | 端点里 `accept` |
| 用 `async with` | 不是异步上下文 | `with` |
| 断言 `receive_*` 超时 | 无内置超时 | 加保护或改设计 |
| 在 `def` 端点里写 ws | 类型错误 | `async def` |
| 忘了覆盖后的清理 | 污染后续 | `finally: clear()` |

## 毕业自查

- [ ] 能连上、发、收、断言
- [ ] 能断言关闭码与原因
- [ ] 能测两条连接广播
- [ ] 能对 WebSocket 端点做依赖覆盖
- [ ] 知道异常在哪一步抛
- [ ] 动手题一：加一个「鉴权失败 close(1008)」的 ws 并测试
- [ ] 动手题二：测 10 条消息的顺序

> 想看 `websocket_connect` 的内部消息流、`WebSocketDisconnect` 的抛出时机、并发连接、广播管理器设计、18 条坑，继续读 [`base.md`](./base.md)。