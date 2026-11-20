"""第 42 章 · 实战：分页依赖（PageParams + Page[T]）。

核心：用一个依赖统一所有列表接口的分页参数，用泛型模型统一响应结构
      `{items, total, page, size, pages}`。客户端与前端只需要写一套解析，
      OpenAPI 里会出现 `Page_ItemOut_` 这样的具体泛型。

启动：uvicorn main:app --reload
验收：python verify.py
"""

import math
from typing import Annotated, Any, Generic, TypeVar

from fastapi import Depends, FastAPI, Query
from pydantic import BaseModel, Field

app = FastAPI(title="第 42 章 · 分页依赖实战", version="0.1.0")

T = TypeVar("T")

_ITEMS: list[dict[str, Any]] = [
    {"id": i, "name": f"商品 {i}", "price": i * 100} for i in range(1, 24)
]
_USERS: list[dict[str, Any]] = [{"id": i, "name": f"user{i}"} for i in range(1, 8)]


# ============================================================
# 1. 分页参数依赖
# ============================================================
class PageParams:
    """【作用】所有列表接口共用；越界不报错，返回空 items（客户端友好）

    【注意】`size` 上限 50，防止一次拉全表
    """

    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="页码，从 1 开始")] = 1,
        size: Annotated[int, Query(ge=1, le=50, description="每页条数")] = 5,
    ) -> None:
        self.page = page
        self.size = size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


# ============================================================
# 2. 泛型响应模型
# ============================================================
class Page(BaseModel, Generic[T]):
    """【实测】OpenAPI 里生成 `Page_ItemOut_` / `Page_UserOut_` 两个 schema"""

    items: list[T]
    total: int = Field(description="总条数")
    page: int
    size: int
    pages: int = Field(description="总页数，0 表示没有数据")


class ItemOut(BaseModel):
    id: int
    name: str
    price: int


class UserOut(BaseModel):
    id: int
    name: str


# ============================================================
# 3. 组装分页结果
# ============================================================
def paginate(rows: list[dict[str, Any]], params: PageParams) -> dict[str, Any]:
    """【作用】切片 + 统计；total 必须来自「全量」而不是当前页"""
    total = len(rows)
    start = params.offset
    return {
        "items": rows[start : start + params.size],
        "total": total,
        "page": params.page,
        "size": params.size,
        "pages": math.ceil(total / params.size) if total else 0,
    }


# ============================================================
# 4. 两个端点复用同一套分页
# ============================================================
@app.get("/items", response_model=Page[ItemOut], tags=["分页"], summary="商品分页")
def list_items(params: Annotated[PageParams, Depends()]) -> Any:
    """【实测】`?page=2&size=5` → items 是 6..10，total=23，pages=5"""
    return paginate(_ITEMS, params)


@app.get("/users", response_model=Page[UserOut], tags=["分页"], summary="用户分页")
def list_users(params: Annotated[PageParams, Depends()]) -> Any:
    """【实测】同一依赖、另一个泛型：schema 为 `Page_UserOut_`"""
    return paginate(_USERS, params)


@app.get("/items/empty", response_model=Page[ItemOut], tags=["分页"], summary="空结果集")
def empty_page(params: Annotated[PageParams, Depends()]) -> Any:
    """【实测】total=0 → pages=0，items=[]"""
    return paginate([], params)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)