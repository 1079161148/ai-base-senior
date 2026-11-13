"""待办 HTTP 接口（S9 起按用户隔离）。

本层只做三件事：解析请求 → 调 service → 交给 response_model 序列化。
**任何业务判断都不写在这里**，否则将来接 Agent 工具时逻辑要抄第二遍。
"""

from typing import Annotated

import aiosqlite
from fastapi import APIRouter, Depends, status

from ...core.db import get_db
from ...core.security import CurrentUserDep
from ...models.todo import TodoCreate, TodoOut, TodoUpdate
from ...services import todo as todo_service

router = APIRouter(prefix="/todos", tags=["todos"])

# 把「数据库连接依赖」抽成类型别名：
# 不抽的话每个函数签名都要写 db: aiosqlite.Connection = Depends(get_db)
DbDep = Annotated[aiosqlite.Connection, Depends(get_db)]


@router.get("", response_model=list[TodoOut], summary="待办列表")
async def list_todos(user: CurrentUserDep, db: DbDep) -> list[TodoOut]:
    return await todo_service.list_todos(db, user_id=user.id)


@router.get("/{todo_id}", response_model=TodoOut, summary="待办详情")
async def get_todo(todo_id: int, user: CurrentUserDep, db: DbDep) -> TodoOut:
    return await todo_service.get_todo(db, todo_id, user_id=user.id)


@router.post(
    "",
    response_model=TodoOut,
    status_code=status.HTTP_201_CREATED,  # 201 而不是 200：明确告诉客户端"创建成功了"
    summary="新增待办",
)
async def create_todo(payload: TodoCreate, user: CurrentUserDep, db: DbDep) -> TodoOut:
    return await todo_service.create_todo(db, payload, user_id=user.id)


@router.patch("/{todo_id}", response_model=TodoOut, summary="局部更新待办")
async def update_todo(
    todo_id: int,
    payload: TodoUpdate,
    user: CurrentUserDep,
    db: DbDep,
) -> TodoOut:
    return await todo_service.update_todo(db, todo_id, payload, user_id=user.id)


@router.delete(
    "/{todo_id}",
    status_code=status.HTTP_204_NO_CONTENT,  # 204 无响应体，前端不该去解析 JSON
    summary="删除待办",
)
async def delete_todo(todo_id: int, user: CurrentUserDep, db: DbDep) -> None:
    await todo_service.delete_todo(db, todo_id, user_id=user.id)
