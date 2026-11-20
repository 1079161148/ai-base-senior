# 05 路径参数 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「路径参数从哪来、类型转换在哪一步、404 与 422 的分界线、bool 的 6 种写法」拆开。学完这章，你要能对任意 `/users/{id}` 说出「传 `abc` 会返回什么、为什么」。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1 / Python 3.12.8（本机实测） |
| 前置 | 第 03 章（路由匹配）、第 04 章（骨架） |
| 覆盖范围 | 路径模板语法、类型转换、转换器、404/422、bool 行为、默认值陷阱、多参数、OpenAPI 声明 |
| 明确不覆盖 | `Path()` 的校验参数（06）、查询参数（07）、请求体（13） |
| 学完验收 | 能跑通 `verify.py` 10/10、能说出 `/users/abc` 返回 422 而 `/products/abc` 返回 404 的原因 |

## 0. 怎么用这份文件

**依据约定**：`` `[An]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 路径参数在 HTTP 请求的哪个位置
2 机制（第 2 节）    → 从 URL 到函数参数的 4 步（重点）
3 API（第 3 节）     → 模板语法、类型表、转换器表
4 边界（第 4 节）    → 404/422、bool、默认值、编码
5 注意事项（第 5 节）→ 32 条对照
6 最佳实践（第 6 节）→ 命名与选型
```

## 1. 概念：参数在请求的哪个位置

```text
GET /users/42/orders/7?status=paid HTTP/1.1
     └────┬────┘└───┬───┘└────┬────┘ └─────┬──────┘
       路径参数   路径参数   查询参数      请求头
       (path)     (path)    (query)      (header)
```

| 位置 | 声明方式 | 是否必填 | 是否进日志 | 依据 |
| --- | --- | --- | --- | --- |
| 路径 `path` | 写进路由模板 `{name}` | **总是必填** | 会（完整 URL） | `[A1]` |
| 查询 `query` | 函数参数但不在模板里 | 有默认值则可选 | 会 | 第 07 章 |
| 请求头 `header` | `Header()` | 视声明 | 部分 | 第 11 章 |
| Cookie | `Cookie()` | 视声明 | 否 | 第 10 章 |
| 请求体 `body` | Pydantic 模型 | 视声明 | 通常不 | 第 13 章 |

| 路径参适合 | 路径参不适合 |
| --- | --- |
| 资源标识（`/users/42`） | 密码、token（会进日志与浏览器历史） |
| 层级关系（`/users/42/orders`） | 大段文本（URL 长度限制） |
| 需要被缓存/CDN 识别的标识 | 可选过滤条件（用查询参数） |

## 2. 机制：从 URL 到函数参数的 4 步

```text
① 路由匹配：用编译好的正则匹配整个 path
   /users/{user_id}  →  ^/users/(?P<user_id>[^/]+)$
② 提取原始值：仍是字符串 "42"
③ Pydantic 校验：按标注 int 转换 → 42
   ├─ 成功 → 继续
   └─ 失败 → RequestValidationError → 422
④ 注入函数：以关键字参数调用 get_user(user_id=42)
```

| 步骤 | 谁在做 | 失败结果 | 依据 |
| --- | --- | --- | --- |
| ① | Starlette Router | 404 | `[A2]` |
| ② | Starlette | — | `[A2]` |
| ③ | FastAPI + Pydantic | 422 + `detail` 数组 | `[A3]` |
| ④ | FastAPI | 500（函数自己抛异常） | `[A3]` |

### 2.1 404 与 422 的分界线

实测两组对照：

```text
# 标注 int（正则只做 [^/]+）
GET /users/42   -> 200 {"user_id": 42, "type": "int"}
GET /users/abc  -> 422 {"detail": [{"type": "int_parsing", "loc": ["path", "user_id"], ...}]}

# 转换器 {code:int}（正则就是 [0-9]+）
GET /products/5   -> 200 {"code": 5}
GET /products/abc -> 404 {"detail": "Not Found"}
```

