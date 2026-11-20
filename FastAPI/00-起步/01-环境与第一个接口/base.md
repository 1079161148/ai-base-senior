# 01 环境与第一个接口 · 完整版（base.md）

> `README.md` 是「30 分钟跑通」；本文件把「FastAPI 是什么、一个请求进来发生了什么、`FastAPI()` 和 `@app.get` 的每个参数、返回值怎么被处理、边界条件、39 条坑」逐条展开。学完这章，你要能说清框架在背后做的 7 件事，而不只是会写 `@app.get`。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12.8 / FastAPI 0.146.0 / Pydantic 2.14.1 / Starlette 1.9.0 / Uvicorn 0.54.0（本机实测） |
| 前置 | `py-base` 的装饰器、类型标注、函数基础 |
| 覆盖范围 | 应用实例、路由声明、请求处理 7 步、返回值序列化、文档三件套、同步与异步、健康检查 |
| 明确不覆盖 | 路径参数（05）、请求体（13）、依赖注入（35）、中间件（50）——本章只立骨架 |
| 学完验收 | 能跑通 `verify.py` 6/6、能解释 404 与 405 的区别、能说清「返回标注写错会 500 而不是被强转」 |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Fn]` `` 指向第 7 节官方链接；标「实测」的是本机 FastAPI 0.146.0 运行结果。

**推荐顺序**：

```text
1 概念（第 1 节）        → FastAPI 到底由哪几块拼起来
2 机制（第 2 节）        → 请求进来的 7 步（重点）
3 API 拆解（第 3 节）    → FastAPI() 与 @app.get 的每个参数
4 边界（第 4 节）        → 尾斜杠、返回标注、HEAD、异常
5 注意事项（第 5 节）    → 40 条错误对照
6 最佳实践（第 6 节）    → 可以直接抄的项目约定
```

**与 README 的分工**：README 让你跑起来，本文件让你讲得出原理。冲突时以本文件为准。

## 1. 概念：FastAPI 由哪几块拼起来

```text
你的代码
  ├── 类型标注（Pydantic 模型）  → 数据校验 + 序列化 + OpenAPI schema
  ├── 装饰器注册的函数            → 路由处理器（endpoint）
  └── FastAPI() 实例              → 装配中心
        ├── Starlette   → ASGI 应用、路由匹配、中间件、WebSocket
        ├── Pydantic v2 → 数据校验与序列化
        └── OpenAPI     → 自动生成的接口契约（/openapi.json）
