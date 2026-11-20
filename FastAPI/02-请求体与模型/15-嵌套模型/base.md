# 15 嵌套模型 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「什么时候该嵌套、`loc` 是怎么拼出来的、内层配置为什么不继承、嵌套多深算过头」拆开。学完这章，你要能设计出让前端**知道具体改哪一行**的请求结构。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1 / Python 3.12.8（本机实测） |
| 前置 | 第 13–14 章（`BaseModel`、`Field` 约束） |
| 覆盖范围 | 模型套模型、模型列表、`loc` 定位、递归校验、内层配置隔离、`$ref` 与 `additionalProperties` |
| 明确不覆盖 | 多参数混用与 `embed`（第 16 章）、模型继承与复用（第 19 章）、跨字段校验（第 20 章） |
| 学完验收 | 能跑通 `verify.py` 11/11、能按 `loc` 定位到元素字段、能说清配置不继承 |

## 0. 怎么用这份文件

**依据约定**：`` `[Nn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 什么时候必须嵌套（值对象 vs 一对多）
2 机制（第 2 节）    → 递归校验 + loc 拼接（重点）
3 API（第 3 节）     → 对象字段 / 模型列表 / 个数约束
4 边界（第 4 节）    → 配置不继承、空值、类型错、深度、性能
5 注意事项（第 5 节）→ 25 条对照
6 最佳实践（第 6 节）→ 三层结构模板
```

## 1. 概念：两种嵌套，两种动机

| 动机 | 例子 | 结构 | 语义 |
| --- | --- | --- | --- |
| **值对象**（从属于父级，不可独立存在） | 地址、金额、时间区间 | `Address` 作为字段 | 父级没有它就不完整 |
| **一对多**（子项可独立存在） | 订单条目、标签 | `list[OrderItem]` | 数量可变，每个都是实体 |

判断标准：

- 子结构**换一个父级就没意义** → 值对象嵌入；
- 子结构**有自己的 id、能单独查询** → 应该拆成独立资源接口，body 里只传 id 列表。

反例（常见设计错误）：

```http
POST /orders
{"items": [{"id": 1, "name": "笔", "price": 9.9}]}
```

商品名和价格是**服务端数据**，客户端传进来就可能被篡改。正确做法是只传 `{"sku": "A-1", "qty": 2}`，价格由服务端查库补全。

## 2. 机制：递归校验与 `loc` 拼接

```text
校验 Order
├─ customer: Customer
│   ├─ name: str
│   └─ address: Address
│       ├─ city: str          ← 出错 → ["body","customer","address","city"]
│       └─ street: str
└─ items: list[OrderItem]
    ├─ [0] OrderItem
    │   ├─ sku: str
    │   └─ price: float       ← 出错 → ["body","items",0,"price"]
    └─ [1] OrderItem ...
```

拼接规则（实测）：

| 层级 | `loc` | 说明 |
| --- | --- | --- |
| 整个 body | `["body"]` | body 缺失或不是对象 |
| 顶层字段 | `["body","customer"]` | 对象字段缺/类型错 |
| 嵌套对象字段 | `["body","customer","address","street"]` | 逐层加字段名 |
| 列表元素字段 | `["body","items",0,"price"]` | 列表层插入**整数下标** |
| 元素本身不是对象 | `["body","items",0]` | 停在下标，不再往下 |

递归校验的两个特性：

1. **错误聚合**：多层同时出错时，一个 422 里各层错误都在（实测：`customer.name` + `customer.address.street` 两条）。
2. **深度优先**：内层全过才构造内层实例，全过才构造外层实例——函数体不可能拿到「半成品」。

`model_dump()` 同样是递归的：`order.items[0]` 是 `OrderItem` 实例，但 `order.model_dump()["items"][0]` 是普通 dict。

## 3. API 逐个拆解

### 3.1 三种嵌套写法

```python
class Order(BaseModel):
    customer: Customer                                        # 对象（必填）
    shipping: Address | None = None                            # 对象（可选）
    items: list[OrderItem]                                     # 模型列表
    tags: Annotated[list[str], Field(max_length=5)] = []       # 标量列表
    meta: dict[str, str] = {}                                  # 字典
```