| 写法 | 路径正则 | `abc` 的结果 | 语义 |
| --- | --- | --- | --- |
| `{v}` + `v: int` | `[^/]+` | **422** | 路由存在，参数不合法 |
| `{v:int}` | `[0-9]+` | **404** | 路由根本不存在 |

| 选哪个 | 场景 | 理由 |
| --- | --- | --- |
| `{v:int}` | 资源 ID | 404 才是「没有这个资源」的正确语义 |
| `{v}` + `int` | 需要区分「路径对但参数错」 | 前端能提示「ID 必须是数字」 |

> 注意：这是本章最容易答错的面试题。记住分界线在**正则层**还是**校验层**：正则层失败 = 404，校验层失败 = 422。`[A2]` `[A3]`

### 2.2 422 响应的结构

实测完整结构：

```json
{
  "detail": [
    {
      "type": "int_parsing",
      "loc": ["path", "user_id"],
      "msg": "Input should be a valid integer, unable to parse string as an integer",
      "input": "abc"
    }
  ]
}
```

| 字段 | 含义 | 用途 |
| --- | --- | --- |
| `type` | Pydantic 错误类型码 | 前端可按码做国际化 |
| `loc` | 出错位置数组 | `["path","user_id"]` 表示路径参数 |
| `msg` | 英文消息 | 只适合开发期展示 |
| `input` | 原始输入 | **可能含敏感数据**，生产要过滤 |

| `loc` 第一段 | 含义 |
| --- | --- |
| `"path"` | 路径参数 |
| `"query"` | 查询参数 |
| `"header"` | 请求头 |
| `"cookie"` | Cookie |
| `"body"` | 请求体 |

## 3. 类型与转换器

### 3.1 常用类型的实测行为

| 标注 | 输入 | 输出 | 失败 `type` |
| --- | --- | --- | --- |
| `int` | `"42"` / `"-7"` | `42` / `-7` | `int_parsing` |
| `float` | `"3.14"` | `3.14` | `float_parsing` |
| `str` | `"abc"` | `"abc"`（不转换） | — |
| `bool` | `"true"` / `"1"` / `"yes"` | `True` | `bool_parsing` |
| `bool` | `"0"` | `False` | — |
| `uuid.UUID` | 标准 UUID | `UUID` 对象 | `uuid_parsing` |
| `datetime` | ISO 8601 | `datetime` | `datetime_parsing` |
| `date` | `"2026-01-01"` | `date` | `date_parsing` |

实测输出：

```text
/int/42        -> 200 {"value":42,"type":"int"}
/int/-7        -> 200 {"value":-7,"type":"int"}
/float/3.14    -> 200 {"value":3.14,"type":"float"}
/str/abc       -> 200 {"value":"abc","type":"str"}
/bool/true     -> 200 {"value":true,"type":"bool"}
/bool/1        -> 200 {"value":true,"type":"bool"}
/bool/yes      -> 200 {"value":true,"type":"bool"}
/bool/0        -> 200 {"value":false,"type":"bool"}
/bool/maybe    -> 422 bool_parsing
```

### 3.2 bool 的完整取值表

Pydantic v2 对布尔字符串的解析（`[A4]`）：

| 输入 | 结果 |
| --- | --- |
| `"true"` / `"True"` / `"TRUE"` | `True` |
| `"1"` / `"yes"` / `"on"` / `"t"` / `"y"` | `True` |
| `"false"` / `"False"` / `"FALSE"` | `False` |
| `"0"` / `"no"` / `"off"` / `"f"` / `"n"` | `False` |
| `"maybe"` / `"2"` | 422 `bool_parsing` |

| 风险 | 说明 |
| --- | --- |
| `/flags/1` 与 `/flags/true` 等价但 URL 不同 | CDN/浏览器缓存会存两份 |
| 日志里看不出实际语义 | 排查时要在脑内做映射 |
| 前端拼 URL 容易写出 `?flag=undefined` | 变成 422 |

