"""第 13 章 · 请求体基础。

核心：用 Pydantic 模型声明 body，FastAPI 自动完成「解析 JSON → 校验 → 类型转换 → 注入对象」，
      并同步生成 OpenAPI 的 requestBody 结构。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict

app = FastAPI(title="第 13 章 · 请求体基础", version="0.1.0")


# ============================================================
# 1. 请求体模型：一个类就是一份契约
# ============================================================
class ItemCreate(BaseModel):
    """创建商品的入参。

    【作用】继承 BaseModel 的类会被 FastAPI 当成「请求体模型」：
           - 出现在 OpenAPI 的 components/schemas 里
           - 请求体必须是 JSON 对象，缺字段/类型错 → 422
    【注意】非 `str` 字段在 Pydantic v2 的默认（lax）模式下会做**宽松转换**：
           `"9.9"` → `9.9`，但 `1` → `"1"` 不会发生（str 不接受数字）。
    """

    name: str
    price: float
    # 【作用】有默认值 → 非必填；OpenAPI 里 required 列表不包含它
    in_stock: bool = True


class ItemStrict(BaseModel):
    """演示 `extra="forbid"`：多传字段直接报错。

    【注意】默认行为是 `extra="ignore"`——多余字段被**静默丢弃**，
           前端多传了 `hack: 1`，服务端既不报错也拿不到，是排障黑洞。
    """

    # 【作用】禁止未声明字段；配合第 19 章的模型复用使用
    model_config = ConfigDict(extra="forbid")

    name: str
    price: float


# ============================================================
# 2. 最小创建接口
# ============================================================
@app.post("/items", tags=["商品"], summary="创建商品（请求体 = JSON 对象）")
def create_item(item: ItemCreate) -> dict[str, object]:
    """参数没有默认值 → 请求体**必填**。

    【实测】POST /items  body={"name":"笔","price":9.9} → 200
           {"received": {"name":"笔","price":9.9,"in_stock":true}, "price_type": "float"}
    【注意】`item` 已经是 `ItemCreate` 实例，不是 dict：
           - 取字段用 `item.name`（属性访问）
           - 转 dict 用 `item.model_dump()`
           - 不要写 `item["name"]`，会 TypeError
    """
    return {
        "received": item.model_dump(),
        # 【作用】验证转换结果：JSON 里的 9.9 到这里已经是 float
        "price_type": type(item.price).__name__,
    }


@app.post("/items-strict", tags=["商品"], summary="创建商品（禁止多余字段）")
def create_item_strict(item: ItemStrict) -> dict[str, object]:
    """【实测】多传 `hack` → 422 `extra_forbidden`，`loc=["body","hack"]`。"""
    return {"received": item.model_dump()}


# ============================================================
# 3. 可选请求体：整个 body 可以不传
# ============================================================
@app.post("/items-optional", tags=["商品"], summary="可选请求体")
def create_item_optional(item: ItemCreate | None = None) -> dict[str, object]:
    """【作用】`Model | None = None` 表示「整个请求体可选」。
    【实测】不传 body / 传 `null` → 200，`item is None`。
    【注意】它与「字段可选」是两件事：
           - `item: ItemCreate | None = None` → body 可以不传
           - `name: str | None = None`（模型内部）→ body 必须传，字段可以不传
    """
    return {"item": item.model_dump() if item is not None else None}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