| 写法 | 约束写在哪 | 注意 |
| --- | --- | --- |
| `customer: Customer` | 子模型内部 | 必填对象；`null` → 422 |
| `shipping: Address \| None = None` | 同上 | 可选；传 `null` 合法 |
| `items: list[OrderItem]` | 子模型内部 + 列表层 | 列表层用 `min_length`/`max_length` |
| `items: Annotated[list[OrderItem], Field(min_length=1, max_length=5)]` | 两层都要 | 个数与元素内容是两回事 |
| `meta: dict[str, str]` | 键值类型 | 键不可枚举时用；业务字段优先显式模型 |

### 3.2 约束的分层

| 想约束 | 写在哪 | 示例 |
| --- | --- | --- |
| 至少 1 个条目 | 列表层 | `Field(min_length=1)` |
| 最多 5 个条目 | 列表层 | `Field(max_length=5)` |
| 每个 sku 的格式 | 元素模型内 | `Field(pattern=...)` |
| 每个条目的数量范围 | 元素模型内 | `Field(ge=1, le=999)` |
| 不允许条目里有多余字段 | 元素模型内 | `model_config = ConfigDict(extra="forbid")` |

**关键**：列表层的约束与元素层的约束互不替代，必须分别写。

### 3.3 OpenAPI 产出（实测）

```text
Order.properties.customer        -> {"$ref": "#/components/schemas/Customer"}
Order.properties.items           -> {"items": {"$ref": ".../OrderItem"}, "type": "array",
                                     "minItems": 1, "maxItems": 5}
Order.additionalProperties       -> false        ← 来自外层 extra="forbid"
components.schemas               -> Address / Customer / OrderItem / Order
```

| 观察 | 含义 |
| --- | --- |
| 每个模型独立成组件 | 前端可用工具生成类型（`datamodel-code-generator` 等） |
| 嵌套用 `$ref` 而非内联 | 结构复用时不会重复膨胀 |
| `additionalProperties: false` | 只有配了 `extra="forbid"` 的模型才有 |
| `minItems`/`maxItems` | 直接映射到前端表单的「至少/最多几条」 |

## 4. 边界条件

### 4.1 内层配置**不继承**（实测，最容易误判）

```python
class Order(BaseModel):
    model_config = ConfigDict(extra="forbid")   # 只管 Order 自己的字段
    items: list[OrderItem]                      # OrderItem 没配 → 默认 ignore
```

| 请求 | 结果 |
| --- | --- |
| 外层多传 `hack` | 422 `extra_forbidden`，`loc=["body","hack"]` |
| 元素内多传 `hack` | **200**，`hack` 被静默丢弃 |

结论：`model_config` 是**每个模型自己的**。要全局严格，就每个模型都写，或用基类统一（第 19 章）。

### 4.2 空值与空集合

| 输入 | 结果 |
| --- | --- |
| `items: []` + `min_length=1` | 422 `too_short`，`loc=["body","items"]` |
| `items: []` + 无约束 | 200（空数组合法） |
| `customer: null` | 422（字段不是可选） |
| `customer: {}` | 422，逐个子字段报 `missing` |
| `items: {"sku": ...}`（对象当列表） | 422 `list_type`，`loc=["body","items"]` |
| 元素传字符串 | 422 `model_attributes_type`，`loc=["body","items",0]` |

### 4.3 深度与规模

| 维度 | 建议 | 原因 |
| --- | --- | --- |
| 嵌套深度 | ≤ 4 层 | 再深前端难渲染、错误难定位、日志难读 |
| 列表元素上限 | 一定设 `max_length` | 未设上限时一次可传任意多条，内存与 CPU 都被放大 |
| 单条 body 大小 | 由网关限制（如 1MB） | 框架不做限制，`request.json()` 会全量读入内存 |
| 校验开销 | 与元素数量线性相关 | 大批量导入用「分批接口 + 后台任务」，别用一个 POST 传几万条 |

> 关于递归深度：Pydantic 能处理多层嵌套，但**具体上限取决于 Python 递归限制与实现**，本章未做压力测试，**不确定**精确阈值。工程上限制在 4 层以内不需要关心这个上限。

