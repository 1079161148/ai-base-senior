"""第 08 章 · 查询参数校验（Query）。

核心：Query() 给查询参数加约束与文档；与 Path() 唯一差异是「用默认值表达可选性」。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, Query
from pydantic import Field

app = FastAPI(title="第 08 章 · 查询参数校验", version="0.1.0")


# ============================================================
# 1. 必填 + 校验：不写默认值
# ============================================================
@app.get("/articles", tags=["文章"], summary="文章列表")
def list_articles(
    q: Annotated[
        str,
        # 【注意】正则用 raw string，`\w` 才不会被 Python 当成转义字符
        Query(min_length=1, max_length=50, pattern=r"^[\w\s\u4e00-\u9fa5]+$", description="搜索词，必填"),
    ],
    limit: Annotated[int, Query(ge=1, le=100, description="每页条数，1–100")] = 20,
    offset: Annotated[int, Query(ge=0, description="偏移量")] = 0,
) -> dict[str, object]:
    """`q` 没有默认值 → 必填；`limit`/`offset` 有默认值 → 可选。

    【作用】`Query(min_length=1)` 拒绝空串：`?q=` 会 422，
           而第 07 章不带约束时 `?q=` 会返回 200 + ""。
    【注意】`limit` 的 `le=100` 是防线：没有它，`?limit=999999` 会原封不动打进数据库。
    【实测】`/articles` → 422 missing；`/articles?q=a&limit=0` → 422 greater_than_equal
    """
    return {"q": q, "limit": limit, "offset": offset}


# ============================================================
# 2. 别名：查询串里的键名与函数参数名解耦
# ============================================================
@app.get("/orders", tags=["订单"], summary="订单列表（连字符参数）")
def list_orders(
    page_size: Annotated[int, Query(alias="page-size", ge=1, le=50, description="每页条数")] = 10,
    order_by: Annotated[str, Query(alias="order-by", pattern="^(created|amount)$")] = "created",
    # 【作用】deprecated=True 会在 OpenAPI 里标记该参数已废弃，文档 UI 会划掉
    legacy: Annotated[str | None, Query(alias="old-flag", deprecated=True, description="已废弃，改用 page-size")] = None,
) -> dict[str, object]:
    """别名演示。

    【注意】用 `alias="page-size"` 后，**只有** `?page-size=30` 生效。
           传 `?page_size=30` 不会报错，而是**静默使用默认值 10**——
           这是本章最危险的坑：参数名拼错永远不 422，只表现为「行为不对」。
    【为什么】HTTP 规范里未知查询参数应被忽略，所以框架不会对多余的键报错。
    """
    return {"page_size": page_size, "order_by": order_by, "legacy": legacy}


# ============================================================
# 3. 数组参数的校验
# ============================================================
@app.get("/tags", tags=["标签"], summary="多值 + 数组约束 vs 元素约束")
def by_tags(
    # 【实测】Query(min_length/max_length) 作用在 list 上，限制的是**数组长度**（元素个数），
    #        不是每个元素的字符串长度。写成 min_length=1 会让默认值 [] 直接 422。
    tag: Annotated[list[str], Query(max_length=10, description="标签，最多 10 个")] = [],
    ids: Annotated[list[int], Query(description="ID 列表")] = [],
    # 【作用】要约束**每个元素**，必须把约束放到元素类型上：list[Annotated[str, Field(...)]]
    codes: Annotated[list[Annotated[str, Field(min_length=2, max_length=4)]], Query()] = [],
) -> dict[str, object]:
    """数组参数的两层约束。

    【注意】错误 `loc` 会带索引：`["query","ids",0]` 表示第 0 个元素不是整数；
           而数组长度错误是 `["query","tag"]` + `type: too_long`。
    【实测】11 个 tag → `too_long`；`?ids=a` → `int_parsing` 且 loc 带索引；
           `?codes=x` → `string_too_short` 且 loc 带索引。
    """
    return {"tag": tag, "ids": ids, "codes": codes}


# ============================================================
# 4. 内部参数：不进文档但仍可用
# ============================================================
@app.get("/debug/echo", tags=["运维"], summary="回显（内部参数不进文档）")
def echo(
    value: str,
    # 【作用】include_in_schema=False：参数可用，但不写进 OpenAPI
    _internal: Annotated[str | None, Query(include_in_schema=False, alias="_internal")] = None,
) -> dict[str, object]:
    """`_internal` 不出现在 `/docs`，但 `?_internal=x` 能传进来。

    【注意】实测：当一个接口的**全部**参数都被隐藏时，OpenAPI 里连
           `parameters` 这个键都会消失（不是空数组）。
    【注意】隐藏参数不是安全措施——知道名字就能传，真正的保护靠鉴权。
    """
    return {"value": value, "internal_used": _internal is not None}


# ============================================================
# 5. 可选 + 约束的正确组合
# ============================================================
@app.get("/optional", tags=["示例"], summary="可选但有约束")
def optional_checked(
    q: Annotated[str | None, Query(min_length=3, description="不传则跳过校验")] = None,
) -> dict[str, str | None]:
    """`T | None = None` + 约束：不传时是 None（不触发 min_length），传了才校验。

    【注意】如果写成 `q: str = None`（类型不含 None），OpenAPI 会丢 null，
           前端生成的类型就错了——这是第 07 章讲过的坑。
    """
    return {"q": q}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
