# 19 模型复用 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「什么时候用别名、什么时候用继承、什么时候必须组合、继承到底继承了什么」拆开。学完这章，你要能让三个模型长得像一家人，而不是三份复制粘贴。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1（本机实测） |
| 前置 | 第 13–18 章（模型、约束、嵌套、PATCH） |
| 覆盖范围 | 类型别名、配置基类、字段基类、多模型分工、字段覆盖、MRO、配置合并 |
| 明确不覆盖 | 校验器复用（第 20 章）、响应模型字段过滤（第 21 章）、ORM 映射（M09） |
| 学完验收 | 能跑通 `verify.py` 10/10、能画出 Create/Patch/Read 的继承图、能预判覆盖结果 |

## 0. 怎么用这份文件

**依据约定**：`` `[Rn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 复用的三种手段与边界
2 机制（第 2 节）    → 继承到底继承了什么
3 API（第 3 节）     → 别名 / 配置基类 / 字段基类 / 覆盖
4 边界（第 4 节）    → 配置合并、MRO、别名污染、循环
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 三件套模板
```

## 1. 概念：三种复用手段，三种适用面

| 手段 | 复用对象 | 产生新类 | 典型用法 |
| --- | --- | --- | --- |
| 类型别名 `Annotated[T, Field(...)]` | 类型 + 约束 | ❌ | `Money`、`ShortText`、`Tags` |
| 配置基类 | `model_config` | ✅ | `StrictModel` |
| 字段基类 | 字段定义 | ✅ | `ProductBase` |
| 组合（字段引用） | 整个模型 | ✅ | `Order.product: ProductRead` |

选择顺序（从轻到重）：

```text
只是同一个字段反复出现 → 类型别名
只是配置一致         → 配置基类
字段集合一致、视图不同 → 字段基类 + 继承
两个独立实体         → 组合（嵌套），不要继承
```

反例：为了「复用 2 个字段」建三层继承，最后没人看得懂哪个字段从哪来。**三处重复再抽象。**

## 2. 机制：继承到底继承了什么

```text
class StrictModel(BaseModel):     model_config = {...}
class ProductBase(StrictModel):   name / price / tags
class ProductRead(ProductBase):   + id / created_at
```

| 项目 | 是否继承 | 实测 |
| --- | --- | --- |
| 字段定义 | ✅ | `ProductRead.model_fields` 含 5 个字段 |
| `model_config` | ✅（浅合并，同类键覆盖） | 子类 `extra="forbid"` 生效 |
| `@field_validator` | ✅ | 第 20 章演示 |
| `model_fields` 顺序 | 父类字段在前，子类追加在后 | Read 顺序为 name, price, tags, id, created_at |
| OpenAPI 组件 | 每个类独立成一个 schema | 父子各自成组件，互不内联 |
| 表/数据库结构 | ❌ 完全无关 | 模型继承不产生 ORM 关系 |

## 3. API 逐个拆解

### 3.1 类型别名

```python
Money = Annotated[Decimal, Field(gt=0, max_digits=10, decimal_places=2)]
ShortText = Annotated[str, Field(min_length=1, max_length=32)]
```

| 特性 | 说明 |
| --- | --- |
| 不产生新类 | 只是把 `FieldInfo` 挂到类型上 |
| 处处生效 | Create/Patch/Read 用同一个别名 → 约束完全一致 |
| 修改影响全局 | 改别名 = 改所有使用点，等同公共契约变更 |
| 可嵌套 | `list[ShortText]`、`Annotated[list[ShortText], Field(max_length=5)]` |

### 3.2 配置基类

```python
class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
```

| 注意 | 说明 |
| --- | --- |
| 子类可覆盖单项 | 子类写 `model_config = ConfigDict(extra="ignore")` 会覆盖 `extra`，其余继承？**实测：ConfigDict 是浅合并到父类，同名键覆盖** |
| 不要放字段 | 配置基类只放 `model_config`，避免「基类也有必填字段」的意外 |
| 可放公共校验器 | 第 20 章 |

### 3.3 字段基类与视图拆分

