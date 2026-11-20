"""第 41 章 · 依赖覆盖（dependency_overrides）。

核心：`app.dependency_overrides[原依赖] = 替身` —— key 是**可调用对象本身**，
      所以必须用同一个函数/类对象作 key（不能靠名字）。
      覆盖只影响当前 app，测试结束要清掉，否则会污染后续用例。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from collections.abc import Iterator
from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException

app = FastAPI(title="第 41 章 · 依赖覆盖", version="0.1.0")

REAL_CALLS: list[str] = []


# ============================================================
# 1. 真实依赖：数据库会话（yield）
# ============================================================
def get_db() -> Iterator[dict[str, str]]:
    """【作用】真实实现：开连接（这里用 dict 模拟）并记录调用"""
    REAL_CALLS.append("open")
    try:
        yield {"source": "real-db"}
    finally:
        REAL_CALLS.append("close")


DbDep = Annotated[dict[str, str], Depends(get_db)]


@app.get("/items", tags=["覆盖"], summary="读数据库")
def list_items(db: DbDep) -> dict[str, Any]:
    """【实测】未被覆盖时 `source == "real-db"`"""
    return {"source": db["source"], "items": [1, 2, 3]}


# ============================================================
# 2. 嵌套依赖：覆盖子依赖
# ============================================================
def get_config(db: DbDep) -> dict[str, str]:
    """【作用】依赖 `get_db` —— 覆盖 `get_db` 后这里自动用替身"""
    return {"db": db["source"], "env": "prod"}


@app.get("/config", tags=["覆盖"], summary="嵌套依赖")
def read_config(config: Annotated[dict[str, str], Depends(get_config)]) -> dict[str, str]:
    return config


# ============================================================
# 3. 类依赖：key 是类对象
# ============================================================
class Clock:
    def __init__(self) -> None:
        self.now = "2026-11-18T10:00:00"

    def __call__(self) -> str:
        return self.now


@app.get("/now", tags=["覆盖"], summary="类依赖可被覆盖")
def now(clock: Annotated[Clock, Depends(Clock)]) -> dict[str, str]:
    return {"now": clock.now}


# ============================================================
# 4. 鉴权依赖：测试里想绕过
# ============================================================
def require_token(x_token: Annotated[str | None, Header(alias="X-Token")] = None) -> str:
    if x_token != "secret":
        raise HTTPException(status_code=401, detail="X-Token 无效")
    return x_token


@app.get("/me", tags=["覆盖"], summary="鉴权依赖")
def me(token: Annotated[str, Depends(require_token)]) -> dict[str, str]:
    return {"token": token}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)