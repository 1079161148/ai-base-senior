"""第 71 章 · TestClient 基础。

`TestClient` 直接走 ASGI 协议，不开端口、不走网络：

    client = TestClient(app)
    response = client.get("/items/1")
    assert response.status_code == 200

【要点】测试要覆盖**三层**：
        1. 成功路径（200/201 + body）
        2. 资源不存在（404 + detail）
        3. 参数非法（422 + detail[0].type / loc）

启动：uvicorn main:app --reload
验收：python verify.py        （不依赖 pytest）
或：  uv run pytest -q        （跑 tests/）
"""

from contextlib import asynccontextmanager
from typing import Annotated, Any, AsyncIterator

from fastapi import FastAPI, HTTPException, Query, Request, status
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import BaseModel, Field

ITEMS: dict[int, dict[str, Any]] = {1: {"id": 1, "name": "键盘", "price": 19900}}
STATE: dict[str, Any] = {"next_id": 2, "started": False}


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """【要点】只有 `with TestClient(app)` 或真实启动才会执行"""
    STATE["started"] = True
    app.state.started = True
    try:
        yield
    finally:
        STATE["started"] = False
        app.state.started = False


app = FastAPI(title="第 71 章 · TestClient 基础", version="0.1.0", lifespan=lifespan)


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    price: int = Field(ge=0, description="单位：分")


@app.get("/items", tags=["商品"], summary="商品列表")
def list_items(
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[dict[str, Any]]:
    return list(ITEMS.values())[:limit]


@app.post("/items", tags=["商品"], summary="新建商品", status_code=status.HTTP_201_CREATED)
def create_item(payload: ItemCreate) -> dict[str, Any]:
    item = {"id": STATE["next_id"], "name": payload.name, "price": payload.price}
    ITEMS[item["id"]] = item
    STATE["next_id"] += 1
    return item


@app.get("/items/{item_id}", tags=["商品"], summary="商品详情")
def read_item(item_id: int) -> dict[str, Any]:
    item = ITEMS.get(item_id)
    if item is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="item not found")
    return item


@app.get("/redirect", tags=["演示"], summary="307 跳转到列表")
def redirect_to_list() -> RedirectResponse:
    return RedirectResponse("/items", status_code=status.HTTP_307_TEMPORARY_REDIRECT)


@app.get("/cookie/set", tags=["演示"], summary="种 cookie", response_model=None)
def set_cookie() -> JSONResponse:
    response = JSONResponse({"ok": "true"})
    response.set_cookie("session", "abc123")
    return response


@app.get("/cookie/read", tags=["演示"], summary="读 cookie")
def read_cookie(request: Request) -> dict[str, str]:
    return {"session": request.cookies.get("session", "missing")}


@app.get("/boom", tags=["演示"], summary="故意抛异常")
def boom() -> dict[str, str]:
    raise RuntimeError("故意炸了")


@app.get("/state", tags=["演示"], summary="读 lifespan 状态")
def read_state() -> dict[str, bool]:
    return {"started": bool(STATE["started"])}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)