# 20 校验器 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「四类校验器的执行顺序、错误定位规则、跨字段怎么拿其他值、性能与安全边界」拆开。学完这章，你要能判断一条规则该写在 `Field`、字段校验器还是模型校验器。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1（本机实测） |
| 前置 | 第 13–19 章（模型、约束、复用） |
| 覆盖范围 | `field_validator`（before/after）、`model_validator`（before/after）、错误定位、继承、`ValidationInfo` |
| 明确不覆盖 | 自定义类型（`__get_validators__`）、`PydanticCustomError` 深入（仅提及）、异步校验（不支持） |
| 学完验收 | 能跑通 `verify.py` 10/10、能预测 `loc`、能说出四类校验器的顺序 |

## 0. 怎么用这份文件

**依据约定**：`` `[Vn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 什么规则该写在哪
2 机制（第 2 节）    → 四类校验器的执行顺序（重点）
3 API（第 3 节）     → 装饰器、参数、返回值约束
4 边界（第 4 节）    → loc、多错误、继承、性能、安全
5 注意事项（第 5 节）→ 20 条对照
6 最佳实践（第 6 节）→ 模板与拆分建议
```

## 1. 概念：规则该写在哪一层

| 规则类型 | 例子 | 写在哪 |
| --- | --- | --- |
| 单字段、纯声明式 | 长度、范围、正则、枚举 | `Field`（第 14 章） |
| 值变形 | 去空格、转小写、空串转 `None` | `field_validator(mode="before")` |
| 单字段但需要逻辑 | 密码强度、手机号校验位 | `field_validator`（默认 after） |
| 跨字段 | 两次密码一致、结束≥开始、合计=明细和 | `model_validator(mode="after")` |
| 整个入参结构 | 至少给一个筛选条件 | `model_validator(mode="after")` |
| 需要查库/调外部 | 用户名是否已存在 | **服务层**，不要放校验器 |

最后一行很重要：校验器是**纯函数**，不能查库（没有 `await`、拿不到依赖）。需要外部信息的校验放业务层，返回 409/422 由你自己控制。

## 2. 机制：四类校验器的执行顺序

```text
① model_validator(mode="before")   拿原始 dict，可整体改写
② 字段类型转换                     "2" → 2
③ 字段约束校验                     min_length / ge / pattern ...
   └─ 失败 → 直接 422，后面的校验器都不执行（实测）
④ field_validator(mode="before")   拿原始输入
⑤ field_validator（默认 after）     拿转换后的值，按字段声明顺序执行
⑥ model_validator(mode="after")    拿完整模型实例
```

实测证据：

| 输入 | 结果 | 说明 |
| --- | --- | --- |
| `email="a@b"`（长度 3 <5） | `string_too_short` | ③ 先于 ⑤，@ 检查没跑到 |
| `email="bademail"`（长度 8） | `value_error, 邮箱必须包含 @` | ③ 通过后才进 ⑤ |
| `confirm` 不一致 | `value_error`, `loc=["body"]` | ⑥ 的错误落在模型层 |

`mode="before"` 的字段校验器拿到的可能是任何类型（`int`、`None`、`list`），必须先判类型再处理——这是最常见的崩溃点。

## 3. API 逐个拆解

### 3.1 `field_validator`

```python
@field_validator("email")
@classmethod
def normalize_email(cls, value: str) -> str:
    if "@" not in value:
        raise ValueError("邮箱必须包含 @")
    return value.lower()
```

| 要点 | 说明 |
| --- | --- |
| 必须 `@classmethod` | v2 要求；不写会告警/行为异常 |
| 可一次管多个字段 | `@field_validator("a", "b")` |
| 可多个校验器管同一字段 | 按声明顺序执行 |
| 返回值即最终值 | 不返回 = 返回 `None`，字段被改成 `None` |
| 抛 `ValueError` | 转成 422 `value_error` |
| 抛 `TypeError` | 也会被转成 422，但错误类型不同（不推荐依赖） |

### 3.2 `model_validator`

```python
@model_validator(mode="after")
def check_rules(self) -> "BookingCreate":
    if self.password != self.confirm:
        raise ValueError("两次输入的密码不一致")
    return self
```

| 要点 | 说明 |
| --- | --- |
| `mode="after"` 拿 `self` | 所有字段已通过，可随意读取 |
| 必须 `return self` | 返回 `None` 会让整个模型变成 `None`，随后报错 |
| `mode="before"` 拿 dict | 可整体重命名/补齐字段，风险高，慎用 |
| 错误 `loc` 是 `["body"]` | 想定位到字段，改写成字段校验器 + `ValidationInfo.data` |

### 3.3 用 `ValidationInfo` 读其他字段

```python
from pydantic import ValidationInfo, field_validator


@field_validator("end")
@classmethod
def check_end(cls, value: date, info: ValidationInfo) -> date:
    start = info.data.get("start")     # 只能拿到「已校验过」的字段
    if start is not None and value < start:
        raise ValueError("结束日期不能早于开始日期")
    return value
```

