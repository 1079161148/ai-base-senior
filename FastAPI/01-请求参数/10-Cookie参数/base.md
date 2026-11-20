# 10 Cookie 参数 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「Cookie 从哪来、为什么必须用 Response 写、6 个安全属性各防什么、CSRF 是怎么发生的」拆开。学完这章，你要能给一个登录系统配出不会被打穿的 Cookie。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Starlette 1.9.0 / Python 3.12.8（本机实测） |
| 前置 | 第 07、08 章（查询参数与校验） |
| 覆盖范围 | `Cookie()` 声明、`set_cookie`/`delete_cookie`、安全属性、CSRF、大小限制、与 Header 的关系 |
| 明确不覆盖 | 完整鉴权流程（44–49）、JWT 存储策略（47）、会话服务端存储（56） |
| 学完验收 | 能跑通 `verify.py` 9/9、能说出三个安全属性各防什么、能解释为什么 Cookie 鉴权仍需 CSRF 防护 |

## 0. 怎么用这份文件

**依据约定**：`` `[Cn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → Cookie 是浏览器存储，不是 Header 的别名
2 机制（第 2 节）    → 读与写分别走哪条链路（重点）
3 API（第 3 节）     → Cookie() 与 set_cookie 全参数
4 边界（第 4 节）    → 安全属性、CSRF、大小、删除、大小写
5 注意事项（第 5 节）→ 24 条对照
6 最佳实践（第 6 节）→ 会话 Cookie 模板
```

## 1. 概念：Cookie 是什么

```text
浏览器                                       服务器
  │  ① 登录，服务端 Set-Cookie: sid=abc        │
  │<──────────────────────────────────────────│
  │  ② 之后每次请求自动带 Cookie: sid=abc       │
  │──────────────────────────────────────────>│
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| Cookie 是 HTTP 头的一种 | 请求头 `Cookie`、响应头 `Set-Cookie` | `[C1]` |
| **由浏览器自动携带** | 前端代码不用管 | `[C1]` |
| 受同源/域/路径限制 | 不同域不会互带 | `[C1]` |
| 单个域名总量约 4KB | 每请求都带，浪费带宽 | `[C1]` |
| 数量上限约 50 个/域 | 浏览器差异 | `[C1]` |

| Cookie 适合 | Cookie 不适合 |
| --- | --- |
| 会话 id（短 token） | 大量业务数据（4KB 限制 + 每请求传输） |
| 用户偏好（主题、语言） | 敏感明文（即使 httponly 也建议只存 id） |
| 需要跨标签页共享的状态 | 前端要频繁读写的缓存（用 localStorage） |

> 注意：Cookie 与 `Authorization` 头的关键差异是**自动携带**——这既是便利，也是 CSRF 的根源。`[C2]`

## 2. 机制：读与写是两条链路

### 2.1 读：`Cookie()` → 请求头解析

```text
请求头：Cookie: session_id=abc; theme=dark
        ↓ Starlette 解析成 dict
        ↓ FastAPI 按参数名取值
函数参数：session_id="abc"
```

实测：

```text
无 cookie          -> {"session_id": null, "theme": null}
cookies={session_id:xyz} -> {"session_id": "xyz"}
```

| 步骤 | 失败表现 | 依据 |
| --- | --- | --- |
| 头里没有该 Cookie | 可选参数为 `None`；必填参数 422 `missing` | `[C3]` |
| 名字不匹配 | 同上（大小写敏感） | 实测 |
| 值非法 | 不做类型转换之外的校验 | `[C3]` |

### 2.2 写：`Response` 参数 → `Set-Cookie`

```python
@app.get("/login")
def login(response: Response) -> dict[str, str]:
    response.set_cookie("session_id", "abc", httponly=True)
    return {"ok": "1"}
