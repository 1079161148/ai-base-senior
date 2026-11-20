# 17 特殊类型 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「每个类型在 JSON 里是什么、校验失败报什么、金额精度在哪一步丢、时区怎么处理」拆开。学完这章，你要能给每个业务字段选出**唯一正确**的类型。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1 / Python 3.12.8（本机实测） |
| 前置 | 第 13–16 章（模型、约束、嵌套、多参数） |
| 覆盖范围 | `UUID`/`Decimal`/`datetime`/`date`/`HttpUrl`/`Enum`/`Literal`、序列化模式、OpenAPI format |
| 明确不覆盖 | 响应模型与字段过滤（第 21 章）、`jsonable_encoder` 全解（第 30 章）、时区库（`zoneinfo` 属标准库，仅提及） |
| 学完验收 | 能跑通 `verify.py` 13/13、能说清金额精度链路、能预测每种类型的 422 |

## 0. 怎么用这份文件

**依据约定**：`` `[Tn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 业务字段 → 类型映射表
2 机制（第 2 节）    → 解析 → 校验 → 内部类型 → 序列化
3 API（第 3 节）     → 各类型写法与错误
4 边界（第 4 节）    → 金额精度、时区、URL 限制、枚举演进
5 注意事项（第 5 节）→ 24 条对照
6 最佳实践（第 6 节）→ 类型选型与序列化模板
```

## 1. 概念：字段类型决定契约质量

JSON 只有 4 种标量：字符串、数字、布尔、null。所有「富类型」到线上都必须降级成这四种，因此每个字段都要回答三个问题：

1. **线上用什么表达**（字符串/数字）
2. **内部用什么承载**（`Decimal`/`UUID`/`datetime`）
3. **非法输入怎么报错**（422 的 `type`）

业务字段 → 类型的映射表：

| 业务语义 | 正确类型 | 不要用 | 原因 |
| --- | --- | --- | --- |
| 金额、单价、税额 | `Decimal` | `float` | 二进制浮点误差（`0.1+0.2 != 0.3`） |
| 唯一标识（内部） | `UUID` | `int` 自增暴露规模 | 可枚举、可猜 |
| 业务编号（外部可见） | `str` + `pattern` | `UUID` | 编号有自己的格式规则 |
| 时间点 | `datetime`（带时区） | `str` / `int` 时间戳 | 无类型无法校验 |
| 日期（不含时间） | `date` | `datetime` | 语义精确 |
| 回调/跳转地址 | `HttpUrl` | `str` | 避免 `javascript:` 等非 http 协议 |
| 有限状态 | `Enum` / `Literal` | `str` | 取值不受控 |
| 大整数（订单号） | `str` | `int` | JS 超过 2^53 丢精度 |

## 2. 机制：从 JSON 到 Python 的四步

```text
① 解析 JSON        "19.99" / 19.99 / "2026-01-02T03:04:05"
② 类型转换         Decimal("19.99") / datetime(2026,1,2,3,4,5) / UUID(...)
③ 约束校验         gt/max_digits/decimal_places → 422 带 ctx
④ 构造模型实例      函数体拿到真正的强类型对象
```

四条实测结论：

| 结论 | 证据 |
| --- | --- |
| 转换与校验是分开的两步 | `"not-a-uuid"` → `uuid_parsing`（转换失败），不是 `missing` |
| `Decimal` 接受字符串与数字 | `"19.99"` 与 `19.99` 都得到 `Decimal('19.99')` |
| `datetime` 无时区就是 naive | `"2026-01-02T03:04:05"` → `tzinfo=None` |
| 响应编码走两条不同路径 | 有返回注解 → Pydantic 序列化；无注解 → `jsonable_encoder` |

## 3. API 逐个拆解

### 3.1 `UUID`

```python
from uuid import UUID

order_id: UUID
```

| 输入 | 结果 |
| --- | --- |
| `"123e4567-e89b-12d3-a456-426614174000"` | 200，`uuid.UUID` |
| `"not-a-uuid"` | 422 `uuid_parsing`，`ctx.error="invalid character: found \`n\` at 0"` |
| 大写/无连字符（部分格式） | Pydantic 会尝试解析；**不要依赖非标准写法** |

### 3.2 `Decimal`