| 注意 | 说明 |
| --- | --- |
| `info.data` 只含**前面已校验**的字段 | 字段顺序决定能拿到谁 |
| 拿不到时是 `None` | 必须判空 |
| 错误 `loc` 指向 `end` | 前端可精确高亮 |

### 3.4 错误结构（实测）

```json
{"type": "value_error", "loc": ["body", "email"], "msg": "Value error, 邮箱必须包含 @", "input": "bademail"}
{"type": "value_error", "loc": ["body"], "msg": "Value error, 两次输入的密码不一致", "input": {...}}
```

| 事实 | 含义 |
| --- | --- |
| `msg` 带 `Value error, ` 前缀 | 前端展示时要剥掉，或自己映射 |
| `input` 是原值 | 可用于回显 |
| 模型校验器的 `loc` 只有两段 | 无法自动定位字段 |

## 4. 边界条件

### 4.1 多错误与短路

| 情况 | 行为 |
| --- | --- |
| 多个字段的 `Field` 约束都违反 | 一次返回多条（第 12 章实测） |
| 同一字段：约束违反 | 该字段的校验器不执行 |
| 字段校验器抛错 | 该字段后续校验器不执行 |
| 模型校验器抛错 | 该模型只报这一条 |

同一校验器里的多条 `if`：命中第一条即 `raise`，后面的看不到。要「一次报全」，需在校验器里收集错误后统一抛出（Pydantic 支持 `PydanticCustomError`/`ValueError` 单条，多错需拆成多个字段校验器，或抛 `AssertionError` 列表——**不确定**，本章未实测）。

### 4.2 继承与覆盖

| 场景 | 结果（实测） |
| --- | --- |
| 子类继承父类校验器 | ✅ 生效，`VipBookingCreate` 仍校验 `@` |
| 子类重定义同字段的 `Field` 约束 | 取子类，父类校验器仍在 |
| 子类定义同名校验器 | 覆盖父类（**未实测**，按 Python 语义推断） |
| 父类 `model_validator` | 子类继承，`self` 是子类实例 |

### 4.3 性能

| 事实 | 影响 |
| --- | --- |
| 校验器是 Python 函数 | 比 `Field` 约束慢（后者在 Rust 层） |
| 每个请求每个字段都会调用 | 高频接口避免在校验器里做重活 |
| 大列表逐元素校验 | 10k 元素 × 校验器 = 明显开销，考虑限流/批量 |

### 4.4 安全

| 风险 | 说明 |
| --- | --- |
| `assert` 校验 | `python -O` 会移除断言，校验静默失效 |
| 校验器里抛带敏感信息的 `ValueError` | 消息会原样返回客户端 |
| 校验器里做 DB 查询 | 阻塞事件循环、放大攻击面 |
| 用校验器做权限判断 | 校验器不知道「谁在调用」，必须放依赖层 |

### 4.5 `model_validator(mode="before")` 的坑

| 坑 | 说明 |
| --- | --- |
| 拿到的是 dict | 不是模型，字段名可能还是别名 |
| 返回错误结构 | 后续解析直接失败，错误难以理解 |
| 绕过字段约束 | 你在 before 里改了值，约束按改后值算 |

除非要做「整体结构迁移」，否则不要用 `mode="before"`。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 跨字段规则写 `Field` | 无法表达 | `model_validator` | 实测 |
| `model_validator` 不 `return self` | 模型变 `None` | 必须返回 | `[V1]` |
| 用 `assert` | `-O` 下失效 | `raise ValueError` | `[V3]` |
| 以为模型校验器能定位字段 | `loc=["body"]` | 字段校验器 + `info.data` | 实测 |
| 以为规则会进 `/docs` | schema 只有字段 | `Field(description=...)` 补充 | 实测 |
| `before` 里直接 `.strip()` | 值可能是 `int` | 先 `isinstance` | `[V1]` |
| 校验器里查库 | 阻塞、无依赖 | 服务层校验 | `[V4]` |
| 校验器里做权限判断 | 拿不到用户 | 依赖层（第 44 章） | `[V4]` |
| 一个校验器堆十条规则 | 只报第一条 | 拆分或收集错误 | `[V2]` |
| 字段校验器忘 `@classmethod` | 告警/异常 | 加上 | `[V1]` |
| 用 `TypeError` 表达业务错误 | 错误类型不可控 | `ValueError` | `[V1]` |
| `msg` 直接透给用户 | 带 `Value error, ` 前缀 | 前端剥离/映射 | 实测 |
| 把异常 message 写成内部细节 | 信息泄露 | 写用户可读的话 | `[V4]` |
| `info.data` 拿到 `None` 没判空 | `TypeError` | 判空 | `[V2]` |
| 依赖字段顺序却没保证 | `info.data` 缺键 | 把依赖字段声明在前 | `[V2]` |
| 用 `mode="before"` 做业务 | 绕过类型与约束 | 只在结构迁移用 | `[V1]` |
| 校验器返回 `None` 想「不改」 | 字段真的变 `None` | 返回原值 | `[V1]` |
| 校验器做重计算 | 每请求都跑 | 移到服务层缓存 | `[V5]` |
| 以为校验器能异步 | 不支持 `async def`（会当同步调用，返回协程） | 同步写，耗时逻辑外移 | `[V2]` |
| 只给成功用例写测试 | 规则回退无人发现 | 每条规则一个 422 用例 | 第 71 章 |
| 校验器里 `print` 调试后没删 | 日志污染、性能下降 | 用日志级别控制并清理 | `[V5]` |

