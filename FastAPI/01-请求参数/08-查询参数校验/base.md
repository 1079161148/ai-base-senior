# 08 查询参数校验 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「`Query()` 与 `Path()` 差在哪、默认值怎么决定可选性、`alias` 写错为什么静默失败、数组约束作用在哪一层」拆开。学完这章，你要能给一个 12 个参数的后台列表接口设计出不会出事的参数契约。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1 / Python 3.12.8（本机实测） |
| 前置 | 第 07 章（查询参数基础）、第 06 章（`Path` 校验） |
| 覆盖范围 | `Query()` 全参数、可选性组合、`alias` 陷阱、`include_in_schema`、数组两层约束、OpenAPI 映射 |
| 明确不覆盖 | 查询参数模型（09）、分页规范（58）、统一错误格式（34） |
| 学完验收 | 能跑通 `verify.py` 10/10、能说出 `alias` 写错的后果、能区分数组长度约束与元素约束 |

## 0. 怎么用这份文件

**依据约定**：`` `[Wn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → Query 与 Path 的结构差异
2 机制（第 2 节）    → 可选性三态 + 校验时机
3 API（第 3 节）     → 全参数表、数组两层约束
4 边界（第 4 节）    → alias 静默失败、隐藏参数、可选+约束
5 注意事项（第 5 节）→ 30 条对照
6 最佳实践（第 6 节）→ 后台列表接口模板
```

## 1. 概念：与 `Path()` 的唯一结构差异

| 维度 | `Path()` | `Query()` | 依据 |
| --- | --- | --- | --- |
| 是否必填 | 恒必填 | 由默认值决定 | `[W1]` `[W2]` |
| `default` 参数 | ❌ 不支持 | ✅ 支持 | `[W1]` `[W2]` |
| 校验能力 | 同 | 同 | `[W3]` |
| 文档元信息 | 同 | 同 | `[W2]` |
| `loc` 首段 | `"path"` | `"query"` | 实测 |

> 注意：`Path()` 不能写 `default`，`Query()` 必须通过默认值表达可选性。这不是 API 不对称，而是 HTTP 语义决定的：路径段不存在就没有 URL，查询键不存在是常态。

## 2. 机制：可选性三态

```text
① 必填    Annotated[str, Query(min_length=3)]
          → 缺键 422 missing；有键就校验

② 可选有默认  Annotated[str, Query(...)] = "abc"
          → 缺键用 "abc"；有键就校验

③ 可选可空   Annotated[str | None, Query(min_length=3)] = None
          → 缺键为 None（跳过 min_length）；有键就校验
```

| 组合 | 缺键 | `?q=`（空串） | `?q=ab` |
| --- | --- | --- | --- |
| `Annotated[str, Query(min_length=3)]` | 422 `missing` | 422 `string_too_short` | 422 |
| `Annotated[str, Query(min_length=3)] = "abc"` | `"abc"` | 422 | 422 |
| `Annotated[str \| None, Query(min_length=3)] = None` | `None` | 422 | 422 |
| `Annotated[str, Query()] = ""` | `""` | `""` | `"ab"` |

实测：

```text
/must            -> 422 missing loc=["query","q"]
/must?q=abc      -> 200 {"q":"abc"}
/must?q=ab       -> 422 string_too_short
/optional        -> 200 {"q":null}
/optional?q=ab   -> 422 string_too_short
/optional?q=abc  -> 200 {"q":"abc"}
```

> 注意：第 ③ 种写法里，`None` **不参与** `min_length` 校验。这是「可选 + 有约束」的唯一正确姿势；写成 `Annotated[str, Query(min_length=3)] = None` 会让 OpenAPI 丢 `null`（第 07 章 2.3）。

## 3. API 逐一拆解

### 3.1 `Query()` 参数全表

| 参数 | 类型 | 默认 | 作用 | 失败 `type` | 依据 |
| --- | --- | --- | --- | --- | --- |
| `default` | 任意 | `PydanticUndefined` | 默认值，决定可选性 | — | `[W2]` |
| `alias` | `str` | `None` | 查询串里的键名 | — | `[W2]` |
| `title` / `description` | `str` | `None` | 文档 | — | `[W2]` |
| `deprecated` | `bool` | `False` | 标记废弃 | — | `[W2]` |
| `include_in_schema` | `bool` | `True` | 是否进文档 | — | `[W2]` |
| `ge` / `gt` | 数值 | `None` | 下界 | `greater_than_equal` / `greater_than` | `[W3]` |
| `le` / `lt` | 数值 | `None` | 上界 | `less_than_equal` / `less_than` | `[W3]` |
| `min_length` / `max_length` | `int` | `None` | 字符串长度 / **数组长度** | `string_too_short` / `too_short` / `too_long` | 实测 |
| `pattern` | `str` | `None` | 正则（整串） | `string_pattern_mismatch` | `[W3]` |
| `examples` | `list` | `None` | 文档示例 | — | `[W2]` |

