# 44 安全总览（Security / securitySchemes） · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「安全方案对象做了什么、`Security` 与 `Depends` 差在哪、`securitySchemes` 怎么生成、缺凭证为什么是 401、多方案 OR/AND 的语义」拆开。学完这章，你要能在 `/docs` 里看到正确的 Authorize，并知道它只是文档，不是防护。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0（本机实测）/ OpenAPI 3.1 |
| 前置 | 第 35–39 章（依赖、装饰器、全局依赖） |
| 覆盖范围 | 安全方案对象、`Security` 对比 `Depends`、`securitySchemes`、`scheme_name`、OR 语义、全局安全 |
| 明确不覆盖 | OAuth2 流程（45）、JWT 签发（47）、作用域（48）、Basic/APIKey 细节（49）|
| 学完验收 | 能跑通 `verify.py` 14/14、能解释 401 来源、能写出 OR 语义 |

## 0. 怎么用这份文件

**依据约定**：`` `[Sn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 方案对象 vs 校验函数
2 机制（第 2 节）    → 凭证抽取 + 文档登记
3 API（第 3 节）     → 各类方案、scheme_name、auto_error
4 边界（第 4 节）    → 401/403、OR/AND、默认值、全局
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 双通道鉴权模板
```

## 1. 概念：方案对象只做「取凭证 + 记文档」

| 角色 | 职责 | 例子 |
| --- | --- | --- |
| 方案对象（`APIKeyHeader` 等）| 从请求取凭证；缺了按 `auto_error` 拒绝；写 `securitySchemes` | `api_key_scheme` |
| 校验函数（自己写）| 判值、查库、抛 401/403 | `verify_key` |
| `Security(...)` | 把两者接起来，并让 OpenAPI 记录 | — |

**方案对象不做业务校验**。它不知道「key 是否有效」，只管「头在不在、格式对不对」。

## 2. 机制：两条路径

```text
请求 → 方案对象取值
        ├─ 取到 → 传给校验函数 → 你的逻辑（200/401/403）
        └─ 取不到且 auto_error=True → 401 {"detail":"Not authenticated"}（不进你的函数）

文档 → Security(...) 标记
        → components.securitySchemes[键名] = {type, in, name ...}
        → path.operation.security = [{键名: []}]
```

| 事实 | 说明 |
| --- | --- |
| 401 来自方案层 | 缺凭证时你的函数根本没跑（实测 `Basic` 打 bearer 端点，函数未调用）|
| `security` 是路由级 | 子依赖里的 `Security` 会合并到路由 |
| 键名可覆盖 | `scheme_name="BearerAuth"` |

## 3. API 逐个拆解

### 3.1 方案对象清单

| 类 | 位置 | OpenAPI |
| --- | --- | --- |
| `APIKeyHeader(name=...)` | header | `{"type":"apiKey","in":"header","name":...}` |
| `APIKeyQuery(name=...)` | query | `in: query` |
| `APIKeyCookie(name=...)` | cookie | `in: cookie` |
| `HTTPBearer()` | header | `{"type":"http","scheme":"bearer"}` |
| `HTTPBasic()` | header | `{"type":"http","scheme":"basic"}` |
| `OAuth2PasswordBearer(tokenUrl=...)` | header | `{"type":"oauth2","flows":{...}}` |

### 3.2 `Security` 的两种位置

```python
# 参数位置：能拿返回值
def me(user: Annotated[str, Security(verify_key)]): ...

# 装饰器位置：只校验
@app.get("/audit", dependencies=[Security(api_key_scheme)])
def audit(): ...
```

实测：装饰器位置也写入 `security`，但端点拿不到 key。

### 3.3 `security` vs `securitySchemes`

| 字段 | 位置 | 作用 |
| --- | --- | --- |
| `components.securitySchemes` | 全局定义 | 方案「是什么」 |
| `paths./x.get.security` | 每个操作 | 这个接口「用哪个」 |

实测 `/plain` 完全没有 `security` 键（`operation.get("security") is None`）。

### 3.4 `auto_error`

| 值 | 缺凭证时 |
| --- | --- |
| `True`（默认）| 方案直接 401 `Not authenticated` |
| `False` | 返回 `None`，由你决定 |

