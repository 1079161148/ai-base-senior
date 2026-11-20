"""商品路由：一个资源一个文件。

文件内部的注册顺序遵循第 03 章的规则：精确路径（/latest）写在通配路径（/{item_id}）之前。
"""

from __future__ import annotations

from fastapi import APIRouter, Response, status

# 【作用】APIRouter 是「小号 FastAPI」，只管一组路由，不创建应用、不监听端口
# 【注意】prefix 不要以 `/` 结尾，否则会和子路径拼出 `//`
# 【注意】prefix 里的路径段必须写死，不能含 `{param}`——路径参数要写在各个接口上
router = APIRouter(prefix="/items", tags=["商品"])

# 【作用】进程内假数据，替代数据库（第 55 章才接真实库）
ITEMS: dict[int, str] = {1: "苹果", 2: "香蕉"}


@router.get("/latest", summary="最新商品")
def get_latest() -> dict[str, str]:
    """精确路径必须先注册，否则会被下面的 `/{item_id}` 吃掉。"""
    return {"latest": "苹果"}


@router.get("", summary="商品列表")
def list_items() -> list[dict[str, object]]:
    """注意这里是空字符串 `""`，不是 `"/"`。

    【为什么】router 的 prefix 已经是 `/items`：
             `""` → `/items`；`"/"` → `/items/`（多一个尾斜杠，会触发 307 重定向）。
    """
    return [{"id": k, "name": v} for k, v in ITEMS.items()]


@router.get("/{item_id}", summary="商品详情")
def get_item(item_id: int) -> dict[str, object]:
    return {"id": item_id, "name": ITEMS.get(item_id)}


@router.post("", status_code=status.HTTP_201_CREATED, summary="创建商品")
def create_item(name: str) -> dict[str, object]:
    new_id = max(ITEMS) + 1 if ITEMS else 1
    ITEMS[new_id] = name
    return {"id": new_id, "name": name}


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除商品")
def delete_item(item_id: int) -> Response:
    ITEMS.pop(item_id, None)
    return Response(status_code=status.HTTP_204_NO_CONTENT)
