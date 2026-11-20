# 46 获取当前用户 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「为什么要两级依赖、token→用户怎么查、401 与 400 怎么分、内部模型怎么不泄露、依赖缓存怎么证明」拆开。学完这章，你要能写出一个不会被枚举、不会泄字段的 `/users/me`。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Pydantic 2.14.1（本机实测） |
| 前置 | 第 45 章（OAuth2 密码流）、第 37 章（依赖缓存）、第 21 章（响应模型） |
| 覆盖范围 | `get_current_user`、`get_current_active_user`、模型分层、错误码、可选用户 |
| 明确不覆盖 | JWT 解码（47）、作用域（48）、刷新令牌、权限矩阵 |
| 学完验收 | 能跑通 `verify.py` 12/12、能解释每层错误码、能证明字段过滤 |

## 0. 怎么用这份文件

**依据约定**：`` `[Un]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 三层职责
2 机制（第 2 节）    → 依赖链
3 API（第 3 节）     → 模型、依赖、别名
4 边界（第 4 节）    → 401/400、枚举、缓存、schema
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 目录组织
```

## 1. 概念：三层各管一件事

| 层 | 负责 | 失败 |
| --- | --- | --- |
| `oauth2_scheme` | header 在不在、前缀对不对 | 401 `Not authenticated` |
| `get_current_user` | token 对应哪个用户 | 401 `无效的 token` |
| `get_current_active_user` | 账号能不能用 | 400 `Inactive user` |

分层的价值：**每层可单独覆盖/测试**（第 41 章），且错误码语义清晰。

## 2. 机制：依赖链

```text
Authorization: Bearer token-alice
 → oauth2_scheme → "token-alice"
 → get_current_user: _TOKENS["token-alice"] = "alice" → _DB["alice"]
 → get_current_active_user: disabled? → 400
 → 端点拿到 User 实例
```

| 事实 | 说明 |
| --- | --- |
| 同请求只跑一次 | 实测 `CALLS == ["get_current_user","get_current_active_user"]` |
| 跨请求不共享 | 两次请求 → 四条 |
| 失败即中断 | 401/400 后端点不执行 |

## 3. API 逐个拆解

### 3.1 模型分层

| 模型 | 字段 | 用途 |
| --- | --- | --- |
| `User` | `username/email/full_name/hashed_password/disabled` | 内部 |
| `UserOut` | 去掉 `hashed_password` | 响应 |
| `Token` | `access_token/token_type` | `/token` |

实测 `components.schemas` 只有 `UserOut`、`Token`，**没有 `User`**——因为 `User` 从未用作 `response_model` 或请求体。

### 3.2 `get_current_user`

```python
async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    ...
```

| 设计点 | 选择 | 理由 |
| --- | --- | --- |
| 用 `async def` | 是 | 后续查库是 IO |
| 失败 401 | 是 | 认证问题 |
| 文案统一 | 是 | 防枚举 |

### 3.3 别名

```python
CurrentUserDep = Annotated[User, Depends(get_current_user)]
ActiveUserDep = Annotated[User, Depends(get_current_active_user)]
```

第 38 章的 `type X = ...` 也可用；`= Annotated[...]` 兼容更低版本。

### 3.4 可选用户

```python
oauth2_optional = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

async def get_optional_user(token: Annotated[str | None, Depends(oauth2_optional)]) -> User | None:
    ...
```

实测匿名 → `{"message":"你好，游客"}`，登录 → `"你好，Alice Chen"`。

## 4. 边界条件

### 4.1 401 vs 400（实测）

| 情况 | 状态码 | detail |
| --- | --- | --- |
| 没带 header | 401 | `Not authenticated` |
| `Bearer nope` | 401 | `无效的 token` |
| 停用账号 | 400 | `Inactive user` |

### 4.2 防枚举（实测）

`alice` 密码错与 `ghost` 不存在返回**完全相同**的 `{"detail": "用户名或密码错误"}`。

### 4.3 字段泄露（实测）

`/users/me/raw` 里 `sorted(user.model_dump())` 含 `hashed_password`。这就是「不加 `response_model` 会出事」的直接证据。

### 4.4 响应注解也会校验（实测）

初版 `/users/me/name` 注解 `dict[str, str]` 但返回 `calls: int` → **500 `ResponseValidationError`**（`loc=("response","calls")`）。返回注解不是装饰，是会校验的。

### 4.5 缓存证明

`CALLS` 列表是全局的，验收里必须 `clear()`；否则断言会被前面的用例污染。

### 4.6 `EmailStr` 的隐性依赖

