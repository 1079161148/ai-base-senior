# 13 请求体基础

## 一句话结论

用一个继承 `BaseModel` 的类声明请求体：FastAPI 自动完成「读 JSON → 校验 → 类型转换 → 注入模型实例」，并同步生成 `/docs` 里的 `requestBody`。缺字段是 422 `loc=["body","字段名"]`，完全没传 body 只有一条 `loc=["body"]`。

学完这一章，你能：写出第一份 body 模型、读懂 body 的 422 结构、说清「宽松转换」与「多余字段」这两个默认行为。

## 最小可运行案例

```python
from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class ItemCreate(BaseModel):
    name: str
    price: float
    in_stock: bool = True   # 有默认值 → 非必填


@app.post("/items")
def create_item(item: ItemCreate) -> dict[str, object]:
    # item 已经是模型实例：属性访问 + model_dump()
    return {"received": item.model_dump()}
```

完整版本（`extra="forbid"`、可选 body、Content-Type 陷阱）见 `examples/main.py`。

## 怎么跑

```powershell
cd "02-请求体与模型\13-请求体基础\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 合法请求体 -> {'name': '笔', 'price': 9.9, 'in_stock': True}
[PASS] 缺字段 loc 两段 -> 422 missing loc=['body', 'price']
[PASS] 空对象聚合 -> 2 条 missing（name/price）
[PASS] 无 body / null -> 422 missing loc=["body"]（单条）
[PASS] 宽松类型转换 -> "9.9"→9.9；9→9.0(float)
[PASS] int 不转 str -> 422 string_type（1 不会变成 "1"）
[PASS] 未知字段默认丢弃 -> 200 且 hack 被丢弃（不报错）
[PASS] extra=forbid -> 422 extra_forbidden loc=['body', 'hack']
[PASS] Content-Type 陷阱 -> 422 model_attributes_type（body 仍是字符串）
[PASS] 可选请求体 -> 不传/null → item=None；传了 → 正常解析
[PASS] OpenAPI requestBody -> items required=true；items-optional 省略 required（等价 false）

结果：11/11 通过
```

## 核心 API 速查

| 写法 | 含义 |
| --- | --- |
| `def f(item: ItemCreate)` | 请求体必填 |
| `def f(item: ItemCreate \| None = None)` | 整个请求体可选 |
| `class Item(BaseModel)` | 定义 body 契约 |
| `field: str` | 必填字段 |
| `field: str = "x"` | 可选字段 + 默认值 |
| `field: str \| None = None` | 可选字段，缺省 `None` |
| `model_config = ConfigDict(extra="forbid")` | 拒绝多余字段 |
| `item.model_dump()` | 模型 → dict（Python 侧） |

| 请求 | 结果 |
| --- | --- |
| `{"name":"笔","price":9.9}` | 200，`in_stock=True` |
| `{"name":"笔"}` | 422 `loc=["body","price"]` |
| `{}` | 422 两条 `missing` |
| 不发 body / `null` | 422 **一条** `missing`，`loc=["body"]` |
| `{"name":"笔","price":"9.9"}` | 200，转成 `9.9`（lax 模式） |
| `{"name":1,...}` | 422 `string_type`（数字不转字符串） |
| 多传 `hack` | 200，**静默丢弃** |
| `Content-Type: text/plain` | 422 `model_attributes_type`（body 未解析） |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 把 `item` 当 dict：`item["name"]` | `TypeError: 'ItemCreate' object is not subscriptable` | `item.name` / `item.model_dump()` |
| 以为多传字段会报错 | 默认 `extra="ignore"`，**静默丢弃** | 需要严格就 `extra="forbid"` |
| 以为字段缺失会返回 500 | 是 422，函数根本没执行 | 依赖 422 契约 |
| `Content-Type` 不是 `application/json` | 422 `model_attributes_type`，`input` 是原始字符串 | 客户端固定 `JSON.stringify` + 正确头 |
| 把字段可选写成 `name: str = None` | 类型不符，静态检查/运行时都可能炸 | `name: str \| None = None` |
| 以为「body 可选」=「字段可选」 | 两者完全不同层级 | 看参数级 vs 字段级 |
| 用 GET 传请求体 | 语义错乱，很多网关直接丢弃 | 用 POST/PUT/PATCH |

## 毕业自查

- [ ] 能写出一个带默认值字段的 body 模型
- [ ] 能说出「缺字段」与「没传 body」的 `loc` 差异
- [ ] 能说出 `extra` 的默认策略与改为 `forbid` 的写法
- [ ] 能解释为什么 `"9.9"` 能进 `float`，而 `1` 进不了 `str`
- [ ] 能说出 `Content-Type` 不对时会发生什么
- [ ] 动手题一：给 `ItemCreate` 加一个可选字段 `description: str | None = None`
- [ ] 动手题二：把 `in_stock` 改成必填，观察 `/docs` 的 `required` 变化

> 想看 Pydantic 校验机制、lax/strict 模式、OpenAPI schema 生成细节、23 条坑，继续读 [`base.md`](./base.md)。
