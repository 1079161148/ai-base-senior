# 42 实战：分页依赖（PageParams + Page[T]）

## 一句话结论

一套 `PageParams`（`page`/`size` + `offset` 属性）配一个泛型 `Page[T]`（`items/total/page/size/pages`），所有列表接口共用。实测：`?page=2&size=5` 返回 6–10、`total=23`、`pages=5`；越界页返回 200 + 空 `items`（`total` 不变）；空结果集 `pages=0`；OpenAPI 生成 `Page_ItemOut_` / `Page_UserOut_` 两个具体 schema。

学完这一章，你能：给任意列表接口加统一分页、让前端只写一套解析、避开「越界 404」「只查当前页算 total」这类问题。

## 最小可运行案例

```python
import math
from typing import Annotated, Generic, TypeVar

from fastapi import Depends, FastAPI, Query
from pydantic import BaseModel

app = FastAPI()
T = TypeVar("T")


class PageParams:
    def __init__(
        self,
        page: Annotated[int, Query(ge=1)] = 1,
        size: Annotated[int, Query(ge=1, le=50)] = 5,
    ) -> None:
        self.page = page
        self.size = size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int


class ItemOut(BaseModel):
    id: int
    name: str


ROWS = [{"id": i, "name": f"商品 {i}"} for i in range(1, 24)]


@app.get("/items", response_model=Page[ItemOut])
def list_items(params: Annotated[PageParams, Depends()]) -> dict:
    total = len(ROWS)
    return {
        "items": ROWS[params.offset : params.offset + params.size],
        "total": total,
        "page": params.page,
        "size": params.size,
        "pages": math.ceil(total / params.size) if total else 0,
    }
```

完整版本（两个模型复用、空集、边界）见 `examples/main.py`。

## 怎么跑

```powershell
cd "06-依赖注入\42-实战分页依赖\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 默认参数 -> total=23, pages=5
[PASS] 第二页 -> page=2 → ids=[6, 7, 8, 9, 10]
[PASS] total/pages -> total=23, pages=3
[PASS] 最后一页 -> 最后一页 3 条
[PASS] 越界空页 -> 越界 → items=[] 且 total 不变
[PASS] 空数据集 -> total=0 → pages=0
[PASS] size 上限 -> size=51 → 422
[PASS] page 下限 -> page=0 → 422
[PASS] 响应模型 -> 字段=['items', 'page', 'pages', 'size', 'total']
[PASS] 泛型 schema -> schemas=['Page_ItemOut_', 'Page_UserOut_']
[PASS] 泛型结构 -> Page_ItemOut_.items → ItemOut
[PASS] 两模型复用 -> 两端点参数一致，用户分页正确

结果：12/12 通过
```

## 核心 API 速查

| 组件 | 定义 | 作用 |
| --- | --- | --- |
| `PageParams` | `page/size` + `offset` | 解析查询参数 |
| `Page[T]` | 泛型 `BaseModel` | 统一响应结构 |
| `response_model=Page[ItemOut]` | 泛型具体化 | 生成 `Page_ItemOut_` |
| `Depends()` | 无参推断 | 注入 `PageParams` |

| 字段 | 语义 |
| --- | --- |
| `items` | 当前页数据 |
| `total` | **全量**条数（不是当前页）|
| `page` | 当前页（从 1 开始）|
| `size` | 每页条数 |
| `pages` | `ceil(total/size)`，空集为 0 |

| 实测行为 | 结果 |
| --- | --- |
| `page=2&size=5` | ids 6–10 |
| `page=3&size=10` | 3 条（不满）|
| `page=99` | 200 + `items=[]`，`total` 不变 |
| 空数据集 | `pages=0` |
| `size=51` | 422 |
| `page=0` | 422 |
| OpenAPI | `Page_ItemOut_`、`Page_UserOut_` 两个 schema |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `total` 取当前页长度 | 前端看不到总页数 | 查全量 count |
| 越界返回 404 | 前端翻页报错 | 200 + 空 items |
| `size` 不设上限 | 一次拉全表 | `le=50` |
| `page` 从 0 开始 | 与前端约定冲突 | 明确从 1 |
| `offset` 用 `page*size` | 第一页跳过数据 | `(page-1)*size` |
| `pages` 用 `total//size` | 最后一页丢失 | `ceil` |
| 空集 `pages` 算成 1 | 前端显示一页空白 | 0 |
| 泛型模型不写 `response_model` | 文档无具体 schema | 显式声明 |
| `Page[T]` 里 `items` 用 `list[Any]` | 丢失字段校验 | `list[T]` |
| 排序不固定 | 翻页重复/漏数据 | 加稳定排序键 |

## 毕业自查

- [ ] 能写出 `PageParams` + `offset`
- [ ] 能写出 `Page[T]` 泛型模型
- [ ] 能正确处理最后一页与越界页
- [ ] 能说明 `total` 必须来自全量
- [ ] 能在 OpenAPI 里找到 `Page_ItemOut_`
- [ ] 动手题一：加 `sort`/`order` 参数并限制枚举
- [ ] 动手题二：把 `total` 换成游标分页（`next_cursor`）

> 想看泛型模型在 OpenAPI 中的命名规则、`response_model` 与注解的优先级、`total` 的查询策略、18 条坑，继续读 [`base.md`](./base.md)。