# 42 实战：分页依赖 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「分页参数怎么抽象、泛型模型怎么进 OpenAPI、`total` 从哪来、边界怎么定」拆开。学完这章，你要能交付一套全站复用的分页契约。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1（本机实测） |
| 前置 | 第 35–38 章（依赖、别名）、第 21 章（响应模型） |
| 覆盖范围 | `PageParams`、`Page[T]`、`response_model` 泛型、边界、OpenAPI 命名 |
| 明确不覆盖 | 数据库 count 优化、游标分页完整实现、前端组件 |
| 学完验收 | 能跑通 `verify.py` 12/12、能定契约、能避开越界与 total 错误 |

## 0. 怎么用这份文件

**依据约定**：`` `[Pn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 分页契约
2 机制（第 2 节）    → 依赖 + 泛型模型
3 API（第 3 节）     → 参数、模型、response_model
4 边界（第 4 节）    → 越界、空集、上限、排序
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 契约模板
```

## 1. 概念：分页是「契约」不是「实现」

| 决定 | 选项 | 本章选择 |
| --- | --- | --- |
| 页码基准 | 0/1 | **1** |
| 越界 | 404 / 空页 | **空页 200** |
| 每页上限 | 无/有 | **50** |
| total | 当前页/全量 | **全量** |
| pages | `ceil`/`//` | **`ceil`，空集 0** |

契约一旦定，所有列表接口照做，前端只写一套。

## 2. 机制：两段拼装

```text
GET /items?page=2&size=5
 → PageParams(page=2, size=5)，offset=5
 → 查询：rows[offset:offset+size] + count(all)
 → Page[ItemOut](items=..., total=23, page=2, size=5, pages=5)
 → response_model 校验并过滤
```

| 事实 | 说明 |
| --- | --- |
| 参数由依赖解析 | 与端点参数同权，进 OpenAPI |
| 泛型模型生成具体 schema | `Page_ItemOut_` |
| 响应模型过滤多余字段 | 实测只输出 5 个字段 |

## 3. API 逐个拆解

### 3.1 `PageParams`

```python
class PageParams:
    def __init__(self, page: int = Query(1, ge=1), size: int = Query(5, ge=1, le=50)) -> None:
        ...

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size
```

| 要点 | 说明 |
| --- | --- |
| `offset` 用 property | 计算一次、无状态 |
| 上限必须有 | 防大页拖垮 DB |
| `Depends()` 无参 | 从注解推断 |

### 3.2 `Page[T]`

```python
class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int
```

| 字段 | 来源 |
| --- | --- |
| `items` | 切片结果 |
| `total` | 全量 count |
| `pages` | `ceil(total/size)` |

### 3.3 `response_model=Page[ItemOut]`

| 写法 | 效果 |
| --- | --- |
| `response_model=Page[ItemOut]` | 生成 `Page_ItemOut_`（实测）|
| 返回注解 `-> Page[ItemOut]` | 等价 |
| 不声明 | 泛型退化为 `Any`，文档丢失 |

实测：`Page_ItemOut_.properties.items.items.$ref == ItemOut`。

## 4. 边界条件

### 4.1 越界（实测）

`?page=99` → 200，`items=[]`，`total=23`，`page=99`。前端可据此显示「没有更多」。

### 4.2 最后一页（实测）

`?page=3&size=10` → 3 条（21–23）。

### 4.3 空集（实测）

`total=0` → `pages=0`。若用 `total // size` 会得 0 但 `(total + size - 1)//size` 也 0，需保证 `ceil` 语义。

### 4.4 参数边界（实测）

| 输入 | 结果 |
| --- | --- |
| `size=51` | 422 `loc=["query","size"]` |
| `page=0` | 422 `loc=["query","page"]` |
| `size=abc` | 422 `int_parsing` |

### 4.5 排序稳定性

分页必须带稳定排序（如 `ORDER BY id`），否则翻页会重复/漏。示例用列表切片天然稳定，**数据库场景未实测**。

### 4.6 `total` 的成本

| 方案 | 成本 | 精度 |
| --- | --- | --- |
| 每次 `COUNT(*)` | 高（大表）| 精确 |
| 缓存 count | 低 | 有延迟 |
| 近似（`EXPLAIN` 估算）| 低 | 近似 |
| 游标分页 | 无 count | 无总页 |

### 4.7 与 `response_model` 的过滤