### 3.2 数组的两层约束（实测，易错）

```python
tag: Annotated[list[str], Query(max_length=10)] = []              # 约束「数组长度」≤ 10
codes: Annotated[list[Annotated[str, Field(min_length=2)]], Query()] = []  # 约束「每个元素」长度 ≥ 2
```

实测：

| 请求 | 结果 | `loc` | `type` |
| --- | --- | --- | --- |
| 11 个 `tag` | 422 | `["query","tag"]`（**2 段**） | `too_long` |
| `?ids=a` | 422 | `["query","ids",0]`（**3 段**） | `int_parsing` |
| `?codes=x` | 422 | `["query","codes",0]`（**3 段**） | `string_too_short` |

| 结论 | 说明 |
| --- | --- |
| `Query(min_length)` 作用在 `list` 上是**元素个数** | 不是元素字符串长度 |
| 元素级约束要写在**元素类型**上 | `list[Annotated[str, Field(...)]]` |
| `loc` 段数能区分两类错误 | 2 段 = 数组本身；3 段 = 某个元素 |
| 给 `list` 写 `min_length=1` + 默认 `[]` | 默认值本身违规 → 一请求就 422 |

> 注意：最后一条是本机实测踩出来的坑——`Query(min_length=1) = []` 会让「不传 tag」直接 422，因为默认空列表不满足「至少 1 个」。

### 3.3 `alias` 的实测行为

```python
page_size: Annotated[int, Query(alias="page-size", ge=1, le=50)] = 10
```

实测：

```text
/orders?page-size=30  -> {"page_size": 30}      ✅ 生效
/orders?page_size=30  -> {"page_size": 10}      ❌ 200 但用默认值
```

| 事实 | 说明 |
| --- | --- |
| 未知查询键**不报错** | HTTP 规范允许忽略未知参数 |
| 写错键名 = 静默用默认值 | 永远不 422，最难排查 |
| `alias` 只影响**入参解析** | 不影响响应字段名 |
| 响应字段名由模型/返回值决定 | 要改响应用 `serialization_alias`（第 21 章） |

> 注意：这是「前后端联调三天找不到 bug」的典型来源。对策是**契约测试**：断言 `?page-size=30` 返回 30，而不是断言「请求成功」。

### 3.4 `include_in_schema=False` 的连带影响

实测（接口只有一个可见参数 + 一个隐藏参数）：

```text
文档参数=['value']（_internal 已隐藏）
```

实测（接口的**全部**参数都隐藏时）：

```text
operation keys: ['operationId', 'responses', 'summary']
parameters 键存在吗: False
```

| 情况 | OpenAPI 表现 |
| --- | --- |
| 部分参数隐藏 | `parameters` 只列可见的 |
| 全部参数隐藏 | `parameters` 键**整个消失** |
| 路由整个隐藏 | `paths` 里没有该路径（第 03 章） |

> 注意：解析 OpenAPI 的客户端代码可能假设 `parameters` 一定存在，遇到这种响应会 `KeyError`。写工具时要 `.get("parameters", [])`。

## 4. 边界条件

### 4.1 可选 + 约束的组合

| 写法 | 缺键 | 空串 | 太短 | 评价 |
| --- | --- | --- | --- | --- |
| `str, Query(min_length=3)` | 422 | 422 | 422 | 必填 |
| `str, Query(min_length=3)` = `"abc"` | `"abc"` | 422 | 422 | 可选，默认合法 |
| `str \| None, Query(min_length=3)` = `None` | `None` | 422 | 422 | ✅ 推荐 |
| `str, Query()` = `""` | `""` | `""` | `""` | 无校验 |

### 4.2 数值参数的隐式转换

| 输入 | `int` | `float` |
| --- | --- | --- |
| `"10"` | `10` | `10.0` |
| `"10.5"` | 422 `int_parsing` | `10.5` |
| `"1e3"` | 422 | `1000.0` |
| `" 10 "` | 422（不 strip） | 422 |
| `"+10"` | `10` | `10.0` |
| `"0x10"` | 422 | 422 |