> 注意：**不带默认值**的布尔路径参数在生产上几乎不该出现。要么用两个路径（`/enable`、`/disable`），要么放查询参数并显式声明默认值。

### 3.3 转换器表（Starlette 提供）

| 转换器 | 正则 | 示例 |
| --- | --- | --- |
| `str`（默认） | `[^/]+` | `/users/{name}` |
| `int` | `[0-9]+` | `/users/{id:int}` |
| `float` | `[0-9]+(\.[0-9]+)?` | `/prices/{v:float}` |
| `uuid` | UUID 标准格式 | `/orders/{oid:uuid}` |
| `path` | `.*` | `/files/{p:path}` |

| 约束 | 说明 | 依据 |
| --- | --- | --- |
| `int` 不接受负数 | 正则没有 `-`，`/users/-1` → 404 | `[A2]` |
| `path` 吞掉后面所有段 | 必须注册在最后 | 第 03 章 |
| 转换器与标注应一致 | `{oid:uuid}` + `oid: uuid.UUID` | `[A2]` |

> 注意：`{id:int}` 的正则不含负号，所以 `/items/-1` 是 **404**。如果业务需要负数，用 `{id}` + `int` 标注。

## 4. 边界条件

### 4.1 路径参数写默认值 = 静默失效（实测）

```python
@app.get("/legacy/{user_id}")
def legacy(user_id: int = 1) -> dict[str, object]:
    return {"user_id": user_id}
```

实测：

```text
注册成功（未报错）
/legacy/5   -> 200 {"user_id": 5}
/legacy/abc -> 422 int_parsing
OpenAPI     -> [{"name": "user_id", "in": "path", "required": true, "schema": {"type": "integer"}}]
```

| 事实 | 说明 |
| --- | --- |
| **不报错** | 很多人以为会启动失败 |
| 默认值**永远不会生效** | 路径不匹配时是 404，参数必填 |
| OpenAPI 里仍是 `required: true` | 没有 `default` |
| 危害 | 读代码的人以为可选，实际必须传 |

### 4.2 路径参数名必须与模板一致

| 写法 | 结果 |
| --- | --- |
| `"/users/{user_id}"` + `def f(user_id: int)` | ✅ |
| `"/users/{user_id}"` + `def f(id: int)` | ❌ 缺参数报错 |
| `"/users/{user_id}"` + `def f(user_id: int, id: int)` | ❌ `id` 变成必填查询参数 |

> 注意：名字不一致时不会「智能匹配」，而是把 `user_id` 当成缺失的路径参数直接报错。要用别名就写 `Path(alias="user_id")`（第 06 章）。

### 4.3 中文与特殊字符

| 输入 | 说明 |
| --- | --- |
| `/trips/北京/to/上海` | 实测可用，TestClient 会自动编码 |
| 真实浏览器 | 会编码成 `%E5%8C%97%E4%BA%AC`，服务端自动解码 |
| 空格 | 必须编码为 `%20`，否则请求行非法 |
| `/` 在值里 | 单段参数**不能**含 `/`，需要 `:path` |

### 4.4 路径参数的顺序

| 写法 | 结果 |
| --- | --- |
| `"/trips/{from_city}/to/{to_city}"` | ✅ 两个参数按位置提取 |
| `"/{a}/{b}"` | ✅ 但语义不清，且与其它路由冲突概率高 |

> 注意：`/{a}/{b}` 这种「两个裸段」会吃掉 `/anything/anything`，把后面所有同层级路由都堵死。第 03 章 2.1 的规则在这里同样生效。

### 4.5 尾斜杠

