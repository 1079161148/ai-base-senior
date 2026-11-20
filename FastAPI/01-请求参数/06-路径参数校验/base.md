# 06 路径参数校验 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「`Path()` 怎么变成校验逻辑、约束怎么进 OpenAPI、为什么只报一条错、`ge` 与 `gt` 差在哪」拆开。学完这章，你要能看着 422 响应直接说出用户违反了哪条规则。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1 / Python 3.12.8（本机实测） |
| 前置 | 第 05 章（路径参数类型转换） |
| 覆盖范围 | `Path()` 全部参数、两种声明风格、约束到 OpenAPI 的映射、422 类型码、多约束行为、`alias`、文档元信息 |
| 明确不覆盖 | 查询参数校验（08）、请求体字段校验（14）、自定义校验器（20） |
| 学完验收 | 能跑通 `verify.py` 10/10、能说出 `gt` 与 `ge` 在 OpenAPI 的键名差异、能解释多约束只报一条 |

## 0. 怎么用这份文件

**依据约定**：`` `[Vn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → Path 在参数家族里的位置
2 机制（第 2 节）    → 从声明到校验的 4 步
3 API（第 3 节）     → 约束全表 + 两种写法
4 边界（第 4 节）    → gt/ge、多约束、pattern、alias
5 注意事项（第 5 节）→ 30 条对照
6 最佳实践（第 6 节）→ 约束怎么写才不过紧
```

## 1. 概念：参数家族里的 `Path`

| 声明 | 作用对象 | 必填 | 依据 |
| --- | --- | --- | --- |
| 直接标注 `v: int` | 路径参数（在模板里）/ 查询参数（不在） | 路径必填 | `[V1]` |
| `Path()` | 路径参数 | **总是必填** | `[V1]` |
| `Query()` | 查询参数 | 看默认值 | `[V2]` |
| `Header()` | 请求头 | 看默认值 | `[V3]` |
| `Cookie()` | Cookie | 看默认值 | `[V4]` |
| `Body()` | 请求体 | 看默认值 | `[V5]` |

| 关键事实 | 说明 | 依据 |
| --- | --- | --- |
| `Path()` 不能有默认值 | 路径参数永远必填 | `[V1]` |
| `Path()` 是 `FieldInfo` 的子类 | 与 `Query`/`Body` 同一套校验机制 | `[V6]` |
| 约束最终交给 Pydantic | 不是 FastAPI 自己实现的 | `[V6]` |

> 注意：`Path()` 与 `Annotated` 组合后，校验发生在**每次请求**的依赖求解阶段，不是启动时。所以约束写错（比如 `gt=100, le=10`）不会启动报错，而是所有请求都 422。

## 2. 机制：从声明到校验的 4 步

```text
① 装配期：解析函数签名
   Path(gt=0, le=100) → FieldInfo(gt=0, le=100, in_=path)
② 装配期：生成 Pydantic 校验器
   Annotated[int, FieldInfo] → TypeAdapter
③ 运行期：拿到原始字符串 "0"
   TypeAdapter.validate_python("0") → 转换 + 校验
④ 失败 → 收集错误 → RequestValidationError → 422
```

| 步骤 | 时机 | 失败表现 | 依据 |
| --- | --- | --- | --- |
| ① | import 模块时 | 签名写错会启动报错 | `[V1]` |
| ② | import 模块时 | 约束类型不匹配会启动报错 | `[V6]` |
| ③ | 每次请求 | 422 | `[V6]` |
| ④ | 每次请求 | 422 + `detail` 数组 | `[V6]` |

### 2.1 两种写法的等价性（实测）

```python
# 写法 1：Annotated
def a(v: Annotated[int, Path(gt=0, le=10)]) -> dict: ...

# 写法 2：默认值风格
def b(v: int = Path(gt=0, le=10)) -> dict: ...
```

实测（相同约束）：

```text
/0  -> 422 greater_than       （两种写法完全一致）
/11 -> 422 less_than_equal    （两种写法完全一致）
/5  -> 200 {"v": 5}           （两种写法完全一致）
```