### 4.3 `pattern` 与中文

| 需求 | 写法 | 说明 |
| --- | --- | --- |
| 只允许字母数字 | `r"^[a-zA-Z0-9]+$"` | 显式字符集 |
| 允许中文 | `r"^[\w\s\u4e00-\u9fa5]+$"` | `\u4e00-\u9fa5` 覆盖常用汉字 |
| 用 raw string | `r"..."` | 避免 `\w` 被 Python 转义 |

> 注意：不写 `r` 前缀时 `"\w"` 在 Python 里是字面 `\w`（因为 `\w` 不是合法转义会被保留），但 `"\t"`、`"\n"` 会被转成制表符/换行，导致正则意外匹配。一律用 raw string。

### 4.4 参数很多时的接口

| 参数个数 | 建议 |
| --- | --- |
| ≤ 4 | 直接展开 |
| 5–8 | 展开 + 分组 `description` |
| > 8 | 用查询参数模型（第 09 章） |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `alias` 写错/前端传错键 | 静默用默认值 | 契约测试 | 实测 |
| `Query(min_length=1) = []` | 默认值违规 → 恒 422 | 去掉 `min_length` 或改默认 | 实测 |
| 以为 `list` 的 `min_length` 约束元素 | 实际约束元素个数 | 元素级用 `Field` | 实测 |
| `Annotated[str, Query()]` 不写默认值却想可选 | 必填 | 补 `= None` | 实测 |
| 给 `int` 写 `= None` | 类型不符 | `int \| None = None` | 第 07 章 |
| 全部参数设为隐藏 | `parameters` 键消失 | 只隐藏内部参数 | 实测 |
| 隐藏参数当权限 | 照样能传 | 用鉴权 | `[W4]` |
| 分页无上限 | DB 被打爆 | `le=100` | `[W5]` |
| 排序字段无白名单 | SQL 注入 | `pattern="^(a\|b)$"` | `[W6]` |
| `pattern` 用普通字符串 | `\t` 等被转义 | `r"..."` | 实测 |
| 二次手工校验 | 错误格式混乱 | 全交给 `Query` | `[W2]` |
| 用 `Query()` 校验 `list[int]` 元素范围 | 约束到数组长度上 | `list[Annotated[int, Field(ge=1)]]` | 实测 |
| 一个参数既 `Path` 又 `Query` | 启动报错 | 二选一 | `[W2]` |
| `deprecated` 不写替代 | 前端不知怎么迁 | `description` 写替代 | `[W2]` |
| 约束过紧导致 422 激增 | 线上事故 | 灰度 + 监控 422 率 | `[W7]` |
| 依赖 `msg` 字段 | 随版本变 | 用 `type` | `[W3]` |
| 忽略 `input` 回显 | 敏感值泄露 | 第 33 章过滤 | `[W3]` |
| 用 `Query` 做 body 校验 | 位置错 | `Body`/模型 | 第 13 章 |
| `limit` 用 `str` 接收 | 下游要手工转换 | `int` + `le` | `[W5]` |
| 时间参数用 `str` | 无法比较 | `datetime` + `Query` | 第 17 章 |
| 布尔参数无默认值 | 前端漏传即 422 | 给默认值 | 第 07 章 |
| 多值参数用逗号约定但后端 `list` | 只收到 1 个 | 统一约定 | 第 07 章 |
| 参数名用驼峰 | 与前端风格冲突 | kebab-case + `alias` | `[W8]` |
| 忘记给 `list` 参数上限 | 一万个 tag | `max_length`（数组长度） | 实测 |
| 用 `include_in_schema=False` 做灰度开关 | 行为仍在线上 | 用配置开关 | `[W4]` |
| 校验规则散落在业务代码 | 难维护 | 集中到签名 | `[W2]` |
| 未测边界值 | 上线 422 | 边界测试 | `[W7]` |
| 用 `Query` 的 `regex` 参数 | v2 已改名 | 用 `pattern` | `[W3]` |
| `Query(...)` 写 `Ellipsis` 当必填 | 可用但可读性差 | 直接省略默认值 | `[W2]` |
| 依赖参数顺序 | 关键字传参，顺序无关 | 无需关心 | `[W2]` |