```python
from decimal import Decimal
from typing import Annotated

from pydantic import Field

amount: Annotated[Decimal, Field(gt=0, max_digits=8, decimal_places=2)]
```

| 参数 | 含义 | 实测错误 |
| --- | --- | --- |
| `max_digits` | **总位数**（不含小数点与符号） | `decimal_max_digits`，`ctx.max_digits` |
| `decimal_places` | 小数位数 | `decimal_max_places`，`ctx.decimal_places` |
| `gt` / `ge` | 正负与下限 | `greater_than` / `greater_than_equal` |

实测：

```text
"1.999"      -> decimal_max_places（2 位）
"1234567.89" -> decimal_max_digits（8 位）
"19.99"      -> Decimal('19.99')
```

### 3.3 `datetime` / `date`

| 声明 | 接受 | 说明 |
| --- | --- | --- |
| `datetime` | ISO 8601：`2026-01-02T03:04:05`、带偏移、`Z` 结尾 | 不带偏移 → naive |
| `date` | `2026-01-05`；也接受完整 datetime 并截取日期 | 时间部分被丢弃 |
| `time` | `03:04:05` | 少用，注意无时区 |

实测错误：

```text
"2026-13-45"  -> datetime_from_date_parsing（month out of range）
"2026-02-30"  -> date_from_datetime_parsing（day out of range）
```

### 3.4 `HttpUrl`

| 项 | 说明 |
| --- | --- |
| 依赖 | **Pydantic 内置**，无需 `email-validator` |
| 校验 | 必须带 scheme + host；相对地址被拒 |
| schema | `format: uri`、`minLength: 1`、`maxLength: 2083`（实测） |
| 错误 | `url_parsing`，`ctx.error="relative URL without a base"` |
| 类型 | `pydantic_core.Url`（类名 `HttpUrl`） |

安全提醒：`HttpUrl` 只保证是 http(s) URL，**不保证目标安全**。做服务端回调时要额外做 SSRF 防护（禁止内网地址）。

### 3.5 `Enum` 与 `Literal`

```python
from enum import Enum
from typing import Literal


class Channel(str, Enum):
    web = "web"
    app = "app"


channel: Channel = Channel.web
kind: Literal["retail", "wholesale"] = "retail"
```

| 对比 | `Enum` | `Literal` |
| --- | --- | --- |
| OpenAPI | 独立组件 + `$ref` | 内联 `enum` 列表 |
| 可复用 | ✅ | ❌（要重复写） |
| 可带方法 | ✅（`str` 混入后仍可） | ❌ |
| 适合 | 状态机、跨模块共享 | 单个接口的小白名单（2–4 个值） |
| 错误 `type` | `enum` | `literal_error` |

实测错误都带 `ctx.expected="'web' or 'app'"`，可直接给用户看。

## 4. 边界条件

### 4.1 金额精度的完整链路（本章最重要）

| 环节 | 行为 | 风险 |
| --- | --- | --- |
| 客户端 | 传 `"19.99"` 字符串 | ✅ 安全 |
| 客户端 | 传 `19.99` 数字 | 浏览器/JS 已是 float，**入参就可能不准** |
| 服务端校验 | `Decimal("19.99")` | ✅ 精确 |
| 计算 | `Decimal` 运算 | ✅ 精确（注意 `quantize` 定标） |
| 响应序列化 | 有返回注解 → 字符串；无注解 → `19.99` 数字 | ⚠️ 数字形态会丢精度 |
| 客户端解析 | 数字 → float | ⚠️ 再次丢精度 |

结论：**金额全链路都要用字符串表达**。服务端用 `Decimal` 计算，出参用字符串（`model_dump(mode="json")` 或字段 `str()`）。

### 4.2 返回注解决定编码路径（实测）

```python
@app.get("/no-annotation")
def a():
    return M(amount=Decimal("19.99")).model_dump()      # -> {"amount": 19.99}


@app.get("/with-annotation")
def b() -> dict[str, object]:
    return M(amount=Decimal("19.99")).model_dump()      # -> {"amount": "19.99"}
```

| 情况 | 编码器 | Decimal 输出 |
| --- | --- | --- |
| 无返回注解 | `jsonable_encoder`（`decimal_encoder`） | JSON 数字 |
| 有返回注解 | Pydantic 响应模型序列化 | 字符串 |

