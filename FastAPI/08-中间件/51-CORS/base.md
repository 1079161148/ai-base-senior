# 51 CORS · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「浏览器为什么要预检、服务端到底回什么、哪些配置组合是陷阱、为什么它不是安全边界」拆开。学完这章，你要能独立排查「前端跨域失败」而不靠盲改配置。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Starlette（本机实测） |
| 前置 | 第 50 章（中间件） |
| 覆盖范围 | `CORSMiddleware`、预检、`Vary: Origin`、credentials、白名单策略 |
| 明确不覆盖 | 同源策略全貌、CSP、COOP/COEP、CSRF（见第 49 章）|
| 学完验收 | 能跑通 `verify.py` 14/14、能判「配置错」还是「代码错」|

## 0. 怎么用这份文件

**依据约定**：`` `[Cn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 谁在拦
2 机制（第 2 节）    → 简单请求 vs 预检
3 API（第 3 节）     → 六个参数
4 边界（第 4 节）    → 400/200、*、Vary、CDN
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 生产配置
```

## 1. 概念：CORS 不是服务端鉴权

| 谁执行 | 结果 |
| --- | --- |
| 浏览器 | 检查响应头，缺 `ACAO` 就把响应**丢弃**给 JS |
| 服务端 | 只负责「加头」，不阻止返回数据（实测非法 origin 仍 200 + 数据）|
| curl / 后端 | 完全不看 CORS，照样拿数据 |

所以：**CORS 配置错误 = 浏览器用不了；不配置 = 任何人（含脚本）都能用**。

## 2. 机制：两种请求

### 2.1 简单请求（不预检）

条件：方法是 `GET/HEAD/POST`，且头在安全白名单内（`Accept`、`Accept-Language`、`Content-Language`、`Content-Type` 且值为 `text/plain`/`multipart/form-data`/`application/x-www-form-urlencoded`）。

```text
GET /data  Origin: http://localhost:3000
← 200  Access-Control-Allow-Origin: http://localhost:3000
```

### 2.2 预检请求（preflight）

触发：非简单方法（`PUT/DELETE/PATCH`）、自定义头、`Content-Type: application/json`。

```text
OPTIONS /data
Origin: http://localhost:3000
Access-Control-Request-Method: POST
Access-Control-Request-Headers: X-Token

← 200
Access-Control-Allow-Origin: http://localhost:3000
Access-Control-Allow-Methods: GET, POST
Access-Control-Allow-Headers: Accept, ..., X-Token
Access-Control-Max-Age: 600
Access-Control-Allow-Credentials: true
```

之后浏览器才发真实请求。

## 3. API 逐个拆解

| 参数 | 实测效果 |
| --- | --- |
| `allow_origins=["http://localhost:3000"]` | 回声该值 |
| `allow_credentials=True` | `Access-Control-Allow-Credentials: true` |
| `allow_methods=["GET","POST"]` | 预检 `Allow-Methods: GET, POST`；`DELETE` → 400 |
| `allow_headers=["X-Token","Content-Type"]` | 预检 `Allow-Headers` 会**并上安全白名单四个** |
| `expose_headers=["X-Total"]` | `Access-Control-Expose-Headers: X-Total` |
| `max_age=600` | `Access-Control-Max-Age: 600` |

## 4. 边界条件

### 4.1 非法 origin 的两种结局（实测）

| 请求类型 | 结果 |
| --- | --- |
| 真实请求 | **200 + 完整 JSON**，无 `ACAO` |
| 预检 | **400 `Disallowed CORS origin`** |

**这是排查的关键**：前端报「CORS 错误」但 Network 里状态 200 → 服务端没放行这个 origin；状态 400 → 预检被拒，看是 origin/method/header 哪个。

### 4.2 `*` + credentials（实测）

`allow_origins=["*"]` + `allow_credentials=True`：Starlette **回声具体 origin**（`http://any.com`），不是 `*`。

原因：规范禁止 `*` 与 credentials 同用，框架用「回声」实现「全放开」。

**这等于对任意站点开放带 cookie 的访问**——生产绝对不要。

### 4.3 `Vary: Origin`（实测）

两种响应都带 `Vary: Origin`。这是给 CDN/反向代理的：**响应内容随 Origin 变，不能跨 origin 复用缓存**。

如果 Nginx 自己加 CORS 头又没配 `Vary`，会出现「A 站点的缓存被发给 B 站点」。

### 4.4 404 也带 CORS 头（实测）

因为它是中间件（第 50 章）。好处：前端能拿到 404 的具体错误，而不是一个「CORS 错误」掩盖一切。

### 4.5 `allow_headers` 的白名单合并（实测）

配置 `["X-Token","Content-Type"]`，实际回的是：

```text
Accept, Accept-Language, Content-Language, Content-Type, X-Token
```

所以不用手动加这四个。

### 4.6 origin 的格式要求

