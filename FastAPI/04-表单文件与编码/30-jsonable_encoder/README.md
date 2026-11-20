# 30 jsonable_encoder

## 一句话结论

`jsonable_encoder` 把任意 Python 对象递归转成「只含 JSON 原生类型」的结构。FastAPI 返回前本来就会调它，你只在需要**先转再存**（写缓存、写日志、拼进另一个结构）时手动调。**关键实测差异**：裸 `dict` 里的 `Decimal("399.90")` 会变成 `float` 399.9（丢精度），而 Pydantic 模型里的 `Decimal` 输出字符串 `"399.90"`（保精度）。金额千万别走裸 dict。

学完这一章，你能：判断哪些类型会被怎么转、用 `include`/`exclude` 裁剪、写 `custom_encoder`、在 `jsonable_encoder` 与 `model_dump(mode="json")` 之间做对选择。

## 最小可运行案例

```python
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel


class Status(str, Enum):
    ACTIVE = "active"
    DISABLED = "disabled"


class Order(BaseModel):
    id: int
    amount: Decimal
    created_at: datetime
    status: Status


now = datetime(2026, 11, 17, 12, 0, 0, tzinfo=timezone.utc)
order = Order(id=1, amount=Decimal("399.90"), created_at=now, status=Status.ACTIVE)

print(jsonable_encoder(order))     # Decimal → "399.90"（保精度）
print(jsonable_encoder({"amount": Decimal("399.90")}))   # Decimal → 399.9（float！）
print(jsonable_encoder({"dt": now}))                     # "2026-11-17T12:00:00+00:00"
print(jsonable_encoder(order, exclude={"amount"}))       # 裁剪字段
```

完整版本（`custom_encoder`、`SimpleNamespace`、路径枚举、与 `model_dump` 对比）见 `examples/main.py`。

## 怎么跑

```powershell
cd "04-表单文件与编码\30-jsonable_encoder\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 基础类型转换 -> 裸 dict 的 Decimal → float 399.9；其余为 str/list
[PASS] 结果均为 JSON 原生 -> types=['float', 'list', 'str']
[PASS] 模型转 dict -> Decimal='99.50'，status='disabled'
[PASS] 普通对象转 dict -> SimpleNamespace → dict，Decimal 变 float
[PASS] exclude/include -> exclude 去掉 password；include 只剩 id/username
[PASS] custom_encoder -> datetime → int 时间戳，Decimal 仍走默认 float
[PASS] 与 model_dump 对比 -> 两条路结果相同（Decimal 均为字符串）
[PASS] 路径枚举 -> active → ACTIVE；非法值 422
[PASS] 递归转换 -> 嵌套 dict/list 内也被转换
[PASS] bytes 解码 -> 非法字节抛 UnicodeDecodeError
[PASS] __slots__ 对象 -> ValueError: [TypeError("'Slotted' object is not iterable"), Ty
[PASS] 空普通类 -> Plain() → {}

结果：12/12 通过
```

## 核心 API 速查

| 类型 | 转换结果（实测） |
| --- | --- |
| `datetime` | `"2026-11-17T12:00:00+00:00"`（裸 dict）/ `"...Z"`（Pydantic 模型）|
| `date` | `"2026-11-17"` |
| `Decimal`（裸 dict/普通对象）| **`float`**（399.9，精度丢失）|
| `Decimal`（Pydantic 模型）| `str`（`"399.90"`，保精度）|
| `set` | `list`（顺序不保证）|
| `UUID` | `str` |
| `Enum` | 它的 `value` |
| `Path` | `str` |
| `bytes` | 按 utf-8 解码为 `str`（非法字节抛 `UnicodeDecodeError`）|
| 普通对象 | `__dict__` → dict（空对象 → `{}`）|
| `__slots__` 对象 | `ValueError`（无法迭代）|

| 参数 | 作用 |
| --- | --- |
| `include={"a"}` | 只保留 |
| `exclude={"a"}` | 去掉 |
| `by_alias=True` | 用别名输出 |
| `exclude_unset=True` | 只输出设置过的字段（模型）|
| `custom_encoder={datetime: f}` | 覆盖某类型 |
| `sqlalchemy_safe` | 兼容旧版 ORM（本章未用）|

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 金额放裸 dict 过 encoder | `Decimal("399.90")` → `399.9` 丢精度 | 用 Pydantic 模型 |
| 以为 `Decimal` 一定输出字符串 | 裸 dict 是 float | 按容器判断 |
| 想靠 encoder 防泄露 | 只是临时遮字段 | 用出参模型（第 21 章）|
| 有响应模型还手动 encoder | 多一次转换、语义重复 | 交给 FastAPI |
| `exclude` 漏字段 | 密码泄露 | 出参模型根本不放 |
| 依赖 `datetime` 输出格式 | `+00:00` 还是 `Z` 取决于来源 | 前端统一解析 |
| `set` 输出顺序做断言 | 顺序不保证 | 排序后比较 |
| `bytes` 非法字节 | `UnicodeDecodeError` | 先 base64 或显式解码 |
| 用 encoder 处理超大结构 | 全量复制，内存翻倍 | 分页/流式 |
| 自定义编码器命中子类 | 只匹配精确类型 | 显式判断 |
| 以为 `jsonable_encoder` 会调方法 | 只读属性 | 先算好再放对象 |
| 缓存里存原始对象 | 序列化失败 | 存 encoder 结果 |

## 毕业自查

- [ ] 能说出 `jsonable_encoder` 的输出范围（只有 JSON 原生类型）
- [ ] 能说出「裸 dict 的 Decimal」与「模型的 Decimal」差异
- [ ] 能写出 `exclude`/`include`/`by_alias`
- [ ] 能写 `custom_encoder` 把 datetime 转时间戳
- [ ] 能说出 `model_dump(mode="json")` 与该选哪个
- [ ] 能解释 `bytes` 为什么可能抛错
- [ ] 动手题一：把 `Decimal("1.10")` 分别过裸 dict 和模型，对比输出
- [ ] 动手题二：给 `/encode/basic` 加 `UUID` 与 `Enum` 的自定义编码

> 想看实现原理（`ENCODERS_BY_TYPE`、递归顺序）、精度与性能、18 条坑，继续读 [`base.md`](./base.md)。