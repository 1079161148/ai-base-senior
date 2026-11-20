# 21 响应模型（response_model）

## 一句话结论

`response_model` 是**出参白名单**：模型里没声明的字段一律丢弃，不管你的函数返回了什么。入参模型与出参模型必须分开，否则密码、内部备注迟早泄露。返回结构与响应模型不匹配是 **500**（服务端 bug），不是 422。

学完这一章，你能：用不同模型隔离敏感字段、用 `exclude`/`exclude_unset` 裁剪输出、知道 `response_model` 参数与函数返回注解谁优先、知道 `exclude_unset` **不**免除校验。

## 最小可运行案例

```python
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel

app = FastAPI()


class UserIn(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):        # 出参：没有 password
    username: str


@app.post("/users", response_model=UserOut)
def create_user(user: UserIn) -> Any:
    # 即返回里多带了 password，也不会出现在响应中
    return {"username": user.username, "password": user.password, "internal": "secret"}
```

完整版本（`exclude`、`exclude_unset`、参数优先级、`from_attributes`、500 反例）见 `examples/main.py`。

## 怎么跑

```powershell
cd "03-响应\21-响应模型\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 白名单过滤 -> 响应键=['email', 'nickname', 'username']
[PASS] OpenAPI 用出参模型 -> 200 → UserOut
[PASS] response_model_exclude -> 排除 email 后=['nickname', 'username']
[PASS] response_model_exclude_unset -> 只输出已设置字段={'username': 'alice'}
[PASS] exclude_unset 不免除校验 -> 必填字段缺失 → 500（exclude_unset 不能免除校验）
[PASS] 列表响应 -> 元素键=['email', 'nickname', 'username']
[PASS] 参数优先于注解 -> 返回注解 UserOut 被 response_model=TinyOut 覆盖
[PASS] from_attributes -> id=7 amount='19.90'
[PASS] 响应校验失败 500 -> 500 Internal Server Error
[PASS] 入出参是两个组件 -> UserIn 4 字段 / UserOut 3 字段

结果：10/10 通过
```

## 核心 API 速查

| 用法 | 作用 | 注意 |
| --- | --- | --- |
| `response_model=X` | 定义出参白名单 | 优先于函数返回注解 |
| `-> X`（返回注解） | 同上，少写一个参数 | 与 `response_model` 同时存在时后者生效 |
| `response_model_exclude={...}` | 在模型基础上减字段 | 只影响输出 |
| `response_model_include={...}` | 白名单内再取子集 | 与 `exclude` 同用易混乱 |
| `response_model_exclude_unset=True` | 没赋值的字段不输出 | **不改变校验**，必填缺失照样 500 |
| `response_model_exclude_none=True` | `None` 字段不输出 | 客户端拿不到「该字段为 null」信息 |
| `list[X]` / `X \| None` | 列表与可选响应 | 元素逐个过滤 |
| `ConfigDict(from_attributes=True)` | 从对象属性读取 | ORM/`SimpleNamespace` 场景 |

| 场景 | 状态码 | 原因 |
| --- | --- | --- |
| 入参校验失败 | 422 | 客户端参数问题 |
| 返回值不符合响应模型 | **500** | 服务端 bug（`ResponseValidationError`）|

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 入参模型直接当出参用 | 密码、内部字段泄露 | 单独 `UserOut` |
| 依赖「我 return 时没带 password」 | 某个分支顺手带上就泄露 | 靠响应模型兜底 |
| 以为 `exclude_unset` 能省掉必填校验 | 500，直接挂 | 换字段可选的出参模型 |
| 以为响应模型校验失败是 422 | 客户端看到 500 | 500 才是正确语义 |
| 函数返回注解与 `response_model` 都写还期望合并 | 只有参数生效 | 二选一 |
| 把 `id` 只放在返回注解里 | 参数覆盖后 id 消失 | 检查优先级 |
| 用 `exclude_none` 掩盖字段缺失 | 客户端分不清 null 与「没有」 | 明确契约 |
| 以为 docstring 不影响文档 | docstring 进 `description`，可能含敏感词 | 写文档前先看 `/openapi.json` |

## 毕业自查

- [ ] 能说出响应模型为什么是「白名单」而不是「黑名单」
- [ ] 能说出参数与返回注解谁优先
- [ ] 能说出 `exclude_unset` 对校验的影响（没有影响）
- [ ] 能说出响应校验失败为什么是 500
- [ ] 能写出 `list[T]` 的响应模型
- [ ] 能用 `from_attributes` 返回 ORM 对象
- [ ] 动手题一：给 `UserOut` 加 `created_at`，验证缺这个字段会 500
- [ ] 动手题二：写一个端点，用 `response_model_exclude_none=True`，观察 `nickname=None` 是否消失

> 想看响应模型的序列化链路、`ResponseValidationError` 细节、性能与安全边界、21 条坑，继续读 [`base.md`](./base.md)。
