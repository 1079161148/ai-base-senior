"""S4 · 会话持久化。

负责 sessions / session_messages / session_memories 三张表的 CRUD。
所有方法都接受 aiosqlite.Connection 参数 —— 调用方（chat.py）注入。
"""

import logging
import uuid
from datetime import datetime, timezone

import aiosqlite

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


# ---- 会话 ----

async def create_session(db: aiosqlite.Connection, title: str = "", *, user_id: str = "") -> str:
    """新建会话，返回 session_id。"""
    sid = uuid.uuid4().hex[:12]
    now = _now()
    await db.execute(
        "INSERT INTO sessions (id, user_id, title, created_at, updated_at) VALUES (?, ?, ?, ?, ?)",
        (sid, user_id, title or "新对话", now, now),
    )
    await db.commit()
    return sid


async def list_sessions(db: aiosqlite.Connection, *, user_id: str = "") -> list[dict]:
    """按更新时间倒序返回**当前用户**的会话（仅基本信息，不含消息）。

    last_user_message 是会话里最后一次提问。
    标题只在首轮生成、之后不再变，光看标题无法判断「这个会话后来还聊了什么」，
    所以列表要带上最近提问 —— 用户找会话时记的是「我问了什么」，
    不是模型怎么回答的。
    """
    rows = await db.execute_fetchall(
        """SELECT s.id, s.title, s.created_at, s.updated_at,
                  (SELECT COUNT(*) FROM session_messages
                     WHERE session_id = s.id) AS msg_count,
                  (SELECT content FROM session_messages
                     WHERE session_id = s.id AND role = 'user'
                     ORDER BY id DESC LIMIT 1) AS last_user_message
           FROM sessions s
           WHERE s.user_id = ?
           ORDER BY s.updated_at DESC
           LIMIT 50""",
        (user_id,),
    )
    return [dict(r) for r in rows]


async def get_session(db: aiosqlite.Connection, sid: str, *, user_id: str = "") -> dict | None:
    """获取某个会话的基本信息（不含消息）。

    不属于当前用户的会话一律返回 None —— 上层统一报 404，
    不告诉调用方"这个 id 存在但不是你的"（那是免费的信息泄露）。
    """
    row = await db.execute_fetchall(
        """SELECT s.id, s.title, s.created_at, s.updated_at,
                  (SELECT COUNT(*) FROM session_messages WHERE session_id = s.id) AS msg_count
           FROM sessions s WHERE s.id = ? AND s.user_id = ?""",
        (sid, user_id),
    )
    return dict(row[0]) if row else None


async def get_session_messages(db: aiosqlite.Connection, sid: str) -> list[dict]:
    """按时间顺序返回某个会话的所有消息。"""
    rows = await db.execute_fetchall(
        "SELECT id, role, content, tool_call_id, tool_calls FROM session_messages "
        "WHERE session_id = ? ORDER BY id",
        (sid,),
    )
    return [dict(r) for r in rows]


async def maybe_set_title(
    db: aiosqlite.Connection,
    sid: str,
    first_user_text: str,
) -> None:
    """会话还是默认标题时，用第一句用户提问命名。

    只在 title 为空或仍是「新对话」时生效，所以后续轮次不会覆盖用户改过的标题。
    """
    title = " ".join(first_user_text.split())[:30]
    if not title:
        return
    await db.execute(
        "UPDATE sessions SET title = ? WHERE id = ? AND (title = '' OR title = '新对话')",
        (title, sid),
    )
    await db.commit()


async def delete_session(db: aiosqlite.Connection, sid: str, *, user_id: str = "") -> bool:
    """删除会话及其所有消息和记忆。返回是否删到了。

    子表要显式删：SQLite 默认不开启外键约束，
    只删 sessions 会留下一堆孤儿消息。

    先按 user_id 删父行：如果这个会话不属于当前用户，rowcount 为 0，
    后面的子表删除自然不会执行 —— 顺序反了就等于给了别人删数据的入口。
    """
    cur = await db.execute("DELETE FROM sessions WHERE id = ? AND user_id = ?", (sid, user_id))
    if cur.rowcount == 0:
        await db.commit()
        return False
    await db.execute("DELETE FROM session_messages WHERE session_id = ?", (sid,))
    await db.execute("DELETE FROM session_memories WHERE session_id = ?", (sid,))
    await db.commit()
    return cur.rowcount > 0


# ---- 消息 ----

async def save_message(
    db: aiosqlite.Connection,
    session_id: str,
    role: str,
    content: str | None,
    *,
    tool_call_id: str | None = None,
    tool_calls: str | None = None,
) -> None:
    """存一条消息，同时更新会话的 updated_at。"""
    now = _now()
    await db.execute(
        "INSERT INTO session_messages (session_id, role, content, tool_call_id, tool_calls, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, role, content, tool_call_id, tool_calls, now),
    )
    await db.execute(
        "UPDATE sessions SET updated_at = ? WHERE id = ?", (now, session_id)
    )
    await db.commit()


async def delete_messages_from(
    db: aiosqlite.Connection,
    session_id: str,
    msg_start: int,
) -> None:
    """删除 msg_start 及之后的消息（摘要化时会用到：删掉已压缩的部分）。"""
    await db.execute(
        "DELETE FROM session_messages WHERE session_id = ? AND id >= ?",
        (session_id, msg_start),
    )
    await db.execute(
        "UPDATE sessions SET updated_at = ? WHERE id = ?", (_now(), session_id)
    )
    await db.commit()


# ---- 摘要记忆 ----

async def save_memory(
    db: aiosqlite.Connection,
    session_id: str,
    msg_start: int,
    msg_end: int,
    content: str,
    token_count: int,
) -> None:
    """存一条摘要记忆。"""
    await db.execute(
        "INSERT INTO session_memories (session_id, msg_start, msg_end, content, token_count, created_at) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        (session_id, msg_start, msg_end, content, token_count, _now()),
    )
    await db.commit()


async def load_memories(
    db: aiosqlite.Connection,
    session_id: str,
) -> list[dict]:
    """按区间顺序加载所有摘要记忆（最旧的先）。"""
    rows = await db.execute_fetchall(
        "SELECT * FROM session_memories WHERE session_id = ? ORDER BY msg_start",
        (session_id,),
    )
    return [dict(r) for r in rows]


async def get_memory_token_sum(db: aiosqlite.Connection, session_id: str) -> int:
    """某个会话所有摘要记忆的 token 数之和（用于预算计算）。"""
    row = await db.execute_fetchall(
        "SELECT COALESCE(SUM(token_count), 0) AS total FROM session_memories WHERE session_id = ?",
        (session_id,),
    )
    return row[0][0] if row else 0