# 30 jsonable_encoder · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「它到底按什么规则转、为什么 Decimal 有两种结果、`include/exclude` 的边界、什么时候别用它」拆开。学完这章，你要能判断「这段数据能不能直接进 JSON」，以及金额为什么不许走裸 dict。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1（本机实测） |
| 前置 | 第 21 章（响应模型）、第 22–26 章（响应控制） |
| 覆盖范围 | `jsonable_encoder` 类型映射、递归、`include/exclude/by_alias`、`custom_encoder`、与 `model_dump` 对比 |
| 明确不覆盖 | Pydantic 自定义 `serializer` 深入、ORM 懒加载与 N+1（M09） |
| 学完验收 | 能跑通 `verify.py` 12/12、能预测任意常见类型的输出、能说出金额保精度的写法 |

## 0. 怎么用这份文件

**依据约定**：`` `[En]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 为什么要「可 JSON 化」
2 机制（第 2 节）    → 递归规则与两条路径
3 API（第 3 节）     → include/exclude/custom_encoder
4 边界（第 4 节）    → Decimal 精度、datetime 格式、bytes、性能
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 何时用/何时不用
```

## 1. 概念：JSON 只有 6 种原生类型

`dict` / `list` / `str` / `int` / `float` / `bool` / `null`（严格说是 6 种 + null）。

其余都得转：`datetime`、`Decimal`、`UUID`、`Enum`、`Path`、`set`、`bytes`、ORM 对象、自定义类。

`jsonable_encoder` 的职责就是**递归**完成这件事，让 `json.dumps` 不报错。

## 2. 机制：两种输入走两条路（实测）

```text
输入是 Pydantic 模型
  → model_dump(mode="json") / .dict() 风格
  → Decimal → str（保精度）、datetime → ISO（带 Z）

输入是 dict / list / 普通对象
  → 逐键递归 + ENCODERS_BY_TYPE 查表
  → Decimal → float（丢精度！）、datetime → isoformat（+00:00）
  → 普通对象 → vars(obj)
```

| 输入 | `Decimal("399.90")` | `datetime(...tz=utc)` |
| --- | --- | --- |
| 裸 dict | `399.9`（float）| `"2026-11-17T12:00:00+00:00"` |
| Pydantic 模型 | `"399.90"`（str）| `"2026-11-17T12:00:00Z"` |

这是本章最重要的一条：**同一个类型，容器不同，结果不同**。

## 3. API 逐个拆解

### 3.1 类型映射表（实测）

| Python 类型 | 输出 | 备注 |
| --- | --- | --- |
| `datetime` | str | 时区表示随路径不同 |
| `date` / `time` | str | ISO |
| `Decimal` | float 或 str | 取决于是否模型 |
| `UUID` | str | 标准 36 位 |
| `Enum` | `.value` | `str` 枚举就是字符串 |
| `Path` | str | 平台分隔符 |
| `set` / `frozenset` | list | 顺序不保证 |
| `bytes` | str | utf-8 解码，失败抛错 |
| `BaseModel` | dict | 递归 |
| 普通对象 | dict | `__dict__` |
| `__slots__` 对象 | 抛 `ValueError` | 不可迭代 |
| 空普通类 | `{}` | 实测 |

### 3.2 裁剪参数

| 参数 | 作用 | 注意 |
| --- | --- | --- |
| `include` | 白名单 | 与 `exclude` 同用易混乱 |
| `exclude` | 黑名单 | 只是输出时去掉 |
| `by_alias` | 用别名 | 与模型配置有关 |
| `exclude_unset` | 只输出已设置字段 | 模型才有意义 |
| `exclude_defaults` | 跳过默认值字段 | 模型 |
| `exclude_none` | 跳过 None | 客户端分不清 null 与缺失 |

### 3.3 `custom_encoder`

```python
jsonable_encoder(payload, custom_encoder={datetime: lambda v: int(v.timestamp())})
```

| 要点 | 说明 |
| --- | --- |
| 按**精确类型**匹配 | 子类不命中 |
| 只影响指定类型 | 其余走默认 |
| 可覆盖任何已支持类型 | 谨慎，可能破坏契约 |

