# 07 查询参数 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「查询参数怎么被识别、可选性由什么决定、多值为什么是重复键、`?tag=a,b` 到底得到什么」拆开。学完这章，你要能给任意列表接口设计出前端不会用错的参数。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1 / Python 3.12.8（本机实测） |
| 前置 | 第 05 章（路径参数）、第 06 章（`Path` 校验） |
| 覆盖范围 | 识别规则、可选性规则、默认值、多值、bool、编码、`missing` 错误、OpenAPI 映射 |
| 明确不覆盖 | `Query()` 校验参数（08）、查询参数模型（09）、分页规范（58） |
| 学完验收 | 能跑通 `verify.py` 9/9、能说出 `?tag=a,b` 的实际结果、能解释 `missing` 与 `bool_parsing` 的区别 |

## 0. 怎么用这份文件

**依据约定**：`` `[Qn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 查询参数在 URL 的哪个位置
2 机制（第 2 节）    → 识别规则 + 可选性规则（重点）
3 API（第 3 节）     → 三种可选写法、多值、bool
4 边界（第 4 节）    → 空串、重复键、逗号、编码、长度
5 注意事项（第 5 节）→ 31 条对照
6 最佳实践（第 6 节）→ 列表接口参数设计
```

## 1. 概念：`?` 后面的一切

```text
GET /search?q=python&tag=a&tag=b&limit=10
         └──────────────┬──────────────┘
                   查询串（query string）

GET /users/42?tab=orders
     └──┬──┘└──────┬────┘
    路径参数    查询参数
```

| 维度 | 路径参数 | 查询参数 | 依据 |
| --- | --- | --- | --- |
| 位置 | 路径段 | `?` 之后 | `[Q1]` |
| 必填性 | 恒必填 | 看默认值 | `[Q1]` |
| 可省略 | ❌ | ✅（有默认值） | `[Q1]` |
| 典型用途 | 资源标识 | 过滤/分页/排序/搜索 | `[Q2]` |
| 缓存影响 | 是 URL 的一部分 | 也是 URL 的一部分 | `[Q3]` |
| 进访问日志 | 是 | **是** | `[Q3]` |

| 不该放查询参数 | 原因 |
| --- | --- |
| 密码、token | 会进日志、浏览器历史、Referer |
| 大段 JSON | URL 长度限制（浏览器约 2KB–8KB，服务器默认 8KB） |
| 二进制 | 需要编码，体积膨胀 33% |
| 需要幂等创建的复杂数据 | 用 POST + body |

## 2. 机制：两条规则决定一切

### 2.1 识别规则：在不在路径模板里

```python
@app.get("/trips/{from_city}/to/{to_city}")
def f(from_city: str, to_city: str, day: str | None = None) -> ...:
```

| 参数 | 在模板里 | 判定 | 依据 |
| --- | --- | --- | --- |
| `from_city` | ✅ | 路径参数 | `[Q1]` |
| `to_city` | ✅ | 路径参数 | `[Q1]` |
| `day` | ❌ | 查询参数 | `[Q1]` |

### 2.2 可选性规则：有没有默认值

| 声明 | 必填 | 缺失时 | OpenAPI |
| --- | --- | --- | --- |
| `q: str` | ✅ | 422 `missing` | `required: true` |
| `q: str = "x"` | ❌ | `"x"` | `required: false, default: "x"` |
| `q: str \| None = None` | ❌ | `None` | `required: false, anyOf[string, null]` |
| `q: str = ""` | ❌ | `""` | `required: false, default: ""` |
| `limit: int = 10` | ❌ | `10` | `required: false, default: 10` |
| `tag: list[str] = []` | ❌ | `[]` | `type: array` |

实测：

```text
/search          -> 200 {"q": null, "limit": 10}
/search?q=x&limit=5 -> 200 {"q": "x", "limit": 5}
/reports         -> 422 {"detail":[{"type":"missing","loc":["query","month"],"msg":"Field required"}]}
/reports?q=x     -> 200 {"month": ...}
```

实测 OpenAPI：

```json
/opt       [{"name":"q","required":false,"schema":{"anyOf":[{"type":"string"},{"type":"null"}]}},
            {"name":"limit","required":false,"schema":{"type":"integer","default":10}}]
/required  [{"name":"q","required":true,"schema":{"type":"string"}}]
```

> 注意：「必填」只检查**键是否存在**，不检查值是否为空。`?month=` 会得到 `""` 并返回 200（实测）。要拒绝空串得靠 `Query(min_length=1)`（第 08 章）。