`auto_error=False` 是「可选登录」「OR 语义」的唯一正路。

## 4. 边界条件

### 4.1 401 而不是 403（实测）

```text
GET /key（无头） → 401 {"detail": "Not authenticated"}
GET /bearer（无头） → 401 {"detail": "Not authenticated"}
```

大量旧教程写 403，是历史行为（旧版 `HTTPBearer`/`APIKey*` 缺凭证返回 403）。**以你的实际版本为准，别照抄断言**。

### 4.2 scheme 不符先被拒（实测）

`Authorization: Basic token-1` 打 `/bearer` → 401 `Not authenticated`，`verify_bearer` 里的 `creds.scheme` 检查根本没机会执行。

### 4.3 OR 语义（实测）

两个方案写成两个 `Security`：

```json
"security": [{"APIKeyHeader": []}, {"BearerAuth": []}]
```

数组里每个对象是「一个可选方案」，**对象之间 OR**；同一对象里多个键才是 AND。实测 `/either-or` 只有 key 或只有 bearer 都 200。

### 4.4 默认值不会让依赖变可选（实测）

```python
def read_either(key_user: Annotated[str | None, Security(verify_key)] = None): ...
```

无头仍 401，因为 `verify_key` 内部声明了必需的 `Security(api_key_scheme)`。要可选只能用 `auto_error=False`。

### 4.5 全局安全（实测）

`FastAPI(dependencies=[Security(global_guard)])` → `securitySchemes` 有方案，`/g` 的 `security` 也有条目。但它**不保护 `/docs`**（与第 39 章全局依赖一致）。

### 4.6 `/docs` 的 Authorize

实测 `/docs` 200 且含 `swagger-ui`。按钮本身是前端行为，`verify` 只能断言 OpenAPI 侧字段；按钮可用性**未自动化验证**。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 断言缺凭证是 403 | 测试失败（实测 401）| 按实际版本断言 | 实测 |
| 用 `Depends`+`Header` 想要锁图标 | 文档无 security | 用 `Security` | 实测 |
| 参数 `= None` 以为可选 | 仍 401 | `auto_error=False` | 实测 |
| 以为多 `Security` 是 AND | 实际 OR | 手改 OpenAPI 要 AND | 实测 |
| 方案对象里写业务逻辑 | 职责混乱 | 拆校验函数 | `[S1]` |
| 401 不带 `WWW-Authenticate` | 客户端无指引 | 加头 | `[S1]` |
| token 放 query | 进日志/历史 | header | `[S3]` |
| 不传 `scheme_name` | 键名随类名漂移 | 显式命名 | 实测 |
| 用安全方案当唯一防护 | `/docs` 不受全局保护 | 参数/中间件 | 第 39 章 |
| 只测 OR 的一条分支 | 另一条没覆盖 | 两条都测 | 第 71 章 |
| 把 key 硬编码在代码 | 泄露 | 环境变量 + 哈希 | 规则 |
| 401 文案回显收到的 key | 泄露 | 只说「无效」 | `[S3]` |
| `BaseHTTPMiddleware` 里再校验 | 绕过依赖缓存 | 统一在依赖 | 第 46 章 |
| 多方案共用一个 `scheme_name` 但字段不同 | 定义被覆盖 | 每个方案独立命名 | `[S2]` |
| 用 `securitySchemes` 手写覆盖框架生成 | 漂移 | 让框架生成 | `[S2]` |
| cookie 方案不设 `SameSite` | CSRF 风险 | 见第 49 章 | `[S3]` |
| 401 与 422 混淆 | 客户端处理错 | 401 是认证、422 是校验 | 第 31 章 |
| 只在 `/docs` 里点 Authorize 测试 | 环境差异漏测 | 写 `verify.py` | 第 71 章 |
| 用 `APIKeyQuery` 又开详细访问日志 | 凭证进日志 | 用 header + 脱敏 | `[S3]` |

## 6. 最佳实践与编码建议

### 6.1 双通道鉴权模板

