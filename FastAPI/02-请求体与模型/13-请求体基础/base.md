# 13 请求体基础 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「body 为什么必须用模型、422 的 `loc` 为什么两段、宽松转换到底转了什么、多余字段去哪了」拆开。学完这章，你要能独立写出一份不会被前端轻易打穿的请求体契约。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1 / Python 3.12.8（本机实测） |
| 前置 | 第 05–12 章（URL / 头 / Cookie 四类参数） |
| 覆盖范围 | `BaseModel` 声明 body、422 结构、宽松转换、`extra` 策略、`Content-Type`、可选 body、OpenAPI `requestBody` |
| 明确不覆盖 | 字段级约束 `Field`（第 14 章）、嵌套与列表（第 15 章）、多参数混用与 `embed`（第 16 章）、校验器（第 20 章） |
| 学完验收 | 能跑通 `verify.py` 11/11、能预测任意 body 的 422 结构、能说清「静默丢弃」的风险 |

## 0. 怎么用这份文件

**依据约定**：`` `[Bn]` `` 指向第 7 节；标「实测」的是本机真实输出，可用 `examples/verify.py` 复现。

**推荐顺序**：

```text
1 概念（第 1 节）    → body 与另外四类参数的本质差异
2 机制（第 2 节）    → 一次 POST 里 body 被处理的五步（重点）
3 API（第 3 节）     → 模型字段声明 + BaseModel 常用方法
4 边界（第 4 节）    → 空值/转换矩阵/extra/Content-Type/大小
5 注意事项（第 5 节）→ 23 条对照
6 最佳实践（第 6 节）→ DTO 命名与严格模式
```

## 1. 概念：body 是唯一能表达结构的位置

| 位置 | 能表达的数据 | 是否需要 `Content-Type` | 大小 | 可读性 |
| --- | --- | --- | --- | --- |
| 路径 | 单个标量 | 否 | 极短 | 好（日志可见） |
| 查询 | 标量 + 数组 | 否 | 短（URL 上限） | 好（日志可见，但敏感数据危险） |
| 请求头 | 单个标量 | 否 | ~8KB | 差（日志通常不记录） |
| Cookie | 单个标量 | 否 | 4KB | 差 |
| **请求体** | **嵌套对象 + 数组 + 任意深度** | **是** | 大（无框架上限） | 好（不落访问日志） |

结论：**只要数据结构不是「一个值」，就必须用 body**。反过来说，能用一个 id 表达的资源定位，不要塞进 body。

`Content-Type: application/json` 是 body 的「解码声明」。声明不对，框架就不会把它当 JSON 解析——这是本章最容易被忽略的失败模式（见 4.4）。

## 2. 机制：一次 POST 的五个步骤

```text
① 读取 Content-Type
   application/json 或 application/*+json → 走 JSON 解析
   其他（text/plain、缺失等）            → body 保持原始字节

② 解析 JSON
   失败（语法错误）→ 422 json_invalid，loc=["body", 偏移位置]

③ Pydantic 校验 + 转换
   缺字段 → missing（loc=["body", 字段]）
   类型错 → *_type（loc=["body", 字段]）
   多余字段 → 取决于 extra 策略

④ 聚合错误
   全部错误一次性返回；无错误则构造模型实例

⑤ 调用函数
   函数体拿到的是 ItemCreate 实例（不是 dict、不是 bytes）
```

实测对照（同一模型 `name: str, price: float, in_stock: bool = True`）：

| 请求体 | 状态 | `detail[0]` |
| --- | --- | --- |
| `{"name":"笔","price":9.9}` | 200 | — |
| `{"name":"笔"}` | 422 | `missing`，`loc=["body","price"]` |
| `{}` | 422 | 两条 `missing`（name、price） |
| 不发 body / `null` | 422 | 一条 `missing`，`loc=["body"]` |
| `{"name":1,"price":1}` | 422 | `string_type`，`loc=["body","name"]` |
| `{"name":"笔","price":1,"hack":1}` | 200 | —（`hack` 被丢弃） |

> `loc` 的段数是有信息量的：**两段 = 某个字段有问题；一段 = 整个 body 没拿到或不是对象**。

## 3. API 逐个拆解

### 3.1 字段声明的四种形态

| 写法 | 必填 | 缺省值 | OpenAPI `required` |
| --- | --- | --- | --- |
| `name: str` | 是 | 无 | 包含 |
| `name: str = "x"` | 否 | `"x"` | 不包含，schema 有 `default` |
| `name: str \| None = None` | 否 | `None` | 不包含，schema 允许 `null` |
| `name: str = Field(default_factory=str)` | 否 | 工厂产出 | 不包含（第 14 章） |

