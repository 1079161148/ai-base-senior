# 21 响应模型 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「响应模型在哪一步介入、白名单如何生效、什么时候 500、`exclude_*` 的边界」拆开。学完这章，你要能设计出「即使业务代码写错也不会泄露字段」的出参结构。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1（本机实测） |
| 前置 | 第 13–20 章（模型、约束、复用、校验器） |
| 覆盖范围 | `response_model`、返回注解、`exclude_*` 系列、`from_attributes`、响应校验失败、OpenAPI |
| 明确不覆盖 | 状态码控制（第 22 章）、响应头（第 24 章）、直接返回 `Response`（第 25 章）、自定义 OpenAPI（第 26 章） |
| 学完验收 | 能跑通 `verify.py` 10/10、能预测每个参数组合的输出、能解释 500 的来源 |

## 0. 怎么用这份文件

**依据约定**：`` `[On]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 为什么必须入出分离
2 机制（第 2 节）    → 响应模型在请求生命周期哪一步介入了
3 API（第 3 节）     → 7 个参数逐个拆
4 边界（第 4 节）    → 校验失败、exclude 组合、性能、泄漏面
5 注意事项（第 5 节）→ 21 条对照
6 最佳实践（第 6 节）→ 出参模型模板
```

## 1. 概念：入参是「敢不敢收」，出参是「能不能给」

| 方向 | 由谁控制 | 出错后果 |
| --- | --- | --- |
| 请求 → 服务 | 请求模型 + 校验器 | 422，客户端问题 |
| 服务 → 响应 | `response_model` | 字段多 → 泄露；字段缺/类型错 → 500 |

两者的关系是**白名单**与**黑名单**的本质区别：

```text
黑名单思路：「我 return 时小心一点，不带 password」
白名单思路：「出参模型里根本没有 password 这个字段」  ← 唯一可靠
```

实测：函数返回 `{"username","email","nickname","password","hashed_password","internal_note","debug"}`，响应只剩 `username/email/nickname`。

## 2. 机制：请求生命周期里的位置

```text
请求 → 路由匹配 → 依赖注入 → 请求模型校验（422）
     → 你的函数执行 → 返回值
     → 响应模型校验 + 序列化（失败 500）   ← 本章
     → JSON 编码 → 响应
```

关键点：

| 事实 | 含义 |
| --- | --- |
| 响应模型校验在函数返回**之后** | 函数里已经发生的副作用（写库）不会回滚 |
| 失败抛 `ResponseValidationError` | 默认 500，body 是 `Internal Server Error` |
| 多余字段**静默丢弃** | 不报错、不告警，容易被漏测 |
| 缺字段**不静默** | 必填缺失直接 500 |

所以「多字段」是安全默认，「少字段」是事故来源。

## 3. API 逐个拆解

### 3.1 `response_model` 参数 vs 返回注解

| 写法 | 优先级 | 适用 |
| --- | --- | --- |
| `@app.get(..., response_model=X)` | 高 | 需要额外参数（exclude 等）时 |
| `def f() -> X` | 低 | 简单场景，少写一个参数 |

实测：同时存在 `response_model=TinyOut` 与 `-> UserOut`，输出是 `TinyOut`（只有 `username`）。

注意 `-> X` 也会被 FastAPI 用作响应模型，这不是「类型注解仅供阅读」——它会真的过滤字段。

### 3.2 `exclude_*` 三个参数

| 参数 | 作用 | 是否影响校验 |
| --- | --- | --- |
| `response_model_exclude={"f"}` | 输出时去掉 f | ❌ 不影响 |
| `response_model_exclude_unset=True` | 没被赋值过的字段不输出 | ❌ 不影响（必填缺失仍 500） |
| `response_model_exclude_none=True` | 值为 None 的字段不输出 | ❌ 不影响 |

实测两条：

```text
post /users/1/slim      → {"username","nickname"}          # exclude email
get  /users/1/partial   → {"username"}                     # exclude_unset + 可选模型
get  /users/1/force-strict → 500                          # exclude_unset + 必填 email
```

第三条是本课最容易被误解的点：`exclude_unset` 是**序列化**参数，不是**校验**开关。

### 3.3 `include` / 组合

| 组合 | 结果 |
| --- | --- |
| `include={"a","b"}` | 只输出 a、b（仍需通过模型校验） |
| `include` + `exclude` | 先 include 再 exclude，易产生空对象 |
| `exclude_unset` + `exclude_none` | 交集：出现且不为 None |

