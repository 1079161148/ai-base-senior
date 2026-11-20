"""第 26 章 · OpenAPI 文档定制。

核心：文档是**对外契约**。应用级元信息、标签分组、字段说明、响应描述、废弃标记、
      自定义 schema 都要显式写；`/docs` 与 SDK 生成器读的是同一份 `/openapi.json`。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from decimal import Decimal
from typing import Annotated, Any

from fastapi import FastAPI, Query
from pydantic import BaseModel, ConfigDict, Field

# ============================================================
# 1. 应用级元信息（出现在 info 节点）
# ============================================================
app = FastAPI(
    title="商品服务 API",
    description="演示 OpenAPI 定制的示例服务。**文档即契约**，改字段等于改对外接口。",
    version="1.2.3",
    contact={"name": "API 支持", "url": "https://example.com/support"},
    license_info={"name": "MIT"},
    openapi_tags=[
        {"name": "商品", "description": "商品的增删改查"},
        {"name": "运维", "description": "探活与元信息"},
        {"name": "内部", "description": "不对外公开的接口（此处演示隐藏）"},
    ],
    summary="一句话概述服务",
)


# ============================================================
# 2. 模型与字段说明
# ============================================================
class ItemIn(BaseModel):
    """创建商品的入参。"""

    name: Annotated[str, Field(min_length=2, max_length=20, description="商品名称", examples=["机械键盘"])]
    price: Annotated[Decimal, Field(gt=0, decimal_places=2, description="单价（元）", examples=["399.00"])]


class ItemOut(BaseModel):
    """商品的对外结构。

    【作用】`json_schema_extra` 可以给整个对象挂示例，`/docs` 会直接展示
    """

    model_config = ConfigDict(
        json_schema_extra={"examples": [{"id": 1, "name": "机械键盘", "price": "399.00"}]}
    )

    id: int = Field(description="商品 ID")
    name: str = Field(description="商品名称")
    price: Decimal = Field(description="单价（元，字符串传输）")


_ITEMS: dict[int, ItemOut] = {1: ItemOut(id=1, name="机械键盘", price=Decimal("399.00"))}


# ============================================================
# 3. 端点级文档
# ============================================================
@app.post(
    "/items",
    response_model=ItemOut,
    status_code=201,
    tags=["商品"],
    summary="创建商品（短标题）",
    description="长描述支持 **Markdown**，会显示在 `/docs` 展开区。",
    response_description="创建成功的商品",
    responses={
        409: {"description": "同名商品已存在"},
        422: {"description": "参数校验失败"},
    },
)
def create_item(item: ItemIn) -> ItemOut:
    new_id = max(_ITEMS) + 1
    created = ItemOut(id=new_id, name=item.name, price=item.price)
    _ITEMS[new_id] = created
    return created


@app.get(
    "/items",
    response_model=list[ItemOut],
    tags=["商品"],
    summary="商品列表",
    description="按名称过滤；`keyword` 的描述来自 `Query(description=...)`。",
)
def list_items(
    keyword: Annotated[str | None, Query(min_length=1, description="名称关键字", examples=["键盘"])] = None,
) -> Any:
    rows = list(_ITEMS.values())
    if keyword:
        rows = [item for item in rows if keyword in item.name]
    return rows


@app.get(
    "/items/{item_id}",
    response_model=ItemOut,
    tags=["商品"],
    summary="旧版详情（已废弃）",
    deprecated=True,
)
def get_item_old(item_id: int) -> ItemOut:
    """【作用】`deprecated=True` 会在 `/docs` 上划横线，并在 OpenAPI 里标记

    【注意】它不会阻止调用，只是文档信号；真正下线要改状态码/加响应头
    """
    return _ITEMS[item_id]


@app.get(
    "/v2/items/{item_id}",
    response_model=ItemOut,
    tags=["商品"],
    summary="新版详情",
    openapi_extra={"x-internal-owner": "team-goods"},
)
def get_item_v2(item_id: int) -> ItemOut:
    """【作用】`openapi_extra` 会原样合并进该 operation 对象

    【实测】`x-internal-owner` 出现在 `paths./v2/items/{item_id}.get` 下
    【用途】给网关注入扩展字段、标注负责人、挂 vendor extension
    """
    return _ITEMS[item_id]


@app.get("/health", tags=["运维"], summary="探活")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/internal/metrics", tags=["内部"], include_in_schema=False)
def metrics() -> dict[str, int]:
    """【作用】`include_in_schema=False`：能调用，但不出现在 `/openapi.json`

    【实测】`/internal/metrics` 不在 schema 的 paths 里
    """
    return {"items": len(_ITEMS)}


# ============================================================
# 4. 完全自定义 schema
# ============================================================
# 【关键】先保存原始方法，否则 `app.openapi()` 会调到 custom_openapi 自己 → 无限递归
_base_openapi = app.openapi


def custom_openapi() -> dict[str, Any]:
    """【作用】缓存并改写 schema：加服务器列表、统一安全方案等

    【注意】必须缓存到 `app.openapi_schema`，否则每次请求都重建
    【实测】不保存原始方法就替换 `app.openapi` → `RecursionError: maximum recursion depth exceeded`
    """
    if app.openapi_schema:
        return app.openapi_schema
    schema = _base_openapi()
    schema["servers"] = [{"url": "https://api.example.com", "description": "生产环境"}]
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi  # type: ignore[method-assign]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
