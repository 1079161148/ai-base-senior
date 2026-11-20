# 39 装饰器与全局依赖

## 一句话结论

`dependencies=[Depends(fn)]` 放在三个位置：端点装饰器（单点）、`APIRouter(...)`（一组）、`FastAPI(...)`（全局）。它**只执行、只校验，不注入返回值**——实测 `/compare/dec` 拿不到 token，只有参数位置的 `Annotated[str, Depends(require_token)]` 能拿到。全局依赖不作用于 `/docs` 与 `/openapi.json`（实测）；路由注册后再 `router.dependencies.append(...)` **不生效**（实测）。

学完这一章，你能：给一组路由统一加鉴权、给全站加审计、知道什么时候必须改用参数位置。

## 最小可运行案例

```python
from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException

AUDIT: list[str] = []


def audit(x_source: Annotated[str | None, Header(alias="X-Request-Source")] = None) -> None:
    AUDIT.append(x_source or "unknown")


def require_token(x_token: Annotated[str | None, Header()] = None) -> str:
    if x_token != "secret":
        raise HTTPException(401, "X-Token 无效")
    return x_token


app = FastAPI(dependencies=[Depends(audit)])          # 全局：所有路由


@app.get("/public", dependencies=[Depends(require_token)])   # 单点
def public() -> dict[str, str]:
    return {"ok": "true"}


admin = APIRouter(prefix="/admin", dependencies=[Depends(require_token)])   # 一组


@admin.get("/panel")
def panel() -> dict[str, str]:
    return {"panel": "admin"}


app.include_router(admin)
```

完整版本（返回值对比、三层叠加、事后 append）见 `examples/main.py`。

## 怎么跑

```powershell
cd "06-依赖注入\39-装饰器与全局依赖\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 全局依赖执行 -> AUDIT=['test']
[PASS] 全局依赖默认值 -> 默认 unknown
[PASS] 装饰器依赖拦截 -> 401 拦截
[PASS] 装饰器依赖放行 -> 200 放行
[PASS] 装饰器拿不到返回值 -> dec 拿不到；param 拿到 secret
[PASS] Router 依赖生效 -> 无 X-Role → 403；有 → 200
[PASS] Router 全覆盖 -> stats 同样 403
[PASS] 路径前缀不等于 Router -> 只受全局依赖影响
[PASS] 全局 + Router 叠加 -> 全局审计 + router 鉴权都执行
[PASS] OpenAPI 含依赖参数 -> parameters=['X-Request-Source', 'X-Token']
[PASS] /docs 不受限 -> /docs 与 /openapi.json 不受全局依赖限制
[PASS] 全局依赖失败 -> 全局依赖抛 503 → 路由不可用
[PASS] 事后 append 无效 -> 已注册路由不受事后 append 影响
[PASS] 全局与端点共享缓存 -> 同请求只执行 1 次

结果：14/14 通过
```

## 核心 API 速查

| 位置 | 写法 | 作用范围 | 能拿返回值 |
| --- | --- | --- | --- |
| 端点装饰器 | `@app.get(..., dependencies=[Depends(f)])` | 单端点 | 否 |
| Router | `APIRouter(dependencies=[Depends(f)])` | 该 router 全部 | 否 |
| 全局 | `FastAPI(dependencies=[Depends(f)])` | 所有用户路由 | 否 |
| 参数 | `x: Annotated[T, Depends(f)]` | 单端点 | **是** |

| 实测行为 | 结果 |
| --- | --- |
| 全局依赖参数 | 进每个路由的 `parameters`（`X-Request-Source`）|
| `/docs`、`/openapi.json` | **不受**全局依赖约束 |
| 路径以 `/admin` 开头但不在 router 里 | 不受 router 依赖 |
| 全局依赖抛错 | 所有路由 503 |
| 事后 `router.dependencies.append()` | 已注册路由不生效 |
| 全局 + 端点同一依赖 | 单请求只执行 1 次（缓存）|

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 用装饰器依赖却想拿返回值 | 拿不到 | 改用参数位置 |
| 以为 Router 依赖按路径前缀生效 | 未 include 的路由不受保护 | 显式 `include_router` |
| 路由注册后再 append 全局依赖 | 不生效 | 构造时传 |
| 全局依赖里做重 IO | 每个请求都付代价 | 只做轻量审计 |
| 全局依赖放鉴权 | `/docs` 绕过 | 用参数/中间件 |
| 以为全局依赖保护文档 | `/docs` 仍可访问 | 单独保护 |
| Router 依赖传 `Depends()` 空参 | 定义期报错 | 明确 callable |
| 在 router 上写 `dependencies` 但忘了 include | 路由 404 | 检查 include |
| 装饰器依赖与参数依赖重复写 | 执行两次（除非缓存）| 用同一对象复用 |
| 全局依赖改 `response` | 拿不到 response | 参数注入 `Response` |

## 毕业自查

- [ ] 能说出三个层级的覆盖范围
- [ ] 能解释「装饰器位置拿不到返回值」
- [ ] 能说出全局依赖不作用于哪些路径
- [ ] 能解释路径前缀 ≠ Router
- [ ] 能说明事后 append 不生效
- [ ] 动手题一：给所有 `/api/*` 路由加 `X-Api-Version` 检查
- [ ] 动手题二：用全局依赖记录耗时并写进响应头（提示：需 `Response`）

> 想看依赖在路由注册时如何被固化、`dependencies` 与参数位置的差别、全局依赖与中间件的分工、18 条坑，继续读 [`base.md`](./base.md)。