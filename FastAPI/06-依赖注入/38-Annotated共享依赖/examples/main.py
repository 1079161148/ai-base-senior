"""第 38 章 · Annotated 共享依赖。

核心：`type XDep = Annotated[T, Depends(fn)]` 把「类型 + 依赖」打包成一个名字。
      端点签名只写 `XDep`，不用重复 `Depends(...)`；IDE 与类型检查器也看得到 T。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Path, Query, status

app = FastAPI(title="第 38 章 · Annotated 共享依赖", version="0.1.0")

_ITEMS = [{"id": i, "name": f"商品 {i}"} for i in range(1, 21)]
_USERS = {"alice": {"name": "alice", "role": "admin"}, "bob": {"name": "bob", "role": "user"}}


# ============================================================
# 依赖函数
# ============================================================
class CommonQueryParams:
    def __init__(
        self,
        q: Annotated[str | None, Query(max_length=50)] = None,
        skip: Annotated[int, Query(ge=0)] = 0,
        limit: Annotated[int, Query(ge=1, le=100)] = 10,
    ) -> None:
        self.q = q
        self.skip = skip
        self.limit = limit


def get_user(x_user: Annotated[str | None, Header(alias="X-User")] = None) -> dict[str, Any]:
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


def require_admin(user: Annotated[dict[str, Any], Depends(get_user)]) -> dict[str, Any]:
    if user["role"] != "admin":
        raise HTTPException(status_code=403, detail="需要管理员")
    return user


# ============================================================
# 别名：全项目复用（Python 3.12 的 type 语句）
# ============================================================
type CommonsDep = Annotated[CommonQueryParams, Depends()]
type UserDep = Annotated[dict[str, Any], Depends(get_user)]
type AdminDep = Annotated[dict[str, Any], Depends(require_admin)]


# ============================================================
# 1. 同一个别名被多个端点复用
# ============================================================
@app.get("/items", tags=["别名"], summary="分页别名")
def list_items(commons: CommonsDep) -> dict[str, Any]:
    """【实测】别名与直接写 `Annotated[CommonQueryParams, Depends()]` 完全等价"""
    data = _ITEMS[commons.skip : commons.skip + commons.limit]
    return {"q": commons.q, "count": len(data)}


@app.get("/users", tags=["别名"], summary="同一别名复用")
def list_users(commons: CommonsDep) -> dict[str, Any]:
    return {"limit": commons.limit, "users": ["alice", "bob"]}


# ============================================================
# 2. 别名 + 自己的参数
# ============================================================
@app.get("/me", tags=["别名"], summary="UserDep")
def me(user: UserDep, detail: Annotated[bool, Query()] = False) -> dict[str, Any]:
    """【实测】`user` 的类型就是 `dict`，可 `.get()`；别名不改变运行时类型"""
    return user if detail else {"name": user["name"]}


# ============================================================
# 3. 别名嵌套：AdminDep 内部仍依赖 UserDep 的 get_user
# ============================================================
@app.get("/admin", tags=["别名"], summary="AdminDep")
def admin_panel(user: AdminDep) -> dict[str, Any]:
    """【实测】bob 访问 → 403，`get_user` 只执行一次（缓存，第 37 章）"""
    return {"admin": user["name"]}


# ============================================================
# 4. 别名内部就是 Annotated：可以再叠加约束吗？
# ============================================================
@app.get("/items/{item_id}", tags=["别名"], summary="别名 + 路径参数")
def get_item(
    item_id: Annotated[int, Path(ge=1, le=1000)],
    commons: CommonsDep,
) -> dict[str, Any]:
    """【实测】路径参数用 `Query(...)` 带约束会在**定义期**报
           `AssertionError: Cannot use Query for path param 'item_id'`
    """
    return {"item_id": item_id, "limit": commons.limit}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)