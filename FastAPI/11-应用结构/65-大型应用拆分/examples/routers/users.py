"""第 65 章 · users 模块。

【要点】这里只写 `prefix="/users"`，`/api/v1` 由上层组装时叠加。
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status

import store
from models import User

router = APIRouter(prefix="/users", tags=["users"])


# 【要点】静态路径必须定义在参数路径**之前**，否则会被 `/{user_id}` 抢走
@router.get("/count", summary="用户数量")
def count_users() -> dict[str, int]:
    return {"count": len(store.USERS)}


@router.get("", summary="用户列表")
def list_users(
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> list[User]:
    return list(store.USERS.values())[:limit]


@router.get("/{user_id}", summary="用户详情")
def get_user(user_id: int) -> User:
    user = store.USERS.get(user_id)
    if user is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="user not found")
    return user


# 【实测坑】这条定义在 `/{user_id}` **之后** → 请求 `/users/stats` 会被
#          `/{user_id}` 先匹配，`user_id="stats"` 解析失败 → 422 int_parsing。
#          对照上面的 `/users/count`（定义在 `/{user_id}` 之前）就正常。
@router.get("/stats", summary="用户统计（被 {user_id} 抢走）")
def user_stats() -> dict[str, int]:
    return {"users": len(store.USERS)}