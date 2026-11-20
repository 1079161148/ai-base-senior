"""第 23 章 · 联合类型响应。

核心：一个端点返回两种以上结构时，用 `A | B` 声明响应模型（OpenAPI 生成 anyOf），
      并按 `responses=` 给不同状态码挂不同模型；直接返回 `Response` 会绕过响应模型。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI(title="第 23 章 · 联合类型响应", version="0.1.0")


class ItemOut(BaseModel):
    id: int
    name: str


class SuccessOut(BaseModel):
    ok: bool = True
    data: ItemOut


class ErrorOut(BaseModel):
    ok: bool = False
    message: str


_ITEM = ItemOut(id=1, name="机械键盘")


# ============================================================
# 1. 联合类型响应模型
# ============================================================
@app.get(
    "/result/{kind}",
    response_model=SuccessOut | ErrorOut,
    tags=["联合"],
    summary="成功或失败二选一",
)
def get_result(kind: str) -> SuccessOut | ErrorOut:
    """【作用】`response_model=SuccessOut | ErrorOut` → OpenAPI 里生成 `anyOf`

    【实测】返回 `SuccessOut` 实例时按 A 校验，返回 `ErrorOut` 时按 B 校验
    【注意】联合顺序会影响「dict 输入」的匹配结果（见 3.2）
    """
    if kind == "success":
        return SuccessOut(data=_ITEM)
    return ErrorOut(message="查无此项")


# ============================================================
# 2. 不同状态码挂不同模型
# ============================================================
@app.get(
    "/item-or-error/{item_id}",
    response_model=ItemOut,
    responses={
        404: {"model": ErrorOut, "description": "商品不存在"},
        422: {"description": "参数错误"},
    },
    tags=["联合"],
    summary="200 一种模型，404 另一种",
)
def get_item_or_error(item_id: int) -> Any:
    """【作用】成功走 `response_model`，失败状态码的文档用 `responses=` 单独声明

    【实测】OpenAPI 里 200 是 ItemOut、404 是 ErrorOut，两个组件都出现
    【注意】`responses=` 只是**文档**，真正返回什么由你代码决定
    """
    if item_id == _ITEM.id:
        return _ITEM
    return JSONResponse(status_code=404, content={"ok": False, "message": "商品不存在"})


# ============================================================
# 3. 直接返回 Response：绕过响应模型
# ============================================================
@app.get("/raw", tags=["绕过"], summary="直接返回 JSONResponse")
def raw() -> Any:
    """【实测】函数返回 `JSONResponse` 时，响应模型被**完全跳过**：

    - 不做校验（返回非法结构也不会 500）
    - 不做字段过滤（多余字段原样输出）
    【为什么】FastAPI 看到返回值是 `Response` 子类就直接发送
    【注意】签名别声明 `response_model`，否则文档与实际不符
    """
    return JSONResponse({"id": 1, "name": "x", "secret": "不该出现", "count": "不是数字"})


# ============================================================
# 4. 联合顺序影响 dict 匹配
# ============================================================
class A(BaseModel):
    ok: bool
    name: str


class B(BaseModel):
    ok: bool
    message: str


@app.get("/order-ab", response_model=A | B, tags=["联合"], summary="A 在前")
def order_ab() -> Any:
    """【实测】返回的 dict 同时缺 `name` 与 `message` 时：
           `A | B` 两者都不匹配 → 500
           返回 `{"ok": true, "name": "x"}` → 匹配 A
    """
    return {"ok": True, "name": "x"}


@app.get("/order-ba", response_model=B | A, tags=["联合"], summary="B 在前")
def order_ba() -> Any:
    """【实测】同样的 dict，顺序换过来仍按「谁匹配」选，不会因为顺序而乱配"""
    return {"ok": True, "message": "y"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
