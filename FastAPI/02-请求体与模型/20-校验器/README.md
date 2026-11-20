# 20 校验器（field_validator / model_validator）

## 一句话结论

`Field` 只能管单字段；**值变形**用 `@field_validator(mode="before")`，**单字段规则**用 `@field_validator`（after），**跨字段规则**用 `@model_validator(mode="after")`。错误定位不同：字段校验器报 `loc=["body","字段"]`，模型校验器报 `loc=["body"]`，`ValueError` 的消息在响应里带 `Value error, ` 前缀（实测）。

学完这一章，你能：写出两次密码一致、起止日期合法、空串转 `None` 的校验，并知道前端该按什么定位错误。

## 最小可运行案例

```python
from datetime import date

from fastapi import FastAPI
from pydantic import BaseModel, Field, field_validator, model_validator

app = FastAPI()


class BookingCreate(BaseModel):
    email: str = Field(min_length=5, max_length=64)
    password: str
    confirm: str
    start: date
    end: date

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("邮箱必须包含 @")     # → loc ["body","email"]
        return value.lower()

    @model_validator(mode="after")
    def check_rules(self) -> "BookingCreate":
        if self.password != self.confirm:
            raise ValueError("两次输入的密码不一致")  # → loc ["body"]
        if self.end < self.start:
            raise ValueError("结束日期不能早于开始日期")
        return self                              # 必须返回 self


@app.post("/bookings")
def create_booking(payload: BookingCreate) -> dict[str, object]:
    return {"booking": payload.model_dump(mode="json", exclude={"password", "confirm"})}
```

完整版本（`before` 变形、多规则、继承、OpenAPI 断言）见 `examples/main.py`。

## 怎么跑

```powershell
cd "02-请求体与模型\20-校验器\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 合法请求与值变形 -> email=user@example.com，note=None
[PASS] 字段校验器 loc -> value_error loc=['body', 'email']
[PASS] 一个校验器多条规则 -> 短密码 → 至少 8 位；全数字 → 不能全数字
[PASS] 模型校验器 loc -> loc=['body']（整个模型）
[PASS] 跨字段日期规则 -> end<start → value_error loc=['body']
[PASS] before 校验器拿原始值 -> 空白→None；带内容→strip 后保留
[PASS] Field 约束先执行 -> email='a@b' → string_too_short（还没走到 @ 检查）
[PASS] 多错误聚合 -> 2 条错误同时返回
[PASS] 校验器被继承 -> VIP 放宽到 20，邮箱校验器仍继承
[PASS] OpenAPI 不含规则 -> schema 只有字段，无跨字段规则

结果：10/10 通过
```

## 核心 API 速查

| 装饰器 | 时机 | 拿到什么 | 能改值 | 错误 `loc` |
| --- | --- | --- | --- | --- |
| `@field_validator("f")` | 类型+约束通过**后** | 已转换的值 | ✅（返回新值） | `["body","f"]` |
| `@field_validator("f", mode="before")` | 类型转换**前** | 原始输入（可能是任意类型） | ✅ | `["body","f"]` |
| `@model_validator(mode="after")` | 所有字段都通过后 | 模型实例 `self` | ✅（返回 `self`） | `["body"]` |
| `@model_validator(mode="before")` | 任何解析前 | 原始 dict | ✅（返回 dict） | `["body"]` |

| 抛什么 | 响应里的 `type` | `msg` 示例 |
| --- | --- | --- |
| `ValueError("xxx")` | `value_error` | `"Value error, xxx"` |
| `PydanticCustomError(...)` | 自定义 | 自定义（本章未实测） |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 跨字段规则写在 `Field` | 根本表达不了 | `@model_validator` |
| `model_validator` 忘了 `return self` | 返回 `None`，后续报错 | 始终 `return self` |
| 用 `assert` 做校验 | `python -O` 下断言被移除，校验消失 | 抛 `ValueError` |
| 以为校验器错误能定位到字段 | 模型校验器 `loc=["body"]` | 前端按 msg 映射，或拆成字段校验器 |
| 以为校验器规则会进 `/docs` | schema 里没有跨字段规则 | 用 `Field(description=...)` 补说明 |
| `mode="before"` 里按 `str` 处理 | 值可能是 `int`/`None` | 先判类型 |
| 一个校验器里堆十条规则 | 只有第一条错被返回 | 按字段拆，或一次收集多错 |
| 字段校验器不是 `classmethod` | 告警/行为不符预期 | 加 `@classmethod` |

## 毕业自查

- [ ] 能说出 `before` 与 after 的顺序与用途
- [ ] 能说出两类校验器的 `loc` 差异
- [ ] 能写出「两次密码一致」的校验
- [ ] 能写出「空串转 None」的校验
- [ ] 能解释为什么 `Field` 约束先于 after 校验器触发
- [ ] 能说出校验器为什么不出现在 OpenAPI
- [ ] 动手题一：加「手机号必须是 1 开头 11 位」的字段校验器
- [ ] 动手题二：让日期规则返回 `loc` 指向 `end` 字段（提示：拆成字段校验器 + `info.data`）

> 想看校验器执行顺序、`ValidationInfo` 取其他字段、性能与安全边界、20 条坑，继续读 [`base.md`](./base.md)。