```

实测响应头：

```text
session_id=sess-alice; HttpOnly; Max-Age=3600; Path=/; SameSite=lax
```

| 关键点 | 说明 |
| --- | --- |
| 必须声明 `response: Response` 参数 | FastAPI 注入真实响应对象 |
| 不能 `return {...}` 里带 Cookie | 返回值只填 body |
| 多次调用 → 多条 `Set-Cookie` 头 | 实测 2 条 |
| `secure=False` 时不出现 `Secure` | 实测 |

> 注意：读取多条 Set-Cookie 必须用 `headers.get_list("set-cookie")`。普通 `headers["set-cookie"]` 只返回第一条（实测：2 条只拿到 1 条）。

## 3. API 逐一拆解

### 3.1 `Cookie()` 参数

| 参数 | 默认 | 作用 | 依据 |
| --- | --- | --- | --- |
| `default` | 必填标记 | 默认值决定可选性 | `[C3]` |
| `alias` | `None` | Cookie 名（与参数名不同） | `[C3]` |
| `title` / `description` | `None` | 文档 | `[C3]` |
| `deprecated` | `False` | 标记废弃 | `[C3]` |
| `include_in_schema` | `True` | 是否进文档 | `[C3]` |
| 校验参数 | 同 `Query` | `min_length` / `pattern` 等 | 第 08 章 |

### 3.2 `set_cookie` 全参数

| 参数 | 默认 | 作用 | 推荐值 |
| --- | --- | --- | --- |
| `key` | 必填 | 名 | 小写 + 下划线 |
| `value` | 必填 | 值 | 只放 id，不放数据 |
| `max_age` | `None` | 存活秒数 | 会话 不设；持久 7 天 |
| `expires` | `None` | 绝对过期时间 | 与 `max_age` 二选一 |
| `path` | `"/"` | 生效路径 | 尽量收窄 |
| `domain` | `None` | 生效域 | 生产按需 |
| `secure` | `False` | 仅 HTTPS | **生产 `True`** |
| `httponly` | `False` | 禁 JS 读 | **`True`** |
| `samesite` | `"lax"` | CSRF 防护 | `"lax"`（默认够用） |

### 3.3 三个安全属性各防什么

| 属性 | 防什么 | 不设的后果 | 依据 |
| --- | --- | --- | --- |
| `httponly=True` | XSS 用 `document.cookie` 偷 token | 一个 XSS 就能盗号 | `[C4]` |
| `secure=True` | HTTP 明文传输被中间人抓 | 公共 WiFi 直接泄露 | `[C4]` |
| `samesite="lax"` | 跨站请求自动带 Cookie（CSRF） | 用户点恶意链接就被操作 | `[C2]` |

`samesite` 三档：

| 值 | 跨站请求是否带 Cookie | 适用 |
| --- | --- | --- |
| `"strict"` | 完全不带 | 高安全场景（但外链跳转后会掉登录态） |
| `"lax"` | 顶层 GET 导航带，其他不带 | **默认推荐** |
| `"none"` | 都带 | 必须同时 `secure=True`，否则浏览器拒绝 |

## 4. 边界条件

### 4.1 删除必须匹配 path/domain

实测：

```text
session_id=""; expires=Mon, 16 Nov 2026 17:46:28 GMT; Max-Age=0; Path=/; SameSite=lax
```

| 事实 | 说明 |
| --- | --- |
| `delete_cookie` = 设 `Max-Age=0` | 不是「清空值」 |
| `path` 不一致**删不掉** | 常见 bug：设置时 `path="/api"`，删除时用默认 `/` |
| `domain` 不一致也删不掉 | 同上 |

### 4.2 大小写与编码

| 场景 | 实测 |
| --- | --- |
| Cookie 名 `Session_Id` vs `session_id` | **不匹配**（敏感） |
| 值 `a%20b` | 原样返回 `a%20b`（**不自动解码**） |
| 值含 `;` `,` 空格 | 需要编码，否则解析错乱 |

> 注意：写的时候 Starlette 会做必要的引号包裹，但**读的时候不会解码**。要 URL 编码的值请自己 `urllib.parse.unquote`。

### 4.3 CSRF：为什么 Cookie 鉴权必须防

```text
① 用户登录 bank.com，浏览器存了 Cookie
② 用户访问 evil.com，页面里藏 <img src="https://bank.com/transfer?to=hacker&amount=1000">
③ 浏览器**自动带上 bank.com 的 Cookie** 发请求
④ 服务端看到合法 Cookie → 执行转账
```

| 防护手段 | 说明 | 依据 |
| --- | --- | --- |
| `SameSite=Lax/Strict` | 浏览器层面拦截大部分跨站 | `[C2]` |
| CSRF Token | 表单里带一次性 token，跨站拿不到 | `[C2]` |
| 校验 `Origin`/`Referer` | 简单有效 | `[C2]` |
| 用 `Authorization` 头而非 Cookie | 不会自动携带 | `[C5]` |

### 4.4 大小限制

| 限制 | 数值 | 后果 |
| --- | --- | --- |
| 单 Cookie | ~4KB | 超过被浏览器丢弃 |
| 每域名数量 | ~50 个 | 超了会淘汰旧的 |
| 每请求总大小 | 计入请求头 | 影响首字节时间 |

> 注意：把 JWT 放 Cookie 时，JWT 常达 1–2KB。如果还在里面塞权限列表、用户信息，很容易超过 4KB 被静默丢弃——表现为「偶发掉登录」。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `return {"set_cookie": ...}` | 无 Set-Cookie 头 | 用 `Response` 参数 | 实测 |
| `delete_cookie` 忘了 path | 删不掉 | path 与设置时一致 | 实测 |
| `httponly=False` 存 token | XSS 可窃取 | `True` | `[C4]` |
| `secure=False` 上生产 | 明文泄露 | `True` | `[C4]` |
| `samesite="none"` 无 `secure` | 浏览器拒绝 | 配 `secure=True` | `[C2]` |
| Cookie 存 >4KB | 静默丢弃 | 只存 id | `[C1]` |
| Cookie 名大小写混用 | 读不到 | 全小写 | 实测 |
| 期望值自动解码 | 拿到 `%20` | 自己 unquote | 实测 |
| 用 `headers["set-cookie"]` 读多条 | 只得到一条 | `get_list` | 实测 |
| 用 Cookie 存用户信息 | 体积大、易过期 | 存 id，服务端查 | `[C1]` |
| Cookie 做唯一鉴权手段 | CSRF 风险 | 加 SameSite/CSRF token | `[C2]` |
| 必填 Cookie 缺失返回 422 | 用户体验差 | 可选 + 业务层 401 | 第 46 章 |
| `path` 用 `/` 存敏感 Cookie | 全站都带 | 收窄 | `[C1]` |
| `domain=".example.com"` 无必要 | 子域都能读 | 精确域名 | `[C1]` |
| 忘记设 `max_age` 导致会话 Cookie | 关浏览器就掉登录 | 按需设 | `[C1]` |
| 用 Cookie 传 CSRF token 又自动带 | 无效 | token 放 body/头 | `[C2]` |
| 在 Cookie 里放 JSON | 需编码、易超限 | 只放 id | `[C1]` |
| 忘记 `delete_cookie` 前清服务端会话 | 服务端会话残留 | 双端都清 | 第 56 章 |
| 认为 httponly 能防所有 XSS | 只防读 Cookie | 还要防 CSRF/输出转义 | `[C4]` |
| 用 Cookie 存 flush 消息 | 需手动删除，易重复弹 | 服务端一次性消息 | `[C1]` |
| 多标签页并发登录 | Cookie 互相覆盖 | 服务端多会话 | `[C5]` |
| Cookie 里放手机号/邮箱 | 隐私泄露（伴随第三方脚本） | 只放 id | `[C4]` |
| 调试时用 `secure=True` 但走 HTTP | Cookie 不下发 | 本地关，生产开 | `[C1]` |
| 忽略浏览器第三方 Cookie 限制 | 跨域场景失效 | 用 Authorization | `[C5]` |
| 手动拼 Set-Cookie 头 | 属性遗漏 | 用 `set_cookie` | 实测 |

## 6. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 只存会话 id | 数据放服务端 | `[C1]` |
| `httponly=True` 永远开 | 除非前端必须读 | `[C4]` |
| 生产 `secure=True` | 环境变量控制 | `[C4]` |
| `samesite="lax"` 起步 | 需要跨站才升 `none` | `[C2]` |
| `path` 收窄到业务前缀 | 如 `/api` | `[C1]` |
| 登录后轮换 session id | 防会话固定攻击 | `[C2]` |
| 退出时双端清理 | 删 Cookie + 删服务端会话 | 第 56 章 |
| 敏感操作二次验证 | 不依赖 Cookie 状态 | `[C2]` |

**会话 Cookie 模板**：

```python
import os

