# 37 子依赖与缓存

## 一句话结论

依赖可以依赖依赖，形成树，执行顺序是**深度优先、先子后父**（实测 `user → perms → role`）。**同一请求内**，同一个可调用对象（同一个函数/实例）默认只执行一次，结果被复用——即使端点自己也声明了 `Depends(get_user)`（实测 `CALL_LOG.count("user") == 1`）。`Depends(fn, use_cache=False)` 强制重算。缓存**不跨请求**，且按「可调用对象」区分：不同函数各自缓存。

学完这一章，你能：搭三层鉴权链、解释为什么 `get_user` 不会被执行两次、知道什么时候该关缓存。

## 最小可运行案例

```python
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException

app = FastAPI()

CALLS: list[str] = []


def get_user(x_user: str | None = Header(None)) -> dict[str, Any]:
    CALLS.append("user")
    if not x_user:
        raise HTTPException(401, "缺少 X-User")
    return {"name": x_user}


def get_permissions(user: Annotated[dict, Depends(get_user)]) -> dict[str, Any]:
    CALLS.append("perms")
    return {"user": user["name"], "scope": "read"}


def require_role(perms: Annotated[dict, Depends(get_permissions)]) -> dict[str, Any]:
    CALLS.append("role")
    return perms


@app.get("/admin")
def admin(
    info: Annotated[dict, Depends(require_role)],
    user: Annotated[dict, Depends(get_user)],   # 复用缓存，不会重复执行
) -> dict:
    return {"info": info, "user": user["name"], "calls": CALLS}
```

完整版本（`use_cache=False`、OpenAPI 去重、缓存 key 验证）见 `examples/main.py`。

## 怎么跑

```powershell
cd "06-依赖注入\37-子依赖与缓存\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 三层依赖 -> user=alice, role=admin
[PASS] 执行顺序 -> calls=['user', 'perms', 'role']
[PASS] 缓存只执行一次 -> CALL_LOG=['user', 'perms', 'role']
[PASS] use_cache=False -> calls=['user', 'user']（2 次）
[PASS] 缓存不跨请求 -> 两次请求 user 调用 1 → 2
[PASS] 叶子 401 -> 401，CALL_LOG=['user']
[PASS] 用户 404 -> 404，perms/role 未执行
[PASS] 权限 403 -> 403，CALL_LOG=['user', 'perms']
[PASS] 角色 403 -> 403 需要角色 admin
[PASS] OpenAPI 参数去重 -> parameters=['role', 'scope', 'X-User']（X-User 仅一次）
[PASS] 缓存 key 是可调用对象 -> seen=['a', 'b']（dep_a 只跑一次）
[PASS] 同请求同对象 -> 同一请求内是同一个对象

结果：12/12 通过
```

## 核心 API 速查

| 概念 | 说明 |
| --- | --- |
| 子依赖 | 依赖函数的参数也能写 `Depends(...)` |
| 缓存作用域 | **单请求**；跨请求重新执行 |
| 缓存 key | 可调用对象本身（函数/实例），不是参数值 |
| `use_cache=False` | 该处强制重算 |
| 执行顺序 | 深度优先，子依赖先于父依赖 |
| 异常传播 | 任一节点抛错 → 整棵树停止，后续不执行 |

| 实测行为 | 结果 |
| --- | --- |
| 端点 + 子依赖都声明 `get_user` | 只执行 1 次 |
| `Depends(get_user, use_cache=False)` | 同请求执行 2 次 |
| 连续两次请求 | `user` 调用数 1 → 2 |
| 不同函数 `dep_a`/`dep_b` | 各自执行 1 次 |
| `yield` 依赖 | 同请求内是同一个对象（第 40 章展开）|
| OpenAPI | `X-User` 被多层声明，只出现 1 次 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 以为依赖全局只跑一次 | 每请求都跑 | 缓存是单请求 |
| 用不同参数调同一依赖期望不同结果 | 命中缓存，返回旧值 | `use_cache=False` |
| 每次 `Depends(make_dep(...))` 新建闭包 | 不共享缓存、执行多次 | 复用同一闭包对象 |
| 依赖里查库却在多层重复声明 | 以为查多次，其实 1 次 | 确认缓存行为 |
| 用缓存依赖存请求级状态 | 同一请求内共享，跨请求不共享 | 用 `request.state` 或明确作用域 |
| 在 `yield` 依赖退出后还用返回值 | 资源已关闭 | 只在作用域内用 |
| 依赖树很深还做重 IO | 首请求慢 | 拆缓存/异步 |
| 用依赖缓存替代业务缓存 | 语义不同 | Redis/进程缓存 |
| 叶子依赖抛 401 却继续执行 | 不会发生（实测停止）| 依赖 `raise` |
| 依赖返回可变对象并修改 | 同请求内其他使用者受影响 | 返回副本或设为只读 |

## 毕业自查

- [ ] 能画出三层依赖树并说出执行顺序
- [ ] 能解释「同一请求只执行一次」的 key 是什么
- [ ] 能写出 `use_cache=False` 的场景与代价
- [ ] 能说明缓存不跨请求
- [ ] 能解释为什么 OpenAPI 不重复列参数
- [ ] 动手题一：加一层「租户校验」并保证 `get_user` 仍只跑一次
- [ ] 动手题二：把 `get_permissions` 的结果缓存到 `request.state` 供中间件复用

> 想看 `solve_dependencies` 的缓存实现、`use_cache` 在递归中的传播、`yield` 与缓存的交互、18 条坑，继续读 [`base.md`](./base.md)。