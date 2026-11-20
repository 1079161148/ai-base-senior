# 27 表单数据 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「表单与 JSON 的解析差异、`Form` 的约束与转换、OpenAPI 形态、与 body 模型共存的陷阱、安全边界」拆开。学完这章，你要能一眼判断「这个字段该走表单还是 JSON」。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1 / python-multipart 0.0.34（本机实测） |
| 前置 | 第 07–12 章（参数体系）、第 13–20 章（模型与校验） |
| 覆盖范围 | `Form()`、类型转换、约束、别名、与 `Query` 混用、OpenAPI 表单体、共存陷阱 |
| 明确不覆盖 | 文件上传（第 28 章）、多文件混合（第 29 章）、`jsonable_encoder`（第 30 章）、CSRF 完整方案（第 51 章） |
| 学完验收 | 能跑通 `verify.py` 12/12、能解释 422 的 `loc`、能避开 Form+Body 共存 |

## 0. 怎么用这份文件

**依据约定**：`` `[Fn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 表单与 JSON 的本质差异
2 机制（第 2 节）    → 表单体是怎么被解析成参数值的
3 API（第 3 节）     → Form 参数逐个拆
4 边界（第 4 节）    → 共存陷阱、编码、大小、安全
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 登录表单模板
```

## 1. 概念：表单是「键值对字符串」，不是「有类型的对象」

| 维度 | JSON 体 | 表单体 |
| --- | --- | --- |
| `Content-Type` | `application/json` | `application/x-www-form-urlencoded` / `multipart/form-data` |
| 值类型 | 有类型（数字就是数字）| **全是字符串** |
| 嵌套结构 | 天然支持 | 不支持（除少数约定写法）|
| 浏览器原生提交 | 不行 | `<form>` 直接提交 |
| OpenAPI `requestBody.content` | `application/json` | `application/x-www-form-urlencoded` |

所以表单必须靠 Pydantic 做**字符串 → 目标类型**的转换，转换失败也是 422，但 `type` 不一定是 `missing`。

## 2. 机制：从表单体到参数值

```text
请求体（urlencoded / multipart）
  → python-multipart 解析成 [(key, value)] 列表
  → FastAPI 按参数名/alias 匹配
  → Pydantic 转类型 + 校验约束
  → 注入函数参数（失败：422，loc = ["body", field]）
```

| 事实 | 含义 |
| --- | --- |
| `loc` 第一段是 `"body"` | 与 Query 的 `["query", ...]` 区分 |
| 约束在校验后执行 | `min_length` 只对转换后的字符串生效 |
| 默认值即「可选」 | 有 `= 默认值` 就不会 `missing` |
| 未声明的表单字段 | 静默忽略（不报错）|

## 3. API 逐个拆解

### 3.1 必填与可选

```python
username: Annotated[str, Form(min_length=3)]
remember: Annotated[bool, Form()] = False
```

| 写法 | 行为 |
| --- | --- |
| 无默认值 | 必填，缺失 → `missing` |
| 有默认值 | 可选，缺失 → 用默认 |
| `str \| None = None` | 可选，缺失 → `None` |

### 3.2 类型转换

| 目标类型 | 输入 `"abc"` | 输入 `"30"` |
| --- | --- | --- |
| `int` | 422 `int_parsing` | 30 |
| `float` | 422 `float_parsing` | 30.0 |
| `bool` | 视解析（`"true"/"false"` 有效）| — |

测法：`verify.py` 的 `check_int_conversion` / `check_int_parse_error`。

### 3.3 约束与元数据

| 参数 | 作用 |
| --- | --- |
| `min_length` / `max_length` | 字符串长度 |
| `pattern` | 正则 |
| `ge` / `le` / `gt` / `lt` | 数值范围（先转换）|
| `alias` | 外部字段名 |
| `description` / `examples` | OpenAPI |
| `deprecated=True` | 文档标记 |

`Form` 与 `Query` 共享 Pydantic `FieldInfo`，参数几乎一一对应。

### 3.4 与其它参数来源混用

