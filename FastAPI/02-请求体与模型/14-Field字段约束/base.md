# 14 Field 字段约束 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「约束写在哪、什么时候执行、422 的 `ctx` 怎么读、哪些约束看起来能用其实不该用」拆开。学完这章，你要做到：**函数体里不再出现字段级 `if`**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1 / Python 3.12.8（本机实测） |
| 前置 | 第 13 章（`BaseModel` 声明 body） |
| 覆盖范围 | `Field` 长度/数值/正则/别名/示例、`Annotated` 写法、`ctx` 解读、JSON Schema 映射、`model_config` |
| 明确不覆盖 | 嵌套与列表模型（第 15 章）、跨字段校验器（第 20 章）、特殊类型（第 17 章）、响应模型（第 21 章） |
| 学完验收 | 能跑通 `verify.py` 10/10、能预测 `type` 与 `ctx`、能说清 `populate_by_name` 的坑 |

## 0. 怎么用这份文件

**依据约定**：`` `[Fn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 约束是「契约」，不是业务逻辑
2 机制（第 2 节）    → 约束在流水线的哪一步执行
3 API（第 3 节）     → 参数表 + 两种写法 + model_config
4 边界（第 4 节）    → None / list / 长度计数 / 数值 / 正则风险
5 注意事项（第 5 节）→ 24 条对照
6 最佳实践（第 6 节）→ 一份可直接抄的强约束模型
```

## 1. 概念：约束是契约的一部分

同一件事有三种落点，代价完全不同：

| 落点 | 谁看得见 | 何时失败 | 422 结构 | 可复用 |
| --- | --- | --- | --- | --- |
| 前端表单校验 | 前端 | 提交前 | 无 | ❌ |
| `Field` 约束 | **所有人（含 `/docs`）** | 进函数前 | 统一 | ✅ |
| 函数体 `if` | 只有后端 | 进函数后 | 你要自己造 | ❌ |

约束的本质是：**把「什么算合法」变成接口契约的一部分**，让文档、校验、错误信息三处自动一致。

`Field` 与 `Path`/`Query`/`Header`/`Cookie` 共享同一批约束参数（都来自 Pydantic 的 `FieldInfo`），区别只是作用对象：`Field` 用于模型字段，其余用于函数参数。

## 2. 机制：约束在流水线的哪一步

```text
① 类型校验/转换（lax）
   "9.9" → float 9.9
   类型不符 → *_type，**约束不再执行**

② 约束校验
   min_length/max_length/gt/ge/lt/le/pattern
   违反 → string_too_short / greater_than / string_pattern_mismatch...

③ 其他字段规则
   extra 策略、跨字段校验器（第 20 章）

④ 构造实例 → 注入函数
```

两条推论：

- **类型错优先于约束错**：`price="abc"` 报 `float_parsing`，不会报 `greater_than`。
- **`None` 会短路约束**：可选字段传 `null` 时，长度/正则/范围全都不执行（实测 4.7）。

实测错误样本：

```text
name="笔"        → {"type":"string_too_short","loc":["body","name"],"ctx":{"min_length":2}}
price=0          → {"type":"greater_than","loc":["body","price"],"ctx":{"gt":0.0}}
price=100000.01  → {"type":"less_than_equal","ctx":{"le":100000.0}}
sku="abc-1234"   → {"type":"string_pattern_mismatch","ctx":{"pattern":"^[A-Z]{3}-\\d{4}$"}}
tags=[4 个元素]   → {"type":"too_long","ctx":{"max_length":3,"actual_length":4}}
```

## 3. API 逐个拆解

### 3.1 约束参数表

| 参数 | 作用对象 | 含义 | 违反时 `type` |
| --- | --- | --- | --- |
| `min_length` | `str` | 最少字符数 | `string_too_short` |
| `max_length` | `str` | 最多字符数 | `string_too_long` |
| `min_length` | `list` / `set` | 最少**元素个数** | `too_short` |
| `max_length` | `list` / `set` | 最多**元素个数** | `too_long` |
| `gt` / `ge` | 数值 | 大于 / 大于等于 | `greater_than` / `greater_than_equal` |
| `lt` / `le` | 数值 | 小于 / 小于等于 | `less_than` / `less_than_equal` |
| `pattern` | `str` | 正则 | `string_pattern_mismatch` |
| `alias` | 任意 | 对外字段名 | 用错名 → `missing` |
| `description` | 任意 | `/docs` 描述 | — |
| `examples` | 任意 | `/docs` 示例列表 | — |
| `deprecated` | 任意 | 文档标记废弃 | 不拦截请求 |
| `default_factory` | 可变类型 | 默认值工厂 | — |
| `json_schema_extra` | 任意 | 追加 schema 字段 | — |

