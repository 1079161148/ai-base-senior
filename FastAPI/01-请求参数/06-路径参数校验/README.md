# 06 路径参数校验

## 一句话结论

`Path()` 给路径参数加**约束**（数值范围、字符串长度、正则）和**文档元信息**（描述、废弃标记）。约束会写进 OpenAPI，前端能提前看到；校验失败统一返回 422，`detail[].type` 告诉你违反了哪一条。

学完这一章，你能：给任意路径参数加正确约束、读懂 422 的 `type` 与 `ctx`、说清 `ge` 与 `gt` 在 OpenAPI 里的区别。

## 最小可运行案例

```python
from typing import Annotated

from fastapi import FastAPI, Path

app = FastAPI()


@app.get("/items/{item_id}")
def get_item(
    item_id: Annotated[int, Path(gt=0, le=100, description="商品 ID，1–100")],
) -> dict[str, int]:
    # 【作用】gt=0 → 必须 > 0；le=100 → 必须 ≤ 100
    # 【注意】1 和 100 都能过，0 和 101 返回 422
    return {"item_id": item_id}
```

完整版本（字符串约束、废弃标记、两种写法对比）见 `examples/main.py`。

## 怎么跑

```powershell
cd "01-请求参数\06-路径参数校验\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 数值范围边界 -> 1/100 通过，0/101 拒绝
[PASS] 越界错误类型 -> 0→greater_than 101→less_than_equal
[PASS] 浮点开闭区间 -> 0 通过 / 10000 拒绝（less_than）
[PASS] 字符串长度 -> ab→string_too_short abcdefghi→string_too_long
[PASS] 正则整串匹配 -> string_pattern_mismatch pattern=^[a-z]+$
[PASS] 多约束只报一条 -> 违反 2 条只返回 1 条
[PASS] 两种写法等效 -> 同约束下 422 类型完全一致
[PASS] OpenAPI 约束表示 -> exclusiveMinimum/minimum/exclusiveMaximum/minLength/pattern 全部就位
[PASS] 文档元信息 -> title=编码 deprecated=True
[PASS] alias 用法 -> URL 用 real_id，函数用 internal_id，OpenAPI name=real_id

结果：10/10 通过
```

## 核心 API 速查

| 参数 | 类型 | 作用 | OpenAPI 键 | 失败 `type` |
| --- | --- | --- | --- | --- |
| `gt` | 数值 | 大于（不含） | `exclusiveMinimum` | `greater_than` |
| `ge` | 数值 | 大于等于 | `minimum` | `greater_than_equal` |
| `lt` | 数值 | 小于（不含） | `exclusiveMaximum` | `less_than` |
| `le` | 数值 | 小于等于 | `maximum` | `less_than_equal` |
| `min_length` | 字符串 | 最小长度 | `minLength` | `string_too_short` |
| `max_length` | 字符串 | 最大长度 | `maxLength` | `string_too_long` |
| `pattern` | 字符串 | 正则（**匹配整串**） | `pattern` | `string_pattern_mismatch` |
| `title` | 字符串 | 文档标题 | `title` | — |
| `description` | 字符串 | 文档描述 | `description` | — |
| `deprecated` | bool | 标记废弃 | `deprecated` | — |
| `alias` | 字符串 | 路径里的变量名 | `name` | — |

两种写法（行为完全一致，实测 422 类型码相同）：

```python
# 写法 1：Annotated（推荐）
def f(v: Annotated[int, Path(ge=1, le=10)]) -> ...: ...

# 写法 2：默认值（旧风格，仍广泛存在）
def f(v: int = Path(ge=1, le=10)) -> ...: ...
```

> 路径参数不能用 `Path()` 的 `default`——路径参数永远必填。要写就写 `...`（Ellipsis），表示「无默认值」。

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `Path(default=1)` | 默认值不生效（路径参数必填） | 用 `...` 或省略 |
| 以为多约束同时失败会返回多条 | 实测**只返回 1 条**（第一条失败的） | 前端按第一条处理即可 |
| `pattern="[a-z]+"` 想匹配「包含」 | 实际是**整串匹配**，`abc123` 会失败 | 写 `^.*[a-z]+.*$` 或加 `^...$` |
| `gt=0` 却以为 `0` 能过 | 实测 422 `greater_than` | 要含 0 用 `ge=0` |
| 只写 `Path()` 不写 `...` | 参数变成可选 → 与路径模板冲突 | 路径参数不需要默认值位置参数 |
| 用 `Path` 校验后又手工 `if v < 0: raise` | 重复校验、错误格式不统一 | 全交给 `Path` |
| 约束写太紧导致前端传不了 | 线上 422 激增 | 约束按业务真实边界 |
| 忘记 `description` | 文档看不出范围 | 补上，前端可自助 |

## 毕业自查

- [ ] 能说出 `gt` / `ge` 在 OpenAPI 里对应哪个键
- [ ] 能说出 `pattern` 是整串匹配还是包含匹配
- [ ] 能说出多约束同时失败返回几条
- [ ] 能写出 `Annotated` 与默认值两种写法
- [ ] 能读懂 422 里的 `ctx` 字段（`{"gt": 0}`）
- [ ] 能说出 `deprecated=True` 在文档里的效果
- [ ] 动手题一：给 `/items/{item_id}` 加 `ge=1, le=9999`，把 0 和 10000 的 422 打出来
- [ ] 动手题二：把 `pattern` 改成允许「字母+数字」，验证 `abc123` 通过

> 想看约束全表、422 类型码字典、两种写法差异、30 条坑，继续读 [`base.md`](./base.md)。
