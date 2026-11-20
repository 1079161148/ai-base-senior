"""第 22 章 · 状态码。

核心：默认 200 只是「没写」。创建用 201、删除用 204、异步受理用 202。
      三种改法：装饰器 `status_code=`、注入 `Response` 改 `status_code`、抛 `HTTPException`。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Any

from fastapi import FastAPI, HTTPException, Response, status
from pydantic import BaseModel

app = FastAPI(title="第 22 章 · 状态码", version="0.1.0")


class ItemIn(BaseModel):
    name: str


class ItemOut(BaseModel):
    id: int
    name: str


_ITEMS: dict[int, ItemOut] = {}
_NEXT_ID = 1


# ============================================================
# 1. 装饰器定状态码：创建 201
# ============================================================
@app.post(
    "/items",
    status_code=status.HTTP_201_CREATED,  # 【作用】等价于写 201，但常量可读性更好
    response_model=ItemOut,
    tags=["商品"],
    summary="创建（201）",
)
def create_item(item: ItemIn) -> ItemOut:
    """【实测】响应状态码 201，body 正常返回；OpenAPI 的 responses 里出现 201"""
    global _NEXT_ID
    created = ItemOut(id=_NEXT_ID, name=item.name)
    _ITEMS[_NEXT_ID] = created
    _NEXT_ID += 1
    return created


# ============================================================
# 2. 注入 Response：运行时改状态码
# ============================================================
@app.post(
    "/items/async",
    status_code=status.HTTP_201_CREATED,
    response_model=ItemOut,
    tags=["商品"],
    summary="受理后改 202",
)
def create_item_async(item: ItemIn, response: Response) -> ItemOut:
    """【作用】装饰器写 201，函数里改成 202

    【实测】以函数里的 `response.status_code` 为准（202）
    【注意】`Response` 参数不是返回值，只是「可写的响应对象」
    """
    response.status_code = status.HTTP_202_ACCEPTED
    return ItemOut(id=0, name=item.name)


# ============================================================
# 3. 204：删除成功，不能有 body
# ============================================================
@app.delete(
    "/items/{item_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    tags=["商品"],
    summary="删除（204）",
)
def delete_item(item_id: int) -> None:
    """【实测】204 + 空 body；OpenAPI 里该响应没有 content

    【注意】返回注解必须是 `None`（或 `response_class=Response`），
           否则 FastAPI 会尝试序列化 body
    """
    if item_id not in _ITEMS:
        raise HTTPException(status_code=404, detail="商品不存在")
    _ITEMS.pop(item_id)


# 【反例·实测】声明 204 却给返回注解 `dict`，导入期就 AssertionError：
#   AssertionError: Status code 204 must not have a response body
# 复现代码见 verify.py 的 check_204_with_body_rejected_at_import
# 结论：204 端点只能返回 None（或什么都不返回），FastAPI 帮你卡在定义期。


# ============================================================
# 4. 读取：200 与 404
# ============================================================
@app.get("/items/{item_id}", response_model=ItemOut, tags=["商品"], summary="读取")
def get_item(item_id: int) -> ItemOut:
    """【实测】`HTTPException(404)` 覆盖装饰器的默认 200"""
    if item_id not in _ITEMS:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="商品不存在")
    return _ITEMS[item_id]


# ============================================================
# 5. 自定义状态码
# ============================================================
@app.get("/custom-code", status_code=299, tags=["进阶"], summary="自定义 299")
def custom_code() -> dict[str, str]:
    """【实测】装饰器接受 100–599 之外的写法会失败；299 可以正常返回

    【注意】自定义码不会自动进 OpenAPI 的标准描述表，需要自己写 `responses=`
    """
    return {"code": "299"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
