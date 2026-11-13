"""鉴权：密码哈希 + JWT 签发/校验 + FastAPI 依赖。

**为什么不用 pyjwt / passlib**：
本项目只需要「签名一个 JSON、验一个签名」和「PBKDF2 哈希」，
两件事标准库（hmac / hashlib / secrets / base64 / json）都能做。
引入第三方库会多一个依赖面和安全更新负担，而代码只多 40 行。

**JWT 用 HS256 而不是 RS256**：
单服务、无第三方验签需求，对称密钥够用。RS256 的收益（公钥分发）在这里为零。

**密码为什么不用 SHA256 直接存**：
GPU 一秒能算几十亿次。PBKDF2 迭代 26 万次把每次尝试的成本抬到毫秒级，
配合每用户随机 salt，撞库彩虹表也失效。

**这个文件里最容易写错的三处**（都已处理，改动时别退回去）：
1. 签名比较必须用 hmac.compare_digest，不能用 ==（时序攻击）
2. exp 必须校验，且用 UTC 时间戳（本地时区会让 token 提前/延后过期）
3. 解析 token 的所有失败路径都要返回 None，不能抛异常到路由层（否则 500）
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import logging
import secrets
import time
from dataclasses import dataclass
from typing import Annotated

import aiosqlite
from fastapi import Depends, Request

from .config import settings
from .db import get_db
from .errors import ApiError

logger = logging.getLogger(__name__)

# PBKDF2 迭代次数。2024 年 OWASP 对 PBKDF2-HMAC-SHA256 的建议下限是 60 万，
# 但那是给「密码可能被离线爆破」的高价值账户。学习项目取 26 万：
# 单次校验约 60ms，登录体验可接受，同时仍比一次性 SHA256 强几个数量级。
_PBKDF2_ITERATIONS = 260_000
_ALGO = "pbkdf2_sha256"


# ---------------------------------------------------------------- 密码


def hash_password(password: str) -> str:
    """生成 `pbkdf2_sha256$迭代次数$salt$hash` 格式的字符串。

    把参数一起存进去，以后调高迭代次数时老密码仍能校验
    —— 不这么做的话，改一次参数所有用户都得重置密码。
    """
    salt = secrets.token_bytes(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, _PBKDF2_ITERATIONS)
    return f"{_ALGO}${_PBKDF2_ITERATIONS}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    """校验密码。格式不对、算法不认识都返回 False，不抛异常。"""
    try:
        algo, iterations, salt_hex, digest_hex = stored.split("$")
        if algo != _ALGO:
            return False
        digest = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            bytes.fromhex(salt_hex),
            int(iterations),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------- JWT（HS256）


def _b64e(raw: bytes) -> str:
    """URL-safe base64，去掉 padding（JWT 规范要求）。"""
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64d(text: str) -> bytes:
    """补回 padding 再解 —— 少了这一步，长度不是 4 的倍数的段会解码失败。"""
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def _sign(message: str) -> str:
    return _b64e(
        hmac.new(settings.AUTH_SECRET.encode("utf-8"), message.encode("ascii"), hashlib.sha256).digest()
    )


def create_token(user_id: str, username: str, ttl_seconds: int | None = None) -> str:
    """签发 token。payload 只放身份信息，绝不放密码或权限位。

    权限每次从库里读，token 里存权限的话改权限要等 token 过期才生效。
    """
    now = int(time.time())
    ttl = ttl_seconds if ttl_seconds is not None else settings.AUTH_TOKEN_TTL_SECONDS
    header = {"alg": "HS256", "typ": "JWT"}
    payload = {"sub": user_id, "name": username, "iat": now, "exp": now + ttl}

    # separators 去掉空格：JWT 是拿来传输的，能省一个字节是一个
    segments = (
        _b64e(json.dumps(header, separators=(",", ":")).encode("utf-8"))
        + "."
        + _b64e(json.dumps(payload, separators=(",", ":")).encode("utf-8"))
    )
    return f"{segments}.{_sign(segments)}"


def decode_token(token: str) -> dict[str, object] | None:
    """校验并解析 token。任何异常都返回 None —— 调用方只需要判空。"""
    try:
        segments, signature = token.rsplit(".", 1)
    except ValueError:
        return None

    # 先验签再解析 payload：顺序反了等于先信任了攻击者给的 JSON
    if not hmac.compare_digest(_sign(segments), signature):
        return None

    try:
        payload = json.loads(_b64d(segments.split(".")[1]))
    except (ValueError, IndexError):
        return None

    if not isinstance(payload, dict):
        return None

    exp = payload.get("exp")
    if not isinstance(exp, int) or exp < int(time.time()):
        return None

    return payload


# ---------------------------------------------------------------- 当前用户


@dataclass(frozen=True, slots=True)
class CurrentUser:
    id: str
    username: str
    display_name: str = ""

    @property
    def is_demo(self) -> bool:
        return self.id == DEMO_USER.id


# 关闭鉴权时使用的固定用户。
# 存在的意义：本地调 Swagger、跑脚本、做单测不该被迫先登录一遍。
DEMO_USER = CurrentUser(id="demo", username="demo", display_name="演示用户")


def _bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    scheme, _, token = header.partition(" ")
    return token.strip() if scheme.lower() == "bearer" else ""


async def get_current_user(
    request: Request,
    db: Annotated[aiosqlite.Connection, Depends(get_db)],
) -> CurrentUser:
    """FastAPI 依赖：从 Authorization 头解析出当前用户。

    **为什么每次都要查库，而不是直接信任 token 里的 username**：
    用户可能已被删除或改名，token 还没过期。查一次的代价是本地 SQLite 的一次
    主键查询（微秒级），换来的是「删了用户立刻失效」。
    """
    if not settings.AUTH_ENABLED:
        return DEMO_USER

    token = _bearer_token(request)
    if not token:
        raise ApiError(401, "UNAUTHORIZED", "请先登录")

    payload = decode_token(token)
    if payload is None:
        raise ApiError(401, "INVALID_TOKEN", "登录已过期，请重新登录")

    user_id = payload.get("sub")
    if not isinstance(user_id, str) or not user_id:
        raise ApiError(401, "INVALID_TOKEN", "登录状态异常，请重新登录")

    row = await db.execute_fetchall(
        "SELECT id, username, display_name FROM users WHERE id = ?",
        (user_id,),
    )
    if not row:
        # token 有效但用户已被删：不能放行，否则会往一个不存在的 user_id 写数据
        raise ApiError(401, "USER_NOT_FOUND", "账号已不存在，请重新登录")

    return CurrentUser(
        id=row[0]["id"],
        username=row[0]["username"],
        display_name=row[0]["display_name"] or "",
    )


CurrentUserDep = Annotated[CurrentUser, Depends(get_current_user)]