`UserOut.email: EmailStr` 需要 `email-validator`，否则启动即报错。这是最容易被忽略的「运行期依赖」。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| token 无效返回 404 | 用户枚举 | 401 | `[U3]` |
| 停用返回 401 | 前端死循环 | 400/403 | `[U1]` |
| 返回内部模型 | 泄露哈希 | `response_model=UserOut` | 实测 |
| 用户名不存在单独文案 | 枚举 | 同文案 | `[U3]` |
| 401 无 challenge | 客户端无指引 | `WWW-Authenticate` | `[U2]` |
| 日志打密码/token | 泄露 | 脱敏 | `[U3]` |
| 用户信息塞 token | 可伪造/变大 | 只放 `sub` | 第 47 章 |
| 用 dict 当用户 | 字段拼错不报错 | `BaseModel` | `[U1]` |
| 忘 `email-validator` | 启动报错 | 加依赖 | 实测 |
| 返回注解与数据不符 | 500 `ResponseValidationError` | 注解写准 | 实测 |
| 依赖里再 `Depends(oauth2_scheme)` | 重复声明 | 复用缓存 | 第 37 章 |
| `auto_error=False` 后不判 None | 匿名进保护逻辑 | 显式判断 | 实测 |
| 在路由里手工解析 header | 重复代码/易错 | 用方案对象 | `[U2]` |
| 用 GET 传 token | 进日志 | header | `[U3]` |
| 停用用户仍发 token | 登录成功却用不了 | 登录时就拒 | 第 45 章 |
| 只测 200 | 401/400 未覆盖 | 三条都测 | 第 71 章 |
| 全局 `CALLS` 不清理 | 断言污染 | `clear()` | 实测 |
| 把 `User` 当 `UserOut` 用 | 泄露 | 明确分工 | 实测 |
| 在依赖里改 `user.disabled` 等字段 | 共享对象被污染 | 返回副本/不可变模型 | `[U1]` |

## 6. 最佳实践与编码建议

### 6.1 目录组织

```text
app/
  core/security.py     # oauth2_scheme、decode_token
  models/user.py       # User / UserOut / Token
  api/deps.py          # get_current_user / ActiveUserDep
  api/routes/users.py  # /users/me
```

| 建议 | 说明 |
| --- | --- |
| 依赖放 `deps.py` | 一处 import |
| 内部/外部模型分开 | 防泄露 |
| 错误码集中定义 | 前端可枚举 |
| 用别名复用 | 第 38 章 |
| 依赖 `async` | 便于查库 |

### 6.2 错误码约定

| 场景 | 码 | 前端动作 |
| --- | --- | --- |
| 没 token | 401 | 跳登录 |
| token 过期/无效 | 401 + `invalid_token` | 刷新或跳登录 |
| 账号停用 | 403 | 提示联系管理员 |
| 无权限 | 403 | 提示 |

### 6.3 选型速查

| 需求 | 做法 |
| --- | --- |
| 必须登录 | `ActiveUserDep` |
| 可选登录 | `get_optional_user` |
| 只校验不取用户 | `dependencies=[Depends(...)]`（第 39 章）|
| 多角色 | 再加一层依赖（第 48 章）|

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[U1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/security/get-current-user/ | `get_current_user` |
| `[U2]` | RFC | https://www.rfc-editor.org/rfc/rfc6750#section-3 | Bearer 与 401 challenge |
| `[U3]` | 安全指南 | https://cheatsheetseries.owasp.org/cheatsheets/Authentication_Cheat_Sheet.html | 枚举防护 |

> **核对状态**：`[U1]`–`[U3]` 为官方/RFC/指南链接，**本次未逐页直连复核**；`/users/me` 三字段、401 两种文案、400 停用、密码错同文案、依赖链各一次、跨请求不缓存、`model_dump` 含哈希、schema 无 `User`、security 引用、可选登录均为本机实测，`examples/verify.py` 复现 12/12 通过。真实数据库查询与并发**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 三层职责与错误码
- [ ] 为什么 token 无效不用 404
- [ ] `User` 与 `UserOut` 的分工
- [ ] 依赖缓存的作用域
- [ ] 返回注解也会校验

**能写出（代码层）**：

- [ ] `get_current_user`
- [ ] `get_current_active_user`
- [ ] `response_model=UserOut`
- [ ] 可选用户依赖
- [ ] 统一错误文案

**能判断（避坑层）**：

- [ ] 看到返回内部模型 → 指出泄露
- [ ] 看到 404 表示 token 无效 → 指出枚举
- [ ] 看到停用 401 → 指出前端死循环
- [ ] 看到注解与数据不符 → 指出 500
- [ ] 看到忘 `email-validator` → 指出启动失败

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 12/12
- [ ] `/docs` 登录后调 `/users/me`
- [ ] `curl` 无效 token 看 challenge

## 9. 下一章衔接

第 47 章 `JWT 实现`：把 `_TOKENS` 映射表换成真正签名的 JWT——`header.payload.signature`、HS256 用 `hmac`+`hashlib` 手写、`exp` 过期校验、`sub` 存用户名，以及为什么生产该用 PyJWT。

本章留下的伏笔：

1. token 真实性 第 47 章。
2. `sub` 字段 第 47 章。
3. `scopes` 第 48 章。
4. 密码哈希 第 47 章末尾。