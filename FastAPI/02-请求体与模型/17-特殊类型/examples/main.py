"""第 17 章 · 特殊类型。

核心：UUID / Decimal / datetime / date / HttpUrl / Enum / Literal
      在 JSON 里都是字符串（或数字），FastAPI + Pydantic 负责转换与校验；
      响应侧 Decimal 会被编码成 JSON 数字，要保精度必须自己序列化成字符串。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated, Literal
from uuid import UUID

from fastapi import FastAPI
from pydantic import BaseModel, Field, HttpUrl

app = FastAPI(title="第 17 章 · 特殊类型", version="0.1.0")


# ============================================================
# 1. 枚举：限定取值，且进文档
# ============================================================
class Channel(str, Enum):
    """继承 `str` 的枚举：JSON 里就是字符串，前端不用处理额外结构。

    【作用】非法值 → 422 `enum`，`ctx.expected` 直接列出可选值
    【注意】成员名与值可以不同；对外契约是**值**（`web`/`app`），不是成员名
    """

    web = "web"
    app = "app"


# ============================================================
# 2. 一份用满特殊类型的模型
# ============================================================
class PaymentCreate(BaseModel):
    # 【作用】UUID：接受标准 36 位字符串，转成 uuid.UUID 对象
    # 【注意】非法字符串 → 422 uuid_parsing，不是 500
    order_id: UUID

    # 【作用】Decimal：金额唯一正确类型（float 有二进制精度误差）
    # 【注意】max_digits = 总位数（不含小数点与符号），decimal_places = 小数位
    #        超限分别报 decimal_max_digits / decimal_max_places
    amount: Annotated[Decimal, Field(gt=0, max_digits=8, decimal_places=2)]

    # 【作用】datetime：接受 ISO 8601；不带时区就是 naive datetime
    # 【注意】跨时区业务必须显式带偏移（如 2026-01-02T03:04:05+08:00）
    created_at: datetime

    # 【作用】date：只到天；也接受完整 datetime 字符串（会取日期部分）
    ship_date: date | None = None

    # 【作用】HttpUrl：校验 scheme + host，转成 pydantic 的 Url 对象
    # 【注意】它是 Pydantic 内置类型，**不需要** email-validator 之类额外依赖
    callback: HttpUrl | None = None

    # 【作用】枚举：默认值也可以直接给枚举成员
    channel: Channel = Channel.web

    # 【作用】Literal：比 Enum 更轻的「取值白名单」，不进 components
    kind: Literal["retail", "wholesale"] = "retail"


# ============================================================
# 3. 创建支付单
# ============================================================
@app.post("/payments", tags=["支付"], summary="特殊类型全家桶")
def create_payment(payment: PaymentCreate) -> dict[str, object]:
    """演示「内部类型」与「线上 JSON」的差异。

    【实测】amount 传 "19.99"：
           - 内部是 Decimal("19.99")，`str()` 得到 "19.99"
           - `model_dump(mode="json")` 得到字符串 "19.99"（精确保留）
           - 本接口有返回注解 `-> dict[str, object]`，FastAPI 会用它构造响应模型，
             由 Pydantic 序列化 → Decimal 输出为**字符串** "19.99"
    【关键差异】如果**不写返回注解**，FastAPI 走 jsonable_encoder → Decimal 输出为
           JSON **数字** 19.99（可能丢精度）。两种路径实测不同，金额对外建议统一用字符串。
    """
    return {
        # 【作用】python 模式：Decimal 仍是 Decimal，datetime 仍是 datetime
        "dump_python": payment.model_dump(),
        # 【作用】json 模式：全部转成 JSON 可表达的类型，Decimal → str，UUID → str
        "dump_json": payment.model_dump(mode="json"),
        "types": {
            "order_id": type(payment.order_id).__name__,
            "amount": type(payment.amount).__name__,
            "created_at": type(payment.created_at).__name__,
            "callback": type(payment.callback).__name__,
            "channel": type(payment.channel).__name__,
        },
        "amount_exact": str(payment.amount),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