```python
from typing import Annotated, Any

from fastapi import FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPBearer, HTTPAuthorizationCredentials

app = FastAPI()

api_key_scheme = APIKeyHeader(name="X-API-Key", scheme_name="ApiKeyAuth", auto_error=False)
bearer_scheme = HTTPBearer(scheme_name="UserToken", auto_error=False)

API_KEYS = {"key-alice": "alice"}


def resolve_identity(
    key: Annotated[str | None, Security(api_key_scheme)] = None,
    creds: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_scheme)] = None,
) -> str:
    """机器用 API Key，人用 Bearer token，二选一"""
    if key and (user := API_KEYS.get(key)):
        return user
    if creds and creds.credentials == "token-1":
        return "alice"
    raise HTTPException(401, "需要 X-API-Key 或 Bearer token", headers={"WWW-Authenticate": "Bearer"})


IdentityDep = Annotated[str, Security(resolve_identity)]
```

| 建议 | 说明 |
| --- | --- |
| 每个方案显式 `scheme_name` | 前端配置稳定 |
| 401 带 `WWW-Authenticate` | 标准 |
| 方案对象只取凭证 | 可测试 |
| 多通道写在一个依赖里 | 一处维护 |
| 用 `verify.py` 断言 OpenAPI | 防文档回退 |

### 6.2 选型速查

| 场景 | 方案 |
| --- | --- |
| 服务间调用 | `APIKeyHeader` |
| 用户登录 | `OAuth2PasswordBearer`（45）|
| 内部简单登录 | `HTTPBasic`（49）|
| 可选登录 | `auto_error=False` |
| 多通道 | 多个 `Security`（OR）|

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[S1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/security/ | 安全总览 |
| `[S2]` | 规范 | https://spec.openapis.org/oas/v3.1.0#security-scheme-object | `securitySchemes` 字段 |
| `[S3]` | 安全指南 | https://cheatsheetseries.owasp.org/cheatsheets/Transport_Layer_Security_Cheat_Sheet.html | 凭证传输 |

> **核对状态**：`[S1]`–`[S3]` 为官方/规范链接，**本次未逐页直连复核**；`securitySchemes` 两个方案的字段、`scheme_name` 生效、路由 `security` 引用、装饰器位置登记、`Depends` 不登记、缺凭证 401、错 scheme 先拒、OR 语义、默认值不跳过、全局 Security 登记、`/docs` 200 均为本机实测，`examples/verify.py` 复现 14/14 通过。AND 语义手改 OpenAPI、Authorize 按钮交互**未自动化验证**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 方案对象与校验函数的职责分界
- [ ] `Security` 与 `Depends` 的唯一差别
- [ ] `securitySchemes` 与 `security` 的关系
- [ ] 缺凭证为什么是 401
- [ ] OR/AND 在 OpenAPI 里的表示

**能写出（代码层）**：

- [ ] `APIKeyHeader` + 校验函数
- [ ] `HTTPBearer` + `HTTPAuthorizationCredentials`
- [ ] 显式 `scheme_name`
- [ ] `auto_error=False` 的可选登录
- [ ] 双通道 OR

**能判断（避坑层）**：

- [ ] 看到断言 403 → 指出实测 401
- [ ] 看到 `= None` 以为可选 → 指出仍必需
- [ ] 看到多 `Security` 说 AND → 指出是 OR
- [ ] 看到 query 传 token → 指出泄露面
- [ ] 看到方案里写业务逻辑 → 指出职责错位

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 14/14
- [ ] `uvicorn` 起服务后打开 `/docs` 点 Authorize
- [ ] `curl` 无头请求看 401 body

## 9. 下一章衔接

第 45 章 `OAuth2 密码流`：`OAuth2PasswordBearer` + `OAuth2PasswordRequestForm`，用表单提交 `username/password` 换 token，`tokenUrl` 在文档里生成 Authorize 面板；讲 `python-multipart` 依赖、表单 vs JSON、`token_type` 为什么要写 `bearer`。

本章留下的伏笔：

1. `OAuth2PasswordBearer` 的 `tokenUrl` 第 45 章。
2. `get_current_user` 第 46 章。
3. JWT 签发 第 47 章。
4. `SecurityScopes` 第 48 章。
5. `HTTPBasic` / `APIKeyCookie` 第 49 章。