| 来源 | 声明 | 数据位置 |
| --- | --- | --- |
| 表单体 | `Form()` | body（urlencoded/multipart）|
| 查询串 | `Query()` | URL `?a=1` |
| 路径 | `Path()` | `/items/{id}` |
| 请求头 | `Header()` | headers |
| Cookie | `Cookie()` | cookies |

实测 `POST /search?page=2` + 表单 `keyword=键盘`：两者都能取到。

### 3.5 OpenAPI 形态

实测 `requestBody`：

```json
{"content": {"application/x-www-form-urlencoded": {"schema": {"$ref": "#/components/schemas/Body_login_login_post"}}},
 "required": true}
```

| 现象 | 说明 |
| --- | --- |
| 没有 `application/json` | 表单端点不声明 JSON |
| schema 名形如 `Body_<函数名>_<路径>_post` | 自动生成的表单模型 |
| `/docs` 里是表单输入框 | 可以直接试 |

## 4. 边界条件

### 4.1 Form 与 JSON 模型共存（实测，最容易误解）

```python
@app.post("/conflict")
def conflict(item: Item, username: Annotated[str, Form()]): ...
```

| 阶段 | 结果 |
| --- | --- |
| 定义期 | **不报错**（不会提示你不能混用）|
| OpenAPI | 仍是 `application/x-www-form-urlencoded`，模型变成 schema 里的 `item` 字段 |
| 请求带 `item={"name":"x"}` 文本 | 422 `model_attributes_type`（字符串无法转对象）|
| 请求不带 `item` | 422 `missing`（loc `["body","item"]`）|

结论：**共存等于该模型永远传不进去**。要表单就全用 `Form`，要结构就全用 JSON 模型。

### 4.2 表单与 JSON 的互斥选择

| 场景 | 选择 |
| --- | --- |
| 浏览器 `<form>` 提交 | 表单 |
| 前后端 JSON 联调 | JSON |
| 含文件 | `multipart/form-data`（第 28 章）|
| 需要嵌套对象/数组 | JSON |

### 4.3 编码与字符集

| 情况 | 结果 |
| --- | --- |
| 中文值（urlencoded）| 需正确 `Content-Type` 的 charset（未单独断言）|
| 文件名/路径 | 见第 28 章 |
| 值里含 `&` / `=` | 必须 URL 编码，客户端库会处理 |

### 4.4 大小限制

表单体没有内建上限，但反代（nginx `client_max_body_size`）与 ASGI 服务器会有。大表单要显式设限，否则可能被用来打内存（第 51 章）。

### 4.5 安全

| 风险 | 说明 |
| --- | --- |
| 密码明文字段 | 不要写进日志、不要回显 |
| CSRF | 基于 Cookie 的表单提交可被跨站伪造，加 CSRF token 或 `SameSite` |
| 表单字段注入 | 只接受声明过的字段，未声明的会被忽略（但别依赖它做过滤）|
| 暴力破解 | 登录表单要限流（第 51 章）|

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `client.post(..., json={...})` 调表单端点 | 422 全 `missing` | 用 `data=` | 实测 |
| 没装 `python-multipart` | 启动报缺少依赖 | 加进 dependencies | `[F1]` |
| `Form()` 与模型混写 | 模型永远传不进去 | 二选一 | 实测 |
| 认为混写会在启动时报错 | 不报错，线上才发现 | 靠评审/测试 | 实测 |
| 把分页放 `Form` | URL 无痕，排障难 | 用 `Query` | 实测 |
| 用 `Form` 传嵌套结构 | 无法表达 | 换 JSON | `[F1]` |
| 约束写错顺序 | `pattern` 对空串不触发 | 同时加 `min_length` | `[F2]` |
| 密码进日志 | 泄露 | 脱敏/不记录 | `[F4]` |
| 表单登录不防 CSRF | 可被跨站提交 | CSRF token / SameSite | `[F4]` |
| 认为表单字段类型是数字 | 全是字符串 | 依赖转换 | 实测 |
| 用 `alias` 后仍传内部名 | 422 `missing` | 按 alias 传 | 实测 |
| 未声明字段也想拿到 | 被忽略 | 显式声明 | `[F1]` |
| 大表单不设上限 | 内存风险 | 反代/应用层限制 | `[F3]` |
| 在 `Form` 里放 `bytes` | 语义不符 | 用 `File`（第 28 章）| `[F1]` |
| 表单提交后直接 200 无校验 | 脏数据入库 | 用约束 + 业务校验 | 第 20 章 |
| 响应里回显密码 | 泄露 | 出参模型去掉 | 第 21 章 |
| 只测成功路径 | 422 行为漂移 | 每个约束一条用例 | 第 71 章 |
| 用 `GET` 提交表单 | 参数进 URL、被缓存 | 用 `POST` | `[F3]` |
| 用 `Form()` 接文件字段 | 类型不符/解析异常 | 用 `File()`（第 28 章）| `[F1]` |

