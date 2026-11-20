"""第 39 章 · 装饰器与全局依赖。

核心：`dependencies=[Depends(fn)]` 只做「执行 + 校验」，**拿不到返回值**。
      三个层级：端点装饰器 → `APIRouter` → `FastAPI(...)`。
      需要返回值时，只能用参数位置的 `Annotated[T, Depends(fn)]`。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Annotated, Any

from fastapi import APIRouter, Depends, FastAPI, Header, HTTPException, status

AUDIT: list[str] = []


# ============================================================
# 1. 全局依赖：审计（不拦截，只记录）
# ============================================================
def audit_log(
    x_source: Annotated[str | None, Header(alias="X-Request-Source")] = None,
) -> None:
    """【作用】挂在 `FastAPI(dependencies=[...])` 上，所有路由都会执行

    【实测】`/health`、`/admin/panel` 都记录了；`/docs` 与 `/openapi.json` 不受影响
    【注意】返回值 `None` 无法注入端点 —— 装饰器位置的依赖没有返回值通道
    """
    AUDIT.append(x_source or "unknown")


app = FastAPI(
    title="第 39 章 · 装饰器与全局依赖",
    version="0.1.0",
    dependencies=[Depends(audit_log)],
)


# ============================================================
# 2. 端点装饰器依赖：单点鉴权
# ============================================================
def require_token(x_token: Annotated[str | None, Header(alias="X-Token")] = None) -> str:
    if x_token != "secret":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Token 无效",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return x_token


@app.get(
    "/public",
    tags=["装饰器依赖"],
    summary="只挂全局依赖",
    dependencies=[Depends(require_token)],
)
def public() -> dict[str, str]:
    """【实测】无 X-Token → 401；端点体内**拿不到** token 值"""
    return {"ok": "true"}


# ============================================================
# 3. 参数位置 vs 装饰器位置：能不能拿到返回值
# ============================================================
@app.get("/compare/dec", tags=["对比"], summary="装饰器位置")
def with_decorator_dep() -> dict[str, Any]:
    """【关键】装饰器位置的依赖返回值被丢弃，端点无法使用"""
    return {"receives": "nothing"}


@app.get("/compare/param", tags=["对比"], summary="参数位置")
def with_param_dep(token: Annotated[str, Depends(require_token)]) -> dict[str, str]:
    """【关键】参数位置才能注入返回值"""
    return {"token": token}


# ============================================================
# 4. Router 级依赖：一组路由统一鉴权
# ============================================================
def require_admin(x_role: Annotated[str | None, Header(alias="X-Role")] = None) -> str:
    if x_role != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="需要 admin 角色")
    return x_role


admin_router = APIRouter(
    prefix="/admin",
    tags=["Router 依赖"],
    dependencies=[Depends(require_admin)],
)


@admin_router.get("/panel")
def panel() -> dict[str, str]:
    return {"panel": "admin"}


@admin_router.get("/stats")
def stats() -> dict[str, int]:
    return {"users": 2}


app.include_router(admin_router)


# ============================================================
# 5. 不需要任何依赖的端点（只受全局依赖影响）
# ============================================================
@app.get("/health", tags=["全局"], summary="健康检查")
def health() -> dict[str, str]:
    """【实测】只执行全局 `audit_log`，不需要 token/role"""
    return {"status": "ok"}


# ============================================================
# 6. 三层叠加：全局 + Router + 端点
# ============================================================
@app.get("/admin/ops", tags=["叠加"], summary="三层依赖叠加")
def ops() -> dict[str, Any]:
    """【注意】这个端点只挂了全局依赖，路径虽在 /admin 下但**不属于** admin_router

    【实测】不需要 X-Role（因为没 include 进 router）
    """
    return {"audit": list(AUDIT)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)