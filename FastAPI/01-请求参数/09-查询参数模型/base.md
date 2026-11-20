# 09 查询参数模型 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「模型怎么展开成查询参数、为什么必须写 `Query()`、为什么嵌套不行、什么时候该用模型」拆开。学完这章，你要能一眼判断一个接口该展开写还是收敛成模型。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1 / Python 3.12.8（本机实测） |
| 前置 | 第 07、08 章（查询参数与校验）、第 13 章前需先会 Pydantic 模型基础 |
| 覆盖范围 | `Annotated[Model, Query()]` 展开规则、字段默认值/校验/alias、嵌套限制、与直接声明的取舍 |
| 明确不覆盖 | 请求体模型（13）、`Field` 全参数（14）、依赖注入（35） |
| 学完验收 | 能跑通 `verify.py` 9/9、能说出漏写 `Query()` 的后果、能解释嵌套模型的 422 |

## 0. 怎么用这份文件

**依据约定**：`` `[Xn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 什么时候该用模型
2 机制（第 2 节）    → 展开规则（重点）
3 API（第 3 节）     → 字段声明与约束
4 边界（第 4 节）    → 嵌套、漏写 Query()、alias、数组
5 注意事项（第 5 节）→ 26 条对照
6 最佳实践（第 6 节）→ 后台列表接口模板
```

## 1. 概念：什么时候该用模型

| 参数个数 | 建议 | 理由 |
| --- | --- | --- |
| 1–3 | 直接展开 | 模型是负担 |
| 4–6 | 直接展开 + 分组注释 | 可读性还行 |
| 7–12 | **模型** | 签名不再膨胀 |
| > 12 | 拆分接口 | 参数过多本身就是设计问题 |

| 收益 | 说明 | 依据 |
| --- | --- | --- |
| 签名稳定 | 新增参数只改模型 | `[X1]` |
| 复用 | 同一套过滤条件给多个接口 | `[X1]` |
| 集中约束 | 校验规则一处维护 | `[X2]` |
| 可单测 | 模型能脱离路由测试 | `[X2]` |

| 代价 | 说明 |
| --- | --- |
| 多一层间接 | 新人要先看模型才知道参数 |
| 展开后文档很长 | 12 个参数全列出 |
| 不能嵌套 | 复杂结构表达不了 |

## 2. 机制：展开规则

```python
class ArticleFilter(BaseModel):
    q: str | None = None
    tag: list[str] = []
    limit: int = Field(default=20, ge=1, le=100)


@app.get("/articles")
def list_articles(filters: Annotated[ArticleFilter, Query()]) -> ...: ...
```

```text
① 装配期：识别出参数类型是 BaseModel 且带 Query()
② 遍历模型字段，逐个生成「查询参数」描述
   q      → ?q=...        （可空）
   tag    → ?tag=...&tag=... （数组）
   limit  → ?limit=...     （默认 20，1..100）
③ OpenAPI：生成 3 个独立 parameter，**不产生 $ref**
④ 运行期：把所有查询键收集成 dict → 交给模型校验 → 得到实例
```

实测 OpenAPI：

```text
展开 5 个 query 参数：['limit', 'offset', 'order-by', 'q', 'tag']
每个 schema 无 $ref，in=query，无 requestBody
```

| 步骤 | 证据 | 依据 |
| --- | --- | --- |
| ② | 5 个独立参数 | 实测 |
| ③ | 无 `$ref`、无 `requestBody` | 实测 |
| ④ | 字段级 422，`loc=["query","limit"]` | 实测 |

### 2.1 为什么必须写 `Query()`

```python
# 错误：漏写 Query()
@app.get("/forgot")
def forgot(filters: ArticleFilter) -> ...: ...
```

实测：

```text
OpenAPI: 出现 requestBody
GET /forgot -> 422 {"detail":[{"type":"missing","loc":["body"],"msg":"Field required"}]}
```

