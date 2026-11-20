"""第 43 章 · 实战：鉴权与多租户。

核心：依赖链 `token → user → tenant`，租户由**服务端从 token 派生**（不信任客户端传的
      `X-Tenant`）。资源查询一律带 `tenant_id` 过滤；跨租户访问返回 **404** 而不是 403，
      避免泄露「这个 ID 存在」。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Request, status
from pydantic import BaseModel, Field

app = FastAPI(title="第 43 章 · 鉴权与多租户", version="0.1.0")

# 【作用】静态凭据表：token → 主体信息（真实项目查库/缓存）
_TOKENS: dict[str, dict[str, Any]] = {
    "tok-a": {"user": "alice", "tenant": "t-a", "role": "admin", "active": True},
    "tok-b": {"user": "bob", "tenant": "t-b", "role": "member", "active": True},
    "tok-off": {"user": "carol", "tenant": "t-c", "role": "member", "active": False},
}

# 【作用】资源带 tenant_id，隔离的根就在这里
_ITEMS: dict[int, dict[str, Any]] = {
    1: {"id": 1, "name": "A 租户的键盘", "tenant": "t-a"},
    2: {"id": 2, "name": "A 租户的鼠标", "tenant": "t-a"},
    3: {"id": 3, "name": "B 租户的显示器", "tenant": "t-b"},
}
_NEXT_ID = 4


# ============================================================
# 第 1 层：token → 主体
# ============================================================
def get_context(
    x_token: Annotated[str | None, Header(alias="X-Token", description="访问令牌")] = None,
) -> dict[str, Any]:
    """【实测】缺 token / 错误 token → 401；租户被禁用 → 403"""
    if not x_token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少 X-Token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    ctx = _TOKENS.get(x_token)
    if ctx is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Token 无效",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        )
    if not ctx["active"]:
        raise HTTPException(status_code=403, detail="账号或租户已停用")
    return ctx


# ============================================================
# 第 2 层：把租户写进 request.state，供后续/日志使用
# ============================================================
def tenant_context(
    request: Request,
    ctx: Annotated[dict[str, Any], Depends(get_context)],
) -> dict[str, Any]:
    """【作用】租户 id **只**来自 token，客户端传 `X-Tenant` 一律忽略

    【实测】请求头带 `X-Tenant: t-b` 仍按 token 的 `t-a` 隔离
    【注意】不要用 `assert` 做安全校验（异常会变 500），直接忽略或显式 403
    """
    request.state.tenant_id = ctx["tenant"]
    request.state.user = ctx["user"]
    return ctx


CtxDep = Annotated[dict[str, Any], Depends(tenant_context)]


def _find_item(item_id: int, tenant: str) -> dict[str, Any]:
    """【关键】带租户过滤的查询：不存在与不属于本租户，对外都表现为「不存在」"""
    item = _ITEMS.get(item_id)
    if item is None or item["tenant"] != tenant:
        raise HTTPException(status_code=404, detail=f"商品 {item_id} 不存在")
    return item


# ============================================================
# 端点
# ============================================================
@app.get("/items", tags=["多租户"], summary="列表（自动过滤租户）")
def list_items(ctx: CtxDep) -> dict[str, Any]:
    """【实测】alice 只看到 2 条，bob 只看到 1 条"""
    rows = [item for item in _ITEMS.values() if item["tenant"] == ctx["tenant"]]
    return {"tenant": ctx["tenant"], "items": rows, "count": len(rows)}


@app.get("/items/{item_id}", tags=["多租户"], summary="跨租户 → 404")
def get_item(item_id: int, ctx: CtxDep) -> dict[str, Any]:
    """【实测】bob 读 item 1（属于 t-a）→ 404，与「不存在」无法区分"""
    return _find_item(item_id, ctx["tenant"])


class ItemIn(BaseModel):
    name: Annotated[str, Field(min_length=1, max_length=50)]


@app.post("/items", status_code=201, tags=["多租户"], summary="创建自动绑定租户")
def create_item(item: ItemIn, ctx: CtxDep) -> dict[str, Any]:
    """【实测】请求体里传 tenant 字段会被忽略（模型没这个字段）"""
    global _NEXT_ID
    row = {"id": _NEXT_ID, "name": item.name, "tenant": ctx["tenant"]}
    _ITEMS[_NEXT_ID] = row
    _NEXT_ID += 1
    return row


@app.get("/whoami", tags=["多租户"], summary="从 request.state 读上下文")
def whoami(request: Request, ctx: CtxDep) -> dict[str, Any]:
    """【实测】依赖写入的 `request.state` 在端点里可读，与注入值一致"""
    return {
        "user": ctx["user"],
        "tenant": ctx["tenant"],
        "state_tenant": request.state.tenant_id,
        "state_user": request.state.user,
        "role": ctx["role"],
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)