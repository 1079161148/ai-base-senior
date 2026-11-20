"""第 68 章 · 子应用与静态资源。

同一个进程里同时提供：

    /api/items            API
    /static/*             静态资源（css/js/json）
    /                     SPA 首页（StaticFiles(html=True)）
    /sub/*                子应用（独立 docs 在 /sub/docs）

【要点】`mount` 的顺序很关键：先挂具体前缀，再挂兜底的 `/`，
        否则 `/` 会把所有路径吞掉。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from contextlib import asynccontextmanager
from pathlib import Path
from typing import AsyncIterator

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from subapp import sub_app

HERE = Path(__file__).parent
STATIC_DIR = HERE / "static"

APP_EVENTS: list[str] = []


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    APP_EVENTS.append("app:startup")
    app.state.marker = "main-app"
    try:
        yield
    finally:
        APP_EVENTS.append("app:shutdown")


app = FastAPI(
    title="第 68 章 · 子应用与静态资源",
    version="0.1.0",
    lifespan=lifespan,
)


@app.get("/api/items", tags=["API"], summary="普通 API")
def items() -> dict[str, list[str]]:
    return {"items": ["a", "b", "c"]}


@app.get("/api/whoami", tags=["API"], summary="看当前 app 与 root_path")
def whoami(request: Request) -> dict[str, str]:
    return {
        "marker": getattr(request.app.state, "marker", "missing"),
        "root_path": request.scope.get("root_path", ""),
        "path": request.scope.get("path", ""),
    }


@app.get("/events", tags=["诊断"], summary="主应用事件")
def events() -> dict[str, list[str]]:
    return {"events": list(APP_EVENTS)}


# 【要点】先挂具体前缀
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
# 【要点】子应用也挂在具体前缀下
app.mount("/sub", sub_app, name="sub")
# 【要点】最后挂兜底的 `/`，`html=True` 让 `/` 返回 index.html
app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="spa")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)