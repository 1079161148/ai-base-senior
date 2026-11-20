# 33 校验错误定制（RequestValidationError）

## 一句话结论

参数校验失败抛 `RequestValidationError`，默认 422 结构是 `{"detail": [{type, loc, msg, input}]}`——**实测没有 `url` 字段**（旧文档常写有，别照抄）。用 `@app.exception_handler(RequestValidationError)` 接管，把 `loc` 拆成 `source` + `field`、把 `type` 翻成中文、把 `ctx` 里的约束值带进文案。注意：**OpenAPI 不会跟着变**，422 仍指向 `HTTPValidationError`（实测）。

学完这一章，你能：把 422 改成前端好用的字段级结构、区分 body/query/path 来源、处理非法 JSON、多重错误聚合。

## 最小可运行案例

```python
from typing import Any

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()


class UserIn(BaseModel):
    username: str
    age: int


@app.exception_handler(RequestValidationError)
async def validation_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    errors = []
    for error in exc.errors():
        loc = tuple(error["loc"])
        source = loc[0] if loc[0] in {"body", "query", "path"} else "unknown"
        errors.append(
            {
                "field": ".".join(str(p) for p in loc[1:]) or source,
                "source": source,
                "message": error["msg"],
                "type": error["type"],
            }
        )
    return JSONResponse(
        status_code=422,
        content={"code": "VALIDATION_ERROR", "message": "请求参数校验失败", "errors": errors},
    )


@app.post("/users")
def create_user(user: UserIn) -> dict[str, Any]:
    return {"username": user.username}
```

请求 `{"username": "a", "age": "abc"}` → 422：

```json
{"code": "VALIDATION_ERROR", "message": "请求参数校验失败",
 "errors": [{"field": "age", "source": "body", "message": "Input should be a valid integer...", "type": "int_parsing"}]}
```

完整版本（中文文案 + `ctx` 约束值、嵌套路径、非法 JSON、多条错误、OpenAPI 不同步）见 `examples/main.py`。

## 怎么跑

```powershell
cd "05-错误处理\33-校验错误定制\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 默认 422 结构 -> 默认 keys=['input', 'loc', 'msg', 'type'], type=int_parsing
[PASS] 自定义结构 -> code=VALIDATION_ERROR, errors=1
[PASS] field/source 拆分 -> field=age, source=body
[PASS] 中文文案 + ctx -> 数值/长度文案都带 ctx
[PASS] 缺字段 -> email → 必填字段缺失
[PASS] 嵌套路径 -> field=address.city
[PASS] 多条错误 -> 5 条错误：['address.city', 'address.zipcode', 'age', 'email', 'username']
[PASS] 非法 JSON -> type=json_invalid
[PASS] query 来源 -> field=q, source=query
[PASS] path 来源 -> field=item_id, source=path
[PASS] Pydantic ctx -> int_parsing 无 ctx，但 type/loc 足够定位
[PASS] 合法请求 -> body/query 合法路径都 200
[PASS] 状态码 422 -> 状态码 422
[PASS] OpenAPI 仍默认 -> 422 仍引用 HTTPValidationError（需手动同步文档）

结果：14/14 通过
```

## 核心 API 速查

| 概念 | 值 |
| --- | --- |
| 异常类 | `fastapi.exceptions.RequestValidationError` |
| 状态码 | 422（可改 400，需全站统一）|
| `exc.errors()` | `list[dict]`，每条含 `type`/`loc`/`msg`/`input`，部分含 `ctx` |
| `exc.body` | 原始请求体（**可能含密码，别回显**）|
| `loc[0]` | `body` / `query` / `path` / `header` / `cookie` |

| 实测条目键 | 说明 |
| --- | --- |
| `type` | 机器码：`missing`/`int_parsing`/`string_too_short`/`json_invalid`… |
| `loc` | 元组，嵌套时多段：`("body","address","city")` |
| `msg` | 英文句子（Pydantic 提供）|
| `input` | 出错的原始值 |
| `ctx` | 约束参数，如 `{"ge": 18}`、`{"min_length": 3}`；`int_parsing` 没有 |

| 常见 `type` | 触发 |
| --- | --- |
| `missing` | 必填字段缺失 |
| `int_parsing` / `float_parsing` | 字符串转数字失败 |
| `string_too_short` / `string_too_long` | 长度 |
| `greater_than_equal` / `less_than_equal` | 数值范围 |
| `string_pattern_mismatch` | 正则不匹配 |
| `json_invalid` | 请求体不是合法 JSON |
| `model_attributes_type` | 需要对象但给了字符串 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 断言错误条目有 `url` | 实测键只有 4 个 | 按 `type/loc/msg/input` 写 |
| 改完处理器以为文档也变了 | OpenAPI 仍 `HTTPValidationError` | 手动改 `openapi()` |
| 直接返回 `exc.errors()` | 英文 + 多余字段暴露给用户 | 翻译 + 白名单字段 |
| 回显 `exc.body` | 密码等敏感字段泄露 | 不回显或脱敏 |
| `loc` 直接用 `str(loc)` | `"('body', 'age')"` 难以解析 | 拆分 `source`/`field` |
| 忽略 `ctx` | 文案没有「最小 18」这类关键信息 | 从 `ctx` 取约束值 |
| 只取 `errors()[0]` | 多字段错误只报一个 | 全量聚合 |
| 把 422 改成 500 | 客户端以为服务端挂 | 保持 4xx |
| 按 `msg` 做前端映射 | 文案会随 Pydantic 版本变 | 按 `type` 映射 |
| 手动 `raise RequestValidationError` | 构造复杂易错 | 用自定义异常（第 32 章）|
| 在处理器里再校验一遍 | 逻辑重复、可能再抛 | 只做格式转换 |

## 毕业自查

- [ ] 能默写默认 422 的 4 个键
- [ ] 能说明 `loc` 的结构与前缀含义
- [ ] 能把 `loc` 拆成 `source` + `field`
- [ ] 能从 `ctx` 取到 `ge`/`min_length` 并写进文案
- [ ] 能处理 `json_invalid`
- [ ] 能说出「文档不同步」这个坑
- [ ] 动手题一：把错误消息做成中英双语（按 `Accept-Language`）
- [ ] 动手题二：让 422 的 `errors` 按 `field` 排序并去重

> 想看 `RequestValidationError` 的构造、`errors()` 的完整字段表、OpenAPI 同步方案、18 条坑，继续读 [`base.md`](./base.md)。