# 65 大型应用拆分

## 一句话结论

把 app 拆成「每个模块一个 `APIRouter`，只声明自己那段 prefix」，在 `main.py` 里叠加组装。实测三个模块组装后 `openapi()["paths"]` 恰好 **10 条**：`/api/v1`（外层）+ `/users`、`/items`、`/admin`（模块）+ `/health`（直挂 app，不在版本前缀下）。`dependencies=[Depends(require_admin)]` 挂一次，`/admin` 下三个端点（含 `include_in_schema=False` 的 `/admin/debug`）**全部 403**。两个大坑：**静态路径必须写在参数路径之前**（`/users/stats` 写在 `/{user_id}` 之后 → `422 int_parsing`）；**FastAPI 0.146 的 `include_router` 不再把子路由展平进 `app.routes`**（`app.routes` 只有 6 条带 path，必须查 `openapi()["paths"]`）。

## 最小可运行案例

```text
examples/
├── main.py            # 只负责组装
├── models.py          # 共享模型
├── store.py           # 共享数据
├── dependencies.py    # 公共依赖
└── routers/
    ├── __init__.py
    ├── users.py
    ├── items.py
    └── admin.py
```

`routers/users.py`：

```python
from fastapi import APIRouter

router = APIRouter(prefix="/users", tags=["users"])


@router.get("")
def list_users() -> list[str]:
    return ["alice", "bob"]
```

`main.py`：

```python
from fastapi import APIRouter, FastAPI

import routers.users as users

app = FastAPI()
api = APIRouter(prefix="/api/v1")     # 版本前缀只出现这一次
api.include_router(users.router)
app.include_router(api)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}
```

## 怎么跑

```powershell
cd "11-应用结构\65-大型应用拆分\examples"
uv sync
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 路由树 -> 10 条路径
[PASS] 前缀叠加 -> /api/v1/users 可用，/users 404
[PASS] 探针不在前缀下 -> /health 200，/api/v1/health 404
[PASS] 静态路径在前 -> 200 / count=5
[PASS] 静态路径在后 -> 422 int_parsing（被 {user_id} 抢走）
[PASS] 参数路由 -> 3 → 200，99 → 404
[PASS] router 依赖拦截 -> 三个端点全部 403
[PASS] router 依赖放行 -> users=5, items=3
[PASS] 隐藏仍鉴权 -> 文档隐藏，鉴权仍生效
[PASS] tags 生效 -> users / items / admin / ops
[PASS] router responses -> items 两个端点都有 404
[PASS] deprecated -> deprecated=True 且仍返回 200
[PASS] 403 不进文档 -> 文档只有 200/422（403 需手写）
[PASS] app.routes 未展平 -> openapi 10 条 / app.routes 仅 6 条带 path

结果：14/14 通过
```

## 核心 API 速查

| 参数 | 位置 | 作用 |
| --- | --- | --- |
| `prefix="/users"` | `APIRouter()` | 模块自己的路径段 |
| `tags=["users"]` | `APIRouter()` | 文档分组 |
| `dependencies=[Depends(f)]` | `APIRouter()` | 该模块所有端点强制走 |
| `responses={404: ...}` | `APIRouter()` | 该模块所有端点共享文档 |
| `deprecated=True` | 装饰器 | 标记废弃 |
| `include_in_schema=False` | 装饰器 | 不进文档（**但仍鉴权**） |
| `include_router(r, prefix="/x")` | 组装处 | 再叠一层前缀 |

| 实测 | 值 |
| --- | --- |
| 组装后路径数 | 10 |
| `/api/v1/users` | 200 |
| `/users` | 404 |
| `/api/v1/health` | 404 |
| `/users/count`（在前） | 200 `{"count":5}` |
| `/users/stats`（在后） | 422 `int_parsing` |
| `/admin/*` 无 token | 全部 403 |
| `/admin/debug` | 文档无、鉴权有 |
| `app.routes` 带 path | 仅 6 条 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 模块里写死 `/api/v1` | 换版本要改 N 个文件 | 只在外层写 |
| 静态路径写在 `/{id}` 之后 | 被参数路由抢走 → 422 | 静态路径提前 |
| 每个端点重复写鉴权 | 漏一个就裸奔 | router 级 `dependencies` |
| 以为 `include_in_schema=False` 等于不鉴权 | 实际仍会执行依赖 | 只影响文档 |
| 遍历 `app.routes` 找路由 | 0.146 起是 `_IncludedRouter` 包装 | 查 `openapi()["paths"]` |
| router 依赖的 403 不写文档 | 前端看不到 403 | 端点加 `responses={403:...}` |
| 模块之间互相 `import router` | 循环依赖 | 共享 `models/store` |
| 把业务逻辑写进 `main.py` | 又变回单体 | main 只组装 |
| 一个 router 挂两个 prefix | 路径重复难查 | 一个模块一个 prefix |
| `prefix` 结尾带 `/` | 出现 `//` 或尾斜杠重定向 | 不带尾斜杠 |
| 用 `app.include_router` 重复调用 | 路径重复注册 | 组装一次 |
| `tags` 只写 app 级 | 模块混在一起 | 每个模块自己声明 |
| 探针挂版本前缀下 | 发版要改监控 | 直挂 app |
| 依赖里做重活 | 每个请求都跑 | 只做轻量校验 |

## 毕业自查

- [ ] 能画出「app → api → 模块」三层路由树
- [ ] 能解释为什么 prefix 只写在组装处
- [ ] 能说清静态路径与参数路径的顺序规则
- [ ] 能用 router 级 `dependencies` 保护整组端点
- [ ] 知道 `app.routes` 在 0.146 不可直接遍历
- [ ] 动手题一：把 `/api/v1` 改成 `/api/v2`，只改一行
- [ ] 动手题二：给 admin 的 403 补进文档

> 想看路由匹配顺序的源码、`_IncludedRouter` 内部结构、多版本共存、`Mount` 与子应用、跨模块依赖、18 条坑，继续读 [`base.md`](./base.md)。