"""第 69 章 · OpenAPI 定制。

文档是**给前端的契约**，不是附属品。能定制的东西分三层：

    1. 应用级   title / description / version / contact / license / servers
    2. 分组级   openapi_tags
    3. 端点级   summary / description / responses / deprecated / include_in_schema

还能整体接管 `app.openapi()`，注入 `x-` 扩展或改写 schema。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Any

from fastapi import FastAPI, HTTPException, status
from fastapi.openapi.utils import get_openapi
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

TAGS_METADATA = [
    {
        "name": "items",
        "description": "商品读写。**所有金额单位为分**。",
        "externalDocs": {"description": "商品字段说明", "url": "https://example.com/items"},
    },
    {
        "name": "internal",
        "description": "内部接口，不对第三方开放。",
    },
]

app = FastAPI(
    title="订单服务",
    description="""
## 概览

提供订单与商品的读写接口。

### 约定

- 金额单位：**分**
- 时间格式：ISO 8601
- 错误体：`{"detail": "..."}`

> 本文档由 `openapi()` 自动生成，请勿手工编辑。
""",
    version="1.2.3",
    terms_of_service="https://example.com/tos",
    contact={"name": "API 团队", "email": "api@example.com", "url": "https://example.com"},
    license_info={"name": "MIT", "url": "https://opensource.org/licenses/MIT"},
    openapi_tags=TAGS_METADATA,
    servers=[
        {"url": "https://api.example.com", "description": "生产"},
        {"url": "https://staging-api.example.com", "description": "预发"},
    ],
)


class Item(BaseModel):
    id: int
    name: str = Field(min_length=1, max_length=50)
    price: int = Field(ge=0, description="单位：分")


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50, examples=["键盘"])
    price: int = Field(ge=0, description="单位：分", examples=[19900])


ITEMS: dict[int, Item] = {1: Item(id=1, name="键盘", price=19900)}


@app.get("/items", tags=["items"], summary="商品列表", response_model=list[Item])
def list_items() -> list[Item]:
    """返回全部商品。

    - 不分页（内部使用，量小）
    - 按 `id` 升序
    """
    return list(ITEMS.values())


@app.post(
    "/items",
    tags=["items"],
    status_code=status.HTTP_201_CREATED,
    summary="新建商品",
    response_model=Item,
    responses={409: {"description": "同名商品已存在"}},
)
def create_item(payload: ItemCreate) -> Item:
    if any(item.name == payload.name for item in ITEMS.values()):
        raise HTTPException(status_code=409, detail="同名商品已存在")
    new_id = max(ITEMS, default=0) + 1
    item = Item(id=new_id, name=payload.name, price=payload.price)
    ITEMS[new_id] = item
    return item


@app.get(
    "/items/{item_id}",
    tags=["items"],
    summary="商品详情",
    response_model=Item,
    responses={404: {"description": "商品不存在"}},
)
def get_item(item_id: int) -> Item:
    item = ITEMS.get(item_id)
    if item is None:
        raise HTTPException(status_code=404, detail="商品不存在")
    return item


@app.get(
    "/internal/debug",
    tags=["internal"],
    summary="内部调试",
    include_in_schema=False,
)
def debug() -> dict[str, int]:
    """【要点】不进文档，但路径仍可访问"""
    return {"items": len(ITEMS)}


@app.get(
    "/items/legacy",
    tags=["items"],
    summary="旧版列表",
    deprecated=True,
)
def legacy() -> dict[str, str]:
    """【要点】文档标记废弃，仍可调用"""
    return {"status": "deprecated, use /items"}


# ============================================================
# 整体接管 openapi()
# ============================================================
def custom_openapi() -> dict[str, Any]:
    """【要点】第一次生成后缓存，避免每次请求都重新遍历路由"""
    if app.openapi_schema:
        return app.openapi_schema

    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=TAGS_METADATA,
        servers=app.servers,
        # 【要点】`get_openapi()` **不会**自动从 app 上读这三项，必须显式传
        terms_of_service=app.terms_of_service,
        contact=app.contact,
        license_info=app.license_info,
    )
    # 【要点】`x-` 前缀是 OpenAPI 规范允许的扩展位，工具链会保留
    schema["x-owner"] = "team-order"
    schema["x-api-tier"] = "internal"
    schema["info"]["x-audience"] = "frontend-contract"
    schema["info"]["x-generated-by"] = "fastapi"
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi  # type: ignore[method-assign]


@app.get("/openapi/export", include_in_schema=False)
def export_schema() -> JSONResponse:
    """【作用】导出给前端做代码生成，内容与 `/openapi.json` 完全一致"""
    return JSONResponse(app.openapi())


# ============================================================
# 关闭文档的两种方式
# ============================================================
no_docs_app = FastAPI(docs_url=None, redoc_url=None, title="只留 schema")


@no_docs_app.get("/x")
def x() -> dict[str, str]:
    return {"ok": "true"}


no_openapi_app = FastAPI(openapi_url=None, title="完全关闭")


@no_openapi_app.get("/x")
def x2() -> dict[str, str]:
    return {"ok": "true"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)