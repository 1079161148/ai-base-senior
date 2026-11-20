"""第 37 章 · 子依赖与缓存。

核心：依赖可以依赖别的依赖，形成树。**同一请求内**，同一个可调用对象
      （同一个函数/实例）默认只执行一次，结果被缓存并复用；
      `Depends(fn, use_cache=False)` 强制重算。缓存不跨请求。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status

app = FastAPI(title="第 37 章 · 子依赖与缓存", version="0.1.0")

# 【作用】记录依赖执行顺序与次数，便于断言「缓存生效」
CALL_LOG: list[str] = []

_USERS = {
    "alice": {"name": "alice", "roles": {"admin", "user"}},
    "bob": {"name": "bob", "roles": {"user"}},
}
_SCOPES = {"admin": {"read", "write", "delete"}, "user": {"read"}}


# ============================================================
# 第 1 层：认证 → 用户
# ============================================================
def get_user(
    x_user: Annotated[str | None, Header(alias="X-User", description="用户名")] = None,
) -> dict[str, Any]:
    """【实测】同一请求里被多处 `Depends` 时只执行一次（CALL_LOG 只有一条 user）"""
    CALL_LOG.append("user")
    if x_user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 X-User",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = _USERS.get(x_user)
    if user is None:
        raise HTTPException(status_code=404, detail=f"用户 {x_user} 不存在")
    return user


# ============================================================
# 第 2 层：用户 → 权限（依赖 get_user）
# ============================================================
def get_permissions(
    user: Annotated[dict[str, Any], Depends(get_user)],
    scope: Annotated[str, Query(description="要检查的权限名")] = "read",
) -> dict[str, Any]:
    """【实测】`get_user` 已在同请求执行过 → 直接复用，不重复调用"""
    CALL_LOG.append("perms")
    scopes: set[str] = set()
    for role in user["roles"]:
        scopes |= _SCOPES[role]
    if scope not in scopes:
        raise HTTPException(status_code=403, detail=f"缺少权限 {scope}")
    return {"user": user["name"], "scope": scope, "scopes": sorted(scopes)}


# ============================================================
# 第 3 层：权限 → 角色校验（依赖 get_permissions）
# ============================================================
def require_role(
    perms: Annotated[dict[str, Any], Depends(get_permissions)],
    role: Annotated[str, Query(description="要求角色")] = "user",
) -> dict[str, Any]:
    CALL_LOG.append("role")
    if role not in _USERS[perms["user"]]["roles"]:
        raise HTTPException(status_code=403, detail=f"需要角色 {role}")
    return {**perms, "role": role}


# ============================================================
# 依赖树的效果
# ============================================================
@app.get("/admin", tags=["依赖树"], summary="三层依赖")
def admin(
    info: Annotated[dict[str, Any], Depends(require_role)],
    user: Annotated[dict[str, Any], Depends(get_user)],
) -> dict[str, Any]:
    """【实测】执行顺序 `user → perms → role`，`user` 只跑一次

    【关键】端点自己也声明 `Depends(get_user)` —— 与子依赖共用同一份缓存
    """
    return {"info": {k: v for k, v in info.items() if k != "scopes"}, "user": user["name"]}


@app.get("/order", tags=["依赖树"], summary="看执行顺序")
def order(
    _: Annotated[dict[str, Any], Depends(require_role)],
) -> dict[str, list[str]]:
    """【实测】返回 `["user", "perms", "role"]`：深度优先、先子后父"""
    return {"calls": list(CALL_LOG)}


# ============================================================
# use_cache=False：强制重算
# ============================================================
@app.get("/nocache", tags=["缓存"], summary="use_cache=False")
def nocache(
    cached: Annotated[dict[str, Any], Depends(get_user)],
    fresh: Annotated[dict[str, Any], Depends(get_user, use_cache=False)],
) -> dict[str, Any]:
    """【实测】同一请求里 `get_user` 执行 **2 次**：一次缓存、一次强制重算

    【用途】依赖结果带随机性/需要最新值时；但别滥用，会放大 IO
    """
    return {"cached": cached["name"], "fresh": fresh["name"], "calls": list(CALL_LOG)}


# ============================================================
# 缓存作用域：不跨请求
# ============================================================
@app.get("/count", tags=["缓存"], summary="缓存不跨请求")
def count(user: Annotated[dict[str, Any], Depends(get_user)]) -> dict[str, int]:
    """【实测】连续两次请求 → 每次 `user` 各执行一次（累计 2）"""
    return {"calls": len(CALL_LOG), "user_calls": CALL_LOG.count("user")}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)