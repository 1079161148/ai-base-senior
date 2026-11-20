# 45 OAuth2 密码流 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「密码流的两个对象各管什么、表单解析怎么来的、token 怎么从 header 剥离、`tokenUrl` 对文档的影响、错误码为什么是 400」拆开。学完这章，你要能交付一个符合 OAuth2 契约的 `/token`。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / python-multipart 0.0.34（本机实测） |
| 前置 | 第 27 章（表单）、第 44 章（`Security`/securitySchemes） |
| 覆盖范围 | `OAuth2PasswordRequestForm`、`OAuth2PasswordBearer`、表单 vs JSON、`tokenUrl`、可选登录 |
| 明确不覆盖 | JWT 签发与校验（47）、作用域授权（48）、刷新令牌、真实 OAuth2 提供方对接 |
| 学完验收 | 能跑通 `verify.py` 15/15、能解释每个实测差异、能避开 422/400 的坑 |

## 0. 怎么用这份文件

**依据约定**：`` `[On]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 两个对象分工
2 机制（第 2 节）    → 表单解析 + header 剥离
3 API（第 3 节）     → 表单字段、Bearer 参数
4 边界（第 4 节）    → 422/400/401、tokenUrl、auto_error
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 登录端点模板
```

## 1. 概念：发 token 与用 token 是两件事

| 环节 | 对象 | 位置 | 失败码 |
| --- | --- | --- | --- |
| 换 token | `OAuth2PasswordRequestForm` | `POST /token` 表单 | 422（缺字段）/ 400（业务）|
| 用 token | `OAuth2PasswordBearer` | `Authorization: Bearer x` | 401 |

密码流（password grant）本身在 OAuth2.1 里已被标记为不推荐（应使用授权码 + PKCE），但作为**内部系统**或学习路径仍是官方教程主线。生产对外暴露的第三方登录请用授权码流。

## 2. 机制：表单解析 + header 剥离

```text
POST /token
  body: username=alice&password=...&grant_type=password&scope=read+write
  → OAuth2PasswordRequestForm 解析为对象
      username, password（必填）
      grant_type=None, scopes=[], client_id=None, client_secret=None

GET /users/me
  Authorization: Bearer abc
  → OAuth2PasswordBearer 校验前缀 → 注入 "abc"
  → 缺失/前缀不符 → 401 {"detail":"Not authenticated"} + WWW-Authenticate: Bearer
```

| 事实 | 说明 |
| --- | --- |
| 表单不是 JSON | 实测 JSON → 422 |
| `scope` 空格分隔 | `"read write"` → `["read","write"]` |
| 前缀必须存在 | `abc` → 401 |
| 注入的是裸字符串 | 解析留给下一章 |

## 3. API 逐个拆解

### 3.1 `OAuth2PasswordRequestForm`

| 字段 | 注解 | 必填 |
| --- | --- | --- |
| `username` | `str` | 是 |
| `password` | `str` | 是 |
| `grant_type` | `str \| None`（正则 `password`）| 否 |
| `scope` | `str`（默认 `""`）| 否 |
| `client_id` / `client_secret` | `str \| None` | 否 |
| `scopes`（属性）| `list[str]` | 由 `scope` 拆出 |

实测 `verify` 里断言了 `required == ["username","password"]`。

### 3.2 `OAuth2PasswordBearer`

```python
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")
token: Annotated[str, Depends(oauth2_scheme)]
```

| 参数 | 作用 |
| --- | --- |
| `tokenUrl` | 写进 `flows.password.tokenUrl` |
| `auto_error=False` | 没 token 返回 `None` |
| `scheme_name` | `securitySchemes` 键名 |
| `scopes` | 生成 `flows.password.scopes` 字典（第 48 章）|

### 3.3 响应结构

```json
{"access_token": "token-for-alice", "token_type": "bearer"}
```

| 键 | 规范要求 |
| --- | --- |
| `access_token` | 必须（下划线）|
| `token_type` | 必须，通常 `bearer`（大小写不敏感）|
| `expires_in` | 建议（秒）|
| `refresh_token` | 可选 |

## 4. 边界条件

### 4.1 表单 vs JSON（实测）

```text
POST /token  data={...}   → 200
POST /token  json={...}   → 422, loc=[["body","username"],["body","password"]]
```

`loc` 前缀是 `body` 而不是 `query`/`form`，因为表单被当成 body 解析。

### 4.2 状态码选择

| 场景 | 建议 | 理由 |
| --- | --- | --- |
| 缺 username/password | 422 | 框架默认 |
| 密码错 | **400** | OAuth2 规范 `invalid_grant`；401 会被客户端当成「token 失效」|
| 停用 | 400 | 同上 |
| 未带 token 访问保护接口 | 401 | 认证缺失 |

### 4.3 `tokenUrl` 的相对性（实测）

`tokenUrl="token"` 原样写进 OpenAPI。含义：

| 部署位置 | 客户端解析结果 |
| --- | --- |
| `/` | `/token` ✅ |
| `/api/v1/` | `/api/v1/token` ✅ |
| 反代前缀改写 | 可能错 ❌ |

要稳定就写绝对路径或按环境注入。

### 4.4 `auto_error=False`（实测）

无 token → `None`；端点用 `token is None` 判断是否匿名。

### 4.5 请求体 schema 是 `$ref`（实测）

`Body_login_token_post`，不是内联 `properties`。写 OpenAPI 断言时要先解 `$ref`。

### 4.6 安全提醒

