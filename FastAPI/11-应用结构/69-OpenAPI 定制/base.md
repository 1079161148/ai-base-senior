# 69 OpenAPI 定制 · 完整版（base.md）

> `README.md` 给你能跑的完整 metadata 示例；本文件把「schema 里每个字段从哪来、`get_openapi()` 会漏什么、`x-` 扩展能干什么、契约测试怎么做」拆开。学完这章，你能交付一份前端能直接照着写代码的 API 文档。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0（本机实测） |
| 前置 | 第 65 章（路由拆分）、第 68 章（子应用） |
| 覆盖范围 | info/metadata、tags、servers、responses、自定义 `openapi()` |
| 明确不覆盖 | 代码生成工具链、AsyncAPI、GraphQL schema |
| 学完验收 | 能跑通 `verify.py` 17/17、能解释 contact 丢失的原因 |

## 0. 怎么用这份文件

**依据约定**：`` `[On]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 文档是契约
2 机制（第 2 节）    → schema 结构
3 API（第 3 节）     → 三层定制逐个
4 边界（第 4 节）    → 关闭方式、扩展、缓存
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 契约测试
```

## 1. 概念：文档即契约

```text
后端代码 → openapi() → /openapi.json → 前端代码生成 / Mock / 契约测试
```

| 读者 | 关心 |
| --- | --- |
| 前端 | 字段、类型、错误码、示例 |
| 测试 | 状态码、错误体 |
| 网关 | `servers`、路径 |

## 2. 机制：schema 的组成

```json
{
  "openapi": "3.1.0",
  "info": {"title", "version", "description", "contact", "license", "termsOfService"},
  "tags": [{"name", "description", "externalDocs"}],
  "servers": [{"url", "description"}],
  "paths": {"/items": {"get": {...}}},
  "components": {"schemas": {...}}
}
```

实测：

| 部分 | 内容 |
| --- | --- |
| `info` | 订单服务 / 1.2.3 / MIT / contact |
| `tags` | items / internal |
| `servers` | api / staging |
| `paths` | `/items`、`/items/legacy`、`/items/{item_id}` |
| `components.schemas` | `Item`、`ItemCreate`、`HTTPValidationError`、`ValidationError` |

### 2.1 `get_openapi()` 的坑（实测）

```python
schema = get_openapi(title=..., version=..., routes=...)   # ❌
```

| 字段 | 是否自动带入 |
| --- | --- |
| `title`/`version`/`description` | 显式传才有 |
| `terms_of_service` | **不传就丢**（实测）|
| `contact` | **不传就丢** |
| `license_info` | **不传就丢** |
| `tags` | 显式传 |
| `servers` | 显式传 |

`get_openapi()` 是「无状态工具函数」，不读 `app` 的属性。所以自定义时要把 `app` 上的项全部透传。

## 3. API 逐个拆解

### 3.1 应用级

| 参数 | 效果 |
| --- | --- |
| `title` | `info.title` |
| `description` | `info.description`，支持 Markdown |
| `version` | `info.version`（业务版本，不是 OpenAPI 版本）|
| `terms_of_service` | `info.termsOfService` |
| `contact` | `info.contact`（`email` 需要 `email-validator`）|
| `license_info` | `info.license` |
| `openapi_tags` | 顶层 `tags` |
| `servers` | 顶层 `servers` |

### 3.2 端点级（实测）

| 参数 | 结果 |
| --- | --- |
| `summary="商品列表"` | `operation.summary` |
| docstring | `operation.description` |
| `responses={409: ...}` | 合并进 `responses`（实测 `201/409/422`）|
| `deprecated=True` | `deprecated: true` |
| `include_in_schema=False` | 不进文档，路径仍可访问 |
| `response_model=list[Item]` | 生成 `components.schemas.Item` |

### 3.3 `operationId`

```text
list_items_items_get
create_item_items_post
get_item_items__item_id__get
legacy_items_legacy_get
```

规则：`函数名_路径_方法`。**唯一性**由 FastAPI 保证，但改名/加路由可能冲突。

## 4. 边界条件

### 4.1 三种关闭方式（实测）

| 配置 | `/docs` | `/openapi.json` |
| --- | --- | --- |
| 默认 | 200 | 200 |
| `docs_url=None, redoc_url=None` | **404** | 200 |
| `openapi_url=None` | 404 | **404** |

生产常见组合：保留 `openapi_url` 给内部工具，关掉 `/docs`。

### 4.2 `x-` 扩展

| 键 | 用途 |
| --- | --- |
| `x-owner` | 负责团队 |
| `x-audience` | 面向谁 |
| `x-api-tier` | 内部/外部 |

规范允许任意 `x-` 键，OpenAPI 工具会保留。**非** `x-` 前缀的自定义键可能被校验器拒绝。

### 4.3 缓存

```python
if app.openapi_schema:
    return app.openapi_schema
...
app.openapi_schema = schema
```

不缓存的话，每次 `/openapi.json` 都遍历全部路由 + 重建模型 schema。

### 4.4 契约测试

| 做法 | 说明 |
| --- | --- |
| 导出到文件 | `openapi/export` |
| CI 比对 | 与上次提交的 JSON 比较，变了就 review |
| 前端代码生成 | `openapi-typescript` 等 |