不建议在业务代码里大量用 include/exclude——出参结构应该由模型定义，而不是每个端点写一份参数。

### 3.4 `from_attributes`

```python
class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    amount: Decimal
```

| 输入 | 结果（实测） |
| --- | --- |
| `SimpleNamespace(id=1, amount=Decimal("19.90"), note=None, secret_token="x")` | `{"id":1,"amount":"19.90","note":null}` |
| `dict` | 也可以 |
| ORM 对象 | 需要 `from_attributes=True` |

注意：`Decimal` 在响应模型下序列化为**字符串**；`secret_token` 因不在模型里被丢弃。

## 4. 边界条件

### 4.1 响应校验失败的几种触发

| 触发 | 结果 |
| --- | --- |
| 缺必填字段 | 500，日志里 `{'type':'missing','loc':('response','email')}` |
| 类型不符（`"abc"` → `int`） | 500 |
| 返回 `None` 但模型不是 Optional | 500 |
| 返回 list 但模型是单个 | 500 |
| `exclude_unset` + 必填缺失 | 500（实测） |

### 4.2 500 之后会发生什么

| 关注点 | 事实 |
| --- | --- |
| 客户端 | 只看到 `Internal Server Error`，没有字段级信息 |
| 服务端日志 | 有完整 `ResponseValidationError` 与字段路径 |
| 是否回滚已写数据 | **不会** |
| 是否可被客户端触发 | 能（构造让服务端返回非法数据的入参）→ 属于「服务端 bug 被客户端触发」 |

### 4.3 性能

| 事实 | 影响 |
| --- | --- |
| 响应模型每次都做一次完整校验 | 大响应体有 CPU 开销 |
| `exclude_*` 是序列化阶段过滤 | 不影响校验成本 |
| 大列表 `list[X]` | 逐元素校验，10k 条明显变慢 |

取舍：内部微服务之间可以省掉严格响应模型换吞吐；对外接口不要省。

### 4.4 泄漏面清单

| 容易漏的字段 | 建议 |
| --- | --- |
| 密码哈希 | 绝不进出参模型 |
| 内部状态（`deleted_at`、`review_note`） | 单独内部模型 |
| 其它租户 id | 出参不返回，避免越权猜测 |
| 自增 id → 可枚举 | 对外用 UUID |
| 错误堆栈 | 别塞进 detail |

### 4.5 docstring 会进 OpenAPI

实测：`UserOut` 的 docstring 变成 schema 的 `description`。这意味着：

| 风险 | 说明 |
| --- | --- |
| 内部说明被公开 | 「这里故意不带 password」出现在 `/openapi.json` |
| 敏感词被扫描 | 断言「schema 里没有 password」会误报 |

写 docstring 时当成公开文档写。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 复用入参模型作出参 | 密码泄露 | 单独出参模型 | 实测 |
| 依赖「我 return 时没带」 | 某个分支顺手带上就泄露 | 白名单兜底 | 实测 |
| `exclude_unset` 想省掉必填 | 500 | 用字段可选的出参模型 | 实测 |
| 以为响应校验失败是 422 | 客户端拿到 500 | 500 是正确语义 | 实测 |
| 参数与注解都写不同模型 | 只有参数生效 | 二选一 | 实测 |
| `response_model=list[X]` 写成 `list[dict]` | 元素不过滤 | 用具体模型 | `[O2]` |
| `from_attributes` 忘配 | 报 `model_attributes_type` | 配上 | 实测 |
| 以为 `Decimal` 会输出数字 | 实际是字符串 | 与前端约定 | 第 17 章 |
| 出参模型里放 `password: str \| None = None` | 条件满足时照样输出 | 根本不要这个字段 | `[O4]` |
| 只测成功路径 | 500 无人发现 | 加「缺字段」用例 | 第 71 章 |
| 把 `id` 放在返回注解、用参数覆盖 | id 消失 | 统一出参模型 | 实测 |
| 用 `exclude` 做权限控制 | 换个端点就漏 | 权限在依赖层 | `[O4]` |
| 大响应体也全量校验 | 延迟升高 | 内部接口可关 | `[O5]` |
| 把异常详情塞进 detail | 信息泄露 | 统一错误结构 | 第 33 章 |
| docstring 写内部备注 | 出现在 `description` | 当公开文档写 | 实测 |
| `response_model_exclude_none` 表示「无值」 | 客户端分不清 null/缺失 | 明确契约 | `[O3]` |
| 返回 ORM 对象但含 lazy 属性 | 触发额外查询 | 只选需要的列 | M09 |
| 用 `dict` 直接返回不建模型 | 无校验、无文档 | 建模型 | `[O1]` |
| 忘了 `response_model` 但写了 `-> None` | 响应空 | 检查注解 | `[O1]` |
| 认为响应模型能防越权 | 只防字段，不防数据 | 权限 + 数据隔离 | `[O4]` |
| 用 `include` 在多个端点拼不同视图 | 难维护 | 多个出参模型 | `[O3]` |
| 声明 `response_model` 却返回 `Response` 子类 | 文档有、实际无 | 去掉模型或用真实结构 | 第 25 章 |

