# 31 HTTPException · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「异常在请求生命周期里的位置、默认处理器做了什么、状态码怎么选、`detail` 与 `headers` 的边界」拆开。学完这章，你要能在 3 秒内判断「这个失败该用哪个状态码、该不该自己捕获」。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Starlette 1.10.0（本机实测） |
| 前置 | 第 22 章（状态码）、第 23 章（响应模型） |
| 覆盖范围 | `HTTPException` 参数、默认处理器、状态码语义、依赖内抛错、后台任务边界 |
| 明确不覆盖 | 自定义异常类与处理器（第 32 章）、422 定制（第 33 章）、统一契约（第 34 章） |
| 学完验收 | 能跑通 `verify.py` 16/16、能设计错误码表、能说出协议头要求 |

## 0. 怎么用这份文件

**依据约定**：`` `[Hn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 错误在 ASGI 栈里在哪一层
2 机制（第 2 节）    → 默认处理器与 detail 的序列化
3 API（第 3 节）     → 参数、状态码、headers
4 边界（第 4 节）    → 依赖/后台任务/流式/中间件
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 错误码表模板
```

## 1. 概念：`HTTPException` 是「受控的提前返回」

| 普通返回 | `raise HTTPException` |
| --- | --- |
| 走到函数结尾 | 立即中断后续代码 |
| 依赖链继续 | 依赖/路由都不再执行 |
| 状态码由装饰器定 | 状态码由异常定 |
| 可被响应模型过滤 | **不经过**响应模型，`detail` 原样输出 |

它比 `return JSONResponse(status_code=404, ...)` 好在：语义清晰、`headers` 有类型提示、默认处理器统一，且能被异常处理器接管（第 32 章）。

## 2. 机制：从 raise 到响应

```text
raise HTTPException(status_code, detail, headers)
  → 向上冒泡（跳过路由函数剩余代码）
  → ExceptionMiddleware 捕获
  → http_exception_handler：
        body = {"detail": detail}（先 jsonable_encoder）
        headers = exc.headers
  → 返回 JSONResponse(status_code, content=body, headers=headers)
```

| 事实 | 说明 |
| --- | --- |
| `detail` 默认 `"Not Found"` | 不传时用 HTTP 短语 |
| `detail` 会过 `jsonable_encoder` | 所以传 `datetime` 也不会炸（第 30 章）|
| `headers` 不走编码器 | 直接进 ASGI headers，必须 latin-1（实测中文 500）|
| 响应模型不参与 | 结果结构由处理器决定 |

## 3. API 逐个拆解

### 3.1 `status_code`

| 写法 | 建议 |
| --- | --- |
| `404` 字面量 | 可读性差，但常见 |
| `status.HTTP_404_NOT_FOUND` | **推荐**，避免拼错、便于搜索 |

### 3.2 `detail`

| 形态 | 适用 | 风险 |
| --- | --- | --- |
| `str` | 简单场景 | 客户端只能展示 |
| `dict` | 需要 `reason`/字段定位 | 结构即契约，难改 |
| `list` | 多条错误 | 与 422 的 `detail: list` 混淆 |

实测：`detail={"reason": "not_found", "item_id": 99}` → `{"detail": {...}}`。

### 3.3 `headers`

| 场景 | 必备头 |
| --- | --- |
| 401 | `WWW-Authenticate: Bearer`（或其变体）|
| 429 | `Retry-After: 30` |
| 3xx | `Location` |
| 自定义 | 业务错误码头（不推荐替代 body）|

限制：值必须 latin-1；中文会 500。

### 3.4 状态码选择

| 失败原因 | 状态码 | 备注 |
| --- | --- | --- |
| 字段类型/长度不对 | 422 | 框架默认，别手动造 |
| 语义上不合法但结构正确 | 400 或 422 | 团队统一 |
| 没带凭据 / 凭据无效 | 401 | + `WWW-Authenticate` |
| 有凭据但无权限 | 403 | 别用 401 |
| 资源不存在 | 404 | 或 403（隐藏存在性）|
| 状态冲突（重复/版本）| 409 | |
| 请求过多 | 429 | + `Retry-After` |
| 服务端 bug | 500 | 不要手动抛 |