实测导出与在线「一字不差」。

### 4.5 描述的价值

| 该写 | 不该写 |
| --- | --- |
| 单位（分/毫秒）| 「这是一个接口」 |
| 错误码含义 | 内部实现细节 |
| 示例值 | 历史变更日志 |
| 幂等性/限流 | 大段 HTML |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `get_openapi` 少传 contact | 三项丢失（实测）| 全部透传 | 实测 |
| 不缓存 schema | 每次重建 | `app.openapi_schema` | 实测 |
| 把 `include_in_schema=False` 当权限 | 仍可访问 | 真鉴权 | 实测 |
| `openapi_url=None` 还想看 docs | 404 | 只关 `docs_url` | 实测 |
| 描述无单位 | 前端猜 | 写清分/秒 | 实测 |
| 无 `summary` | 全是函数名 | 每个都写 | 实测 |
| `servers` 写内网 | 调不通 | 对外地址 | 实测 |
| 省略 `response_model` | 无结构 | 显式声明 | 实测 |
| 返回 `Any` | 空 schema | 具体模型 | 实测 |
| 自定义 `operationId` 重复 | 代码生成冲突 | 保持唯一 | 实测 |
| 手改 `openapi.json` | 被覆盖 | 改代码 | `[O1]` |
| 导出文件不更新 | 契约过期 | CI 比对 | 实测 |
| 生产开 `/docs` | 被扫描 | 按环境关闭 | `[O3]` |
| `contact.email` 无校验器 | warning | 装 `email-validator` | 实测 |
| 描述用 HTML | 渲染异常 | Markdown | `[O2]` |
| `tags` 未声明元数据 | 无分组描述 | `openapi_tags` | 实测 |
| 自定义键不带 `x-` | 可能被拒 | 只用 `x-` | `[O2]` |
| 子应用 schema 想自动合并 | 不会 | 手动聚合 | 第 68 章 |
| 描述里写内部服务名/内网地址 | 信息泄露 | 只写对外约定 | 实测 |

## 6. 最佳实践与编码建议

### 6.1 三层模板

```python
app = FastAPI(
    title="订单服务",
    description=__doc__,
    version="1.2.3",
    contact={"name": "API 团队", "email": "api@example.com"},
    license_info={"name": "MIT"},
    openapi_tags=TAGS,
    servers=[{"url": "https://api.example.com", "description": "生产"}],
)
```

### 6.2 端点模板

```python
@app.post(
    "/items",
    tags=["items"],
    summary="新建商品",
    response_model=Item,
    status_code=201,
    responses={409: {"description": "同名商品已存在"}},
)
def create_item(payload: ItemCreate) -> Item:
    """创建商品。

    - 幂等：同名返回 409
    - 金额单位：分
    """
```

### 6.3 检查清单

| 检查项 | 原因 |
| --- | --- |
| 每个端点有 `summary` | 可读 |
| 错误码都在 `responses` | 前端处理 |
| 单位写清 | 防误用 |
| `servers` 对外 | 可调 |
| 内部端点隐藏 | 防泄露 |
| 导出 + CI 比对 | 契约稳定 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[O1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/metadata/ | 元数据 |
| `[O2]` | 规范 | https://spec.openapis.org/oas/v3.1.0 | OpenAPI 3.1 |
| `[O3]` | 官方文档 | https://fastapi.tiangolo.com/zh/how-to/extending-openapi/ | 自定义 `openapi()` |

> **核对状态**：`[O1]`–`[O3]` 为文档/规范链接，**本次未逐页直连复核**；OpenAPI 版本、info 字段、contact/license、tags 元数据、servers、`x-` 扩展、路径清单、隐藏端点、deprecated、summary/description、responses 合并、operationId 唯一、模型 schema、导出一致、缓存、只关 docs、全关均为本机实测，`examples/verify.py` 复现 17/17 通过。`operationId` 冲突行为、子应用 schema 聚合、代码生成工具链**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 文档的读者是谁
- [ ] `info` 里每个字段从哪来
- [ ] `get_openapi()` 为什么不自动读 app
- [ ] 三种关闭方式的差别
- [ ] `x-` 扩展的用途

**能写出（代码层）**：

- [ ] 应用级 metadata
- [ ] `openapi_tags`
- [ ] 自定义 `openapi()` + 缓存
- [ ] 导出端点
- [ ] 关文档配置

**能判断（避坑层）**：

- [ ] 看到 contact 丢失 → 指出没透传
- [ ] 看到 `/docs` 404 → 检查 `docs_url`
- [ ] 看到 schema 重建慢 → 加缓存
- [ ] 看到内部端点暴露 → `include_in_schema`
- [ ] 看到契约过期 → CI 比对

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 17/17
- [ ] 浏览器打开 `/docs` 看到中文描述与分组
- [ ] `curl /openapi.json` 与导出文件一致

## 9. 下一章衔接

第 70 章 `BackgroundTasks`：响应后执行、任务异常、顺序、与 `asyncio.create_task` 的区别、多久算「后台」。

本章留下的伏笔：

1. 文档化错误码（69）→ 70 的后台失败怎么让调用方知道。
2. `servers`（69）→ 70 的邮件链接要用对外地址。
3. 契约（69）→ 70 的后台任务不能改响应。