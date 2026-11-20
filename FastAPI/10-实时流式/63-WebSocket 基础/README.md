# 63 WebSocket 基础

## 一句话结论

WebSocket 握手用 HTTP，握手后同一条 TCP 上**双方都能随时发消息**。实测：`/ws/echo` 往返正常，1MB 文本一次发完收到 `1,000,006` 字符；服务端主动 `close(code=1000, reason="done")` 客户端拿到 `1000/done`，不 `accept` 直接 `close(1008)` 则客户端连不上；广播时两个连接都收到 `{"type":"message","from":1,"text":"hello"}`，一方断开另一方收到 `left`；断开后 `active` 归零、`total_closed` 累加。

## 最小可运行案例

```python
from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI()


@app.websocket("/ws/echo")
async def echo(websocket: WebSocket) -> None:
    await websocket.accept()          # 必须先 accept
    try:
        while True:
            text = await websocket.receive_text()
            await websocket.send_text(f"echo: {text}")
    except WebSocketDisconnect:       # 断开是正常路径，不是错误
        pass
```

客户端：

```javascript
const ws = new WebSocket("ws://127.0.0.1:8000/ws/echo");
ws.onopen = () => ws.send("hi");
ws.onmessage = (event) => console.log(event.data);
```

## 怎么跑

```powershell
cd "10-实时流式\63-WebSocket 基础\examples"
uv sync
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 文本回声 -> 两轮往返正常
[PASS] JSON 回声 -> 嵌套结构原样返回
[PASS] 二进制帧 -> 8 字节
[PASS] 服务端关闭码 -> 关闭码 1000 / done
[PASS] 心跳交错 -> tick1 → pong → tick2 → tick3
[PASS] 广播分发 -> 双方都收到 from=1
[PASS] 离开事件 -> 收到 left id=2
[PASS] 连接统计 -> active 1 → 0
[PASS] 未 accept 拒绝 -> 1008 / not allowed
[PASS] 自定义关闭码 -> 4001 / server shutdown
[PASS] 客户端断开清理 -> active=0, closed=1
[PASS] 1MB 消息 -> 1,000,006 字符
[PASS] 消息有序 -> 100 条顺序一致
[PASS] 三条并发连接 -> 3 条连接互不干扰

结果：14/14 通过
```

## 核心 API 速查

| 方法 | 方向 | 说明 |
| --- | --- | --- |
| `await ws.accept()` | 服务端 | 必须最先调用 |
| `await ws.receive_text()` | 收 | 文本帧 |
| `await ws.receive_bytes()` | 收 | 二进制帧 |
| `await ws.receive_json()` | 收 | 自动 `json.loads` |
| `await ws.send_text()` | 发 | 文本帧 |
| `await ws.send_bytes()` | 发 | 二进制帧 |
| `await ws.send_json()` | 发 | 自动序列化 |
| `await ws.close(code, reason)` | 关 | 可自定义关闭码 |

| 关闭码 | 含义 |
| --- | --- |
| 1000 | 正常关闭 |
| 1001 | 端点离开（页面关闭）|
| 1008 | 策略拒绝（鉴权失败）|
| 1011 | 服务端内部错误 |
| 4000–4999 | 应用自定义 |
| 1005/1006 | 保留，不能主动发 |

| 实测 | 值 |
| --- | --- |
| `close(1000,"done")` | 客户端 `1000/done` |
| `close(4001,"server shutdown")` | 客户端 `4001/server shutdown` |
| 未 accept 直接 `close(1008)` | 客户端 `1008/not allowed` |
| 1MB 文本 | 一次往返成功 |
| 100 条连续消息 | 顺序完全一致 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `def echo(ws)` | 同步函数无法 `await` | `async def` |
| 忘 `accept()` | 收发直接报错 | 第一行 accept |
| 把 `WebSocketDisconnect` 当 500 | 日志全是错误噪音 | `except` 后正常返回 |
| `finally` 不清 manager | 幽灵连接，广播报错 | 一定 `disconnect` |
| 后台任务不 `cancel` | 连接断了还在发 | `finally: task.cancel()` |
| 多 worker 用内存 manager | 广播只到 1/N 用户 | Redis pub/sub |
| 不设应用层心跳 | 空闲被中间设备断开 | 定期 ping/pong |
| 无限 `while True` 无 try | 断开时抛异常刷屏 | 包 `WebSocketDisconnect` |
| 断开后继续 `send` | `RuntimeError` | 捕获或先判状态 |
| 广播时遍历中删除 | `RuntimeError: dict changed` | `list(...)` 快照 |
| 把文本和二进制混在一个端点 | 通道错乱 | 分开端点或带类型字段 |
| 在 WS 里做长事务 | 连接占用 + 锁 | 先查后发 |
| 关闭码用 1005/1006 | 协议错误 | 用 1000 或 4000+ |
| 大消息不分片 | 内存峰值高 | 应用层分片 + `seq` |
| 前端不处理 `onclose` | 无重连 | 指数退避重连 |
| 用 WS 传文件 | 内存全量 | 分块或改 HTTP |
| 同一连接并发 `send` | 帧交错 | 单写者或加锁 |
| 忘记 `uvicorn` 要 `ws` 支持 | 无法升级 | `uvicorn[standard]` |

## 毕业自查

- [ ] 能写出最小回声端点
- [ ] 能解释 `accept()` 前后能做什么
- [ ] 能区分「正常断开」与「异常」
- [ ] 能实现广播与清理
- [ ] 能说清 `1008` 与 `4001` 的用途
- [ ] 动手题一：用浏览器 `WebSocket` 连 `/ws/echo` 并打印
- [ ] 动手题二：给 `/ws/broadcast` 加房间号，只广播给同房间

> 想看握手细节、帧协议、多 worker 广播、心跳与超时、背压与分片、18 条坑，继续读 [`base.md`](./base.md)。