## 4. 边界条件

### 4.1 在依赖里抛（实测）

`require_token` 抛 401 → 路由函数**不执行**，响应来自依赖。这让「鉴权」可以完全前置。

### 4.2 后台任务（实测）

```python
background_tasks.add_task(lambda: (_ for _ in ()).throw(HTTPException(404)))
```

结果：**状态码 200**，响应已发出，`HTTPException` 只被记录成任务异常。结论：后台任务里的失败只能靠日志/告警/落库。

### 4.3 流式响应之后

`StreamingResponse` 开始发送后再抛 `HTTPException` 无法改状态码（第 25 章已埋点）。生成器内部必须先判断再 yield。

### 4.4 中间件里抛

在 `BaseHTTPMiddleware` 里抛 `HTTPException` 能生效，但要注意异常处理器链的顺序；`@app.middleware("http")` 中抛出的异常会走 `ExceptionMiddleware`。**未实测**，写代码前先验证。

### 4.5 未捕获异常（实测）

`ValueError` → 500，body 为 `Internal Server Error`，不含堆栈（`raise_server_exceptions=False` 下观察）。生产环境还需关掉 uvicorn 的 debug、统一日志与 trace_id（第 34 章）。

### 4.6 框架自身的 404/405（实测）

| 场景 | 状态码 | body / 头 |
| --- | --- | --- |
| 路由不存在 | 404 | `{"detail": "Not Found"}` |
| 方法不允许 | 405 | `{"detail": "Method Not Allowed"}` + `Allow` |

### 4.7 OpenAPI

`HTTPException` **不会**自动写进 `responses`。实测 `/items/{item_id}` 只有 `200`/`422`。要在文档里表达错误契约，得手动 `responses={404: {...}}`（第 26 章）。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 401 不带 `WWW-Authenticate` | 不符合 RFC，客户端无指引 | 加该头 | `[H2]` |
| 头值写中文 | 500（latin-1） | 英文或编码 | 实测 |
| `except Exception: raise HTTPException(500, str(e))` | 泄露内部信息、丢日志 | 交给兜底 | `[H1]` |
| 后台任务里抛 `HTTPException` | 不生效（200） | 记日志/告警 | 实测 |
| 用 404 掩盖 403 却不统一 | 部分端点泄露存在性 | 明确策略 | `[H3]` |
| `detail` 带 SQL/路径 | 信息泄露 | 只给可操作信息 | `[H3]` |
| `detail` 传 ORM 对象 | 序列化失败 | `jsonable_encoder` | 第 30 章 |
| 403 用 401 返回 | 客户端反复登录 | 403 | `[H2]` |
| 重复创建返回 400 | 语义模糊 | 409 | `[H2]` |
| 429 无 `Retry-After` | 客户端立刻重试 | 加头 | `[H2]` |
| 依赖里 `return {"error": ...}` | 路由继续执行 | `raise` | 实测 |
| 以为 OpenAPI 自动含 404 | 文档缺错误契约 | 手动 `responses` | 实测 |
| 把 `HTTPException` 当业务异常 | 业务层耦合 HTTP | 自定义异常（第 32 章）| `[H1]` |
| 在 `finally` 里抛 `HTTPException` | 覆盖原异常 | 只清理不抛 | `[H1]` |
| 用 `detail` 传超长堆栈 | 客户端无法处理 | 日志留堆栈 | `[H3]` |
| 同一个失败在不同端点用不同码 | 客户端逻辑分叉 | 错误码表 | 第 34 章 |
| 401 与 403 混用同一 `detail` | 排障困难 | 区分文案 | `[H2]` |
| 手动抛 500 表示「兜底」 | 绕过日志/监控 | 让异常自然抛 | `[H1]` |
| 参数不合法却返回 404 | 客户端误判为资源问题 | 用 422 或 400 | `[H2]` |

## 6. 最佳实践与编码建议

