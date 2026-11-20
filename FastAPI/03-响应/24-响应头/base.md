# 24 响应头 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「响应头在 Starlette 里怎么被写入、为什么中文会失败、多值头怎么处理、哪些头不能碰」拆开。学完这章，你要能给任何端点加对头、且不把文档和实际搞混。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1（本机实测） |
| 前置 | 第 21–23 章（响应模型、状态码、联合类型） |
| 覆盖范围 | 注入 `Response`、`JSONResponse` 带头、`set_cookie`、媒体类型、OpenAPI 头文档、编码限制 |
| 明确不覆盖 | CORS 中间件（第 51 章）、缓存策略（第 52 章）、`StreamingResponse` 细节（第 25 章） |
| 学完验收 | 能跑通 `verify.py` 10/10、能解释多值头与编码失败、能判断哪些头不能手改 |

## 0. 怎么用这份文件

**依据约定**：`` `[Hn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 头与 body 的分工
2 机制（第 2 节）    → 头是在哪一步被写出去的
3 API（第 3 节）     → 三种设置方式 + cookie
4 边界（第 4 节）    → 编码、多值、不可改的头、大小限制
5 注意事项（第 5 节）→ 19 条对照
6 最佳实践（第 6 节）→ 安全头模板
```

## 1. 概念：头承载「元信息」，body 承载「数据」

| 头 | 典型用途 |
| --- | --- |
| `Content-Type` | 告诉客户端怎么解析 body |
| `Content-Length` | 传输长度（框架维护）|
| `Set-Cookie` | 下发会话 |
| `Location` | 201 指向新资源 |
| `X-RateLimit-*` | 限流信息 |
| `ETag` / `Last-Modified` | 缓存协商 |
| `X-Request-Id` | 链路追踪 |

原则：**能放 body 的业务数据不要放头**。头有大小限制、大小写与编码规则复杂、部分代理会改写。

## 2. 机制：头什么时候被写出去

```text
你 return 模型 → FastAPI 序列化 → Starlette Response
                                   ├── 框架写 content-type / content-length
                                   └── 你通过注入的 Response 或 JSONResponse 写的头 ← 本章
                                 → 发送
```

| 事实 | 含义 |
| --- | --- |
| 注入的 `Response` 就是最终响应对象 | 改它是真改 |
| 返回 `Response` 子类时，FastAPI 直接发送 | 不走响应模型（第 23 章）|
| `responses=` 里的 headers | 只进 OpenAPI，不进响应 |

## 3. API 逐个拆解

### 3.1 注入 `Response`

```python
@app.get("/items/1")
def get_item(response: Response) -> ItemOut:
    response.headers["X-Request-Id"] = "req-abc-123"
    return ItemOut(id=1, name="键盘")
```

| 要点 | 说明 |
| --- | --- |
| 参数名任意，类型必须是 `Response` | FastAPI 识别类型 |
| 不是返回值 | 返回模型照常 |
| 可以改状态码 | 第 22 章 |
| 头名保留你写的写法 | 读取时不区分大小写（实测）|

### 3.2 直接返回 `Response` 子类

| 类 | 默认 `Content-Type` |
| --- | --- |
| `JSONResponse` | `application/json` |
| `PlainTextResponse` | `text/plain; charset=utf-8` |
| `HTMLResponse` | `text/html; charset=utf-8` |
| `RedirectResponse` | 无 body，带 `Location` |
| `StreamingResponse` | 你指定 |

### 3.3 Cookie

```python
response.set_cookie(
    "session", "token-123",
    max_age=3600, httponly=True, secure=True, samesite="lax", path="/",
)
```

| 参数 | 建议 |
| --- | --- |
| `httponly=True` | 防 XSS 读取（生产必开）|
| `secure=True` | 仅 HTTPS |
| `samesite="lax"` | 防 CSRF 的默认选择 |
| `max_age` | 秒；不设是会话 Cookie |
| `path` / `domain` | 删除时要一致 |

实测头：`session=token-123; Path=/; Max-Age=3600; HttpOnly; SameSite=lax`。

### 3.4 OpenAPI 声明响应头

```python
responses={200: {"headers": {"X-RateLimit-Remaining": {"description": "剩余配额",
            "schema": {"type": "integer", "example": 99}}}}}
```

| 事实 | 说明 |
| --- | --- |
| 只影响文档 | 实测不会真的发 |
| SDK 可生成类型 | 对第三方有用 |
| 容易忘 set | 建议写测试同时断言「文档有 + 实际有」|

## 4. 边界条件

### 4.1 编码：头值必须 latin-1

实测：`response.headers["X-Note"] = "中文"` → 请求 500（`UnicodeEncodeError`，Starlette 用 latin-1 编码头）。

| 方案 | 说明 |
| --- | --- |
| 用 ASCII | 最稳 |
| URL 编码 / Base64 | 需要时 |
| 放 body | 中文内容优先放 body |

### 4.2 多值头

| 头 | 行为 |
| --- | --- |
| `Set-Cookie` | 允许多条，客户端可能合并成 `a=1, b=2` |
| `Content-Length` | **不该**多值；手改会得到 `'7, 999'`（实测）|
| 自定义头 | 多次 set 会覆盖，不会追加 |

读取多值：`r.headers.get_list("set-cookie")`（httpx/httpx2 提供）。

### 4.3 不要手改的头

| 头 | 原因 |
| --- | --- |
| `Content-Length` | 与真实 body 冲突（实测变多值）|
| `Transfer-Encoding` | 由服务器决定 |
| `Connection` | 由服务器/代理管理 |
| `Date` / `Server` | 服务器写 |

