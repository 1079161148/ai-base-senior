# 49 API Key 与 Basic 认证 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「三种 key 位置怎么选、Basic 的协议细节、为什么必须 `compare_digest`、轮换与存储怎么做、cookie 方案的 CSRF」拆开。学完这章，你要能给机器调用和内部工具各配一套合适的认证。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0（本机实测） |
| 前置 | 第 44 章（`Security`）、第 47 章（哈希与比较） |
| 覆盖范围 | `APIKeyHeader/Query/Cookie`、`HTTPBasic`、比较与轮换、CSRF |
| 明确不覆盖 | OAuth2（45–48）、mTLS、签名（HMAC 请求签名）方案 |
| 学完验收 | 能跑通 `verify.py` 14/14、能选对位置、能写出不泄露的校验 |

## 0. 怎么用这份文件

**依据约定**：`` `[Kn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 机器 vs 人
2 机制（第 2 节）    → 取 key / 解 Basic
3 API（第 3 节）     → 四种方案
4 边界（第 4 节）    → 401 头、轮换、CSRF、时序
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 存储与轮换
```

## 1. 概念：两种场景两套方案

| 场景 | 方案 | 生命周期 | 泄漏后果 |
| --- | --- | --- | --- |
| 服务间调用 | API Key | 长期（可轮换）| 需吊销 + 审计 |
| 内部工具人登录 | Basic | 每次请求带密码 | 严重（密码）|
| 前端用户 | OAuth2/JWT（45–48）| 短期 | 可过期 |

**Basic 不适合浏览器前端**：密码每次随请求走，且无法精细撤销。

## 2. 机制

```text
机器：
  X-API-Key: key-service-a
  → APIKeyHeader 取字符串 → 你查表比对 → owner

人：
  Authorization: Basic YWxpY2U6YWxpY2UxMjM=
  → HTTPBasic 校验前缀 + base64 解码 → HTTPBasicCredentials(username, password)
  → 你比对密码哈希
```

| 事实 | 说明 |
| --- | --- |
| Basic 的 base64 可逆 | 实测解出 `alice:alice123` |
| `realm` 进 challenge | 实测 `Basic realm="ch49-demo"` |
| 方案层拒绝用 401 | 实测 `Not authenticated` |

## 3. API 逐个拆解

### 3.1 三种 key 位置

| 类 | 参数名 | 适用 | 风险 |
| --- | --- | --- | --- |
| `APIKeyHeader` | `name="X-API-Key"` | **推荐** | 低 |
| `APIKeyQuery` | `name="api_key"` | 临时调试 | 进日志/Referer |
| `APIKeyCookie` | `name="session_key"` | 浏览器会话 | CSRF |

实测三者 OpenAPI 分别是 `in: header/query/cookie`。

### 3.2 `HTTPBasic`

```python
basic = HTTPBasic(realm="ch49-demo", scheme_name="BasicAuth")
creds: Annotated[HTTPBasicCredentials, Security(basic)]
```

| 参数 | 作用 |
| --- | --- |
| `realm` | challenge 里的提示域 |
| `scheme_name` | `securitySchemes` 键名（实测按此生成 `BasicAuth`）|
| `auto_error` | 缺凭证是否自动 401 |

### 3.3 比较

```python
if not secrets.compare_digest(candidate, provided):
    ...
```

| 要点 | 说明 |
| --- | --- |
| 常量时间 | 不因前缀匹配提前返回 |
| 用户不存在也比对 | 用哨兵值，防时序枚举 |
| 长度不同 | `compare_digest` 对 `str` 仍会因长度不同快速返回；必要时先哈希再比 |

## 4. 边界条件

### 4.1 401 的 `WWW-Authenticate`（实测）

| 方案 | 值 |
| --- | --- |
| `APIKeyHeader` 缺 | `APIKey` |
| 自己抛 | 你写什么是什么（示例 `ApiKey`）|
| `HTTPBasic` 缺 | `Basic realm="ch49-demo"` |

**注意大小写**：方案层给的是 `APIKey`。

### 4.2 `auto_error` 只能写在方案上（实测）

```python
Security(api_key_header, auto_error=False)
# TypeError: Security() got an unexpected keyword argument 'auto_error'
```

正确：`APIKeyHeader(name="X-API-Key", auto_error=False)`。

### 4.3 轮换（实测）

```python
_API_KEYS = {"key-service-a": "service-a", "key-service-a-old": "service-a"}
```

旧 key 仍映射到同一 owner → 客户端可分批切换。

### 4.4 CSRF（cookie 方案）

cookie 会自动随请求发送，若同时允许跨站表单提交就有 CSRF 风险。措施：`SameSite=Lax/Strict`、CSRF token、只接受 `application/json`（简单请求限制）。

### 4.5 Basic 与 HTTPS

base64 不加密。任何明文 HTTP 抓包都能还原密码。**必须 TLS**。

### 4.6 `HTTPBasicCredentials` 的坑

