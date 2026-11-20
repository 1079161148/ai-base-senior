# 50 中间件基础 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「中间件栈怎么构建、`call_next` 到底做了什么、为什么后注册的在外层、异常为什么抓不到 `HTTPException`、中间件与依赖怎么分工」拆开。学完这章，你要能判断一段横切逻辑该放中间件还是依赖。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Starlette（本机实测） |
| 前置 | 第 39 章（全局依赖）、第 12 章（响应） |
| 覆盖范围 | `@app.middleware`、`call_next`、洋葱顺序、`BaseHTTPMiddleware`、异常边界、`request.state` |
| 明确不覆盖 | CORS（51）、请求 ID 与日志（52）、GZip（53）、纯 ASGI 中间件手写 |
| 学完验收 | 能跑通 `verify.py` 14/14、能画出中间件栈、能说清三条边界 |

## 0. 怎么用这份文件

**依据约定**：`` `[Mn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 中间件 vs 依赖
2 机制（第 2 节）    → 栈构建与洋葱
3 API（第 3 节）     → 装饰器、子类、call_next
4 边界（第 4 节）    → 404/异常/body/启动后
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 该放哪
```

## 1. 概念：中间件是「路由之外」，依赖是「路由之内」

| 维度 | 中间件 | 依赖 |
| --- | --- | --- |
| 位置 | 路由之外（包住整个 app）| 路由之内 |
| 404 是否经过 | **是** | 否（实测）|
| `/docs` 是否经过 | **是** | 否（实测）|
| 能否拿到 `Request` | 是 | 是 |
| 能否拿到路径参数 | 否（路由未匹配）| 是 |
| 能否参与 openapi | 否 | 是 |
| 适合 | 耗时、日志、压缩、CORS、安全头 | 鉴权、分页、租户 |

一句话：**中间件不知道你要访问哪个端点；依赖知道**。

## 2. 机制：栈是「列表倒序包装」

```python
# 注册顺序
app.middleware("http")(A)   # A
app.middleware("http")(B)   # B
app.middleware("http")(C)   # C

# 构建（简化）
middleware = [ServerError] + [C, B, A] + [Exception]
for cls in reversed(middleware):   # Exception → A → B → C → ServerError
    app = cls(app)
# 最终：ServerError(C(B(A(Exception(router)))))
```

实测结果：

```text
outer:before → middle:before → inner:before → 端点
→ inner:after → middle:after → outer:after
```

`outer` 是最后注册的，所以最先执行。

## 3. API 逐个拆解

### 3.1 装饰器写法

```python
@app.middleware("http")
async def fn(request: Request, call_next) -> Response:
    ...
    return response
```

`app.middleware("http")` 返回装饰器，内部调用 `add_middleware(BaseHTTPMiddleware, dispatch=fn)`。

### 3.2 子类写法

```python
class X(BaseHTTPMiddleware):
    def __init__(self, app, **cfg): super().__init__(app); ...
    async def dispatch(self, request, call_next): ...
```

| 差异 | 装饰器 | 子类 |
| --- | --- | --- |
| 传配置 | 闭包/全局 | `add_middleware(X, **cfg)` |
| 复用 | 拷贝函数 | 直接 import |
| 类型提示 | 松散 | 明确 |

### 3.3 `call_next`

| 行为 | 说明 |
| --- | --- |
| 是 async callable | `response = await call_next(request)` |
| 触发下游 | 调用时路由才执行 |
| 返回 `Response` | 可以改 header、状态码 |
| 不能改 body | 已经在流式发送 |

## 4. 边界条件

### 4.1 覆盖范围（实测）

| 请求 | 中间件是否生效 |
| --- | --- |
| `/ping` 200 | ✅ |
| `/nope` 404 | ✅（带 `X-Order`）|
| `/docs` | ✅ |
| `/openapi.json` | ✅ |
| 422 | ✅ |
| 全局限流拒绝 | ✅（因为限流若在中间件里）|

### 4.2 异常边界（实测）

| 抛出 | 中间件 `except` | 最终状态码 |
| --- | --- | --- |
| `HTTPException(418)` | ✗ 抓不到 | 418 |
| `RuntimeError` | ✅ 抓到 | 503（示例自定义）|

原因：`HTTPException` 在内层 `ExceptionMiddleware` 被转成响应，不会抛到中间件。

### 4.3 异常跳过 `after`（实测）

`/boom` 的 503 响应**没有** `X-Order`——因为 `outer` 的 `call_next` 抛了，`after` 没执行。

推论：**不要指望「after 一定执行」做资源清理**。清理放 `yield` 依赖或 `try/finally`。

### 4.4 启动后不能加（实测）

```text
RuntimeError: Cannot add middleware after an application has started
```

中间件栈在第一次请求时构建并缓存，之后不可变。

### 4.5 路径重写（实测，慎用）

在中间件里改 `request.scope["path"]`，路由**会**按新路径匹配（`/alias` → `/ping` 返回 200）。原因：路由匹配发生在 `call_next` 内部。

生产该用网关或 `APIRouter(prefix=...)`，不要在中间件里改路径。

### 4.6 `request.state` 的生命周期