### 4.4 大小限制

常见反代默认单头 8KB、总头 16–64KB。用头传 token 列表、权限清单很快就会超限。

### 4.5 与 CORS 的关系

自定义头（`X-*`）在浏览器跨域时，需要服务端 `Access-Control-Expose-Headers` 才能被前端 JS 读到；预检还要允许该请求头。配置在第 51 章。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 用 Pydantic 模型声明响应头 | 模型只能描述 body | 注入 `Response` | 实测 |
| 只写 `responses.headers` 文档 | 实际没有 | 文档 + set | 实测 |
| 头值写中文 | 500 | ASCII / 编码 | 实测 |
| 手改 `Content-Length` | `'7, 999'` 多值 | 交给框架 | 实测 |
| `set_cookie` 不开 `httponly` | XSS 可读 | 生产开 | `[H3]` |
| `set_cookie` 不开 `secure` | 明文传输 | HTTPS 下开 | `[H3]` |
| Cookie 不设 `samesite` | CSRF 风险 | `lax`/`strict` | `[H3]` |
| `delete_cookie` 的 path 不一致 | 删不掉 | 与 set 时一致 | `[H2]` |
| 用头传大 JSON | 8KB 限制/代理截断 | 放 body | `[H1]` |
| 头名带下划线 | 某些代理丢弃 | 用连字符 | `[H1]` |
| 依赖头名大小写 | 客户端读不到 | 读取时忽略大小写 | 实测 |
| 以为多次 set 会追加 | 实际覆盖 | 需要多值用专门头 | 实测 |
| 自定义头跨域前端读不到 | 缺 `Expose-Headers` | 配 CORS | 第 51 章 |
| `RedirectResponse` 忘了状态码 | 默认 307 | 显式 `302/301` | `[H2]` |
| `JSONResponse` 配 `response_model` | 文档骗人 | 去掉 | 第 23 章 |
| 忘设 `Content-Type` | 客户端按文本解析 | 用对应 Response 类 | `[H2]` |
| 用头做权限 | 客户端可伪造请求头 | 服务端会话/令牌 | `[H3]` |
| 头里塞敏感信息 | 日志/代理可见 | 放 body 或加密 | `[H3]` |
| 不测响应头 | 回归无感知 | 断言关键头 | 第 71 章 |
| 想在装饰器里传 `headers=` | 没有该参数 | 用注入 `Response` | `[H2]` |

## 6. 最佳实践与编码建议

### 6.1 安全响应头中间件模板

```python
from fastapi import FastAPI, Request

app = FastAPI()


@app.middleware("http")
async def add_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["Referrer-Policy"] = "no-referrer"
    return response
```

（中间件细节在第 51 章。）

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 自定义头一律 `X-` 前缀 | 避免与标准头冲突 |
| 头值纯 ASCII | 中文放 body |
| Cookie 三件套 | `httponly`+`secure`+`samesite` |
| 头文档与实际都写 | 并写测试 |
| `X-Request-Id` 用中间件统一加 | 不逐端点写 |
| 不要手改 `Content-Length` | 交给框架 |
| 用常量管理头名 | 避免拼错 |

### 6.3 选型速查

| 需求 | 做法 |
| --- | --- |
| 加追踪 id | 中间件 |
| 返回新资源地址 | `Location` 头 |
| 下发会话 | `set_cookie` |
| 限流信息 | `X-RateLimit-*` |
| 多文件下载 | `Content-Disposition`（第 25 章）|
| 跨域暴露 | CORS `Expose-Headers` |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[H1]` | 规范 | https://www.rfc-editor.org/rfc/rfc9110#section-5 | 头字段语义与大小写 |
| `[H2]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/response-headers/ | `Response` 设置头 |
| `[H3]` | 安全指南 | https://owasp.org/www-community/controls/SecureCookieAttribute | Cookie 安全属性 |
| `[H4]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/custom-response/ | 各类 Response 的默认媒体类型 |

> **核对状态**：`[H1]`–`[H4]` 为规范/官方链接，**本次未逐页直连复核**；注入改头、大小写、Cookie 属性、中文头 500、Content-Length 多值均为本机实测，`examples/verify.py` 复现 10/10 通过。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 头与 body 的分工
- [ ] 三种设置响应头的方式
- [ ] `responses.headers` 的真实作用
- [ ] 头值为什么必须是 ASCII
- [ ] 多值头与单值头的区别

**能写出（代码层）**：

- [ ] 注入 `Response` 加头
- [ ] `JSONResponse` 带头
- [ ] 安全 Cookie
- [ ] 文档声明响应头
- [ ] 自定义媒体类型

**能判断（避坑层）**：

- [ ] 看到中文头值 → 指出 500
- [ ] 看到手改 Content-Length → 指出多值
- [ ] 看到只有文档没有 set → 指出骗人
- [ ] 看到 Cookie 缺 `httponly` → 指出 XSS
- [ ] 看到头传大 JSON → 指出限制

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 10/10
- [ ] `curl -i` 看响应头
- [ ] `/docs` 里看到头文档

## 9. 下一章衔接

第 25 章 `直接返回 Response`：本章已用到 `JSONResponse`/`PlainTextResponse`，下一章系统讲「什么时候必须放弃响应模型」——文件下载、流式输出、重定向、XML/CSV，以及各自的头与性能陷阱。

本章留下的伏笔：

1. `Content-Disposition` 在 第 25 章。
2. 中间件加头在 第 51 章。
3. CORS 暴露头在 第 51 章。
4. 缓存协商在 第 52 章。
