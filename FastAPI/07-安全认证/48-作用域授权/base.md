# 48 作用域授权 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「scope 从哪来、怎么汇总、怎么比对、403 怎么写出可用的 challenge、scope 与角色怎么分工」拆开。学完这章，你要能设计一套不越权、不重复的权限声明。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0（本机实测） |
| 前置 | 第 44–47 章（`Security`、OAuth2、JWT） |
| 覆盖范围 | `SecurityScopes`、`scopes=`、交集授予、403 challenge、scope 设计 |
| 明确不覆盖 | RBAC/ABAC 完整模型、授权服务器、token 撤销 |
| 学完验收 | 能跑通 `verify.py` 12/12、能写出正确 challenge、能设计 scope 命名 |

## 0. 怎么用这份文件

**依据约定**：`` `[Cn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → scope vs 角色
2 机制（第 2 节）    → 汇总与比对
3 API（第 3 节）     → 声明、注入、challenge
4 边界（第 4 节）    → AND、交集、401/403、空 scope
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 命名与结构
```

## 1. 概念：scope 控「能力」，角色控「人」

| 维度 | scope | 角色 |
| --- | --- | --- |
| 粒度 | 单个操作 | 一组能力 |
| 举例 | `items:write` | `editor` |
| 变化频率 | 低 | 中 |
| 存在位置 | token（授权结果）| 数据库（授权来源）|

推荐做法：**数据库存角色 → 登录时映射成 scopes → token 里带 scopes → 端点校验 scopes**。端点不直接判角色，避免「角色改了要改代码」。

## 2. 机制：声明 → 汇总 → 比对

```text
端点 A: Security(dep, scopes=["items:read"])
端点 A: Security(dep2, scopes=["audit"])
 → SecurityScopes(scopes=["items:read","audit"], scope_str="items:read audit")
 → dep 内逐项比对 token 里的 scopes
```

| 事实 | 说明 |
| --- | --- |
| 汇总发生在解析阶段 | 同一请求所有依赖的 scope 合并 |
| 依赖只写一次 | 多个端点用同一依赖，scope 由端点决定 |
| challenge 用 `scope_str` | 空格连接（实测）|

## 3. API 逐个拆解

### 3.1 声明

```python
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token", scopes={"items:read": "读取商品"})
```

`scopes` 字典只影响 **OpenAPI 文档**（`flows.password.scopes`），不影响运行时校验。

### 3.2 注入

```python
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    security_scopes: SecurityScopes,
) -> dict:
```

`SecurityScopes` 不需要 `Depends`，直接写注解。

### 3.3 402/403 的输出

实测：

```text
HTTP/1.1 403 Forbidden
WWW-Authenticate: Bearer scope="items:write" error="insufficient_scope"
{"detail": "缺少 scope: items:write"}
```

多 scope：

```text
WWW-Authenticate: Bearer scope="items:read items:write" error="insufficient_scope"
```

## 4. 边界条件

### 4.1 AND 语义（实测）

`security: [{"OAuth2PasswordBearer": ["items:read","items:write"]}]`——同一对象内多个 scope 是 AND；`["items:read"]` 单独通过不了 DELETE。

### 4.2 交集授予（实测）

alice 拥有 `["items:read"]`，请求 `items:read items:write admin` → 只授予 `["items:read"]`。

**绝对不要**把客户端请求的 scope 直接写进 token。

### 4.3 401 与 403 的顺序（实测）

| 请求 | 结果 |
| --- | --- |
| 无 token | 401 + `WWW-Authenticate: Bearer`（方案层）|
| token 有效但缺 scope | 403 + `insufficient_scope` |

### 4.4 空 scopes 用户（实测）

bob `scopes=[]` → token 里 `scopes: []` → 任何声明 scope 的端点都 403。

### 4.5 token 里的 scopes 可被读

payload 明文（第 47 章），所以 scopes 只是「声明」，安全性来自签名，不来自保密。

### 4.6 与 `dependencies=[...]` 混用

