# 26 OpenAPI 文档定制 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「schema 是怎么拼出来的、每层参数落在哪、替换 `app.openapi` 的正确姿势、文档与安全的边界」拆开。学完这章，你要能把文档当契约维护。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1（本机实测） |
| 前置 | 第 21–25 章（响应模型、状态码、联合、响应头、直接返回） |
| 覆盖范围 | 应用/端点/字段三级元信息、`openapi_tags`、`responses`、`openapi_extra`、`include_in_schema`、自定义 schema |
| 明确不覆盖 | 安全方案（第 44 章）、`/docs` 前端替换、SDK 生成细节 |
| 学完验收 | 能跑通 `verify.py` 11/11、能定位每个参数落在 schema 哪处、能安全替换 `app.openapi` |

## 0. 怎么用这份文件

**依据约定**：`` `[Pn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 文档为什么是契约
2 机制（第 2 节）    → schema 怎么拼出来
3 API（第 3 节）     → 三级参数逐个拆
4 边界（第 4 节）    → 自定义、合并、缓存、安全边界
5 注意事项（第 5 节）→ 19 条对照
6 最佳实践（第 6 节）→ 文档模板
```

## 1. 概念：谁在读这份 JSON

| 消费者 | 用途 | 出错的后果 |
| --- | --- | --- |
| `/docs`（Swagger UI） | 人手调试 | 用不了、看不懂 |
| SDK 生成器 | 生成客户端 | 类型错、调用失败 |
| 网关/BFF | 路由与校验 | 请求被拒 |
| 前端 | 联调依据 | 字段对不上 |

结论：schema 里的每个字段名、类型、必填性，都是**契约**，改动等于改 API。

## 2. 机制：schema 的拼装顺序

```text
app = FastAPI(...)              → info / tags / servers
@pydantic 模型                  → components.schemas
@路由装饰器                      → paths.<path>.<method>
   参数（Path/Query/Header/Cookie）→ parameters
   requestBody（模型）           → requestBody
   response_model + status_code  → responses.<code>.content
   responses={...}               → 合并进 responses
   openapi_extra                 → 合并进 operation
docstring                        → description（若无显式 description）
```

| 事实 | 说明 |
| --- | --- |
| 显式 `description` 优先于 docstring | 实测写了就不覆盖 |
| `responses` 与自动生成合并 | 同码以你写的为准 |
| `openapi_extra` 最后合并 | 可覆盖任意键（谨慎）|
| 结果缓存到 `app.openapi_schema` | 同一进程只算一次 |

## 3. API 逐个拆解

### 3.1 应用级

| 参数 | 落点 | 说明 |
| --- | --- | --- |
| `title` / `version` | `info` | 版本变更应与契约变更同步 |
| `description` | `info.description` | 支持 Markdown |
| `summary` | `info.summary` | 一句话 |
| `contact` / `license_info` | `info` 子对象 | 支持与法务要求 |
| `openapi_tags` | 顶层 `tags` | 顺序=展示顺序 |
| `servers` | 顶层 `servers` | 需自定义（构造函数无此参数）|

### 3.2 端点级

| 参数 | 落点 |
| --- | --- |
| `tags=["商品"]` | `operation.tags` |
| `summary` | `operation.summary` |
| `description` | `operation.description` |
| `response_description` | `responses[默认码].description` |
| `deprecated=True` | `operation.deprecated` |
| `responses={...}` | 合并进 `responses` |
| `openapi_extra` | 合并进 operation |
| `include_in_schema=False` | 整条不进 `paths` |

### 3.3 字段级

| 写法 | 落点 |
| --- | --- |
| `Field(description="...")` | `properties.<f>.description` |
| `Field(examples=["..."])` | `properties.<f>.examples` |
| `Query(description=..., examples=[...])` | `parameters[]` |
| `Header(description=...)` | `parameters[]`（in: header）|
| `ConfigDict(json_schema_extra={"examples": [...]})` | 模型根 `examples` |
| `Field(deprecated=True)` | 字段级 deprecated |

## 4. 边界条件