### 6.1 错误码表模板

```python
from fastapi import HTTPException, status

# 【为什么】集中定义，避免每个端点各写一套文案与状态码
ERRORS = {
    "ITEM_NOT_FOUND": (status.HTTP_404_NOT_FOUND, "商品不存在"),
    "ITEM_NAME_TAKEN": (status.HTTP_409_CONFLICT, "商品名称已被占用"),
    "AUTH_REQUIRED": (status.HTTP_401_UNAUTHORIZED, "请先登录"),
    "FORBIDDEN": (status.HTTP_403_FORBIDDEN, "无权访问该资源"),
}


def fail(code: str, **extra: object) -> HTTPException:
    status_code, message = ERRORS[code]
    headers = {"WWW-Authenticate": "Bearer"} if status_code == 401 else None
    return HTTPException(status_code=status_code, detail={"code": code, "message": message, **extra}, headers=headers)
```

用法：`raise fail("ITEM_NOT_FOUND", item_id=99)`。

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 状态码用常量 | 可搜索、防拼错 |
| 401 必带 challenge | 协议要求 |
| `detail` 结构稳定 | 或走第 34 章统一契约 |
| 业务异常不继承 `HTTPException` | 解耦 HTTP 层 |
| 不做 `except Exception` | 让兜底处理器工作 |
| 错误文案可操作 | 「余额不足，需充值 30 元」而非「失败」 |

### 6.3 选型速查

| 需求 | 做法 |
| --- | --- |
| 简单「不存在」 | `raise HTTPException(404, "…")` |
| 需要错误码 | `detail={"code": ..., "message": ...}` 或第 34 章 |
| 业务异常 | 第 32 章 |
| 校验错误 | 第 33 章 |
| 全站统一结构 | 第 34 章 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[H1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/handling-errors/ | `HTTPException` 与处理器 |
| `[H2]` | 规范 | https://www.rfc-editor.org/rfc/rfc9110#section-15 | 401/403/404/409/429 语义与头要求 |
| `[H3]` | 安全指南 | https://owasp.org/www-community/Improper_Error_Handling | 错误信息泄露 |

> **核对状态**：`[H1]`–`[H3]` 为官方/规范/安全链接，**本次未逐页直连复核**；404/401/409/429、依赖抛错、未捕获异常 500、后台任务无效、405 与 `Allow`、OpenAPI 不含 404、中文头 500 均为本机实测，`examples/verify.py` 复现 16/16 通过。中间件内抛错**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] `HTTPException` 与 `return JSONResponse` 的差异
- [ ] 默认处理器如何组装 body
- [ ] 401/403/404/409/429 的边界
- [ ] 为什么 401 必须带 `WWW-Authenticate`
- [ ] 后台任务与流式响应里的失效原因

**能写出（代码层）**：

- [ ] 404 + 结构化 detail
- [ ] 401 + challenge
- [ ] 429 + `Retry-After`
- [ ] 依赖里抛错
- [ ] 集中错误码表

**能判断（避坑层）**：

- [ ] 看到中文头值 → 指出 500
- [ ] 看到 `except Exception` 包 500 → 指出泄露
- [ ] 看到依赖 `return` 错误 → 指出路由会执行
- [ ] 看到后台任务抛 `HTTPException` → 指出无效
- [ ] 看到 OpenAPI 无 404 → 指出需手动声明

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 16/16
- [ ] `/docs` 里触发 404 看结构
- [ ] `curl -i` 看 401 的 `WWW-Authenticate`

## 9. 下一章衔接

第 32 章 `自定义异常与处理器`：把 `NotFoundError` 这类业务异常从 HTTP 层解耦，用 `@app.exception_handler` 统一映射成状态码；顺带讲处理器优先级、`StarletteHTTPException` 与 `RequestValidationError` 的分工。

本章留下的伏笔：

1. 业务异常与 HTTP 解耦在 第 32 章。
2. 422 结构定制在 第 33 章。
3. 统一契约与 `trace_id` 在 第 34 章。
4. 错误响应进日志在 第 50 章。