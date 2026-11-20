"""第 49 章 · API Key 与 Basic 认证。

核心：机器对机器用 **API Key**（header/query/cookie 三个位置），
      简单的人类登录用 **HTTP Basic**（`Authorization: Basic base64(user:pass)`）。
      两者的共同要求：比较用 `secrets.compare_digest`（时序安全）、
      401 必须带 `WWW-Authenticate`，密钥走环境变量。

启动：uvicorn main:app --reload
验收：python verify.py
"""

import secrets
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.security import (
    APIKeyCookie,
    APIKeyHeader,
    APIKeyQuery,
    HTTPBasic,
    HTTPBasicCredentials,
)

app = FastAPI(title="第 49 章 · API Key 与 Basic", version="0.1.0")

# ============================================================
# 1. 三种 API Key 位置
# ============================================================
api_key_header = APIKeyHeader(name="X-API-Key", description="推荐位置", auto_error=True)
api_key_query = APIKeyQuery(name="api_key", description="不推荐：会进日志", auto_error=False)
api_key_cookie = APIKeyCookie(name="session_key", description="浏览器场景", auto_error=False)

# 【作用】静态 key 表；生产放数据库/密钥服务，并支持轮换（多 key 并存）
_API_KEYS: dict[str, str] = {
    "key-service-a": "service-a",
    "key-service-b": "service-b",
    "key-service-a-old": "service-a",  # 轮换期的旧 key
}


def _match_key(candidate: str | None) -> str | None:
    """【要点】逐个比较用 `compare_digest`，避免按字符比较泄漏前缀"""
    if not candidate:
        return None
    for key, owner in _API_KEYS.items():
        if secrets.compare_digest(key, candidate):
            return owner
    return None


def verify_header_key(key: Annotated[str, Security(api_key_header)]) -> str:
    """【实测】缺 `X-API-Key` → 401 `Not authenticated`（由方案层抛）"""
    owner = _match_key(key)
    if owner is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key 无效",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return owner


# ============================================================
# 2. HTTP Basic
# ============================================================
basic_scheme = HTTPBasic(realm="ch49-demo", scheme_name="BasicAuth")

_BASIC_USERS: dict[str, str] = {  # 【警告】演示用明文；生产存哈希
    "alice": "alice123",
    "bob": "bob123",
}


def verify_basic(credentials: Annotated[HTTPBasicCredentials, Security(basic_scheme)]) -> str:
    """【实测】`HTTPBasicCredentials` 有 `.username` / `.password` 两个字段

    【必须】用 `compare_digest` 比较密码，别用 `==`

    【要点】用户不存在时也做一次比较（用哨兵值），
            避免「响应时间差」暴露用户名是否存在
    """
    expected = _BASIC_USERS.get(credentials.username, "\x00invalid-sentinel")
    if not secrets.compare_digest(credentials.password, expected):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="用户名或密码错误",
            headers={"WWW-Authenticate": 'Basic realm="ch49-demo"'},
        )
    return credentials.username


# ============================================================
# 3. 端点
# ============================================================
@app.get("/machine/ping", tags=["API Key"], summary="header 版")
def machine_ping(owner: Annotated[str, Security(verify_header_key)]) -> dict[str, str]:
    """【实测】有效 key → 200；无效 → 401 + `WWW-Authenticate: ApiKey`"""
    return {"owner": owner}


@app.get("/machine/query", tags=["API Key"], summary="query 版（不推荐）")
def machine_query(
    key: Annotated[str | None, Security(api_key_query)],
) -> dict[str, Any]:
    """【实测】`auto_error=False` → 缺参数得到 `None`，需要自己判

    【风险】query 会进 access log、浏览器历史、Referer
    """
    owner = _match_key(key)
    if owner is None:
        raise HTTPException(
            status_code=401,
            detail="api_key 缺失或无效",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return {"owner": owner}


@app.get("/machine/cookie", tags=["API Key"], summary="cookie 版")
def machine_cookie(
    key: Annotated[str | None, Security(api_key_cookie)],
) -> dict[str, Any]:
    """【注意】cookie 方案要考虑 CSRF；纯 API 场景别用"""
    owner = _match_key(key)
    if owner is None:
        raise HTTPException(status_code=401, detail="session_key 无效")
    return {"owner": owner}


@app.get("/basic/me", tags=["Basic"], summary="Basic 认证")
def basic_me(user: Annotated[str, Security(verify_basic)]) -> dict[str, str]:
    return {"user": user}


@app.get("/basic/protected", tags=["Basic"], summary="再挂一层")
def basic_protected(user: Annotated[str, Security(verify_basic)]) -> dict[str, str]:
    return {"secret": "only-for-authenticated", "user": user}


# ============================================================
# 4. 组合：机器用 key，人用 basic
# ============================================================
# 【要点】`Security()` 本身不接受 `auto_error`，要可选必须用「方案对象」上的 auto_error
api_key_header_soft = APIKeyHeader(name="X-API-Key", auto_error=False)
basic_soft = HTTPBasic(realm="ch49-demo", scheme_name="BasicAuth", auto_error=False)


def either_identity(
    key: Annotated[str | None, Security(api_key_header_soft)] = None,
    creds: Annotated[HTTPBasicCredentials | None, Security(basic_soft)] = None,
) -> str:
    """【注意】两个方案都要 `auto_error=False` 才能做 OR（`Security(auto_error=)` 会 TypeError）"""
    if (owner := _match_key(key)) is not None:
        return f"service:{owner}"
    if creds and creds.username in _BASIC_USERS:
        if secrets.compare_digest(creds.password, _BASIC_USERS[creds.username]):
            return f"user:{creds.username}"
    raise HTTPException(
        status_code=401,
        detail="需要 X-API-Key 或 Basic 认证",
        headers={"WWW-Authenticate": 'Basic realm="ch49-demo"'},
    )


@app.get("/any/whoami", tags=["组合"], summary="二选一")
def whoami(identity: Annotated[str, Security(either_identity)]) -> dict[str, str]:
    return {"identity": identity}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)