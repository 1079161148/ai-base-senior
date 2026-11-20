"""第 19 章 · 模型复用。

核心：把「字段 + 约束」抽到类型别名与基类里，Create / Patch / Read 三个模型
      各自声明差异部分，约束只写一遍。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from datetime import datetime, timezone
from decimal import Decimal
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="第 19 章 · 模型复用", version="0.1.0")


# ============================================================
# 1. 类型别名：约束只写一遍，处处复用
# ============================================================
# 【作用】别名 = 类型 + 约束；不产生新类，也不走继承
# 【注意】别名是「同一个 FieldInfo」，改一处等于改所有使用点
Money = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
ShortText = Annotated[str, Field(min_length=1, max_length=32)]
Tags = Annotated[list[str], Field(max_length=5)]


# ============================================================
# 2. 严格基类：统一配置，子类自动继承
# ============================================================
class StrictModel(BaseModel):
    """所有业务模型的共同配置。

    【作用】子类不必重复写 `extra="forbid"`，`model_config` 会被继承并合并
    【注意】继承只复用「字段定义与配置」，父子仍是两个独立的模型类
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ============================================================
# 3. 三个模型各自声明差异
# ============================================================
class ProductBase(StrictModel):
    """商品核心字段（不含 id 与时间戳）。"""

    name: ShortText
    price: Money
    tags: Tags = []


class ProductCreate(ProductBase):
    """创建：核心字段全要，不加不减。

    【注意】`pass` 是正常的：复用的价值在「定义只写一遍」
    """


class ProductPatch(StrictModel):
    """局部更新：字段全可选。

    【注意】它**不继承** `ProductBase`——基类字段必填，而 PATCH 必须可省略。
           这正是「能复用别名、不能硬套继承」的典型场景。
    """

    name: ShortText | None = None
    price: Money | None = None
    tags: Tags | None = None


class ProductRead(ProductBase):
    """读取：核心字段 + 服务端生成字段。"""

    id: int
    created_at: datetime


# ============================================================
# 4. 内存存储与端点
# ============================================================
_PRODUCTS: dict[int, ProductRead] = {}
_NEXT_ID = 1


@app.post("/products", tags=["商品"], summary="创建商品")
def create_product(payload: ProductCreate) -> ProductRead:
    """【作用】用 `ProductRead` 组装响应，客户端直接拿到 id 与 created_at

    【注意】`**payload.model_dump()` 展开的是基类字段，子类自己不加字段也能构造
    """
    global _NEXT_ID
    # 【实测】price 传 "12.30" → Decimal('12.30')；响应里被序列化成字符串
    product = ProductRead(id=_NEXT_ID, created_at=datetime.now(timezone.utc), **payload.model_dump())
    _PRODUCTS[_NEXT_ID] = product
    _NEXT_ID += 1
    return product


@app.patch("/products/{product_id}", tags=["商品"], summary="局部更新")
def patch_product(product_id: int, patch: ProductPatch) -> dict[str, Any]:
    """【作用】复用 `StrictModel` 的配置：拼错字段名一样会 422"""
    if product_id not in _PRODUCTS:
        raise HTTPException(status_code=404, detail="商品不存在")

    updates = patch.model_dump(exclude_unset=True)
    current = _PRODUCTS[product_id].model_dump()
    current.update(updates)
    _PRODUCTS[product_id] = ProductRead(**current)
    return {"product": _PRODUCTS[product_id].model_dump(mode="json"), "updates": list(updates)}


@app.get("/products/{product_id}", tags=["商品"], summary="读取商品")
def get_product(product_id: int) -> ProductRead:
    if product_id not in _PRODUCTS:
        raise HTTPException(status_code=404, detail="商品不存在")
    return _PRODUCTS[product_id]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