### 4.4 循环引用模型

「分类有子分类」这类自引用是合法的建模需求，但本章不展开：它涉及前向引用（`from __future__ import annotations` 或字符串标注）与模型重建，且会让 OpenAPI 出现自引用 `$ref`。需要时参考 `[N2]` 的「Recursive models」，并注意 FastAPI 下 `model_rebuild()` 的调用时机。

### 4.5 与「多参数」的边界

本章的嵌套全部在 **body 内部**。如果业务需要「路径参数 + 查询参数 + body」同时出现，那是第 16 章的内容；body 之外的结构（query/header）**不支持**模型嵌套（第 09 章已说明查询参数模型不能嵌套）。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 以为外层 `extra="forbid"` 管内层 | 内层多余字段 200 静默丢弃 | 每层都配 | 实测 |
| 用 `list[dict]` 代替 `list[Model]` | 元素内容零校验 | 用模型 | `[N1]` |
| 列表不设 `max_length` | 可传任意条数 | 设上限 | 实测 |
| 以为 `loc` 下标是字符串 | 实测是整数 `0` | 前端按 int 处理 | 实测 |
| 只看 `loc[0]` 判断错误 | `loc[0]` 恒为 `body` | 继续读后续段 | 实测 |
| 元素传字符串 | 422 `model_attributes_type` | 客户端传对象 | 实测 |
| 对象当列表传 | 422 `list_type` | 保证是数组 | 实测 |
| 用空列表表达「没有」却配了 `min_length=1` | 422 `too_short` | 明确「至少几条」 | 实测 |
| 嵌套 6 层以上 | 前端/日志/文档都难用 | 拆接口或扁平化 | `[N3]` |
| 让客户端传价格/名称 | 可被篡改 | 只传 id/sku + 数量 | 第 19 章 |
| 用 `dict[str, Any]` 接复杂结构 | 等于放弃校验 | 显式模型 | `[N1]` |
| 内层模型复用外层配置假设 | 配置不继承 | 基类统一（第 19 章） | `[N2]` |
| 用一个 POST 传上万条 | 内存/CPU 双爆 | 批量 + 后台任务（第 70 章） | `[N3]` |
| 递归模型不 `model_rebuild()` | 前向引用解析失败 | 参考官方 Recursive models | `[N2]` |
| 嵌套模型字段名与父级同名 | 日志里难区分 | 命名带语义前缀 | `[N4]` |
| `items: list[OrderItem] = []` 可变默认 | 依赖 Pydantic 的默认值复制 | 统一 `default_factory` | `[N2]` |
| 深层错误只回 `loc[0]` | 前端无法定位 | 完整回传 `loc`（脱敏后） | 第 33 章 |
| 把 `$ref` 当内联结构读 | 看不到字段 | 去 `components.schemas` 查 | `[N5]` |
| 手写 OpenAPI 描述嵌套 | 与模型脱节 | 让模型生成 | `[N5]` |
| 内层字段用 `Optional` 滥用 | 契约变模糊 | 只有真可选才 `None` | `[N2]` |
| 嵌套里放二进制/base64 | body 膨胀 | 用文件上传（第 28 章） | `[N6]` |
| 嵌套结构里放分页参数 | 语义混乱 | 分页放 query（第 42 章） | `[N4]` |
| 元素数量与业务上限不一致 | 应用放行、业务报错 | 上限写进模型 | `[N3]` |
| 只测 happy path | 嵌套错误定位没验证过 | 每个 `loc` 层级都写测试 | 第 71 章 |
| 嵌套模型直接当响应返回 | 可能泄露内部字段 | `response_model`（第 21 章） | `[N5]` |
| 嵌套里的时间字段用无时区字符串 | 跨时区数据错位 | 统一 UTC + 偏移 | 第 17 章 |

## 6. 最佳实践与编码建议

### 6.1 三层结构模板

