# 12 参数总表 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「参数为什么按位置分类、同名为什么不冲突、声明位置错在哪一步爆炸、`Request` 到底该不该用」拆开。学完这章，你要能在 30 秒内判断一个参数该放路径、查询、头还是 Cookie，并说清放错的后果。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Starlette 1.9.0 / Python 3.12.8（本机实测） |
| 前置 | 第 05–11 章（路径、查询、Cookie、Header 各自的细节） |
| 覆盖范围 | 四类参数对照、同名共存、声明位置冲突、幽灵路径参数、`Request` 直取、错误聚合、OpenAPI `in` |
| 明确不覆盖 | 请求体（第 13 章起）、表单与文件（第 27 章起）、依赖注入取参（第 35 章起） |
| 学完验收 | 能跑通 `verify.py` 10/10、能背三条导入期错误、能判断何时不该用 `Request` |

## 0. 怎么用这份文件

**依据约定**：`` `[Pn]` `` 指向第 7 节；标「实测」的是本机真实输出，可用 `examples/verify.py` 复现。

**推荐顺序**：

```text
1 概念（第 1 节）    → 参数是「位置」不是「类型」
2 机制（第 2 节）    → 一次请求里参数被分发到哪（重点）
3 API（第 3 节）     → 四类声明 + Request 属性表
4 边界（第 4 节）    → 可选性矩阵、空值、重复键、错误聚合、编码
5 注意事项（第 5 节）→ 26 条对照
6 最佳实践（第 6 节）→ 选型决策表 + 契约模板
```

**这一章是 M01 的收束**：05–11 章分别讲单个位置，本章讲它们**互相之间的关系**。单独某一类参数的细节，回到对应章节看。

## 1. 概念：参数按「位置」分类

HTTP 请求里能带数据的位置有四个（GET/DELETE 没有 body 时就是全部）：

| 位置 | 长什么样 | FastAPI 容器 | OpenAPI `in` |
| --- | --- | --- | --- |
| 路径 | `/items/42` | `request.path_params` | `path` |
| 查询串 | `?q=x&limit=10` | `request.query_params` | `query` |
| 请求头 | `X-Token: tk` | `request.headers` | `header` |
| Cookie | `Cookie: sid=s1` | `request.cookies` | `cookie` |

**关键认知**：这四类参数在框架里是**四个独立的字典**。所以「同一个名字出现在多个位置」不但合法，而且互不影响——这是本章最重要的结论，也是很多教程讲错的地方（它们会告诉你「路径参数优先级最高」）。

真实场景里一次请求通常同时用到四类：

```text
GET /orders/42?include=items
Authorization: Bearer xxx
Cookie: sid=s1
```

- `/orders/42` 的 `42`：**资源标识**，放路径；
- `include=items`：**表示方式/过滤**，放查询；
- `Authorization`：**调用方身份**，放头；
- `sid`：**会话**，放 Cookie。

选位置的原则是**语义**，不是技术便利：

| 判断问题 | 是 → 放哪 |
| --- | --- |
| 换一个值是否指向「另一个资源」？ | 路径 |
| 换一个值是否只是「换一种看法/范围」？ | 查询 |
| 是否描述调用方/客户端，而非资源？ | 请求头 |
| 是否与浏览器会话绑定、需要自动携带？ | Cookie |

## 2. 机制：一次请求里参数怎么被分发

```text
① Starlette 路由匹配
   /summary/7 → 命中 "/summary/{item_id}"，path_params={"item_id": "7"}
   没命中 → 404（此时参数校验根本不会执行）

② FastAPI 建立依赖树
   扫描函数签名：哪些是 Request / 哪些是参数 / 哪些是 Depends

③ 按声明位置取原始值（全字符串）
   path    ← request.path_params
   query   ← request.query_params
   header  ← request.headers（按转换后的头名查）
   cookie  ← request.cookies

④ Pydantic 校验 + 类型转换
   任一失败 → 聚合成一个 422，函数不执行

⑤ 调用函数
   函数体内拿到的**一定**是校验通过的值
```

三条实测事实，决定了本章所有结论：

