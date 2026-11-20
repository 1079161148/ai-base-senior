"""第 14 章 · Field 字段约束。

核心：`Annotated[T, Field(...)]` 把「类型 + 约束 + 文档」写在一处，
      约束在进入函数前生效，错误类型与 ctx 直接告诉你违反了哪条规则。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Annotated

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="第 14 章 · Field 字段约束", version="0.1.0")


# ============================================================
# 1. 一份带完整约束的请求模型
# ============================================================
class ProductCreate(BaseModel):
    """商品创建入参：所有约束都在模型里，函数体不再写 if。

    【注意】`model_config` 是**类属性**，不是 Field 的参数：
           `Field(alias=..., populate_by_name=True)` 会触发 DeprecationWarning
           且**不生效**（实测仍是 422），必须写在这里。
    """

    model_config = ConfigDict(
        extra="forbid",              # 多余字段直接报错（第 13 章）
        populate_by_name=True,       # 允许用字段名 item_name 代替别名 itemName
        str_strip_whitespace=True,   # 自动 strip，避免 "  钢笔  " 与 "钢笔" 成两个值
    )

    # 【作用】min_length/max_length 作用在字符串上 = 字符数
    name: Annotated[
        str,
        Field(min_length=2, max_length=20, description="商品名", examples=["机械键盘"]),
    ]

    # 【作用】gt 严格大于、ge 大于等于、le 小于等于；浮点可用
    price: Annotated[float, Field(gt=0, le=100_000, description="单价（元）")]

    # 【作用】pattern 是正则，默认**整串匹配**语义由你自己加 ^$ 保证
    sku: Annotated[str, Field(pattern=r"^[A-Z]{3}-\d{4}$", examples=["ABC-1234"])]

    # 【作用】list 上的 max_length = **元素个数**，不是字符串长度（第 08 章同款坑）
    tags: Annotated[list[str], Field(max_length=3, description="最多 3 个标签")] = []

    # 【注意】可选字段的约束只在「值不是 None」时生效：传 null 直接通过（实测）
    note: Annotated[str | None, Field(min_length=5, description="备注，至少 5 字")] = None

    # 【作用】alias 改变对外字段名；用 populate_by_name=True 后两个名字都收
    item_name: Annotated[str | None, Field(alias="itemName", description="前端风格的字段名")] = None


# ============================================================
# 2. 创建接口
# ============================================================
@app.post("/products", tags=["商品"], summary="创建商品（全部约束在模型里）")
def create_product(product: ProductCreate) -> dict[str, object]:
    """函数体只处理业务，不写任何字段校验。

    【实测】name="笔" → 422 string_too_short，ctx={"min_length":2}
    【实测】price=0   → 422 greater_than，ctx={"gt":0.0}
    【注意】返回时用 `model_dump(by_alias=True)` 保留对外字段名；
           不加参数会输出内部字段名 `item_name`（第 21 章讲响应模型）。
    """
    return {
        "internal": product.model_dump(),
        "external": product.model_dump(by_alias=True),
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
