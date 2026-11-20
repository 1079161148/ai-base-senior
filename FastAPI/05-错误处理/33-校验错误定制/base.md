# 33 校验错误定制 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「校验错误从哪来、`errors()` 每个字段的含义、怎么翻译成前端能用的结构、为什么文档不同步」拆开。学完这章，你要能把 422 变成「前端能直接标红字段」的数据，而不是一句英文长句。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1（本机实测） |
| 前置 | 第 13–20 章（模型与校验）、第 31–32 章（异常体系） |
| 覆盖范围 | 默认 422 结构、`RequestValidationError`、`errors()` 字段、loc 拆分、ctx、json_invalid、文档同步 |
| 明确不覆盖 | 统一契约（第 34 章）、i18n 完整方案、前端错误展示 |
| 学完验收 | 能跑通 `verify.py` 14/14、能写出字段级错误结构、能说出文档不同步的补救 |

## 0. 怎么用这份文件

**依据约定**：`` `[Vn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 三种失败：传输/结构/语义
2 机制（第 2 节）    → 异常产生点与 errors() 结构
3 API（第 3 节）     → 处理器写法与字段映射
4 边界（第 4 节）    → json_invalid、multipart、ctx、文档
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 字段级错误模板
```

## 1. 概念：三类失败不要混

| 失败类型 | 例子 | 谁产生 | 状态码 |
| --- | --- | --- | --- |
| 传输层 | JSON 语法错、body 截断 | 解析器 | 422 `json_invalid` |
| 结构/类型 | 字段缺失、`"abc"` 给 int、超长 | Pydantic | 422 多种 `type` |
| 业务语义 | 余额不足、状态冲突 | 你的代码 | 402/409（第 32 章）|

`RequestValidationError` 只管前两类。

## 2. 机制：错误在哪一步产生

```text
请求进来
  → 解析 body（JSON/multipart/urlencoded）
        失败 → RequestValidationError(type=json_invalid …)
  → 按签名把参数交给 Pydantic 校验
        失败 → RequestValidationError(type=missing/int_parsing …)
  → 校验通过 → 进路由函数 → 可能抛业务异常
```

| 事实 | 说明 |
| --- | --- |
| 校验发生在路由函数**之前** | 路由里 `try/except` 抓不到 |
| 所有参数一起校验 | 一次能返回多条错误 |
| `loc` 带来源前缀 | `body`/`query`/`path`/`header`/`cookie` |
| 错误条目 4 个键（实测） | `type`/`loc`/`msg`/`input`；部分有 `ctx` |

### 实测：默认响应

```json
{"detail": [{"type": "int_parsing", "loc": ["body", "qty"],
             "msg": "Input should be a valid integer, unable to parse string as an integer",
             "input": "abc"}]}
```

**没有 `url`**。旧版 Pydantic 文档里的 `url` 字段在当前版本不存在，照着写断言会挂（本章踩过）。

## 3. API 逐个拆解

### 3.1 `errors()` 字段表

| 字段 | 类型 | 用途 |
| --- | --- | --- |
| `type` | str | **稳定机器码**，前端按它映射文案 |
| `loc` | tuple | 定位：来源 + 字段路径 |
| `msg` | str | Pydantic 英文描述（会随版本变）|
| `input` | Any | 原始输入（**可能敏感**）|
| `ctx` | dict? | 约束参数，如 `{"ge": 18}` |
| `url` | — | 实测不存在 |

### 3.2 `loc` 拆分

```python
loc = ("body", "address", "city")
source = loc[0]                    # "body"
field = "address.city"             # 点号路径
```

| loc | 含义 | 建议 field |
| --- | --- | --- |
| `("body","age")` | body 的 age | `age` |
| `("query","q")` | 查询串 q | `q` |
| `("path","item_id")` | 路径参数 | `item_id` |
| `("body","items",0,"name")` | 列表第 0 项 | `items.0.name` |
| `("body", 0)` | 整个 body 解析失败 | 用 `source` 兜底 |

### 3.3 处理器写法

```python
@app.exception_handler(RequestValidationError)
async def handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    ...
```