```

| 层 | 负责 | 你要写的部分 | 依据 |
| --- | --- | --- | --- |
| Uvicorn | 监听端口、HTTP ↔ ASGI 协议转换 | 启动命令 | `[F3]` |
| Starlette | ASGI 应用、路由表、中间件栈、请求/响应对象 | 很少直接碰 | `[F6]` `[F7]` |
| FastAPI | 参数解析、依赖注入、校验、文档生成 | 装饰器 + 类型标注 | `[F1]` `[F2]` |
| Pydantic v2 | 数据校验、类型转换、JSON 序列化 | 模型与标注 | `[F2]` |

| 一句话 | 说明 | 依据 |
| --- | --- | --- |
| ASGI 是「异步版的 WSGI」 | 一个 `(scope, receive, send)` 协程接口，支持 WebSocket 与流式 | `[F7]` |
| FastAPI 不是从零造的 Web 框架 | 它把 Starlette 和 Pydantic 缝在一起，加上了依赖注入与文档生成 | `[F1]` |
| 文档不是额外写的 | 从类型标注与路由声明**推导**出来 | `[F9]` |

> 注意：这决定了一个重要事实——**类型标注在 FastAPI 里是运行时逻辑，不是注释**。你写的 `id: int` 会真的去转换和校验；写错会导致 422 或 500，而不是「不影响运行」。`[F2]`

## 2. 机制：一个请求进来，框架做了 7 件事

以 `GET /health` 为例：

```text
① Uvicorn 收到 TCP 连接，解析 HTTP → 组装 ASGI scope / receive / send
② 调用 app(scope, receive, send) → Starlette 中间件栈（ServerError → 用户中间件 → Exception）
③ Router 按注册顺序匹配 path 与 method → 命中 health 的 route
④ 解析并校验参数（本章无参数，这步几乎空转）
⑤ 调用 handler：同步函数丢进线程池，异步函数直接在事件循环
⑥ serialize_response：按返回标注校验并序列化 → JSONResponse
⑦ 沿中间件栈返回，send 发出响应
```

逐步对照实测：

| 步骤 | 谁在做 | 出错时 | 依据 |
| --- | --- | --- | --- |
| ① | Uvicorn | 端口占用 / 协议错误 | `[F3]` |
| ②③ | Starlette Router | 404（路径不匹配）、405（方法不匹配） | `[F6]` |
| ④ | FastAPI + Pydantic | 422（参数校验失败） | `[F2]` |
| ⑤ | FastAPI | 未捕获异常 → 500 | `[F1]` |
| ⑥ | FastAPI + Pydantic | 返回不符合标注 → 500 `ResponseValidationError` | 实测 |
| ⑦ | Starlette | — | `[F6]` |

### 2.1 第 ③ 步：404 与 405 是两回事

实测：

```text
GET  /not-exist  -> 404 {"detail": "Not Found"}
POST /items      -> 405 {"detail": "Method Not Allowed"}
```

| 状态码 | 含义 | 触发条件 | 依据 |
| --- | --- | --- | --- |
| 404 Not Found | 路径不存在 | 没有任何 route 的 path 匹配 | `[F6]` |
| 405 Method Not Allowed | 路径存在但方法不对 | path 匹配、method 不匹配 | `[F6]` |
| 422 Unprocessable Entity | 参数解析或校验失败 | path 匹配、method 匹配、参数不合法 | `[F2]` |

> 注意：区分这两者能省很多排查时间。「接口 404 了」和「接口 405 了」是完全不同的 bug——前者说明路由没注册或前缀写错，后者说明前端用了错的方法（比如把 `POST` 写成 `PUT`）。`[F6]`

### 2.2 第 ⑤ 步：同步函数跑在线程池

实测 handler 里打印 `threading.current_thread().name`：

```text
SYNC  {'thread': 'AnyIO worker thread', 'is_main': False}
ASYNC {'thread': 'asyncio-portal-203fad38a70', 'is_main': False}
```

| handler 写法 | 执行位置 | 能否并发 | 依据 |
| --- | --- | --- | --- |
| `def`（同步） | AnyIO 线程池（默认 40 个 token） | 受线程池大小限制 | `[F6]` |
| `async def`（异步） | 事件循环线程 | 只要不阻塞就能并发 | `[F1]` |

| 结论 | 说明 | 依据 |
| --- | --- | --- |
| 同步 handler 里写 `time.sleep(5)` | 只阻塞一个线程，其他请求仍能处理 | `[F6]` |
| 异步 handler 里写 `time.sleep(5)` | **阻塞整个事件循环**，所有请求全停 | 第 24 章 |
| 同步 handler 数量 > 线程池大小 | 请求排队，表现为「莫名变慢」 | `[F6]` |

> 注意：这是新手最容易犯的性能错误——`async def` 里调用了阻塞库（`requests`、`time.sleep`、同步数据库驱动），以为写 `async` 就变快了，实际比同步还糟。判断方法：`async def` 里只能 `await` 异步库，其余一律 `await anyio.to_thread.run_sync(...)` 或不要写 `async`。`[F1]`

### 2.3 第 ⑥ 步：返回值怎么被处理

实测四种返回写法：

```text
TYPED    500  'Internal Server Error'
UNTYPED  200  '{"n":1}'
NONE     200  'null'（content-length: 4）
```

| 写法 | FastAPI 行为 | OpenAPI 里的 schema | 依据 |
| --- | --- | --- | --- |
| `-> dict[str, str]` 且返回 `{"n": 1}` | **校验失败 → 500** | `additionalProperties: {type: string}` | 实测 |
| `-> dict` 或不标注 | 原样序列化 | `{}`（空，前端看不到结构） | 实测 |
| `-> None` 且返回 `None` | 返回 `null` | `{}` | 实测 |
| 返回 `Response` 对象 | 跳过序列化，直接用 | 需自己声明 `response_model` | 第 24 章 |

单独验证 Pydantic v2 的类型转换规则：

```python
from pydantic import BaseModel, ValidationError


class StrModel(BaseModel):
    s: str


