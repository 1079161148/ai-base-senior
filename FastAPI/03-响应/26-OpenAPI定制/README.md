# 26 OpenAPI 文档定制

## 一句话结论

`/openapi.json` 是对外契约：SDK、网关、前端都读它。应用级（`title`/`version`/`tags`）、端点级（`summary`/`description`/`responses`/`deprecated`）、字段级（`Field(description=..., examples=...)`）都要显式写。想彻底改写 schema 就替换 `app.openapi` —— 但要先保存原方法，否则无限递归（实测 `RecursionError`）。

学完这一章，你能：写出可读的 `/docs`、给接口打标签分组、标注废弃、注入 vendor 扩展字段、隐藏内部端点、自定义 `servers`。

## 最小可运行案例

```python
from typing import Annotated

from fastapi import FastAPI
from pydantic import BaseModel, Field

app = FastAPI(
    title="商品服务 API",
    version="1.2.3",
    description="**文档即契约**",
    openapi_tags=[{"name": "商品", "description": "商品的增删改查"}],
)


class ItemIn(BaseModel):
    name: Annotated[str, Field(min_length=2, description="商品名称", examples=["机械键盘"])]


@app.post(
    "/items",
    tags=["商品"],
    summary="创建商品",
    description="长描述支持 **Markdown**",
    response_description="创建成功的商品",
    deprecated=False,
    responses={409: {"description": "同名商品已存在"}},
)
def create_item(item: ItemIn) -> dict[str, str]:
    return {"name": item.name}


@app.get("/internal/metrics", include_in_schema=False)
def metrics() -> dict[str, int]:
    return {"items": 1}
```

完整版本（模型示例、`openapi_extra`、自定义 `servers`）见 `examples/main.py`。

## 怎么跑

```powershell
cd "03-响应\26-OpenAPI定制\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

打开 <http://127.0.0.1:8000/docs> 能看到标签分组、字段说明、废弃划线。

预期输出：

```text
[PASS] info 元信息 -> 商品服务 API v1.2.3
[PASS] 标签分组 -> tags=['商品', '运维', '内部']
[PASS] 字段说明与示例 -> name.examples=["机械键盘"]
[PASS] 模型级示例 -> examples=[{'id': 1, 'name': '机械键盘', 'price': '399.00'}]
[PASS] 查询参数描述 -> keyword 描述=名称关键字
[PASS] 响应描述 -> 201 description=创建成功的商品
[PASS] 自定义 responses -> responses=['201', '409', '422']
[PASS] deprecated -> 旧版 marked deprecated，新版没有
[PASS] openapi_extra -> x-internal-owner=team-goods
[PASS] 隐藏端点 -> 不在 paths，但能访问
[PASS] 自定义 schema 缓存 -> servers 已注入，schema 已缓存

结果：11/11 通过
```

## 核心 API 速查

| 层级 | 参数 | 落在 schema 的哪 |
| --- | --- | --- |
| 应用 | `title`/`version`/`description`/`contact`/`license_info` | `info` |
| 应用 | `openapi_tags` | 顶层 `tags` |
| 端点 | `tags`/`summary`/`description`/`deprecated` | operation |
| 端点 | `response_description` | `responses[码].description` |
| 端点 | `responses={409: {"description": ...}}` | 自定义状态码文档 |
| 端点 | `openapi_extra={"x-...": ...}` | operation 里原样合并 |
| 端点 | `include_in_schema=False` | 不进 `paths` |
| 字段 | `Field(description=..., examples=[...])` | `properties.<f>` |
| 模型 | `ConfigDict(json_schema_extra={...})` | 模型 schema 根 |
| 查询 | `Query(description=..., examples=[...])` | `parameters` |

| 自定义需求 | 做法 |
| --- | --- |
| 加 `servers` | 替换 `app.openapi` 并缓存 |
| 加安全方案 | 同上，或 `dependencies`（第 44 章）|
| 隐藏端点 | `include_in_schema=False` |
| 分组顺序 | `openapi_tags` 顺序即展示顺序 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 替换 `app.openapi` 后又调用 `app.openapi()` | **无限递归** `RecursionError` | 先 `_base = app.openapi` |
| 自定义 openapi 不缓存 | 每次请求重建，CPU 升高 | 写 `app.openapi_schema` |
| 以为 `deprecated=True` 会拒绝调用 | 仍能正常调用 | 只是文档标记 |
| 中文标签不声明 `openapi_tags` | 文档里没有分组描述 | 显式声明 |
| docstring 当内部备注写 | 会进 `description`（第 21 章）| 当公开文档写 |
| 隐藏端点当作安全措施 | 只是不写文档，接口仍可调用 | 真正的鉴权在依赖层 |
| `openapi_extra` 覆盖已生成字段 | 可能破坏 schema | 只用 `x-` 扩展 |
| 字段说明写在注释里 | 注释不进 schema | 用 `Field(description=...)` |
| 版本号不改 | 客户端无法判断兼容性 | 变更即升 `version` |

## 毕业自查

- [ ] 能说出 `/openapi.json` 会被谁消费
- [ ] 能写出应用级元信息与标签分组
- [ ] 能给字段加说明与示例
- [ ] 能标注废弃端点
- [ ] 能用 `openapi_extra` 加扩展字段
- [ ] 能隐藏内部端点并说明它不是安全措施
- [ ] 能正确替换 `app.openapi` 且不递归
- [ ] 动手题一：给 `servers` 加第二个环境（测试环境）
- [ ] 动手题二：用一个真实 SDK 生成器（如 openapi-generator）消费本项目 schema

> 想看 schema 合并顺序、`by_alias` 影响、安全方案注入、19 条坑，继续读 [`base.md`](./base.md)。
