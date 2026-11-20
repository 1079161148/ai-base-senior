# 27 表单数据（Form）

## 一句话结论

表单不是 JSON：它走 `application/x-www-form-urlencoded`（或 `multipart/form-data`），值都是字符串，靠 `Form()` 声明并自动转换类型。必须装 `python-multipart`。**不要**把 `Form()` 和 JSON 请求体模型写在同一个端点——不报错，但模型会变成「表单里一个传不进去的字段」（实测）。

学完这一章，你能：接收表单登录、做与 Query 相同的校验、处理别名、区分「表单体」与「URL 查询串」、看懂 422 的 `loc` 为什么带 `body`。

## 最小可运行案例

```python
from typing import Annotated, Any

from fastapi import FastAPI, Form

app = FastAPI()


@app.post("/login")
def login(
    username: Annotated[str, Form(min_length=3, max_length=20)],
    password: Annotated[str, Form(min_length=6)],
    remember: Annotated[bool, Form()] = False,
) -> dict[str, Any]:
    return {"username": username, "remember": remember}
```

调用方式（注意是 `data=` 不是 `json=`）：

```python
client.post("/login", data={"username": "alice", "password": "secret123"})
```

完整版本（类型转换、别名、Form+Query、共存陷阱）见 `examples/main.py`。

## 怎么跑

```powershell
cd "04-表单文件与编码\27-表单数据\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 表单登录成功 -> username=alice, authenticated=True
[PASS] OpenAPI 表单体 -> requestBody.content=['application/x-www-form-urlencoded']
[PASS] 默认值 -> remember 默认 False
[PASS] 缺字段 422 -> loc=['body', 'username']
[PASS] 长度约束 422 -> type=string_too_short
[PASS] int 自动转换 -> age='30' → 30 (int)，score 默认 60.0
[PASS] 转换失败 int_parsing -> type=int_parsing
[PASS] 范围约束 422 -> type=greater_than_equal
[PASS] 字段别名 -> 只认 user-name；username 报 missing
[PASS] Form + Query 混用 -> keyword=键盘, page=2
[PASS] JSON 体不被接受 -> JSON 体不被当表单解析 → missing
[PASS] Form 与 Body 共存 -> 定义期不报错；模型变成表单字段 item，实际传不进去

结果：12/12 通过
```

## 核心 API 速查

| 写法 | 作用 | 注意 |
| --- | --- | --- |
| `Annotated[str, Form()]` | 从表单体取值 | 必填 |
| `Annotated[str, Form()] = "默认"` | 可选 + 默认值 | 缺字段不报 422 |
| `Form(min_length=, ge=, pattern=...)` | 与 `Query` 同样的约束 | 先转换后校验 |
| `Form(alias="user-name")` | 外部字段名 | 内部参数名不变 |
| `Form(description=, examples=)` | 文档 | 出现在 `requestBody` schema |
| `Form(media_type="multipart/form-data")` | 指定媒体类型 | 有文件时必须 multipart |
| `client.post(..., data={...})` | httpx 发表单 | 用 `json=` 会 422 |

| 数据类型 | 表单里的写法 | 转换结果 |
| --- | --- | --- |
| `str` | `"alice"` | 原样 |
| `int` | `"30"` | `30` |
| `float` | `"60.5"` | `60.5` |
| `bool` | `"true"` / `"false"` | `True` / `False` |
| `bool` | `"1"` / `"0"` | 视 Pydantic 解析（本章未断言）|

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 用 `json=` 发表单 | 422，全部 `missing` | 用 `data=` |
| 忘了装 `python-multipart` | 启动报 `Form data requires "python-multipart"` | 加依赖 |
| `Form()` 和 JSON 模型写在同端点 | 不报错，模型变成传不进去的字段 | 二选一 |
| 分页参数也写成 `Form` | URL 里看不到，排障困难 | 分页用 `Query` |
| 以为 `Form` 字段可以是对象 | 只能字符串，复杂结构用 JSON | 换 `application/json` |
| 密码明文进日志 | 泄露 | 不记录 `Form` 字段原值 |
| 以为表单天然防 CSRF | Cookie 场景仍会被利用 | 加 CSRF token / SameSite |
| 别名用错方向 | 422 `missing` | 表单按 `alias` 传 |

## 毕业自查

- [ ] 能说出表单与 JSON 的 `Content-Type` 差异
- [ ] 能写出带约束的 `Form()` 字段
- [ ] 能解释 `Form` + `Query` 各自的数据来源
- [ ] 能说出 `Form` 与 JSON 模型共存时会发生什么
- [ ] 能解释 422 里 `loc=["body","field"]` 的含义
- [ ] 能说出为什么必须装 `python-multipart`
- [ ] 动手题一：给 `/login` 加 `Form(pattern=r"^[a-z0-9_]{3,20}$")`
- [ ] 动手题二：用 `curl -d "username=alice&password=secret123"` 调一次

> 想看表单与 multipart 的底层解析、大小限制、CSRF、18 条坑，继续读 [`base.md`](./base.md)。