## 6. 最佳实践与编码建议

### 6.1 出参模型模板

```python
from datetime import datetime
from decimal import Decimal
from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field


class StrictOut(BaseModel):
    """出参基类：禁止客户端依赖额外字段。"""

    model_config = ConfigDict(from_attributes=True)


class OrderOut(StrictOut):
    id: int
    amount: Annotated[Decimal, Field(gt=0)]
    created_at: datetime
    note: str | None = None
```

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 入参/出参模型永远分开 | 命名带 `In`/`Out` |
| 出参模型只加不减 | 加字段是兼容变更 |
| 敏感字段根本不建 | 不靠 exclude |
| 统一用返回注解或统一用参数 | 团队约定一个 |
| 出参模型放在 `schemas` 包 | M11 |
| 每个出参模型配一条 500 用例 | 防回归 |
| 枚举/状态统一用 `Literal`/`Enum` | 避免自由字符串 |

### 6.3 选型速查

| 需求 | 做法 |
| --- | --- |
| 隐藏敏感字段 | 出参模型不声明 |
| 临时隐藏某字段 | `response_model_exclude` |
| 只输出有值的 | `exclude_unset` + 可选模型 |
| ORM 对象直接返回 | `from_attributes=True` |
| 列表 | `list[Model]` |
| 两种形态 | 两个端点 + 两个模型 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[O1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/response-model/ | `response_model` 与返回注解 |
| `[O2]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/extra-models/ | 多模型与 `list` 响应 |
| `[O3]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/response-model/#response_model_include-and-response_model_exclude | include/exclude |
| `[O4]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/security/ | 敏感字段与权限边界 |
| `[O5]` | 官方文档 | https://fastapi.tiangolo.com/zh/async/ | 大响应与性能 |

> **核对状态**：`[O1]`–`[O5]` 为官方文档链接，**本次未逐页直连复核**；白名单过滤、参数优先级、`exclude_*`、500 行为、docstring 进 description 均为本机实测，`examples/verify.py` 复现 10/10 通过。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 白名单与黑名单的差别
- [ ] 响应模型介入的生命周期位置
- [ ] 500 与 422 的分工
- [ ] `exclude_unset` 为何不影响校验
- [ ] `from_attributes` 解决什么问题
- [ ] docstring 为什么出现在 OpenAPI

**能写出（代码层）**：

- [ ] 一对 In/Out 模型
- [ ] `list[X]` 响应
- [ ] `exclude` 裁剪
- [ ] ORM 对象 + `from_attributes`
- [ ] 一个会 500 的反例

**能判断（避坑层）**：

- [ ] 看到入参模型直接当出参 → 指出泄露
- [ ] 看到 `exclude` 做权限 → 指出绕过
- [ ] 看到 500 被当成 422 处理 → 纠正语义
- [ ] 看到只测成功路径 → 指出缺字段 500 未覆盖
- [ ] 看到响应里出现 ORM 内部字段 → 指出出参模型缺失

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 10/10
- [ ] 手工在 `/docs` 里对比 In/Out 两个 schema
- [ ] 手工触发一次 500 并看日志

## 9. 下一章衔接

第 22 章 `状态码`：本章所有端点都返回 200，但「创建成功」应该是 201、「删除成功」应该是 204。下一章讲 `status_code`、`Response` 改码、204 不能有 body 这些细节，以及 OpenAPI 里的响应差异。

本章留下的伏笔：

1. 出参模型里的 `id` 在创建时由谁生成 —— 第 22 章配合 201 与 `Location` 头。
2. 错误结构统一在 第 33 章。
3. 响应头在 第 24 章。
4. ORM 与查询优化在 M09。
