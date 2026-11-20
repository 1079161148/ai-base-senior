"""第 68 章 · 子应用。

【要点】子应用是**独立的 FastAPI 实例**：自己的 `state`、自己的 `/docs`、
        自己的 lifespan。挂在主应用的某个前缀下，但内部不知道这个前缀。
"""

from contextlib import asynccontextmanager
from typing import AsyncIterator

from fastapi import FastAPI, Request

SUB_EVENTS: list[str] = []


@asynccontextmanager
async def sub_lifespan(app: FastAPI) -> AsyncIterator[None]:
    SUB_EVENTS.append("sub:startup")
    app.state.marker = "sub-app"
    try:
        yield
    finally:
        SUB_EVENTS.append("sub:shutdown")


sub_app = FastAPI(
    title="子应用",
    version="0.1.0",
    lifespan=sub_lifespan,
    docs_url="/docs",
    openapi_url="/openapi.json",
)


@sub_app.get("/hello", summary="子应用端点")
def hello(request: Request) -> dict[str, str]:
    return {
        "who": "sub-app",
        "marker": getattr(request.app.state, "marker", "missing"),
        # 【实测】子应用看到的 root_path 是挂载前缀
        "root_path": request.scope.get("root_path", ""),
    }


@sub_app.get("/events", summary="子应用事件")
def sub_events() -> dict[str, list[str]]:
    return {"events": list(SUB_EVENTS)}