`request.state` 是每个请求独立的 `State` 对象。中间件写、依赖读、端点读都一致；但**不能跨请求**（要跨请求用 `contextvars`，第 52 章）。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 忘记 `return response` | 500 或空响应 | 每层都返回 | 实测 |
| 以为先注册在外层 | 顺序全反 | 后注册在外层 | 实测 |
| `except Exception` 想抓 `HTTPException` | 抓不到（实测 418 原样）| 用 `exception_handler` | 实测 |
| 靠 after 做清理 | 异常时跳过（实测无 `X-Order`）| `yield` 依赖 / `finally` | 实测 |
| 中间件里 `await request.body()` | 下游拿不到 body | 用 `request.state` 传解析结果 | `[M1]` |
| `call_next` 后改 `response.body` | 无效 | 改 header/状态码 | `[M1]` |
| 用中间件做鉴权 | `/docs` 被拦、难测试 | 用 `Security` 依赖 | 第 44 章 |
| 中间件里存全局 dict | 并发串数据 | `request.state`/contextvars | `[M2]` |
| 启动后 `add_middleware` | `RuntimeError` | 模块加载期注册 | 实测 |
| 中间件里 `raise HTTPException` | 500（无法被自己捕获）| 返回 `JSONResponse` | `[M1]` |
| 用中间件做参数校验 | 拿不到 schema | 用 Pydantic/依赖 | 第 31 章 |
| 顺序无注释 | 排错困难 | 注明「最外/最内」 | 规则 |
| 中间件里改 `scope["path"]` | 路由错乱、难调试 | 用 prefix/网关 | 实测 |
| 在中间件里 `print` 全量 header | 泄露 token | 脱敏/只记 id | 规则 |
| 用 `BaseHTTPMiddleware` 包 `StreamingResponse` | 背景任务/流式行为异常 | 需要时用纯 ASGI | `[M3]` |
| 中间件里再 `await` 长时间任务 | 拖慢所有请求 | 放后台任务 | 第 21 章 |
| 每个中间件都解析 JSON | CPU 浪费 | 只解析一次并共享 | `[M2]` |
| 只测 200 路径 | 404/异常路径未覆盖 | 三条都测 | 第 71 章 |
| `call_next` 后改 `response.status_code` 想换 body | 状态码变了 body 没变 | 返回新的 `JSONResponse` | `[M1]` |

## 6. 最佳实践与编码建议

### 6.1 选择树

```text
需要拿到路径参数 / 请求体模型？
  ├─ 是 → 依赖
  └─ 否 → 需要覆盖 404 / 静态 / /docs？
          ├─ 是 → 中间件
          └─ 否 → 依赖优先
```

| 需求 | 放哪 |
| --- | --- |
| 耗时统计 | 中间件 |
| 请求 ID | 中间件 + contextvars（52）|
| 安全响应头 | 中间件 |
| 鉴权/限流（按用户）| 依赖 |
| 全局 IP 限流 | 中间件 |
| CORS | `CORSMiddleware`（51）|
| 压缩 | `GZipMiddleware`（53）|

### 6.2 写法约定

```python
# 层级从内到外，注释标清楚
@app.middleware("http")      # 最内：只做 header
async def inner(request, call_next): ...

@app.middleware("http")      # 最外：异常兜底
async def catch_errors(request, call_next): ...
```

| 建议 | 说明 |
| --- | --- |
| 最外层放异常兜底 | 能包住全部 |
| 最内层放轻量逻辑 | 减少嵌套影响 |
| 用子类承载配置 | 可复用 |
| 中间件不写业务 | 只做横切 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[M1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/middleware/ | 中间件写法 |
| `[M2]` | 官方文档 | https://www.starlette.io/middleware/ | 中间件顺序与 `BaseHTTPMiddleware` |
| `[M3]` | 源码 | https://github.com/encode/starlette/blob/master/starlette/middleware/base.py | `_StreamingResponse` 语义 |

> **核对状态**：`[M1]`–`[M3]` 为官方文档/源码链接，**本次未逐页直连复核**；洋葱顺序、后注册在外层、404/`/docs`/`/openapi.json`/422 全部经过、`HTTPException` 不捕获、异常跳过 after、`RuntimeError`、路径重写生效、全局依赖不覆盖 404 均为本机实测，`examples/verify.py` 复现 14/14 通过。`await request.body()` 导致下游失流、`StreamingResponse` 背景任务行为**未自动化验证**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 中间件与依赖的覆盖范围差异
- [ ] 洋葱顺序与注册顺序的关系
- [ ] `call_next` 做了三件事
- [ ] `HTTPException` 为什么不进中间件
- [ ] 为什么 after 不能被依赖做清理

**能写出（代码层）**：

- [ ] 装饰器版耗时中间件
- [ ] 子类版带配置中间件
- [ ] 异常兜底返回 `JSONResponse`
- [ ] `request.state` 跨层传值

**能判断（避坑层）**：

- [ ] 看到中间件做鉴权 → 指出 `/docs` 也被拦
- [ ] 看到 after 里 `close()` → 指出异常跳过
- [ ] 看到中间件读 body → 指出下游会空
- [ ] 看到启动后 add → 指出 RuntimeError
- [ ] 看到顺序无注释 → 指出排错成本

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 14/14
- [ ] `curl -i /nope` 看中间件头
- [ ] `curl -i /docs` 看中间件头

## 9. 下一章衔接

第 51 章 `CORS`：`CORSMiddleware` 的 `allow_origins`/`allow_credentials`/预检 `OPTIONS`，讲「为什么浏览器要预检」「`*` + credentials 为什么被禁」「`allow_origins` 不能写带路径的 URL」。

本章留下的伏笔：

1. `CORSMiddleware` 是中间件 → 覆盖 404（51）。
2. `request.state` → 请求 ID（52）。
3. 纯 ASGI 中间件（52/53）。