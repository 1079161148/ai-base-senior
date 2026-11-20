# FastAPI 学习路线 · 80 章

> 本目录是一套**逐章毕业**的 FastAPI 实战教程：15 个模块、80 章，每章 = 一个最小知识点 + 一个可直接运行的最小案例 + 一份可自查的验收标准。学完一章就掌握一章，不用回头补。
>
> 章节骨架对齐 [FastAPI 官方中文文档](https://fastapi.tiangolo.com/zh/)（教程 51 节 + 高级 35 节），案例形态参考本仓库 `code/agent-lab` 的真实生产结构（`api/v1` 分模块、`core/config`、`core/errors`、`core/security`、`core/sse`、`services` 分层）。

## 目录

- [0. 怎么用这套教程](#0-怎么用这套教程)
- [1. 环境与版本基线](#1-环境与版本基线)
- [2. 学习路径总览](#2-学习路径总览)
- [3. 完整章节清单](#3-完整章节清单)
- [4. 每章的文件结构与内容模板](#4-每章的文件结构与内容模板)
- [5. 每章的毕业验收标准](#5-每章的毕业验收标准)
- [6. 依赖清单（按模块）](#6-依赖清单按模块)
- [7. 阶段验收项目](#7-阶段验收项目)
- [8. 与前序教程的衔接](#8-与前序教程的衔接)

## 0. 怎么用这套教程

**一章 = 一次学习单元**。每章控制在 30–60 分钟：读概念 → 跑案例 → 改案例 → 过验收清单。

| 你的目标 | 学到哪 |
| --- | --- |
| 能写一个能用的 CRUD 接口 | 阶段一（M00–M03，26 章） |
| 能写带登录鉴权的业务接口 | 阶段二（M04–M07，23 章） |
| 能搭生产级项目结构 | 阶段三（M08–M11，21 章） |
| 能测试、调试、部署上线 | 阶段四（M12–M14，10 章） |

**每章都有四个文件**，职责不同：

| 文件 | 读多久 | 内容 |
| --- | --- | --- |
| `README.md` | 5–10 分钟 | 一句话结论、最小可运行代码、跑起来的命令与预期输出、3–5 条最容易踩的坑 |
| `base.md` | 20–30 分钟 | 完整机制、参数逐个拆解、边界条件、注意事项表、最佳实践、官方依据 |
| `examples/main.py` | 5–10 分钟 | **可直接运行**的完整示例，每行关键 API 都有「作用 / 注意 / 为什么」注释 |
| `examples/pyproject.toml` | 1 分钟 | 本章独立项目声明（依赖 + `uv` 配置），让 `examples/` 能单独 `uv run` |

**两条铁律**：

1. **每个案例必须能直接跑**。章内给的命令复制粘贴即可，不依赖上一章的临时文件，不依赖未说明的环境变量。
2. **每章自带验收**。跑不出预期输出 = 没学完，不要进入下一章。

## 1. 环境与版本基线

本章案例在本机实测版本：

| 组件 | 版本 | 说明 |
| --- | --- | --- |
| Python | 3.12.8 | `requires-python = ">=3.12"` |
| FastAPI | 0.146.0 | 教程以 0.11x+ 为准 |
| Pydantic | 2.14.1 | **v2 语法**，不要用 v1 的 `@validator` |
| Starlette | 1.9.0 | FastAPI 的底层框架 |
| Uvicorn | 0.54.0 | ASGI 服务器 |
| pydantic-settings | 2.16.0 | 配置管理 |
| httpx | 0.28.1 | 测试客户端 |

**每章都是独立项目，但共享一份环境**：

- 每个 `examples/` 都有自己的 `pyproject.toml`，`cd` 进去 `uv run` 就能跑，不依赖其他章节；
- 根 `pyproject.toml` 用 `[tool.uv.workspace]` 把这些 `examples/` 注册成 workspace 成员，成员共享根目录的 `uv.lock` 与 `.venv`，因此不会产生 80 份重复依赖；
- 新增章节目录不用改根配置（`members` 用 glob）。

```powershell
cd E:\ai-agent-study\FastAPI
uv sync                                    # 一次装好所有章节的依赖（实测 17 章共用一个 .venv）

cd "00-起步\01-环境与第一个接口\examples"     # 进入任意一章，它自己就是一个项目
uv run uvicorn main:app --reload           # 起服务
uv run python verify.py                    # 跑本章验收
```

**版本说明**：`uv sync` 实际解析到的版本可能比上表略新（本机实测装到 Pydantic 2.14.3 / Starlette 1.10.0），章内标注的版本是首次验证时的版本，行为一致。

**版本约定**：教程只用 3.12 可用的语法（`Annotated`、`X | None`、`match`），不使用 `EmailStr`（需 `email-validator`，见第 6 节标注）。

## 2. 学习路径总览

```text
阶段一 能写接口          阶段二 能写业务            阶段三 能上生产          阶段四 能交付
M00 起步(4)              M04 表单文件(4)            M08 中间件(5)            M12 测试调试(6)
M01 请求参数(8)    →     M05 错误处理(4)     →      M09 数据持久化(5)  →     M13 毕业项目(3)
M02 请求体(8)            M06 依赖注入(9)            M10 实时流式(5)
M03 响应(6)              M07 安全认证(6)            M11 应用结构(6)
```

| 模块 | 章数 | 解决什么问题 | 学完的标志 |
| --- | --- | --- | --- |
| M00 起步 | 4 | 服务怎么跑起来、路由怎么组织 | 能起服务、能看 `/docs`、能拆项目骨架 |
| M01 请求参数 | 8 | 数据从 URL / Header / Cookie 进来 | 能取出并校验任意入参 |
| M02 请求体与模型 | 8 | 数据从 JSON 进来、模型怎么设计 | 能定义请求模型并做完整校验 |
| M03 响应 | 6 | 数据怎么出去、怎么不泄露字段 | 能控制响应结构、状态码、文档 |
| M04 表单文件 | 4 | 文件与表单上传、编码 | 能处理上传并安全存储 |
| M05 错误处理 | 4 | 错误怎么表达、怎么统一契约 | 能设计全局错误契约 |
| M06 依赖注入 | 9 | 跨接口共享逻辑（**官方重点**） | 能用依赖解决鉴权、分页、资源管理 |
| M07 安全认证 | 6 | 登录、令牌、权限 | 能实现 JWT + scopes 的完整鉴权 |
| M08 中间件 | 5 | 请求前后的横切逻辑 | 能做请求 ID、日志、CORS、代理适配 |
| M09 数据持久化 | 5 | 数据库怎么接、事务怎么管 | 能做分层 + 事务 + 分页 |
| M10 实时流式 | 5 | 流式响应、SSE、WebSocket | 能做打字机效果与双向通信 |
| M11 应用结构 | 6 | 大项目怎么拆、配置怎么管 | 能搭出可维护的多模块应用 |
| M12 测试调试 | 6 | 怎么证明它是对的 | 能写接口测试与依赖覆盖 |
| M13 毕业项目 | 3 | 从零到一做出完整服务 | 能独立交付一个生产级 API |

## 3. 完整章节清单

> 「官方对应」列指向 [fastapi.tiangolo.com/zh](https://fastapi.tiangolo.com/zh/) 的具体页面，便于对照原文。
> 「依赖」列标 `—` 表示只用基础依赖即可运行。

### 阶段一：能写接口（M00–M03，26 章）

#### M00 起步（4 章）

| 编号 | 章节 | 核心 API | 案例 | 官方对应 |
| --- | --- | --- | --- | --- |
| 01 | 环境与第一个接口 | `FastAPI()`、`@app.get`、`/docs` | 返回 `{"message": "hello"}` 的最小服务 | `tutorial/first-steps` |
| 02 | 开发服务器与热重载 | `fastapi dev`、`uvicorn --reload` | 改一行代码看自动重启 | `fastapi-cli` |
| 03 | 路由与 HTTP 方法 | `@app.post/put/patch/delete`、`APIRouter` | 一个资源的四个动作 | `tutorial/first-steps` |
| 04 | 项目骨架 | `include_router`、多文件组织 | 单文件拆成 `main.py + api/v1/router.py` | `tutorial/bigger-applications` |

#### M01 请求参数（8 章）

| 编号 | 章节 | 核心 API | 案例 | 官方对应 |
| --- | --- | --- | --- | --- |
| 05 | 路径参数 | `{item_id}`、类型自动转换 | `/items/{id}` + 非法 id 报 422 | `tutorial/path-params` |
| 06 | 路径参数校验 | `Path(gt/le/min_length/pattern)` | `/items/{id}` 限 1–100 | `tutorial/path-params-numeric-validations` |
| 07 | 查询参数 | 默认值、`Optional`、`list[str]` | `/search?q=x&tags=a&tags=b` | `tutorial/query-params` |
| 08 | 查询参数校验 | `Query(ge/le/pattern/alias/deprecated)` | 分页 `?limit=10&offset=0` 限范围 | `tutorial/query-params-str-validations` |
| 09 | 查询参数模型 | `Annotated[Model, Query()]` | 把 4 个查询参数收成一个模型 | `tutorial/query-param-models` |
| 10 | Cookie 参数 | `Cookie()`、`set_cookie` | 读取并写入会话标记 | `tutorial/cookie-params` |
| 11 | Header 参数 | `Header(convert_underscores)`、`X-Token` | 读取自定义头与 `user-agent` | `tutorial/header-params` |
| 12 | 参数总表 | 四类参数对照、`Request` 直取 | 同一接口同时收路径/查询/头/Cookie | `tutorial/using-request-directly` |

#### M02 请求体与模型（8 章）

| 编号 | 章节 | 核心 API | 案例 | 官方对应 |
| --- | --- | --- | --- | --- |
| 13 | 请求体基础 | Pydantic 模型 + `POST` | 创建商品，自动生成 schema | `tutorial/body` |
| 14 | Field 字段约束 | `Field(ge/le/min_length/pattern/examples)` | 商品名长度、价格范围 | `tutorial/body-fields` |
| 15 | 嵌套模型 | 模型套模型、`list[Item]` | 订单包含多个商品条目 | `tutorial/body-nested-models` |
| 16 | 多参数与 embed | 路径+查询+body 混用、`Body(embed=True)` | 创建时带来源与标签 | `tutorial/body-multiple-params` |
| 17 | 特殊类型 | `UUID`、`Decimal`、`datetime`、`HttpUrl` | 订单号用 UUID、金额用 Decimal | `tutorial/extra-data-types` |
| 18 | 局部更新 | `PATCH` + `exclude_unset=True` | 只改传来的字段 | `tutorial/body-updates` |
| 19 | 模型复用与继承 | 基类 + 创建/更新/输出三件套、`extra="forbid"` | 一个实体的模型分层 | `tutorial/body-nested-models` |
| 20 | 校验器与错误定位 | `field_validator`、`model_validator`、422 结构 | 密码与确认密码一致校验 | `tutorial/body`（+ Pydantic v2） |

#### M03 响应（6 章）

| 编号 | 章节 | 核心 API | 案例 | 官方对应 |
| --- | --- | --- | --- | --- |
| 21 | response_model 与字段过滤 | `response_model`、`model_config` | 输出不含 `password` | `tutorial/response-model` |
| 22 | 响应状态码 | `status_code`、`status.HTTP_201_CREATED` | 创建返回 201、删除返回 204 | `tutorial/response-status-code` |
| 23 | 多响应模型 | `Union[A, B]`、`list[Model]` | 列表接口与详情接口共用模型 | `tutorial/extra-models` |
| 24 | 直接返回 Response | `JSONResponse`、`PlainTextResponse` | 手动控制响应体与头 | `advanced/response-directly` |
| 25 | 响应 Cookie 与 Header | `Response` 参数、`set_cookie` | 登录后种 Cookie + 自定义头 | `advanced/response-cookies` |
| 26 | 文档完善 | `summary/description/tags/deprecated`、`additional_responses` | 让 `/docs` 可直接对外 | `tutorial/path-operation-configuration` |

### 阶段二：能写业务（M04–M07，23 章）

#### M04 表单、文件与编码（4 章）

| 编号 | 章节 | 核心 API | 案例 | 依赖 | 官方对应 |
| --- | --- | --- | --- | --- | --- |
| 27 | 表单数据 | `Form()` | 提交用户名密码（非 JSON） | `python-multipart` | `tutorial/request-forms` |
| 28 | 文件上传 | `File()`、`UploadFile` | 上传文本文件并返回大小 | `python-multipart` | `tutorial/request-files` |
| 29 | 表单 + 文件组合 | `list[UploadFile]`、混合字段 | 多文件上传 + 附件说明 | `python-multipart` | `tutorial/request-forms-and-files` |
| 30 | jsonable_encoder | `jsonable_encoder`、自定义编码 | 把 `datetime`/`Decimal`/ORM 对象转 JSON | — | `tutorial/encoder` |

#### M05 错误处理（4 章）

| 编号 | 章节 | 核心 API | 案例 | 官方对应 |
| --- | --- | --- | --- | --- |
| 31 | HTTPException | `HTTPException(status_code, detail, headers)` | 资源不存在 404、未登录 401 | `tutorial/handling-errors` |
| 32 | 自定义异常与处理器 | `@app.exception_handler` | 业务异常 `NotFoundError` → 404 | `tutorial/handling-errors` |
| 33 | 校验错误定制 | `RequestValidationError`、`exc.errors()` | 把 422 改成可读结构 | `tutorial/handling-errors` |
| 34 | 统一错误契约 | 全局兜底 + `trace_id` | `{code, message, trace_id}` 全站一致 | `tutorial/handling-errors` |

#### M06 依赖注入（9 章，官方重点）

| 编号 | 章节 | 核心 API | 案例 | 官方对应 |
| --- | --- | --- | --- | --- |
| 35 | 第一个依赖项 | `Depends(func)` | 共享分页参数函数 | `tutorial/dependencies` |
| 36 | 类依赖与带参依赖 | `__call__`、`Depends(make_dep(x))` | 可配置的限流器依赖 | `tutorial/dependencies/classes-as-dependencies` |
| 37 | 子依赖与缓存 | 依赖树、`use_cache=False` | 用户 → 权限 → 角色三层 | `tutorial/dependencies/sub-dependencies` |
| 38 | Annotated 共享依赖 | `Annotated[T, Depends(...)]`、`type XDep` | 全项目复用一个依赖别名 | `tutorial/dependencies` |
| 39 | 装饰器与全局依赖 | `dependencies=[Depends(...)]`、`FastAPI(dependencies=[...])` | 给一组路由统一加鉴权 | `tutorial/dependencies/dependencies-in-path-operation-decorators` / `global-dependencies` |
| 40 | yield 依赖 | `yield` + `finally` | 数据库会话自动关闭 | `tutorial/dependencies/dependencies-with-yield` |
| 41 | 依赖覆盖 | `app.dependency_overrides` | 测试里替换真实数据库 | `advanced/testing-dependencies` |
| 42 | 实战：分页依赖 | `PageParams` + `Page[T]` | 任意列表接口统一分页 | `tutorial/dependencies` |
| 43 | 实战：鉴权与多租户 | 依赖链 + `Request.state` | 从 token 解析用户并隔离租户 | `tutorial/dependencies` |

#### M07 安全认证（6 章）

| 编号 | 章节 | 核心 API | 案例 | 依赖 | 官方对应 |
| --- | --- | --- | --- | --- | --- |
| 44 | 安全总览 | `Security`、`securitySchemes` | `/docs` 出现 Authorize 按钮 | — | `tutorial/security` |
| 45 | OAuth2 密码流 | `OAuth2PasswordBearer`、`OAuth2PasswordRequestForm` | `/token` 换 token | `python-multipart` | `tutorial/security/first-steps` / `simple-oauth2` |
| 46 | 获取当前用户 | `get_current_user` 依赖 | 受保护接口返回「你好，xx」 | — | `tutorial/security/get-current-user` |
| 47 | JWT 实现 | `hmac`+`hashlib` 手写 HS256（生产用 PyJWT） | 签发带 `exp` 的 token 并校验 | 可选 `PyJWT` | `tutorial/security/oauth2-jwt` |
| 48 | 作用域授权 | `SecurityScopes`、`scopes` | 普通用户 vs 管理员 | — | `advanced/security/oauth2-scopes` |
| 49 | API Key 与 Basic | `APIKeyHeader`、`HTTPBasic` | 机器对机器调用的两种姿势 | — | `advanced/security/http-basic-auth` |

### 阶段三：能上生产（M08–M11，21 章）

#### M08 中间件与横切（5 章）

| 编号 | 章节 | 核心 API | 案例 | 官方对应 |
| --- | --- | --- | --- | --- |
| 50 | 中间件基础 | `@app.middleware("http")`、`call_next` | 记录每个请求耗时 | `tutorial/middleware` |
| 51 | CORS | `CORSMiddleware` | 前端跨域调用 | `tutorial/cors` |
| 52 | 请求上下文与日志 | `contextvars`、请求 ID | 全链路 `trace_id` 贯穿日志 | `advanced/middleware` |
| 53 | 性能中间件 | `GZipMiddleware`、`TrustedHostMiddleware` | 压缩响应 + 限制 Host | `advanced/middleware` |
| 54 | 反向代理适配 | `--root-path`、`X-Forwarded-*` | Nginx 后面 `/api` 前缀正常 | `advanced/behind-a-proxy` |

#### M09 数据持久化（5 章）

| 编号 | 章节 | 核心 API | 案例 | 依赖 | 官方对应 |
| --- | --- | --- | --- | --- | --- |
| 55 | 数据库连接与生命周期 | `lifespan` + 连接 | 启动建连接、关闭释放 | `sqlite3`（标准库） | `tutorial/sql-databases` |
| 56 | 仓储层分层 | repository/service/router | 路由不写 SQL | — | `tutorial/sql-databases` |
| 57 | 事务边界 | `yield` 依赖 + commit/rollback | 出错自动回滚 | — | `tutorial/dependencies/dependencies-with-yield` |
| 58 | 分页与查询规范 | 偏移 vs 游标、索引意识 | 百万行分页不卡 | — | `tutorial/sql-databases` |
| 59 | 异步数据库陷阱 | 连接池、N+1、阻塞调用 | 用 `to_thread` 隔离阻塞 | `aiosqlite`（可选） | `advanced/async-tests` |

#### M10 实时与流式（5 章）

| 编号 | 章节 | 核心 API | 案例 | 官方对应 |
| --- | --- | --- | --- | --- |
| 60 | StreamingResponse | `StreamingResponse`、生成器 | 大文件边生成边下载 | `advanced/stream-data` |
| 61 | JSON Lines 流 | `application/jsonl` | 逐行返回搜索结果 | `tutorial/stream-json-lines` |
| 62 | SSE | `text/event-stream` | 打字机效果（不用 WebSocket） | `tutorial/server-sent-events` |
| 63 | WebSocket 基础 | `@app.websocket`、`accept/receive/send` | 回声服务 + 心跳 | `advanced/websockets` |
| 64 | WebSocket 鉴权 | 首帧鉴权、断连清理 | 未登录不能连 | `advanced/websockets` |

#### M11 应用结构与运营（6 章）

| 编号 | 章节 | 核心 API | 案例 | 官方对应 |
| --- | --- | --- | --- | --- |
| 65 | 大型应用拆分 | `APIRouter` 树、`prefix/tags` | 3 个模块组装成一个应用 | `tutorial/bigger-applications` |
| 66 | 配置管理 | `pydantic-settings`、`.env` | 开发/生产配置切换、密钥不入库 | `advanced/settings` |
| 67 | lifespan 生命周期 | `@asynccontextmanager` | 启动预热 + 关闭清理 | `advanced/events` |
| 68 | 子应用与静态资源 | `mount`、`StaticFiles` | 同时提供 API 与前端页面 | `advanced/sub-applications` |
| 69 | OpenAPI 定制 | `title/servers`、自定义 `openapi()` | 文档可直接交给前端 | `tutorial/metadata` |
| 70 | BackgroundTasks | `BackgroundTasks` | 响应后发邮件 | `tutorial/background-tasks` |

### 阶段四：能交付（M12–M14，10 章）

#### M12 测试与调试（6 章）

| 编号 | 章节 | 核心 API | 案例 | 依赖 | 官方对应 |
| --- | --- | --- | --- | --- | --- |
| 71 | TestClient 基础 | `TestClient` | 三层测试（成功/404/422） | `pytest` | `tutorial/testing` |
| 72 | 异步测试 | `httpx.AsyncClient` + `ASGITransport` | 用 `pytest-asyncio` 跑异步接口 | `pytest-asyncio` | `advanced/async-tests` |
| 73 | 依赖覆盖与测试库 | `dependency_overrides` | 真实路由 + 假数据库 | `pytest` | `advanced/testing-dependencies` |
| 74 | 测试 WebSocket 与事件 | `websocket_connect`、lifespan | 连上、发消息、断言回复 | `pytest` | `advanced/testing-websockets` / `testing-events` |
| 75 | 调试与可观测 | 日志、`/openapi.json` 快照、断点 | 一行配置打出请求全貌 | — | `tutorial/debugging` |
| 76 | 部署与交付 | `uvicorn` 参数、容器、健康检查 | 优雅退出 + 健康探针 | — | `deployment` |

#### M13 毕业项目（3 章）

| 编号 | 章节 | 内容 | 验收 |
| --- | --- | --- | --- |
| 77 | 毕业项目（一）：业务实现 | 待办服务：CRUD + 分页 + 鉴权 + 错误契约 | 全部接口可用，`/docs` 完整 |
| 78 | 毕业项目（二）：生产化改造 | 配置、日志、中间件、事务、依赖注入重构 | 无硬编码、无裸 `except`、有测试 |
| 79 | 毕业项目（三）：验收与复盘 | 逐项自查清单、性能与安全复核 | 79 条验收全过 |

#### M14 工程化实战（1 章）

| 编号 | 章节 | 内容 | 验收 |
| --- | --- | --- | --- |
| 80 | 从 0 到 1 搭工程化项目 | 12 块积木：骨架 → 配置 → 迁移 → 数据 → 契约 → 仓储 → 服务 → 依赖 → 错误 → 路由 → 装配 → 交付 | 12/12 积木验收 + 架构守卫 |

## 4. 每章的文件结构与内容模板

```text
FastAPI/
├── README.md                    ← 本文件（路线图）
├── pyproject.toml               ← workspace 根：登记所有章节、共享一个 .venv
├── 00-起步/
│   ├── 01-环境与第一个接口/
│   │   ├── README.md            ← 快速版（5–10 分钟）
│   │   ├── base.md              ← 完整版（20–30 分钟）
│   │   └── examples/            ← 本章独立项目（可单独 cd 进来 uv run）
│   │       ├── main.py          ← 可直接运行
│   │       ├── verify.py        ← 自动验收，输出「结果：N/N 通过」
│   │       └── pyproject.toml   ← 本章依赖声明
│   └── 02-开发服务器与热重载/
│       └── ...
├── 01-请求参数/
├── 02-请求体与模型/
├── 03-响应/
├── 04-表单文件/
├── 05-错误处理/
├── 06-依赖注入/
├── 07-安全认证/
├── 08-中间件/
├── 09-数据持久化/
├── 10-实时流式/
├── 11-应用结构/
├── 12-测试调试/
├── 13-毕业项目/
└── 14-工程化实战/
```

### 4.1 `README.md` 固定六段

| 段落 | 写什么 | 篇幅 |
| --- | --- | --- |
| 一句话结论 | 本章解决什么、学完能做什么 | ≤ 3 行 |
| 最小可运行案例 | 完整代码（不要「省略部分代码」） | 20–60 行 |
| 怎么跑 | 命令 + 预期输出 + 出错的排查 | ≤ 10 行 |
| 核心 API 速查 | 用到的每个函数/类：作用 + 必填参数 + 默认值 | 表格 |
| 最容易踩的坑 | 3–5 条，每条给「错误写法 → 现象 → 正确写法」 | 表格 |
| 毕业自查 | 5–8 条勾选项 + 2 道动手改案例的题 | 清单 |

### 4.2 `base.md` 固定结构

```text
0. 怎么用这份文件（依据约定、推荐顺序、与 README 分工）
1. 概念：这个知识点在什么位置、解决什么问题
2. 机制：请求进来 → 框架做什么 → 你写的代码什么时候被调用
3. API 逐个拆解（参数表：名称/类型/默认值/作用/注意）
4. 边界条件（空值、超限、并发、编码、版本差异）
5. 注意事项对照表（40 条左右：错误写法 → 现象 → 正确写法 → 依据）
6. 最佳实践与编码建议（含风格示范代码）
7. 依据索引（官方文档链接 + 核对状态）
8. 毕业自查清单（概念层 / 代码层 / 避坑层 / 可运行层）
9. 下一章衔接
```

**硬性要求**：每章 `examples/` 必须带 `pyproject.toml`，否则它就不是「可独立运行的项目」。模板：

```toml
[project]
name = "chNN-英文短名"
version = "0.1.0"
description = "第 NN 章 · 标题：可独立运行的示例项目"
requires-python = ">=3.12"
dependencies = ["fastapi>=0.146.0", "uvicorn[standard]>=0.54.0", "pydantic>=2.14.0"]

[tool.uv]
package = false

[dependency-groups]
dev = ["httpx>=0.28.1"]   # TestClient 需要
```

用到额外依赖的章节（如表单文件的 `python-multipart`、认证的 `pyjwt`）只在该章 `dependencies` 里加，不影响其他章节。

### 4.3 `examples/main.py` 注释规范

每个关键行都要有三类注释之一：

```python
from fastapi import FastAPI

# 【作用】创建应用实例；所有路由、中间件、异常处理器都挂在它上面
# 【注意】`title`/`version` 会直接显示在 /docs 页面，不写就是默认值
# 【为什么】模块级单例，供 uvicorn 以 "main:app" 方式加载
app = FastAPI(title="示例服务", version="0.1.0")


@app.get("/health")
def health() -> dict[str, str]:
    """健康检查：K8s / 负载均衡探活用。"""
    # 【作用】直接返回 dict，FastAPI 自动序列化为 JSON 并加 Content-Type
    return {"status": "ok"}


if __name__ == "__main__":
    # 【作用】本地直接运行 `python main.py` 也能起服务
    # 【注意】生产不要用 reload=True；它只适合开发期
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
```

## 5. 每章的毕业验收标准

一章算「毕业」，要同时满足 4 类条件：

| 层次 | 验收方式 | 不合格的表现 |
| --- | --- | --- |
| 能跑 | 按 README 命令启动，输出与预期完全一致 | 要改代码才能跑、要装没提到的依赖 |
| 能讲 | 不看资料说清「这个参数不写会怎样」 | 只会背 API 名，说不出默认行为 |
| 能改 | 完成 2 道动手题（改需求不改框架） | 改一行就报错，找不到改哪里 |
| 能辨 | 给出 3 个错误写法能立刻说出后果 | 认为「能跑就等于对」 |

**统一验收命令**（在任意一章的 `examples/` 目录内，都能用）：

```powershell
cd "00-起步\01-环境与第一个接口\examples"
uv run python verify.py                  # 每章必备：输出「结果：N/N 通过」，退出码 0 才算毕业
uv run uvicorn main:app --reload         # 起服务，打开 /docs 手动验证
uv run python -m pytest -q               # 有 pytest 用例的章节（M12）
```

> 验收脚本用 `fastapi.testclient.TestClient` 内存调用，不占端口、不需要先起服务，退出码非 0 表示有断言失败。

## 6. 依赖清单（按模块）

基础依赖（M00–M03、M05–M06 全部章节只需这些）：

```toml
[project]
dependencies = [
    "fastapi>=0.146.0",
    "uvicorn[standard]>=0.54.0",
    "pydantic>=2.14.0",
    "pydantic-settings>=2.16.0",
    "httpx>=0.28.1",
]
```

按模块追加：

| 模块 | 追加依赖 | 原因 | 无法安装时的替代 |
| --- | --- | --- | --- |
| M04 表单文件 | `python-multipart` | `Form`/`File` 解析必需，缺失会报 `Form data requires "python-multipart"` | 无（必须装） |
| M07 JWT | `PyJWT`（可选） | 生产级 JWT | **第 47 章用标准库 `hmac`+`hashlib` 手写 HS256，零依赖可跑** |
| M07 密码哈希 | `passlib[bcrypt]`（可选） | 生产级密码存储 | 第 47 章用标准库 `hashlib.scrypt` 替代 |
| M09 数据库 | `aiosqlite`（可选） | 异步 SQLite | **第 55–58 章用标准库 `sqlite3` + `to_thread`** |
| M12 测试 | `pytest`、`pytest-asyncio` | 测试框架 | 无（必须装） |

**设计原则**：能用标准库完成的章节，一律不引入第三方依赖，保证「克隆仓库就能跑」。生产替代方案在正文里给出对比。

安装命令：

```powershell
uv sync --all-extras        # 一次装全
# 或按需
uv add python-multipart pytest pytest-asyncio
```

## 7. 阶段验收项目

每个阶段结束做一个能跑的小项目，把该阶段所有知识点串起来。

| 阶段 | 验收项目 | 涉及章节 | 通过标准 |
| --- | --- | --- | --- |
| 一 | 商品目录 API | 01–26 | 列表（分页/过滤/排序）、详情、创建、局部更新、删除；输出不含内部字段；`/docs` 可交互 |
| 二 | 带登录的待办 API | 27–49 | 注册/登录/刷新 token；每人只能看自己的待办；管理员可看全部；非法 token 返回 401 而非 500 |
| 三 | 生产化改造 | 50–70 | 有请求 ID 与结构化日志；CORS 只放行白名单；数据库事务正确回滚；大列表用流式返回 |
| 四 | 交付验收 | 71–80 | 单元 + 接口测试覆盖核心路径；依赖覆盖可用；容器健康检查通过；OpenAPI 快照稳定；工程骨架分层不违规 |

## 8. 与前序教程的衔接

本目录依赖 `py-base` 已建立的基础，不再重复讲解：

| 前置知识 | 出处 | 在 FastAPI 里的用途 |
| --- | --- | --- |
| 函数、装饰器、闭包 | `py-base/01-函数与作用域`、`03-…/13-装饰器` | 路由装饰器、依赖注入的实现原理 |
| 类、继承、`__call__` | `py-base/02-面向对象基础`、`11-可调用对象` | 类依赖、Pydantic 模型 |
| 类型标注、`Annotated` | `py-base/05-…/20-类型标注` | 所有参数声明的基石 |
| 异步 `async/await` | `py-base/06-并发与异步/24–28` | `async def` 路由、异步依赖、连接池 |
| 异常与上下文管理器 | `py-base/04-…/16`、`18` | `HTTPException`、`yield` 依赖 |
| 环境与依赖管理 | `py-base/07-…/29–30` | `pyproject.toml`、`uv`、构建发布 |
| 断点调试 | `py-base/07-…/32` | 调试路由与依赖 |

**本教程的定位**：`py-base` 教你语言，本目录教你**用语言构建一个能上线的 HTTP 服务**。每章都会指出「这个 API 背后用到了 py-base 的哪个知识点」，但不重复展开。

未覆盖范围（明确不含）：ORM 深度（SQLAlchemy 全量）、消息队列、GraphQL、微服务治理、K8s 编排细节。这些在 M09/M11 只给边界说明与延伸阅读。