from fastapi import Cookie, FastAPI, Response
from typing import Annotated

app = FastAPI()
IS_PROD = os.getenv("APP_ENV") == "prod"


@app.post("/auth/login")
def login(response: Response) -> dict[str, str]:
    session_id = "生成的随机 id"
    response.set_cookie(
        key="sid",
        value=session_id,
        max_age=7 * 24 * 3600,
        httponly=True,
        secure=IS_PROD,        # 本地 HTTP 调试关掉
        samesite="lax",
        path="/api",
    )
    return {"ok": "1"}


@app.get("/auth/me")
def me(sid: Annotated[str | None, Cookie()] = None) -> dict[str, str | None]:
    return {"sid": sid}
```

**边界**：

- Cookie 的值长度与编码规则由 RFC 6265 定义，本章只覆盖实践常见部分。
- 本章不涉及 JWT 内容与签名，第 47 章展开。
- 跨域前端（不同站点）场景下 Cookie 会被第三方 Cookie 策略限制，更推荐 `Authorization` 头（第 47 章）。

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[C1]` | 规范 | https://www.rfc-editor.org/rfc/rfc6265 | Cookie 语义、大小限制、属性 |
| `[C2]` | 规范 | https://owasp.org/www-community/attacks/csrf | CSRF 与 SameSite |
| `[C3]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/cookie-params/ | `Cookie()` 参数 |
| `[C4]` | 规范 | https://owasp.org/www-project-top-ten/ | XSS 与传输安全 |
| `[C5]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/security/ | 鉴权方案选型（第 44 章） |