| 事实 | 实测输出 | 含义 |
| --- | --- | --- |
| typed 与 raw 是两条独立通道 | `typed=7` / `raw={'item_id': '7'}` | 声明了 `int` 不代表 `request.path_params` 也是 `int` |
| 参数位置由「声明」决定 | `/conflict/pathval?q=queryval` → `{"path":"pathval","query":"queryval"}` | 同名不会互相覆盖 |
| 校验在函数调用之前 | 三个参数同时非法 → 一个 422 里三条错误 | 函数体内不需要防御性 `if not valid` |

**位置判定规则**（按优先级，先命中先用）：

| 顺序 | 条件 | 结果 |
| --- | --- | --- |
| 1 | 参数名出现在路由模板 `{...}` 里 | 路径参数（写 `Query()`/`Header()` 会报错） |
| 2 | 标注了 `Path()/Query()/Header()/Cookie()` | 按标注的位置 |
| 3 | 都没标注、名字不在模板里 | 查询参数 |

> 第 1 条是硬约束：**名字在模板里就只能是路径参数**，换个位置标注是导入期错误，不是运行期 422。

## 3. API 逐个拆解

### 3.1 四类参数的声明写法

```python
from typing import Annotated

from fastapi import Cookie, Header, Path, Query

item_id: Annotated[int, Path(ge=1)]
q: Annotated[str | None, Query(max_length=50)] = None
x_token: Annotated[str | None, Header()] = None
sid: Annotated[str | None, Cookie()] = None
```

四个函数共享同一批参数（都继承自 `Param`）：

| 参数 | 类型 | 默认 | 作用 | 注意 |
| --- | --- | --- | --- | --- |
| `default` | `Any` | `...`（必填） | 缺省值 | 路径参数**禁止**设置 |
| `alias` | `str \| None` | `None` | 改外部名字 | Header/Cookie 同名时靠它区分 |
| `title` / `description` | `str \| None` | `None` | 文档展示 | 对外接口必写 |
| `deprecated` | `bool` | `False` | 标记废弃 | 只影响文档，不拦截请求 |
| `examples` | `list` | `None` | 文档示例 | 比 `example` 更推荐 |
| `gt/ge/lt/le` | 数值 | `None` | 数值范围 | 仅数值类型有效 |
| `min_length/max_length` | `int` | `None` | 长度 | `list` 上是**元素个数**（第 08 章） |
| `pattern` | `str` | `None` | 正则 | 需整串匹配时自己加 `^...$` |
| `include_in_schema` | `bool` | `True` | 是否进文档 | 内部参数用 |

各位置的**专属差异**：

| 位置 | 专属注意 |
| --- | --- |
| `Path()` | 恒 `required=True`；不能有默认值；名字必须在模板里 |
| `Query()` | 默认值决定可选性；`list[str]` 收重复键；不拆分逗号 |
| `Header()` | 默认 `convert_underscores=True`；头名大小写不敏感；缺失 `loc` 是连字符形式 |
| `Cookie()` | 名字即 cookie 键；写 Cookie 要用 `response.set_cookie`（第 10/25 章） |

### 3.2 `Request` 属性表（实测值）

请求 `GET /summary/12?q=1&q=2&n=notanint`：

| 属性 | 实测值 | 类型 | 注意 |
| --- | --- | --- | --- |
| `path_params` | `{"item_id": "12"}` | `dict[str, str]` | 永远字符串 |
| `query_params` | `{"q": "2", "n": "notanint"}` | `QueryParams` | `.get()` 取**最后一个** |
| `query_params.getlist("q")` | `["1", "2"]` | `list[str]` | 多值必须用它 |
| `headers.get("x-token")` | `"tk"` | `str \| None` | 大小写不敏感；`.get()` 取**第一个** |
| `headers.getlist("x-tag")` | `["a", "b"]` | `list[str]` | 重复头 |
| `cookies` | `{"sid": "s1"}` | `dict[str, str]` | 已解码 |
| `method` / `url` | `"GET"` / `URL(...)` | — | `request.url.query` 是原始查询串 |
| `client` | `Address(host, port)` | `Address \| None` | 代理后是代理 IP（第 54 章） |
| `state` | `State` 对象 | `State` | 跨依赖传值（第 43 章） |
| `scope` | `dict` | `dict` | ASGI 原始作用域 |