| 请求 | 注册 `/users/{id}` 时 |
| --- | --- |
| `/users/42` | 200 |
| `/users/42/` | 307 → `/users/42` |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 路径参数名与模板不一致 | 启动报错/缺值 | 名字必须一致 | `[A3]` |
| 给路径参数写默认值 | 实测静默失效 | 不写默认值 | 实测 |
| 以为 `{v:int}` 会 422 | 实际 404 | 要 422 用标注 | 实测 |
| 以为标注 `int` 会 404 | 实际 422 | 要 404 用转换器 | 实测 |
| `{id:int}` 接负数 | `/items/-1` → 404 | 用 `{id}` + `int` | 实测 |
| bool 路径参数 | `1`/`yes` 也是 True | 避免使用 | 实测 |
| 用路径参数传 token | 进日志与历史记录 | 用 Header | `[A5]` |
| 用路径参数传可选过滤 | 无法表达「不传」 | 用查询参数 | `[A1]` |
| `{p:path}` 放前面 | 后续路由全不可达 | 放最后 | 第 03 章 |
| `str` 接收 ID 再手工 `int()` | 错误码不统一 | 直接标注 `int` | `[A3]` |
| 忽略 422 的 `input` 字段 | 可能泄露敏感输入 | 生产过滤（第 33 章） | `[A3]` |
| 前端把 `undefined` 拼进 URL | `/users/undefined` → 422 | 前端校验 | `[A3]` |
| 路径里带 `.` 后缀（`/v1.0/x`） | 被当成值的一部分 | 用前缀或头 | `[A5]` |
| 路径含中文未编码 | 请求行非法 | 编码或改 ID | `[A6]` |
| 路径参数做 SQL 拼接 | SQL 注入 | 参数化查询 | `[A7]` |
| 用路径参数传文件路径 | 路径穿越 | 白名单校验 | `[A7]` |
| 一个接口 5 个路径参数 | URL 难读、易错 | 层级化或改 body | `[A5]` |
| 用 ID 自增暴露业务量 | 竞对推算单量 | UUID/短码 | `[A5]` |
| 路径参数大小写混用 | 大小写敏感 | 统一小写 | `[A5]` |
| 未处理 404 的前端 | 白屏 | 统一错误处理 | 第 31 章 |
| 用 `Optional[int]` 做路径参数 | 仍是必填 | 改查询参数 | 实测 |
| 多个路由同层级冲突 | 后者不可达 | 用不同前缀 | 第 03 章 |
| 路径参数直接当 ORM 主键 | 类型不匹配 | 转换后再查 | 第 56 章 |
| 查询大量 ID 用路径参数 | URL 超长 | 用 body 或逗号分隔查询参数 | `[A6]` |
| 用 `int` 接手机号 | 前导 0 丢失 | 用 `str` | `[A3]` |
| 用 `float` 接金额 | 精度丢失 | 用 `Decimal`（第 17 章） | `[A4]` |
| 用 `date` 接带时区时间 | 丢时区 | 用 `datetime` | `[A4]` |
| 没给路径参数加 `tags` | 文档杂乱 | 统一分组 | 第 26 章 |
| 路径参数缺 `description` | 文档无说明 | `Path(description=...)` | 第 06 章 |
| 依赖 `required` 默认可改 | 路径参数永远必填 | 不要试图改 | 实测 |
| 用 `Path()` 但没装 `annotated-types` | 导入报错 | FastAPI 已带 | `[A4]` |
| 在 `str` 上期望去掉空格 | 不会自动 strip | 自己 `.strip()` | `[A4]` |

## 6. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 资源 ID 用 `{id:int}` 或 `{id:uuid}` | 404 语义准确 | `[A2]` |
| 路径参数一律不写默认值 | 写了也不生效 | 实测 |
| 参数名与模板完全一致 | 避免隐式错误 | `[A3]` |
| 布尔语义用两个路径或查询参数 | 避免 6 种写法 | 实测 |
| 敏感信息不进路径 | 日志/历史/Referer | `[A5]` |
| 金额用 `Decimal` | 避免浮点误差 | `[A4]` |
| 手机号/编号用 `str` | 保留前导 0 | `[A3]` |
| 路径不超过 3 段 | 可读性 | `[A5]` |
| 统一小写 + 连字符 | 与第 03 章一致 | `[A5]` |
| 每个路径参数写 `description` | 文档可读 | 第 06 章 |