| 结论 | 说明 |
| --- | --- |
| 裸模型参数 = **请求体** | FastAPI 的默认约定 |
| body 本身必填 | 即使所有字段都有默认值 |
| GET 通常没有 body | 所以永远 422 |
| 修法 | `Annotated[Model, Query()]` 或 `= Query()` |

> 注意：这是本章最高频的错误。判断方法：`GET` 接口报 `loc: ["body"]` 的 422，就是漏了 `Query()`。

### 2.2 字段默认值决定可选性

| 字段声明 | 查询参数 | 缺键行为 |
| --- | --- | --- |
| `q: str \| None = None` | 可选 | `None` |
| `limit: int = 20` | 可选 | `20` |
| `limit: int`（无默认） | **必填** | 422 `missing` |
| `tag: list[str] = []` | 可选 | `[]` |

与第 07 章规则完全一致，只是「默认值」写在了模型里。

## 3. API 逐一拆解

### 3.1 字段声明要点

| 需求 | 写法 | 依赖 |
| --- | --- | --- |
| 可选字符串 | `q: str \| None = None` | — |
| 带约束的数值 | `Field(default=20, ge=1, le=100)` | `pydantic.Field` |
| 带约束的字符串 | `Field(default="", max_length=50)` | `pydantic.Field` |
| 连字符键名 | `Field(default="x", alias="order-by")` | — |
| 数组 | `tag: list[str] = []` | — |
| 元素级约束的数组 | `list[Annotated[str, Field(min_length=1)]]` | — |
| 日期 | `day: date \| None = None` | — |

> 注意：模型里用的是 `pydantic.Field`，不是 `fastapi.Query`。两者都能加约束，但 `Field` 不携带「参数位置」信息——位置由外层的 `Query()` 决定。

### 3.2 `model_dump()` 的用处

```python
return filters.model_dump()
```

| 方法 | 结果 | 用途 |
| --- | --- | --- |
| `model_dump()` | `dict`（Python 对象） | 传给业务层 |
| `model_dump(exclude_none=True)` | 去掉 `None` 字段 | 构造 SQL 条件 |
| `model_dump(by_alias=True)` | 用 `alias` 作为键 | 输出给前端（第 21 章） |
| `model_dump_json()` | JSON 字符串 | 日志 |

> 注意：`model_dump()` 默认用字段名（`order_by`），不是 alias（`order-by`）。要让响应也用连字符，需要 `by_alias=True` 或 `response_model` 配置（第 21 章）。

## 4. 边界条件

### 4.1 嵌套模型：不支持（实测）

```python
class Range(BaseModel):
    min_price: int = 0
    max_price: int = 100


class WrongFilter(BaseModel):
    range: Range = Field(default_factory=Range)
```

实测 `GET /wrong?range=x`：

```text
422 {"detail":[{"type":"model_attributes_type","loc":["query","range"],
     "msg":"Input should be a valid dictionary or object to extract fields from"}]}
```

| 事实 | 说明 |
| --- | --- |
| 启动**不报错** | 问题延迟到请求期 |
| 传子字段 `?min_price=1` | 直接忽略（不是 `range` 的字段） |
| 传 `?range=x` | 422 `model_attributes_type` |
| OpenAPI | 出现 `$ref` 到 `Range`，前端无法拼查询串 |

> 注意：查询串是扁平结构，没有表达嵌套的标准语法。要表达区间就平铺成 `min_price` / `max_price`。`[X3]`

### 4.2 别名与静默失败

```python
order_by: str = Field(default="created", alias="order-by")
```

实测：

```text
?order-by=views -> order_by="views"     ✅
?order_by=views -> order_by="created"   ❌ 静默用默认值，200
```

| 风险 | 说明 |
| --- | --- |
| 前端传错键名永远不报错 | 与第 08 章 3.3 同源 |
| 排查手段 | 契约测试断言**值**，不是断言「状态码 200」 |

### 4.3 数组字段

```python
tag: list[str] = []
```

实测：

```text
?tag=a&tag=b  -> ["a","b"]
?tag=a,b      -> ["a,b"]        （不拆分）
```

