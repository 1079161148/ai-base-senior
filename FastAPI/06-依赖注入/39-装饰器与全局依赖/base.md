# 39 装饰器与全局依赖 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「三个层级怎么生效、为什么拿不到返回值、注册时机为什么重要、全局依赖与中间件怎么选」拆开。学完这章，你要能给任意粒度的路由加前置逻辑，并清楚它的边界。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0（本机实测） |
| 前置 | 第 35–38 章（`Depends`、缓存、别名） |
| 覆盖范围 | 端点/路由器/全局依赖、返回值差异、注册时机、与 docs 的关系、缓存共享 |
| 明确不覆盖 | 中间件细节（第 46–49 章）、安全性方案（第 44 章） |
| 学完验收 | 能跑通 `verify.py` 14/14、能选对层级、能解释事后 append 无效 |

## 0. 怎么用这份文件

**依据约定**：`` `[Rn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 三个层级
2 机制（第 2 节）    → 注册时固化
3 API（第 3 节）     → 写法与返回值
4 边界（第 4 节）    → docs、前缀、时机、缓存
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 鉴权分层
```

## 1. 概念：三种粒度，一种语义

| 层级 | 写法 | 覆盖 | 典型用途 |
| --- | --- | --- | --- |
| 端点 | `@app.get(..., dependencies=[...])` | 单路由 | 单点二次校验 |
| Router | `APIRouter(dependencies=[...])` | 组内路由 | 后台管理区鉴权 |
| 全局 | `FastAPI(dependencies=[...])` | 所有用户路由 | 审计、限流基线 |

共同点：**只执行，不注入返回值**。想用返回值，必须写进参数。

## 2. 机制：注册时固化

```text
@app.get("/x", dependencies=[Depends(f)])
  → APIRoute(dependencies=[...])   # 拷贝进路由对象
  → 请求时 solve_dependencies 遍历
```

| 事实 | 说明 |
| --- | --- |
| 装饰器参数在注册时使用 | 事后改 `router.dependencies` 不影响已注册路由（实测）|
| 全局依赖在 `FastAPI.__init__` 传给 router | 同样在注册时快照 |
| 依赖参数照常进 OpenAPI | 实测 `X-Request-Source`、`X-Token` 都在 |
| 依赖结果进缓存 | 与参数位置共享（实测只执行 1 次）|

## 3. API 逐个拆解

### 3.1 端点装饰器

```python
@app.get("/public", dependencies=[Depends(require_token)])
def public() -> dict: ...
```

| 优点 | 限制 |
| --- | --- |
| 声明在路由旁，直观 | 拿不到返回值 |
| 可叠加多个 | 多依赖顺序即列表顺序 |

### 3.2 Router

```python
router = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])
app.include_router(router)
```

| 要点 | 说明 |
| --- | --- |
| 只作用于 include 进来的路由 | 实测 `/admin/ops` 不受保护 |
| 前缀只是路径拼接 | 不等于路由归属 |
| 可嵌套 include | 依赖按层叠加 |

### 3.3 全局

```python
app = FastAPI(dependencies=[Depends(audit)])
```

| 要点 | 说明 |
| --- | --- |
| 只作用于用户路由 | `/docs`、`/openapi.json` 不受影响（实测）|
| 全局依赖抛错 → 全站挂 | 实测 503 |
| 适合审计/版本/租户基线 | 不适合做唯一鉴权 |

### 3.4 返回值差异

| 位置 | 端点可用 | 拿不到时的替代 |
| --- | --- | --- |
| `dependencies=[...]` | 否 | 改用参数位置 |
| `Annotated[T, Depends(f)]` | 是 | — |

实测：`/compare/dec` → `{"receives": "nothing"}`；`/compare/param` → `{"token": "secret"}`。

## 4. 边界条件

### 4.1 文档路由（实测）

`/docs`、`/openapi.json` 不执行全局依赖。含义：**不要用全局依赖做安全边界**。

### 4.2 路径前缀与 Router（实测）

`/admin/ops` 定义在 app 上，路径含 `/admin` 但不在 `admin_router` 里 → 只需全局依赖，`X-Role` 不校验。这是「按前缀猜归属」的经典误判。

### 4.3 注册时机（实测）

```python
app.router.dependencies.append(Depends(boom))  # 路由已注册 → 无效
```

必须在 `FastAPI(...)` 构造时传，或在 `include_router`/注册前设置。

### 4.4 缓存共享（实测）

全局依赖与端点依赖用**同一对象** → 单请求只执行一次。

### 4.5 与中间件的区别

| | 依赖 | 中间件 |
| --- | --- | --- |
| 作用对象 | 路由 | 所有请求（含 docs/404）|
| 能否拿返回值 | 参数位置可以 | 不能，但能改 response |
| 执行顺序 | 依赖解析阶段 | 更外层 |
| 适合 | 业务前置 | 日志、CORS、耗时 |

### 4.6 多个依赖的顺序

