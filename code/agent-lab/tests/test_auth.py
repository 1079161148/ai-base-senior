"""S9 鉴权与多租户隔离测试。

**这组测试的重点不是"登录能用"，而是"越权做不到"**：
1. 密码哈希不可逆、同一密码两次哈希不同（salt 生效）
2. token 被改动一个字节就失效（签名校验生效）
3. 过期 token 失效
4. A 用户看不到、改不了、删不掉 B 用户的数据
"""

import base64
import json

import pytest

from agent_lab.app.core import security
from agent_lab.app.core.errors import ApiError
from agent_lab.app.models.todo import TodoCreate
from agent_lab.app.services import todo as todo_service
from agent_lab.app.services import users as user_svc


# ---------------------------------------------------------------- 密码


def test_password_hash_is_salted():
    """同一密码两次哈希必须不同 —— 相同就说明没加盐，彩虹表直接命中。"""
    a = security.hash_password("demo123")
    b = security.hash_password("demo123")
    assert a != b
    assert a.startswith("pbkdf2_sha256$")


def test_verify_password():
    stored = security.hash_password("demo123")
    assert security.verify_password("demo123", stored)
    assert not security.verify_password("demo124", stored)


@pytest.mark.parametrize(
    "broken",
    ["", "plaintext", "pbkdf2_sha256$abc", "md5$1$aa$bb", "pbkdf2_sha256$1$zz$zz"],
)
def test_verify_password_tolerates_garbage(broken: str):
    """库里的哈希坏了应该返回 False，而不是抛异常把登录接口打成 500。"""
    assert security.verify_password("demo123", broken) is False


# ---------------------------------------------------------------- token


def test_token_roundtrip():
    token = security.create_token("u1", "alice")
    payload = security.decode_token(token)
    assert payload is not None
    assert payload["sub"] == "u1"
    assert payload["name"] == "alice"


def test_token_expired():
    token = security.create_token("u1", "alice", ttl_seconds=-1)
    assert security.decode_token(token) is None


def test_token_tampered_payload():
    """改 payload 但保留原签名 —— 必须被拒。

    这是最常见的一种攻击：把 sub 改成别人的 id 想冒充。
    """
    token = security.create_token("u1", "alice")
    segments, signature = token.rsplit(".", 1)
    header, _payload = segments.split(".")

    forged_payload = base64.urlsafe_b64encode(
        json.dumps({"sub": "u2", "name": "bob", "exp": 9999999999}).encode()
    ).rstrip(b"=").decode()
    forged = f"{header}.{forged_payload}.{signature}"

    assert security.decode_token(forged) is None


def test_token_garbage():
    for bad in ["", "a", "a.b", "a.b.c", "....", "not-a-token"]:
        assert security.decode_token(bad) is None


# ---------------------------------------------------------------- 多租户


async def _make_user(db, name: str) -> str:  # type: ignore[no-untyped-def]
    return await user_svc.create_user(db, name, "pw123456")


async def test_todos_are_isolated(db):  # type: ignore[no-untyped-def]
    alice = await _make_user(db, "alice")
    bob = await _make_user(db, "bob")

    await todo_service.create_todo(db, TodoCreate(title="alice 的待办"), user_id=alice)
    await todo_service.create_todo(db, TodoCreate(title="bob 的待办"), user_id=bob)

    a_items = await todo_service.list_todos(db, user_id=alice)
    b_items = await todo_service.list_todos(db, user_id=bob)

    assert [i.title for i in a_items] == ["alice 的待办"]
    assert [i.title for i in b_items] == ["bob 的待办"]


async def test_cannot_read_others_todo(db):  # type: ignore[no-untyped-def]
    alice = await _make_user(db, "alice")
    bob = await _make_user(db, "bob")
    item = await todo_service.create_todo(db, TodoCreate(title="alice 的"), user_id=alice)

    with pytest.raises(ApiError) as exc:
        await todo_service.get_todo(db, item.id, user_id=bob)
    # 必须是 404 而不是 403：403 等于告诉对方"这条存在，只是不属于你"
    assert exc.value.status_code == 404


async def test_cannot_update_others_todo(db):  # type: ignore[no-untyped-def]
    from agent_lab.app.models.todo import TodoUpdate

    alice = await _make_user(db, "alice")
    bob = await _make_user(db, "bob")
    item = await todo_service.create_todo(db, TodoCreate(title="alice 的"), user_id=alice)

    with pytest.raises(ApiError):
        await todo_service.update_todo(
            db, item.id, TodoUpdate(title="被 bob 改了"), user_id=bob
        )

    # 原数据必须完好
    still = await todo_service.get_todo(db, item.id, user_id=alice)
    assert still.title == "alice 的"


async def test_cannot_delete_others_todo(db):  # type: ignore[no-untyped-def]
    alice = await _make_user(db, "alice")
    bob = await _make_user(db, "bob")
    item = await todo_service.create_todo(db, TodoCreate(title="alice 的"), user_id=alice)

    with pytest.raises(ApiError):
        await todo_service.delete_todo(db, item.id, user_id=bob)

    assert len(await todo_service.list_todos(db, user_id=alice)) == 1


async def test_sessions_are_isolated(db):  # type: ignore[no-untyped-def]
    from agent_lab.app.services.memory import session as session_svc

    alice = await _make_user(db, "alice")
    bob = await _make_user(db, "bob")

    sid = await session_svc.create_session(db, "alice 的会话", user_id=alice)

    assert [s["id"] for s in await session_svc.list_sessions(db, user_id=alice)] == [sid]
    assert await session_svc.list_sessions(db, user_id=bob) == []

    # 别人的会话读不到、删不掉
    assert await session_svc.get_session(db, sid, user_id=bob) is None
    assert await session_svc.delete_session(db, sid, user_id=bob) is False
    assert await session_svc.get_session(db, sid, user_id=alice) is not None


async def test_ensure_demo_user_is_idempotent(db):  # type: ignore[no-untyped-def]
    first = await user_svc.ensure_demo_user(db)
    second = await user_svc.ensure_demo_user(db)
    assert first == second
    assert len(await db.execute_fetchall("SELECT id FROM users")) == 1