### 3.2 两种写法：默认值与 `Annotated`

```python
# 写法 A（旧）：Field 直接当默认值
name: str = Field(min_length=2)
note: str | None = Field(default=None, max_length=100)

# 写法 B（推荐）：Annotated 放约束，默认值单独给
name: Annotated[str, Field(min_length=2)]
note: Annotated[str | None, Field(max_length=100)] = None
```

| 对比项 | 写法 A | 写法 B |
| --- | --- | --- |
| 类型检查器友好 | 一般 | **好**（类型仍是 `str`） |
| 约束可复用 | 否 | 可抽成类型别名（第 19 章） |
| 必填写法 | `Field(...)` 省略号 | 不写默认值 |
| 官方推荐 | — | ✅ |

**不要混用两种风格**：同一模型里出现 `x: str = Field(...)` 和 `y: Annotated[str, Field(...)]` 会让读者不停切换心智。

### 3.3 `model_config` 常用项

`model_config` 是**类属性**，不是 `Field` 参数：

```python
from pydantic import BaseModel, ConfigDict


class Strict(BaseModel):
    model_config = ConfigDict(
        extra="forbid",              # 拒绝多余字段（第 13 章）
        populate_by_name=True,       # 别名与字段名都收
        str_strip_whitespace=True,   # 字符串自动 strip
        frozen=True,                 # 不可变（内部 DTO 用）
    )
```

| 配置 | 作用 | 常见误用 |
| --- | --- | --- |
| `extra` | 多余字段策略 | 写成 `Field(extra=...)` |
| `populate_by_name` | 允许字段名代替别名 | 写成 `Field(populate_by_name=True)`（实测无效） |
| `str_strip_whitespace` | 自动去首尾空格 | 以为 `min_length` 会先 strip |
| `frozen` | 禁止赋值 | 以为能防住嵌套可变对象 |

## 4. 边界条件

### 4.1 `None` 会短路所有约束（实测）

```python
note: Annotated[str | None, Field(min_length=5)] = None
```

| 输入 | 结果 |
| --- | --- |
| `null` | 200（`note=None`，`min_length` 不执行） |
| `"abc"` | 422 `string_too_short` |
| 不传 | 200（默认 `None`） |

所以「可选但非空」用 `Field` 表达不了，需要校验器或「空串视为不传」的约定（第 20 章）。

### 4.2 长度约束的计数单位

| 场景 | 行为 |
| --- | --- |
| `str` 的 `min_length` | 按 Python `len()` = Unicode 码点计数 |
| emoji / 组合字符 | 一个 emoji 可能是多个码点，长度与「用户感知字数」不一致 |
| `list` 的 `max_length` | 元素个数 |
| 元素内部约束 | `list[Annotated[str, Field(max_length=10)]]`（第 08 章同款） |

> 需要「按用户看到的字数」限制时，只能在校验器里自己算，`Field` 做不到。

### 4.3 数值边界

| 约束 | 含义 | 实测 |
| --- | --- | --- |
| `gt=0` | 严格大于 | `0` → 422；`0.01` → 200 |
| `ge=0` | 大于等于 | `0` → 200 |
| `le=100000` | 小于等于 | `100000` → 200；`100000.01` → 422 |

注意：

- `int` 与 `float` 的边界值在 `ctx` 里会显示成 `0.0` 这类浮点形式，属正常。
- 金额不要用 `float` + `le`：精度误差不会因约束而消失，用 `Decimal`（第 17 章）。
- 大整数（超过 2^53）在 JSON 里可能丢精度，涉及订单号/trace id 建议用字符串。

### 4.4 正则的三个坑

| 坑 | 说明 |
| --- | --- |
| 未加锚点 | 是否允许子串匹配依赖底层实现，**一律写 `^...$`** |
| 灾难性回溯 | 复杂嵌套量词可被构造输入打成 CPU 100%（ReDoS） |
| 用正则校验邮箱 | 永远写不全，用 `EmailStr`（需 `email-validator`） |