> `name: str = None` 是**错误写法**：类型说 str、默认给 None，静态检查会报，运行时也可能放行脏数据。用 `str | None = None`。

### 3.2 `BaseModel` 常用方法（Pydantic v2）

| 方法 | 作用 | 注意 |
| --- | --- | --- |
| `model_dump()` | 模型 → dict | 嵌套模型也会转 dict |
| `model_dump(mode="json")` | 转成「可 JSON 序列化」的值 | `datetime`→str 等 |
| `model_dump_json()` | 直接出 JSON 字符串 | 绕开 FastAPI 编码器时用 |
| `model_validate(obj)` | dict → 模型（带校验） | 手工校验外部数据 |
| `model_validate_json(s)` | JSON 字符串 → 模型 | 处理消息队列/文件时用 |
| `model_copy(update={...})` | 复制并覆盖字段 | **不校验**覆盖值（第 18 章） |
| `model_json_schema()` | 生成 JSON Schema | 与 OpenAPI 组件同源 |
| `ItemCreate.model_fields` | 字段元信息 | 写通用逻辑时用 |

`model_copy(update=...)` 不校验这一点很关键：它适合「已知合法的内部改写」，不适合处理外部输入。

### 3.3 可选性的两个层级

```python
# 层级一：整个请求体可选
def f(item: ItemCreate | None = None): ...


# 层级二：请求体必填，内部字段可选
class ItemCreate(BaseModel):
    name: str
    description: str | None = None
```

| 写法 | body 不传 | `{}` |
| --- | --- | --- |
| `item: ItemCreate \| None = None` | 200，`item is None` | 422（name 缺失） |
| `item: ItemCreate` | 422 `loc=["body"]` | 422（name 缺失） |

## 4. 边界条件

### 4.1 空值三兄弟

| 输入 | HTTP body | 结果 |
| --- | --- | --- |
| 不发 body | （空） | 422 一条，`loc=["body"]`，`input=null` |
| `null` | `null` | 同上（实测与「不发」等价） |
| `{}` | 对象但无字段 | 422 多条，`loc=["body", 字段]` |
| 可选 body + 不发/`null` | — | 200，参数为 `None` |

> 「客户端没传」和「客户端传了空对象」在日志里必须能区分，否则排查时会误判成前端漏传。

### 4.2 宽松转换矩阵（Pydantic v2 默认 `lax` 模式）

| 目标类型 | 接受 | 拒绝 |
| --- | --- | --- |
| `int` | `"12"`、`12`、`12.0` | `"12.5"`、`12.5`（`int_from_float`）、`true` |
| `float` | `"9.9"`、`9`、`9.9` | `"abc"`、`NaN` 字符串 |
| `bool` | `true`、`"true"`、`"1"`、`"yes"`、`"on"` / 对应 false 值 | `"maybe"`、`2` |
| `str` | `"x"` | `1`、`true`（**不转**） |
| `datetime` | ISO 8601 字符串 | 无时区的歧义格式（建议统一带时区） |

实测两条例：

```text
{"name":"笔","price":"9.9"} -> price == 9.9（float）
{"name":1,"price":1}        -> 422 string_type（"1" 不会生成）
```

> 转换的**方向性**是重点：数字←字符串可以，字符串←数字不行。前端传 `id: 123` 给 `str` 字段会直接 422，这是联调高频事故。

### 4.3 `extra` 三种策略

| 配置 | 多余字段 | 实测结果 |
| --- | --- | --- |
| 默认（`ignore`） | 静默丢弃 | 200，`hack` 不在 `model_dump()` 里 |
| `extra="forbid"` | 报错 | 422 `extra_forbidden`，`loc=["body","hack"]` |
| `extra="allow"` | 保留 | 出现在 `model_extra` 里（不建议） |

取舍：

- **公开 API**：`forbid` 更安全——前端拼错字段名会立刻报错，而不是「数据莫名其妙没生效」。
- **对接第三方 / 版本兼容**：`ignore` 更宽容——对方加字段不会打挂你。
- **永远不要 `allow`**：等于把未知数据带进业务，后面必然出现「这个字段哪来的」。

### 4.4 `Content-Type` 陷阱（实测）

```text
POST /items
Content-Type: text/plain
body: {"name":"pen","price":1}

→ 422 {"type":"model_attributes_type","loc":["body"],
       "msg":"Input should be a valid dictionary or object to extract fields from",
       "input":"{\"name\":\"pen\",\"price\":1}"}
```