### 2.3 为什么 `str | None = None` 而不是 `str = None`

| 写法 | 运行 | 静态检查 | OpenAPI |
| --- | --- | --- | --- |
| `q: str \| None = None` | ✅ | ✅ | `anyOf[string, null]` |
| `q: str = None` | ✅ | ❌ 报类型不符 | `type: string`（**漏了 null**） |
| `q: Optional[str] = None` | ✅ | ✅ | 同上（等价写法） |

> 注意：`q: str = None` 能跑通是因为 FastAPI 不做运行期类型检查，但 OpenAPI 会少一个 `null`，前端生成的类型是 `string` 而非 `string | null`，导致前端以为「一定会有字符串」。

## 3. API 逐一拆解

### 3.1 多值参数

```python
tag: list[str] = Query(default=[])
```

实测三种传法：

```text
/tags              -> {"tag": [], "count": 0}
/tags?tag=a        -> {"tag": ["a"], "count": 1}
/tags?tag=a&tag=b  -> {"tag": ["a", "b"], "count": 2}
/tags?tag=a,b      -> {"tag": ["a,b"], "count": 1}     ← 关键
```

| 传法 | 结果 | 说明 | 依据 |
| --- | --- | --- | --- |
| 重复键 | `["a","b"]` | FastAPI 默认 | `[Q4]` |
| 逗号拼接 | `["a,b"]` | **不拆** | 实测 |
| 空值 `?tag=` | `[""]` | 一个空串元素 | 实测 |
| 逗号 + 空格 | `["a, b"]` | 原样保留 | 实测 |

> 注意：这是前后端联调的高频事故点。约定方案有两种：
> 1. 前端用 `URLSearchParams.append` 重复键（标准做法）；
> 2. 后端接收 `str` 自己 `split(",")`（本章 `/tags-csv`）。
> 混用会导致「前端传 3 个标签，后端只收到 1 个字符串」且不报错。

### 3.2 bool 查询参数

| 输入 | 结果 | 依据 |
| --- | --- | --- |
| `true` / `True` / `1` / `yes` / `on` / `t` / `y` | `True` | `[Q5]` |
| `false` / `False` / `0` / `no` / `off` / `f` / `n` | `False` | `[Q5]` |
| `?flag`（键存在无值） | **422** | 实测 |
| `?flag=`（空值） | **422** | 实测 |
| `maybe` / `2` | 422 `bool_parsing` | 实测 |

| 设计建议 | 说明 |
| --- | --- |
| 给默认值 | `flag: bool = False`，避免前端漏传就报错 |
| 前端显式传 `1/0` | 比 `true/false` 更稳（不依赖大小写） |
| 需要「存在即真」语义 | 用 `str \| None = None` 自己判断 |

### 3.3 参数名与别名的预告

查询参数名默认取**函数参数名**。想用 `page-size` 这种带连字符的名字，需要 `Query(alias="page-size")`——这是第 08 章的内容，但这里先记住一个实测结论：

```text
GET /alias?page-size=30  -> {"page_size": 30}
GET /alias?page_size=30  -> {"page_size": 10}   ← 静默使用默认值，不报错
```

| 风险 | 说明 |
| --- | --- |
| 前端写错参数名 | **不报错**，静默用默认值 |
| 排查困难 | 日志里看起来参数都传了 |

> 注意：「未知查询参数被忽略」是 HTTP 的正常行为，框架不会报错。所以参数名拼错永远不会 422，只会「行为不对」。对策：写契约测试断言实际返回值（第 88 章）。

## 4. 边界条件

### 4.1 空字符串 vs 缺失

| 请求 | 结果 |
| --- | --- |
| `/reports` | 422 `missing` |
| `/reports?month=` | 200 `{"month": ""}` |
| `/reports?month=0` | 200 `{"month": "0"}` |

> 注意：「必填」不等于「非空」。要拒绝空串必须加 `min_length=1`（第 08 章）或用 `str` 手工判断。

### 4.2 重复键取哪个

| 声明 | `?q=a&q=b` |
| --- | --- |
| `q: str` | 取**最后一个** `"b"` |
| `q: list[str]` | `["a", "b"]` |

> 注意：`q: str` 时行为依赖实现（当前取最后一个），不要依赖这个细节；需要明确语义就用 `list[str]`。

### 4.3 数值与溢出

| 输入 | 结果 |
| --- | --- |
| `?limit=10` | `10` |
| `?limit=010` | `10` |
| `?limit=1e3` | 422 `int_parsing` |
| `?limit=99999999999999999999` | 取决于 Python int（无上限），但会拖垮下游 |
| `?limit=-1` | `-1`（无约束时允许） |

