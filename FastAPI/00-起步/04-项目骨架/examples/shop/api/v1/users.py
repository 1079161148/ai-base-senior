"""用户路由：演示第二个资源模块，结构与 items.py 完全对称。

新增一个资源时，只需复制这个文件的骨架，然后到 router.py 里 include 一行。
"""

from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["用户"])

USERS: dict[int, str] = {1: "alice", 2: "bob"}


@router.get("", summary="用户列表")
def list_users() -> list[dict[str, object]]:
    return [{"id": k, "name": v} for k, v in USERS.items()]


@router.get("/{user_id}", summary="用户详情")
def get_user(user_id: int) -> dict[str, object]:
    return {"id": user_id, "name": USERS.get(user_id)}
