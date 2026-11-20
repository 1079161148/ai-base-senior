# 47 JWT 实现（HS256） · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「三段怎么拼、签名输入是什么、为什么必须校 `alg`、`exp` 的边界、手写与 PyJWT 的差距」拆开。学完这章，你要能读懂任何 JWT，并知道手写版缺什么。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0（本机实测） |
| 前置 | 第 45–46 章（OAuth2、当前用户）、`hmac`/`hashlib` 基础 |
| 覆盖范围 | JWT 结构、HS256 签名/验签、`alg` 白名单、`exp`、密码哈希、常见攻击 |
| 明确不覆盖 | RS256/ES256、JWKS 轮换、刷新令牌完整方案、`aud`/`iss` 多租户校验 |
| 学完验收 | 能跑通 `verify.py` 14/14、能手工构造/破解测试 token、能列出手写版缺失项 |

## 0. 怎么用这份文件

**依据约定**：`` `[Jn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 三段是什么
2 机制（第 2 节）    → 签名/验签
3 API（第 3 节）     → 签发、校验、密码
4 边界（第 4 节）    → 攻击类型、过期、时钟
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 生产方案
```

## 1. 概念：签名不是加密

| 段 | 明文内容 | 谁能读 |
| --- | --- | --- |
| header | 算法、类型 | 任何人 |
| payload | `sub`/`exp`/自定义 | 任何人 |
| signature | HMAC 摘要 | 任何人（但不可伪造）|

实测：`/debug/payload` 不验签就返回 `{"sub":"alice","exp":...}`。

**推论**：JWT 里不放密码、手机号、内部角色矩阵——要放就加密（JWE）或只放 id。

## 2. 机制：签名与验签

```text
signing_input = base64url(header) + "." + base64url(payload)
signature     = base64url(HMAC-SHA256(secret, signing_input))
token         = signing_input + "." + signature
```

| 环节 | 关键点 |
| --- | --- |
| 编码 | `base64.urlsafe_b64encode` + 去掉 `=` |
| 解码 | 补齐 padding 再 `urlsafe_b64decode` |
| 比较 | `hmac.compare_digest`（常量时间）|
| JSON | `separators=(",", ":")`，`sort_keys` 保证可复现 |

实测：token 147 字符、无 `=` 填充、三段。

## 3. API 逐个拆解

### 3.1 签发

```python
payload = {"sub": "alice", "iat": now, "exp": now + ttl}
```

| claim | 含义 | 备注 |
| --- | --- | --- |
| `sub` | 主体（用户名/id）| 不要放对象 |
| `iat` | 签发时间 | 秒 |
| `exp` | 过期时间 | 秒；必校验 |
| `jti` | 唯一 id | 撤销用（本章未实现）|
| `aud`/`iss` | 受众/签发方 | 多服务必须校验 |

### 3.2 校验顺序（重要）

| 步骤 | 失败 |
| --- | --- |
| 1 段数 = 3 | `token 必须是三段` |
| 2 `alg` 在白名单 | `不支持的算法 'none'` |
| 3 签名一致 | `签名不符` |
| 4 `exp` 存在且未过 | `缺少 exp` / `已过期` |

**顺序不能换**：先验签再读 payload，否则你会信任未经验证的数据。

### 3.3 密码哈希

```python
salt = secrets.token_hex(16)
dk = hashlib.pbkdf2_hmac("sha256", password.encode(), bytes.fromhex(salt), 100_000)
stored = f"pbkdf2_sha256${salt}${dk.hex()}"
```

| 要点 | 说明 |
| --- | --- |
| 随机 salt | 实测同密码两次哈希不同 |
| 迭代次数 | 10 万起，可调 |
| 比较 | `compare_digest` |
| 生产 | 用 `bcrypt`/`argon2-cffi`/`passlib` |

## 4. 边界条件

### 4.1 篡改（实测）

改 `sub` 保留原签名 → `签名不符`。这就是签名的全部价值。

### 4.2 `alg: none`（实测）

我构造了 `{"alg":"none"}` + 空签名 → 被 `不支持的算法 'none'` 拒绝。**若省略第 2 步**，这类 token 会直接通过（经典漏洞）。

### 4.3 过期（实测）

`/token/expired` 签发 `exp = now - 1` → 401 `已过期`，与签名错区分。

### 4.4 异密钥（实测）

换 `secret` 签的 token → `签名不符`。

### 4.5 时钟偏差

分布式系统里校验方与签发方时钟可能差几秒。工程上常允许 `leeway=5~30s`。本章**未实现**。

### 4.6 手写版缺什么

| 缺项 | 影响 |
| --- | --- |
| `jti` 撤销 | token 泄漏后无法提前失效 |
| `aud`/`iss` 校验 | 跨服务 token 混用 |
| RS256/ES256 | 无法让第三方只验不签 |
| `leeway` | 时钟偏差误拒 |
| 密钥轮换（kid）| 换密钥要全量重登 |
| 解析健壮性 | 畸形 JSON/base64 边界 |

