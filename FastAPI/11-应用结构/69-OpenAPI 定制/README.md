# 69 OpenAPI 定制

## 一句话结论

文档是**给前端的契约**，可以分三层定制：应用级（`title/description/version/contact/license/servers`）、分组级（`openapi_tags`）、端点级（`summary/description/responses/deprecated/include_in_schema`），最后还能整体接管 `app.openapi()` 注入 `x-` 扩展。实测生成了 `3.1.0` 的 schema：3 条业务路径、2 个 `servers`、4 个唯一 `operationId`、`409`/`404` 都在 `responses` 里，导出的 JSON 与在线 `/openapi.json` **一字不差**。一个大坑：自己写 `custom_openapi()` 时，`get_openapi()` **不会**自动从 `app` 读 `terms_of_service`/`contact`/`license_info`，必须显式传，否则这三项静默丢失。

## 最小可运行案例

```python
from typing import Any

from fastapi import FastAPI
from fastapi.openapi.utils import get_openapi

app = FastAPI(
    title="订单服务",
    description="金额单位为分",
    version="1.2.3",
    contact={"name": "API 团队", "email": "api@example.com"},
    license_info={"name": "MIT"},
    openapi_tags=[{"name": "items", "description": "商品读写"}],
    servers=[{"url": "https://api.example.com", "description": "生产"}],
)


@app.get("/items", tags=["items"], summary="商品列表")
def list_items() -> list[str]:
    return ["键盘"]


def custom_openapi() -> dict[str, Any]:
    if app.openapi_schema:
        return app.openapi_schema
    schema = get_openapi(
        title=app.title,
        version=app.version,
        description=app.description,
        routes=app.routes,
        tags=app.openapi_tags,
        servers=app.servers,
        # 这三项必须显式传
        terms_of_service=app.terms_of_service,
        contact=app.contact,
        license_info=app.license_info,
    )
    schema["x-owner"] = "team-order"
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi  # type: ignore[method-assign]
```

## 怎么跑

```powershell
cd "11-应用结构\69-OpenAPI 定制\examples"
uv sync
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] OpenAPI 版本 -> 3.1.0
[PASS] info 核心 -> 订单服务 v1.2.3
[PASS] contact/license -> contact + MIT
[PASS] tags 元数据 -> items / internal
[PASS] servers -> 生产 + 预发
[PASS] x- 扩展 -> x-owner / x-api-tier / x-audience
[PASS] 路径清单 -> 3 条
[PASS] 隐藏端点 -> 隐藏但仍可调用
[PASS] deprecated -> deprecated=True
[PASS] summary/description -> summary + description
[PASS] 共享 responses -> 409 / 404 均在
[PASS] operationId -> 4 个唯一 operationId
[PASS] 模型 schema -> Item / ItemCreate / 校验错误
[PASS] 导出一致 -> 一字不差
[PASS] 缓存 -> 同一 dict 对象
[PASS] 只关 docs -> /docs 404 / schema 200
[PASS] 全关 -> 全 404

结果：17/17 通过
```

## 核心 API 速查

| 层级 | 参数 | 实测 |
| --- | --- | --- |
| 应用 | `title` / `version` | `订单服务` / `1.2.3` |
| 应用 | `terms_of_service` | 进 `info.termsOfService` |
| 应用 | `contact` / `license_info` | 进 `info.contact/license` |
| 应用 | `servers` | 两条，顺序保留 |
| 应用 | `openapi_tags` | 进顶层 `tags` |
| 端点 | `summary` | 进 operation |
| 端点 | docstring | 进 `description` |
| 端点 | `responses` | 与默认合并 |
| 端点 | `deprecated` | `true` |
| 端点 | `include_in_schema=False` | 文档没有，路径可用 |
| 应用 | `docs_url=None` | `/docs` 404，schema 仍在 |
| 应用 | `openapi_url=None` | schema 与 docs 全 404 |

| 实测 | 值 |
| --- | --- |
| `openapi` | `3.1.0` |
| 业务路径 | 3 条 |
| `operationId` | 4 个唯一 |
| `schemas` | `Item`/`ItemCreate`/`HTTPValidationError`/`ValidationError` |
| 导出 vs 在线 | 完全相同 |
| `app.openapi()` | 同一对象（缓存）|

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `custom_openapi()` 少传 contact | 三项静默丢失 | 显式传全 |
| 不缓存 `openapi_schema` | 每次请求重建 | 赋值后返回 |
| 用 `include_in_schema=False` 当权限 | 路径仍可访问 | 真正的鉴权依赖 |
| `openapi_url=None` 还想要 `/docs` | `/docs` 也 404 | 只关 `docs_url` |
| 描述写一堆废话 | 前端不看 | 写单位、错误体、示例 |
| 不给 `summary` | 文档里全是函数名 | 每个端点都写 |
| `servers` 写内网地址 | 前端调不通 | 写对外地址 |
| `response_model` 省略 | 前端拿不到结构 | 显式声明 |
| 用 `Any` 当返回值 | schema 为空 | 具体模型 |
| `operationId` 重名 | 代码生成冲突 | 自定义或改名 |
| 手工改 `openapi.json` | 下次生成被覆盖 | 改代码 |
| 导出文件不更新 | 前端契约过期 | CI 里比对 |
| 文档暴露内部端点 | 信息泄露 | `include_in_schema=False` |
| 生产开着 `/docs` | 可被扫描 | 按环境关闭 |
| email 字段无校验器 | 启动 warning | 装 `email-validator` |
| 描述里写 HTML | 渲染异常 | 用 Markdown |
| `tags` 没在 `openapi_tags` 声明 | 分组无描述 | 声明元数据 |
| `x-` 键名随便写 | 部分工具丢弃非标准键 | 只用 `x-` 前缀 |

## 毕业自查

- [ ] 能写出应用级 metadata
- [ ] 能用 `openapi_tags` 分组
- [ ] 能接管 `openapi()` 注入扩展
- [ ] 能区分三种关闭方式
- [ ] 能导出契约给前端
- [ ] 动手题一：给所有端点补 `summary` 与示例
- [ ] 动手题二：CI 里比对导出文件与在线 schema

> 想看 OpenAPI 3.1 结构、`get_openapi()` 的字段来源、`operationId` 生成规则、契约测试、18 条坑，继续读 [`base.md`](./base.md)。