### 3.4 与 `model_dump(mode="json")` 对比

| 维度 | `jsonable_encoder` | `model_dump(mode="json")` |
| --- | --- | --- |
| 输入 | 任意对象/混合结构 | 仅 Pydantic 模型 |
| Decimal | 裸 dict 时 float | str |
| 可配置 | `custom_encoder` | `serializers` / `field_serializer` |
| 推荐场景 | 混合结构先转 | 有模型时 |

实测：同一个 `Order` 模型走两条路结果完全相同（`same: true`）。

## 4. 边界条件

### 4.1 金额精度（最危险）

```python
jsonable_encoder({"amount": Decimal("399.90")})   # {'amount': 399.9}
jsonable_encoder(Order(amount=Decimal("399.90"))) # {'amount': '399.90'}
```

`399.90` 变成 `399.9` 只是显示差异，但 `Decimal("1.10")` → `1.1`、更大的数会丢有效位。金额、税率、积分一律用模型或显式 `str(amount)`。

### 4.2 时间格式

| 来源 | 输出 |
| --- | --- |
| 裸 dict | `2026-11-17T12:00:00+00:00` |
| 模型 | `2026-11-17T12:00:00Z` |

前端解析通常都能处理，但**断言里写死一种就会挂**。跨系统契约要显式规定格式（如统一 UTC + `Z`）。

### 4.3 `bytes`

| 情况 | 结果 |
| --- | --- |
| 合法 utf-8 | 解码后的 str |
| 非法字节 | `UnicodeDecodeError` |

二进制内容应 base64 或走文件下载（第 25 章），别指望 encoder 兜底。

### 4.4 `set` 顺序

输出 list，但顺序不保证。断言/签名要排序后再比较。

### 4.5 性能

| 场景 | 成本 |
| --- | --- |
| 大列表 10k 条 | 递归复制，内存 ≈ 2 倍 |
| 深层嵌套 | 递归深度受限（极端情况 `RecursionError`）|
| 循环引用 | 直接报错/爆栈 |

大导出用流式（第 25 章），别整包 encoder。

### 4.6 何时不该用

| 场景 | 更合适 |
| --- | --- |
| 有响应模型 | 交给 FastAPI |
| 需要保精度 | 模型 + `model_dump(mode="json")` |
| 需要严格契约 | 响应模型 + JSON Schema |
| 只需要写日志 | `repr` / 结构化日志（第 50 章）|

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 金额放裸 dict | Decimal → float 丢精度 | 用模型 | 实测 |
| 断言 datetime 固定为 `Z` | 裸 dict 是 `+00:00` | 只断言前缀或规范化 | 实测 |
| 靠 encoder 遮密码 | 换端点就漏 | 出参模型 | 第 21 章 |
| 有模型还手动 encoder | 重复转换 | 交给框架 | 实测 |
| `include` 与 `exclude` 混用 | 空对象 | 只用一种 | `[E1]` |
| 对 `set` 断言顺序 | 偶发失败 | 排序 | 实测 |
| `bytes` 含二进制 | UnicodeDecodeError | base64 | 实测 |
| 缓存存原始对象 | 序列化失败 | 存 encoder 结果 | `[E3]` |
| 大列表整包 encoder | 内存翻倍 | 分页/流式 | `[E3]` |
| `custom_encoder` 期望命中子类 | 不生效 | 精确类型或自定义类 | 实测 |
| 循环引用结构 | 递归爆栈 | 断开引用 | `[E2]` |
| 用 `exclude_none` 当「无值」 | 客户端分不清 | 明确契约 | 第 23 章 |
| 认为 `jsonable_encoder` 会调用方法 | 只读属性 | 先计算 | 实测 |
| `__slots__` 对象直接转 | ValueError | 手动构 dict | 实测 |
| 用 encoder 处理 ORM 懒属性 | 触发额外查询 | 只选需要的列 | M09 |
| 以为输出就是最终响应 | 中间件/响应模型还会改 | 明确层级 | 第 21 章 |
| `exclude` 里写错字段名 | 静默无效 | 用 `include` 或测试 | 实测 |
| 只测 dict 输入 | 模型路径差异没覆盖 | 两种都测 | 第 71 章 |
| 用 encoder 结果回写数据库 | 金额已变 float，精度丢了 | 存原始 `Decimal` | `[E3]` |

