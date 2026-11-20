# 32 自定义异常与处理器 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「异常怎么被路由到处理器、为什么要业务异常、处理器里能做什么不能做什么、多层处理器怎么组织」拆开。学完这章，你要能把 `raise OrderNotFound()` 稳定变成 404，并且换协议时业务层不用改。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Starlette 1.10.0（本机实测） |
| 前置 | 第 31 章（`HTTPException`） |
| 覆盖范围 | 自定义异常基类、`@app.exception_handler`、优先级、处理器限制、依赖内抛错 |
| 明确不覆盖 | 422 定制（第 33 章）、统一契约与 `trace_id`（第 34 章）、中间件内异常 |
| 学完验收 | 能跑通 `verify.py` 13/13、能画出处理器查找顺序、能避开两个 500 反例 |

## 0. 怎么用这份文件

**依据约定**：`` `[Cn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 为什么不让业务层写 404
2 机制（第 2 节）    → 异常如何被查找与翻译
3 API（第 3 节）     → 注册方式、签名、返回值
4 边界（第 4 节）    → 优先级、处理器内抛错、并发、生命周期
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 分层异常设计
```

## 1. 概念：业务异常表达「领域事实」，处理器表达「协议」

| 层次 | 说什么 | 例子 |
| --- | --- | --- |
| 领域/业务 | 发生了什么 | `OrderNotFound`、`InsufficientBalance` |
| 传输/HTTP | 怎么告诉客户端 | 404 + `{code, message}` |
| 基础设施 | 怎么记录 | 日志、指标、trace |

如果业务层直接 `raise HTTPException(404)`：

| 代价 | 说明 |
| --- | --- |
| 领域逻辑依赖 Web 框架 | 换 CLI/gRPC 要改业务 |
| 状态码散落 | 同一个业务失败在不同端点用不同码 |
| 结构不统一 | 每个端点自己拼 `detail` |
| 无法携带业务字段 | `HTTPException` 只有 `detail` + `headers` |

## 2. 机制：异常查找与翻译

```text
raise OrderNotFound
  → ExceptionMiddleware 捕获
  → Starlette 用 exc.__class__.__mro__ 逐级查 handlers
        OrderNotFound → AppError → Exception → (无) 
  → 命中第一个注册过的类型
  → 调用 handler(request, exc) → Response
  → 处理器没命中：交给 ServerErrorMiddleware → 500
```

| 事实 | 说明 |
| --- | --- |
| 按 MRO 查找 | 子类处理器优先，**与注册顺序无关**（实测）|
| `BaseException` 不参与 | `KeyboardInterrupt` 不受影响 |
| 未命中 → 500 | 不会兜底成 422 |
| handler 必须返回 `Response` | 返回 dict 会被当响应对象 → 500（实测）|

## 3. API 逐个拆解

### 3.1 注册方式

| 方式 | 写法 | 适用 |
| --- | --- | --- |
| 装饰器 | `@app.exception_handler(X)` | 单文件 |
| 显式 | `app.add_exception_handler(X, fn)` | 插件化、循环注册 |
| 路由器 | `router` 上无此装饰器 | 只能挂在 app 上 |

实测：`add_exception_handler` 与装饰器等价。

### 3.2 处理器签名

```python
async def handler(request: Request, exc: AppError) -> JSONResponse: ...
```

| 要点 | 说明 |
| --- | --- |
| 必须两个参数 | `request` 和 `exc` |
| 同步也可 | 但不要在里面做阻塞 IO |
| 不能是 lambda | 需要两个位置参数，可读性也差 |
| 注解里的 `exc` 类型 | 仅用于类型检查，运行时不校验 |

### 3.3 返回值

| 返回 | 结果 |
| --- | --- |
| `JSONResponse` | 正常 |
| `PlainTextResponse` | 正常 |
| `Response` 子类 | 正常 |
| `dict` / `str` | **500**（实测）|

### 3.4 携带业务字段

```python
class InsufficientBalance(AppError):
    def __init__(self, required: int, balance: int) -> None:
        super().__init__(f"余额不足，还需 {required - balance} 分", required=required, balance=balance)
```

实测响应里带 `required=99999, balance=10000`，客户端可据此提示。

## 4. 边界条件

### 4.1 优先级（实测）

```text
OrderNotFound  →  order_not_found_handler（更具体）
DuplicateOrder →  app_error_handler（继承 AppError）
ValueError     →  500（无处理器）
```

注册顺序反写不影响结果。

### 4.2 处理器内部抛异常（实测）

`RuntimeError` → 500，body 为 `Internal Server Error`，不含 `RuntimeError`。**不会**二次进入其他处理器（避免死循环）。

### 4.3 处理器返回错类型（实测）

返回 dict → 500。这类 bug 本地容易漏，因为只有错误路径才触发——**必须给每个处理器写一条 422/404 用例**。

### 4.4 依赖里抛错

与路由内抛错完全等价（实测 403）。这让鉴权/租户校验可以集中在依赖里。

### 4.5 并发与状态

处理器是全局单例调用，`request`/`exc` 都是本次请求独有；**不要**在处理器里写模块级可变状态（如计数器），并发下会乱。

### 4.6 与中间件的关系

- `@app.middleware("http")` 里抛的异常：会进入异常处理器（中间件在异常处理器外层）。
- `BaseHTTPMiddleware` 内抛异常的行为与版本相关，**未实测**，生产前验证。

### 4.7 处理器与 OpenAPI