`dependencies=[Depends(a), Depends(b)]` 按列表顺序执行；`a` 抛错则 `b` 不执行。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 装饰器依赖想拿返回值 | 拿不到 | 参数位置 | 实测 |
| 路径前缀当 Router 归属 | 漏保护 | 显式 include | 实测 |
| 事后 append 依赖 | 不生效 | 构造时传 | 实测 |
| 全局依赖当唯一鉴权 | `/docs` 绕过 | 参数/中间件 | 实测 |
| 全局依赖做重 IO | 全站变慢 | 轻量审计 | `[R3]` |
| Router 依赖忘了 include | 路由 404 | 检查 include | `[R1]` |
| 两个依赖期望顺序但没注意 | 校验顺序错 | 按列表顺序 | `[R1]` |
| 同一依赖写两处 | 可能执行两次 | 复用同一对象 | 实测 |
| 全局依赖里改 response | 拿不到 | 注入 `Response` | 第 24 章 |
| 用全局依赖做限流 | docs 不计入 | 中间件/网关 | `[R3]` |
| 全局依赖抛错未兜底 | 全站 500 | 明确状态码 | 第 31 章 |
| Router 依赖里读 body | 可能已消费 | 用参数 | `[R2]` |
| 嵌套 include 依赖叠加无注释 | 难排障 | 注释层级 | `[R1]` |
| 以为全局依赖也保护挂载子应用 | 实际按子应用路由表 | 子应用自己配 | `[R2]` |
| 依赖里 `return` 忽略 | 逻辑未生效 | 用 `raise` 校验 | 第 31 章 |
| 装饰器依赖参数与端点同名 | 覆盖/冲突 | 改名 | `[R1]` |
| 全局依赖里访问 `request.state` 未初始化 | AttributeError | 先设后读 | 第 34 章 |
| 只测一个端点 | 组依赖漏测 | 每层各测一条 | 第 71 章 |
| 全局依赖强制所有端点同版本 | 旧客户端全挂 | 按 Router 分组 | `[R1]` |

## 6. 最佳实践与编码建议

### 6.1 鉴权分层

```python
# 全局：审计/请求标识（不拦截）
app = FastAPI(dependencies=[Depends(audit)])

# 分组：后台区必须 admin
admin = APIRouter(prefix="/admin", dependencies=[Depends(require_admin)])

# 单点：敏感操作再验 token 且要用返回值
@app.post("/admin/reindex", dependencies=[Depends(require_admin)])
def reindex(user: UserDep) -> dict: ...
```

### 6.2 编码建议

| 建议 | 说明 |
| --- | --- |
| 全局只放无副作用或轻量逻辑 | 影响面最大 |
| 组依赖用 Router | 一处声明 |
| 需要返回值就用参数 | 别绕 |
| 依赖抛 `HTTPException`/业务异常 | 第 31–32 章 |
| 依赖对象复用 | 避免重复执行 |

### 6.3 选型速查

| 需求 | 做法 |
| --- | --- |
| 单端点鉴权 | 装饰器 + 参数 |
| 一组路由 | Router |
| 全站审计 | 全局 |
| 需要改响应 | 中间件 |
| 需要返回值 | 参数位置 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[R1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/dependencies/dependencies-in-path-operation-decorators/ | 装饰器依赖 |
| `[R2]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/dependencies/global-dependencies/ | 全局依赖 |
| `[R3]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/middleware/ | 与中间件分工 |

> **核对状态**：`[R1]`–`[R3]` 为官方链接，**本次未逐页直连复核**；三层级生效范围、装饰器拿不到返回值、docs 不受限、前缀≠归属、事后 append 无效、缓存共享均为本机实测，`examples/verify.py` 复现 14/14 通过。挂载子应用的全局依赖行为**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 三种粒度的覆盖范围
- [ ] 为什么装饰器位置拿不到返回值
- [ ] 全局依赖为什么不保护 docs
- [ ] 注册时机为什么关键
- [ ] 依赖与中间件的分工

**能写出（代码层）**：

- [ ] 端点装饰器依赖
- [ ] Router 组依赖
- [ ] 全局审计依赖
- [ ] 参数位置拿返回值
- [ ] 三层叠加

**能判断（避坑层）**：

- [ ] 看到按前缀猜保护 → 指出漏保护
- [ ] 看到全局依赖做鉴权 → 指出 docs 绕过
- [ ] 看到事后 append → 指出无效
- [ ] 看到重复写同一依赖 → 指出缓存/顺序
- [ ] 看到全局依赖做重 IO → 指出全站代价

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 14/14
- [ ] `/docs` 直接访问看是否受限
- [ ] `/admin/ops` 与 `/admin/panel` 对比

## 9. 下一章衔接

第 40 章 `yield 依赖`：用 `yield` 把「创建 → 使用 → 清理」写在一个依赖里（数据库会话、临时文件），讲 `finally` 与异常穿透、`yield` 之后代码何时执行、以及「依赖退出早于/晚于响应」的版本差异。

本章留下的伏笔：

1. 资源清理 第 40 章。
2. 测试替换 第 41 章。
3. 分页/鉴权实战 第 42–43 章。