`creds.username`/`.password` 来自 base64 解码，**可能包含任意字节**（非 UTF-8 时会解码失败 → 401）。不要直接拼 SQL/日志。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `Security(..., auto_error=False)` | `TypeError`（实测）| 方案对象上设 | 实测 |
| 用 `==` 比密码 | 时序侧信道 | `compare_digest` | `[K2]` |
| 用户不存在直接 return | 时间差枚举 | 哨兵比对 | `[K2]` |
| 401 无 challenge | 浏览器不弹框 | 加头 | `[K1]` |
| key 放 query | 日志泄露 | header | `[K3]` |
| key 硬编码 | 泄露 | 环境变量 | 规则 |
| 单 key 无轮换 | 换 key 停机 | 新旧并存 | `[K3]` |
| Basic 走 HTTP | 明文密码 | HTTPS | `[K1]` |
| cookie 无 `SameSite` | CSRF | 设置 | `[K4]` |
| cookie 无 CSRF token | 伪造请求 | 双提交/同步令牌 | `[K4]` |
| 把 Basic 当会话 | 密码每请求 | 换 JWT/session | `[K1]` |
| 明文存密码 | 拖库失守 | 哈希 | 第 47 章 |
| key 明文入库 | 泄露 | 存哈希/前缀索引 | `[K3]` |
| 401 文案回显收到的 key | 泄露 | 只说无效 | `[K3]` |
| 忽略大小写差异 | 客户端认证失败 | 按方案实际值 | 实测 |
| 用 `Depends` 声明方案 | 文档无 scheme | 用 `Security` | 第 44 章 |
| 一个端点挂两个必需方案 | 要同时满足 | 明确 OR/AND | 第 44 章 |
| 只在 /docs 测 | 环境差异 | 写 verify | 第 71 章 |
| 把 Basic 用户名打进日志 | 账号枚举 | 只记 id/脱敏 | `[K3]` |

## 6. 最佳实践与编码建议

### 6.1 Key 存储

| 方案 | 说明 |
| --- | --- |
| 存 `sha256(key)` | 校验时哈希比对；不可逆 |
| 存前缀 + 哈希 | 便于展示「key-service-a…」|
| 定期轮换 | 90 天或按事件 |
| 每 key 限权 | 绑定 scope/租户 |

```python
import hashlib, secrets

def key_fingerprint(raw: str) -> str:
    return hashlib.sha256(raw.encode()).hexdigest()

def verify_key(raw: str, stored_hash: str) -> bool:
    return secrets.compare_digest(key_fingerprint(raw), stored_hash)
```

### 6.2 选型速查

| 需求 | 方案 |
| --- | --- |
| 服务间 | `APIKeyHeader` |
| 浏览器会话 | cookie + CSRF / JWT |
| CI/脚本 | `APIKeyHeader` + 环境变量 |
| 内网简单登录 | `HTTPBasic` + HTTPS |
| 第三方 | OAuth2 授权码 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[K1]` | RFC | https://www.rfc-editor.org/rfc/rfc7617 | HTTP Basic |
| `[K2]` | 文档 | https://docs.python.org/3/library/secrets.html#secrets.compare_digest | 常量时间比较 |
| `[K3]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/security/ | API Key 方案 |
| `[K4]` | 指南 | https://cheatsheetseries.owasp.org/cheatsheets/Cross-Site_Request_Forgery_Prevention_Cheat_Sheet.html | CSRF |

> **核对状态**：`[K1]`–`[K4]` 为 RFC/官方/指南链接，**本次未逐页直连复核**；四种 scheme 字段、`APIKey` challenge 大小写、`Basic realm`、轮换、`auto_error` TypeError、Basic base64 可逆、OR 组合、源码含 `compare_digest` 均为本机实测，`examples/verify.py` 复现 14/14 通过。CSRF 实际攻击、key 哈希存储、速率限制**未实现**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 三种 key 位置的取舍
- [ ] Basic 的 base64 与 TLS 关系
- [ ] `compare_digest` 防什么
- [ ] 轮换为什么需要双 key
- [ ] cookie 方案的 CSRF 来源

**能写出（代码层）**：

- [ ] `APIKeyHeader` + 查表
- [ ] `HTTPBasic` + 哨兵比对
- [ ] 正确的 401 challenge
- [ ] 轮换表
- [ ] OR 组合（`auto_error=False`）

**能判断（避坑层）**：

- [ ] 看到 `Security(auto_error=)` → 指出 TypeError
- [ ] 看到 `==` 比密码 → 指出时序
- [ ] 看到 query 传 key → 指出日志泄露
- [ ] 看到 Basic 上 HTTP → 指出明文
- [ ] 看到单 key → 指出轮换困难

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 14/14
- [ ] `/docs` 里三种 Authorize 都试一遍
- [ ] `curl -u alice:alice123` 看 200

## 9. M07 小结与下一章

M07（44–49）走完了安全认证主线：`Security`/`securitySchemes` → OAuth2 密码流 → 当前用户 → JWT → 作用域 → API Key/Basic。共同骨架是**方案对象取凭证 + 依赖校验 + 401/403 语义 + 文档登记**。

下一模块 M08 `中间件`（50–53）：`@app.middleware("http")`、`call_next`、`BaseHTTPMiddleware` 的限制、CORS、GZip、可信主机。第 44 章提到的「全局依赖不保护 `/docs`」在那里会得到正面解决。