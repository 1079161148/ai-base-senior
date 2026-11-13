"""S9 · 鉴权接口。

POST /auth/login     用户名密码换 token
POST /auth/register  自助注册（演示用，生产应关闭或加邀请码）
GET  /auth/me        校验 token 并返回当前用户
"""

import logging

import aiosqlite
from fastapi import APIRouter, Depends

from ...core.config import settings
from ...core.db import get_db
from ...core.errors import ApiError
from ...core.security import CurrentUserDep, create_token, verify_password
from ...models.auth import LoginRequest, RegisterRequest, TokenOut, UserOut
from ...services import users as user_svc

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])

DbDep = aiosqlite.Connection


@router.post("/login", summary="登录，换取 token")
async def login(
    body: LoginRequest,
    db: DbDep = Depends(get_db),
) -> TokenOut:
    row = await user_svc.get_by_username(db, body.username)

    # 用户不存在和密码错误返回**同一句话**：
    # 区分开等于送给攻击者一个用户名枚举接口。
    if not row or not verify_password(body.password, str(row["password_hash"])):
        logger.info("登录失败：%s", body.username)
        raise ApiError(401, "BAD_CREDENTIALS", "用户名或密码错误")

    token = create_token(str(row["id"]), str(row["username"]))
    return TokenOut(
        access_token=token,
        expires_in=settings.AUTH_TOKEN_TTL_SECONDS,
        user=UserOut(
            id=str(row["id"]),
            username=str(row["username"]),
            display_name=str(row["display_name"] or ""),
        ),
    )


@router.post("/register", summary="注册新用户")
async def register(
    body: RegisterRequest,
    db: DbDep = Depends(get_db),
) -> TokenOut:
    if await user_svc.get_by_username(db, body.username):
        raise ApiError(409, "USERNAME_TAKEN", "用户名已被占用")

    uid = await user_svc.create_user(db, body.username, body.password, body.display_name)
    token = create_token(uid, body.username)
    return TokenOut(
        access_token=token,
        expires_in=settings.AUTH_TOKEN_TTL_SECONDS,
        user=UserOut(id=uid, username=body.username, display_name=body.display_name or body.username),
    )


@router.get("/me", summary="当前登录用户")
async def me(user: CurrentUserDep) -> UserOut:
    return UserOut(id=user.id, username=user.username, display_name=user.display_name)