> **核对状态**：`[C1]`、`[C2]`、`[C4]` 为规范类来源；`[C3]`、`[C5]` 按官方文档结构整理，**本次未逐页直连复核**。文中「实测」为本机 FastAPI 0.146.0 / Starlette 1.9.0 输出，`examples/verify.py` 可复现 9/9 通过。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] Cookie 与 Header 的关系
- [ ] 读 Cookie 与写 Cookie 为什么是两条链路
- [ ] `httponly` / `secure` / `samesite` 各防什么
- [ ] CSRF 的完整链路
- [ ] 为什么 Set-Cookie 不能合并
- [ ] 4KB 限制的后果

**能写出（代码层）**：

- [ ] 读 Cookie 的可选/必填两种写法
- [ ] 带三个安全属性的 `set_cookie`
- [ ] 正确的 `delete_cookie`（path 一致）

**能判断（避坑层）**：

- [ ] 看到 `return` 里带 Cookie 能指出不生效
- [ ] 看到 `samesite="none"` 无 `secure` 能指出被拒
- [ ] 看到 Cookie 存大 JWT 能指出超限风险
- [ ] 看到 `headers["set-cookie"]` 能指出只拿一条
- [ ] 看到 Cookie 鉴权无 CSRF 防护能指出风险

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 9/9
- [ ] 用 curl 看到 Set-Cookie 头
- [ ] 复现「大小写不同读不到」

## 9. 下一章衔接

第 11 章 `Header 参数`：同类机制换成请求头，讲清 `convert_underscores` 的双向行为（实测 `False` 时只认下划线头）、重复头解析成列表、大小写不敏感、必填头缺失的 `loc` 为什么是 kebab-case。

本章留下的伏笔：

1. Cookie 与 Header 都能承载 token——第 44–49 章做选型。
2. 会话服务端存储——第 56 章。
3. CSRF 中间件化——第 50 章。
