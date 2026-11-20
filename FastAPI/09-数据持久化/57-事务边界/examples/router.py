"""第 57 章 · 路由层：只做 HTTP 语义。

【要点】领域异常不在这里翻译，统一交给 `main.py` 的 `exception_handler`，
        路由函数就能保持「一行业务调用」的干净形态。
"""

import sqlite3
from typing import Annotated, Iterator

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status

from db import get_db
from models import Item, ItemCreate
from repository import ItemRepository
from service import ItemService

router = APIRouter(prefix="/items", tags=["条目"])


def get_repository(
    conn: Annotated[sqlite3.Connection, Depends(get_db)],
) -> ItemRepository:
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
    return service.get_item(item_id)


@router.post("", response_model=Item, status_code=status.HTTP_201_CREATED, summary="新增")
def create_item(payload: ItemCreate, service: ServiceDep) -> Item:
    return service.create_item(payload)


@router.post(
    "/batch",
    response_model=list[Item],
    status_code=status.HTTP_201_CREATED,
    summary="批量新增（原子）",
)
def create_batch(payloads: list[ItemCreate], service: ServiceDep) -> list[Item]:
    """【实测】`[ok1, ok2, dup]` → 409，且 `ok1/ok2` **都不落库**"""
    return service.create_many(payloads)


@router.post("/crash", status_code=status.HTTP_204_NO_CONTENT, summary="故意失败（验证回滚）")
def crash(payload: ItemCreate, service: ServiceDep) -> Response:
    """【实测】写一条再抛 `RuntimeError` → 500，写入被回滚"""
    service.rename_then_fail(payload)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/_/audit", summary="审计记录（同事务内的第二次写）")
def read_audit(
    service: ServiceDep,
    limit: Annotated[int, Query(ge=1, le=100)] = 10,
) -> dict[str, list[str]]:
    """【要点】审计与主表在**同一个连接**里写，所以天然一致"""
    return {"notes": service.audit_notes()[-limit:]}


@router.post("/teapot", status_code=status.HTTP_418_IM_A_TEAPOT, summary="HTTPException 也回滚")
def teapot(payload: ItemCreate, service: ServiceDep) -> None:
    """【实测】先写一条、再抛 `HTTPException(418)` → 418 且写入被回滚"""
    service.create_item(payload)
    raise HTTPException(status_code=418, detail="我是茶壶")


def get_marker(
    conn: Annotated[sqlite3.Connection, Depends(get_db)],
) -> Iterator[sqlite3.Connection]:
    """【作用】第二个 `yield` 依赖，用于观察清理顺序（后进先出）"""
    from db import EVENTS

    EVENTS.append("marker:begin")
    try:
        yield conn
        EVENTS.append("marker:end")
    finally:
        EVENTS.append("marker:close")


@router.get("/_/marker", summary="观察依赖清理顺序")
def with_marker(
    marker: Annotated[sqlite3.Connection, Depends(get_marker)],
    service: ServiceDep,
) -> dict[str, int]:
    return {"count": len(service.list_items())}