## 6. 最佳实践与编码建议

### 6.1 登录表单模板

```python
from typing import Annotated

from fastapi import APIRouter, Form

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login")
def login(
    username: Annotated[str, Form(min_length=3, max_length=64, pattern=r"^[A-Za-z0-9_.-]+$")],
    password: Annotated[str, Form(min_length=8, max_length=128)],
    remember: Annotated[bool, Form()] = False,
) -> TokenOut:
    ...
```

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 表单端点只收表单 | 不与 JSON 模型混写 |
| 登录/注册用表单 | 浏览器友好 |
| 业务 CRUD 用 JSON | 结构清晰 |
| 分页/过滤用 `Query` | 可分享、可缓存 |
| 密码字段不记录 | 日志脱敏 |
| 统一 422 处理 | 第 33 章 |

### 6.3 选型速查

| 需求 | 选择 |
| --- | --- |
| 登录、注册、搜索框 | `Form` |
| 前后端分离 CRUD | JSON 模型 |
| 文件 | `File`/`UploadFile`（第 28 章）|
| 表单 + 文件 | `multipart/form-data`（第 29 章）|

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[F1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/request-forms/ | `Form()` 用法与 `python-multipart` |
| `[F2]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/query-params-str-validations/ | 约束语义（Form 与 Query 共享）|
| `[F3]` | 规范 | https://www.rfc-editor.org/rfc/rfc1866#section-8.2 | `application/x-www-form-urlencoded` 编码 |
| `[F4]` | 安全指南 | https://owasp.org/www-community/attacks/csrf | 表单 CSRF 风险 |

> **核对状态**：`[F1]`–`[F4]` 为官方/规范/安全链接，**本次未逐页直连复核**；表单解析、类型转换、约束、别名、Form+Query、共存陷阱、OpenAPI 结构均为本机实测（python-multipart 0.0.34），`examples/verify.py` 复现 12/12 通过。中文表单编码与大小限制**未单独实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 表单与 JSON 的三种差异（内容类型/类型/嵌套）
- [ ] `loc=["body", f]` 的含义
- [ ] 为什么需要 `python-multipart`
- [ ] Form 与 Body 共存为什么会坏
- [ ] 表单字段为什么全是字符串

**能写出（代码层）**：

- [ ] 带约束的登录表单
- [ ] 可选字段与默认值
- [ ] `Form(alias=...)`
- [ ] Form + Query 混用
- [ ] 数值字段的转换与范围校验

**能判断（避坑层）**：

- [ ] 看到 `json=` 发表单 → 指出 422
- [ ] 看到 Form 与模型混写 → 指出模型传不进去
- [ ] 看到分页塞进表单 → 指出排障问题
- [ ] 看到密码进日志 → 指出泄露
- [ ] 看到表单登录无 CSRF 防护 → 指出风险

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 12/12
- [ ] `/docs` 里能用表单控件试登录
- [ ] `curl -d` 手工提交一次

## 9. 下一章衔接

第 28 章 `文件上传`：`File()` 与 `UploadFile` 的区别、为什么大文件必须用 `UploadFile`、`SpooledTemporaryFile` 的落盘阈值、文件名与内容类型不可信、如何安全校验与存储。

本章留下的伏笔：

1. `multipart/form-data` 的解析在 第 28 章展开。
2. 上传大小限制与安全存储在本章只提了一句，第 28 章细讲。
3. CSRF 完整方案在第 51 章。
4. 422 统一处理在第 33 章。