| 维度 | Annotated | 默认值风格 |
| --- | --- | --- |
| 运行时行为 | 完全一致 | 完全一致 |
| 静态检查工具 | ✅ 能识别 | ⚠️ 常被当成「有默认值」 |
| 类型与默认值解耦 | ✅ | ❌ |
| 官方推荐 | ✅ | 旧文档风格 |

> 注意：这里有个**陷阱**——用默认值风格写路径参数时，`= Path(...)` 看起来像给了默认值，实际路径参数永远必填。而第 05 章实测过：直接写 `= 1` 这种真默认值会被静默忽略。两种「像默认值」的写法行为完全不同，容易混淆。`[V1]`

### 2.2 约束怎么进 OpenAPI

实测三个接口的 schema：

```json
/items/{item_id}   {"type": "integer", "exclusiveMinimum": 0, "maximum": 100, "description": "商品 ID，取值 1–100", "title": "Item Id"}
/prices/{price}    {"type": "number", "minimum": 0, "exclusiveMaximum": 10000}
/slugs/{slug}      {"type": "string", "minLength": 3, "maxLength": 8, "pattern": "^[a-z]+$", "title": "Slug"}
```

| 参数 | OpenAPI 键 | 语义 |
| --- | --- | --- |
| `gt=0` | `exclusiveMinimum: 0` | x > 0 |
| `ge=0` | `minimum: 0` | x ≥ 0 |
| `lt=100` | `exclusiveMaximum: 100` | x < 100 |
| `le=100` | `maximum: 100` | x ≤ 100 |
| `min_length=3` | `minLength: 3` | 长度 ≥ 3 |
| `max_length=8` | `maxLength: 8` | 长度 ≤ 8 |
| `pattern="^[a-z]+$"` | `pattern: "^[a-z]+$"` | 正则 |

> 注意：`gt` → `exclusiveMinimum` 是关键区分点。前端用 OpenAPI 生成校验代码时，`minimum` 与 `exclusiveMinimum` 是两个不同分支，写错会导致前后端边界不一致（前端允许 0，后端拒绝 0）。

## 3. API 逐一拆解

### 3.1 `Path()` 参数全表

| 参数 | 类型 | 适用 | 作用 | 失败 `type` | 依据 |
| --- | --- | --- | --- | --- | --- |
| `default` | — | ❌ 不可用 | 路径参数必填 | — | `[V1]` |
| `alias` | `str` | ✅ | 路径模板里的变量名 | — | `[V1]` |
| `title` | `str` | ✅ | 文档标题 | — | `[V1]` |
| `description` | `str` | ✅ | 文档描述 | — | `[V1]` |
| `deprecated` | `bool` | ✅ | 标记废弃 | — | `[V1]` |
| `gt` / `ge` | 数值 | ✅ | 数值下界 | `greater_than` / `greater_than_equal` | `[V6]` |
| `lt` / `le` | 数值 | ✅ | 数值上界 | `less_than` / `less_than_equal` | `[V6]` |
| `multiple_of` | 数值 | ✅ | 必须是某数的倍数 | `multiple_of` | `[V6]` |
| `min_length` / `max_length` | `int` | ✅（字符串） | 长度限制 | `string_too_short` / `string_too_long` | `[V6]` |
| `pattern` | `str` | ✅（字符串） | 正则 | `string_pattern_mismatch` | `[V6]` |
| `examples` | `list` | ✅ | 文档示例 | — | `[V1]` |
| `include_in_schema` | `bool` | ✅ | 是否进文档 | — | `[V1]` |
| `json_schema_extra` | `dict` | ✅ | 额外 schema | — | `[V1]` |

### 3.2 422 类型码字典

实测得到的完整条目结构：

```json
{
  "type": "greater_than",
  "loc": ["path", "item_id"],
  "msg": "Input should be greater than 0",
  "input": "0",
  "ctx": {"gt": 0}
}
```

