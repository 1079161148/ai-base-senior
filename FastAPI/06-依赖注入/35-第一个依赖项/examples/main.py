"""第 35 章 · 第一个依赖项（Depends）。

核心：把「多个端点都要用的参数」抽成一个函数，用 `Depends()` 声明。
      框架会先解析这个函数的参数（它们照样进 OpenAPI），再把返回值注入端点。
      依赖里可以 `raise HTTPException`，路由函数根本不会执行。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status

app = FastAPI(title="第 35 章 · 第一个依赖项", version="0.1.0")

_ITEMS = [{"id": i, "name": f"商品 {i}"} for i in range(1, 21)]


# ============================================================
# 1. 被复用的依赖：分页参数
# ============================================================
async def common_parameters(
    q: Annotated[str | None, Query(max_length=50, description="搜索关键词")] = None,
    skip: Annotated[int, Query(ge=0, description="跳过条数")] = 0,
    limit: Annotated[int, Query(ge=1, le=100, description="每页条数")] = 10,
) -> dict[str, Any]:
    """【作用】声明一次，所有列表端点共享

    【实测】OpenAPI 里 `/items` 的 parameters 就是 `q`/`skip`/`limit` 三个 query 参数，
           与「直接写在端点签名里」完全一样
    【注意】依赖函数的参数校验失败 → 422，`loc` 是 `["query", "limit"]`，不是依赖名
    """
    return {"q": q, "skip": skip, "limit": limit}


# ============================================================
# 2. 两个端点复用同一个依赖
# ============================================================
@app.get("/items", tags=["Depends"], summary="列表（用依赖）")
def list_items(
    commons: Annotated[dict[str, Any], Depends(common_parameters)],
) -> dict[str, Any]:
    """【实测】不传参 → `skip=0, limit=10`；`?limit=200` → 422"""
    start = commons["skip"]
    data = _ITEMS[start : start + commons["limit"]]
    return {"params": commons, "count": len(data), "first": data[0]["id"] if data else None}


@app.get("/users", tags=["Depends"], summary="另一端点复用")
def list_users(
    commons: Annotated[dict[str, Any], Depends(common_parameters)],
) -> dict[str, Any]:
    """【实测】同一依赖在另一端点自动展开，无需重复声明参数"""
    return {"params": commons, "users": ["alice", "bob"][: commons["limit"]]}


# ============================================================
# 3. 依赖里抛错：路由不执行
# ============================================================
def require_token(x_token: Annotated[str | None, Header(alias="X-Token")] = None) -> str:
    """【实测】缺 token → 401，响应里没有路由函数的任何痕迹"""
    if x_token != "secret":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="依赖要求登录",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return x_token


@app.get("/secure", tags=["Depends"], summary="依赖里抛 401")
def secure(token: Annotated[str, Depends(require_token)]) -> dict[str, str]:
    return {"token": token, "route_ran": "true"}


# ============================================================
# 4. 依赖里拿 Request：能读头、路径、状态
# ============================================================
async def client_info(request: Request) -> dict[str, str]:
    """【作用】依赖可以声明 `Request`，不用它出现在端点签名里

    【实测】能读到 `user-agent` 与 `client.host`，端点只拿到结果
    """
    return {
        "ua": request.headers.get("user-agent", ""),
        "path": request.url.path,
        "method": request.method,
    }


@app.get("/client", tags=["Depends"], summary="依赖读 Request")
def client(
    info: Annotated[dict[str, str], Depends(client_info)],
) -> dict[str, str]:
    return info


# ============================================================
# 5. 依赖与路径参数并存
# ============================================================
@app.get("/items/{item_id}", tags=["Depends"], summary="路径参数 + 依赖")
def get_item(
    item_id: int,
    commons: Annotated[dict[str, Any], Depends(common_parameters)],
) -> dict[str, Any]:
    """【注意】参数顺序无要求：路径参数、依赖、普通 query 可任意排列"""
    return {"item_id": item_id, "params": commons}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)