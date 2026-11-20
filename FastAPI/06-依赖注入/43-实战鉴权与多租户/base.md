# 43 实战：鉴权与多租户 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「鉴权链怎么搭、租户边界画在哪、为什么跨租户要 404、`request.state` 怎么用、怎么测越权」拆开。学完这章，你要能交付一条不会被越权的依赖链。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0（本机实测） |
| 前置 | 第 35–42 章（依赖链、缓存、分页）、第 31 章（`HTTPException`） |
| 覆盖范围 | 认证→授权→租户上下文、查询隔离、404/403 选择、`request.state` |
| 明确不覆盖 | OAuth2/JWT（第 44–47 章）、RBAC 完整模型、审计日志 |
| 学完验收 | 能跑通 `verify.py` 12/12、能指出越权点、能写越权用例 |

## 0. 怎么用这份文件

**依据约定**：`` `[Tn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 三层边界
2 机制（第 2 节）    → 依赖链与 state
3 API（第 3 节）     → 解析、传递、过滤
4 边界（第 4 节）    → 404/403、伪造头、停用、并发
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 可复用鉴权层
```

## 1. 概念：认证、授权、租户是三件事

| 层 | 问题 | 失败码 | 例子 |
| --- | --- | --- | --- |
| 认证 | 你是谁 | 401 | token 缺失/无效 |
| 授权 | 你能做什么 | 403 | 缺角色/账号停用 |
| 租户 | 你能看到哪些数据 | **404** | 跨租户访问 |

把租户边界放在**查询层**（`WHERE tenant_id = ?`），而不是在返回前判断——后者容易漏（列表、统计、导出各一处）。

## 2. 机制：依赖链 + `request.state`

```text
X-Token
 → get_context：查表 → 主体（user/tenant/role/active）
     ├─ 缺失/无效 → 401
     └─ 停用 → 403
 → tenant_context：request.state.tenant_id = ctx["tenant"]
 → 端点：查询过滤 tenant
```

| 事实 | 说明 |
| --- | --- |
| 依赖链按 DAG 执行 | 第 37 章缓存生效 |
| `request.state` 是请求级 | 适合日志/下游读取 |
| 租户来自 token | 客户端头一律忽略（实测）|

## 3. API 逐个拆解

### 3.1 认证

```python
def get_context(x_token: Annotated[str | None, Header(alias="X-Token")] = None) -> dict:
    ...
```

| 状态 | 返回 |
| --- | --- |
| 无 token | 401 + `WWW-Authenticate: Bearer` |
| token 无效 | 401 + `error="invalid_token"` |
| 账号停用 | 403 |

### 3.2 上下文传递

```python
def tenant_context(request: Request, ctx: Annotated[dict, Depends(get_context)]) -> dict:
    request.state.tenant_id = ctx["tenant"]
    return ctx
```

实测：`/whoami` 里 `state_tenant == tenant == "t-a"`，`state_user == "alice"`。

### 3.3 查询隔离

```python
def _find_item(item_id: int, tenant: str) -> dict:
    item = _ITEMS.get(item_id)
    if item is None or item["tenant"] != tenant:
        raise HTTPException(404, f"商品 {item_id} 不存在")
    return item
```

| 写法 | 结果 |
| --- | --- |
| 查完再判租户 | 可用，但容易在列表/统计漏 |
| 查询条件带租户 | **推荐**（DB 层过滤）|

### 3.4 创建

请求模型里**没有** `tenant` 字段，客户端传了也被丢弃（实测），落库时用 `ctx["tenant"]`。

## 4. 边界条件

### 4.1 404 vs 403（实测）

跨租户读 `/items/1`（属 t-a）用 B 的 token：

```json
{"detail": "商品 1 不存在"}
```

与 `/items/999` 的结构完全一致。文案里只有客户端已知的 id，不泄露存在性。

### 4.2 客户端伪造头（实测）

`X-Tenant: t-b` 被忽略，仍返回 t-a 的数据。**不要**把客户端头当租户来源。

### 4.3 停用租户（实测）

`tok-off` → 403 `账号或租户已停用`。注意：401 会让客户端反复重试登录，停用应 403。

### 4.4 并发

| 风险 | 处理 |
| --- | --- |
| 全局变量存租户 | 用 `request.state` |
| 单例缓存按租户 | key 里带 tenant |
| 连接池跨租户复用 session | 每请求新 session（第 40 章）|

### 4.5 `assert` 不能当校验（实测教训）

示例初版在依赖里用 `assert` 检查客户端头，客户端传不一致值时抛 `AssertionError` → 500，且 `python -O` 下会被禁用。**安全校验必须 `raise HTTPException`**。

### 4.6 越权测试清单

