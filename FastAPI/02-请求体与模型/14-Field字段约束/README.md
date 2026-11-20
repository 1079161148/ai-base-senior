# 14 Field 字段约束

## 一句话结论

`Annotated[T, Field(...)]` 把「类型 + 约束 + 文档」写在一处：`min_length`/`max_length` 限长度、`gt`/`ge`/`lt`/`le` 限数值、`pattern` 限格式、`examples` 进文档。约束在进入函数前生效，422 里的 `type` 与 `ctx` 直接告诉你违反了哪条。`list` 上的 `max_length` 是**元素个数**；可选字段传 `null` 时约束**不执行**。

学完这一章，你能：给每个字段配上准确的约束、读懂 `ctx`、避开 `alias`/`populate_by_name` 的位置陷阱。

## 最小可运行案例

```python
from typing import Annotated

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI()


class ProductCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Annotated[str, Field(min_length=2, max_length=20, examples=["机械键盘"])]
    price: Annotated[float, Field(gt=0, le=100_000)]
    sku: Annotated[str, Field(pattern=r"^[A-Z]{3}-\d{4}$")]
    tags: Annotated[list[str], Field(max_length=3)] = []


@app.post("/products")
def create_product(product: ProductCreate) -> dict[str, object]:
    return {"external": product.model_dump(by_alias=True)}
```

完整版本（可选字段、别名、`populate_by_name` 陷阱）见 `examples/main.py`。

## 怎么跑

```powershell
cd "02-请求体与模型\14-Field字段约束\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 合法请求 -> external.itemName=礼盒装
[PASS] 字符串长度 -> string_too_short ctx={'min_length': 2}
[PASS] gt 边界 -> 0 → greater_than；0.01 → 200
[PASS] le 边界 -> 100000 → 200；100000.01 → less_than_equal
[PASS] 正则 -> abc-1234 → 422；XYZ-0001 → 200
[PASS] 列表元素个数 -> too_long actual_length=4
[PASS] None 跳过约束 -> null → 200；'abc' → string_too_short
[PASS] 别名只认 alias -> 422 missing loc=['body', 'itemName']
[PASS] populate_by_name 位置 -> model_config → 200；Field 参数 → 422
[PASS] OpenAPI 约束映射 -> minLength/maxLength/exclusiveMinimum/maxItems/examples 全部生成

结果：10/10 通过
```

## 核心 API 速查

| 参数 | 适用类型 | 作用 | 违反时 `type` |
| --- | --- | --- | --- |
| `min_length` / `max_length` | `str` | 字符数 | `string_too_short` / `string_too_long` |
| `min_length` / `max_length` | `list` | **元素个数** | `too_short` / `too_long` |
| `gt` / `ge` | 数值 | 大于 / 大于等于 | `greater_than` / `greater_than_equal` |
| `lt` / `le` | 数值 | 小于 / 小于等于 | `less_than` / `less_than_equal` |
| `pattern` | `str` | 正则 | `string_pattern_mismatch` |
| `alias` | 任意 | 对外字段名 | 用错名字 → `missing` |
| `description` / `examples` | 任意 | 进 `/docs` | — |
| `default_factory` | 可变类型 | 默认值工厂 | — |

| OpenAPI 映射 | 来源 |
| --- | --- |
| `minLength` / `maxLength` | `min_length` / `max_length` |
| `exclusiveMinimum` / `minimum` | `gt` / `ge` |
| `exclusiveMaximum` / `maximum` | `lt` / `le` |
| `maxItems` / `minItems` | `list` 的 `max_length` / `min_length` |
| `pattern` / `examples` / `default` | 同名参数 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `Field(populate_by_name=True)` | 有 `DeprecationWarning` 且**不生效**（实测仍 422） | 写到 `model_config = ConfigDict(populate_by_name=True)` |
| `Field(max_length=3)` 用在 `list` 上以为限字符 | 限的是**元素个数** | 元素内容约束用 `list[Annotated[str, Field(...)]]` |
| 可选字段以为 `null` 会触发约束 | 实测 `note=null` → 200，约束跳过 | 需要「非空」用必填或校验器（第 20 章） |
| `pattern` 不加 `^...$` | 匹配语义依赖实现，可能放过子串 | 一律加锚点 |
| 用 `gt=0` 想要「允许 0」 | 0 被拒 | 用 `ge=0` |
| 以为约束能替代业务校验 | 跨字段规则（密码一致）表达不了 | `model_validator`（第 20 章） |
| 只在函数体里 `if price <= 0` | 文档无约束、422 结构不统一 | 用 `Field` |
| 用 `float` 存金额 + `le` | 精度误差仍在 | `Decimal` + `gt=0`（第 17 章） |

## 毕业自查

- [ ] 能说出 `gt` 与 `ge`、`lt` 与 `le` 的区别
- [ ] 能说出 `list` 上 `max_length` 的含义
- [ ] 能读懂 422 的 `ctx`（`min_length`/`gt`/`actual_length`）
- [ ] 能说出可选字段传 `null` 时约束是否执行
- [ ] 能说出 `populate_by_name` 该写在哪
- [ ] 能说出约束如何映射成 JSON Schema
- [ ] 动手题一：给 `tags` 加「每个标签 1–10 字」的元素级约束
- [ ] 动手题二：把 `price` 改成 `Decimal` 并保留 `gt=0`

> 想看约束与 JSON Schema 的完整映射、ReDoS 风险、`alias` 序列化细节、24 条坑，继续读 [`base.md`](./base.md)。
