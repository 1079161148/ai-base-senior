# 16 多参数与 embed · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「body 到底怎么打包、包装键名能不能改、`embed` 该不该用、四类位置混用时错误怎么归位」拆开。学完这章，你要能一眼看出一个接口的请求体该长什么样。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1 / Python 3.12.8（本机实测） |
| 前置 | 第 12 章（四类位置）、第 13–15 章（模型与嵌套） |
| 覆盖范围 | 位置混用、多 body 自动包装、`Body(embed=True)`、标量 body、`Body_*` 组件、GET 带 body |
| 明确不覆盖 | 表单/文件（第 27 章）、`Depends` 取参（第 35 章）、响应模型（第 21 章） |
| 学完验收 | 能跑通 `verify.py` 11/11、能预测请求体形状、能解释包装键名的来源 |

## 0. 怎么用这份文件

**依据约定**：`` `[Mn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 为什么需要「多个 body 参数」
2 机制（第 2 节）    → 打包规则（重点）
3 API（第 3 节）     → Body() 参数表、三种形状
4 边界（第 4 节）    → 键名/别名、混合位置、标量、GET、兼容性
5 注意事项（第 5 节）→ 21 条对照
6 最佳实践（第 6 节）→ 契约形状决策
```

## 1. 概念：为什么会有「多 body 参数」

HTTP 的 body 是**一个**字节流，JSON 顶层只能有一个值。所以「一次提交两类独立数据」时必须二选一：

| 方案 | 请求体 | 优点 | 缺点 |
| --- | --- | --- | --- |
| 合成一个模型 | `{"item":{...},"address":{...}}` 用一个 `ShipmentCreate` 承载 | 结构固定、文档单一、易校验 | 需要多定义一个模型 |
| 多个 body 参数 | `def f(item: Item, address: Address)` | 少写模型、参数直观 | 包装键名隐式依赖参数名 |

FastAPI 选择了「自动包装」来支持第二种：把多个 body 参数按**参数名**合成一个对象。理解这一点，就能理解本章所有行为。

三种形状（实测）：

| 声明 | 请求体 |
| --- | --- |
| 单个 body 参数 | `{"sku":"A-1","qty":2}`（裸对象） |
| 两个 body 参数 | `{"item":{"sku":...},"address":{"city":...}}` |
| 单个 body + `embed=True` | `{"coupon":{"city":...}}` |

## 2. 机制：打包规则

```text
① 统计「body 参数」个数
   - 模型类型                  → body 参数
   - Annotated[..., Body()]     → body 参数
   - Path/Query/Header/Cookie   → 不算
   - Request                    → 不算

② 决策
   0 个  → 没有 requestBody
   1 个且未 embed → 请求体 = 该参数（裸）
   1 个且 embed   → 请求体 = {参数名: 值}
   ≥2 个          → 请求体 = {参数名1: 值, 参数名2: 值}

③ 校验
   裸对象：错误 loc = ["body", 字段]
   包装后：错误 loc = ["body", 参数名, 字段]
```

实测证据：

| 请求 | 结果 |
| --- | --- |
| `POST /shipments` body=`{"item":{...},"address":{...}}` | 200 |
| 同上但发扁平 `{"sku":...}` | 422，两条 `missing`：`["body","item"]`、`["body","address"]` |
| 只缺 `address` | 422，一条 `["body","address"]` |
| `POST /coupons` 发裸对象 | 422 `["body","coupon"]` |

注意第 ② 步：**是否包装取决于「body 参数个数」和 `embed`，不取决于类型**。所以「加了一个标量 `Body()`」也会让原本的裸对象变成包装对象——这是典型的破坏性变更。

## 3. API 逐个拆解

### 3.1 `Body()` 参数表

