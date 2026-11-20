# 65 大型应用拆分 · 完整版（base.md）

> `README.md` 给你能跑的三模块组装；本文件把「prefix 到底怎么拼、路由按什么顺序匹配、router 级依赖与文档的关系、`app.routes` 为什么不能遍历」拆开。学完这章，你能把一个 2000 行的 `main.py` 拆成可维护的模块树。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0（本机实测） |
| 前置 | 第 03 章（路由）、第 06 章（依赖注入） |
| 覆盖范围 | `APIRouter`、prefix/tags、router 级依赖与 responses、组装顺序 |
| 明确不覆盖 | `Mount` 与子应用（68 章）、配置（66 章）、lifespan（67 章） |
| 学完验收 | 能跑通 `verify.py` 14/14、能解释 422 是怎么来的 |

## 0. 怎么用这份文件

**依据约定**：`` `[Bn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 三层路由树
2 机制（第 2 节）    → 前缀拼接与匹配顺序
3 API（第 3 节）     → APIRouter 参数逐个
4 边界（第 4 节）    → 依赖、文档、app.routes
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 目录模板
```

## 1. 概念：三层路由树

```text
app
 ├── /openapi.json, /docs, /redoc     (框架内置)
 ├── /health, /routes                 (直挂 app)
 └── /api/v1                           (APIRouter，版本前缀)
      ├── /users   → routers/users.py
      ├── /items   → routers/items.py
      └── /admin   → routers/admin.py（带鉴权依赖）
```

| 层 | 谁负责 | 好处 |
| --- | --- | --- |
| 版本前缀 | `main.py` | 换版本只改一处 |
| 模块前缀 | 各 `routers/*.py` | 模块自治 |
| 端点路径 | 装饰器 | 一目了然 |

## 2. 机制

### 2.1 前缀拼接

```python
api = APIRouter(prefix="/api/v1")
api.include_router(users.router)      # users.router 的 prefix 是 "/users"
```

结果：`/api/v1` + `/users` + `""` = `/api/v1/users`。

| 写法 | 结果 |
| --- | --- |
| `prefix="/api/v1"` + `"/users"` | `/api/v1/users` |
| `include_router(r, prefix="/x")` | 在当前 prefix 后再叠 `/x` |
| 尾斜杠 | 可能出现 `//` 或 307 重定向 |

### 2.2 匹配顺序（实测）

路由按**注册顺序**匹配，先到先得：

```text
注册顺序：/users/count → /users → /users/{user_id} → /users/stats
```

| 请求 | 命中 | 结果 |
| --- | --- | --- |
| `/users/count` | `/users/count` | 200 `{"count":5}` |
| `/users/stats` | `/users/{user_id}` | **422 `int_parsing`** |

**结论**：所有静态路径必须写在参数路径之前。

### 2.3 `app.routes` 不再是扁平列表（实测）

```text
len(app.routes) = 7
['/openapi.json', '/docs', '/docs/oauth2-redirect', '/redoc',
 <_IncludedRouter>, '/health', '/routes']
```

FastAPI 0.146 的 `include_router` 往 `app.routes` 塞的是 `_IncludedRouter` 包装对象，子路由**没有**被展平。

| 需求 | 正确做法 |
| --- | --- |
| 列出全部路径 | `app.openapi()["paths"]` |
| 遍历自定义 | 递归处理包装对象（内部 API，易变）|
| 权限扫描 | 用 `openapi()` |

## 3. API 逐个拆解

| `APIRouter(...)` 参数 | 作用 | 实测 |
| --- | --- | --- |
| `prefix` | 路径段 | `/api/v1/users` |
| `tags` | 文档分组 | operation 上 `["users"]` |
| `dependencies` | 全组强制依赖 | 三个端点全 403 |
| `responses` | 全组共享文档 | items 两个端点都有 404 |
| `deprecated` | 全组标记废弃 | 文档 `deprecated: true` |
| `include_in_schema` | 全组是否进文档 | 与端点级可叠加 |

### 3.1 端点级开关

```python
@router.get("/debug", include_in_schema=False)
def debug(): ...
```

| 影响 | 是否 |
| --- | --- |
| 文档 | 不出现 |
| 路由 | 仍可访问 |
| router 级依赖 | **仍然执行**（实测 403）|

### 3.2 `deprecated=True`（实测）

| 项 | 值 |
| --- | --- |
| 文档 | `deprecated: true` |
| 调用 | 仍返回 200 |

### 3.3 router 级 `responses`（实测）

```python
router = APIRouter(responses={404: {"description": "商品不存在"}})
```

`/items` 与 `/items/{item_id}` 的文档都出现 `404`。

### 3.4 router 级依赖的副作用（实测）

```text
/api/v1/admin/stats 的 responses = ["200", "422"]
```

`require_admin` 抛的 403 **不会**自动进文档。要手动补：

```python
@router.get("/stats", responses={403: {"description": "需要管理员"}})
```

## 4. 边界条件

### 4.1 多版本共存

```python
api_v1 = APIRouter(prefix="/api/v1")
api_v2 = APIRouter(prefix="/api/v2")
api_v1.include_router(users.router)
api_v2.include_router(users_v2.router)
app.include_router(api_v1)
app.include_router(api_v2)
```

同一套 router 可以挂到不同前缀，但**同一个 `APIRouter` 对象挂两次**会重复注册。

