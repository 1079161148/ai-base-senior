"""第 09 章 · 查询参数模型。

核心：用一个 Pydantic 模型装下所有查询参数，标 `Annotated[Model, Query()]` 后逐字段展开。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

app = FastAPI(title="第 09 章 · 查询参数模型", version="0.1.0")


# ============================================================
# 1. 扁平模型：所有字段都是标量或标量数组
# ============================================================
class ArticleFilter(BaseModel):
    """文章列表的过滤条件。

    【注意】字段只能是「能从查询串里解析出来的」类型：
           标量（str/int/bool/datetime）、标量数组（list[str]）、可空标量。
    【注意】不要放嵌套模型或 dict——查询串没有嵌套的表示法（见第 4 节实测）。
    """

    q: str | None = Field(default=None, min_length=1, max_length=50, description="搜索词")
    tag: list[str] = Field(default=[], description="标签，可重复传")
    # 【作用】Field 的约束与 Path/Query 完全同源，都会进 OpenAPI
    limit: int = Field(default=20, ge=1, le=100, description="每页条数，1–100")
    offset: int = Field(default=0, ge=0, description="偏移量")
    # 【作用】alias 让查询键用连字符，Python 侧保持下划线
    order_by: str = Field(default="created", alias="order-by", pattern="^(created|views)$")


@app.get("/articles", tags=["文章"], summary="文章列表（模型版）")
def list_articles(
    # 【关键】必须写 Query()。不写的话 FastAPI 会认为这是**请求体**，
    #        GET 请求不会带 body，于是所有字段都取默认值（或报 422）。
    filters: Annotated[ArticleFilter, Query()],
) -> dict[str, object]:
    """8 个参数收敛成一个模型。

    【作用】OpenAPI 里会被展开成 5 个独立 query 参数，**不会**出现 `$ref`。
    【实测】`?limit=0` → 422 `greater_than_equal`，`loc=["query","limit"]`
    【注意】`order-by` 是别名；传 `?order_by=views` 会静默用默认值 `created`。
    """
    return filters.model_dump()


# ============================================================
# 2. 模型 + 模型外的额外参数（不推荐，但可行）
# ============================================================
class PageFilter(BaseModel):
    limit: int = Field(default=10, ge=1, le=50)
    offset: int = Field(default=0, ge=0)


@app.get("/users", tags=["用户"], summary="模型 + 独立参数混用")
def list_users(
    filters: Annotated[PageFilter, Query()],
    # 【注意】模型之外的参数仍然可以单独声明，但会把参数布局拆成两处，
    #        不利于维护。参数多时建议全部放进同一个模型。
    keyword: Annotated[str | None, Query(max_length=30)] = None,
) -> dict[str, object]:
    return {**filters.model_dump(), "keyword": keyword}


# ============================================================
# 3. 反例：嵌套模型（实测不可用）
# ============================================================
class Range(BaseModel):
    min_price: int = 0
    max_price: int = 100


class WrongFilter(BaseModel):
    # 【注意】这一行在**启动时不会报错**，但请求时会 422：
    #   {"type": "model_attributes_type", "loc": ["query", "range"], ...}
    # OpenAPI 里会出现一个指向 Range 的 $ref，前端生成的客户端无法正确拼查询串。
    range: Range = Field(default_factory=Range)
    limit: int = 10


@app.get("/wrong", tags=["反例"], summary="嵌套模型（错误示范）", include_in_schema=False)
def wrong_nested(filters: Annotated[WrongFilter, Query()]) -> dict[str, object]:
    """放在这里是为了让 verify.py 能实测「嵌套不可用」。

    【为什么不可用】查询串是 `key=value` 的扁平结构，没有表达嵌套的标准语法。
                   要传区间就用 `min_price` / `max_price` 两个平铺字段。
    """
    return filters.model_dump()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