稳妥做法：正则保持**简单 + 有长度上限**，复杂规则放业务层。

### 4.5 空白字符

| 配置 | 行为 |
| --- | --- |
| 默认 | `"  钢笔  "` 原样保留，`min_length=2` 也算通过 |
| `str_strip_whitespace=True` | 先 strip 再校验 |

不确定点（明确标注）：strip 与长度约束的**精确执行顺序**本章未做专项断言，只验证了「不配置时不去空格」。需要严格保证时，用第 20 章的校验器显式处理。

### 4.6 约束与 OpenAPI 的映射（实测）

```text
name  -> {"type":"string","minLength":2,"maxLength":20,"examples":["机械键盘"]}
price -> {"type":"number","exclusiveMinimum":0.0,"maximum":100000.0}
tags  -> {"type":"array","maxItems":3}
sku   -> {"type":"string","pattern":"^[A-Z]{3}-\\d{4}$","examples":["ABC-1234"]}
required -> ["name","price","sku"]
```

> 前端可以直接把 JSON Schema 交给表单库生成校验规则，**这是「约束写在模型里」的最大收益**。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `Field(populate_by_name=True)` | `DeprecationWarning` 且无效，字段名仍 422 | 写进 `model_config` | 实测 |
| `list` 上 `max_length=3` 以为限字符 | 限的是元素个数 | 元素级用 `list[Annotated[str, Field(...)]]` | 实测 |
| 以为 `null` 会触发约束 | 实测 200，约束跳过 | 必填或校验器 | 实测 |
| `pattern` 不加 `^...$` | 匹配语义不确定 | 加锚点 | 实测 |
| `gt=0` 却想允许 0 | `0` → 422 | `ge=0` | 实测 |
| 未配 `populate_by_name` 又传字段名 | 422 `missing`，`loc` 用别名 | 配 `model_config` 或统一别名 | 实测 |
| `model_dump()` 直接返回 | 输出内部字段名 | `model_dump(by_alias=True)` | 实测 |
| `name: str = None` | 类型不符 | `str \| None = None` | `[F2]` |
| 只在前端校验 | 后端无约束，绕过即脏数据 | 后端 `Field` 独立校验 | `[F1]` |
| 约束写在函数体 | 文档看不到、422 不统一 | 移到模型 | `[F1]` |
| 以为 `min_length` 会 strip | 空格也算长度 | `str_strip_whitespace` | `[F4]` |
| 用 `pattern` 约束数值 | 数值类型没有 pattern | 用 `ge`/`le` | `[F2]` |
| 金额用 `float` + `le` | 精度误差仍在 | `Decimal` | `[F3]` |
| 大整数直接传 JSON number | 超 2^53 丢精度 | 传字符串 | `[F3]` |
| 复杂正则防注入 | ReDoS，CPU 打满 | 简单正则 + 长度上限 | `[F6]` |
| 用 `pattern` 校验邮箱 | 覆盖不全、误杀 | `EmailStr`（需依赖） | `[F2]` |
| `examples` 塞几十条 | `/docs` 臃肿 | 1–2 条代表值 | `[F1]` |
| `description` 中英混杂 | 文档难读 | 统一语言与术语 | `[F1]` |
| `alias` 用中文 | 部分客户端/网关不兼容 | 英文 + 文档说明 | `[F4]` |
| 应用约束与 DB 约束不一致 | 应用放行、DB 报错 500 | 以一处为准并对齐 | 第 55 章 |
| 只约束 body 不约束 query | 同一业务两套标准 | 约束参数与字段用同一套规则 | 第 08 章 |
| 用 `deprecated` 字段 | 文档标废弃但请求仍生效 | 设过渡期 + 监控调用量 | `[F2]` |
| `= []` 与 `default_factory=list` 混用 | 团队风格不一 | 统一 `default_factory` | `[F2]` |
| 在 `Annotated` 里写 `Field(...)` 省略号 | 省略号是旧写法的「必填」标记 | 不写默认值即可 | `[F1]` |
| 把「可空」当成「可空串」 | `null` 通过，但 `""` 长度 0 仍会 422 | 明确 `null` 与 `""` 的语义 | 实测 |

## 6. 最佳实践与编码建议

### 6.1 一份强约束模型模板