| 风险 | 处理 |
| --- | --- |
| 明文密码比对 | bcrypt/argon2（第 47 章）|
| 无限尝试 | 限流 + 锁定 |
| token 明文可猜 | 随机不可预测（`secrets.token_urlsafe()`）|
| 密码流用于第三方 | 改授权码 + PKCE |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 前端发 JSON | 422（实测）| urlencoded | 实测 |
| 响应键名驼峰 | 客户端解析失败 | `access_token` | `[O2]` |
| 漏 `token_type` | 客户端报错 | `bearer` | `[O2]` |
| 密码错返回 401 | 前端跳登录死循环 | 400 | `[O2]` |
| `tokenUrl` 相对路径 | 子路径部署后打错 | 绝对路径/注入 | 实测 |
| 忘装 `python-multipart` | 启动报错 | 加依赖 | `[O1]` |
| 以为 `token` 是 dict | `TypeError` | 它是 `str` | 实测 |
| 用 `form.scope` | `AttributeError` | `form.scopes` | 实测 |
| 把密码写日志 | 泄露 | 脱敏 | 规则 |
| 生产用明文密码 | 泄露 | 哈希 | 第 47 章 |
| `auto_error=False` 后不做判断 | 匿名也能进 | 显式判 `None` | 实测 |
| 用 `Security` 与 `Depends` 混写同一方案 | 文档重复 | 统一 | 第 44 章 |
| 自定义 `/token` 路径名 | Authorize 面板 404 | 保持 `tokenUrl` 一致 | `[O1]` |
| 在 `/token` 上加 CSRF 校验 | 客户端调不通 | 表单登录豁免/用 token | `[O3]` |
| token 放 URL | 泄露 | header | `[O3]` |
| 不设过期 | 永久有效 | `exp`（第 47 章）| `[O3]` |
| 登录失败泄露「用户不存在」 | 枚举 | 统一文案 | `[O3]` |
| 只测成功路径 | 422/400 未覆盖 | 各测一条 | 第 71 章 |
| 想在 `OAuth2PasswordRequestForm` 里加自定义字段 | 收不到 | 另写 `Form()` 参数 | `[O1]` |

## 6. 最佳实践与编码建议

### 6.1 登录端点模板

```python
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")   # 绝对路径更稳


@app.post("/token")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> dict[str, str]:
    user = authenticate(form.username, form.password)      # 内部用哈希校验
    if user is None:
        raise HTTPException(400, "用户名或密码错误")
    token = issue_token(user)                              # 第 47 章
    return {"access_token": token, "token_type": "bearer", "expires_in": 1800}
```

| 建议 | 说明 |
| --- | --- |
| `tokenUrl` 用绝对路径 | 子路径安全 |
| 错误文案统一 | 防枚举 |
| 加 `expires_in` | 客户端可续期 |
| 限流 | 防撞库 |
| 用常量类组织表单字段 | 可读 |

### 6.2 选型速查

| 场景 | 做法 |
| --- | --- |
| 内部系统 | 密码流 |
| 第三方登录 | 授权码 + PKCE |
| 机器调用 | API Key（第 49 章）|
| 可选登录 | `auto_error=False` |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[O1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/security/first-steps/ | `OAuth2PasswordBearer` |
| `[O2]` | RFC | https://www.rfc-editor.org/rfc/rfc6749#section-5.1 | 成功响应字段 |
| `[O3]` | RFC | https://www.rfc-editor.org/rfc/rfc6749#section-4.3 | 密码流限制与风险 |

> **核对状态**：`[O1]`–`[O3]` 为官方/RFC 链接，**本次未逐页直连复核**；`oauth2` 方案结构、`tokenUrl` 原样、401 + `Bearer`、缺前缀拒绝、token 剥离、表单 200、JSON 422、400 分支、可选登录、`scope` 拆分、表单默认值、请求体 `$ref` 名均为本机实测，`examples/verify.py` 复现 15/15 通过。`expires_in`/刷新令牌、授权码流**未实现**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 两个对象各自的职责
- [ ] 为什么要 urlencoded
- [ ] `access_token`/`token_type` 的规范
- [ ] 密码错为什么 400
- [ ] `tokenUrl` 相对路径的风险

**能写出（代码层）**：

- [ ] `/token` 表单登录
- [ ] `OAuth2PasswordBearer` 保护端点
- [ ] `auto_error=False` 可选登录
- [ ] `form.scopes` 解析
- [ ] 统一错误文案

**能判断（避坑层）**：

- [ ] 看到 JSON 打 `/token` → 指出 422
- [ ] 看到 401 表示密码错 → 指出前端会死循环
- [ ] 看到 `token["sub"]` → 指出是 str
- [ ] 看到相对 `tokenUrl` → 指出子路径风险
- [ ] 看到明文密码 → 指出必须哈希

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 15/15
- [ ] `/docs` 点 Authorize 用 alice/alice123 登录
- [ ] `curl -d 'username=alice&password=alice123' /token`

## 9. 下一章衔接

第 46 章 `获取当前用户`：把第 45 章拿到的 token 字符串变成用户对象——`decode_token` → `get_current_user`，讲「为什么不能把用户信息塞 token」「依赖链怎么组合」「用户不存在/停用分别返回什么」。

本章留下的伏笔：

1. token → 用户 第 46 章。
2. JWT 签发/校验 第 47 章。
3. `scopes` 参数 第 48 章。
4. `HTTPBasic` / API Key 第 49 章。