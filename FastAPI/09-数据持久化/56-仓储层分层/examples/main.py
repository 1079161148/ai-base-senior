"""第 56 章 · 仓储层分层。

核心：把「HTTP / 业务 / SQL」拆成三层，各自只有一个变化理由。
      - `router.py`     只做参数绑定、状态码、异常翻译
      - `service.py`    只做业务规则（重名拒绝、不存在抛领域异常）
      - `repository.py` 只有 SQL
      分层的直接收益不是「好看」，而是**可替换**：测试里用
      `app.dependency_overrides[get_repository]` 换掉数据库，路由代码一行不改。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI

from db import DB_FILE, init_db
from router import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    DB_FILE.unlink(missing_ok=True)
    init_db()
    app.state.started = True
    try:
        yield
    finally:
        app.state.started = False
        DB_FILE.unlink(missing_ok=True)


app = FastAPI(title="第 56 章 · 仓储层分层", version="0.1.0", lifespan=lifespan)
app.include_router(router)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)