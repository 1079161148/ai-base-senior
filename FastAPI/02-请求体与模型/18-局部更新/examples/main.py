"""第 18 章 · 局部更新（PATCH）。

核心：PATCH 的模型要「所有字段都可选」，再用 `model_dump(exclude_unset=True)`
      只取出「请求里真的出现过」的字段，避免把没传的字段清空。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Annotated, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="第 18 章 · 局部更新", version="0.1.0")


# ============================================================
# 1. 内存存储：代替数据库，只为本机演示
# ============================================================
_PRODUCTS: dict[int, dict[str, Any]] = {
    1: {"id": 1, "name": "机械键盘", "price": 399.0, "tags": ["数码"], "note": "原装备注"},
    2: {"id": 2, "name": "无线鼠标", "price": 99.0, "tags": ["数码", "办公"], "note": None},
}


# ============================================================
# 2. 局部更新模型：每个字段都可选，默认 None
# ============================================================
class ProductPatch(BaseModel):
    """所有字段都可选 —— 这是 PATCH 模型与创建模型最大的区别。

    【注意】可选 ≠ 不校验：传了值就照样走 `min_length`/`gt` 等约束。
    【注意】`extra="forbid"` 让拼错的字段名立刻 422，而不是静默忽略。
    """

    model_config = ConfigDict(extra="forbid")

    name: Annotated[str | None, Field(min_length=2, max_length=20)] = None
    price: Annotated[float | None, Field(gt=0)] = None
    tags: Annotated[list[str] | None, Field(max_length=5)] = None
    note: Annotated[str | None, Field(max_length=100)] = None


# ============================================================
# 3. PATCH 端点
# ============================================================
@app.patch("/products/{product_id}", tags=["商品"], summary="只更新传来的字段")
def patch_product(product_id: int, patch: ProductPatch) -> dict[str, Any]:
    """局部更新。

    【作用】`exclude_unset=True` 只保留「请求体里出现过」的字段
    【为什么】不这样写，`{}` 会得到四个 None，把没传的字段全部清空
    【实测】`{"name": "新名字"}` → updates 里只有 name
           `{"note": null}`   → updates 里是 {"note": None}（显式置空，必须保留）
    【注意】想「忽略 null」用 `exclude_none=True`，语义完全不同，见 base.md
    """
    if product_id not in _PRODUCTS:
        # 【注意】HTTPException 由框架转成 404，不会变成 500
        raise HTTPException(status_code=404, detail=f"商品 {product_id} 不存在")

    # 【作用】只取被显式赋值过的字段，null 也算「赋值过」
    updates = patch.model_dump(exclude_unset=True)

    product = _PRODUCTS[product_id]
    product.update(updates)

    return {
        "product": product,
        # 【作用】`model_fields_set` 记录「本次请求出现过哪些字段」，便于审计
        "fields_set": sorted(patch.model_fields_set),
        "updates": updates,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