### 4.1 替换 `app.openapi` 的正确写法（实测）

```python
_base_openapi = app.openapi          # ← 必须，否则递归


def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema
    schema = _base_openapi()
    schema["servers"] = [{"url": "https://api.example.com"}]
    app.openapi_schema = schema
    return schema


app.openapi = custom_openapi
```

| 错误做法 | 现象（实测） |
| --- | --- |
| 函数里调 `app.openapi()` | `RecursionError: maximum recursion depth exceeded` |
| 不缓存 `app.openapi_schema` | 每次 `/openapi.json` 都重建 |

### 4.2 `openapi_extra` 的风险

| 用法 | 评价 |
| --- | --- |
| 加 `x-` 扩展字段 | ✅ 安全 |
| 覆盖 `responses` | ⚠️ 可能与你写的合并冲突 |
| 覆盖 `requestBody` | ❌ 破坏参数校验文档 |

### 4.3 `include_in_schema=False` 不是安全措施

实测：端点不在 `paths`，但 `GET /internal/metrics` 仍返回 200。

| 需求 | 正确做法 |
| --- | --- |
| 不想让人看到 | `include_in_schema=False` |
| 不想让人调用 | 鉴权依赖 / 网络隔离 |
| 两者都要 | 都做 |

### 4.4 模型复用与 schema 命名

| 现象 | 说明 |
| --- | --- |
| 同名模型冲突 | FastAPI 会加后缀（如 `ItemOut-Input`）|
| `response_model` 与入参同名 | 生成 `<Name>-Input` / `<Name>-Output` |
| `by_alias=False` 时 | schema 用字段名而非别名（第 14 章）|

SDK 生成器对后缀名敏感，命名时带 `In`/`Out` 后缀更稳。

### 4.5 文档与代码不同步

| 漂移来源 | 例子 |
| --- | --- |
| 返回值绕过模型 | `return JSONResponse(...)`（第 25 章）|
| 运行时改状态码 | `response.status_code=202`，文档仍是 201 |
| `exclude` 参数 | 文档说有该字段，实际被排除 |

对策：把 OpenAPI 快照纳入 CI，变更时人工确认（契约测试）。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 替换 openapi 后调 `app.openapi()` | 递归崩溃 | 保存原方法 | 实测 |
| 不缓存 schema | 每次重建 | 写 `openapi_schema` | 实测 |
| `deprecated=True` 想禁止调用 | 仍可用 | 加状态码/下线策略 | 实测 |
| 用 `include_in_schema=False` 当鉴权 | 接口仍可访问 | 加依赖鉴权 | 实测 |
| 字段说明写注释 | 不进 schema | `Field(description=)` | 实测 |
| 中文 tag 不声明 `openapi_tags` | 无分组描述 | 显式声明 | 实测 |
| `openapi_extra` 覆盖核心键 | schema 损坏 | 只用 `x-` | 实测 |
| docstring 写内部备注 | 公开可见 | 当公开文档 | 第 21 章 |
| 版本号从不改 | 客户端无法判断 | 随契约变更 | `[P1]` |
| 同码 `responses` 写两次 | 后者覆盖 | 合并写一处 | `[P1]` |
| 用 `responses` 期望改变返回 | 只是文档 | 代码自己控制 | 第 23 章 |
| 大量端点无 tag | `/docs` 一坨 | 按模块分组 | `[P2]` |
| `summary` 写太长 | `/docs` 挤 | 短句 | `[P2]` |
| 模型里 `examples` 用 Python 对象 | 某些生成器不认 | 用 JSON 可序列化的值 | `[P3]` |
| 直接改 `app.openapi_schema` 后不复位 | 测试间互相污染 | fixture 里重置 | 第 71 章 |
| 未给 4xx 写文档 | 客户端不知道怎么处理 | `responses={4xx: ...}` | `[P1]` |
| 忽略 `by_alias` | 文档字段名与线上不一致 | 统一约定 | 第 14 章 |
| 认为 `/docs` 可上生产 | 暴露内部接口清单 | 生产关掉或加鉴权 | `[P4]` |
| 手写 openapi.json | 与代码不同步 | 由框架生成 + 定制钩子 | `[P1]` |
| 忘了 `/docs` 也读 `servers` | 「Try it out」打到错误地址 | 按环境配 `servers` | `[P2]` |