装饰器位置也支持 `scopes=`（实测 `/audit` 200），但拿不到用户对象。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 客户端请求即授予 | 越权（实测会过滤）| 取交集 | 实测 |
| 403 缺 `scope=` | 客户端无法申请 | 完整 challenge | `[C3]` |
| 403 缺 `insufficient_scope` | 客户端误判 | 加上 | `[C3]` |
| 多 scope 用逗号拼 | 解析错 | 空格 | 实测 |
| 无 token 返回 403 | 语义错 | 401 | `[C2]` |
| scope 校验写在路由 | 重复/易漏 | 依赖里统一 | `[C1]` |
| 用 `Depends` 声明 scopes | 不生效 | `Security(..., scopes=)` | 实测 |
| 以为多 scope 是 OR | 越权 | AND | 实测 |
| token 不带 scopes | 依赖读不到 | 签发时加 | 第 47 章 |
| scope 命名无语义 | 难维护 | `资源:动作` | `[C1]` |
| 用 scope 替代角色表 | 组合爆炸 | 角色→scope 映射 | `[C4]` |
| scope 太细（字段级）| token 膨胀 | 按资源 | `[C4]` |
| 只校验 scope 不校验资源归属 | 越权读写他人数据 | 加租户/属主判断（第 43 章）| `[C4]` |
| 把 `admin` 当万能 scope | 一处泄露全失守 | 拆细 + 二次校验 | `[C4]` |
| 忘记给 `/docs` 保护 | 文档暴露 | 独立保护 | 第 39 章 |
| scope 变更不通知客户端 | 突然 403 | 版本化 | `[C4]` |
| 只测一个 scope | 组合漏测 | 矩阵测试 | 第 71 章 |
| 用 GET 传 token | 泄露 | header | `[C3]` |
| 装饰器位置带 scopes 却想取用户 | 拿不到 | 用参数位置 `Security` | `[C1]` |

## 6. 最佳实践与编码建议

### 6.1 scope 命名

```text
<resource>:<action>        例：items:read / items:write / users:delete
<resource>:* （慎用）       宽 scope 要单独评估
```

| 规则 | 理由 |
| --- | --- |
| 全小写 + 冒号 | 与 RFC 6749 示例一致 |
| 动词用 `read/write/delete/admin` | 统一 |
| 不用数字后缀 | 无语义 |

### 6.2 权限依赖结构

```python
async def get_current_user(...) -> User: ...          # 认证 + scope 校验
def require_scope(scope: str):                         # 可选：工厂
    async def dep(user: Annotated[User, Security(get_current_user, scopes=[scope])]) -> User:
        return user
    return dep
```

| 建议 | 说明 |
| --- | --- |
| 认证与授权分层 | 便于覆盖测试 |
| scope 校验集中在依赖 | 一处维护 |
| 资源归属单独校验 | scope 只管「能不能做这类事」|
| 用常量定义 scope | 防拼错 |

### 6.3 选型速查

| 需求 | 做法 |
| --- | --- |
| 少量固定权限 | 角色 |
| 需要委托/第三方 | scope |
| 两者都有 | 角色→scope 映射 |
| 字段级权限 | 业务层判断 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[C1]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/security/oauth2-scopes/ | `SecurityScopes` |
| `[C2]` | RFC | https://www.rfc-editor.org/rfc/rfc6750#section-3.1 | `insufficient_scope` |
| `[C3]` | RFC | https://www.rfc-editor.org/rfc/rfc6749#section-3.3 | scope 定义与格式 |
| `[C4]` | 指南 | https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html | 授权设计 |

> **核对状态**：`[C1]`–`[C4]` 为官方/RFC/指南链接，**本次未逐页直连复核**；`flows.password.scopes`、路由 `security` 带 scopes、装饰器位置、交集授予、空 scope 403、缺 scope challenge、多 scope AND 与空格连接、无 token 401、token 带 scopes 均为本机实测，`examples/verify.py` 复现 12/12 通过。真实角色表映射、scope 撤销**未实现**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] scope 与角色的分工
- [ ] `SecurityScopes` 的汇总时机
- [ ] 403 challenge 的三个要素
- [ ] 为什么必须取交集
- [ ] 401 与 403 的边界

**能写出（代码层）**：

- [ ] `OAuth2PasswordBearer(scopes={...})`
- [ ] `Security(dep, scopes=[...])`
- [ ] `SecurityScopes` 比对
- [ ] 正确的 challenge
- [ ] 交集授予逻辑

**能判断（避坑层）**：

- [ ] 看到客户端请求全授予 → 指出越权
- [ ] 看到 403 无 challenge → 指出客户端无法自愈
- [ ] 看到逗号分隔 scope → 指出格式错
- [ ] 看到 scope 校验散落 → 指出重复
- [ ] 看到 `admin` 万能 → 指出爆炸半径

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 12/12
- [ ] `/docs` 里看 scope 勾选
- [ ] curl 缺 scope 看 403 头

## 9. 下一章衔接

第 49 章 `API Key 与 Basic`：`APIKeyHeader`/`APIKeyQuery`/`APIKeyCookie` 三种取 key 位置，`HTTPBasic` + `HTTPBasicCredentials` 的 `secrets.compare_digest` 用法，以及「机器对机器」与「人」的鉴权怎么分场景选型。M07 到此收尾。

本章留下的伏笔：

1. 机器鉴权 第 49 章。
2. Basic 的 `WWW-Authenticate: Basic realm=...` 第 49 章。
3. 中间件 CORS 第 51 章。