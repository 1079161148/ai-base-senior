# 18 局部更新（PATCH）

## 一句话结论

PATCH 的模型**所有字段都可选**（默认 `None`），再用 `model_dump(exclude_unset=True)` 只取出「请求里真的出现过」的字段。不这样做，一个 `{"name": "x"}` 会把其余字段全部写成 `None`。`exclude_unset` 保留显式 `null`，`exclude_none` 会丢掉 `null`——语义完全不同。

学完这一章，你能：写出不会误清空字段的 PATCH 接口、区分「没传」与「传了 null」、用 `model_fields_set` 做审计。

## 最小可运行案例

```python
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI()

_PRODUCTS: dict[int, dict[str, Any]] = {1: {"id": 1, "name": "机械键盘", "price": 399.0}}


class ProductPatch(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: Annotated[str | None, Field(min_length=2, max_length=20)] = None
    price: Annotated[float | None, Field(gt=0)] = None


@app.patch("/products/{product_id}")
def patch_product(product_id: int, patch: ProductPatch) -> dict[str, Any]:
    if product_id not in _PRODUCTS:
        raise HTTPException(status_code=404, detail="商品不存在")

    updates = patch.model_dump(exclude_unset=True)   # 只取请求里出现过的字段
    _PRODUCTS[product_id].update(updates)
    return {"product": _PRODUCTS[product_id], "updates": updates}
```

完整版本（显式 `null`、空对象、审计字段）见 `examples/main.py`。

## 怎么跑

```powershell
cd "02-请求体与模型\18-局部更新\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 只更新传入字段 -> updates={'name': '静音键盘'}，price/tags 未变
[PASS] 显式 null 置空 -> updates={"note": None}
[PASS] exclude_none 语义不同 -> exclude_unset→{'note': None}；exclude_none→{}
[PASS] 未传字段不进 updates -> fields_set=["price"]
[PASS] 空对象合法 -> 空对象 200，updates={}
[PASS] 可选字段仍校验 -> name='笔' → string_too_short；price=0 → greater_than
[PASS] 多余字段被拒 -> loc=['body', 'nmae']
[PASS] 未知商品 404 -> 404
[PASS] fields_set 不被 dump 改变 -> fields_set=['name', 'price']，多次 dump 后不变
[PASS] OpenAPI 无 required -> PATCH 无 required，additionalProperties=false

结果：10/10 通过
```

## 核心 API 速查

| 用法 | 作用 | 注意 |
| --- | --- | --- |
| `字段: T \| None = None` | 让字段可选 | 可选 ≠ 不校验 |
| `model_dump(exclude_unset=True)` | 只输出**被赋值过**的字段 | 显式 `null` 会保留 |
| `model_dump(exclude_none=True)` | 去掉所有值为 `None` 的字段 | 显式 `null` 也会被丢掉 |
| `model_fields_set` | 本次请求出现过的字段名集合 | 只读快照，多次 dump 不变 |
| `extra="forbid"` | 拒绝拼错的字段名 | 防「以为改了其实没改」 |
| `HTTPException(404)` | 资源不存在 | 不要用 422 表达「不存在」 |

| 序列化参数 | `{"name": "x"}` | `{"note": null}` | `{}` |
| --- | --- | --- | --- |
| `exclude_unset=True` | `{"name": "x"}` | `{"note": None}` | `{}` |
| `exclude_none=True` | `{"name": "x"}` | `{}` | `{}` |
| 不带参数 | 4 个 `None` | 4 个 `None` | 4 个 `None` |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| PATCH 直接复用 `ProductCreate` | 没传的字段变成 `None`，数据被清空 | 单独的 `ProductPatch`（全可选） |
| 用 `model_dump()` 全量 `update` | 同上，等于 PUT 语义 | `exclude_unset=True` |
| 想要「忽略 null」却用了 `exclude_unset` | `null` 被写进库 | 按业务选 `exclude_none` |
| 以为可选字段不做校验 | `name="笔"` 仍 422 | 可选只是「可省略」 |
| 用 PUT 实现局部更新 | 语义错、客户端要传全量 | 用 PATCH |
| 资源不存在返回 422 | 客户端无法区分「参数错」与「没这个资源」 | 404 |

## 毕业自查

- [ ] 能说出 `exclude_unset` 与 `exclude_none` 的差别
- [ ] 能解释 `{}` 请求为什么合法、以及它应该改什么
- [ ] 能说出 PATCH 模型为什么不能复用创建模型
- [ ] 能读出 `model_fields_set` 的内容
- [ ] 能说出「可选字段仍校验」的证据
- [ ] 能说清 404 与 422 的分工
- [ ] 动手题一：加 `tags: list[str] | None`，验证传 `[]` 能清空标签
- [ ] 动手题二：把 `{"note": null}` 改成忽略 null 的语义，写出改动点

> 想看 PUT/PATCH 语义对比、`exclude_*` 全家桶、并发覆盖问题、20 条坑，继续读 [`base.md`](./base.md)。
