"""鉴权：只保护写操作。

【要点】用 `HTTPBearer(auto_error=False)` 而不是 `True`：
        这样「没带令牌」和「令牌错误」走我们统一的错误契约，而不是框架默认的 403。
"""

from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

# 本章演示用固定令牌；第 78 章改成从配置读
DEMO_TOKEN = "demo-token"

bearer_scheme = HTTPBearer(auto_error=False, description="Bearer demo-token")


def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer_scheme)],
) -> str:
    if credentials is None or credentials.credentials != DEMO_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "unauthorized", "message": "需要有效的 Bearer 令牌"},
            headers={"WWW-Authenticate": "Bearer"},
        )
    return "demo-user"


CurrentUser = Annotated[str, Depends(get_current_user)]


def require_writer(user: CurrentUser) -> str:
    """【作用】写操作的统一依赖，读操作不挂它"""
    return user


Writer = Annotated[str, Depends(require_writer)]