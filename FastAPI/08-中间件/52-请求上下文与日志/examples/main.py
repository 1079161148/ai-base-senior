"""第 52 章 · 请求上下文与日志（contextvars）。

核心：`trace_id` 要贯穿「中间件 → 依赖 → 业务 → 日志 → 响应头」，
      靠 `contextvars.ContextVar` 而不是全局变量。它在**同一异步上下文**里共享，
      并发请求之间天然隔离；请求结束要 `reset(token)` 归还，避免污染。

启动：uvicorn main:app --reload
验收：python verify.py
"""

import logging
import uuid
from contextvars import ContextVar
from typing import Annotated, Any

from fastapi import BackgroundTasks, Depends, FastAPI, Request

app = FastAPI(title="第 52 章 · 请求上下文与日志", version="0.1.0")

# 【作用】请求级唯一 id；`default` 让「没有中间件的场景」也能读到空串
trace_id_var: ContextVar[str] = ContextVar("trace_id", default="")

# 【反例】全局变量：并发时会被后一个请求覆盖
GLOBAL_TRACE_ID: str = ""


# ============================================================
# 1. 日志：把 trace_id 注入每条记录
# ============================================================
class TraceFilter(logging.Filter):
    """【作用】让 `%(trace_id)s` 在 format 里可用

    【要点】filter 读的是 contextvar，所以同一个 logger 在任何地方输出都对
    """

    def filter(self, record: logging.LogRecord) -> bool:
        record.trace_id = trace_id_var.get() or "-"
        return True


handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter("%(levelname)s [%(trace_id)s] %(name)s: %(message)s"))
handler.addFilter(TraceFilter())

logger = logging.getLogger("ch52")
logger.setLevel(logging.INFO)
logger.addHandler(handler)
logger.propagate = False


# ============================================================
# 2. 中间件：生成/透传 trace_id
# ============================================================
@app.middleware("http")
async def add_trace_id(request: Request, call_next: Any) -> Any:
    """【实测】`set` 必须在 `call_next` **之前**：`BaseHTTPMiddleware` 会在
    `call_next` 时创建子 task，子 task 复制的是**当时**的 context

    【要点】`finally` 里 `reset(token)` 保证请求结束后上下文干净
    """
    global GLOBAL_TRACE_ID
    incoming = request.headers.get("X-Request-ID")
    trace_id = incoming or uuid.uuid4().hex[:12]
    token = trace_id_var.set(trace_id)
    GLOBAL_TRACE_ID = trace_id  # 【反例】并发的另一个请求会把它改掉
    request.state.trace_id = trace_id
    logger.info("请求开始 %s %s", request.method, request.url.path)
    try:
        response = await call_next(request)
        response.headers["X-Request-ID"] = trace_id
        logger.info("请求结束 status=%s", response.status_code)
        return response
    finally:
        trace_id_var.reset(token)


# ============================================================
# 3. 依赖：从 contextvar 取，而不是从函数参数层层传
# ============================================================
def current_trace_id() -> str:
    """【作用】任何依赖/工具函数都能直接拿，不用改签名"""
    return trace_id_var.get()


TraceIdDep = Annotated[str, Depends(current_trace_id)]


# ============================================================
# 端点
# ============================================================
@app.get("/work", tags=["上下文"], summary="读 trace_id")
def work(trace_id: TraceIdDep, request: Request) -> dict[str, Any]:
    """【实测】端点读到 == 中间件写入 == 响应头 `X-Request-ID`"""
    logger.info("业务处理中")
    logger.warning("模拟一条警告")
    return {
        "trace_id": trace_id,
        "state": request.state.trace_id,
        "global_after": GLOBAL_TRACE_ID,
    }


@app.get("/work/global", tags=["上下文"], summary="反例：全局变量")
def work_global() -> dict[str, str]:
    """【注意】这里故意用全局变量模拟错误写法：并发下会互相覆盖"""
    return {"global": GLOBAL_TRACE_ID}


@app.get("/background", tags=["上下文"], summary="后台任务里的上下文")
def background_work(background_tasks: BackgroundTasks) -> dict[str, str]:
    """【实测】`BackgroundTasks` 在响应后执行，`contextvars` 副本仍可用

    【要点】后台任务失败不会影响响应，但异常要自己记日志
    """

    def task() -> None:
        logger.info("后台任务 trace_id=%s", trace_id_var.get() or "-")

    background_tasks.add_task(task)
    return {"trace_id": trace_id_var.get()}


@app.get("/deep", tags=["上下文"], summary="嵌套调用也能读到")
def deep() -> dict[str, Any]:
    """【实测】三层函数调用不用传参，直接 `get()`"""
    return {"level3": _level3()}


def _level3() -> str:
    return f"trace={trace_id_var.get()}"


@app.get("/leak", tags=["上下文"], summary="请求结束后上下文是否干净")
def leak() -> dict[str, str]:
    """【实测】当前请求内仍能读到；这里返回的是**上一请求**是否残留的判断依据"""
    return {"in_request": trace_id_var.get() or "-"}


@app.get("/race", tags=["上下文"], summary="并发对照：contextvar vs 全局变量")
async def race() -> dict[str, str]:
    """【实测】两个请求并发时：
    - `trace_id_var` 各自正确（AAA / BBB）
    - `GLOBAL_TRACE_ID` 被后到的请求覆盖，**两个响应读到同一个值**
    """
    import asyncio

    before = trace_id_var.get()
    global_before = GLOBAL_TRACE_ID
    await asyncio.sleep(0.02)  # 让另一个请求插进来
    return {
        "ctx_before": before,
        "ctx_after": trace_id_var.get(),
        "global_before": global_before,
        "global_after": GLOBAL_TRACE_ID,
    }


@app.get("/docs-probe", include_in_schema=False)
def docs_probe() -> dict[str, str]:
    return {"ok": "1"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)