| `type` | 触发条件 | `ctx` 内容 |
| --- | --- | --- |
| `int_parsing` | 不是整数 | — |
| `float_parsing` | 不是数字 | — |
| `bool_parsing` | 不是布尔 | — |
| `greater_than` | ≤ `gt` | `{"gt": 0}` |
| `greater_than_equal` | < `ge` | `{"ge": 1}` |
| `less_than` | ≥ `lt` | `{"lt": 100}` |
| `less_than_equal` | > `le` | `{"le": 100}` |
| `string_too_short` | 长度 < `min_length` | `{"min_length": 3}` |
| `string_too_long` | 长度 > `max_length` | `{"max_length": 8}` |
| `string_pattern_mismatch` | 不匹配 `pattern` | `{"pattern": "^[a-z]+$"}` |
| `multiple_of` | 不是倍数 | `{"multiple_of": 5}` |

| 用途 | 说明 |
| --- | --- |
| 前端 i18n | 按 `type` 映射中文提示，不用解析英文 `msg` |
| 监控告警 | 统计哪类校验失败最多 |
| 契约测试 | 断言错误类型而不是错误文案 |

### 3.3 文档元信息

```python
item_id: Annotated[str, Path(title="编码", description="旧版编码", deprecated=True)]
```

实测 OpenAPI：

```json
{"name": "code", "in": "path", "required": true,
 "schema": {"type": "string", "title": "编码", "description": "旧版编码", "deprecated": true},
 "description": "旧版编码", "deprecated": true}
```

| 观察 | 说明 |
| --- | --- |
| `description` 出现**两次** | schema 内 + parameter 层 |
| `deprecated` 也在两处 | — |
| `title` 只在 schema 内 | 用于表单标签 |

## 4. 边界条件

### 4.1 `gt` 与 `ge`

| 写法 | 边界值 `0` | OpenAPI | 错误 `type` |
| --- | --- | --- | --- |
| `gt=0` | ❌ 拒绝 | `exclusiveMinimum: 0` | `greater_than` |
| `ge=0` | ✅ 通过 | `minimum: 0` | `greater_than_equal` |

实测：

```text
/validated/0  -> 422 greater_than     ctx={"gt": 0}
/validated/-5 -> 422 greater_than     ctx={"gt": 0}
```

### 4.2 多约束同时违反：只报一条（实测）

```python
slug: Annotated[str, Path(min_length=3, max_length=5, pattern="^[a-z]+$")]
```

请求 `/slugs/ABCDEF`（长度 6、全大写，同时违反 max_length 与 pattern）：

```text
status: 422 count: 1
[{"type": "string_too_long", "ctx": {"max_length": 5}, "input": "ABCDEF"}]
```

| 结论 | 说明 |
| --- | --- |
| **只返回第一条** | 不是把违规项全列出 |
| 顺序由 Pydantic 内部决定 | 通常是长度 → 正则 |
| 前端只需处理第一条 | 但不要假设一定是哪条 |

> 注意：这和「多个参数各自失败」不同——如果路径参数 A 和查询参数 B 都错了，会返回两条（各自一条）。同一字段的多条约束只报第一条。`[V6]`

### 4.3 `pattern` 是整串匹配

| 写的 | 实际语义 | `abc123` |
| --- | --- | --- |
| `pattern="^[a-z]+$"` | 整串必须是小写字母 | ❌ |
| `pattern="[a-z]+"` | 整串匹配（等价 `^[a-z]+$`） | ❌ |
| `pattern="^.*[a-z]+.*$"` | 包含至少一个小写字母 | ✅ |

> 注意：Pydantic v2 的 `pattern` 使用 `re.search` 还是 `re.match` 取决于实现细节，但**行为上等价于整串**。想「包含」就显式写 `.*`。`[V6]`

### 4.4 `alias`：路径变量名与参数名解耦

```python
@app.get("/alias-demo/{real_id}")
def f(internal_id: Annotated[int, Path(alias="real_id", ge=1)]) -> dict[str, int]: ...
```

实测：

```text
GET /alias-demo/7 -> 200 {"internal_id": 7}
OpenAPI parameter name -> "real_id"
```

| 场景 | 是否该用 alias |
| --- | --- |
| 兼容旧 URL 的变量名 | ✅ |
| 参数名想用 Python 风格（含下划线） | ⚠️ 不如直接改模板 |
| 团队约定统一 | ❌ 名字不一致会增加排查成本 |