| 模型 | 继承自 | 字段 | 用途 |
| --- | --- | --- | --- |
| `ProductBase` | `StrictModel` | name/price/tags | 公共字段（不直接对外） |
| `ProductCreate` | `ProductBase` | 同基类 | POST 入参 |
| `ProductPatch` | `StrictModel` | 全可选 | PATCH 入参 |
| `ProductRead` | `ProductBase` | +id/created_at | 出参 |

为什么 Patch 不继承 Base：Base 的字段**必填**，而 PATCH 必须能省略。强行继承只能靠重定义全部字段，得不偿失。

### 3.4 字段覆盖

```python
class TighterCreate(ProductCreate):
    name: Annotated[str, Field(min_length=5, max_length=8)]
```

| 行为 | 实测 |
| --- | --- |
| 子类约束生效 | `name="abc"` → `string_too_short` |
| 父类不受影响 | `ProductCreate` 仍是 `min_length=1` |
| 未重写的约束会丢 | 覆盖字段时要**写全**新约束（默认值也要重给） |

## 4. 边界条件

### 4.1 配置合并

| 场景 | 结果 |
| --- | --- |
| 子类不写 `model_config` | 完全继承父类 |
| 子类写 `ConfigDict(extra="ignore")` | 该键被覆盖，其余键仍继承 |
| 多继承两个配了 `model_config` 的父类 | MRO 靠前者优先（**不确定**具体合并细节，本章未专项断言；建议只从一个配置基类继承） |

### 4.2 MRO 与多继承

```python
class Merged(WithNote, WithOtherNote):
    pass

Merged().note   # "from-first"（实测：MRO 第一个父类生效）
```

| 建议 | 理由 |
| --- | --- |
| 只做「单继承字段基类 + 单继承配置基类」 | 可预测 |
| 不允许多个父类定义同名字段 | 读者无法一眼判断来源 |
| 需要混入能力用 `Mixin`（无字段） | 语义清晰 |

### 4.3 别名的污染面

| 变更 | 影响 |
| --- | --- |
| 把 `max_digits` 从 10 改到 12 | 所有用 `Money` 的模型一起变，客户端契约可能被破坏 |
| 新增别名（不修改旧的） | 安全 |

结论：别名一旦发布，按「公共 API」管理，变更走评审与 CHANGELOG。

### 4.4 继承深度

| 深度 | 评价 |
| --- | --- |
| 2–3 层（Strict → Base → View） | ✅ 推荐 |
| 4–5 层 | ⚠️ 需要画图才能维护 |
| 6 层以上 | ❌ 拆成组合，或直接写字段 |

### 4.5 循环引用

`A` 里有 `B`、`B` 里有 `A` 的模型（树形结构）必须用前向引用 + `model_rebuild()`，与「复用」是两件事。本章**不覆盖**，参考 Pydantic Recursive models。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| PATCH 继承必填基类 | 字段全变必填 | Patch 只继承配置基类 | 实测 |
| 字段基类直接对外 | 客户端能传 `id` | 仅 Create/Patch 对外 | `[R1]` |
| 继承 4 层以上 | 字段来源难追 | 控制在 3 层内 | `[R2]` |
| 为复用 2 个字段就抽基类 | 抽象过度 | 重复到第三处再抽 | `[R2]` |
| 子类重定义字段只写部分约束 | 父类约束丢失 | 写全新字段定义 | 实测 |
| 多继承同名字段 | 顺序决定结果 | 避免，或显式重定义 | 实测 |
| 改别名不评估影响 | 所有模型契约同时变 | 按公共 API 变更流程 | `[R3]` |
| 以为继承 = 同一 schema | OpenAPI 出两个组件 | 用 `$ref` 理解 | 实测 |
| 用继承表达实体关系 | 语义错乱 | 组合/嵌套 | `[R4]` |
| 配置基类里写字段 | 所有子类莫名多必填字段 | 配置基类只放 config | `[R3]` |
| 靠继承复用校验器又覆盖它 | 父类行为被意外关闭 | 明确重写并注释 | 第 20 章 |
| `model_config` 写成实例属性 | 不生效 | 必须是类属性 | `[R3]` |
| 直接 `ProductRead(**dict)` 含多余键 | 报 `extra_forbidden` | 先裁剪字段 | 实测 |
| 用 `dict` 手拼响应 | 无校验、无文档 | 用模型 | `[R1]` |
| 在基类加 `created_at` 默认值 | 所有模型都带时间戳 | 只在 Read/ORM 层加 | `[R4]` |
| 继承顺序依赖 Pydantic 内部行为 | 升级可能变 | 显式声明、写测试 | `[R2]` |
| 一个模型同时做入参与出参 | 泄露内部字段 | Create/Read 分离 | 第 21 章 |
| 别名里塞 validator | 不支持 | 校验器放模型 | 第 20 章 |

