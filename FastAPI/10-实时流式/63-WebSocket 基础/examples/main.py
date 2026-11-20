"""第 63 章 · WebSocket 基础。

核心：WebSocket 是**双向**长连接。握手用 HTTP（`Upgrade: websocket`），
      之后同一条 TCP 上双方都能随时发消息。

生命周期：
      connect → accept() → 循环 receive/send → 任一方 close → WebSocketDisconnect

【要点】WebSocket 端点必须是 `async def`；`def` 端点会用同步线程，`await` 无从谈起。

启动：uvicorn main:app --reload
验收：python verify.py
"""

import asyncio
import json
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI(title="第 63 章 · WebSocket 基础", version="0.1.0")


# ============================================================
# 连接管理器：多连接广播 + 统计
# ============================================================
class ConnectionManager:
    """【要点】必须用 **dict + id**，不能只存 WebSocket 对象：
    断连时同一个对象可能被多次移除，用 id 才能幂等
    """

    def __init__(self) -> None:
        self.active: dict[int, WebSocket] = {}
        self.next_id = 0
        self.total_connected = 0
        self.total_closed = 0

    async def connect(self, websocket: WebSocket) -> int:
        await websocket.accept()
        self.next_id += 1
        self.active[self.next_id] = websocket
        self.total_connected += 1
        return self.next_id

    def disconnect(self, client_id: int) -> bool:
        removed = self.active.pop(client_id, None) is not None
        if removed:
            self.total_closed += 1
        return removed

    async def broadcast(self, payload: dict[str, Any]) -> int:
        sent = 0
        for client_id, websocket in list(self.active.items()):
            try:
                await websocket.send_json(payload)
                sent += 1
            except Exception:  # noqa: BLE001 - 单个连接坏掉不能影响广播
                self.disconnect(client_id)
        return sent

    def reset(self) -> None:
        self.active.clear()
        self.next_id = 0
        self.total_connected = 0
        self.total_closed = 0


manager = ConnectionManager()


# ============================================================
# 1. 最小回声
# ============================================================
@app.websocket("/ws/echo")
async def echo(websocket: WebSocket) -> None:
    """【实测】`accept()` 之后才能收发；断开抛 `WebSocketDisconnect`"""
    await websocket.accept()
    try:
        while True:
            text = await websocket.receive_text()
            await websocket.send_text(f"echo: {text}")
    except WebSocketDisconnect:
        pass  # 客户端断开是正常路径，不是错误


@app.websocket("/ws/echo-once")
async def echo_once(websocket: WebSocket) -> None:
    """【作用】只收一条就关，用于观察服务端主动关闭"""
    await websocket.accept()
    text = await websocket.receive_text()
    await websocket.send_text(f"only: {text}")
    await websocket.close(code=1000, reason="done")


# ============================================================
# 2. JSON 协议
# ============================================================
@app.websocket("/ws/json")
async def json_echo(websocket: WebSocket) -> None:
    """【要点】`receive_json` / `send_json` 自动编解码，省掉手动 `json.loads`"""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            await websocket.send_json({"type": "echo", "payload": data})
    except WebSocketDisconnect:
        pass


# ============================================================
# 3. 心跳：客户端 ping → 服务端 pong，+ 服务端主动 tick
# ============================================================
@app.websocket("/ws/heartbeat")
async def heartbeat(websocket: WebSocket) -> None:
    """【要点】WebSocket 协议层有 ping/pong 帧，但应用层心跳更灵活

    【实测】服务端主动 `tick` 与客户端 `ping` 的回复会交错到达
    """
    await websocket.accept()

    async def server_ticks() -> None:
        for index in range(3):
            await asyncio.sleep(0.05)
            await websocket.send_json({"type": "tick", "n": index + 1})

    task = asyncio.create_task(server_ticks())
    try:
        while True:
            text = await websocket.receive_text()
            if text == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                await websocket.send_json({"type": "unknown", "text": text})
    except WebSocketDisconnect:
        pass
    finally:
        # 【要点】后台任务必须取消，否则连接断了它还在发
        task.cancel()


@app.websocket("/ws/bytes")
async def bytes_echo(websocket: WebSocket) -> None:
    """【实测】二进制帧与文本帧是两条独立通道，不会串"""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_bytes()
            await websocket.send_bytes(b"echo:" + data)
    except WebSocketDisconnect:
        pass


# ============================================================
# 4. 广播
# ============================================================
@app.websocket("/ws/broadcast")
async def broadcast(websocket: WebSocket) -> None:
    """【实测】一个连接发的消息，其余连接都能收到"""
    client_id = await manager.connect(websocket)
    try:
        await manager.broadcast({"type": "joined", "id": client_id})
        while True:
            text = await websocket.receive_text()
            await manager.broadcast({"type": "message", "from": client_id, "text": text})
    except WebSocketDisconnect:
        pass
    finally:
        manager.disconnect(client_id)
        await manager.broadcast({"type": "left", "id": client_id})


@app.get("/ws/stats", tags=["诊断"], summary="连接统计")
def stats() -> dict[str, int]:
    return {
        "active": len(manager.active),
        "total_connected": manager.total_connected,
        "total_closed": manager.total_closed,
    }


@app.delete("/ws/stats", tags=["诊断"], summary="重置统计")
def reset_stats() -> dict[str, int]:
    manager.reset()
    return {"reset": 1}


# ============================================================
# 5. 未鉴权就拒绝：先 close 不 accept
# ============================================================
@app.websocket("/ws/reject")
async def reject(websocket: WebSocket) -> None:
    """【实测】不 `accept` 直接 `close(1008)`，客户端收到 `WebSocketDisconnect(1008)`"""
    await websocket.close(code=1008, reason="not allowed")


@app.websocket("/ws/server-close")
async def server_close(websocket: WebSocket) -> None:
    """【实测】accept 后立刻 close(4001)，客户端能拿到自定义关闭码"""
    await websocket.accept()
    await websocket.send_text("bye")
    await websocket.close(code=4001, reason="server shutdown")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)