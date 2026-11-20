"""第 30 章 · jsonable_encoder。

核心：把「Python 对象」转成「只含 JSON 原生类型（dict/list/str/int/float/bool/None）」的结构。
      FastAPI 在返回前本来就会调它；需要自己先转（写缓存、写日志、塞进另一个结构）时才手动用。
      有响应模型时优先用 `model_dump(mode="json")`，别绕一层 encoder。

启动：uvicorn main:app --reload
验收：python verify.py
"""

import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from types import SimpleNamespace
from typing import Annotated, Any

from fastapi import FastAPI, Path as PathParam
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

app = FastAPI(title="第 30 章 · jsonable_encoder", version="0.1.0")


class Status(str, Enum):
    """字符串枚举：JSON 化后是它的值。"""

    ACTIVE = "active"
    DISABLED = "disabled"


class Order(BaseModel):
    id: int
    amount: Decimal
    created_at: datetime
    status: Status


_NOW = datetime(2026, 11, 17, 12, 0, 0, tzinfo=timezone.utc)


# ============================================================
# 1. 基础：各种类型怎么变
# ============================================================
@app.get("/encode/basic", tags=["编码"], summary="基础类型转换")
def encode_basic() -> dict[str, Any]:
    """【作用】`jsonable_encoder` 递归转换，输出只含 JSON 原生类型

    【实测】datetime→ISO 字符串、Decimal→字符串、set→list、UUID→str、
           Enum→值、Path→字符串、bytes→解码后的字符串
    """
    encoded = jsonable_encoder(
        {
            "dt": _NOW,
            "day": date(2026, 11, 17),
            "amount": Decimal("399.90"),
            "tags": {"b", "a"},
            "id": uuid.UUID("12345678-1234-5678-1234-567812345678"),
            "status": Status.ACTIVE,
            "path": Path("var/uploads/a.txt"),
            "raw": b"hello",
        }
    )
    return {"encoded": encoded, "types": {key: type(value).__name__ for key, value in encoded.items()}}


# ============================================================
# 2. Pydantic 模型与 ORM 风格对象
# ============================================================
@app.get("/encode/model", tags=["编码"], summary="模型对象转 dict")
def encode_model() -> dict[str, Any]:
    """【实测】模型实例 → dict；`Decimal` 变字符串、`datetime` 变 ISO 串

    【注意】`jsonable_encoder` 会调用模型的 `model_dump()`，不是简单 `__dict__`
    """
    order = Order(id=1, amount=Decimal("99.50"), created_at=_NOW, status=Status.DISABLED)
    return jsonable_encoder(order)


@app.get("/encode/object", tags=["编码"], summary="任意对象转 dict")
def encode_object() -> dict[str, Any]:
    """【作用】非 Pydantic 对象（如 ORM 行）走 `vars(obj)` / `__dict__`

    【实测】`SimpleNamespace` 与带 `__dict__` 的普通类都能被转成 dict
    【注意】只转实例属性，属性和方法不会被调用（不会触发懒加载之外的逻辑）
    """
    row = SimpleNamespace(id=7, name="机械键盘", price=Decimal("399.00"))
    return jsonable_encoder(row)


# ============================================================
# 3. include / exclude / by_alias
# ============================================================
class UserOut(BaseModel):
    id: int
    username: str
    email: str
    password: str


_USER = UserOut(id=1, username="alice", email="a@example.com", password="should-not-leak")


@app.get("/encode/filter", tags=["编码"], summary="字段裁剪")
def encode_filter() -> dict[str, Any]:
    """【作用】`include`/`exclude` 与响应模型参数同名同义

    【注意】用编码器裁字段只是「临时遮一下」，真正防泄露靠出参模型（第 21 章）
    """
    return {
        "excluded": jsonable_encoder(_USER, exclude={"password"}),
        "included": jsonable_encoder(_USER, include={"id", "username"}),
        "by_alias": jsonable_encoder(_USER, exclude={"password"}, by_alias=True),
    }


# ============================================================
# 4. 自定义编码器
# ============================================================
@app.get("/encode/custom", tags=["编码"], summary="custom_encoder")
def encode_custom() -> dict[str, Any]:
    """【作用】`custom_encoder` 可以覆盖某类型的默认转换

    【实测】把 `datetime` 转成 Unix 时间戳（int）；其余类型仍走默认逻辑
    【注意】`custom_encoder` 只作用于精确类型，子类不会自动命中
    """
    payload = {"created_at": _NOW, "amount": Decimal("1.5")}
    encoded = jsonable_encoder(
        payload,
        custom_encoder={datetime: lambda value: int(value.timestamp())},
    )
    return {"encoded": encoded, "types": {key: type(value).__name__ for key, value in encoded.items()}}


# ============================================================
# 5. 与 model_dump(mode="json") 对比
# ============================================================
@app.get("/encode/compare", tags=["编码"], summary="与 model_dump 对比")
def encode_compare() -> dict[str, Any]:
    """【实测】两条路对 `Decimal` 都输出字符串，但类型标注与扩展能力不同

    【建议】有响应模型时用 `model_dump(mode="json")`（Pydantic 原生、可配 `serializers`）；
           需要转「任意混合结构」时才用 `jsonable_encoder`
    """
    order = Order(id=1, amount=Decimal("12.30"), created_at=_NOW, status=Status.ACTIVE)
    via_encoder = jsonable_encoder(order)
    via_dump = order.model_dump(mode="json")
    return {
        "via_encoder": via_encoder,
        "via_dump": via_dump,
        "same": via_encoder == via_dump,
    }


# ============================================================
# 6. 路径参数里的枚举：FastAPI 自动编码
# ============================================================
@app.get("/orders/{status}", tags=["编码"], summary="路径枚举自动转换")
def orders_by_status(
    status: Annotated[Status, PathParam(description="订单状态")],
) -> dict[str, str]:
    """【作用】路径里的 `"active"` 会被转成 `Status.ACTIVE`

    【实测】返回时枚举又被编码回 `"active"`，不需要手动调 encoder
    """
    return {"status": status.value, "enum_name": status.name}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)