## 6. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 「可选 + 有约束」用 `T \| None = None` | 唯一正确姿势 | 实测 |
| 分页参数永远设上限 | `le=100` | `[W5]` |
| 排序字段用 `pattern` 白名单 | 防注入 | `[W6]` |
| 参数名 kebab-case + `alias` | 前端友好 | `[W8]` |
| 每个参数写 `description` | 后台接口自助 | `[W2]` |
| 数组参数分两层设约束 | 个数 + 元素 | 实测 |
| 写契约测试断言值 | 抓静默失败 | 第 88 章 |
| 组内统一参数命名 | `limit`/`offset`/`sort` | `[W5]` |

**后台列表接口模板**：

```python
from typing import Annotated

from fastapi import FastAPI, Query

app = FastAPI()


@app.get("/admin/orders")
def list_orders(
    q: Annotated[str | None, Query(min_length=1, max_length=50, description="订单号/用户模糊搜索")] = None,
    status: Annotated[str | None, Query(pattern="^(pending|paid|shipped|canceled)$", description="状态")] = None,
    created_from: Annotated[str | None, Query(pattern=r"^\d{4}-\d{2}-\d{2}$", description="起始日期 YYYY-MM-DD")] = None,
    limit: Annotated[int, Query(ge=1, le=100, description="每页条数")] = 20,
    offset: Annotated[int, Query(ge=0, description="偏移量")] = 0,
    sort: Annotated[str, Query(pattern="^(created|amount)$", description="排序字段")] = "created",
) -> dict[str, object]:
    return {"q": q, "status": status, "created_from": created_from, "limit": limit, "offset": offset, "sort": sort}
```

**边界**：

- 本章约束能力与第 06 章完全同源（Pydantic），差异只在参数来源。
- 数组的两层约束是本章最容易混淆的点，`verify.py` 用三条断言把它固定下来。
- 查询参数模型的字段级约束见第 09 章。

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[W1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/path-params-numeric-validations/ | `Path` 与 `Query` 对照 |
| `[W2]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/query-params-str-validations/ | `Query()` 参数、`alias`、`deprecated` |
| `[W3]` | 官方文档 | https://docs.pydantic.dev/latest/concepts/fields/ | 约束语义、错误类型码 |
| `[W4]` | 规范 | https://owasp.org/www-project-top-ten/ | 隐藏不等于授权 |
| `[W5]` | 规范 | https://www.rfc-editor.org/rfc/rfc9110 | 分页与幂等 |
| `[W6]` | 规范 | https://owasp.org/www-community/attacks/SQL_Injection | 排序注入 |
| `[W7]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/testing/ | 边界测试 |
| `[W8]` | 规范 | https://restfulapi.net/resource-naming/ | 参数命名 |

> **核对状态**：`[W4]`–`[W6]`、`[W8]` 为规范类来源；`[W1]`–`[W3]`、`[W7]` 按官方文档结构整理，**本次未逐页直连复核**。文中「实测」为本机 FastAPI 0.146.0 / Pydantic 2.14.1 输出，`examples/verify.py` 可复现 10/10 通过。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] `Query()` 与 `Path()` 的唯一结构差异
- [ ] 可选性三态及各自的缺键行为
- [ ] `alias` 写错为什么静默失败
- [ ] `include_in_schema=False` 对 `parameters` 的影响
- [ ] 数组两层约束的区别与 `loc` 段数
- [ ] `pattern` 为什么必须用 raw string

**能写出（代码层）**：

- [ ] 后台列表接口（6 个参数，含上限与白名单）
- [ ] 连字符别名接口
- [ ] 数组两层约束接口
- [ ] 可选 + 约束接口

**能判断（避坑层）**：

- [ ] 看到 `Query(min_length=1) = []` 能指出恒 422
- [ ] 看到 `?page_size=30` 能指出静默失效
- [ ] 看到 `pattern="\w+"` 能指出该用 raw string
- [ ] 看到 `loc` 三段能指出是元素错误
- [ ] 看到排序字段直传能指出注入风险

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 10/10
- [ ] 用错别名复现「200 但值不对」
- [ ] 打出数组长度错误与元素错误的两种 `loc`

## 9. 下一章衔接

第 09 章 `查询参数模型`：把 8 个分页/过滤参数收成一个 Pydantic 模型，讲清 `Annotated[Model, Query()]` 的展开规则、模型字段的默认值与 `alias`、以及**为什么不支持嵌套模型**（实测会 422）。

本章留下的伏笔：

1. 参数 > 8 个怎么收敛——第 09 章。
2. `Field` 的用法在第 09 章正式出现（第 14 章展开）。
3. 统一错误格式——第 33、34 章。