**`Request` 不进 OpenAPI**：实测 `/openapi.json` 里 `parameters` 是 `None`。所以「用 `Request` 图省事」的代价是**文档上完全看不出这个接口需要什么参数**。

## 4. 边界条件

### 4.1 可选性矩阵

| 位置 | 无默认值 | 有默认值 | 缺失时 |
| --- | --- | --- | --- |
| 路径 | 必填 | **导入期报错** | 路由不匹配 → 404 |
| 查询 | 必填 | 可选 | 422 `missing`，`loc=["query", ...]` |
| 请求头 | 必填 | 可选 | 422 `missing`，`loc=["header", ...]` |
| Cookie | 必填 | 可选 | 422 `missing`，`loc=["cookie", ...]` |

### 4.2 空值 ≠ 缺失（实测）

| 请求 | 结果 |
| --- | --- |
| `/summary/7?q=` | `q == ""`，**不是** `None`，也不报 422 |
| `X-Token: ""` | `x_token == ""` |
| `Cookie: sid=` | `sid == ""` |

> 想拒绝空串必须加 `min_length=1`。这是「必填」和「非空」的分界线（第 07/08 章）。

### 4.3 重复键取哪个（实测，属实现细节）

| 读法 | `?q=1&q=2` | `X-Tag: a` + `X-Tag: b` |
| --- | --- | --- |
| typed `str` | `"2"`（最后一个） | `"a"`（第一个） |
| typed `list[str]` | `["1","2"]` | `["a","b"]` |
| `request.xxx.get()` | `"2"` | `"a"` |
| `request.xxx.getlist()` | `["1","2"]` | `["a","b"]` |

> 查询串取最后一个、请求头取第一个，**方向相反**。这是 Starlette 底层容器的实现差异，不要依赖；要全量就用 `list[str]` / `getlist()`。

### 4.4 路由匹配边界（实测）

| 请求 | 结果 | 原因 |
| --- | --- | --- |
| `/summary/7` | 200 | 正常 |
| `/summary/abc` | 422 `int_parsing`，`loc=["path","item_id"]` | 路由已匹配，转换失败 |
| `/summary/7.5` | 422 `int_parsing` | `int` 不接受小数串 |
| `/summary/0` | 422 `greater_than_equal` | `Path(ge=1)` |
| `/summary/` | **404** | 模板要求有 `{item_id}` 段，空段不匹配 |
| `/no-such-route` | 404 | 无此路由 |

> 记住这条因果链：**404 是路由层的事，422 是校验层的事**。看到 422 就别再怀疑路由了。

### 4.5 错误聚合与顺序（实测）

`/aggregate/abc?limit=999` + `X-Token: abc` → 一个 422，三条错误：

```text
("path", "item_id")   int_parsing
("header", "x-token") string_too_short
("query", "limit")    less_than_equal
```

- 三条**一次返回**，不是遇到第一个就停；
- 排列顺序随框架内部实现变化（与函数签名顺序**无关**），测试断言请用集合；
- 每条都带 `loc` 首段（`path`/`query`/`header`/`cookie`），前端可据此定位到具体控件。

### 4.6 编码与字符集

| 场景 | 实测结果 | 说明 |
| --- | --- | --- |
| 查询值含中文 | `?q=北京` → `"北京"` | 自动 URL 解码 |
| 路径含中文 | `/summary/7?q=北京` 正常 | 路径段也会解码（但资源 id 不建议用中文） |
| 头值含中文 | 报错/乱码 | HTTP 头只允许 latin-1，需 URL 编码或 Base64 |
| 头值带空格 | `"  tk  "` 原样保留 | **不会** strip，自己处理 |
| 未编码的空格/特殊字符 | 客户端行为不一致 | 一律 `encodeURIComponent` |

### 4.7 OpenAPI 表现

```text
/summary/{item_id}  ->  [('item_id','path',True), ('q','query',False),
                        ('x-token','header',False), ('sid','cookie',False)]
```