| 要点 | 说明 |
| --- | --- |
| 必须返回 `Response` | 同第 32 章 |
| 状态码可改 | 422 → 400 也行，但全站统一 |
| 能读 `request` | 可加 path、trace_id |
| 别做重 IO | 错误路径要快 |

### 3.4 `ctx` 的用法

| type | ctx 示例 |
| --- | --- |
| `greater_than_equal` | `{"ge": 18}` |
| `less_than_equal` | `{"le": 120}` |
| `string_too_short` | `{"min_length": 3}` |
| `string_too_long` | `{"max_length": 20}` |
| `int_parsing` | 无 |

实测文案：`数值太小（最小 18）`、`长度不足（至少 3 个字符）`。

## 4. 边界条件

### 4.1 非法 JSON（实测）

`content=b"{not json"` → 422，`type=json_invalid`，`loc` 为 `("body", 0)`。前端要按 `source=body` 且 `field` 为空处理。

### 4.2 缺 body（实测）

POST 一个需要 body 的端点但不发 body → 422 `missing`，`loc=("body",)`。

### 4.3 嵌套与列表

`address.city` 变点号路径；列表项会带下标（`items.0.name`）。

### 4.4 multipart / form（第 27–29 章衔接）

表单端点的校验错误同样走这个处理器，`loc[0]` 是 `body`（表单也算 body）。

### 4.5 文档不同步（实测，重要）

自定义处理器只改运行时响应。OpenAPI 里 `422` 仍引用 `HTTPValidationError`：

```json
"422": {"content": {"application/json": {"schema": {"$ref": "#/components/schemas/HTTPValidationError"}}}}
```

补救方式：

| 做法 | 成本 |
| --- | --- |
| 手动改 `app.openapi()` | 中，需维护 schema |
| 用 `responses={422: {...}}` 覆盖单端点 | 低，但重复 |
| 接受不同步，文档里写说明 | 低，易误导 |

### 4.6 敏感信息

`exc.body` 含原始请求体；`input` 含出错字段的原值。**不要**把整个 body 回显——登录接口会把密码写进错误响应和日志。

### 4.7 与业务异常的顺序

校验错误先于业务逻辑：请求结构不对时，路由里的余额判断根本不会执行。写测试时要区分「422 结构错」与「409 业务错」。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 断言错误条目有 `url` | 实测没有 | 只按 4 键处理 | 实测 |
| 以为文档会同步 | OpenAPI 仍默认 | 手动改 schema | 实测 |
| 回显 `exc.body` | 密码泄露 | 脱敏/不回显 | `[V3]` |
| 按 `msg` 映射前端文案 | 版本升级文案变 | 按 `type` | `[V1]` |
| `str(loc)` 直接给前端 | 难以解析 | 拆 `source`/`field` | 实测 |
| 忽略 `ctx` | 缺关键阈值信息 | 从 ctx 取 | 实测 |
| 只报第一条错误 | 用户反复试错 | 全量聚合 | `[V1]` |
| 422 改成 500 | 客户端误判 | 保持 4xx | `[V2]` |
| 处理器返回 dict | 500 | 返回 `Response` | 第 32 章 |
| 在路由里 try/except 校验 | 抓不到 | 用异常处理器 | 实测 |
| 手动构造 `RequestValidationError` | 构造签名不稳 | 用业务异常 | 第 32 章 |
| 处理器里查库翻译 | 错误路径变慢/再失败 | 静态映射表 | `[V3]` |
| `input` 原样返回给前端 | 可能反射 XSS | 转义后再用 | `[V3]` |
| 忽略 `json_invalid` | 前端提示「字段缺失」误导 | 单独处理 | 实测 |
| 用 400 又用 422 混着来 | 客户端逻辑分叉 | 全站统一 | `[V2]` |
| 列表错误不带下标 | 无法定位第几项 | `items.0.name` | 实测 |
| 处理器里 `await` 外部服务 | 错误响应变慢 | 只做本地转换 | `[V3]` |
| 只测正常请求 | 处理器 bug 上线才发现 | 每个约束一条用例 | 第 71 章 |
| 处理器里把状态码改成 200 | 客户端以为成功 | 保持 4xx | `[V2]` |

## 6. 最佳实践与编码建议

### 6.1 字段级错误模板