```python
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

Money = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
Sku = Annotated[str, Field(pattern=r"^[A-Z]{3}-\d{4}$")]


class ProductCreate(BaseModel):
    """商品创建入参。所有字段级规则都在这里，service 只处理业务规则。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: Annotated[str, Field(min_length=2, max_length=20, examples=["机械键盘"])]
    price: Money
    sku: Sku
    tags: Annotated[list[Annotated[str, Field(min_length=1, max_length=10)]], Field(max_length=3)] = []
```

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 约束与字段同处声明 | 读模型即读契约 |
| 把常用约束抽成类型别名 | `Money`、`Sku`、`Slug`（第 19 章展开） |
| 每个字段写 `description` | `/docs` 是交付物 |
| `examples` 给 1–2 条 | 能直接点「Try it out」 |
| 数值边界成对写 | `ge`/`le` 一起给，别只给一半 |
| 字符串一律给上限 | 防止超长输入打满内存/DB |
| 正则保持简单 | 复杂规则放校验器 |
| 约束与 DB 对齐 | 迁移里同步长度/精度 |

### 6.3 选型速查

| 想表达 | 用什么 |
| --- | --- |
| 必填 | 不写默认值 |
| 可空 | `T \| None = None` |
| 非空字符串 | `min_length=1` |
| 枚举 | `Literal["a","b"]` 或 `Enum`（第 17 章） |
| 跨字段规则 | `model_validator`（第 20 章） |
| 外部字段名 | `alias` + `populate_by_name` |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[F1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/body-fields/ | `Field` 在 FastAPI 中的用法、`Annotated` |
| `[F2]` | 官方文档 | https://docs.pydantic.dev/latest/concepts/fields/ | `Field` 全参数、`alias`、`default_factory` |
| `[F3]` | 官方文档 | https://docs.pydantic.dev/latest/concepts/types/ | 数值类型、`Decimal`、转换行为 |
| `[F4]` | 官方文档 | https://docs.pydantic.dev/latest/api/config/ | `ConfigDict`（`populate_by_name`、`str_strip_whitespace`） |
| `[F5]` | 规范 | https://json-schema.org/understanding-json-schema/reference/ | 约束到 JSON Schema 的映射 |
| `[F6]` | 安全 | https://owasp.org/www-community/attacks/Regular_expression_Denial_of_Service_-_ReDoS | 正则拒绝服务 |

> **核对状态**：`[F1]`–`[F6]` 为官方文档/规范链接，**本次未逐页直连复核**；所有错误结构、边界值、schema 映射均为本机实测，`examples/verify.py` 复现 10/10 通过。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 约束为什么要写在模型里而不是函数体
- [ ] 类型错与约束错的先后顺序
- [ ] `None` 为什么跳过约束
- [ ] `list` 的 `max_length` 与元素约束的区别
- [ ] `gt`/`ge` 与 `lt`/`le` 的语义
- [ ] `populate_by_name` 为什么不能写在 `Field` 里

**能写出（代码层）**：

- [ ] 一份带长度/范围/正则的模型
- [ ] 元素级约束的 `list`
- [ ] `alias` + `model_config` 的模型
- [ ] `model_dump(by_alias=True)` 的输出

**能判断（避坑层）**：

- [ ] 看到 `list` 上 `max_length` → 指出是元素个数
- [ ] 看到 `pattern` 无锚点 → 指出匹配语义风险
- [ ] 看到 `note=null` 通过 → 指出约束被短路
- [ ] 看到 `Field(populate_by_name=True)` → 指出无效
- [ ] 看到金额 `float` → 指出精度问题

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 10/10
- [ ] `/docs` 的 schema 里看到 `minLength`/`maxItems`/`examples`
- [ ] 手工触发一次 `string_too_short`，读出 `ctx`

## 9. 下一章衔接

第 15 章 `嵌套模型`：本章的字段都是标量或标量列表。真实业务里「订单包含多个商品条目」需要模型套模型、模型套列表，那时 `loc` 会变成三段（`["body","items",0,"price"]`），`$ref` 会出现在 OpenAPI 组件里。

本章留下的伏笔：

1. 类型别名（`Money`/`Sku`）的复用与继承在第 19 章。
2. 跨字段约束（密码一致、起止时间）在第 20 章。
3. `Decimal`/`UUID`/`datetime` 的具体写法在第 17 章。
4. 响应侧的字段过滤在第 21 章。