> 这不是「哪个对」的问题，而是**必须显式选择**。金额接口建议固定用「返回模型 + `Decimal` 字段」，行为稳定可预期（第 21 章）。

### 4.3 时区

| 输入 | 内部 | 建议 |
| --- | --- | --- |
| `2026-01-02T03:04:05` | naive | 只在「本地日历时间」场景用；入库前明确时区 |
| `2026-01-02T03:04:05+08:00` | aware | 推荐：偏移明确 |
| `2026-01-02T03:04:05Z` | aware（UTC） | API 间传输推荐 UTC |

工程约定：**存储用 UTC，展示按客户端时区**。跨时区业务禁止用 naive datetime 做比较。

### 4.4 大整数与 JS 精度

| 数据 | 问题 | 方案 |
| --- | --- | --- |
| 订单号 > 2^53 | 前端 `JSON.parse` 丢精度 | 用字符串传 |
| 数据库 `bigint` 主键 | 同上 | 出参转字符串 |
| 金额「分」为单位 | 可避免小数 | 整数 + 文档说明单位 |

### 4.5 枚举演进

| 变更 | 兼容性 |
| --- | --- |
| 新增枚举值 | 客户端需同步（老客户端可能不认） |
| 删除/改名 | **破坏性** |
| 值改名（`web`→`h5`） | 破坏性，需过渡期双写 |

建议：枚举值一旦发布当常量对待；新增值前先确认客户端降级行为。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 金额用 `float` | 0.1+0.2 精度误差 | `Decimal` | 实测 |
| 只给 `decimal_places` 不给 `max_digits` | 整数部分可无限大 | 两个都给 | 实测 |
| 以为 `max_digits` 是整数位 | 它是总位数 | 按总位数算 | 实测 |
| 传数字金额 | 已是 float，可能不准 | 传字符串 | 实测 |
| 返回注解时有时无 | 同一字段两种形态 | 统一返回模型 | 实测 |
| 金额出参用数字 | 前端解析丢精度 | 字符串 | 实测 |
| `datetime` 不带时区 | 跨时区错位 | 带偏移或统一 UTC | `[T3]` |
| 用 `date` 接带时间的字符串 | 时间被静默丢弃 | 粒度统一 | 实测 |
| 以为 `HttpUrl` 要装依赖 | 其实内置 | 直接用 | 实测 |
| `EmailStr` 没装依赖 | 启动报错 | `uv add email-validator` | `[T1]` |
| 用 `HttpUrl` 就以为安全 | 只校验格式，不防 SSRF | 额外白名单（第 49 章） | `[T6]` |
| 用 `UUID` 接业务编号 | 格式不符 422 | `str` + `pattern` | `[T2]` |
| 用 `int` 存订单号 | 超 2^53 丢精度 | 字符串 | `[T4]` |
| 枚举传成员名 | 422 | 传值 | 实测 |
| 用 `Literal` 表达 20 个状态 | 内联庞大、不可复用 | `Enum` | `[T2]` |
| `Enum` 不继承 `str` | 序列化/文档形态异常 | `class X(str, Enum)` | `[T2]` |
| 枚举改名 | 破坏性变更 | 新增值 + 过渡 | `[T2]` |
| 用 `Any` 收特殊类型 | 等于不校验 | 显式类型 | `[T1]` |
| 用时间戳整数传时间 | 单位（秒/毫秒）易错 | ISO 8601 字符串 | `[T3]` |
| `Decimal` 做除法不 `quantize` | 出现 28 位小数 | `quantize(Decimal("0.01"))` | `[T5]` |
| `Decimal` 与 `float` 混算 | `TypeError` | 全链路 Decimal | `[T5]` |
| 时区用 `datetime.utcnow()` | 已弃用且 naive | `datetime.now(timezone.utc)` | `[T3]` |
| 忘记 `URL` 长度上限 | 超 2083 被拒（实测 schema） | 客户端截断/校验 | 实测 |
| 在 query 里传 `datetime` | 可行但需 URL 编码 | 复杂条件放 body | 第 07 章 |
| 用 `str` 存金额且不校验位数 | 脏数据入库、对账对不上 | `Decimal` + `max_digits`/`decimal_places` | 实测 |