元素级约束要写在元素类型上：`list[Annotated[str, Field(min_length=1)]]`（第 08 章 3.2）。

### 4.4 模型 + 独立参数混用

```python
def list_users(filters: Annotated[PageFilter, Query()], keyword: str | None = None): ...
```

| 评价 | 说明 |
| --- | --- |
| 可行 | 实测正常 |
| 不推荐 | 参数布局被拆成两处，维护成本上升 |
| 例外 | `keyword` 是临时加的、或语义上不属于过滤条件 |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `filters: Model` 漏写 `Query()` | GET 恒 422 `loc=["body"]` | `Annotated[Model, Query()]` | 实测 |
| 模型里嵌模型 | 422 `model_attributes_type` | 平铺字段 | 实测 |
| 模型里放 `dict` | 无法从查询串表达 | 用 `str` + 自解析 | `[X3]` |
| 模型里放 `Union[Model, str]` | 解析不确定 | 拆成两个参数 | `[X3]` |
| 字段名带下划线给前端 | 静默失效 | `Field(alias="...")` | 实测 |
| 字段无默认值却想可选 | 必填 422 | 给默认值 | 实测 |
| `list` 字段写 `Field(min_length=1)` + `= []` | 默认值违规恒 422 | 去掉或改默认 | 第 08 章 |
| 用 `Query` 而不是 `Field` 写在模型里 | 位置信息被丢弃，可能报错 | 模型内用 `Field` | `[X2]` |
| 用模型装 body 字段 | 语义错位 | 第 13 章 | `[X1]` |
| 一个模型给 GET 和 POST 共用 | body 与 query 语义冲突 | 分开建模型 | `[X1]` |
| 参数 > 20 还放一个模型 | 文档爆炸 | 拆接口 | `[X4]` |
| 模型里写跨字段 `model_validator` | 可用但 `loc` 不精确 | 简单规则用 `Field` | 第 20 章 |
| `model_dump()` 直接返回 | 响应键用下划线 | `by_alias=True` | 第 21 章 |
| 忽略 `exclude_unset` | 把默认值也当用户输入 | 需要区分时用 | 第 18 章 |
| 模型字段顺序依赖 | 不影响解析 | 无需关心 | `[X2]` |
| 用 `BaseModel` 的 `extra="allow"` | 未知查询键被收集 | 谨慎使用 | `[X2]` |
| 未知查询键期望报错 | 默认忽略 | 需要严格就自定义 | 第 08 章 |
| 模型里放文件/表单字段 | 位置冲突 | 用 Form/File | 第 27 章 |
| 复用 ORM 模型当过滤器 | 耦合 | 单独建 Filter 模型 | 第 56 章 |
| 默认值用可变对象但没 `default_factory` | Pydantic 会深拷贝，实际安全 | 用 `Field(default_factory=list)` 更明确 | `[X2]` |
| 字段名与 Python 关键字冲突 | 语法错 | 用 `alias` | `[X2]` |
| 用模型做依赖注入 | 需 `Depends` | 第 38 章 | `[X1]` |
| 期望 `?filter[q]=x` 深对象语法 | 不支持 | 平铺 | 实测 |
| 未写 `description` | 后台接口不可自助 | 每个字段补 | `[X1]` |
| 模型放 `api/v1/items.py` 里 | 复用困难 | 放 `models/` | 第 04 章 |
| 忽略展开后的参数数量 | 前端表单过长 | 分组或分页 | `[X4]` |

## 6. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 参数 ≥ 7 个时用模型 | 签名稳定 | `[X1]` |
| 模型放独立 `models/` 目录 | 可复用 | 第 04 章 |
| 每个字段写 `description` | 后台自助 | `[X1]` |
| 字段一律给默认值 | 避免必填地狱 | `[X2]` |
| 数值字段带上限 | 防滥用 | 第 08 章 |
| 别名统一 kebab-case | 前端友好 | `[X5]` |
| 嵌套结构改为平铺 | 查询串不支持 | 实测 |
| 写契约测试断言值 | 抓静默失败 | 第 88 章 |
| 用 `model_dump(exclude_none=True)` 构造查询 | 减少无效条件 | 第 56 章 |

