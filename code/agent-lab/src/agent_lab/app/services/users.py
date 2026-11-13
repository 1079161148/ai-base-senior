"""用户注册 / 查询。

只做数据访问，密码哈希交给 core.security —— 服务层不关心算法细节。
"""

import logging
import uuid
from datetime import datetime, timezone

import aiosqlite

from ..core.config import settings
from ..core.security import hash_password

logger = logging.getLogger(__name__)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


async def create_user(
    db: aiosqlite.Connection,
    username: str,
    password: str,
    display_name: str = "",
) -> str:
    """新建用户，返回 user_id。用户名重复会抛 sqlite3.IntegrityError。"""
    uid = uuid.uuid4().hex[:12]
    await db.execute(
        "INSERT INTO users (id, username, password_hash, display_name, created_at) "
        "VALUES (?, ?, ?, ?, ?)",
        (uid, username, hash_password(password), display_name or username, _now()),
    )
    await db.commit()
    return uid


async def get_by_username(db: aiosqlite.Connection, username: str) -> dict | None:
    rows = await db.execute_fetchall(
        "SELECT id, username, password_hash, display_name FROM users WHERE username = ?",
        (username,),
    )
    return dict(rows[0]) if rows else None


async def get_by_id(db: aiosqlite.Connection, user_id: str) -> dict | None:
    rows = await db.execute_fetchall(
        "SELECT id, username, display_name FROM users WHERE id = ?",
        (user_id,),
    )
    return dict(rows[0]) if rows else None


async def ensure_demo_user(db: aiosqlite.Connection) -> str:
    """确保演示账号存在，并返回它的 id。

    启动时调用。**幂等**：已存在就什么都不做（也不重置密码，
    否则用户改过的密码每次重启都会被改回去）。
    """
    existing = await get_by_username(db, settings.DEMO_USERNAME)
    if existing:
        return str(existing["id"])

    uid = await create_user(
        db,
        settings.DEMO_USERNAME,
        settings.DEMO_PASSWORD,
        display_name="演示用户",
    )
    logger.info(
        "已创建演示账号 %s / %s —— 上线前请改密码或关闭 SEED_DEMO_USER",
        settings.DEMO_USERNAME,
        settings.DEMO_PASSWORD,
    )
    return uid


async def claim_legacy_rows(db: aiosqlite.Connection, user_id: str) -> int:
    """把 S9 之前没有归属的数据划给指定用户。

    **为什么要做**：升级后如果不管，老会话/待办会因为 `user_id = ''`
    而谁都看不到 —— 用户会以为数据丢了。一次性认领比让数据变孤儿好。

    返回被认领的行数（用于日志）。
    """
    total = 0
    for table in ("todos", "sessions", "task_plans", "trace_metrics"):
        cur = await db.execute(
            f"UPDATE {table} SET user_id = ? WHERE user_id = ''",
            (user_id,),
        )
        total += cur.rowcount or 0
    await db.commit()
    return total
