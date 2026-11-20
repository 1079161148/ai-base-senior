"""第 47 章手写 HS256 的精简复用版（本章只需签发/校验）。

【说明】生产请用 PyJWT；这里为了不引入依赖并保持「可读的每一步」。
"""

import base64
import hashlib
import hmac
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Final

SECRET_KEY: Final = "demo-secret-please-change-me-0123456789"
ALGORITHM: Final = "HS256"
DEFAULT_TTL_MINUTES: Final = 30


class InvalidToken(Exception):
    def __init__(self, reason: str) -> None:
        self.reason = reason
        super().__init__(reason)


def _b64encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64decode(text: str) -> bytes:
    return base64.urlsafe_b64decode(text + "=" * (-len(text) % 4))


def create_access_token(data: dict[str, Any], ttl_minutes: int = DEFAULT_TTL_MINUTES) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        **data,
        "iat": int(now.timestamp()),
        "exp": int((now + timedelta(minutes=ttl_minutes)).timestamp()),
    }
    header = {"alg": ALGORITHM, "typ": "JWT"}
    segments = (
        _b64encode(json.dumps(header, separators=(",", ":"), sort_keys=True).encode()),
        _b64encode(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode()),
    )
    signing_input = ".".join(segments)
    signature = hmac.new(SECRET_KEY.encode(), signing_input.encode("ascii"), hashlib.sha256).digest()
    return f"{signing_input}.{_b64encode(signature)}"


def decode_token(token: str) -> dict[str, Any]:
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
    if not hmac.compare_digest(expected, parts[2]):
        raise InvalidToken("签名不符")
    exp = payload.get("exp")
    if not isinstance(exp, int):
        raise InvalidToken("缺少 exp")
    if exp < int(time.time()):
        raise InvalidToken("已过期")
    return payload