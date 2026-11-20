"""第 46 章 · 获取当前用户。

核心：把第 45 章拿到的 **token 字符串** 换成 **用户对象**，分两级依赖：
      `oauth2_scheme`（取 token）→ `get_current_user`（查用户）
      → `get_current_active_user`（判停用）。
      本章 token 仍是「查表映射」，真正的 JWT 解析在第 47 章。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel, EmailStr

app = FastAPI(title="第 46 章 · 获取当前用户", version="0.1.0")

CALLS: list[str] = []

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


# ============================================================
# 数据模型：对外模型不含密码
# ============================================================
class User(BaseModel):
    """【作用】内部用户模型（含密码哈希）"""

    username: str
    email: str
    full_name: str | None = None
    hashed_password: str
    disabled: bool = False


class UserOut(BaseModel):
    """【作用】对外模型：没有 `hashed_password`，靠 `response_model` 过滤"""

    username: str
    email: EmailStr
    full_name: str | None = None


class Token(BaseModel):
    access_token: str
    token_type: str


_DB: dict[str, User] = {
    "alice": User(
        username="alice",
        email="alice@example.com",
        full_name="Alice Chen",
        hashed_password="hashed:alice123",
        disabled=False,
    ),
    "bob": User(
        username="bob",
        email="bob@example.com",
        full_name="Bob Wang",
        hashed_password="hashed:bob123",
        disabled=True,
    ),
}

# 【作用】token → username 的映射表；第 47 章换成 JWT 解码
_TOKENS: dict[str, str] = {"token-alice": "alice", "token-bob": "bob"}


def _unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
    )


# ============================================================
# 1. 登录（与第 45 章一致）
# ============================================================
@app.post("/token", response_model=Token, tags=["认证"], summary="换 token")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> Token:
    user = _DB.get(form.username)
    if user is None or user.hashed_password != f"hashed:{form.password}":
        raise HTTPException(status_code=400, detail="用户名或密码错误")
    for token, name in _TOKENS.items():
        if name == user.username:
            return Token(access_token=token, token_type="bearer")
    raise HTTPException(status_code=400, detail="该用户没有可用 token")


# ============================================================
# 2. token → 用户
# ============================================================
async def get_current_user(
    token: Annotated[str, Depends(oauth2_scheme)],
) -> User:
    """【实测】token 无效返回 **401**（不是 404），避免暴露「这个用户存在」

    【注意】依赖链里 `oauth2_scheme` 已经负责 401（缺失/前缀错），
            这里只处理「token 格式对但查不到」
    """
    CALLS.append("get_current_user")
    username = _TOKENS.get(token)
    if username is None:
        raise _unauthorized("无效的 token")
    user = _DB.get(username)
    if user is None:
        raise _unauthorized("用户不存在")
    return user


CurrentUserDep = Annotated[User, Depends(get_current_user)]


# ============================================================
# 3. 再加一层：停用判断
# ============================================================
async def get_current_active_user(user: CurrentUserDep) -> User:
    """【实测】停用用户 → **400** `Inactive user`（官方示例约定），
           也可以选 403，但要与前端约定一致
    """
    CALLS.append("get_current_active_user")
    if user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


ActiveUserDep = Annotated[User, Depends(get_current_active_user)]


# ============================================================
# 端点
# ============================================================
@app.get("/users/me", response_model=UserOut, tags=["当前用户"], summary="我是谁")
async def read_me(user: ActiveUserDep) -> Any:
    """【实测】响应里没有 `hashed_password`；依赖链同请求只解析一次"""
    return user


@app.get("/users/me/raw", tags=["当前用户"], summary="不套模型（会泄露字段）")
async def read_me_raw(user: ActiveUserDep) -> dict[str, Any]:
    """【反例】不加 `response_model` 时，`model_dump()` 会把 `hashed_password` 带出去

    【实测】这里只列出字段名以证明风险，不真的输出哈希值
    """
    return {"dumped_fields": sorted(user.model_dump()), "calls": list(CALLS)}


@app.get("/users/me/name", tags=["当前用户"], summary="只返回名字")
async def read_me_name(user: ActiveUserDep) -> dict[str, Any]:
    """【实测】`CALLS` 里每个依赖各出现一次，证明同请求内只解析一次（第 37 章）"""
    return {"hello": user.full_name or user.username, "calls": list(CALLS)}


# ============================================================
# 4. 可选用户：匿名也能访问
# ============================================================
oauth2_optional = OAuth2PasswordBearer(tokenUrl="token", auto_error=False)


async def get_optional_user(
    token: Annotated[str | None, Depends(oauth2_optional)],
) -> User | None:
    if token is None:
        return None
    username = _TOKENS.get(token)
    return _DB.get(username) if username else None


@app.get("/greet", tags=["当前用户"], summary="可选登录")
async def greet(user: Annotated[User | None, Depends(get_optional_user)]) -> dict[str, str]:
    """【实测】无 token → 匿名问候；有 token → 带名字"""
    return {"message": f"你好，{user.full_name}" if user else "你好，游客"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)