## 6. 最佳实践与编码建议

### 6.1 模板：三类校验器各司其职

```python
from datetime import date
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator, model_validator


class BookingCreate(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    email: str = Field(min_length=5, max_length=64)
    password: str = Field(min_length=8)
    confirm: str
    start: date
    end: date

    @field_validator("email")
    @classmethod
    def normalize_email(cls, value: str) -> str:
        if "@" not in value:
            raise ValueError("邮箱格式不正确")
        return value.lower()

    @field_validator("end")
    @classmethod
    def check_end(cls, value: date, info: ValidationInfo) -> date:
        start = info.data.get("start")
        if start is not None and value < start:
            raise ValueError("结束日期不能早于开始日期")
        return value

    @model_validator(mode="after")
    def check_password(self) -> "BookingCreate":
        if self.password != self.confirm:
            raise ValueError("两次输入的密码不一致")
        return self
```

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 能用 `Field` 就不用校验器 | 快、进文档、错误结构标准 |
| 校验器只写「逻辑」，不写「取数」 | 保持纯函数 |
| 错误消息面向用户 | 「密码至少 8 位」而不是「len<8」 |
| 能定位字段就定位 | 用 `info.data` 而不是模型校验器 |
| `model_validator` 只做跨字段 | 单字段的别放这里 |
| 校验器统一放模型内 | 与字段声明在一起 |
| 测试覆盖每条规则 | 一条规则一个 422 断言 |

### 6.3 选型速查

| 需求 | 写法 |
| --- | --- |
| 长度/范围/正则 | `Field` |
| 转小写/去空格 | `field_validator(mode="before")` |
| 密码强度 | `field_validator` |
| 两次密码一致 | `model_validator(mode="after")` |
| 结束≥开始且要定位到 end | `field_validator` + `info.data` |
| 查库判重 | 服务层 + `HTTPException(409)` |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[V1]` | 官方文档 | https://docs.pydantic.dev/latest/concepts/validators/ | `field_validator`/`model_validator` 全部用法 |
| `[V2]` | 官方文档 | https://docs.pydantic.dev/latest/api/functional_validators/ | `ValidationInfo`、`mode` 参数 |
| `[V3]` | 官方文档 | https://docs.python.org/3/using/cmdline.html#cmdoption-O | `-O` 移除 assert |
| `[V4]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/handling-errors/ | 校验失败与业务错误的分工 |
| `[V5]` | 工程实践 | https://fastapi.tiangolo.com/zh/async/ | 阻塞事件循环的代价 |

> **核对状态**：`[V1]`–`[V5]` 为官方文档链接，**本次未逐页直连复核**；执行顺序、`loc`、`msg` 前缀、继承行为均为本机实测，`examples/verify.py` 复现 10/10 通过。4.1 的「一次报多条」与 4.2 的「子类同名覆盖」**未验证**，已标注。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 四类校验器的执行顺序
- [ ] `before` 与 after 的差别与风险
- [ ] 两类校验器的 `loc` 差异
- [ ] 为什么 `Field` 约束先于校验器
- [ ] 校验器为什么不能查库
- [ ] `Value error, ` 前缀的来源

**能写出（代码层）**：

- [ ] 值变形校验器
- [ ] 跨字段模型校验器
- [ ] `info.data` 版日期校验
- [ ] 继承并覆盖约束的子模型

**能判断（避坑层）**：

- [ ] 看到 `assert` 校验 → 指出 `-O` 风险
- [ ] 看到模型校验器定位字段 → 指出做不到
- [ ] 看到校验器里查库 → 指出阻塞
- [ ] 看到 `mode="before"` 滥用 → 指出绕过约束
- [ ] 看到只报一条错 → 指出拆分策略

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 10/10
- [ ] 手工触发 `loc=["body"]` 的模型级错误
- [ ] `/docs` 里确认规则不可见

## 9. 下一章衔接

第 21 章 `响应模型`：本章的 `exclude={"password", "confirm"}` 只是临时手段。下一章用 `response_model` 与返回注解，把「对外字段」定义成一个模型，从机制上杜绝泄露，并讲清 `response_model_exclude_unset` 等参数。

M02（13–20）到此收尾：你现在能定义请求模型、约束、嵌套、局部更新、复用与校验器；接下来进入 M03「响应」，开始控制数据怎么出去。

本章留下的伏笔：

1. 密码字段的彻底隔离在第 21 章（对应本系列第 308 行「M03 响应」）。
2. 错误消息的对外映射在第 33 章（统一错误结构）。
3. 依赖注入里做跨字段校验在第 38 章。
4. 性能与异步在第 45 章附近。
