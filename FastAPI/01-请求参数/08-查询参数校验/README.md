# 08 查询参数校验

## 一句话结论

`Query()` 与第 06 章的 `Path()` 是同一套校验机制，唯一的结构差异是：**`Query()` 能（也必须）通过默认值表达可选性**。`Annotated[str, Query(min_length=3)]` 不带默认值 = 必填；`= ""` 或 `= None` = 可选。

学完这一章，你能：给分页/搜索/排序参数加正确约束、识破 `alias` 写错却静默用默认值的坑、说清 `include_in_schema=False` 对 OpenAPI 的影响。

## 最小可运行案例

```python
from typing import Annotated

from fastapi import FastAPI, Query

app = FastAPI()


@app.get("/articles")
def list_articles(
    # 必填 + 校验：不写默认值就是必填
    q: Annotated[str, Query(min_length=1, max_length=50, description="搜索词，必填")],
    # 可选 + 校验：靠默认值表达可选
    limit: Annotated[int, Query(ge=1, le=100, description="每页条数")] = 20,
) -> dict[str, object]:
    return {"q": q, "limit": limit}
```

完整版本（alias、deprecated、隐藏参数）见 `examples/main.py`。

## 怎么跑

```powershell
cd "01-请求参数\08-查询参数校验\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 必填缺失 missing -> 422 missing loc=['query', 'q']
[PASS] min_length 拒空串 -> 空串 -> string_too_short
[PASS] 可选 + 范围约束 -> {'low': 'greater_than_equal', 'high': 'less_than_equal'}
[PASS] 别名生效 -> page-size=30 → 30
[PASS] 别名写错静默失败 -> page_size=30 → 200 但得到默认值 10（不报错）
[PASS] deprecated 进文档 -> name=page-size, old-flag deprecated=True
[PASS] 隐藏参数 -> 文档参数=['value']（_internal 已隐藏）
[PASS] 数组逐项校验 -> 数组超限 loc=['query','tag']；元素错误 loc=['query','ids',0]
[PASS] 可选 + 约束 -> 不传 → None；ab → 422；abc → 200
[PASS] 约束进 schema -> q: minLength+pattern+required；limit: minimum/maximum

结果：10/10 通过
```

## 核心 API 速查

| 参数 | 作用 | 与 `Path()` 的差异 |
| --- | --- | --- |
| `default` | 默认值，**决定可选性** | `Path()` 不支持 |
| `alias` | 查询串里的键名 | 相同 |
| `ge` / `gt` / `le` / `lt` | 数值范围 | 相同 |
| `min_length` / `max_length` | 字符串长度 | 相同 |
| `pattern` | 正则 | 相同 |
| `description` / `title` | 文档 | 相同 |
| `deprecated` | 标记废弃 | 相同 |
| `include_in_schema` | 是否进文档 | 相同 |
| `examples` | 文档示例 | 相同 |

| 声明 | 可选性 | 缺失时 |
| --- | --- | --- |
| `Annotated[str, Query(min_length=3)]` | **必填** | 422 `missing` |
| `Annotated[str, Query(min_length=3)] = "abc"` | 可选 | `"abc"` |
| `Annotated[str \| None, Query(min_length=3)] = None` | 可选 | `None`（不校验） |
| `Annotated[list[int], Query()] = []` | 可选 | `[]` |

> 注意：`Annotated[str | None, Query(min_length=3)] = None` 时，不传会跳过 `min_length`——因为 `None` 不参与校验。这是「可选 + 有约束」的正确组合方式。

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `Query(alias="page-size")` 但前端传 `page_size` | **不报错**，静默用默认值 | 前后端统一，或写契约测试 |
| 以为 `alias` 是双向的 | 只影响解析，不影响响应 | 响应用 `serialization_alias` |
| `Query()` 不写默认值却想可选 | 必填，422 `missing` | 补 `= None` |
| 给 `int` 参数写 `= None` | 类型不符 | `int \| None = None` |
| 所有参数都设 `include_in_schema=False` | OpenAPI 里整个 `parameters` 键**消失** | 只隐藏内部参数 |
| 用 `Query()` 又手工二次校验 | 错误格式不统一 | 全交给 `Query` |
| 分页 `limit` 不设上限 | 被 `?limit=999999` 拖垮 | `le=100` |
| `pattern` 想匹配「包含」 | 整串匹配 | 加 `.*` |
| `list[str]` 上写 `Query(min_length=1)` 想限制每个元素长度 | 实测限制的是**数组长度**，默认值 `[]` 直接 422 | 元素级约束写 `list[Annotated[str, Field(min_length=1)]]` |
| 数组元素报错时 `loc` 只看到两段 | 那是数组长度错误，不是元素错误 | 元素错误是 `["query","ids",0]` 三段 |

## 毕业自查

- [ ] 能说出 `Query()` 与 `Path()` 的唯一结构差异
- [ ] 能说出「不写默认值 = 必填」的完整规则
- [ ] 能解释 `alias` 写错为什么静默失败
- [ ] 能说出 `include_in_schema=False` 对 `parameters` 的影响
- [ ] 能写出「可选 + 有校验」的正确组合
- [ ] 能读懂数组参数报错的 `loc` 结构
- [ ] 动手题一：把 `limit` 上限从 100 改成 10，验证 `11` 报 422
- [ ] 动手题二：故意用错别名传参，确认服务端不报错但值不对

> 想看 `Query` 全表、alias 静默失败实测、9 类边界、30 条坑，继续读 [`base.md`](./base.md)。