## 6. 最佳实践与编码建议

### 6.1 类型别名与模板

```python
from datetime import datetime
from decimal import Decimal
from typing import Annotated
from uuid import UUID

from pydantic import BaseModel, Field, HttpUrl

Money = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
OrderId = UUID
ExternalCode = Annotated[str, Field(pattern=r"^[A-Z]{2}\d{8}$")]


class PaymentCreate(BaseModel):
    order_id: OrderId
    amount: Money
    paid_at: datetime
    callback: HttpUrl | None = None
```

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 金额用 `Decimal` + 字符串传输 | 全链路精确 |
| 时间统一 UTC + 偏移 | 避免 naive |
| 内部 id 用 `UUID`，外部编号用 `str` | 语义分明 |
| 状态用 `Enum`（`str` 混入） | 可复用、可文档化 |
| 小白名单用 `Literal` | 轻量 |
| 出参固定用「返回模型」 | 编码路径稳定（第 21 章） |
| `Decimal` 运算后 `quantize` | 控制位数 |
| 回调地址做 SSRF 校验 | 格式合法 ≠ 安全 |

### 6.3 选型速查

| 需求 | 类型 |
| --- | --- |
| 金额 | `Decimal` |
| 时间点 | `datetime`（aware） |
| 日期 | `date` |
| 内部主键 | `UUID` |
| 交易号/单号 | `str` + `pattern` |
| 有限状态 | `Enum` |
| 2–3 个取值 | `Literal` |
| 回调地址 | `HttpUrl` |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[T1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/extra-data-types/ | 特殊类型总览、依赖说明 |
| `[T2]` | 官方文档 | https://docs.pydantic.dev/latest/concepts/types/ | `UUID`/`Enum`/`Literal`/`Url` |
| `[T3]` | 官方文档 | https://docs.python.org/3/library/datetime.html | 时区与 aware/naive |
| `[T4]` | 规范 | https://www.rfc-editor.org/rfc/rfc8259 | JSON number 精度与实现限制 |
| `[T5]` | 官方文档 | https://docs.python.org/3/library/decimal.html | `Decimal` 运算与 `quantize` |
| `[T6]` | 安全 | https://owasp.org/www-community/attacks/Server_Side_Request_Forgery | SSRF |

> **核对状态**：`[T1]`–`[T6]` 为官方文档/规范链接，**本次未逐页直连复核**；所有错误类型、`ctx`、schema `format`、两种序列化路径均为本机实测，`examples/verify.py` 复现 13/13 通过。`Decimal` 除法 `quantize` 行为属标准库语义，本章未单独断言。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] JSON 四种标量如何承载富类型
- [ ] 金额为什么不能用 `float`
- [ ] `max_digits` 与 `decimal_places` 的区别
- [ ] naive 与 aware datetime 的差异
- [ ] 有/无返回注解导致的编码差异
- [ ] `Enum` 与 `Literal` 的取舍

**能写出（代码层）**：

- [ ] 带精度约束的金额字段
- [ ] 带时区的 datetime 字段
- [ ] `Enum` 与 `Literal` 字段
- [ ] `HttpUrl` 字段

**能判断（避坑层）**：

- [ ] 看到 `float` 金额 → 指出精度风险
- [ ] 看到枚举传成员名 → 指出应传值
- [ ] 看到 `datetime` 无时区 → 指出跨时区风险
- [ ] 看到金额出参是数字 → 指出前端丢精度
- [ ] 看到 `HttpUrl` 就放心 → 指出 SSRF

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 13/13
- [ ] `/docs` 里看到 `format: uuid`、`date-time`、`uri`
- [ ] 手工复现 `decimal_max_places`

## 9. 下一章衔接

第 18 章 `局部更新`：本章的类型都在「创建」场景。PATCH 场景要区分「字段没传」与「字段传了 null」，这需要 `exclude_unset`/`exclude_none`，否则「只想改价格」的请求会把其他字段清空。

本章留下的伏笔：

1. 返回模型的字段过滤在第 21 章（也是金额输出形态的最终解法）。
2. `jsonable_encoder` 的完整行为在第 30 章。
3. SSRF 防护在第 49 章（API Key 与外部调用）。
4. 数据库 `Numeric` 类型映射在第 55 章。
