# 15 嵌套模型

## 一句话结论

模型可以套模型、套列表。校验逐层递归，`loc` 按层级变长：对象字段用**字段名**、列表元素用**整数下标**（`["body","items",0,"price"]`）。内层模型的配置（`extra` 等）**不会**从外层继承——这是最容易误判的一条。

学完这一章，你能：设计三层以内的订单结构、按 `loc` 精确定位到「第几行的哪个字段」、说清 $ref 与 `additionalProperties`。

## 最小可运行案例

```python
from typing import Annotated

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI()


class Address(BaseModel):
    city: str
    street: str


class Customer(BaseModel):
    name: str
    address: Address          # 模型套模型


class OrderItem(BaseModel):
    sku: str
    qty: Annotated[int, Field(ge=1)]
    price: Annotated[float, Field(gt=0)]


class Order(BaseModel):
    customer: Customer
    items: Annotated[list[OrderItem], Field(min_length=1, max_length=5)]  # 模型套列表


@app.post("/orders")
def create_order(order: Order) -> dict[str, object]:
    return {"total": sum(i.price * i.qty for i in order.items)}
```

完整版本（多层错误聚合、内层 `extra` 不继承）见 `examples/main.py`。

## 怎么跑

```powershell
cd "02-请求体与模型\15-嵌套模型\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 合法嵌套请求 -> item=OrderItem total=19.8
[PASS] 嵌套缺字段 loc 五段 -> loc=['body', 'customer', 'address', 'street']
[PASS] 列表下标定位 -> loc=['body', 'items', 0, 'price']（0 是整数下标）
[PASS] 元素内部约束 -> loc=['body', 'items', 0, 'qty'] ctx={'ge': 1}
[PASS] 元素不是对象 -> loc=['body', 'items', 0]
[PASS] 空列表 -> too_short actual_length=0
[PASS] 内层 extra 不继承 -> 200，内层 hack 被静默丢弃
[PASS] 外层 extra=forbid -> loc=['body', 'hack']
[PASS] 对象当列表传 -> list_type loc=['body', 'items']
[PASS] 多层错误聚合 -> 2 条错误，分别定位到不同层级
[PASS] OpenAPI $ref -> 3 层 $ref 链 + minItems/maxItems + additionalProperties=false

结果：11/11 通过
```

## 核心 API 速查

| 写法 | 含义 |
| --- | --- |
| `address: Address` | 字段是对象，必填 |
| `address: Address \| None = None` | 可选对象 |
| `items: list[OrderItem]` | 数组，元素是模型 |
| `items: Annotated[list[OrderItem], Field(min_length=1, max_length=5)]` | 限元素个数 |
| `tags: list[str]` | 标量数组 |
| `meta: dict[str, str]` | 字典（键值都受约束） |

`loc` 的读法：

| 输入问题 | `loc` |
| --- | --- |
| 顶层缺字段 | `["body","items"]` |
| 嵌套对象缺字段 | `["body","customer","address","street"]` |
| 列表第 2 个元素缺字段 | `["body","items",1,"price"]` |
| 元素不是对象 | `["body","items",0]` |
| 整个 body 不是对象 | `["body"]` |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 以为外层 `extra="forbid"` 管住内层 | 实测内层多余字段仍被静默丢弃 | 每层都配 `extra="forbid"` |
| 用 `list[dict]` 代替 `list[Model]` | 元素内容完全不校验 | 用模型 |
| 无限层级嵌套 | 前端难用、错误难定位、递归开销大 | 层级 ≤ 4，业务拆接口 |
| 列表不设上限 | 一次传 10 万条打满内存 | `max_length` |
| 为空列表纠结是否合法 | 默认合法 | 需要非空就 `min_length=1` |
| 把对象当列表传 | 422 `list_type` | 客户端保证数组 |
| 以为 `loc` 里是字符串下标 | 实测是**整数** `0` | 前端按类型处理 |
| 深拷贝共享引用 | — | `model_dump()` 已递归转 dict，无需手写 copy |

## 毕业自查

- [ ] 能写出「对象 + 列表 + 对象列表」三种嵌套
- [ ] 能根据 `loc` 说出是第几个元素的哪个字段
- [ ] 能说出 `loc` 里下标是 int 还是 str
- [ ] 能说出内层 `extra` 为什么不继承
- [ ] 能说出 `list` 的 `min_length`/`max_length` 含义
- [ ] 能说出 OpenAPI 里嵌套结构为什么是 `$ref`
- [ ] 动手题一：给 `OrderItem` 加 `discount: float | None`，并让内层也 `extra="forbid"`
- [ ] 动手题二：把 `items` 上限改成 3，观察 `maxItems` 变化

> 想看递归校验流程、`loc` 构造规则、深度与性能边界、25 条坑，继续读 [`base.md`](./base.md)。
