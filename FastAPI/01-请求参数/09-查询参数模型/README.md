# 09 查询参数模型

## 一句话结论

用一个 Pydantic 模型装下所有查询参数，再标 `Annotated[Model, Query()]`，FastAPI 会把模型的**每个字段展开成一个独立的查询参数**。适合参数超过 6–8 个的列表接口；但**不支持嵌套模型**，也不该放复杂校验。

学完这一章，你能：把 8 个散落的参数收敛成一个模型、说清 `Query()` 为什么必须写、识别「模型当请求体」的错误用法。

## 最小可运行案例

```python
from typing import Annotated

from fastapi import FastAPI, Query
from pydantic import BaseModel, Field

app = FastAPI()


class ArticleFilter(BaseModel):
    q: str | None = None
    tag: list[str] = []
    limit: int = Field(default=20, ge=1, le=100)
    offset: int = Field(default=0, ge=0)


@app.get("/articles")
def list_articles(
    # 【关键】必须写 Query()，否则 FastAPI 会把它当成请求体
    filters: Annotated[ArticleFilter, Query()],
) -> dict[str, object]:
    return filters.model_dump()
```

请求 `GET /articles?q=python&tag=a&tag=b&limit=5` 会得到 `{"q":"python","tag":["a","b"],"limit":5,"offset":0}`。

完整版本（别名、校验失败结构）见 `examples/main.py`。

## 怎么跑

```powershell
cd "01-请求参数\09-查询参数模型\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 不传时全用默认值 -> q=None tag=[] limit=20 offset=0
[PASS] 展开成独立查询参数 -> q/tag/limit/offset 均可单独覆盖
[PASS] 字段级校验生效 -> limit=0 -> greater_than_equal loc=['query','limit']
[PASS] 数组字段用重复键 -> ['a', 'b']
[PASS] 字段 alias 生效 -> local-name=Z
[PASS] 用错字段名静默失败 -> 得到默认值
[PASS] 嵌套模型不可用 -> 422 model_attributes_type
[PASS] OpenAPI 展开为四个参数 -> 无 $ref
[PASS] 不写 Query() 变成请求体 -> OpenAPI 有 requestBody；GET → 422 missing loc=['body']

结果：9/9 通过
```

## 核心 API 速查

| 写法 | 效果 |
| --- | --- |
| `Annotated[Model, Query()]` | 模型字段展开成查询参数 ✅ |
| `filters: Model`（不加 `Query()`） | 被当成**请求体** ❌ |
| `Annotated[Model, Query()]` + 字段默认值 | 默认值生效 |
| `Field(alias="page-size")` | 字段名映射到查询键 |
| `list[str]` 字段 | 重复键接收 |
| 嵌套模型字段 | **不支持**，报 422 |

| 模型字段声明 | 查询参数行为 |
| --- | --- |
| `q: str \| None = None` | 可选，缺省 `None` |
| `limit: int = 20` | 可选，缺省 `20` |
| `limit: int`（无默认） | **必填** |
| `tag: list[str] = []` | 可选，缺省 `[]` |
| `limit: int = Field(default=20, ge=1, le=100)` | 可选 + 范围校验 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `filters: Model` 不加 `Query()` | 被当成请求体，GET 请求 422 或参数全空 | `Annotated[Model, Query()]` |
| 模型里嵌另一个模型 | 实测 422 `model_attributes_type`，OpenAPI 里是 `$ref` 但无法展开 | 扁平化字段 |
| 模型里放 `dict` / `Union[复杂类型]` | 无法从查询串表达 | 用 `str` + 自解析 |
| 字段名带下划线给前端 | 前端写 kebab-case 静默失效 | `Field(alias="page-size")` |
| 模型字段无默认值却想可选 | 必填，缺失 422 | 给默认值 |
| 用模型装 body 字段 | 位置错 | 第 13 章 |
| 模型字段过多（>20） | 文档臃肿 | 拆分接口 |
| 在模型里写 `@field_validator` 做跨字段校验 | 可用但错误 `loc` 指向不直观 | 简单规则用 `Field` |

## 毕业自查

- [ ] 能说出 `Annotated[Model, Query()]` 与直接声明 8 个参数的区别
- [ ] 能说出不写 `Query()` 会发生什么
- [ ] 能说出为什么嵌套模型不行
- [ ] 能写出带 `Field` 约束的查询参数模型
- [ ] 能读懂 422 里 `loc: ["query","limit"]` 的含义
- [ ] 能判断什么规模该用模型、什么规模不该
- [ ] 动手题一：把 `limit` 上限改成 10，验证 11 报 422
- [ ] 动手题二：加一个嵌套模型字段，观察 422 与 OpenAPI 的变化

> 想看待展开规则、9 类边界、26 条坑，继续读 [`base.md`](./base.md)。