StrModel(s=1)      # ValidationError: string_type
```

```text
PYDANTIC_STR_INT_ERR string_type
```

| 结论 | 说明 | 依据 |
| --- | --- | --- |
| `str` **不会**把 int 隐式转成 `"1"` | Pydantic v2 的 `str` 类型是严格的 | `[F2]` |
| `int` 会接受 `"1"` 吗？ | 会（lax 模式对数字字符串转换） | `[F2]` |
| 返回标注写错 = 500，不是静默转换 | 这是保护，不是限制 | 实测 |

> 注意：`dict[str, str]` 是**契约**，不是提示。它的价值在于：一旦 handler 返回了不符合契约的数据，服务立刻 500 而不是把错误数据发给前端。对手写文档的系统，这种错误会以「前端拿到 string 却按 number 处理」的形式在两周后爆炸。`[F2]`

## 3. API 逐个拆解

### 3.1 `FastAPI(...)`

| 参数 | 类型 | 默认值 | 作用 | 注意 | 依据 |
| --- | --- | --- | --- | --- | --- |
| `title` | `str` | `"FastAPI"` | 文档标题 | 进 `info.title`，前端可能展示 | `[F5]` |
| `description` | `str` | `""` | 文档描述，支持 Markdown | 会渲染成 HTML | `[F5]` |
| `version` | `str` | `"0.1.0"` | 接口版本 | 与包版本是两回事 | `[F5]` |
| `openapi_url` | `str \| None` | `"/openapi.json"` | 契约地址 | `None` 会连带关掉两个 UI | `[F2]` |
| `docs_url` | `str \| None` | `"/docs"` | Swagger UI | 生产建议关掉或加鉴权 | `[F2]` |
| `redoc_url` | `str \| None` | `"/redoc"` | ReDoc | 同上 | `[F2]` |
| `dependencies` | `Sequence[Depends]` | `[]` | 全局依赖 | 第 39 章 | `[F2]` |
| `lifespan` | 异步上下文管理器 | `None` | 启停钩子 | 第 67 章 | `[F2]` |
| `root_path` | `str` | `""` | 反向代理子路径 | 第 54 章 | `[F2]` |
| `servers` | `list[dict]` | `None` | OpenAPI servers | 多环境时有用 | `[F9]` |
| `swagger_ui_parameters` | `dict` | `None` | Swagger UI 配置 | 如 `deepLinking` | `[F2]` |
| `default_response_class` | `type[Response]` | `JSONResponse` | 默认响应类 | 全局换 ORJSON 时用 | `[F2]` |
| `debug` | `bool` | `False` | 异常时返回堆栈 | **生产必须 False** | `[F1]` |

实测 `docs_url=None, redoc_url=None`：

```text
GET /docs          -> 404
GET /openapi.json  -> 200
```

| 结论 | 说明 |
| --- | --- |
| 关 UI 不影响契约 | `/openapi.json` 仍可访问 |
| 想彻底关掉 | `openapi_url=None` 会同时关掉 `/docs` 与 `/redoc` |

### 3.2 `@app.get(path, ...)`

| 参数 | 类型 | 默认值 | 作用 | 依据 |
| --- | --- | --- | --- | --- |
| `path` | `str` | 必填 | 必须以 `/` 开头 | `[F2]` |
| `response_model` | `type` | 由返回标注推断 | 输出模型（过滤字段） | `[F1]` |
| `status_code` | `int` | `200` | 成功状态码 | `[F2]` |
| `tags` | `list[str \| Enum]` | `None` | 文档分组 | `[F5]` |
| `summary` | `str` | 由函数名生成 | 文档摘要 | `[F5]` |
| `description` | `str` | 由 docstring 生成 | 文档详情 | `[F5]` |
| `deprecated` | `bool` | `False` | 标记废弃 | `[F5]` |
| `include_in_schema` | `bool` | `True` | 是否进文档 | `[F2]` |
| `response_class` | `type[Response]` | `JSONResponse` | 响应类 | `[F2]` |
| `name` | `str` | 函数名 | `url_path_for` 用的路由名 | `[F2]` |
| `operation_id` | `str` | 自动生成 | 生成客户端时的函数名 | `[F9]` |

`path` 的硬规则（实测）：

| 写法 | 结果 |
| --- | --- |
| `"/items"` | ✅ |
| `"items"` | ❌ 启动报 `Path must start with /` |
| `"/items/"` | ✅ 但会与 `"/items"` 产生重定向行为 |
| `"/"` | ✅ 根路径 |

### 3.3 文档三件套

| 地址 | 内容 | 依赖 | 依据 |
| --- | --- | --- | --- |
| `/docs` | Swagger UI，可交互发请求 | CDN 资源 | `[F2]` |
| `/redoc` | ReDoc，只读精美文档 | CDN 资源 | `[F2]` |
| `/openapi.json` | OpenAPI 3.1 契约 | 无 | `[F9]` |

| 实测事实 | 说明 |
| --- | --- |
| 三个地址全部 200 | 默认开启 |
| `/docs` 依赖外网 CDN | 内网/离线环境会白屏，需自托管（`code/agent-lab` 用 `app/static/docs/` 自托管，见第 69 章） | 

### 3.4 启动方式

| 方式 | 命令 | 热重载 | 适用 | 依据 |
| --- | --- | --- | --- | --- |
| 命令行 | `uvicorn main:app --reload` | ✅ | 开发（推荐） | `[F3]` |
| fastapi-cli | `fastapi dev main.py` | ✅ | 开发（更省事） | `[F3]` |
| 代码启动 | `uvicorn.run(app, ...)` | ❌ | 调试、脚本 | `[F3]` |
| 生产 | `uvicorn main:app --workers 4` | ❌ | 生产 | `[F4]` |

| `uvicorn` 常用参数 | 作用 | 依据 |
| --- | --- | --- |
| `--host` | 绑定地址，`0.0.0.0` 才能被外部访问 | `[F3]` |
| `--port` | 端口 | `[F3]` |
| `--reload` | 代码变更自动重启（仅开发） | `[F3]` |
| `--workers N` | 多进程（与 `--reload` 互斥） | `[F4]` |
| `--log-level` | 日志级别 | `[F3]` |
| `--proxy-headers` | 信任 `X-Forwarded-*` | `[F4]` |
| `--root-path` | 反向代理前缀 | `[F4]` |

> 注意：`--reload` 与 `--workers` **互斥**，同时给会报错。`--reload` 会额外起一个监控进程，内存翻倍，生产禁用。`[F3]`

## 4. 边界条件

### 4.1 尾斜杠：307 重定向

实测：

```text
GET /items    -> 200
GET /items/   -> 307  Location: http://testserver/items
```

| 注册路径 | 请求路径 | 行为 | 依据 |
| --- | --- | --- | --- |
| `/items` | `/items` | 200 | `[F6]` |
| `/items` | `/items/` | 307 重定向到 `/items` | `[F6]` |
| `/items/` | `/items` | 307 重定向到 `/items/` | `[F6]` |

| 风险 | 说明 |
| --- | --- |
| 307 会保留方法，POST 被重定向时客户端可能不跟随 | 前端表现为「创建失败但没报错」 |
| 反向代理/网关对 307 处理不一致 | 线上偶发 404 |
| `redirect_slashes=False` 可关闭重定向 | `FastAPI(redirect_slashes=False)` |

### 4.2 HEAD 不自动支持

实测：

```text
HEAD /items -> 405
POST /items -> 405
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `@app.get` **只**注册 GET | 不会隐含 HEAD | `[F6]` |
| 需要 HEAD 就显式声明 | `@app.head("/items")` | `[F6]` |
| 库路由 `app.api_route(path, methods=["GET","HEAD"])` | 一次注册多个方法 | `[F6]` |