注意 `input` 是**字符串**而不是解析后的对象——说明框架没有做 JSON 解析。这条错误的可读性很差，前端常误以为是模型写错了。

结论：

- 客户端必须发 `application/json`（`fetch` 用 `JSON.stringify` + 头，`requests` 用 `json=`，`httpx` 用 `json=`）。
- 服务端不要为「兼容不规范的客户端」去手工 `json.loads(request.body())`，那等于放弃整章的所有校验能力。

### 4.5 其他边界

| 边界 | 行为 | 建议 |
| --- | --- | --- |
| body 是数组 `[{...}]`，模型是对象 | 422 `model_attributes_type` | 模型改成 `list[Item]`（第 15 章） |
| JSON 语法错（少引号、尾逗号） | 422 `json_invalid` | 前端修；必要时第 33 章定制文案 |
| body 极大（百 MB） | 无框架上限，全量读入内存 | 用流式（第 60 章）或对象存储直传 |
| GET 带 body | 我们的 `/items` 只注册了 POST → **405** | 不要用 GET 传 body |
| 金额用 `float` | 二进制浮点误差 | 用 `Decimal`（第 17 章） |
| 重复 JSON key | 解析器行为（通常后者覆盖） | 客户端不要产生重复 key |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `item["name"]` 取字段 | `TypeError`（模型不是 dict） | `item.name` 或 `item.model_dump()` | `[B1]` |
| 以为多传字段会报错 | 默认静默丢弃（实测 200） | `extra="forbid"` | 实测 |
| 以为 `{}` 与「不传 body」等价 | `{}` 报多条字段错；不传只报一条 `loc=["body"]` | 按 `loc` 段数区分 | 实测 |
| 用 `str = None` 表示可选 | 类型不符 | `str \| None = None` | `[B2]` |
| 以为 body 可选 = 字段可选 | 两个层级，行为完全不同 | 分清参数级/字段级 | 实测 |
| `Content-Type` 不是 JSON | 422 `model_attributes_type`，`input` 是字符串 | 客户端显式声明 | 实测 |
| 用 `request.body()` 又想用模型 | 二选一，模型拿到的 body 已被消费 | 需要原始 body 就不要声明模型 | `[B1]` |
| 手工 `json.loads` 替代模型 | 失去校验/文档/422 契约 | 声明模型 | `[B1]` |
| 模型字段太多（>15） | 难维护、难复用 | 拆子模型（第 15 章） | `[B2]` |
| 用 `dict` 接 body | 无校验、无文档 | 用模型 | `[B1]` |
| `id` 交给客户端传 | 可被伪造 | 服务端生成 | 第 19 章 |
| 把 ORM/DB 行对象直接当模型 | 泄露内部字段 | 用独立 DTO（第 21 章） | `[B2]` |
| 金额/价格用 `float` | 精度误差 | `Decimal`（第 17 章） | `[B3]` |
| 时间不带时区 | 跨时区错乱 | 统一 UTC + 时区偏移 | `[B3]` |
| 依赖 `"9.9"` 被转换 | 这只是 lax 模式，可被关掉 | 前端传正确类型 | `[B3]` |
| 以为 `1` 会变成 `"1"` | 不会，直接 422 | 前端转字符串 | 实测 |
| 嵌套字段写 `a.b: str` | 语法上不存在这种写法 | 定义子模型（第 15 章） | `[B2]` |
| 允许任意字段（`extra="allow"`） | 脏数据进业务 | `ignore` 或 `forbid` | 实测 |
| 把校验写在函数体里 | 重复代码 + 422 结构不统一 | 用模型/`Field`（第 14 章） | `[B1]` |
| 用 GET 传 body | 网关可能丢弃，语义错 | POST/PUT/PATCH | `[B5]` |
| 忽略 `422` 的 `input` 字段 | 排查时看不到原始输入 | 日志记录 `loc` + `input`（脱敏） | `[B5]` |
| 响应里直接返回模型对象 | 依赖框架默认编码，行为不显式 | 显式 `response_model`（第 21 章） | `[B6]` |
| 超大 body 直连应用 | 内存被打爆 | 上传走对象存储 / 流式 | 第 60 章 |
| 用中文做字段名 | 与前端/其他语言客户端不兼容 | 用 `alias` 映射（第 14 章） | `[B4]` |

## 6. 最佳实践与编码建议

### 6.1 DTO 命名与职责

```python
from pydantic import BaseModel, ConfigDict


class ItemCreate(BaseModel):
    """创建入参：只有客户端能给的可写字段。"""

    model_config = ConfigDict(extra="forbid")

    name: str
    price: float
    in_stock: bool = True


class ItemUpdate(BaseModel):
    """局部更新入参：全字段可选（第 18 章）。"""

    model_config = ConfigDict(extra="forbid")

    name: str | None = None
    price: float | None = None
    in_stock: bool | None = None
```

