"""第 57 章 · 事务边界。

核心：事务放 `yield` 依赖，一次请求一个事务：
      正常 → commit；异常 → rollback；无论如何 → close。
      仓储只 `execute`，service 只判业务，router 只翻译异常。
      这样「批量写一半失败」时，已写的部分会自动回滚，不需要手写 savepoint。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from db import DB_FILE, init_db
from models import DuplicateItemError, ItemNotFoundError
from router import router


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    DB_FILE.unlink(missing_ok=True)
    init_db()
    yield
    DB_FILE.unlink(missing_ok=True)


app = FastAPI(title="第 57 章 · 事务边界", version="0.1.0", lifespan=lifespan)
app.include_router(router)


@app.exception_handler(DuplicateItemError)
async def duplicate_handler(request: Request, exc: DuplicateItemError) -> JSONResponse:
    """【作用】领域异常统一翻译，避免每个路由都写 try/except"""
    return JSONResponse(status_code=409, content={"detail": f"名称已存在：{exc.name}"})


@app.exception_handler(ItemNotFoundError)
async def not_found_handler(request: Request, exc: ItemNotFoundError) -> JSONResponse:
    return JSONResponse(status_code=404, content={"detail": "条目不存在"})


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)