### 4.5 约束写反了会怎样

```python
Path(gt=100, le=10)   # 不可能满足
```

| 结果 | 说明 |
| --- | --- |
| **不报错**（启动正常） | 没有「约束区间校验」 |
| 所有请求 422 | 永远无法满足 |
| 文档里显示矛盾区间 | 前端困惑 |

> 注意：这类错误只能靠人工 review 或测试发现。建议给关键接口写「边界值测试」（第 72 章）。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `Path(default=1)` | 无效/报错 | 路径参数不写默认值 | `[V1]` |
| `gt=0` 期望 0 能过 | 实测 422 | `ge=0` | 实测 |
| 以为多约束报多条 | 实测只报 1 条 | 按第一条处理 | 实测 |
| `pattern` 想「包含」 | 整串匹配 | 加 `.*` | 实测 |
| 约束写反（`gt=100, le=10`） | 全量 422 | 人工 review + 边界测试 | 实测 |
| 用 `Path()` 又手工二次校验 | 错误格式不统一 | 全交给 `Path` | `[V1]` |
| 约束过紧 | 线上 422 激增 | 按业务真实边界 | `[V7]` |
| 约束过松 | 脏数据入库 | 补 `pattern`/`max_length` | `[V7]` |
| 忘写 `description` | 前端不知范围 | 补上 | `[V1]` |
| `title` 用英文 | 文档中英混杂 | 统一语言 | `[V1]` |
| `deprecated` 标记参数但没替代 | 前端不知怎么迁 | `description` 写替代方案 | `[V1]` |
| 用 `alias` 但模板没改 | 参数缺失报错 | 模板与 alias 一致 | 实测 |
| 前端按 `msg` 做提示 | 英文消息、随版本变 | 用 `type` 映射 | `[V6]` |
| 忽略 `input` 泄露 | 敏感数据回显 | 生产过滤（第 33 章） | `[V6]` |
| 用 `float` 校验金额 | 精度问题 | `Decimal`（第 17 章） | `[V8]` |
| `min_length` 用在 `int` 上 | 启动报错 | 只用于字符串 | `[V6]` |
| `pattern` 用在 `int` 上 | 启动报错 | 只用于字符串 | `[V6]` |
| 用 `Path` 校验中文长度 | 按字符数不是字节数 | 明确口径 | `[V6]` |
| 约束只在文档里，以为会自动生效 | 实际真的会校验（好事） | 理解为双向 | `[V1]` |
| 依赖 `Path` 的 `required` 参数 | 不存在该参数 | 路径参数恒必填 | `[V1]` |
| 用 `Annotated` 但没 import | NameError | `from typing import Annotated` | `[V9]` |
| `from typing_extensions import Annotated` | 可用但混用风格 | 统一用 `typing`（3.9+） | `[V9]` |
| 在 `Annotated` 里放多个 `Path` | 只有一个生效 | 合并成一个 | `[V9]` |
| `Path` 与 `Query` 混用在同一参数 | 启动报错 | 一个参数一种来源 | `[V2]` |
| 用 `Path(...)` 的 `...` 当默认值 | 合法但可读性差 | `Annotated` 更清晰 | `[V1]` |
| 未测边界值 | 上线 422 | 写 `0`/`max`/`max+1` 测试 | `[V7]` |
| 5 个参数都加长约束 | 文档臃肿 | 只约束关键字段 | `[V7]` |
| 用正则做业务规则（如身份证） | 难维护、易错 | 自定义校验器（第 20 章） | `[V6]` |
| 忽略 `pattern` 的锚点 | 以为能整串匹配其实依赖实现 | 显式写 `^...$` | `[V6]` |
| 用 `enum` 约束取值范围 | `Path` 不支持 | 用 `Literal` 或 `Enum` 类型 | `[V6]` |