| 观察 | 说明 |
| --- | --- |
| 四种 `in` 都出现 | 文档上能看出参数来源 |
| 路径参数恒 `required: true` | 与是否有默认值无关（也不允许有） |
| 头名转小写 | `x_token` → `x-token`；用 `alias` 则保留 alias 写法 |
| `Request` 参数不出现 | 直取是「文档盲区」 |
| 幽灵参数也显示 `required: true` | 文档骗人，前端照着传依然 422 |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `Path()` 用在不存在的模板参数上 | 启动正常，永远 422 `loc=["path","x"]` | 名字与 `{x}` 对齐或改 `Query()` | 实测 |
| 模板参数声明成 `Query()` | 导入期 `AssertionError: Cannot use Query for path param` | 路径参数只能写名字或 `Path()` | 实测 |
| 模板参数声明成 `Header()` | 导入期 `AssertionError: Cannot use Header for path param` | 同上 | 实测 |
| 模板参数给默认值 | 导入期 `AssertionError: Path parameters cannot have default values` | 可选参数移出路径 | 实测 |
| 以为同名参数有「优先级链」 | 四个位置各自取值，互不影响 | 按「位置」理解 | 实测 |
| 用 `Request` 替代类型标注 | `?limit=abc` 也 200，脏数据进业务 | 能标注就标注 | 实测 |
| 把 `request.path_params` 当 int | 拿到 `"7"` 字符串 | 声明 typed 或自己 `int()` | 实测 |
| 依赖 `query_params.get()` 取第一个 | 实际取最后一个 | 用 `getlist()` | 实测 |
| 依赖 `headers.get()` 取最后一个 | 实际取第一个 | 用 `getlist()` | 实测 |
| 断言 422 错误的排列顺序 | 顺序与签名无关，测试随机失败 | 用集合比较 | 实测 |
| 用 404 判断参数非法 | 参数错误是 422 | 看 `loc` 首段 | 实测 |
| 把路径参数写成 `?item_id=7` | 走不到路径容器，取值失败 | 资源标识放路径 | 实测 |
| 函数参数写 `request` 不写类型 | 变成**必填查询参数**，缺失 422；传入得到 str | `request: Request` | 实测 |
| 用头传大 JSON | 头有 ~8KB 上限 | 用 body（第 13 章） | `[P1]` |
| 用查询参数传 token | 进访问日志与浏览器历史 | 用 `Authorization` 头 | `[P3]` |
| 用头传业务数据 | 语义混乱、无法校验结构 | 用 body | `[P1]` |
| Cookie 存大对象 | 单 Cookie 4KB、域名下总大小受限 | 只存 session id | 第 10 章 |
| 空串当缺失处理 | `?q=` 得到 `""`，不报 422 | 加 `min_length=1` | 实测 |
| 路径参数想做成可选 | 路径参数恒必填 | 可选条件放查询参数 | `[P2]` |
| 一个接口参数超过 8 个 | 签名难读、难复用 | 查询参数模型（第 09 章） | `[P5]` |
| 头值不 `strip()` | 前后空格原样进业务 | 手工 `.strip()` 或正则约束 | 实测 |
| 忘了 `Request` 也是依赖 | 以为它不占参数位 | 它与 typed 参数可共存 | `[P4]` |
| 把 `Request` 对象存到全局变量 | 并发请求互相串数据 | 用 `request.state` / `contextvars` | 第 52 章 |
| 读 `request.client.host` 当真实 IP | 代理后拿到代理 IP | 配 `--forwarded-allow-ips` | `[P6]` |
| 混用 Cookie 会话与 Bearer 令牌 | 两套身份来源冲突 | 只保留一套 | `[P3]` |
| 用 GET + 查询参数传敏感数据 | 进日志/浏览器历史/Referer | POST + body，或放头 | `[P3]` |

## 6. 最佳实践与编码建议

### 6.1 选型决策表

| 参数性质 | 放哪 | 理由 |
| --- | --- | --- |
| 资源标识（`order_id`） | 路径 | 可缓存、可分享、REST 语义 |
| 过滤/分页/排序 | 查询 | 组合自由、可省略 |
| 身份凭证 | 请求头 | 不进 URL、不进日志 |
| 会话状态 | Cookie（`httponly`） | 浏览器自动携带 |
| 复杂结构（嵌套/数组对象） | 请求体 | 头与查询表达不了（第 13 章） |
| 文件 | `multipart/form-data` | 第 28 章 |
| 内部调试开关 | 查询 + `include_in_schema=False` | 不污染对外文档 |

### 6.2 契约模板