| 用例 | 期望 |
| --- | --- |
| 无 token | 401 |
| 错 token | 401 |
| 停用 | 403 |
| 读他人资源 | 404 |
| 列表条数 | 只含本租户 |
| 创建带他人 tenant | 忽略，落自己租户 |
| 统计/导出 | 同列表 |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 信 `X-Tenant` | 越权 | 从 token 派生 | 实测 |
| 跨租户 403 | 泄露存在性 | 404 | `[T3]` |
| 查询不带 tenant | 越权读 | 查询层过滤 | `[T2]` |
| `assert` 做校验 | 500 / `-O` 失效 | `raise` | 实测 |
| 404 文案泄露归属 | 信息泄露 | 与不存在一致 | `[T3]` |
| 停用返回 401 | 反复重试 | 403 | `[T1]` |
| 401 无 challenge | 客户端无指引 | `WWW-Authenticate` | `[T1]` |
| 租户存全局变量 | 并发串租户 | `request.state` | `[T2]` |
| 列表 count 不过滤 | 数量泄露 | 同条件 count | `[T2]` |
| 只在前端隐藏 | 无防护 | 服务端 | `[T3]` |
| 创建允许客户端指定 tenant | 越权创建 | 服务端赋值 | 实测 |
| token 明文入库 | 泄露 | 哈希/签名 | `[T4]` |
| 角色判断散落端点 | 易漏 | 依赖/装饰器 | 第 39 章 |
| 把租户 id 放 URL | 可被改 | 从上下文取 | `[T3]` |
| 日志打印 token | 泄露 | 脱敏 | `[T4]` |
| 导出/搜索不过滤 | 越权 | 统一查询构造 | `[T2]` |
| 依赖里做重查库 | 每请求成本 | 缓存/连接池 | 第 40 章 |
| 只测 200 路径 | 越权漏测 | 越权用例 | 第 71 章 |
| 平台管理员绕过租户过滤无审计 | 越权难追责 | 记录审计日志 | `[T2]` |

## 6. 最佳实践与编码建议

### 6.1 可复用鉴权层

```python
from typing import Annotated, Any

from fastapi import Depends, Header, HTTPException, Request


async def get_principal(x_token: Annotated[str | None, Header()] = None) -> Principal:
    ...


async def require_tenant(request: Request, p: Annotated[Principal, Depends(get_principal)]) -> Principal:
    request.state.tenant_id = p.tenant_id
    return p


type PrincipalDep = Annotated[Principal, Depends(require_tenant)]
```

| 建议 | 说明 |
| --- | --- |
| 租户过滤封装成仓储方法 | 一处实现 |
| 404 统一文案 | 不泄露 |
| 越权用例进 CI | 防回归 |
| token 不入日志 | 脱敏 |
| 403/401 区分 | 语义正确 |

### 6.2 选型速查

| 需求 | 做法 |
| --- | --- |
| 单租户 | 只需认证 + 角色 |
| 多租户 | 上下文 + 查询过滤 |
| 跨租户共享 | 显式白名单 |
| 平台管理员 | 独立角色，绕过滤需审计 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[T1]` | 规范 | https://www.rfc-editor.org/rfc/rfc9110#section-15.5.2 | 401/403 |
| `[T2]` | 参考 | https://cheatsheetseries.owasp.org/cheatsheets/Multitenant_Security_Cheat_Sheet.html | 多租户隔离 |
| `[T3]` | 安全指南 | https://cheatsheetseries.owasp.org/cheatsheets/Authorization_Cheat_Sheet.html | 越权与信息泄露 |
| `[T4]` | 安全指南 | https://cheatsheetseries.owasp.org/cheatsheets/Password_Storage_Cheat_Sheet.html | 凭据存储 |

> **核对状态**：`[T1]`–`[T4]` 为规范/安全指南，**本次未逐页直连复核**；401/403/404 行为、列表隔离、跨租户同结构、创建绑定租户、忽略 `X-Tenant`、`request.state` 传递、OpenAPI 仅 `X-Token` 均为本机实测，`examples/verify.py` 复现 12/12 通过。并发与 DB 层过滤**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 认证/授权/租户三层边界
- [ ] 为什么跨租户用 404
- [ ] 租户为什么不能来自客户端
- [ ] `request.state` 的作用域
- [ ] `assert` 为什么不能做校验

**能写出（代码层）**：

- [ ] token → 主体依赖
- [ ] 写 `request.state`
- [ ] 查询带租户过滤
- [ ] 创建绑定租户
- [ ] 401/403/404 三分支

**能判断（避坑层）**：

- [ ] 看到信 `X-Tenant` → 指出越权
- [ ] 看到跨租户 403 → 指出泄露
- [ ] 看到 `assert` 校验 → 指出 500
- [ ] 看到 count 不过滤 → 指出泄露数量
- [ ] 看到 token 明文 → 指出风险

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 12/12
- [ ] 用 A/B token 对比列表
- [ ] 跨租户读看 404

## 9. M06 小结与下一章

M06（35–43）覆盖了依赖注入的完整链路：`Depends` 基础 → 类/实例/工厂 → 子依赖与缓存 → `Annotated` 别名 → 装饰器与全局 → `yield` 生命周期 → 覆盖 → 分页/多租户实战。

下一模块 M07 `安全认证`（44–49）：`Security`、`OAuth2PasswordBearer`、JWT、密码哈希、`HTTPBasic`、作用域。本章的 401/403 语义与依赖链会直接复用。