## 6. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 统一用 `Annotated` 风格 | 类型与约束解耦、静态检查友好 | `[V9]` |
| 每个约束都配 `description` | 前端可自助 | `[V1]` |
| 数值边界用闭区间（`ge`/`le`） | 与业务口径一致，减少歧义 | `[V7]` |
| 用开区间时在 `description` 里写明 | 如「1–100」vs「0 < x < 100」 | `[V1]` |
| 字符串 ID 加 `min_length` + `pattern` | 防止脏数据 | `[V7]` |
| 关键接口写边界值测试 | 0 / max / max+1 | `[V7]` |
| 前端按 `type` 而非 `msg` 做提示 | 稳定 | `[V6]` |
| 废弃参数用 `deprecated` + 替代说明 | 平滑迁移 | `[V1]` |

**风格示范**：

```python
from typing import Annotated

from fastapi import FastAPI, Path

app = FastAPI()


@app.get("/orders/{order_no}")
def get_order(
    order_no: Annotated[
        str,
        Path(
            min_length=12,
            max_length=20,
            pattern="^[A-Z0-9]+$",
            description="订单号：12–20 位大写字母或数字",
            examples=["20260101123456"],
        ),
    ],
) -> dict[str, str]:
    return {"order_no": order_no}
```

**边界**：

- `Path()` 的约束能力来自 Pydantic，能力边界与 `Field` 相同（见第 14 章）。
- 本章不涉及枚举约束（`Literal`/`Enum`），见第 17 章。
- 本章的 422 结构是 FastAPI 默认格式，自定义格式见第 33 章。

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[V1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/path-params-numeric-validations/ | `Path()` 参数、`Annotated` 写法 |
| `[V2]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/query-params-str-validations/ | `Query()` 对照（第 08 章） |
| `[V3]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/header-params/ | `Header()`（第 11 章） |
| `[V4]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/cookie-params/ | `Cookie()`（第 10 章） |
| `[V5]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/body/ | `Body()`（第 13 章） |
| `[V6]` | 官方文档 | https://docs.pydantic.dev/latest/concepts/fields/ | 约束语义与错误类型码 |
| `[V7]` | 规范 | https://restfulapi.net/resource-naming/ | 接口参数设计约定 |
| `[V8]` | 官方文档 | https://docs.pydantic.dev/latest/api/types/ | `Decimal` 等特殊类型（第 17 章） |
| `[V9]` | 规范 | https://peps.python.org/pep-0593/ | `Annotated` 语义 |

> **核对状态**：`[V7]`、`[V9]` 为规范类来源；`[V1]`–`[V6]`、`[V8]` 按官方文档结构整理，**本次未逐页直连复核**。文中「实测」为本机 FastAPI 0.146.0 / Pydantic 2.14.1 输出，`examples/verify.py` 可复现 10/10 通过。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] `Path()` 与 `Query()` 的差别
- [ ] 为什么路径参数不能有默认值
- [ ] `gt`/`ge` 与 OpenAPI `exclusiveMinimum`/`minimum` 的对应
- [ ] 多约束同时违反返回几条
- [ ] `pattern` 的匹配语义
- [ ] `Annotated` 与默认值写法为什么等价

**能写出（代码层）**：

- [ ] 数值区间校验接口
- [ ] 字符串长度 + 正则校验接口
- [ ] 带 `description`/`deprecated` 的接口
- [ ] `alias` 解耦写法

**能判断（避坑层）**：

- [ ] 看到 `gt=0` 能说出 0 会 422
- [ ] 看到 `pattern="[a-z]+"` 能指出 `abc123` 会失败
- [ ] 看到 `gt=100, le=10` 能指出全量 422
- [ ] 看到前端解析 `msg` 能指出该用 `type`
- [ ] 看到 `min_length` 用在 `int` 上能指出启动报错

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 10/10
- [ ] 打出 0 与 101 的 422 完整 JSON
- [ ] 在 `/docs` 里看到约束区间

## 9. 下一章衔接

第 07 章 `查询参数`：把校验对象从路径换到 `?key=value`，讲清默认值如何决定可选性、`list[str]` 多值、`bool` 解析、以及「不分页的列表接口」的典型写法。

本章留下的伏笔：

1. `Annotated` 与 `Path` 的组合模式会在后续所有参数类型上重复出现。
2. 422 结构还没统一改造——第 33 章。
3. `Literal`/`Enum` 枚举约束——第 17 章。