| 参数 | 默认 | 作用 | 注意 |
| --- | --- | --- | --- |
| `embed` | `False` | 单参数是否包装 | 只在「恰好一个 body 参数」时有意义 |
| `alias` | `None` | 包装键名/字段名 | 用于锁定键名，避免改参数名破坏契约 |
| `description` | `None` | 文档 | 标量 body 也需要说明 |
| `gt/ge/lt/le` | `None` | 数值约束 | 标量 body 才有意义 |
| `min_length/max_length` | `None` | 长度 | 同上 |
| `pattern` | `None` | 正则 | 同上 |
| `examples` | `None` | 文档示例 | — |
| `default` | `PydanticUndefined` | 缺省值 | 有默认值 → 整个 body 可选 |

### 3.2 三种形状的写法

```python
# A. 单 body（裸对象）
def add_item(order_id: int, item: Item) -> ...: ...


# B. 多 body（自动包装）
def create_shipment(item: Item, address: Address) -> ...: ...


# C. 单 body + embed（强制包装）
def create_coupon(coupon: Annotated[Item, Body(embed=True)]) -> ...: ...
```

### 3.3 `Body_*` 组件（实测）

多 body 与 embed 时，OpenAPI 会生成自动命名的组件：

```text
/shipments  -> #/components/schemas/Body_create_shipment_shipments_post
/coupons    -> #/components/schemas/Body_create_coupon_coupons_post
/orders/{order_id}/items -> #/components/schemas/OrderItemIn   （单 body，不生成 Body_*）
```

| 观察 | 含义 |
| --- | --- |
| 组件名包含函数名与路径 | 自动生成，**不要依赖具体拼写** |
| 组件内 `properties` = 参数名 | 参数名即契约 |
| `required` 包含所有无默认值的 body 参数 | 可用默认值让某个 body 参数可选 |
| 单 body 直连模型 `$ref` | 前端生成的类型更干净 |

## 4. 边界条件

### 4.1 包装键名与别名

| 写法 | 请求体键 |
| --- | --- |
| `def f(item: Item, ...)` | `item` |
| `def f(goods: Item, ...)` | `goods` |
| `Annotated[Item, Body(alias="item")]` | `item`（参数名可改，契约不变） |

结论：**参数名对外可见**。重命名参数 = 破坏性变更；想自由重构内部命名，就用 `alias` 把契约钉死。

### 4.2 混合位置的归位（实测）

```text
POST /orders/9/items?notify=true
X-Trace-Id: t-1
body={"sku":"A-1","qty":2}
→ 200 {"order_id":9,"item":{...},"notify":true,"trace_id":"t-1"}
```

| 出错位置 | `loc` |
| --- | --- |
| 路径 | `["path","order_id"]` |
| 查询 | `["query","notify"]` |
| 头 | `["header","x-trace-id"]` |
| body 字段 | `["body","qty"]` |

一个请求里多处出错时，全部聚合在一个 422 里（第 12 章已实测）。

### 4.3 标量 body

```python
def verify_token(
    token: Annotated[str, Body()],
    item: Item,
) -> ...: ...
```

| 场景 | 请求体 |
| --- | --- |
| 只有标量 body | `"abc"`（裸 JSON 字符串）——此时**不加 embed 就不包装** |
| 标量 + 模型 | `{"token":"abc","item":{...}}` |

> 标量裸 body（`"abc"`）在实践里很别扭，且客户端容易忘 `Content-Type`。需要标量时优先放 header/query；确实要在 body 里就配 `embed=True`。

### 4.4 GET 带 body

实测：`GET` 路由 + `Body()` 参数可以工作（TestClient 发得出去）。但：

| 问题 | 说明 |
| --- | --- |
| 网关/代理 | 很多实现直接丢弃 GET body |
| 缓存 | 缓存键通常只含 URL，body 不参与 |
| 语义 | HTTP 规范允许但不建议 |
| 工具 | 部分客户端库不支持 GET body |

结论：**契约里不要依赖 GET body**。要传结构就用 POST/PUT/PATCH。

### 4.5 契约演进（破坏性变更）

