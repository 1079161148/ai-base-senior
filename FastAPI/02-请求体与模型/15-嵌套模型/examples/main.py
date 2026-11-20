"""第 15 章 · 嵌套模型。

核心：模型可以套模型、套列表；`loc` 会按嵌套层级变长，列表元素用**下标**定位。
      校验是逐层递归的，内层模型的配置（如 extra）不会从外层继承。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Annotated

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="第 15 章 · 嵌套模型", version="0.1.0")


# ============================================================
# 1. 三层结构：订单 → 客户 → 地址
# ============================================================
class Address(BaseModel):
    """最内层：地址。没有默认值 → 两个字段都必填。"""

    city: Annotated[str, Field(min_length=1, max_length=32)]
    street: Annotated[str, Field(min_length=1, max_length=128)]


class Customer(BaseModel):
    """中间层：模型字段的类型就是另一个模型。"""

    name: Annotated[str, Field(min_length=1, max_length=32)]
    # 【作用】字段类型是 Address → 请求体里必须给一个对象，否则 422
    # 【注意】嵌套深浅不影响用法：Pydantic 递归校验，直到叶子字段
    address: Address


class OrderItem(BaseModel):
    """列表元素模型。

    【注意】本章**故意不加** `extra="forbid"`：用来演示「内层配置不继承外层」——
           外层 Order 配了 forbid，但 OrderItem 里多传字段仍会被静默忽略。
    """

    sku: Annotated[str, Field(pattern=r"^[A-Z]-\d+$", examples=["A-1"])]
    qty: Annotated[int, Field(ge=1, le=999)]
    price: Annotated[float, Field(gt=0)]


class Order(BaseModel):
    """最外层：包含一个嵌套对象 + 一个模型列表。"""

    model_config = ConfigDict(extra="forbid")

    customer: Customer
    # 【作用】`list[Model]` 表示「数组，每个元素都要满足 Model」
    # 【注意】min_length/max_length 在这层限制的是**元素个数**
    items: Annotated[list[OrderItem], Field(min_length=1, max_length=5)]
    note: str | None = None


# ============================================================
# 2. 创建订单
# ============================================================
@app.post("/orders", tags=["订单"], summary="创建订单（三层嵌套 + 列表）")
def create_order(order: Order) -> dict[str, object]:
    """函数体拿到的嵌套结构已经全部是模型实例。

    【实测】合法请求 → items[0] 是 OrderItem 实例（不是 dict）
           `order.items[0].sku` 可属性访问；`order.model_dump()` 会递归转成 dict
    【实测】`items[0].price` 缺失 → 422 loc=["body","items",0,"price"]
           —— 列表元素用**整数下标**定位，前端可据此高亮第 0 行第 price 列
    """
    return {
        "dump": order.model_dump(),
        "first_item_type": type(order.items[0]).__name__,
        "item_count": len(order.items),
        "total": round(sum(item.price * item.qty for item in order.items), 2),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