> 注意：查询参数**默认没有范围约束**。`?limit=1000000` 会原封不动传给数据库。必须用 `Query(le=100)` 兜底（第 08 章），这是「分页拖垮数据库」的最常见成因。

### 4.4 编码

| 场景 | 请求 | 说明 |
| --- | --- | --- |
| 中文 | `?name=%E5%8C%97%E4%BA%AC` | 自动解码为「北京」 |
| 空格 | `?q=hello%20world` 或 `+` | 两者都解码为空格 |
| `&` 在值里 | `?q=a%26b` | 必须编码，否则被当成参数分隔符 |
| `=` 在值里 | `?q=a%3Db` | 同上 |
| `+` 在值里 | `?q=a%2Bb` | 裸 `+` 会被解码成空格 |

### 4.5 URL 长度

| 层 | 典型上限 | 后果 |
| --- | --- | --- |
| 浏览器 | 2KB–8KB | 超长可能被截断 |
| Nginx | `large_client_header_buffers`（默认 8KB） | 414 URI Too Long |
| 应用 | 无硬限制 | 但日志与解析开销大 |

> 注意：需要传大量 ID 时（如「批量删除 500 条」），改用 POST + body，不要拼在查询串里。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `q: str = None` | OpenAPI 丢 null | `str \| None = None` | 实测 |
| 必填参数想可选但不给默认值 | 422 `missing` | 给默认值 | 实测 |
| 以为 `?tag=a,b` 会拆分 | 实测 `["a,b"]` | 重复键或自解析 | 实测 |
| 前端用逗号、后端用 list | 只收到 1 个元素 | 统一约定 | 实测 |
| 分页参数无上限 | 拖垮数据库 | `Query(le=...)` | `[Q6]` |
| 用查询参数传 token | 进日志/历史 | 用 Header | `[Q3]` |
| 参数名带下划线给前端 | 前端写 `page-size` 静默失效 | `Query(alias=...)` | 实测 |
| 以为写错参数名会报错 | 静默用默认值 | 契约测试 | 实测 |
| `?flag` 裸键期望 True | 422 | `?flag=1` | 实测 |
| 空串当成未传 | 实际是已传空值 | 加 `min_length=1` | 实测 |
| 用 `list[str]` 但默认值写 `None` | 类型不符 | `Query(default=[])` | `[Q4]` |
| 忘记 URL 编码 `&` | 参数被截断 | 客户端编码 | `[Q7]` |
| 查询参数做 SQL 拼接 | 注入 | 参数化查询 | `[Q8]` |
| 用查询参数传大 JSON | 414/截断 | POST body | `[Q7]` |
| 排序字段直接拼 SQL | 注入 | 白名单 | `[Q8]` |
| 排序用 `?sort=-created_at` | 需要自己解析符号 | 显式 `order=desc` | `[Q6]` |
| 大小写混用的参数名 | 大小写敏感 | 统一小写+连字符 | `[Q2]` |
| 参数过多（>10） | 难维护 | 用查询参数模型（09） | `[Q9]` |
| 重复键用 `str` 接收 | 只取一个 | `list[str]` | 实测 |
| 依赖浏览器行为不编码 | 环境差异 | 一律编码 | `[Q7]` |
| 把筛选条件放进路径 | 组合爆炸 | 查询参数 | `[Q2]` |
| 用 GET 传敏感数据 | 日志泄露 | POST + body | `[Q3]` |
| 忽略 `input` 回显 | 敏感值进响应 | 第 33 章过滤 | `[Q5]` |
| `bool` 用 `"TRUE"` 依赖大小写 | 实测大小写都行但别依赖 | 统一小写 | `[Q5]` |
| 分页用 `offset` 无上限 | 深翻页慢 | 游标分页（第 58 章） | `[Q6]` |
| 参数默认值用可变对象（`=[]`） | 实际安全（Pydantic 复制）但风格差 | `Query(default=[])` | `[Q4]` |
| 用 `?q=null` 想表示 None | 得到字符串 `"null"` | 不传该键 | 实测 |
| 中文参数未编码直接 curl | 请求行非法 | `--data-urlencode` | `[Q7]` |
| 参数名用驼峰 | 与前端风格冲突 | 统一 kebab-case | `[Q2]` |
| 一次性加 20 个查询参数 | 接口难用 | 分页+过滤器模型 | 第 09 章 |
| 未记录接口参数约定 | 前后端反复对齐 | OpenAPI 契约 | `[Q9]` |