## 6. 最佳实践与编码建议

### 6.1 三件套 + 两个基类模板

```python
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field

# ① 公共约束：别名
Money = Annotated[Decimal, Field(gt=0, max_digits=12, decimal_places=2)]
ShortText = Annotated[str, Field(min_length=1, max_length=32)]


# ② 公共配置：基类
class StrictModel(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


# ③ 公共字段：基类
class ProductBase(StrictModel):
    name: ShortText
    price: Money


# ④ 三个视图：只写差异
class ProductCreate(ProductBase):
    pass


class ProductPatch(StrictModel):
    name: ShortText | None = None
    price: Money | None = None


class ProductRead(ProductBase):
    id: int
    created_at: datetime
```

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 别名集中放一处 | `schemas/common.py` |
| 配置基类只一个 | 避免合并歧义 |
| 命名带视图后缀 | `Create`/`Patch`/`Read` |
| Base 不对外暴露 | 只作为父类 |
| 子类覆盖要写全 | 约束 + 默认值 |
| 继承层级 ≤3 | 超过就组合 |
| 模型放 `schemas` 包 | 与路由、服务分层（M11） |

### 6.3 选型速查

| 场景 | 做法 |
| --- | --- |
| 同一字段多处用 | 别名 |
| 全项目统一严格模式 | 配置基类 |
| 同资源多视图 | 字段基类 + 继承 |
| 两个资源有关联 | 组合 |
| 需要给某视图加约束 | 子类覆盖 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[R1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/body-nested-models/ | 模型组合与复用 |
| `[R2]` | 官方文档 | https://docs.pydantic.dev/latest/concepts/models/#model-inheritance | 继承、字段覆盖、MRO |
| `[R3]` | 官方文档 | https://docs.pydantic.dev/latest/concepts/config/ | 配置继承与合并 |
| `[R4]` | 官方文档 | https://docs.pydantic.dev/latest/concepts/fields/ | `Annotated` 与类型别名 |

> **核对状态**：`[R1]`–`[R4]` 为官方文档链接，**本次未逐页直连复核**；字段集合、配置继承、MRO 顺序、OpenAPI 组件均为本机实测，`examples/verify.py` 复现 10/10 通过。4.1 中「多继承配置合并细节」**未验证**，已标注。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 三种复用手段的适用面
- [ ] 继承到底继承了什么、没继承什么
- [ ] PATCH 为什么不能继承必填基类
- [ ] 子类覆盖字段时为什么会丢约束
- [ ] MRO 对同名字段的影响

**能写出（代码层）**：

- [ ] 一套类型别名
- [ ] 一个配置基类
- [ ] Create/Patch/Read 三件套
- [ ] 一次字段覆盖

**能判断（避坑层）**：

- [ ] 看到 5 层继承 → 指出该拆
- [ ] 看到 Patch 继承 Base → 指出必填冲突
- [ ] 看到多继承同名 → 指出顺序风险
- [ ] 看到改别名 → 指出全局影响
- [ ] 看到基类带 `id` → 指出越权

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 10/10
- [ ] `/docs` 里 Create 与 Read 是两个组件
- [ ] 手工验证子类覆盖后父类不变

## 9. 下一章衔接

第 20 章 `校验器`：本章复用的是「字段级约束」。真实业务还有跨字段规则（起止时间、密码一致、金额合计），`Field` 表达不了，需要 `@field_validator` / `@model_validator`，并且要处理它们在 422 里的 `loc` 差异。

本章留下的伏笔：

1. 校验器可以被继承与覆盖，第 20 章有专门说明。
2. 响应侧如何用 Read 模型过滤字段，第 21 章。
3. `schemas` 包的目录组织在 M11。
4. 别名与 DB `Numeric` 的精度对齐在 M09。