| 建议 | 说明 |
| --- | --- |
| 模型名带动作后缀 | `ItemCreate` / `ItemUpdate` / `ItemOut`，一眼看出用途 |
| 不给模型加业务方法 | 模型只负责结构与校验；业务逻辑放 service 层 |
| 主键/时间戳不进 Create 模型 | 由服务端生成，避免客户端伪造 |
| 公开 API 用 `extra="forbid"` | 让「拼错字段」立刻暴露 |
| 每个模型写 docstring | `/docs` 的 schema 描述会更好读 |
| 多传字段一律当攻击面 | 任何「静默丢弃」都要在契约里说清 |

### 6.2 一份可直接抄的创建接口

```python
from fastapi import FastAPI, status
from pydantic import BaseModel, ConfigDict

app = FastAPI()


class ItemCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    name: str
    price: float
    in_stock: bool = True


@app.post("/items", status_code=status.HTTP_201_CREATED)
def create_item(item: ItemCreate) -> dict[str, object]:
    # 这里 item 一定是合法的；剩下的只有业务规则
    return {"id": 1, **item.model_dump()}
```

- `str_strip_whitespace=True`：去掉首尾空格，避免 `" 笔 "` 与 `"笔"` 被当成两个商品。
- `status_code=201`：创建语义（第 22 章展开）。
- 返回前显式构造 dict：不把内部模型直接当响应（第 21 章）。

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[B1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/body/ | 用 `BaseModel` 声明请求体、`model_dump()` |
| `[B2]` | 官方文档 | https://docs.pydantic.dev/latest/concepts/models/ | 模型定义、字段可选性、方法 |
| `[B3]` | 官方文档 | https://docs.pydantic.dev/latest/concepts/conversion_table/ | lax/strict 类型转换矩阵 |
| `[B4]` | 官方文档 | https://docs.pydantic.dev/latest/api/config/ | `ConfigDict`（`extra`、`alias`、`str_strip_whitespace`） |
| `[B5]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/handling-errors/ | 422 结构与 `loc` |
| `[B6]` | 规范 | https://spec.openapis.org/oas/v3.1.0#request-body-object | `requestBody.required` 缺省含义 |

> **核对状态**：`[B1]`–`[B6]` 为官方文档/规范链接，**本次未逐页直连复核**；本章所有状态码与错误结构均为本机实测，`examples/verify.py` 可复现 11/11 通过。`ConfigDict` 的 `str_strip_whitespace` 属文档特性，未在本章脚本中断言。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 为什么嵌套结构只能用 body
- [ ] `loc` 一段与两段分别代表什么
- [ ] lax 模式的转换方向性（谁能转谁）
- [ ] `extra` 三种策略的取舍
- [ ] `Content-Type` 不对时框架做了什么
- [ ] 「body 可选」与「字段可选」的区别

**能写出（代码层）**：

- [ ] 一个带默认值字段的模型
- [ ] 一份 `extra="forbid"` 的严格模型
- [ ] 可选 body 的接口
- [ ] 用 `model_dump()` 回显的接口

**能判断（避坑层）**：

- [ ] 看到 `item["x"]` → 指出模型不是 dict
- [ ] 看到多传字段 200 → 指出默认 `ignore`
- [ ] 看到 `name: str = None` → 指出类型不一致
- [ ] 看到 422 `model_attributes_type` → 先查 `Content-Type`
- [ ] 看到 `float` 存金额 → 指出精度风险

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 11/11
- [ ] `/docs` 里点开 `POST /items` 看到 `ItemCreate` 的字段与默认值
- [ ] 手工发一次 `text/plain` 请求，复现 `model_attributes_type`

## 9. 下一章衔接

第 14 章 `Field 字段约束`：本章只区分了「必填/可选」，但 `price` 还能是负数、`name` 还能是空串。下一章用 `Field` 给每个字段加长度、范围、正则、别名与文档示例，并把「约束写在类型上而不是函数体里」这件事做到底。

本章留下的伏笔：

1. `extra`、`alias`、`str_strip_whitespace` 的完整配置在第 14/19 章。
2. 模型嵌套与列表在第 15 章；同名字段与 `embed` 在第 16 章。
3. 局部更新的「没传」与「传了 null」在第 18 章用 `exclude_unset` 区分。
4. 422 的 `input` 是否要回传给前端、如何脱敏，在第 33 章统一处理。