**风格示范**：

```python
from typing import Annotated

from fastapi import FastAPI, Path

app = FastAPI()


@app.get("/users/{user_id}/orders/{order_id}")
def get_order(
    user_id: Annotated[int, Path(gt=0, description="用户 ID")],
    order_id: Annotated[int, Path(gt=0, description="订单 ID")],
) -> dict[str, int]:
    """两个路径参数都用 Annotated + Path 声明约束与说明。"""
    return {"user_id": user_id, "order_id": order_id}
```

**边界**：

- 本章的转换行为基于 Pydantic v2 的 lax 模式；切换 `strict=True` 会拒绝 `"42"` 这类字符串输入，但 HTTP 路径永远是字符串，所以路径参数**必须**允许从字符串转换。
- `bool` 的 6 种写法在不同 Pydantic 小版本可能微调，写代码时不要依赖具体集合。
- 本章不涉及 `Path()` 的校验参数，那是第 06 章。

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[A1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/path-params/ | 路径参数声明与类型转换 |
| `[A2]` | 官方文档 | https://www.starlette.io/routing/ | 转换器、路径正则 |
| `[A3]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/handling-errors/ | 422 响应结构、`loc` |
| `[A4]` | 官方文档 | https://docs.pydantic.dev/latest/concepts/conversion_table/ | 类型转换表（含 bool） |
| `[A5]` | 规范 | https://restfulapi.net/resource-naming/ | 资源命名约定 |
| `[A6]` | 规范 | https://www.rfc-editor.org/rfc/rfc3986 | URL 编码与长度限制 |
| `[A7]` | 规范 | https://owasp.org/www-project-top-ten/ | 注入与路径穿越 |
| `[A8]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/path-params-numeric-validations/ | `Path()` 校验（第 06 章） |

> **核对状态**：`[A5]`–`[A7]` 为规范类来源；`[A1]`–`[A4]`、`[A8]` 按官方文档结构整理，**本次未逐页直连复核**。文中「实测」为本机 FastAPI 0.146.0 / Pydantic 2.14.1 输出，`examples/verify.py` 可复现 10/10 通过。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 路径参数与查询参数的三个区别
- [ ] 从 URL 到函数参数的 4 步
- [ ] 404 与 422 的分界线在正则层还是校验层
- [ ] 422 响应里 `loc` / `type` / `input` 的含义
- [ ] `bool` 的 6 种写法与风险
- [ ] 路径参数写默认值会发生什么

**能写出（代码层）**：

- [ ] 单参数 `{id:int}` 接口
- [ ] 多参数 `/a/{x}/b/{y}` 接口
- [ ] UUID 路径参数接口
- [ ] 路径参数 + 查询参数混用

**能判断（避坑层）**：

- [ ] 看到 `/users/abc` 能说出返回码（标注 `int` → 422）
- [ ] 看到 `/products/abc`（`{code:int}`）能说出 404
- [ ] 看到 `/items/-1` 能指出 404（正则无负号）
- [ ] 看到路径参数带默认值能指出无效
- [ ] 看到路径传 token 能指出日志泄露

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 10/10
- [ ] 改造 `{code:int}` 为 `{code}` 观察 404→422

## 9. 下一章衔接

第 06 章 `路径参数校验`：同一批参数，加上 `Path(gt=0, le=100, min_length, pattern, description, deprecated)`，讲清约束怎么进 OpenAPI、`Annotated` 与「默认值风格」两种写法、以及为什么 `Path()` 里必须写 `...`。

本章留下的伏笔：

1. `Path()` 还没用上——第 06 章。
2. `Annotated` 的角色——第 06 章正式引入，第 38 章用于依赖。
3. 422 结构如何统一改造——第 33 章。