| 变更 | 影响 |
| --- | --- |
| 裸对象 → 包装对象 | 客户端全部要改 |
| 包装键改名 | 同上 |
| 新增第二个 body 参数 | 原来的裸对象变成包装，**破坏性** |
| 新增可选 body 参数（有默认值） | 兼容；`required` 不变 |
| 用 `alias` 固定键名 | 内部可自由重构 |

这条是本章最重要的工程结论：**只要预判未来可能有第二个 body 参数，一开始就用 `embed=True` 或合成一个模型**。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 两个 body 参数发扁平 JSON | 422 两条 `missing` | 按参数名包装 | 实测 |
| 以为包装键可随意改 | 键名 = 参数名，改名即破坏契约 | 用 `alias` 固定 | 实测 |
| 单 body 加 `embed` 仍发裸对象 | 422 `["body", 参数名]` | 包一层 | 实测 |
| 以为 `embed` 对多 body 有效 | 多 body 恒包装，embed 无意义 | 只在单 body 时用 | `[M1]` |
| 后来才加第二个 body 参数 | 客户端全量改 | 预先 `embed=True` | 实测 |
| 标量 body 忘记会包装 | 与模型混用时形状变了 | 统一包装并用 `alias` | 实测 |
| 需要标量却放 body | 客户端易错 | 放 header/query | `[M2]` |
| 依赖 GET body | 代理丢弃/缓存错 | 用 POST | `[M3]` |
| 把分页参数放 body | 列表接口无法用标准分页 | 放 query（第 42 章） | `[M2]` |
| 多 body 里参数名用 `data`/`body` | 语义模糊 | 用业务名 `item`/`address` | `[M1]` |
| 多 body 里一个参数可选 | 忘记给默认值 → 仍必填 | 给 `= None` 或默认值 | 实测 |
| 依赖 `Body_*` 组件名做代码生成 | 名称随函数/路径变化 | 只依赖 `$ref` 指向的字段 | 实测 |
| 在 body 里重复路径 id | 两份 id 可能不一致 | 路径 id 为准 | 第 12 章 |
| 同一个模型同时做多 body 参数 | 键名不同即可，但语义易混 | 拆成不同模型 | `[M1]` |
| 用 `Body(media_type="text/plain")` 传纯文本又声明模型 | 解析失败 | 明确内容类型 | `[M4]` |
| 混用 `Form` 与 `Body` | 编码冲突（form 是 urlencoded/multipart） | 二选一（第 27 章） | `[M5]` |
| 多 body 参数顺序影响契约 | 不影响 JSON 对象，但影响文档展示 | 按重要性排序 | `[M1]` |
| 以为包装后 `loc` 少一段 | 实际多一段参数名 | 按 `loc` 全量处理 | 实测 |
| 用 `embed=True` 又加 `alias` | 键名取 alias | 两者可组合 | 实测 |
| 让两个 body 参数同名 | Python 语法不允许 | 用不同参数名 | `[M1]` |
| 忘记 `Body()` 导入 | `NameError` | `from fastapi import Body` | `[M1]` |
| 用 `Depends` 里的 Body 参数 | 依赖里声明的 body 会合并进同一 requestBody | 注意合并规则（第 35 章） | `[M6]` |

## 6. 最佳实践与编码建议

### 6.1 决策表

| 场景 | 推荐 |
| --- | --- |
| 一类数据 | 单模型参数（裸对象） |
| 两类以上独立数据 | 合成一个 `XxxCreate` 模型（首推） |
| 两类以上但想复用现有模型 | 多 body 参数 + 明确参数名 |
| 未来可能扩展 | 单 body + `embed=True` |
| 标量 + 结构 | 合成模型，别用标量 body |

**首选「合成模型」**的理由：形状显式、文档干净、`loc` 层级固定、字段可统一加约束，也不会因为「加参数」意外改变形状。

### 6.2 契约模板