```python
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class StrictModel(BaseModel):
    """统一严格基类：子模型自动继承配置（第 19 章展开）。"""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class OrderItemIn(StrictModel):
    sku: Annotated[str, Field(pattern=r"^[A-Z]-\d+$")]
    qty: Annotated[int, Field(ge=1, le=999)]


class CustomerIn(StrictModel):
    name: Annotated[str, Field(min_length=1, max_length=32)]
    phone: Annotated[str, Field(pattern=r"^1\d{10}$")]


class OrderCreate(StrictModel):
    customer: CustomerIn
    items: Annotated[list[OrderItemIn], Field(min_length=1, max_length=50)]
    note: Annotated[str | None, Field(max_length=200)] = None
```

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 先画结构再写模型 | 值对象 vs 一对多决定用字段还是列表 |
| 客户端只传「不可推导」的数据 | 价格/名称/状态由服务端补 |
| 每层都配 `extra` | 配置不继承 |
| 列表必设上限 | 防放大攻击 |
| 层级 ≤ 4 | 超过就拆接口 |
| 元素模型加 `In`/`Out` 后缀 | 与响应模型区分（第 21 章） |
| 用 `$ref` 生成前端类型 | 契约单一来源 |
| 错误回传完整 `loc` | 前端能精确高亮 |

### 6.3 结构选型速查

| 需求 | 结构 |
| --- | --- |
| 地址、金额区间 | 值对象字段 |
| 订单条目、明细 | `list[Model]` |
| 动态键（如多语言文案） | `dict[str, str]` |
| 二选一结构 | `Union[A, B]`（第 23 章） |
| 大量条目导入 | 独立批量接口 + 后台任务 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[N1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/body-nested-models/ | 嵌套模型、模型列表、`dict` |
| `[N2]` | 官方文档 | https://docs.pydantic.dev/latest/concepts/models/ | 递归模型、配置继承、默认值 |
| `[N3]` | 工程实践 | https://fastapi.tiangolo.com/zh/tutorial/background-tasks/ | 大批量任务放后台 |
| `[N4]` | 规范 | https://restfulapi.net/resource-naming/ | 资源与子资源划分 |
| `[N5]` | 规范 | https://spec.openapis.org/oas/v3.1.0#schema-object | `$ref`、`additionalProperties` |
| `[N6]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/request-files/ | 文件不用 base64 塞 body |

> **核对状态**：`[N1]`–`[N6]` 为官方文档/规范链接，**本次未逐页直连复核**；`loc` 结构、错误类型、schema 输出均为本机实测，`examples/verify.py` 复现 11/11 通过。4.4 的递归模型细节**未实测**，文中已标注。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 值对象与一对多的区别，以及各自在 body 里怎么表达
- [ ] `loc` 的四段/五段是怎么拼出来的
- [ ] 为什么列表元素用整数下标
- [ ] 内层配置为什么不继承外层
- [ ] 嵌套层级与性能/可维护性的取舍

**能写出（代码层）**：

- [ ] 三层嵌套模型
- [ ] 带个数约束的模型列表
- [ ] 可选嵌套字段
- [ ] 每层 `extra="forbid"` 的严格模型

**能判断（避坑层）**：

- [ ] 看到 `list[dict]` → 指出零校验
- [ ] 看到外层 forbid 就以为内层安全 → 指出不继承
- [ ] 看到列表无上限 → 指出放大攻击
- [ ] 看到客户端传价格 → 指出篡改风险
- [ ] 看到嵌套 6 层 → 指出该拆

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 11/11
- [ ] `/docs` 里看到 `Order` 的 `$ref` 与 `minItems`
- [ ] 手工制造一次元素级错误，读出带下标的 `loc`

## 9. 下一章衔接

第 16 章 `多参数与 embed`：本章所有结构都在**一个** body 参数里。真实接口常常同时需要「路径里的 id + 查询里的来源 + body 里的内容」，还要处理「多个 body 参数」被自动包装成 `{"item": ..., "user": ...}` 的行为，以及 `Body(embed=True)` 强制包装。

本章留下的伏笔：

1. 统一严格基类在第 19 章（模型复用与继承）。
2. 嵌套里的跨字段规则（条目总价校验）在第 20 章。
3. 批量导入的后台任务在第 70 章。
4. 完整的 422 契约与脱敏在第 33–34 章。
