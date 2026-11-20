"""第 48 章 · 作用域授权（SecurityScopes）。

核心：端点声明「需要哪些 scope」→ `Security(fn, scopes=[...])`；
      框架把它们汇总成 `SecurityScopes`，注入依赖里；
      依赖比对「token 里的 scopes」是否覆盖，不覆盖返回
      403 + `WWW-Authenticate: Bearer scope="..." error="insufficient_scope"`。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm, SecurityScopes
from pydantic import BaseModel

import jwt_lite as jwt  # 本章复用第 47 章的手写实现（同目录 jwt_lite.py）

app = FastAPI(title="第 48 章 · 作用域授权", version="0.1.0")

# 【关键】`scopes` 字典会写进 OpenAPI 的 `flows.password.scopes`
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="token",
    scopes={
        "items:read": "读取商品",
        "items:write": "创建/修改商品",
        "admin": "管理后台",
    },
)

_USERS: dict[str, dict[str, Any]] = {
    "alice": {"username": "alice", "scopes": ["items:read"]},
    "admin": {"username": "admin", "scopes": ["items:read", "items:write", "admin"]},
    "bob": {"username": "bob", "scopes": []},
}


class TokenOut(BaseModel):
    access_token: str
    token_type: str
    scopes: list[str]


# ============================================================
# 1. 发 token：客户端「请求」的 scope 与服务端「授予」的要分开
# ============================================================
@app.post("/token", response_model=TokenOut, tags=["OAuth2"], summary="按请求的 scope 签发")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> TokenOut:
    """【实测】`form.scopes` 是客户端在表单 `scope=items:read admin` 里请求的列表

    【要点】只授予「用户实际拥有 ∩ 请求的」，绝不因为客户端要就给
    """
    user = _USERS.get(form.username)
    if user is None:
        raise HTTPException(status_code=400, detail="用户名或密码错误")

    granted = [s for s in form.scopes if s in user["scopes"]]
    token = jwt.create_access_token({"sub": user["username"], "scopes": granted})
    return TokenOut(access_token=token, token_type="bearer", scopes=granted)


# ============================================================
# 2. 依赖：校验 token + 校验 scope
# ============================================================
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
    security_scopes: SecurityScopes,
) -> dict[str, Any]:
    """【实测】`security_scopes.scopes` 是本请求**所有**依赖声明的 scope 并集

    【注意】403 的 `WWW-Authenticate` 必须带 `scope="..."` 与
           `error="insufficient_scope"`，客户端才能据此申请更多权限
    """
    try:
        payload = jwt.decode_token(token)
    except jwt.InvalidToken as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"token 无效：{exc.reason}",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        ) from exc

    user = _USERS.get(payload.get("sub", ""))
    if user is None:
        raise HTTPException(status_code=401, detail="用户不存在")

    token_scopes: list[str] = payload.get("scopes", [])
    for scope in security_scopes.scopes:
        if scope not in token_scopes:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=f"缺少 scope: {scope}",
                headers={
                    "WWW-Authenticate": (
                        f'Bearer scope="{security_scopes.scope_str}" '
                        'error="insufficient_scope"'
                    )
                },
            )
    return user


# ============================================================
# 3. 端点：单 scope / 多 scope
# ============================================================
@app.get("/items", tags=["作用域"], summary="需要 items:read")
async def read_items(
    user: Annotated[dict[str, Any], Security(get_current_user, scopes=["items:read"])],
) -> dict[str, Any]:
    return {"items": [1, 2, 3], "user": user["username"]}


@app.post("/items", tags=["作用域"], summary="需要 items:write")
async def create_item(
    user: Annotated[dict[str, Any], Security(get_current_user, scopes=["items:write"])],
) -> dict[str, str]:
    return {"created_by": user["username"]}


@app.delete("/items", tags=["作用域"], summary="需要两个 scope")
async def delete_item(
    user: Annotated[
        dict[str, Any],
        Security(get_current_user, scopes=["items:read", "items:write"]),
    ],
) -> dict[str, Any]:
    """【实测】多 scope 是 **AND**：`security` 里同一个对象列出两个 → 都要满足"""
    return {"deleted_by": user["username"], "scopes": user["scopes"]}


@app.get("/admin", tags=["作用域"], summary="需要 admin")
async def admin_panel(
    user: Annotated[dict[str, Any], Security(get_current_user, scopes=["admin"])],
) -> dict[str, str]:
    return {"admin": user["username"]}


# ============================================================
# 4. 只校验不取用户（装饰器位置 + scopes）
# ============================================================
@app.get(
    "/audit",
    tags=["作用域"],
    summary="dependencies=[Security(..., scopes=[...])]",
    dependencies=[Security(get_current_user, scopes=["items:read"])],
)
async def audit() -> dict[str, str]:
    return {"ok": "true"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)