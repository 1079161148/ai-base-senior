"""第 45 章 · OAuth2 密码流。

核心：`/token` 端点用 `OAuth2PasswordRequestForm` 收**表单**
      （`username`/`password`/`grant_type`/`scope`/`client_id`/`client_secret`），
      校验通过后返回 `{"access_token": ..., "token_type": "bearer"}`；
      受保护端点用 `OAuth2PasswordBearer(tokenUrl="token")` 从
      `Authorization: Bearer <token>` 取值。文档里会出现 Authorize 面板。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

app = FastAPI(title="第 45 章 · OAuth2 密码流", version="0.1.0")

# 【关键】tokenUrl 是相对路径 "token"（会原样写进 OpenAPI，见 verify）
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

# 【作用】可选登录版本：没 token 时不报错，返回 None
oauth2_scheme_optional = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)

_FAKE_USERS: dict[str, dict[str, Any]] = {
    "alice": {"username": "alice", "password": "alice123", "disabled": False},
    "bob": {"username": "bob", "password": "bob123", "disabled": True},
}


# ============================================================
# 1. 发 token：表单提交，不是 JSON
# ============================================================
@app.post("/token", tags=["OAuth2"], summary="用户名密码换 token")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> dict[str, str]:
    """【实测】必须用 `application/x-www-form-urlencoded`；发 JSON → 422

    【要点】响应字段名是 `access_token`（下划线）与 `token_type: bearer`，
            OAuth2 客户端按规范解析这两个键，不能随便改名
    """
    user = _FAKE_USERS.get(form.username)
    if user is None or user["password"] != form.password:
        # 【注意】OAuth2 规范建议密码错误返回 400 + error 字段，而不是 401
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="用户名或密码错误",
        )
    if user["disabled"]:
        raise HTTPException(status_code=400, detail="用户已停用")
    return {
        "access_token": f"token-for-{user['username']}",
        "token_type": "bearer",
    }


# ============================================================
# 2. 消费 token
# ============================================================
@app.get("/users/me", tags=["OAuth2"], summary="受保护端点")
def read_me(token: Annotated[str, Depends(oauth2_scheme)]) -> dict[str, str]:
    """【实测】缺 `Authorization: Bearer xxx` → 401 + `WWW-Authenticate: Bearer`

    【注意】这里只演示「拿到 token 字符串」，真正的解析在第 46–47 章
    """
    return {"token": token}


@app.get("/users/me/soft", tags=["OAuth2"], summary="可选登录")
def read_me_optional(
    token: Annotated[str | None, Depends(oauth2_scheme_optional)],
) -> dict[str, Any]:
    """【实测】`auto_error=False` → 没 token 时得到 `None`，端点自己决定是否放行"""
    return {"anonymous": token is None, "token": token}


# ============================================================
# 3. 表单里还能拿到什么
# ============================================================
@app.post("/token/debug", tags=["OAuth2"], summary="表单字段全览")
def token_debug(form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> dict[str, Any]:
    """【实测】`form` 含 `grant_type`/`scopes`/`client_id`/`client_secret` 等字段，
           未传时 `grant_type=None`、`scopes=[]`
    """
    return {
        "username": form.username,
        "grant_type": form.grant_type,
        "scopes": form.scopes,
        "client_id": form.client_id,
        "client_secret": form.client_secret,
    }


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)