```python
from typing import Annotated

from fastapi import APIRouter, Cookie, Header, Path, Query, Request

router = APIRouter(prefix="/orders", tags=["订单"])


@router.get("/{order_id}")
def get_order(
    order_id: Annotated[int, Path(ge=1, description="订单 ID")],
    request: Request,  # 只用于日志/追踪，不参与业务校验
    include: Annotated[list[str], Query(description="附加数据，可重复传")] = [],
    x_trace_id: Annotated[str | None, Header(alias="X-Trace-Id")] = None,
    sid: Annotated[str | None, Cookie()] = None,
) -> dict[str, object]:
    return {
        "order_id": order_id,
        "include": include,
        "trace_id": x_trace_id,
        "session": bool(sid),
        # 只在需要时读原始值，且明确它没被校验过
        "raw_path": request.path_params["order_id"],
    }
```

### 6.3 编码建议

| 建议 | 说明 |
| --- | --- |
| 一个接口最多 4–6 个参数 | 再多就抽查询参数模型或拆接口 |
| 能用 typed 就不用 `Request` | typed 有校验 + 文档，`Request` 两者都没有 |
| `Request` 只出现在「读不到」的场景 | 动态头名、原始 body、条件解析、日志 |
| 参数名统一 `snake_case` | 头名靠 `alias` 保风格，函数参数不要写连字符 |
| 同名跨位置时用 `alias` 而不是改语义 | 但更推荐**从一开始就别同名** |
| 每个对外参数写 `description` | `/docs` 是给别人看的契约 |
| 断言错误用集合，不用列表 | 顺序是内部实现 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[P1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/using-request-directly/ | `Request` 直取、`path_params`/`query_params` |
| `[P2]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/path-params/ | 路径参数必填、类型转换 |
| `[P3]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/query-params/ | 查询参数可选性、多值 |
| `[P4]` | 官方文档 | https://fastapi.tiangolo.com/zh/reference/request/ | `Request` 全部属性 |
| `[P5]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/query-param-models/ | 参数多时收成模型 |
| `[P6]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/behind-a-proxy/ | 代理与 `client` 地址 |
| `[P7]` | 规范 | https://spec.openapis.org/oas/v3.1.0#parameter-object | `in` 的四种取值 |

> **核对状态**：`[P1]`–`[P7]` 为官方文档/规范链接，**本次未逐页直连复核**；本章所有机制结论都有「实测」支撑，由 `examples/verify.py` 复现 10/10 通过。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 四类参数对应的容器与 `in` 值
- [ ] 为什么同名参数不会互相覆盖
- [ ] 位置判定规则的三级顺序
- [ ] 路径参数为什么不能有默认值
- [ ] `Request` 直取的两个代价
- [ ] 404 与 422 的分界线

**能写出（代码层）**：

- [ ] 一个接口同时收四类参数
- [ ] 同名参数跨位置共存的写法
- [ ] 用 `Request` 读 `getlist()` 的写法
- [ ] 错误聚合后按 `loc` 分类处理的代码

**能判断（避坑层）**：

- [ ] 看到 `Path()` 但模板里没有该名字 → 指出永远 422
- [ ] 看到模板参数写 `Query()` → 指出导入期报错
- [ ] 看到 `request` 没写类型 → 指出会变成必填查询参数
- [ ] 看到 `query_params.get()` 取多值 → 指出只拿最后一个
- [ ] 看到测试断言错误顺序 → 指出顺序不可依赖

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 10/10
- [ ] 手动访问 `/summary/7?q=hello` 看到 typed 与 raw 的差异
- [ ] `/docs` 里看到 `path/query/header/cookie` 四种参数

## 9. 下一章衔接

第 13 章 `请求体基础`：参数从 JSON 进来。本章的四个位置都是**标量/字符串**通道，表达不了嵌套结构与数组对象；下一章开始用 Pydantic 模型收 `body`，并讲清「请求体与查询参数混用」「`loc` 首段变成 `body`」这两件事。

本章留下的伏笔：

1. 同名冲突在 body 与查询参数之间会以另一种形式出现（第 16 章）。
2. `request.state` 在本章只出现一次，第 43 章用它做多租户传递。
3. `request.client` 的真实 IP 问题在第 54 章解决。
4. 参数超过 8 个的收束方案在第 09 章（查询）与第 13 章（body 模型）。
