"""第 64 章 · WebSocket 鉴权。

核心：WebSocket 握手是 HTTP，所以三种鉴权位置都能用：

      1. query  `?token=...`        握手前可判，但会进日志
      2. header `Authorization: ...` 握手前可判，浏览器 `WebSocket` 不能自定义头
      3. cookie                      握手前可判，浏览器自动带
      4. 首帧    `{"type":"auth"}`   握手后判，最灵活，但要设超时防挂

【要点】鉴权失败用 `close(1008)`；**能不 accept 就不 accept**，省一个业务连接。

启动：uvicorn main:app --reload
验收：python verify.py
"""

import asyncio
from typing import Any

from fastapi import FastAPI, WebSocket, WebSocketDisconnect

app = FastAPI(title="第 64 章 · WebSocket 鉴权", version="0.1.0")

# 【作用】演示用明文 token；生产用 JWT/会话，且从环境变量读
VALID_TOKEN = "secret-token"

ACTIVE: dict[str, WebSocket] = {}
STATS = {"connected": 0, "closed": 0, "rejected": 0}


def reset_stats() -> None:
    ACTIVE.clear()
    STATS.update({"connected": 0, "closed": 0, "rejected": 0})


def token_from_header(value: str | None) -> str | None:
    if not value:
        return None
    if value.lower().startswith("bearer "):
        return value[7:].strip()
    return value.strip()


async def reject(websocket: WebSocket, reason: str) -> None:
    """【要点】握手阶段直接拒绝：不发 101，不发业务数据"""
    STATS["rejected"] += 1
    await websocket.close(code=1008, reason=reason)


async def serve(websocket: WebSocket, user: str) -> None:
    """【作用】鉴权通过后的公共业务循环"""
    await websocket.accept()
    STATS["connected"] += 1
    ACTIVE[user] = websocket
    try:
        await websocket.send_json({"type": "ready", "user": user})
        while True:
            message = await websocket.receive_json()
            await websocket.send_json({"type": "echo", "payload": message})
    except WebSocketDisconnect:
        pass
    finally:
        # 【要点】无论正常断开还是异常，都要移除，否则 ACTIVE 里留幽灵
        ACTIVE.pop(user, None)
        STATS["closed"] += 1


# ============================================================
# 1. query 参数鉴权
# ============================================================
@app.websocket("/ws/auth/query")
async def auth_query(websocket: WebSocket) -> None:
    """【实测】`?token=secret-token` 通过；缺失/错误 → 客户端收到 1008

    【注意】URL 会进访问日志、代理日志、浏览器历史 —— 只适合短期一次性票据
    """
    token = websocket.query_params.get("token")
    if token != VALID_TOKEN:
        await reject(websocket, "invalid query token")
        return
    await serve(websocket, "query-user")


# ============================================================
# 2. header 鉴权
# ============================================================
@app.websocket("/ws/auth/header")
async def auth_header(websocket: WebSocket) -> None:
    """【实测】`Authorization: Bearer secret-token`

    【注意】浏览器原生 `WebSocket` **不能**自定义头，只能用 cookie 或首帧
    """
    token = token_from_header(websocket.headers.get("authorization"))
    if token != VALID_TOKEN:
        await reject(websocket, "invalid authorization header")
        return
    await serve(websocket, "header-user")


# ============================================================
# 3. cookie 鉴权
# ============================================================
@app.websocket("/ws/auth/cookie")
async def auth_cookie(websocket: WebSocket) -> None:
    """【实测】`session=secret-token`；浏览器同域自动带"""
    token = websocket.cookies.get("session")
    if token != VALID_TOKEN:
        await reject(websocket, "invalid session cookie")
        return
    await serve(websocket, "cookie-user")


# ============================================================
# 4. 首帧鉴权
# ============================================================
@app.websocket("/ws/auth/first-frame")
async def auth_first_frame(websocket: WebSocket, timeout: float = 1.0) -> None:
    """【实测】先 accept，再等第一帧 `{"type":"auth","token":"..."}`

    【要点】必须设超时：否则攻击者连上不发帧，就能白占连接
    """
    await websocket.accept()
    try:
        frame = await asyncio.wait_for(websocket.receive_json(), timeout=timeout)
    except TimeoutError:
        STATS["rejected"] += 1
        await websocket.close(code=1008, reason="auth timeout")
        return
    except WebSocketDisconnect:
        return

    if not isinstance(frame, dict) or frame.get("type") != "auth":
        STATS["rejected"] += 1
        await websocket.close(code=1008, reason="first frame must be auth")
        return
    if frame.get("token") != VALID_TOKEN:
        STATS["rejected"] += 1
        await websocket.close(code=1008, reason="invalid token")
        return

    STATS["connected"] += 1
    user = str(frame.get("user") or "first-frame-user")
    ACTIVE[user] = websocket
    try:
        await websocket.send_json({"type": "ready", "user": user})
        while True:
            message = await websocket.receive_json()
            if message.get("type") == "ping":
                await websocket.send_json({"type": "pong"})
            else:
                await websocket.send_json({"type": "echo", "payload": message})
    except WebSocketDisconnect:
        pass
    finally:
        ACTIVE.pop(user, None)
        STATS["closed"] += 1


# ============================================================
# 诊断
# ============================================================
@app.get("/stats", tags=["诊断"], summary="鉴权统计")
def stats() -> dict[str, Any]:
    return {"active": sorted(ACTIVE), **STATS}


@app.delete("/stats", tags=["诊断"], summary="重置")
def clear() -> dict[str, int]:
    reset_stats()
    return {"reset": 1}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)