```python
from typing import Annotated

from fastapi import Body, FastAPI, Path, Query
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI()


class ShipmentDraft(BaseModel):
    model_config = ConfigDict(extra="forbid")

    item: ItemIn
    address: AddressIn
    note: Annotated[str | None, Field(max_length=200)] = None


@app.post("/orders/{order_id}/shipments")
def create_shipment(
    order_id: Annotated[int, Path(ge=1)],
    draft: ShipmentDraft,
    notify: Annotated[bool, Query(description="是否短信通知")] = False,
) -> dict[str, object]:
    return {"order_id": order_id, "draft": draft.model_dump(), "notify": notify}
```

这个写法同时满足：形状固定、扩展安全、`loc` 恒为 `["body", 字段]`、文档清晰。

### 6.3 编码建议

| 建议 | 说明 |
| --- | --- |
| 一个接口只用一个 body 参数 | 形状可控 |
| 需要多块数据就定义组合模型 | 显式优于隐式包装 |
| 必须多 body 时用 `alias` 钉住键名 | 内部可重构 |
| 预判扩展就用 `embed=True` | 避免破坏性变更 |
| 参数名用业务语义 | `item`/`address`，不要 `data1` |
| 契约变更写进 CHANGELOG | 客户端有据可查 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[M1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/body-multiple-params/ | 多 body 参数、自动包装、`embed` |
| `[M2]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/query-params/ | 查询参数承载过滤/分页 |
| `[M3]` | 规范 | https://www.rfc-editor.org/rfc/rfc9110#section-9.3.1 | GET 语义与 body |
| `[M4]` | 官方文档 | https://fastapi.tiangolo.com/zh/reference/parameters/ | `Body` 的 `media_type` 等参数 |
| `[M5]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/request-forms/ | 表单与 JSON 编码差异 |
| `[M6]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/dependencies/ | 依赖中声明的参数合并规则 |

> **核对状态**：`[M1]`–`[M6]` 为官方文档/规范链接，**本次未逐页直连复核**；请求体形状、`loc`、`Body_*` 组件名均为本机实测，`examples/verify.py` 复现 11/11 通过。4.4 中「GET body 被部分代理丢弃」属行业常见现象，非本机实测结论。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 为什么 JSON 顶层只能有一个值
- [ ] 打包决策的三条分支
- [ ] 包装键名由什么决定
- [ ] `embed` 只在什么情况下有意义
- [ ] 哪种变更属于破坏性变更
- [ ] 为什么 GET body 不可依赖

**能写出（代码层）**：

- [ ] 四类位置 + 单 body 的接口
- [ ] 两个 body 参数的接口
- [ ] `embed=True` 的接口
- [ ] 合成模型版（推荐写法）的接口

**能判断（避坑层）**：

- [ ] 看到扁平 JSON 发给多 body → 指出 `missing`
- [ ] 看到 `embed` 后仍发裸对象 → 指出要包装
- [ ] 看到参数名当契约 → 指出改名破坏兼容
- [ ] 看到标量 body → 指出形状变化
- [ ] 看到 GET body → 指出网关风险

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 11/11
- [ ] `/docs` 里看到 `Body_*` 组件的 `properties`
- [ ] 手工制造一次 `["body","address"]` 的 422

## 9. 下一章衔接

第 17 章 `特殊类型`：本章的字段还是 `str/int/float`。下一章开始用 `UUID`、`Decimal`、`datetime`、`HttpUrl`、`Enum`，讲清它们在 JSON 里长什么样、校验失败报什么、以及 `Decimal` 为什么是金额的唯一正确选择。

本章留下的伏笔：

1. `Body(alias=...)` 与字段 `alias` 的叠加规则在本章只给了结论，实际项目里建议统一「字段别名走模型」。
2. 依赖里声明 body 参数的合并行为在第 35 章。
3. 表单与文件的编码差异在第 27–29 章。
4. 契约变更管理在毕业项目第 78 章。
