# 64 WebSocket 鉴权 · 完整版（base.md）

> `README.md` 给你能跑的四条鉴权路线；本文件把「浏览器到底能带什么、首帧为什么必须超时、握手前拒绝省了什么、多设备怎么不互踢」拆开。学完这章，你能判断一个「前端连不上/连上就被踢/登录后别人能看到我的消息」的问题出在哪。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0（本机实测） |
| 前置 | 第 63 章（WebSocket 基础）、第 07 模块（安全认证） |
| 覆盖范围 | query/header/cookie/首帧鉴权、1008、超时、清理、隔离 |
| 明确不覆盖 | OAuth2 全流程、JWT 签发细节、CSWSH 完整防护、Redis 会话 |
| 学完验收 | 能跑通 `verify.py` 14/14、能说出四种方式各自的坑 |

## 0. 怎么用这份文件

**依据约定**：`` `[An]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 握手是 HTTP，但有浏览器限制
2 机制（第 2 节）    → 四种位置的时间线
3 API（第 3 节）     → 逐个写法
4 边界（第 4 节）    → 超时、清理、多设备、CSWSH
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 选型与模板
```

## 1. 概念：握手是 HTTP，但客户端有限制

```text
浏览器：new WebSocket(url)   ← 只能给 URL 和子协议
       不能设 Authorization、不能设自定义头
```

| 客户端 | 能带 header |
| --- | --- |
| 浏览器 `WebSocket` | 不能（只能 cookie + URL）|
| 浏览器 `fetch` + 手写协议 | 不能（WebSocket 不能 fetch）|
| Python `websockets` | 能 |
| 移动端/桌面端 | 一般能 |

所以**面向浏览器的方案只能选 cookie 或首帧**。

## 2. 机制：四种位置的时间线

```text
① query   : GET /ws?token=x  → 服务端校验 → 101 或 close(1008)
② header  : GET /ws + Authorization → 校验 → 101 或 close(1008)
③ cookie  : GET /ws + Cookie → 校验 → 101 或 close(1008)
④ 首帧    : GET /ws → 101 accept → 等第一帧 → 校验 → ready 或 close(1008)
```

| 位置 | 拒绝时机 | 消耗 |
| --- | --- | --- |
| ①②③ | 握手前 | 几乎为 0 |
| ④ | 握手后 | 一个连接 + 一个超时定时器 |

实测：

| 场景 | 客户端看到 |
| --- | --- |
| query 缺失 | `1008 / invalid query token` |
| header 缺失 | `1008 / invalid authorization header` |
| cookie 缺失 | `1008 / invalid session cookie` |
| 首帧 token 错 | `1008 / invalid token` |
| 首帧类型错 | `1008 / first frame must be auth` |
| 首帧超时（0.15s）| 153ms 后 `1008 / auth timeout` |

## 3. API 逐个拆解

### 3.1 query

```python
token = websocket.query_params.get("token")
```

| 优点 | 缺点 |
| --- | --- |
| 实现最简单，浏览器可用 | 进访问日志、代理日志、浏览器历史 |
| 握手前可判 | 不适合长期令牌 |

**用法**：一次性票据（30 秒有效、用后即焚）。

### 3.2 header

```python
auth = websocket.headers.get("authorization", "")
token = auth.removeprefix("Bearer ").strip()
```

| 优点 | 缺点 |
| --- | --- |
| 不落日志 | 浏览器 `WebSocket` 用不了 |

适合服务间、CLI、移动端。

### 3.3 cookie

```python
token = websocket.cookies.get("session")
```

| 优点 | 缺点 |
| --- | --- |
| 浏览器自动带 | 需防 CSWSH（跨站 WebSocket 劫持）|

**必须校验 `Origin`**：

```python
origin = websocket.headers.get("origin")
if origin not in ALLOWED_ORIGINS:
    await websocket.close(code=1008, reason="bad origin")
```

### 3.4 首帧

```python
await websocket.accept()
frame = await asyncio.wait_for(websocket.receive_json(), timeout=timeout)
```

| 优点 | 缺点 |
| --- | --- |
| 浏览器可用、可带任意凭证 | 必须先 accept，占连接 |
| 可做多步认证 | 必须设超时 |

**超时是硬要求**：不设的话，攻击者建立连接后不发帧，就能用极低成本耗尽连接数。

## 4. 边界条件

### 4.1 超时（实测）

| 设置 | 实际 |
| --- | --- |
| `timeout=0.15` | 153ms 后关闭 |

`asyncio.wait_for` 在超时后取消 `receive_json`，此时**不能**再 `receive`，只能 `close`。

### 4.2 拒绝时的资源

| 路径 | 是否进 `ACTIVE` |
| --- | --- |
| 握手前拒绝 | 否 |
| 首帧拒绝 | 否（只有 accept，无业务登记）|

实测：2 次拒绝 + 1 次成功 → `rejected=2, connected=1`。

### 4.3 清理（实测）

```text
连接中：active = ["query-user"]
断开后：active = []，closed = 1
```

**关键**：`ACTIVE.pop(user)` 必须在 `finally`，否则异常断开时留幽灵。

### 4.4 多设备

| key 选择 | 后果 |
| --- | --- |
| `ACTIVE[user]` | 后登录踢掉先登录（单设备）|
| `ACTIVE[connection_id]` | 多设备并存 |
| `ACTIVE[user] = set()` | 多设备 + 可定向踢 |

实测用的是 `user` 作为 key，所以同用户第二次连接会覆盖第一次。生产按需求选。

### 4.5 CSWSH