> 注意：部分监控系统/CDN 会用 `HEAD` 做探活。如果只写了 `@app.get("/health")`，`HEAD /health` 会返回 405，探活可能被判失败。健康检查接口建议 `@app.api_route("/health", methods=["GET", "HEAD"])`。

### 4.3 未捕获异常：500 是纯文本

实测：

```text
BOOM 500 'Internal Server Error'  content-type: text/plain; charset=utf-8
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 未捕获异常 → 500 | 由 `ServerErrorMiddleware` 兜底 | `[F6]` |
| 响应体是**纯文本**，不是 JSON | 前端按 JSON 解析会二次报错 | 实测 |
| `debug=True` 时会返回堆栈 | **生产必须关**，会泄露源码路径 | `[F1]` |
| `TestClient` 默认会抛出异常 | 与真实运行不一致 | 第 71 章 |

> 注意：「前端说接口报错但拿不到错误信息」通常就是这里——500 的 body 是 `Internal Server Error` 纯文本，`response.json()` 会抛解析错误。统一错误契约（第 34 章）就是解决这个问题的。

### 4.4 `-> None` 的坑

实测：

```text
GET /none -> 200 'null'（content-length 4）
```

| 期望 | 实际 | 正确做法 |
| --- | --- | --- |
| 返回空响应体 | 返回字符串 `null` | 返回 `Response(status_code=204)` |
| 204 No Content | 需要显式声明 | `@app.delete(..., status_code=204)` + `return None` |

> 注意：`204` 按规范**不能有响应体**。`-  ` 返回 `None` 且状态码 200 会得到 `null`；要真正的 204 必须同时设 `status_code=204` 并返回 `Response(status_code=204)`。`[F9]`

### 4.5 OpenAPI schema 的有无

实测：

| 返回标注 | OpenAPI 里的 `responses.200.content` |
| --- | --- |
| `-> dict[str, str]` | `{"application/json": {"schema": {...}}}` |
| `-> dict` / 不写 | `{}`（空对象） |
| `-> None` | `{}` |

| 结论 | 影响 |
| --- | --- |
| 不写返回标注 → 文档里没有响应结构 | 前端只能靠猜，生成客户端会得到 `any` |
| 写标注 → 自动生成 schema | 契约可校验、可生成 TS 类型 |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `app = FastAPI()` 写在函数/`if` 块里 | `Could not import module "main"` | 模块级变量 | `[F2]` |
| 文件名与模块名冲突（`fastapi.py`） | `ImportError` 循环导入 | 不要用库名命名文件 | `[F2]` |
| `@app.get("items")` 少斜杠 | 启动报 `Path must start with /` | `"/items"` | `[F2]` |
| 在错误目录启动 `uvicorn main:app` | `Could not import module "main"` | `cd` 到文件所在目录或用 `--app-dir` | `[F3]` |
| 生产开 `--reload` | 内存翻倍、文件监听占 CPU | 去掉 | `[F3]` |
| `--reload` 与 `--workers` 同时给 | 启动报错 | 二选一 | `[F3]` |
| `host` 写 `127.0.0.1` 放容器里 | 外部访问不通 | `0.0.0.0` | `[F4]` |
| 用 `python main.py` 想要热重载 | 改了代码不生效 | `uvicorn main:app --reload` | `[F3]` |
| 8000 端口被占 | `address already in use` | 换端口或杀进程 | `[F3]` |
| 同步 `def` 里写 `time.sleep(10)` | 占一个线程池槽位 | 改 `async def` + `await asyncio.sleep` | `[F1]` |
| `async def` 里调 `requests.get` | 阻塞事件循环，全站卡住 | `httpx.AsyncClient` 或 `to_thread` | 第 24 章 |
| `async def` 里写 `time.sleep` | 同上，且比同步更糟 | `await asyncio.sleep` | 第 24 章 |
| 返回标注 `dict[str, str]` 但返回 int | **500**（实测） | 标注与实际一致 | 实测 |
| 返回标注 `-> dict` 不写具体类型 | `/docs` 无响应结构 | 写具体模型 | 实测 |
| 返回 `None` 期望 204 | 得到 200 + `null` | `status_code=204` + `Response` | 实测 |
| 期望 HEAD 自动支持 | 405（实测） | 显式 `@app.head` 或 `api_route` | `[F6]` |
| 把 404 当 405 排查 | 查错方向 | 看 `detail` 与 `Allow` 头 | `[F6]` |
| `debug=True` 上生产 | 堆栈泄露路径与变量 | 生产 `False` | `[F1]` |
| 500 时用 `response.json()` 解析 | 前端二次报错（body 是纯文本） | 先看 `content-type` | 实测 |
| 生产保留 `/docs` | 完整接口清单公开 | `docs_url=None` 或加鉴权 | `[F2]` |
| 只关 `docs_url` 就以为关全了 | `/openapi.json` 仍可访问 | `openapi_url=None` | 实测 |
| `/docs` 白屏 | 内网无法加载 CDN | 自托管静态资源 | 第 69 章 |
| 健康检查里查数据库 | 数据库抖动导致实例批量重启 | 存活探针只查自身 | `[F4]` |
| 健康检查不写 HEAD | 探活 405 | `methods=["GET","HEAD"]` | 实测 |
| 健康检查返回业务数据 | 泄露内部信息 | 只返回 `{"status": "ok"}` | `[F4]` |
| 用 `tags` 不写导致文档全挤一起 | 几十个接口一团乱 | 按模块加 `tags` | `[F5]` |
| `summary` 留空靠函数名生成 | 文档出现 `read_root_items_get` | 显式写中文摘要 | `[F5]` |
| 忘记写 docstring | 文档没有说明 | 每个 handler 写 docstring | `[F5]` |
| 路由函数重名 | 后注册的覆盖前者？不会，但 `url_path_for` 混乱 | 函数名唯一 | `[F2]` |
| `include_in_schema=False` 用在正式接口 | 前端不知道有这个接口 | 只用于内部/调试接口 | `[F2]` |
| 直接 `return {"a": datetime.now()}` | `JSON serialization` 错误 | 让 Pydantic 处理或 `jsonable_encoder` | 第 30 章 |
| 用 `print` 做请求日志 | 无级别、无请求 ID、多进程交错 | `logging` | 第 52 章 |
| `@app.get` 装饰器写在 `async def` 上但内部有全局状态 | 并发下竞态 | 避免全局可变状态 | 第 28 章 |
| 单文件堆到 2000 行 | 无法协作 | 拆 `APIRouter` | 第 04、65 章 |
| 启动时连数据库在模块顶层 | 导入即连，测试也会连 | 用 `lifespan` | 第 67 章 |
| 配置硬编码在代码里 | 换环境要改代码 | `pydantic-settings` | 第 66 章 |
| 端口写死在代码里 | 容器里改不了 | 环境变量 | 第 66 章 |
| 响应里直接返回 ORM 对象 | 序列化失败或泄露字段 | `response_model` 过滤 | 第 21 章 |
| 用 `HTTPException(200)` 表示业务错误 | 语义混乱、监控失真 | 用 4xx + 业务码 | 第 31、34 章 |

## 6. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| `app` 放模块级，文件名不用库名 | `main.py` / `app.py` | `[F2]` |
| 每个 handler 写返回标注 | 契约可生成、错误早暴露 | 实测 |
| 每个 handler 写 docstring | 直接变成文档 description | `[F5]` |
| 用 `tags` 分组 | 文档可读性 | `[F5]` |
| 健康检查独立文件 | 与业务代码解耦 | `[F4]` |
| 健康检查极轻 | 不查依赖、返回常量 | `[F4]` |
| 开发 `--reload`，生产 `--workers` | 各取所需 | `[F3]` `[F4]` |
| 生产关 `debug` 与 `/docs` | 安全 | `[F1]` |
| 版本号从单一来源注入 | 别在两处维护 | 第 66 章 |
| 启动命令写进 `Makefile`/`scripts` | 团队一致 | `py-base/30` |
| 先用 `TestClient` 验证再接前端 | 反馈快 | 第 71 章 |

**风格示范**：

```python
"""main.py：应用装配入口，只做三件事——建 app、挂路由、暴露 app。"""

