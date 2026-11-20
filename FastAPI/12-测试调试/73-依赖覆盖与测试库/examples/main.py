"""第 73 章 · 依赖覆盖与测试库。

`app.dependency_overrides[原函数] = 替身` 让「真实路由 + 假数据库」成为可能：

    真实路由 → 覆盖 get_db → 内存字典
    schema、参数校验、响应序列化全是真的，只有数据层被换掉

【要点】key 必须是**同一个函数对象**，不是字符串、不是同名函数。
         覆盖是全局的，用完必须清理，否则污染后续用例。

启动：uvicorn main:app --reload
验收：python verify.py
或：  uv run pytest -q
"""

from dataclasses import dataclass
from typing import Annotated, Any, Iterator

from fastapi import Depends, FastAPI, Header, HTTPException, Query, status
from pydantic import BaseModel, Field

app = FastAPI(title="第 73 章 · 依赖覆盖与测试库", version="0.1.0")

# ------------------------------------------------------------
# 真实数据（测试里会被替换）
# ------------------------------------------------------------
REAL_DB: dict[str, Any] = {
    "users": {1: {"id": 1, "name": "真实用户"}, 2: {"id": 2, "name": "另一个"}},
    "next_id": 3,
}

ADMIN_TOKEN = "admin-secret"


# ------------------------------------------------------------
# 依赖
# ------------------------------------------------------------
def get_db() -> Iterator[dict[str, Any]]:
    """【要点】生成器依赖：请求结束会走 `finally`，适合会话清理"""
    db = REAL_DB
    try:
        yield db
    finally:
        pass


DBDep = Annotated[dict[str, Any], Depends(get_db)]


@dataclass
class Settings:
    max_items: int = 100
    debug: bool = True


def get_settings() -> Settings:
    return Settings()


SettingsDep = Annotated[Settings, Depends(get_settings)]


def get_current_user(x_token: Annotated[str | None, Header()] = None) -> str:
    """【要点】覆盖它就能绕过鉴权，不用伪造真令牌"""
    if x_token != ADMIN_TOKEN:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="bad token")
    return "admin"


UserDep = Annotated[str, Depends(get_current_user)]


class UserRepo:
    """【要点】嵌套依赖：覆盖 `get_db` 时它自动跟着换"""

    def __init__(self, db: dict[str, Any]) -> None:
        self.db = db

    def all(self, limit: int) -> list[dict[str, Any]]:
        return list(self.db["users"].values())[:limit]

    def get(self, user_id: int) -> dict[str, Any] | None:
        return self.db["users"].get(user_id)

    def add(self, name: str) -> dict[str, Any]:
        new_id = self.db["next_id"]
        user = {"id": new_id, "name": name}
        self.db["users"][new_id] = user
        self.db["next_id"] = new_id + 1
        return user


def get_repo(db: DBDep) -> UserRepo:
    return UserRepo(db)


RepoDep = Annotated[UserRepo, Depends(get_repo)]


# ------------------------------------------------------------
# 端点
# ------------------------------------------------------------
class UserCreate(BaseModel):
    name: str = Field(min_length=1, max_length=30)


@app.get("/users", tags=["用户"], summary="用户列表")
def list_users(
    repo: RepoDep,
    settings: SettingsDep,
    limit: Annotated[int, Query(ge=1, le=50)] = 10,
) -> list[dict[str, Any]]:
    return repo.all(min(limit, settings.max_items))


@app.get("/users/{user_id}", tags=["用户"], summary="用户详情")
def read_user(user_id: int, repo: RepoDep) -> dict[str, Any]:
    user = repo.get(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="user not found")
    return user


@app.post("/users", tags=["用户"], summary="新建用户", status_code=201)
def create_user(payload: UserCreate, repo: RepoDep) -> dict[str, Any]:
    return repo.add(payload.name)


@app.get("/me", tags=["鉴权"], summary="需要令牌")
def read_me(user: UserDep) -> dict[str, str]:
    return {"user": user}


@app.get("/config", tags=["诊断"], summary="读配置")
def read_config(settings: SettingsDep) -> dict[str, Any]:
    return {"max_items": settings.max_items, "debug": settings.debug}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)