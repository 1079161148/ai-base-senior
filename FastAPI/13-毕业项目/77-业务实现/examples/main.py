"""第 77 章 · 毕业项目（一）：业务实现。

待办服务的最小完整形态：

    CRUD     POST/GET/PATCH/DELETE /api/v1/todos
    分页     ?page=&size=（返回 items/total/page/size/pages）
    过滤     ?done=&priority=&q=
    鉴权     写操作要 Bearer，读操作不要
    错误契约 全部错误统一 {"error": {"code","message","details"}}

启动：uvicorn main:app --reload
       打开 http://127.0.0.1:8000/docs，点 Authorize 填 demo-token
验收：python verify.py
"""

from fastapi import FastAPI

from errors import install_error_handlers
from store import store
from todos_router import router as todos_router

app = FastAPI(
    title="待办服务",
    version="0.1.0",
    description="第 77 章毕业项目：CRUD + 分页 + 过滤 + 鉴权 + 统一错误契约",
)

install_error_handlers(app)
app.include_router(todos_router, prefix="/api/v1")


@app.get("/healthz", tags=["诊断"], summary="存活探针")
def healthz() -> dict[str, str]:
    return {"status": "ok", "version": app.version}


@app.get("/events", tags=["诊断"], summary="当前数据量")
def events() -> dict[str, int]:
    return {"count": store.stats()["total"]}


@app.get("/boom", include_in_schema=False)
def boom() -> None:
    """【作用】验收 500 契约用：异常不能把内部信息返给客户端"""
    raise RuntimeError("内部炸了：这里不该出现在响应里")


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)