"""第 65 章 · 公共依赖。

【要点】依赖放独立模块，router 通过 `dependencies=[Depends(...)]` 批量挂载，
        而不是每个端点重复写一遍。
"""

from typing import Annotated

from fastapi import Header, HTTPException, status

ADMIN_TOKEN = "secret-admin"


def require_admin(
    x_admin_token: Annotated[str | None, Header(alias="X-Admin-Token")] = None,
) -> str:
    """【作用】router 级依赖：挂一次，该 router 下所有端点都生效"""
    if x_admin_token != ADMIN_TOKEN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="admin token required",
        )
    return x_admin_token