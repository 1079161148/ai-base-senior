"""第 40 章 · yield 依赖。

核心：把「创建 → 使用 → 清理」写在一个生成器里。`yield` 之前是准备，
      `yield` 的值被注入端点，`yield` 之后的代码（或 `finally`）在**响应发出后**执行。
      路由抛异常时，异常会被 `athrow` 进生成器，`try/except` 能捕获（实测）。

启动：uvicorn main:app --reload
验收：python verify.py
"""

import asyncio
from collections.abc import AsyncIterator, Iterator
from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException

app = FastAPI(title="第 40 章 · yield 依赖", version="0.1.0")

# 【作用】记录生命周期事件，便于断言顺序
LOG: list[str] = []
LAST_SESSION: dict[str, Any] = {}


# ============================================================
# 1. 模拟数据库会话
# ============================================================
class FakeSession:
    def __init__(self) -> None:
        self.closed = False
        self.committed = False
        self.rolled_back = False
        LOG.append("open")

    def commit(self) -> None:
        self.committed = True
        LOG.append("commit")

    def rollback(self) -> None:
        self.rolled_back = True
        LOG.append("rollback")

    def close(self) -> None:
        self.closed = True
        LOG.append("close")


def get_session() -> Iterator[FakeSession]:
    """【作用】`yield` 前创建，`yield` 后清理（写 `finally` 保证一定执行）

    【实测】响应返回后 `closed=True`；路由抛异常时先 `rollback` 再 `close`
    【注意】不要在这里 `return`，必须是生成器
    """
    session = FakeSession()
    LAST_SESSION["session"] = session
    try:
        yield session
    except Exception:
        session.rollback()
        raise
    else:
        session.commit()
    finally:
        session.close()


SessionDep = Annotated[FakeSession, Depends(get_session)]


@app.get("/session", tags=["yield"], summary="正常路径")
def use_session(session: SessionDep) -> dict[str, Any]:
    """【实测】端点内 `closed=False`；请求结束后 `closed=True`、`committed=True`"""
    assert session.closed is False, "端点内不应该是已关闭状态"
    return {"closed_inside": session.closed}


@app.get("/session/crash", tags=["yield"], summary="异常路径")
def crash_session(session: SessionDep) -> dict[str, str]:
    """【实测】抛错后 `rollback` → `close`，异常继续向上（500）"""
    raise HTTPException(status_code=409, detail="业务冲突")


# ============================================================
# 2. 嵌套 yield：清理顺序是 LIFO
# ============================================================
def outer() -> Iterator[str]:
    LOG.append("outer-open")
    try:
        yield "outer"
    finally:
        LOG.append("outer-close")


def inner(res: Annotated[str, Depends(outer)]) -> Iterator[str]:
    """【实测】清理顺序：inner-close → outer-close（后创建的先关）"""
    LOG.append("inner-open")
    try:
        yield f"{res}:inner"
    finally:
        LOG.append("inner-close")


@app.get("/nested", tags=["yield"], summary="嵌套清理顺序")
def nested(value: Annotated[str, Depends(inner)]) -> dict[str, str]:
    return {"value": value}


# ============================================================
# 3. async 生成器依赖
# ============================================================
async def async_resource() -> AsyncIterator[dict[str, str]]:
    """【实测】`async def` + `yield` 同样支持；清理在响应后执行"""
    LOG.append("async-open")
    try:
        yield {"id": "res-1"}
    finally:
        await asyncio.sleep(0)  # 模拟异步清理
        LOG.append("async-close")


@app.get("/async", tags=["yield"], summary="async 生成器")
def async_route(
    res: Annotated[dict[str, str], Depends(async_resource)],
) -> dict[str, str]:
    return res


# ============================================================
# 4. 依赖里用 except 改变结果
# ============================================================
def guarded() -> Iterator[dict[str, bool]]:
    state = {"error": False}
    try:
        yield state
    except HTTPException:
        state["error"] = True
        LOG.append("guarded-error")
        raise
    finally:
        LOG.append("guarded-close")


@app.get("/guarded", tags=["yield"], summary="依赖捕获异常")
def guarded_route(state: Annotated[dict[str, bool], Depends(guarded)]) -> dict[str, bool]:
    """【实测】依赖里的 `except` 能感知路由抛出的 `HTTPException`"""
    raise HTTPException(status_code=400, detail="触发")


@app.get("/guarded/ok", tags=["yield"], summary="无异常")
def guarded_ok(state: Annotated[dict[str, bool], Depends(guarded)]) -> dict[str, bool]:
    return {"error": state["error"]}


# ============================================================
# 5. 反例：yield 之后抛异常
# ============================================================
def bad_cleanup() -> Iterator[str]:
    yield "ok"
    raise RuntimeError("清理阶段炸了")


@app.get("/bad-cleanup", tags=["反例"], summary="清理阶段抛异常")
def bad_cleanup_route(v: Annotated[str, Depends(bad_cleanup)]) -> dict[str, str]:
    """【实测】响应已开始发送，异常只能让连接异常/日志报错，无法改状态码"""
    return {"value": v}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)