```python
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

MESSAGES: dict[str, str] = {
    "missing": "必填",
    "int_parsing": "必须是整数",
    "string_too_short": "太短",
    "string_too_long": "太长",
    "greater_than_equal": "太小",
    "less_than_equal": "太大",
    "json_invalid": "请求体不是合法 JSON",
}


def build_errors(exc: RequestValidationError) -> list[dict[str, Any]]:
    result: list[dict[str, Any]] = []
    for error in exc.errors():
        loc = tuple(error["loc"])
        source = loc[0] if loc and isinstance(loc[0], str) else "unknown"
        field = ".".join(str(part) for part in loc[1:]) or source
        ctx = error.get("ctx") or {}
        detail = {" ".join(f"{k}={v}" for k, v in ctx.items())} if ctx else ""
        result.append(
            {
                "field": field,
                "source": source,
                "code": error["type"],
                "message": MESSAGES.get(error["type"], "参数不合法") + (f"（{detail}）" if detail else ""),
            }
        )
    return result


def install_validation_handler(app: FastAPI) -> None:
    @app.exception_handler(RequestValidationError)
    async def handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        # 【为什么】只回白名单字段：不泄露 input/body，不依赖英文 msg
        return JSONResponse(
            status_code=422,
            content={"code": "VALIDATION_ERROR", "message": "参数不合法", "errors": build_errors(exc)},
        )
```

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 只暴露 `field`/`code`/`message` | 不回 `input`/`body` |
| 文案按 `type` 映射 | 稳定 |
| 保留 `code` 给前端 | 可国际化 |
| 全量错误一起返回 | 减少往返 |
| 文档显式声明 422 | 或接受并注明 |
| 处理器保持纯函数 | 便于测试 |

### 6.3 选型速查

| 需求 | 做法 |
| --- | --- |
| 默认结构够用 | 不写处理器 |
| 前端要字段级 | 自定义处理器 |
| 要错误码 | `type` 当 code 或另设表 |
| 要国际化 | 按 `type` + `Accept-Language` |
| 文档一致 | 手改 schema 或 `responses` |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[V1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/handling-errors/#requestvalidationerror-vs-validationerror | 校验错误处理器 |
| `[V2]` | 规范 | https://www.rfc-editor.org/rfc/rfc9110#section-15.5.21 | 422 语义 |
| `[V3]` | 安全指南 | https://owasp.org/www-community/Improper_Error_Handling | 错误信息泄露 |

> **核对状态**：`[V1]`–`[V3]` 为官方/规范/安全链接，**本次未逐页直连复核**；默认条目 4 键（无 `url`）、loc 前缀、ctx 文案、json_invalid、多条错误、嵌套路径、OpenAPI 不同步均为本机实测，`examples/verify.py` 复现 14/14 通过。表单/multipart 场景的 422 与 i18n 方案**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 三类失败与对应状态码
- [ ] 校验发生时机（路由前）
- [ ] `errors()` 的字段与含义
- [ ] `loc` 前缀与嵌套路径
- [ ] 文档为什么不同步

**能写出（代码层）**：

- [ ] 自定义处理器 + 字段级结构
- [ ] `ctx` 进文案
- [ ] 非法 JSON 单独处理
- [ ] 多条错误聚合
- [ ] 敏感字段不外泄

**能判断（避坑层）**：

- [ ] 看到断言 `url` → 指出实测无此字段
- [ ] 看到回显 body → 指出泄露
- [ ] 看到按 `msg` 做映射 → 指出不稳定
- [ ] 看到只取第一条 → 指出体验差
- [ ] 看到文档未改 → 指出契约不一致

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 14/14
- [ ] `/docs` 里故意传错类型看 422
- [ ] `curl` 传非法 JSON 看 `json_invalid`

## 9. 下一章衔接

第 34 章 `统一错误契约`：把 `HTTPException`、业务异常、校验异常、未捕获异常四条路径收敛成同一个 `{code, message, trace_id, details}` 结构，并保证日志里能按 `trace_id` 串起来。

本章留下的伏笔：

1. 统一结构在 第 34 章。
2. `trace_id` 与日志在 第 50 章。
3. 错误契约的测试在 第 71 章。
4. 文档同步在 第 26 章已讲手段。