from fastapi import FastAPI

from app.api.v1.router import api_router

# 【为什么】模块级单例：uvicorn 以字符串 "main:app" 定位它
app = FastAPI(
    title="示例服务",
    version="0.1.0",
    # 【注意】关掉文档 UI 不等于关掉契约；两者要分开决策
    docs_url="/docs",
    redoc_url="/redoc",
)

# 【作用】把所有业务路由挂在统一前缀下，main.py 不再关心具体接口
app.include_router(api_router, prefix="/api/v1")


@app.get("/health", tags=["运维"])
def health() -> dict[str, str]:
    """存活探针：只证明进程能响应，不检查下游依赖。"""
    return {"status": "ok"}
```

**命令清单**：

```powershell
uv sync                                              # 装依赖
uv run uvicorn main:app --reload                     # 开发
uv run fastapi dev main.py                           # 开发（fastapi-cli）
uv run uvicorn main:app --host 0.0.0.0 --workers 4   # 生产
uv run python verify.py                              # 自动验收
```

**边界**：

- 本章只用了两个 `def` handler，没有参数、没有模型、没有依赖。第 05 章起才会用到 FastAPI 的解析能力。
- `--workers` 多进程下，模块级可变状态**不共享**；靠内存做缓存/限流的方案在多进程下不成立。
- `/docs` 依赖外网 CDN，离线环境需自托管（`code/agent-lab/app/static/docs/` 就是自托管方案）。

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[F1]` | 官方文档 | https://fastapi.tiangolo.com/zh/ | FastAPI 定位、特性、`debug`、异步 handler |
| `[F2]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/first-steps/ | `FastAPI()`、`@app.get`、`/docs`、`/openapi.json`、返回标注 |
| `[F3]` | 官方文档 | https://fastapi.tiangolo.com/zh/fastapi-cli/ | `fastapi dev`、uvicorn 启动参数、热重载 |
| `[F4]` | 官方文档 | https://fastapi.tiangolo.com/zh/deployment/ | 生产部署、`--workers`、健康检查、`--proxy-headers` |
| `[F5]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/metadata/ | `title`/`version`/`tags`/`summary`/`description` |
| `[F6]` | 官方文档 | https://www.starlette.io/ | Router 匹配、404/405、中间件栈、线程池 |
| `[F7]` | 规范 | https://asgi.readthedocs.io/en/latest/ | ASGI `scope`/`receive`/`send` 三元组 |
| `[F8]` | PEP 官方 | https://peps.python.org/pep-0008/ | 命名、注释写「为什么」 |
| `[F9]` | 规范 | https://spec.openapis.org/oas/latest.html | OpenAPI 3.1、`responses`、`operationId` |