## 6. 最佳实践与编码建议

### 6.1 文档模板

```python
app = FastAPI(
    title="<业务> API",
    version="1.0.0",
    description="一句话定位 + 认证方式 + 错误结构说明",
    openapi_tags=[
        {"name": "商品", "description": "CRUD"},
        {"name": "运维", "description": "探活/版本"},
    ],
    contact={"name": "后端组", "url": "https://example.com"},
)


@app.post(
    "/items",
    tags=["商品"],
    summary="创建商品",
    response_description="创建成功的商品",
    status_code=201,
    responses={409: {"description": "同名已存在"}},
)
def create_item(item: ItemIn) -> ItemOut: ...
```

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 每个端点都有 `tags`+`summary` | 文档可用性底线 |
| 4xx 都写 `responses` | 客户端契约 |
| 字段都写 `description` | 前端少问 |
| 版本号随契约变 | 便于灰度 |
| `include_in_schema=False` 只用于内部 | 不代替鉴权 |
| 自定义 openapi 放 `main.py` 一处 | 好维护 |
| 文档快照进 CI | 防漂移 |

### 6.3 选型速查

| 需求 | 做法 |
| --- | --- |
| 分组 | `openapi_tags` |
| 废弃 | `deprecated=True` |
| 隐藏 | `include_in_schema=False` |
| 扩展字段 | `openapi_extra` |
| 多环境地址 | 自定义 `servers` |
| 统一安全方案 | 自定义 openapi 或依赖 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[P1]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/additional-responses/ | `responses` 定制 |
| `[P2]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/metadata/ | 元信息与 tags |
| `[P3]` | 官方文档 | https://docs.pydantic.dev/latest/concepts/json_schema/ | `json_schema_extra`/examples |
| `[P4]` | 安全指南 | https://owasp.org/www-project-api-security/ | 文档暴露面 |

> **核对状态**：`[P1]`–`[P4]` 为官方/安全链接，**本次未逐页直连复核**；info/tags/字段说明/响应描述/`deprecated`/`openapi_extra`/隐藏端点/自定义 servers 与递归陷阱均为本机实测，`examples/verify.py` 复现 11/11 通过。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 谁在读 `/openapi.json`
- [ ] 三级元信息各自的落点
- [ ] 为什么 `include_in_schema` 不是安全措施
- [ ] 替换 `app.openapi` 为什么要保存原方法
- [ ] 文档漂移的三种来源

**能写出（代码层）**：

- [ ] 应用元信息 + tags
- [ ] 端点 summary/description/responses
- [ ] 字段 description/examples
- [ ] `openapi_extra` 扩展
- [ ] 自定义 servers 且缓存

**能判断（避坑层）**：

- [ ] 看到递归崩溃 → 指出保存原方法
- [ ] 看到无缓存 → 指出重建成本
- [ ] 看到隐藏端点当鉴权 → 指出仍可访问
- [ ] 看到 `openapi_extra` 覆盖核心键 → 指出风险
- [ ] 看到版本不变 → 指出契约不可追

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 11/11
- [ ] `/docs` 里看到标签分组与废弃划线
- [ ] `/openapi.json` 里看到 `servers`

## 9. 下一章衔接

M03（21–26）到此收尾：你现在能控制「数据怎么出去」——模型过滤、状态码、联合结构、响应头、字节级响应、文档契约。

第 27 章进入 M04 `表单与文件`：`Form`、`File`、`UploadFile`、`python-multipart`，从「JSON 世界」切到「表单世界」，第一件事就是加依赖。

本章留下的伏笔：

1. 安全方案注入在第 44 章。
2. 生产关闭 `/docs` 在 M13 部署。
3. 契约测试在第 71 章。
4. 网关与 schema 在 M13。