浏览器发 WebSocket 会带 cookie，跨站页面也能发起连接。防护：

| 措施 | 说明 |
| --- | --- |
| 校验 `Origin` | 最直接 |
| `SameSite=Lax/Strict` | 减少跨站携带 |
| 首帧带 CSRF token | 双保险 |

**未实测**，标注为文档推导。

### 4.6 双用户隔离（实测）

```text
alice 发 {"to":"alice"} → 只有 alice 收到
bob   发 {"to":"bob"}   → 只有 bob 收到
```

隔离靠「每条连接一个 `WebSocket` 对象」，不是靠广播。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 首帧无超时 | 连接被白占 | `wait_for` | 实测 |
| 未鉴权 accept 后不关 | 挂死 | 立即 `close(1008)` | 实测 |
| 长期 token 放 URL | 泄露到日志 | 一次性票据 | `[A2]` |
| 浏览器带 Authorization | 不支持 | cookie/首帧 | `[A1]` |
| 失败返回 200 | 客户端误判 | `close(1008)` | 实测 |
| 只校验首帧 | 后续无身份 | 建会话 | 实测 |
| `finally` 不清理 | 幽灵连接 | `pop` | 实测 |
| 用 token 当 key | 多设备互踢 | 连接 id | 实测 |
| 握手后才校验 query | 已建连接 | 尽量前移 | 实测 |
| 关闭码 1006 | 协议错误 | 1000/1008/4000+ | `[A1]` |
| 超时 30s | 慢速攻击 | 1~5s | 实测 |
| reason 不区分 | 排障难 | 写清原因 | 实测 |
| 不校验 Origin | CSWSH | 白名单 | `[A3]` |
| cookie 无 SameSite | 跨站携带 | `Lax/Strict` | `[A3]` |
| CDN 记录 URL | token 泄露 | 换位置 | `[A2]` |
| 多 worker 内存统计 | 数字不准 | 外部存储 | 第 63 章 |
| 鉴权后不刷新权限 | 降权不生效 | 定期重校验 | 实测未覆盖 |
| 忘记关闭 Redis 订阅 | 泄漏 | `finally` 退订 | 第 63 章 |
| 只在连接建立时校验一次 | 令牌过期后仍能继续发消息 | 定时或逐帧复核 | 实测未覆盖 |

## 6. 最佳实践与编码建议

### 6.1 选型

| 客户端 | 推荐 |
| --- | --- |
| 浏览器 + 同域 | cookie + `Origin` 校验 |
| 浏览器 + 跨域 | 首帧鉴权（带短期票据）|
| 移动端/CLI | header |
| 一次性下载链接 | query 票据（短 TTL）|

### 6.2 首帧协议

```json
→ {"type": "auth", "token": "<短期票据>"}
← {"type": "ready", "user": "alice"}
← {"type": "error", "code": "INVALID_TOKEN"}   // 随后 close(1008)
```

### 6.3 检查清单

| 检查项 | 原因 |
| --- | --- |
| 超时 1~5s | 防白占 |
| 失败 `close(1008)` | 客户端可识别 |
| `finally` 清理 | 防幽灵 |
| `Origin` 白名单 | 防 CSWSH |
| 短期票据 | 防日志泄露 |
| 连接 id 做 key | 多设备 |
| 权限可刷新 | 降权生效 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[A1]` | 规范 | https://www.rfc-editor.org/rfc/rfc6455 | 握手与关闭码 |
| `[A2]` | 文档 | https://developer.mozilla.org/zh-CN/docs/Web/API/WebSocket | 浏览器 API 限制 |
| `[A3]` | 文档 | https://developer.mozilla.org/zh-CN/docs/Web/HTTP/Headers/Set-Cookie | SameSite 与 CSWSH |

> **核对状态**：`[A1]`–`[A3]` 为规范/文档链接，**本次未逐页直连复核**；四种鉴权有效/缺失/错误、首帧超时实测耗时、拒绝计数与连接计数、断开清理、双用户隔离均为本机实测，`examples/verify.py` 复现 14/14 通过。CSWSH、`Origin` 校验、多 worker 会话、权限刷新、Redis 退订**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 浏览器 `WebSocket` 为什么不能带自定义头
- [ ] 四种鉴权位置各自的代价
- [ ] 首帧为什么必须超时
- [ ] 握手前拒绝与握手后拒绝的差别
- [ ] CSWSH 与 `Origin` 校验

**能写出（代码层）**：

- [ ] query 鉴权
- [ ] header 鉴权
- [ ] cookie 鉴权
- [ ] 首帧鉴权 + 超时
- [ ] `finally` 清理
- [ ] `Origin` 白名单

**能判断（避坑层）**：

- [ ] 看到无超时首帧 → 指出白占
- [ ] 看到长期 token 在 URL → 指出泄露
- [ ] 看到 `finally` 缺失 → 指出幽灵
- [ ] 看到 user 作 key → 指出多设备互踢
- [ ] 看到无 `Origin` 校验 → 指出 CSWSH

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 14/14
- [ ] 浏览器带 cookie 连 `/ws/auth/cookie`
- [ ] 手工用一个超时参数验证 153ms 级别的关闭

## 9. 下一章衔接

第 65 章 `大型应用拆分`：`APIRouter` 树、`prefix`/`tags`、按模块组装、依赖与生命周期归属。

本章留下的伏笔：

1. 鉴权依赖（64）→ 65 的 router 级 `dependencies`。
2. 连接管理器（63/64）→ 65 抽成独立模块。
3. `Origin`/cookie 配置（64）→ 65 统一配置入口。