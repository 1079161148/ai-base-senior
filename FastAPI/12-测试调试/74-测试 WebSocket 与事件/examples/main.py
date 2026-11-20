"""第 74 章 · 测试 WebSocket 与事件。

`TestClient.websocket_connect()` 走 ASGI 直连，不需要 `websockets` 库：

    with client.websocket_connect("/ws/echo") as ws:
        ws.send_text("hi")
        assert ws.receive_text() == "echo: hi"

【要点】服务端 `close()` 后，客户端再 `receive_*` 会抛
        `starlette.websockets.WebSocketDisconnect`，用 `.code` / `.reason` 断言。

启动：uvicorn main:app --reload
验收：python verify.py
或：  uv run pytest -q
"""

from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncIterator

from fastapi import Depends, FastAPI, WebSocket, WebSocketDisconnect

STATS: dict[str, Any] = {"active": [], "closed": 0, "messages": 0}
DB: dict[int, dict[str, Any]] = {1: {"id": 1, "name": "真实用户"}}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    STATS["active"].clear()
    STATS["closed"] = 0
    STATS["messages"] = 0
    try:
        yield
    finally:
        STATS["active"].clear()


app = FastAPI(title="第 74 章 · 测试 WebSocket 与事件", version="0.1.0", lifespan=lifespan)


def get_db() -> dict[int, dict[str, Any]]:
    """【要点】WebSocket 端点也能用普通依赖，测试里同样能覆盖"""
    return DB


def reset() -> None:
    STATS["active"].clear()
    STATS["closed"] = 0
    STATS["messages"] = 0
    DB.clear()
    DB[1] = {"id": 1, "name": "真实用户"}


# ============================================================
# 1. 回声
# ============================================================
@app.websocket("/ws/echo")
async def echo(websocket: WebSocket) -> None:
    await websocket.accept()
    name = f"conn-{len(STATS['active']) + 1}"
    STATS["active"].append(name)
    try:
        while True:
            text = await websocket.receive_text()
            STATS["messages"] += 1
            await websocket.send_text(f"echo: {text}")
    except WebSocketDisconnect:
        STATS["active"].remove(name)
        STATS["closed"] += 1


@app.websocket("/ws/json")
async def json_echo(websocket: WebSocket) -> None:
    await websocket.accept()
    try:
        while True:
            payload = await websocket.receive_json()
            await websocket.send_json({"received": payload, "type": "json"})
    except WebSocketDisconnect:
        pass


# ============================================================
# 2. 关闭语义
# ============================================================
@app.websocket("/ws/close")
async def close_after_one(websocket: WebSocket) -> None:
    """【要点】先返回一条，再主动关闭：客户端能拿到消息，然后收到 4001"""
    await websocket.accept()
    await websocket.send_json({"bye": True})
    await websocket.close(code=4001, reason="server shutdown")


@app.websocket("/ws/reject")
async def reject(websocket: WebSocket) -> None:
    """【要点】不 accept 直接 close：客户端连不上，直接抛 Disconnect"""
    await websocket.close(code=1008, reason="not allowed")


# ============================================================
# 3. 广播
# ============================================================
class Manager:
    def __init__(self) -> None:
        self.rooms: dict[str, list[WebSocket]] = {}

    async def join(self, room: str, websocket: WebSocket) -> None:
        self.rooms.setdefault(room, []).append(websocket)

    def leave(self, room: str, websocket: WebSocket) -> None:
        if websocket in self.rooms.get(room, []):
            self.rooms[room].remove(websocket)

    async def broadcast(self, room: str, message: str) -> None:
        for websocket in list(self.rooms.get(room, [])):
            await websocket.send_text(message)


manager = Manager()


@app.websocket("/ws/room/{room_name}")
async def room(websocket: WebSocket, room_name: str) -> None:
    await websocket.accept()
    await manager.join(room_name, websocket)
    try:
        while True:
            text = await websocket.receive_text()
            await manager.broadcast(room_name, f"[{room_name}] {text}")
    except WebSocketDisconnect:
        manager.leave(room_name, websocket)


# ============================================================
# 4. 依赖与 HTTP 端点
# ============================================================
@app.websocket("/ws/user/{user_id}")
async def user_socket(
    websocket: WebSocket,
    user_id: int,
    db: Annotated[dict[int, dict[str, Any]], Depends(get_db)],
) -> None:
    """【要点】依赖在 accept 之前解析；覆盖 `get_db` 后这里立刻用假库"""
    user = db.get(user_id)
    if user is None:
        await websocket.close(code=1008, reason="user not found")
        return
    await websocket.accept()
    await websocket.send_json(user)
    try:
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass


@app.get("/stats", tags=["诊断"], summary="连接统计")
def read_stats() -> dict[str, Any]:
    return {
        "active": list(STATS["active"]),
        "closed": STATS["closed"],
        "messages": STATS["messages"],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)