### 4.2 跨模块依赖

| 方案 | 说明 |
| --- | --- |
| 共享 `dependencies.py` | 推荐 |
| 共享 `store.py`/`models.py` | 数据层 |
| 互相 import router | ❌ 循环依赖 |

### 4.3 组装的幂等性

`include_router` 调用两次 → 路径重复注册，先匹配的第一个生效，第二个成死代码。自检：

```python
len(app.openapi()["paths"]) == 预期数量
```

### 4.4 探针路径

`/health`、`/metrics` **不要**挂版本前缀。发版换 `/api/v2` 时监控不用改。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 模块写死 `/api/v1` | 换版本改 N 处 | 只在外层写 | 实测 |
| 静态路径在 `/{id}` 后 | 422 而非 200 | 提前声明 | 实测 |
| 每端点重复鉴权 | 漏一个裸奔 | router `dependencies` | 实测 |
| 以为隐藏=不鉴权 | 实际仍执行 | 只影响文档 | 实测 |
| 遍历 `app.routes` | 拿不到子路由 | `openapi()["paths"]` | 实测 |
| 403 不写文档 | 前端不知道 | `responses={403:...}` | 实测 |
| 模块互相 import | 循环依赖 | 共享层 | 实测 |
| 业务写进 main | 又成单体 | main 只组装 | 实测 |
| 一个模块两个 prefix | 路径难查 | 一模块一 prefix | 实测 |
| prefix 带尾斜杠 | `//` 或 307 | 不带 | `[B1]` |
| 重复 `include_router` | 死代码 | 组装一次 + 断言 | 实测 |
| tags 只写 app 级 | 文档混成一坨 | 模块自己声明 | 实测 |
| 探针挂版本前缀 | 监控要改 | 直挂 app | 实测 |
| 依赖里做重活 | 每请求都跑 | 只轻量校验 | 第 06 章 |
| 用 `app.routes` 做权限扫描 | 漏掉子路由 | 用 openapi | 实测 |
| `include_router` 后再改 router | 包装对象已捕获 | 组装前配置完 | `[B2]` |
| 路径参数不加类型 | 不校验 | `user_id: int` | 第 01 章 |
| 一个 router 承担多个资源 | 边界模糊 | 按资源拆 | `[B1]` |
| 模块 prefix 与 `include_router(prefix=)` 都写 | 双前缀叠加，路径变长 | 只在一处加前缀 | 实测 |

## 6. 最佳实践与编码建议

### 6.1 目录模板

```text
app/
├── main.py              # 组装
├── models.py            # 共享模型
├── store.py             # 数据访问
├── dependencies.py      # 公共依赖
├── routers/
│   ├── __init__.py
│   ├── users.py
│   ├── items.py
│   └── admin.py
└── pyproject.toml
```

### 6.2 `main.py` 只做三件事

```python
app = FastAPI(...)                       # 1. 创建
api = APIRouter(prefix="/api/v1")        # 2. 组装
api.include_router(users.router)
app.include_router(api)
# 3. 少量全局端点（health）
```

### 6.3 自检

| 检查 | 期望 |
| --- | --- |
| `len(openapi()["paths"])` | 与设计一致 |
| 每个模块 tags | 唯一 |
| 静态路径位置 | 都在参数路径前 |
| 403/401 | 都写进 `responses` |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[B1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/bigger-applications/ | `APIRouter` 与组装 |
| `[B2]` | 文档 | https://fastapi.tiangolo.com/zh/reference/apirouter/ | `APIRouter` 参数 |

> **核对状态**：`[B1]`–`[B2]` 为官方文档链接，**本次未逐页直连复核**；路由树 10 条、前缀叠加、探针位置、静态/参数路径顺序（200 vs 422）、router 级依赖（403/200）、隐藏端点仍鉴权、tags、router responses、deprecated、403 不进文档、`app.routes` 不展平均为本机实测，`examples/verify.py` 复现 14/14 通过。多版本共存、`Mount`、`include_router` 嵌套三层的细节**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 三层路由树各管什么
- [ ] 前缀怎么拼
- [ ] 为什么静态路径要提前
- [ ] router 依赖与端点依赖的区别
- [ ] 为什么 `app.routes` 不能直接遍历

**能写出（代码层）**：

- [ ] 一个模块 router
- [ ] 组装 main
- [ ] router 级鉴权
- [ ] 隐藏端点
- [ ] 共享 responses

**能判断（避坑层）**：

- [ ] 看到 422 `int_parsing` → 想到路由顺序
- [ ] 看到 `/users` 404 → 想到前缀漏了
- [ ] 看到 403 文档缺失 → 手写 `responses`
- [ ] 看到遍历 `app.routes` → 改用 openapi
- [ ] 看到模块互相 import → 抽共享层

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 14/14
- [ ] `/docs` 里看到 users/items/admin/ops 四组
- [ ] 改 `prefix="/api/v2"` 后所有路径跟着变

## 9. 下一章衔接

第 66 章 `配置管理`：`pydantic-settings`、`.env`、环境切换、密钥不入库、依赖注入配置对象。

本章留下的伏笔：

1. `main.py` 只组装（65）→ 66 把 `FastAPI(title=...)` 这类参数也搬进配置。
2. 模块自治（65）→ 66 让每个模块通过 `Depends(get_settings)` 拿配置。
3. 探针路径（65）→ 66 用环境变量控制是否暴露。