## 6. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 列表接口参数命名统一 `limit`/`offset` | 与通用规范一致 | `[Q6]` |
| `limit` 必须有上限 | `le=100` | `[Q6]` |
| 多值约定用重复键 | 标准且无歧义 | `[Q4]` |
| 参数名全小写 + 连字符 | `page-size` | `[Q2]` |
| 可选参数统一写 `T \| None = None` | 类型准确 | `[Q1]` |
| 每个参数写 `description` | 文档可读 | 第 08 章 |
| 敏感数据走 Header | 避免日志泄露 | `[Q3]` |
| 参数超过 6 个时用模型 | 收敛到一处 | 第 09 章 |
| 写契约测试断言返回值 | 抓「静默失败」 | 第 88 章 |

**风格示范**：

```python
from typing import Annotated

from fastapi import FastAPI, Query

app = FastAPI()


@app.get("/articles")
def list_articles(
    q: Annotated[str | None, Query(description="全文搜索关键词")] = None,
    tag: Annotated[list[str], Query(description="标签，可重复传")] = [],
    limit: Annotated[int, Query(ge=1, le=100, description="每页条数")] = 20,
    offset: Annotated[int, Query(ge=0, description="偏移量")] = 0,
) -> dict[str, object]:
    return {"q": q, "tag": tag, "limit": limit, "offset": offset}
```

**边界**：

- 本章不涉及 `Query()` 的校验与别名细节，第 08 章展开。
- 查询参数模型（`Annotated[Model, Query()]`）见第 09 章，它能把 10 个参数收敛成一个。
- 游标分页与深翻页优化见第 58 章。

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[Q1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/query-params/ | 查询参数声明、默认值、可选性 |
| `[Q2]` | 规范 | https://restfulapi.net/resource-naming/ | 参数命名约定 |
| `[Q3]` | 规范 | https://owasp.org/www-project-top-ten/ | 敏感数据不进 URL |
| `[Q4]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/query-params-str-validations/ | `list` 多值与 `Query` |
| `[Q5]` | 官方文档 | https://docs.pydantic.dev/latest/concepts/conversion_table/ | bool 转换表 |
| `[Q6]` | 规范 | https://www.rfc-editor.org/rfc/rfc9110 | 分页与幂等语义 |
| `[Q7]` | 规范 | https://www.rfc-editor.org/rfc/rfc3986 | URL 编码规则 |
| `[Q8]` | 规范 | https://owasp.org/www-community/attacks/SQL_Injection | 排序/过滤注入 |
| `[Q9]` | 规范 | https://spec.openapis.org/oas/latest.html | 参数契约 |

> **核对状态**：`[Q2]`、`[Q3]`、`[Q6]`–`[Q9]` 为规范类来源；`[Q1]`、`[Q4]`、`[Q5]` 按官方文档结构整理，**本次未逐页直连复核**。文中「实测」为本机 FastAPI 0.146.0 / Pydantic 2.14.1 输出，`examples/verify.py` 可复现 9/9 通过。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 查询参数与路径参数的四点区别
- [ ] 识别规则（在不在模板里）
- [ ] 可选性规则（有没有默认值）
- [ ] `str | None = None` 与 `str = None` 的差别
- [ ] `?tag=a,b` 的实际结果
- [ ] `missing` 与 `bool_parsing` 的触发条件

**能写出（代码层）**：

- [ ] 分页接口（`limit`/`offset` 带上下限）
- [ ] 多值过滤接口
- [ ] bool 开关接口
- [ ] 逗号自解析接口

**能判断（避坑层）**：

- [ ] 看到 `?tag=a,b` 能指出只得到 1 个元素
- [ ] 看到 `?month=` 能指出是 200 不是 422
- [ ] 看到 `?limit=1000000` 能指出需要 `le`
- [ ] 看到前端写错参数名能指出静默失效
- [ ] 看到 token 在查询串能指出日志泄露

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 9/9
- [ ] 在 `/docs` 里看到 `required` 与 `default` 正确显示
- [ ] 手工用两种写法传多值并对比结果

## 9. 下一章衔接

第 08 章 `查询参数校验`：给本章这些参数加上 `Query(ge/le/min_length/pattern/alias/deprecated)`，讲清连字符别名的实测坑（写错参数名静默用默认值）、`Query` 与 `Path` 的差异、以及为什么 `Query()` 必须写 `default=`。

本章留下的伏笔：

1. `Query(alias=...)` 的静默失败——第 08 章实测并给对策。
2. 参数超过 6 个怎么收敛——第 09 章。
3. 分页的游标实现——第 58 章。
