"""第 16 章 · 多参数与 embed。

核心：路径/查询/头与 body 可以同时出现，互不干扰；
      但**多个 body 参数**会被 FastAPI 自动包装成 {"参数名": 值}，
      单个 body 参数则直接收裸对象；`Body(embed=True)` 可以强制单参数也包装。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Annotated

from fastapi import Body, FastAPI, Header, Path, Query
from pydantic import BaseModel, Field

app = FastAPI(title="第 16 章 · 多参数与 embed", version="0.1.0")


class OrderItemIn(BaseModel):
    sku: Annotated[str, Field(pattern=r"^[A-Z]-\d+$")]
    qty: Annotated[int, Field(ge=1, le=999)]


class Address(BaseModel):
    city: str
    street: str


# ============================================================
# 1. 路径 + 查询 + 头 + 单个 body：body 收裸对象
# ============================================================
@app.post("/orders/{order_id}/items", tags=["订单"], summary="四类位置混用（单 body）")
def add_item(
    # 【作用】路径参数：参与 URL 匹配
    order_id: Annotated[int, Path(ge=1, description="订单 ID")],
    # 【作用】唯一的 body 参数 → 请求体就是 OrderItemIn 本身，不包装
    item: OrderItemIn,
    # 【作用】查询参数：控制行为，不影响资源定位
    notify: Annotated[bool, Query(description="是否通知客户")] = False,
    # 【作用】请求头：调用方追踪信息
    x_trace_id: Annotated[str | None, Header()] = None,
) -> dict[str, object]:
    """【实测】POST /orders/9/items?notify=true  body={"sku":"A-1","qty":2}

    返回 order_id=9、notify=True、item 已校验。
    【注意】body 出错时 `loc` 是 `["body","sku"]`——路径/查询/头的错误会**分开**出现在同一个 422 里。
    """
    return {
        "order_id": order_id,
        "item": item.model_dump(),
        "notify": notify,
        "trace_id": x_trace_id,
    }


# ============================================================
# 2. 两个 body 参数：必须包装
# ============================================================
@app.post("/shipments", tags=["物流"], summary="两个 body 参数（自动包装）")
def create_shipment(item: OrderItemIn, address: Address) -> dict[str, object]:
    """两个模型参数 → 请求体必须写成 `{"item": {...}, "address": {...}}`。

    【实测】直接发 `{"sku":"A-1","qty":2,"city":"北京","street":"x"}` →
           422，两条 missing：loc=["body","item"] 与 ["body","address"]
    【为什么】JSON 顶层只能有一个值；FastAPI 用「参数名做键」的方式把多个 body 合成一个对象，
           并在 OpenAPI 里生成一个叫 `Body_create_shipment_shipments_post` 的组件。
    【注意】键名就是**函数参数名**，改参数名等于改接口契约。
    """
    return {"item": item.model_dump(), "address": address.model_dump()}


# ============================================================
# 3. 单个 body 参数 + embed=True：强制包装
# ============================================================
@app.post("/coupons", tags=["优惠券"], summary="embed 强制包装单个 body")
def create_coupon(
    coupon: Annotated[Address, Body(embed=True, description="券的适用范围")],
) -> dict[str, object]:
    """`embed=True` 让单个 body 参数也必须包一层 `{"coupon": {...}}`。

    【实测】直接发 `{"city":"北京","street":"x"}` → 422 missing loc=["body","coupon"]
    【什么时候用】接口未来可能加第二个 body 参数时，先用 embed 定好包装形状，
           避免上线后从「裸对象」改成「包装对象」造成破坏性变更。
    """
    return {"coupon": coupon.model_dump()}


# ============================================================
# 4. 标量 body：也必须包装
# ============================================================
@app.post("/tokens/verify", tags=["令牌"], summary="标量 body + 模型 body")
def verify_token(
    token: Annotated[str, Body(description="待校验的令牌")],
    item: OrderItemIn,
) -> dict[str, object]:
    """`Body()` 标注的标量参数也是一个 body 参数，同样参与包装。

    【实测】请求体必须是 `{"token": "abc", "item": {"sku": "A-1", "qty": 1}}`
    【注意】标量 body 没有 embed 参数也**必须**包装——因为这里已经有两个 body 参数了。
    """
    return {"token_length": len(token), "item": item.model_dump()}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
