"""第 65 章 · items 模块。

【要点】`responses={404: ...}` 写在 router 上，所有端点共享这份文档。
"""

from fastapi import APIRouter, HTTPException, status

import store
from models import Item

router = APIRouter(
    prefix="/items",
    tags=["items"],
    responses={404: {"description": "商品不存在"}},
)


@router.get("", summary="商品列表")
def list_items() -> list[Item]:
    return list(store.ITEMS.values())


@router.get("/{item_id}", summary="商品详情")
def get_item(item_id: int) -> Item:
    item = store.ITEMS.get(item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
    return item


@router.post("", status_code=status.HTTP_201_CREATED, summary="新建商品")
def create_item(name: str, price: int) -> Item:
    new_id = max(store.ITEMS, default=0) + 1
    item = Item(id=new_id, name=name, price=price)
    store.ITEMS[new_id] = item
    return item