结论：**生产用 PyJWT**，本章代码只用于理解。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 不校验 `alg` | `none` 算法绕过 | 白名单 | 实测 |
| 用 `==` 比签名 | 时序侧信道 | `compare_digest` | `[J2]` |
| 以为 JWT 加密 | 敏感信息泄露 | 只放 id | 实测 |
| 把密码放 payload | 明文可见 | 绝不放 | `[J3]` |
| 不校验 `exp` | 永不过期 | 必校验 | `[J1]` |
| `exp` 用毫秒 | 校验恒真 | 用秒 | 实测 |
| 手写实现上生产 | 边界漏 | PyJWT | `[J1]` |
| 密钥硬编码 | 泄露 | 环境变量 | 规则 |
| 密钥 < 32 字节 | 可暴力 | 随机 ≥32B | `[J2]` |
| 明文存密码 | 拖库失守 | 哈希 + salt | `[J3]` |
| 用 JWT 存大对象 | 请求头膨胀 | 只放 `sub` | `[J1]` |
| `sub` 放 email 又允许改邮箱 | 授权漂移 | 放不可变 id | `[J1]` |
| 不校验 `aud` | 跨服务混用 | 校验 | `[J1]` |
| token 放 URL | 日志泄露 | header | `[J3]` |
| 无 `leeway` | 时钟偏差误拒 | 允许几秒 | `[J1]` |
| 忽略 `typ` | 接受非 JWT | 校验 | `[J1]` |
| 退出登录只前端删 token | 服务端仍有效 | 短 TTL + 黑名单 | `[J3]` |
| 只测成功路径 | 攻击面未覆盖 | 篡改/过期/异密钥 | 第 71 章 |
| base64 解码不补 padding | `binascii.Error` | 补齐 `=` | `[J1]` |

## 6. 最佳实践与编码建议

### 6.1 生产版（PyJWT）

```python
import jwt
from datetime import datetime, timedelta, timezone

SECRET = settings.jwt_secret          # 从环境变量读
ALGORITHM = "HS256"


def create_access_token(sub: str, minutes: int = 30) -> str:
    now = datetime.now(timezone.utc)
    return jwt.encode(
        {"sub": sub, "iat": now, "exp": now + timedelta(minutes=minutes)},
        SECRET,
        algorithm=ALGORITHM,
    )


def decode_token(token: str) -> dict:
    return jwt.decode(
        token,
        SECRET,
        algorithms=[ALGORITHM],       # 白名单，PyJWT 用它防 none
        options={"require": ["exp", "sub"]},
        leeway=10,
    )
```

| 建议 | 说明 |
| --- | --- |
| 短 TTL + 刷新令牌 | 降低泄漏窗口 |
| 只放 `sub`/`scopes` | 体积与安全 |
| `algorithms=[...]` | 必须显式 |
| `require=["exp"]` | 防无过期 token |
| 密钥走配置 | 可轮换 |

### 6.2 选型速查

| 场景 | 算法 |
| --- | --- |
| 单体/内部服务 | HS256 |
| 第三方需验签 | RS256/ES256 |
| 需要撤销 | 短期 token + 黑名单/`jti` |
| 需要加密载荷 | JWE（另一套）|

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[J1]` | RFC | https://www.rfc-editor.org/rfc/rfc7519 | JWT 结构与 claims |
| `[J2]` | RFC | https://www.rfc-editor.org/rfc/rfc7515#section-5.2 | JWS 与 `alg` 校验 |
| `[J3]` | 安全指南 | https://cheatsheetseries.owasp.org/cheatsheets/JSON_Web_Token_for_Java_Cheat_Sheet.html | 常见 JWT 攻击 |

> **核对状态**：`[J1]`–`[J3]` 为 RFC/指南链接，**本次未逐页直连复核**；三段结构、无填充、147 长度、`alg`/claims、payload 明文可解、签名错、篡改 payload、`alg=none` 拒绝、过期、异密钥、challenge 头、salt 随机、`expires_in` 均为本机实测，`examples/verify.py` 复现 14/14 通过。`leeway`、`jti` 撤销、`aud`/`iss`、密钥轮换**未实现**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 三段各是什么、签名输入是什么
- [ ] 为什么 payload 不算机密
- [ ] `alg=none` 攻击原理
- [ ] `compare_digest` 的必要性
- [ ] 手写版与 PyJWT 的差距

**能写出（代码层）**：

- [ ] 签发（`sub`/`iat`/`exp`）
- [ ] 校验（段数/alg/签名/exp）
- [ ] 密码哈希与校验
- [ ] 401 + `invalid_token`
- [ ] 手工构造过期 token

**能判断（避坑层）**：

- [ ] 看到不校验 alg → 指出致命
- [ ] 看到 `==` 比签名 → 指出时序
- [ ] 看到敏感信息进 payload → 指出明文
- [ ] 看到毫秒 `exp` → 指出校验恒真
- [ ] 看到手写 JWT 上生产 → 指出缺项

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 14/14
- [ ] `/debug/payload` 看明文
- [ ] 手动改一个字符看 401

## 9. 下一章衔接

第 48 章 `作用域授权`：`SecurityScopes` + `OAuth2PasswordBearer(scopes={...})`，让同一个端点支持「普通用户可读、管理员可写」，讲 `scopes` 在 token 里怎么带、`SecurityScopes` 怎么合并、403 文案里 `WWW-Authenticate: Bearer scope="..."` 的写法。

本章留下的伏笔：

1. `scopes` claim 第 48 章。
2. `SecurityScopes` 第 48 章。
3. Basic/API Key 第 49 章。