> **核对状态**：`[F8]` 与前序 `py-base` 章节已核对来源一致；`[F1]`–`[F7]`、`[F9]` 按官方文档结构整理，**本次未逐页直连复核**（FastAPI 中文站侧边栏为 JS 渲染，已确认页面存在且路径有效）。文中「实测」为本机 FastAPI 0.146.0 / Pydantic 2.14.1 / Starlette 1.9.0 的真实输出，验收脚本 `examples/verify.py` 可复现 6/6 通过。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] FastAPI、Starlette、Pydantic、Uvicorn 四者的分工
- [ ] ASGI 是什么，为什么能支持 WebSocket
- [ ] 一个请求进来经过的 7 步
- [ ] 404 / 405 / 422 三者的精确区别
- [ ] 同步 handler 与异步 handler 的执行位置差异
- [ ] 返回标注为什么是「运行时契约」而不是注释
- [ ] `/docs`、`/redoc`、`/openapi.json` 的关系
- [ ] `--reload` 为什么不能上生产

**能写出（代码层）**：

- [ ] 一个两接口的最小服务，带 `title`/`version`
- [ ] 用 `-> dict[str, str]` 标注返回值
- [ ] 健康检查接口（GET + HEAD）
- [ ] `TestClient` 版本的验收脚本
- [ ] 从命令行与代码两种方式启动