**完整模板**：

```python
from datetime import date
from typing import Annotated

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

app = FastAPI()


class OrderFilter(BaseModel):
    """订单列表过滤条件（全部可选，靠默认值表达）。"""

    keyword: str | None = Field(default=None, max_length=50, description="订单号/用户名")
    status: str | None = Field(default=None, pattern="^(pending|paid|canceled)$", description="状态")
    created_from: date | None = Field(default=None, description="起始日期")
    created_to: date | None = Field(default=None, description="结束日期")
    min_amount: int | None = Field(default=None, ge=0, description="最小金额（分）")
    max_amount: int | None = Field(default=None, ge=0, description="最大金额（分）")
    limit: int = Field(default=20, ge=1, le=100, description="每页条数")
    offset: int = Field(default=0, ge=0, description="偏移量")
    order_by: str = Field(default="created", alias="order-by", pattern="^(created|amount)$")


@app.get("/admin/orders")
def list_orders(filters: Annotated[OrderFilter, Query()]) -> dict[str, object]:
    # 【注意】exclude_none=True：没传的条件不参与 SQL 构造
    return filters.model_dump(exclude_none=True, by_alias=True)
```

**边界**：

- 本章只讲 GET 查询参数场景；同样的模型加 `Depends` 也能做共享过滤条件（第 38 章）。
- 模型字段的约束能力与 `Field` 完全一致（第 14 章展开）。
- 嵌套限制是「查询串扁平」决定的，不是 FastAPI 的缺陷；body 场景完全支持嵌套（第 15 章）。

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[X1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/query-param-models/ | 查询参数模型 |
| `[X2]` | 官方文档 | https://docs.pydantic.dev/latest/concepts/models/ | 模型字段、默认值、`model_dump` |
| `[X3]` | 规范 | https://www.rfc-editor.org/rfc/rfc3986 | 查询串扁平结构 |
| `[X4]` | 规范 | https://restfulapi.net/resource-naming/ | 接口参数设计 |
| `[X5]` | 规范 | https://spec.openapis.org/oas/latest.html | 参数契约 |

> **核对状态**：`[X3]`–`[X5]` 为规范类来源；`[X1]`、`[X2]` 按官方文档结构整理，**本次未逐页直连复核**。文中「实测」为本机 FastAPI 0.146.0 / Pydantic 2.14.1 输出，`examples/verify.py` 可复现 9/9 通过。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 什么时候该用模型（参数个数门槛）
- [ ] 展开规则的 4 步
- [ ] 漏写 `Query()` 的后果
- [ ] 嵌套模型为什么不行
- [ ] `model_dump()` 与 `by_alias` 的作用

**能写出（代码层）**：

- [ ] 8 字段的过滤模型（含约束与别名）
- [ ] `Annotated[Model, Query()]` 接口
- [ ] 用 `exclude_none` 构造查询条件

**能判断（避坑层）**：

- [ ] 看到 GET 报 `loc=["body"]` 能指出漏了 `Query()`
- [ ] 看到嵌套模型能指出会 422
- [ ] 看到 `?order_by=` 能指出静默失效
- [ ] 看到 `list` 上写 `min_length=1` + `=[]` 能指出恒 422

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 9/9
- [ ] 在 `/docs` 里看到 5 个展开参数
- [ ] 复现嵌套模型的 422

## 9. 下一章衔接

第 10 章 `Cookie 参数`：进入「浏览器自动携带的凭证」这一类参数，讲清 `Cookie()` 声明、`set_cookie` 的 6 个安全属性、以及为什么 Cookie 不能替代 Header 鉴权。

本章留下的伏笔：

1. 模型还可以用 `Depends` 注入（第 38 章）。
2. `Field` 的完整能力在第 14 章。
3. `model_dump(by_alias=True)` 的响应侧用法在第 21 章。
