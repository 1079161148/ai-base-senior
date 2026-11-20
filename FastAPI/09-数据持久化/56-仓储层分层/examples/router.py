"""第 56 章 · 路由层：**只有 HTTP 语义**，不含 SQL、不含业务规则。

【判据】这里不该出现查询语句，也不该做「重名判断」；
        它只做参数绑定、状态码、把领域异常翻译成 HTTP。
"""

import sqlite3
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Response, status

from db import get_db
from models import DuplicateItemError, Item, ItemCreate, ItemNotFoundError
from repository import ItemRepository
from service import ItemService

router = APIRouter(prefix="/items", tags=["条目"])


def get_repository(
    conn: Annotated[sqlite3.Connection, Depends(get_db)],
) -> ItemRepository:
    """【作用】组装仓储；换实现只改这一个函数（或 `dependency_overrides`）"""
    return ItemRepository(conn)


def get_service(
    repository: Annotated[ItemRepository, Depends(get_repository)],
) -> ItemService:
    return ItemService(repository)


ServiceDep = Annotated[ItemService, Depends(get_service)]


@router.get("", response_model=list[Item], summary="列表")
def list_items(service: ServiceDep) -> list[Item]:
    return service.list_items()


@router.get("/{item_id}", response_model=Item, summary="详情")
def get_item(item_id: int, service: ServiceDep) -> Item:
    try:
        return service.get_item(item_id)
    except ItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail="条目不存在") from exc


@router.post(
    "",
    response_model=Item,
    status_code=status.HTTP_201_CREATED,
    summary="新增",
)
def create_item(payload: ItemCreate, service: ServiceDep) -> Item:
    try:
        return service.create_item(payload)
    except DuplicateItemError as exc:
        raise HTTPException(status_code=409, detail=f"名称已存在：{exc.name}") from exc


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除")
def delete_item(item_id: int, service: ServiceDep) -> Response:
    try:
        service.delete_item(item_id)
    except ItemNotFoundError as exc:
        raise HTTPException(status_code=404, detail="条目不存在") from exc
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/_/count", summary="计数")
def count_items(service: ServiceDep) -> dict[str, int]:
    """【注意】这条路由要在 `/{item_id}` **之后**声明吗？

    【实测】`/_/count` 与 `/{item_id}` 不冲突（前者是两段），但 `/items/count`
            这种单段路径会被 `/{item_id}` 先匹配 → 422（`int` 解析失败）
    """
    return {"count": service.count()}