| 写法 | 结果 |
| --- | --- |
| `http://a.com` | ✅ |
| `http://a.com/` | ❌ 不匹配 |
| `http://a.com/api` | ❌ 不匹配 |
| `https://a.com:8443` | ✅ 端口必须写 |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| origin 带尾斜杠 | 永不匹配 | 去掉 | 实测 |
| origin 带路径 | 永不匹配 | 只写源 | `[C1]` |
| 生产用 `*` + credentials | 任意站点可带 cookie 访问 | 白名单 | 实测 |
| 以为 CORS 防越权 | 脚本直连照样读 | 真正的鉴权 | 实测 |
| `allow_headers` 漏自定义头 | 预检 400 | 列全 | 实测 |
| 漏 `expose_headers` | JS 读不到自定义头 | 显式列出 | `[C1]` |
| 只在开发环境配置 | 线上跨域失败 | 按环境配 | 规则 |
| Nginx 与中间件同时加头 | `ACAO: a, b` 非法 | 只在一处 | `[C3]` |
| 忽略 `Vary: Origin` | CDN 串缓存 | 保留框架默认 | 实测 |
| `allow_origin_regex=".*"` | 等价全放开 | 精确正则 | `[C1]` |
| 预检返回 204 却被 Nginx 改 301 | 浏览器不发真实请求 | 放行 OPTIONS | `[C3]` |
| 把 `OPTIONS` 拦在鉴权中间件前 | 预检 401 | 预检跳过鉴权 | 第 50 章 |
| 用 `allow_methods=["*"]` 又 `["GET"]` 混写 | 后者覆盖 | 明确列 | `[C1]` |
| 前端用开发代理就以为线上没问题 | 线上是不同源 | 生产也配 | 规则 |
| 把 token 放 cookie 又开 `*` | CSRF + 全放开 | 白名单 + SameSite | `[C2]` |
| 只测预检 | 真实响应缺头未覆盖 | 两种都测 | 实测 |
| 报错就加 `*` | 掩盖真实配置问题 | 查 Network 状态码 | 规则 |
| 忘记 `Content-Type: application/json` 触发预检 | 以为「简单请求」 | 预期预检 | `[C1]` |
| 预检被路由层 405 拦 | 浏览器不发真实请求 | CORS 中间件放最外层 | `[C1]` |

## 6. 最佳实践与编码建议

### 6.1 生产配置

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,          # 从环境变量读，逗号分隔
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-Total-Count"],
    max_age=600,
)
```

| 建议 | 说明 |
| --- | --- |
| origin 走配置 | 分环境 |
| 不用 `*` | 除非纯公开只读 API |
| `max_age` 600s | 减少预检 |
| 与 Nginx 二选一 | 避免重复头 |
| 预检跳过鉴权 | 否则 401 |

### 6.2 排查流程

```text
1. Network 看 OPTIONS 状态码
   ├─ 400 Disallowed CORS origin  → 白名单没加对（检查斜杠/路径/端口）
   ├─ 400 Disallowed CORS headers → allow_headers 漏了
   ├─ 400 Disallowed CORS method  → allow_methods 漏了
   ├─ 401/403                     → 鉴权中间件拦了预检
   └─ 200 但真实请求无 ACAO        → 真实响应被别的层覆盖（Nginx/网关）
2. 看 Vary 是否含 Origin
3. 看是否有重复 ACAO（逗号拼接即非法）
```

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[C1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/cors/ | `CORSMiddleware` 参数 |
| `[C2]` | 规范 | https://fetch.spec.whatwg.org/#cors-protocol | CORS 协议原文 |
| `[C3]` | 文档 | https://www.starlette.io/middleware/#corsmiddleware | 实现行为 |

> **核对状态**：`[C1]`–`[C3]` 为官方/规范链接，**本次未逐页直连复核**；回声、`Vary`、非法 origin 200/400、无 Origin 无头、预检三类 400、404 带 CORS、`*`+credentials 回声、expose、任意 origin 放行均为本机实测，`examples/verify.py` 复现 14/14 通过。真实浏览器行为、Nginx 双层冲突、CDN 缓存**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 谁在执行 CORS
- [ ] 简单请求与预检的触发条件
- [ ] 非法 origin 为什么还是 200
- [ ] `*` + credentials 的处理
- [ ] `Vary: Origin` 的作用

**能写出（代码层）**：

- [ ] 完整 `CORSMiddleware` 配置
- [ ] `expose_headers`
- [ ] 正则可配置
- [ ] 环境变量驱动

**能判断（避坑层）**：

- [ ] 看到 origin 带斜杠 → 指出不匹配
- [ ] 看到生产 `*` + credentials → 指出风险
- [ ] 看到「CORS 防越权」→ 指出只约束浏览器
- [ ] 看到 Nginx 也加头 → 指出重复
- [ ] 看到预检 401 → 指出鉴权拦了

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 14/14
- [ ] `curl -i -H "Origin: http://localhost:3000" /data`
- [ ] `curl -i -X OPTIONS` 看预检

## 9. 下一章衔接

第 52 章 `请求上下文与日志`：`contextvars` + 请求 ID，让 `trace_id` 贯穿中间件、依赖、业务日志与响应头，讲「为什么不能用全局变量」「`BaseHTTPMiddleware` 与 contextvar 的传播」「结构化日志怎么接」。

本章留下的伏笔：

1. 请求 ID 放 `X-Request-ID` 也在 `expose_headers` 里（51）。
2. 中间件里设 contextvar（50）。
3. 日志不记 token（第 49 章）。