处理器不改变 OpenAPI。错误结构要在文档体现，仍需 `responses={...}`（第 26 章）。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 处理器 `return dict` | 500 | 返回 `Response` | 实测 |
| 处理器内再抛异常 | 500，原错误被掩盖 | 只做安全转换 | 实测 |
| 忘了注册处理器 | 照旧 500 | 挂到 app | 实测 |
| 业务层 `raise HTTPException` | 领域耦合 HTTP | 自定义异常 | `[C1]` |
| 异常类无 `code` | 客户端只能比对文案 | 加稳定码 | 第 34 章 |
| 处理器里查库/发请求 | 错误路径再失败 | 纯转换 | `[C3]` |
| 处理器里写全局计数器 | 并发串数据 | 用指标/日志 | `[C3]` |
| `BaseException` 兜底 | 吞掉 Ctrl+C | 用 `Exception` | `[C2]` |
| 只注册子类不注册基类 | 新子类漏接 | 基类兜底 + 子类特化 | 实测 |
| 处理器签名少写 `request` | TypeError → 500 | 两参数 | `[C1]` |
| 在处理器里读 body | 流已消费 | 只读 path/headers | `[C2]` |
| 用处理器改成功响应 | 它不是钩子 | 用中间件/响应模型 | `[C2]` |
| 依赖里 `return` 错误 dict | 流程继续 | `raise` | 第 31 章 |
| 异常里存 ORM 对象 | 序列化失败 | 只存标量 | 第 30 章 |
| 处理器中 `await` 长任务 | 拖慢错误响应 | 丢后台任务 | 第 50 章 |
| 只在本地测成功路径 | 处理器 bug 上线才发现 | 每个处理器一条用例 | 第 71 章 |
| 多个模块各自注册同一异常 | 后者覆盖前者 | 集中注册 | `[C2]` |
| 异常继承 `BaseException` | 不被 `ExceptionMiddleware` 处理 | 继承 `Exception` | `[C2]` |
| 想注册在 `router` 上 | 没有该装饰器 | 挂到 `app` | `[C1]` |

## 6. 最佳实践与编码建议

### 6.1 分层异常设计

```python
# domain/errors.py —— 不 import fastapi
class AppError(Exception):
    code = "APP_ERROR"

    def __init__(self, message: str, **extra: object) -> None:
        super().__init__(message)
        self.message = message
        self.extra = extra


class NotFound(AppError):
    code = "NOT_FOUND"


class OrderNotFound(NotFound):
    code = "ORDER_NOT_FOUND"


# api/errors.py —— 只在这里出现状态码
from fastapi import Request
from fastapi.responses import JSONResponse

STATUS = {"NOT_FOUND": 404, "ORDER_NOT_FOUND": 404, "CONFLICT": 409}


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return JSONResponse(
        status_code=STATUS.get(exc.code, 400),
        content={"code": exc.code, "message": exc.message, **exc.extra},
    )
```

好处：状态码映射集中在一张表，测试可以直接断言映射表。

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 异常继承链 2–3 层 | 太深难维护 |
| `code` 用大写下划线 | 稳定、可搜索 |
| 处理器只做转换 | 日志交给兜底/中间件 |
| 每个处理器一条测试 | 错误路径才触发，易漏 |
| 不把堆栈放进响应 | 泄露 |
| 处理器返回同一套结构 | 第 34 章 |

### 6.3 选型速查

| 需求 | 做法 |
| --- | --- |
| 简单错误 | `HTTPException`（第 31 章）|
| 多端点复用同一错误 | 自定义异常 |
| 需要业务字段 | 自定义异常 + `extra` |
| 全站统一结构 | 第 34 章 |
| 422 定制 | 第 33 章 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[C1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/handling-errors/#install-custom-exception-handlers | 自定义处理器 |
| `[C2]` | 官方文档 | https://www.starlette.io/exceptions/ | 异常中间件与查找顺序 |
| `[C3]` | 安全指南 | https://owasp.org/www-community/Improper_Error_Handling | 错误路径安全 |

> **核对状态**：`[C1]`–`[C3]` 为官方/安全链接，**本次未逐页直连复核**；处理器优先级、返回 dict 500、处理器内抛异常 500、普通异常不被捕获、`add_exception_handler` 等价、处理器读请求、依赖内抛错均为本机实测，`examples/verify.py` 复现 13/13 通过。`BaseHTTPMiddleware` 内抛错**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 业务异常与 HTTP 异常的职责边界
- [ ] MRO 查找顺序
- [ ] 处理器必须返回 `Response` 的原因
- [ ] 处理器内抛异常为什么不会二次进入处理器
- [ ] 处理器能做/不能做什么

**能写出（代码层）**：

- [ ] 基类 + 两个子类 + 两个处理器
- [ ] 携带业务字段的异常
- [ ] `add_exception_handler` 注册
- [ ] 依赖里抛业务异常
- [ ] 状态码映射表

**能判断（避坑层）**：

- [ ] 看到 `return dict` → 指出 500
- [ ] 看到处理器内 try/except → 指出掩盖
- [ ] 看到业务层 import fastapi → 指出耦合
- [ ] 看到只注册子类 → 指出漏接风险
- [ ] 看到没测试处理器 → 指出错误路径漏测

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 13/13
- [ ] `/orders/99` 返回自定义结构
- [ ] `/bad-handler` 观察 500

## 9. 下一章衔接

第 33 章 `校验错误定制`：`RequestValidationError`、`exc.errors()` 的结构、把 `loc`/`type`/`msg` 翻译成人类可读字段级错误，并处理 `json_invalid`、`body` 缺失等边界。

本章留下的伏笔：

1. 422 的定制在 第 33 章。
2. 全站统一契约在 第 34 章。
3. 错误日志与 trace 在 第 50 章。
4. 处理器测试在 第 71 章。