**能判断（避坑层）**：

- [ ] 看到 `-> dict[str, str]` 返回 int 能预判 500
- [ ] 看到 `async def` 里 `time.sleep` 能指出阻塞事件循环
- [ ] 看到只有 `@app.get` 能指出 HEAD 会 405
- [ ] 看到 `docs_url=None` 能指出 `/openapi.json` 仍可访问
- [ ] 看到 500 的纯文本 body 能指出前端解析会二次报错
- [ ] 看到 `--reload --workers` 同时出现能指出互斥

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 6/6 通过
- [ ] `uvicorn main:app --reload` 启动后 `/docs` 可交互
- [ ] 改一行代码确认热重载生效
- [ ] 用 `docs_url=None` 复现 `/docs` 404 而 `/openapi.json` 200

## 9. 下一章衔接

第 02 章 `开发服务器与热重载`：同一个 app，换三种启动方式，讲清 `--reload` 的监控机制、端口与日志、`fastapi dev` 与 `uvicorn` 的差异、启动失败的五类原因。

本章留下的伏笔：

1. `uvicorn main:app` 里的 `main:app` 到底怎么解析——第 02 章展开。
2. `--workers` 多进程与模块级状态的关系——第 02 章与第 66 章。
3. 本章只有两个无参数接口，参数从哪来——第 03 章起进入 M01。