模型外的字段会被丢弃（实测只保留 5 个键）。别把 `next`/`prev` 之类塞进 dict 再指望输出。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `total` 用当前页长度 | 前端无法算页数 | 全量 count | `[P1]` |
| 越界 404 | 翻页报错 | 200 空页 | `[P1]` |
| `offset = page * size` | 第一页跳过 | `(page-1)*size` | `[P1]` |
| `pages` 用整除 | 最后一页丢 | `ceil` | `[P1]` |
| 空集 `pages=1` | 空白页 | 0 | 实测 |
| 不设 `size` 上限 | 拖垮 DB | `le=50` | `[P2]` |
| 页码基准不统一 | 前端差一页 | 文档写清 | `[P1]` |
| 不声明 `response_model` | 文档无具体结构 | `Page[T]` | 实测 |
| `items: list[Any]` | 丢字段校验 | `list[T]` | 实测 |
| 排序不固定 | 翻页重复 | 稳定排序 | `[P2]` |
| 在大表上每次 count | 慢 | 缓存/近似 | `[P3]` |
| 分页参数散落各端点 | 不一致 | 依赖统一 | 第 35 章 |
| 用 `page` 做 offset 计算两次 | 不一致 | 统一 property | `[P1]` |
| `size=0` 允许 | 除零/空页 | `ge=1` | 实测 |
| 越界时 `pages` 重算错 | 前端混乱 | 只按 total 算 | 实测 |
| 返回 `total` 为 str | 契约破坏 | 类型注解 int | 第 21 章 |
| 忽略 `response_model` 的过滤 | 多字段泄露 | 用模型 | 第 21 章 |
| 分页与过滤/搜索分离 | 两次查询不一致 | 同一查询构造 | `[P2]` |
| 用 Header 传 `size` | 缓存/日志里不可见 | 用 query 参数 | `[P1]` |

## 6. 最佳实践与编码建议

### 6.1 契约模板

```python
from typing import Annotated, Generic, TypeVar

from fastapi import Depends, Query
from pydantic import BaseModel, Field

T = TypeVar("T")


class PageParams:
    def __init__(
        self,
        page: Annotated[int, Query(ge=1, description="页码，从 1 开始")] = 1,
        size: Annotated[int, Query(ge=1, le=50)] = 20,
    ) -> None:
        self.page, self.size = page, size

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.size


class Page(BaseModel, Generic[T]):
    items: list[T]
    total: int = Field(ge=0)
    page: int = Field(ge=1)
    size: int = Field(ge=1)
    pages: int = Field(ge=0)


type PageDep = Annotated[PageParams, Depends()]
```

| 建议 | 说明 |
| --- | --- |
| 契约写进 README | 前端对齐 |
| 上限可配 | 环境变量 |
| `pages` 由服务端算 | 前端不再算 |
| 排序必填或有默认 | 稳定 |
| 与过滤共享查询 | 一致 |

### 6.2 选型速查

| 场景 | 做法 |
| --- | --- |
| 管理后台 | 页码分页 |
| 信息流 | 游标分页 |
| 大表统计 | 近似 total |
| 导出 | 流式，不分页 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[P1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/dependencies/ | 依赖构造分页参数 |
| `[P2]` | 参考 | https://www.postgresql.org/docs/current/queries-limit.html | `LIMIT/OFFSET` 与性能 |
| `[P3]` | 参考 | https://use-the-index-luke.com/no-offset | 大偏移分页问题 |

> **核对状态**：`[P1]`–`[P3]` 为官方/参考链接，**本次未逐页直连复核**；切片、`total/pages`、越界空页、空集、边界 422、泛型 schema 名与结构、两模型复用均为本机实测，`examples/verify.py` 复现 12/12 通过。数据库 `COUNT(*)` 成本**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 分页契约的 5 个决定
- [ ] `offset` 与 `page` 的关系
- [ ] `total` 与 `pages` 的来源
- [ ] 越界为什么返回空页
- [ ] 泛型 schema 命名规则

**能写出（代码层）**：

- [ ] `PageParams` + `offset`
- [ ] `Page[T]`
- [ ] `response_model=Page[X]`
- [ ] 空集/越界处理
- [ ] 两个模型复用

**能判断（避坑层）**：

- [ ] 看到 `total=len(items)` → 指出错
- [ ] 看到 `offset=page*size` → 指出差一页
- [ ] 看到 `pages` 整除 → 指出丢页
- [ ] 看到无上限 → 指出拖库
- [ ] 看到无排序 → 指出翻页重复

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 12/12
- [ ] `/docs` 找 `Page_ItemOut_`
- [ ] `?page=99` 看空页

## 9. 下一章衔接

第 43 章 `实战：鉴权与多租户`：依赖链解析 token → 用户 → 租户，用 `Request.state` 传递上下文，保证跨租户隔离（同一资源 ID 不同租户互不可见），并讲 401/403/404 的选择。

本章留下的伏笔：

1. 多租户隔离 第 43 章。
2. 安全方案与 OAuth2 第 44 章起。
3. 测试策略 第 71 章。