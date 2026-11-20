# 17 特殊类型

## 一句话结论

`UUID`/`Decimal`/`datetime`/`date`/`HttpUrl`/`Enum`/`Literal` 在 JSON 里都是字符串或数字，FastAPI + Pydantic 负责转成 Python 类型并校验。金额只用 `Decimal`；`HttpUrl` 是 Pydantic 内置（无需额外依赖）；Decimal 的线上形态取决于**有没有写返回注解**（实测：无注解→数字，有注解→字符串）。

学完这一章，你能：为每个业务字段选对类型、读懂各自的 422 错误、说清金额精度在序列化环节的坑。

## 最小可运行案例

```python
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Annotated
from uuid import UUID

from fastapi import FastAPI
from pydantic import BaseModel, Field, HttpUrl

app = FastAPI()


class Channel(str, Enum):
    web = "web"
    app = "app"


class PaymentCreate(BaseModel):
    order_id: UUID
    amount: Annotated[Decimal, Field(gt=0, max_digits=8, decimal_places=2)]
    created_at: datetime
    callback: HttpUrl | None = None
    channel: Channel = Channel.web


@app.post("/payments")
def create_payment(payment: PaymentCreate) -> dict[str, object]:
    return {
        "json": payment.model_dump(mode="json"),
        "amount_exact": str(payment.amount),
    }
```

完整版本（`Literal`、类型断言、序列化对比）见 `examples/main.py`。

## 怎么跑

```powershell
cd "02-请求体与模型\17-特殊类型\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 特殊类型转换 -> {'order_id': 'UUID', 'amount': 'Decimal', 'created_at': 'datetime', 'callback': 'HttpUrl', 'channel': 'Channel'}
[PASS] UUID 非法 -> uuid_parsing：invalid character: found `n` at 0
[PASS] 小数位超限 -> decimal_max_places ctx={'decimal_places': 2}
[PASS] 总位数超限 -> decimal_max_digits ctx={'max_digits': 8}
[PASS] 时间非法 -> month value is outside expected range of 1-12
[PASS] 日期非法 -> day value is outside expected range
[PASS] 枚举非法 -> enum expected='web' or 'app'
[PASS] Literal 非法 -> literal_error expected='retail' or 'wholesale'
[PASS] URL 非法 -> relative URL without a base
[PASS] 数字金额 -> 数字 19.99 → Decimal('19.99')
[PASS] 两种序列化模式 -> json 模式：amount="19.99"（字符串）
[PASS] 返回注解影响编码 -> 无注解→19.99(number)；有注解→"19.99"(string)
[PASS] OpenAPI format -> uuid/date-time/uri/enum/anyOf 全部生成

结果：13/13 通过
```

## 核心 API 速查

| 类型 | JSON 输入 | Python 类型 | 非法时 `type` |
| --- | --- | --- | --- |
| `UUID` | `"123e4567-..."` | `uuid.UUID` | `uuid_parsing` |
| `Decimal` | `"19.99"` 或 `19.99` | `decimal.Decimal` | `decimal_parsing` / `decimal_max_places` / `decimal_max_digits` |
| `datetime` | ISO 8601 字符串 | `datetime.datetime` | `datetime_from_date_parsing` |
| `date` | `"2026-01-05"` | `datetime.date` | `date_from_datetime_parsing` |
| `HttpUrl` | `"https://..."` | `pydantic.HttpUrl` | `url_parsing` |
| `Enum` | 成员**值** | 枚举成员 | `enum`（`ctx.expected`） |
| `Literal[...]` | 白名单值 | 字面量 | `literal_error` |

| 序列化方式 | Decimal | UUID/datetime |
| --- | --- | --- |
| `model_dump()` | `Decimal` | 原对象 |
| `model_dump(mode="json")` | `"19.99"` | 字符串 |
| 返回**无**注解（`jsonable_encoder`） | `19.99`（数字） | 字符串 |
| 返回**有**注解（Pydantic 响应模型） | `"19.99"`（字符串） | 字符串 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 金额用 `float` | 0.1+0.2 精度误差 | `Decimal` + `max_digits`/`decimal_places` |
| 以为 `HttpUrl` 要装依赖 | 它是 Pydantic 内置 | 直接用；`EmailStr` 才需 `email-validator` |
| `Enum` 传成员名（`"web"` 是值，`WEB` 是名） | 传名会 422 | 传**值** |
| `datetime` 不带时区 | 跨时区错位 | 统一带偏移或存 UTC |
| 返回 `model_dump()` 就以为金额是字符串 | 有无返回注解结果不同（实测） | 金额显式 `str()` 或 `mode="json"` |
| 用 `date` 接完整 datetime 字符串 | 实际可用（取日期部分），但语义易混 | 输入输出保持同一粒度 |
| 用 `Literal` 表达大枚举 | 文档里没有独立组件 | 大集合用 `Enum` |
| 用 `UUID` 接不是 UUID 的业务编号 | 422 | 自定义编号用 `str` + `pattern` |

## 毕业自查

- [ ] 能说出金额为什么必须用 `Decimal`
- [ ] 能说出 `max_digits` 与 `decimal_places` 的区别
- [ ] 能写出带时区与不带时区的 `datetime` 输入
- [ ] 能说出 `Enum` 与 `Literal` 的取舍
- [ ] 能说出 `HttpUrl` 的依赖情况
- [ ] 能解释「同一份数据，有无返回注解导致 Decimal 输出不同」
- [ ] 动手题一：给 `amount` 加 `le=1000000` 并验证边界
- [ ] 动手题二：把 `kind` 从 `Literal` 改成 `Enum`，比较 OpenAPI

> 想看类型选型表、时区处理、序列化链路、24 条坑，继续读 [`base.md`](./base.md)。
