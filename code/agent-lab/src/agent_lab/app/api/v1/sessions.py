"""S4 · 会话管理 API（S9 起按用户隔离）。

GET  /sessions         列出当前用户的会话
POST /sessions         新建会话
GET  /sessions/{id}    获取会话详情（含消息）
DELETE /sessions/{id}  删除会话

**每个接口都带 CurrentUserDep**：这不是"加个装饰"，而是数据隔离的唯一入口。
少了它，前端换一个 session_id 就能读到别人的聊天记录。
"""

import aiosqlite
from fastapi import APIRouter, Depends

from ...core.db import get_db
from ...core.errors import ApiError
from ...core.security import CurrentUserDep
from ...models.session import SessionCreate, SessionDetail, SessionInfo
from ...services.memory import session as session_svc

router = APIRouter(prefix="/sessions", tags=["sessions"])


@router.post("", summary="新建会话")
async def create(
    user: CurrentUserDep,
    body: SessionCreate = SessionCreate(),
    db: aiosqlite.Connection = Depends(get_db),
) -> dict[str, str]:
    sid = await session_svc.create_session(db, title=body.title or "", user_id=user.id)
    return {"id": sid}


@router.get("", summary="会话列表")
async def list_sessions_endpoint(
    user: CurrentUserDep,
    db: aiosqlite.Connection = Depends(get_db),
) -> list[SessionInfo]:
    rows = await session_svc.list_sessions(db, user_id=user.id)
    return [SessionInfo(**r) for r in rows]


@router.get("/{sid}", summary="会话详情")
async def get(
    sid: str,
    user: CurrentUserDep,
    db: aiosqlite.Connection = Depends(get_db),
) -> SessionDetail:
    info = await session_svc.get_session(db, sid, user_id=user.id)
    if not info:
        raise ApiError(404, "SESSION_NOT_FOUND", f"会话 {sid} 不存在")
    messages = await session_svc.get_session_messages(db, sid)
    return SessionDetail(messages=messages, **info)


@router.delete("/{sid}", summary="删除会话")
async def delete(
    sid: str,
    user: CurrentUserDep,
    db: aiosqlite.Connection = Depends(get_db),
) -> dict[str, str]:
    ok = await session_svc.delete_session(db, sid, user_id=user.id)
    if not ok:
        raise ApiError(404, "SESSION_NOT_FOUND", f"会话 {sid} 不存在")
    return {"ok": "deleted"}
