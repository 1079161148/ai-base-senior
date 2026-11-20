"""第 47 章 · JWT 实现（HS256）。

核心：JWT = `base64url(header).base64url(payload).base64url(signature)`，
      签名 = `HMAC-SHA256(secret, header.payload)`。**payload 只是 base64，不是加密**，
      任何人都能读；能防的只有「篡改」。
      本章用 `hmac` + `hashlib` 手写，看清每一步；生产直接上 PyJWT。

启动：uvicorn main:app --reload
验收：python verify.py
"""

import base64
import hashlib
import hmac
import json
import secrets
import time
from datetime import datetime, timedelta, timezone
from typing import Annotated, Any, Final

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

app = FastAPI(title="第 47 章 · JWT 实现", version="0.1.0")

# 【警告】演示用硬编码；生产从环境变量/密钥管理服务读，且长度 ≥32 字节随机
SECRET_KEY: Final = "demo-secret-please-change-me-0123456789"
ALGORITHM: Final = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES: Final = 30

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# ============================================================
# 1. base64url 工具（JWT 用无填充的 urlsafe base64）
# ============================================================
def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    padding = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + padding)


# ============================================================
# 2. 签发
# ============================================================
def create_access_token(
    data: dict[str, Any],
    expires_delta: timedelta | None = None,
) -> str:
    """【实测】三段用 `.` 连接，每段都无 `=` 填充；`exp`/`iat` 是 unix 秒

    【要点】`sub` 放用户名（不是整个用户对象），token 里**不要**放密码/手机号
    """
    now = datetime.now(timezone.utc)
    expire = now + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    payload = {**data, "iat": int(now.timestamp()), "exp": int(expire.timestamp())}
    header = {"alg": ALGORITHM, "typ": "JWT"}

    segments = (
        _b64encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode()),
        _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()),
    )
    signing_input = ".".join(segments)
    signature = hmac.new(
        SECRET_KEY.encode(),
        signing_input.encode("ascii"),
        hashlib.sha256,
    ).digest()
    return f"{signing_input}.{_b64encode(signature)}"


# ============================================================
# 3. 校验
# ============================================================
class InvalidToken(Exception):
    """【作用】内部异常，映射为 401"""

    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def decode_token(token: str) -> dict[str, Any]:
    """【实测】校验顺序：段数 → 头算法 → 签名 → exp

    【关键】必须校验 `alg`！否则 `{"alg":"none"}` 的攻击 token 会被放行
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise InvalidToken("token 必须是三段")

    try:
        header = json.loads(_b64decode(parts[0]))
        payload = json.loads(_b64decode(parts[1]))
    except (ValueError, json.JSONDecodeError) as exc:
        raise InvalidToken("无法解析") from exc

    if header.get("alg") != ALGORITHM:
        raise InvalidToken(f"不支持的算法 {header.get('alg')!r}")

    expected = _b64encode(
        hmac.new(
            SECRET_KEY.encode(),
            f"{parts[0]}.{parts[1]}".encode("ascii"),
            hashlib.sha256,
        ).digest()
    )
    # 【要点】用 compare_digest 防时序攻击，别用 ==
    if not hmac.compare_digest(expected, parts[2]):
        raise InvalidToken("签名不符")

    now = int(time.time())
    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise InvalidToken("缺少 exp")
    if exp < now:
        raise InvalidToken("已过期")

    return payload


# ============================================================
# 4. 密码哈希（不引第三方，只是演示原理）
# ============================================================
def hash_password(password: str, salt: str | None = None) -> str:
    """【实测】同一密码两次调用得到**不同的哈希**（salt 随机）"""
    salt = salt or secrets.token_hex(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000)
    return f"pbkdf2_sha256${salt}${dk.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        _, salt, _ = stored.split("$")
    except ValueError:
        return False
    return hmac.compare_digest(hash_password(password, salt), stored)


_USERS: dict[str, dict[str, Any]] = {
    "alice": {
        "username": "alice",
        "full_name": "Alice Chen",
        "hashed_password": hash_password("alice123"),
        "disabled": False,
    },
    "bob": {
        "username": "bob",
        "full_name": "Bob Wang",
        "hashed_password": hash_password("bob123"),
        "disabled": False,
    },
}


# ============================================================
# 5. 端点
# ============================================================
class TokenOut(BaseModel):
    access_token: str
    token_type: str
    expires_in: int


class UserOut(BaseModel):
    username: str
    full_name: str


@app.post("/token", response_model=TokenOut, tags=["JWT"], summary="签发 JWT")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> TokenOut:
    user = _USERS.get(form.username)
    if user is None or not verify_password(form.password, user["hashed_password"]):
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    token = create_access_token({"sub": user["username"]})
    return TokenOut(
        access_token=token,
        token_type="bearer",
        expires_in=ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> dict[str, Any]:
    """【实测】签名错/过期/算法不对 → 401 + `error="invalid_token"`"""
    try:
        payload = decode_token(token)
    except InvalidToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"token 无效：{exc.reason}",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        ) from exc

    user = _USERS.get(payload.get("sub", ""))
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")
    if user["disabled"]:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


@app.get("/users/me", response_model=UserOut, tags=["JWT"], summary="解码取用户")
async def read_me(user: Annotated[dict[str, Any], Depends(get_current_user)]) -> Any:
    return user


@app.post("/token/expired", tags=["JWT"], summary="签一个已过期的 token")
def make_expired(username: str = "alice") -> dict[str, str]:
    """【作用】验收用：立刻过期的 token"""
    return {
        "access_token": create_access_token({"sub": username}, timedelta(seconds=-1)),
        "token_type": "bearer",
    }


@app.get("/debug/payload", tags=["JWT"], summary="payload 是明文")
def debug_payload(token: str) -> dict[str, Any]:
    """【实测】不验签也能读出 payload —— 证明 JWT 不是加密

    【警告】仅演示；任何端点都不该提供这种能力
    """
    parts = token.split(".")
    if len(parts) != 3:
        raise HTTPException(status_code=400, detail="格式错")
    return {
        "header": json.loads(_b64decode(parts[0])),
        "payload": json.loads(_b64decode(parts[1])),
        "segments": len(parts),
        "has_padding": "=" in token,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)