## 6. 最佳实践与编码建议

### 6.1 推荐写法

```python
from datetime import datetime, timezone
from decimal import Decimal

from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel


class PaymentOut(BaseModel):
    id: int
    amount: Decimal
    paid_at: datetime


async def cache_payment(payment: PaymentOut) -> dict:
    # 【为什么】走模型 → Decimal 输出字符串，金额保精度
    payload = payment.model_dump(mode="json")
    await cache.set(f"payment:{payment.id}", payload, ttl=300)
    return payload


def log_mixed_event(event: dict) -> dict:
    # 【为什么】混合结构没有模型，才用 encoder；金额字段先 str 化
    safe = {**event, "amount": str(event["amount"])}
    return jsonable_encoder(safe, exclude={"password"})
```

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 金额用模型 | 或用 `str()` 显式 |
| 时间统一 UTC | 契约写清格式 |
| 有模型用 `model_dump(mode="json")` | 少一层 |
| 混合结构才用 encoder | 并显式处理 Decimal |
| 二进制走 base64/下载 | 不靠解码 |
| 大结构分页/流式 | 控制内存 |
| 不用它做安全边界 | 出参模型才是 |

### 6.3 选型速查

| 需求 | 做法 |
| --- | --- |
| 返回模型 | 交给 FastAPI |
| 写缓存 | `model_dump(mode="json")` |
| 写日志 | `jsonable_encoder` + 脱敏 |
| 混合 dict + 特殊类型 | `jsonable_encoder` |
| 自定义时间格式 | `custom_encoder` 或序列化器 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[E1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/encoder/ | `jsonable_encoder` 用法 |
| `[E2]` | 源码 | https://github.com/fastapi/fastapi/blob/master/fastapi/encoders.py | `ENCODERS_BY_TYPE` 与递归规则 |
| `[E3]` | 官方文档 | https://docs.pydantic.dev/latest/concepts/serialization/ | `model_dump` 与序列化模式 |

> **核对状态**：`[E1]`–`[E3]` 为官方/源码链接，**本次未逐页直连复核**；类型映射、Decimal 两条路径、datetime 两种格式、`bytes` 解码、`__slots__` 行为、与 `model_dump` 一致性均为本机实测，`examples/verify.py` 复现 12/12 通过。大结构性能与循环引用**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] JSON 原生类型只有哪几种
- [ ] 模型与裸 dict 的两条转换路径
- [ ] Decimal 两种结果的成因
- [ ] datetime 两种格式的成因
- [ ] 为什么 encoder 不能当安全边界

**能写出（代码层）**：

- [ ] 基础类型转换
- [ ] `exclude`/`include`/`by_alias`
- [ ] `custom_encoder`
- [ ] `model_dump(mode="json")` 写缓存
- [ ] 显式 `str(Decimal)` 保精度

**能判断（避坑层）**：

- [ ] 看到金额在裸 dict → 指出精度
- [ ] 看到断言 `Z` 格式 → 指出来源不同
- [ ] 看到 `bytes` 直接转 → 指出可能抛错
- [ ] 看到 encoder 遮密码 → 指出出参模型
- [ ] 看到大列表整包转 → 指出内存

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 12/12
- [ ] 手工对比 `jsonable_encoder` 与 `model_dump`
- [ ] `/docs` 里看到 `Status` 枚举选项

## 9. 下一章衔接

M04 到此结束（27–30）。下一模块 M05 `错误处理`（31–34）：`HTTPException` 的细节、自定义异常类、异常处理器、统一错误响应结构，把本章「编码」与第 23 章「联合响应」的伏笔收口。

本章留下的伏笔：

1. 错误响应体的结构统一在 第 31–34 章。
2. 日志中的结构化编码在 第 50 章。
3. ORM 序列化在 M09。
4. 响应模型与 encoder 的层级关系在 第 21 章已讲。