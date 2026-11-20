"""第 70 章 · BackgroundTasks。

响应发送**之后**再执行的任务：

    return {"status": "accepted"}   ← 客户端已经拿到
    → 后台任务开始跑（发邮件、写审计、清临时文件）

【要点】它**不是**队列：
        - 任务与请求同进程、同事件循环
        - 进程重启就丢
        - 多个任务按添加顺序**串行**执行
        - 真正的重活交给 Celery/RQ/Arq

启动：uvicorn main:app --reload
验收：python verify.py
"""

import asyncio
import threading
import time
from typing import Any

from fastapi import BackgroundTasks, Depends, FastAPI

app = FastAPI(title="第 70 章 · BackgroundTasks", version="0.1.0")

EVENTS: list[str] = []
RESULTS: dict[str, Any] = {}


def reset() -> None:
    EVENTS.clear()
    RESULTS.clear()


# ============================================================
# 任务定义
# ============================================================
def record(name: str) -> None:
    """【要点】同步任务会在**线程池**里跑，不阻塞事件循环"""
    EVENTS.append(f"record:{name}")
    RESULTS["record_thread"] = threading.get_ident()


async def notify(name: str, channel: str = "email") -> None:
    """【要点】异步任务直接在当前事件循环里跑"""
    EVENTS.append(f"notify:{name}:{channel}")
    RESULTS["notify_loop"] = asyncio.get_running_loop()
    await asyncio.sleep(0)


def boom() -> None:
    """【作用】故意失败，观察响应是否受影响"""
    EVENTS.append("boom")
    raise RuntimeError("后台任务失败了")


def slow() -> None:
    time.sleep(0.12)


# ============================================================
# 端点
# ============================================================
@app.post("/orders", tags=["订单"], summary="下单：响应后发通知")
def create_order(
    background: BackgroundTasks,
    name: str = "默认商品",
    channel: str = "email",
) -> dict[str, Any]:
    """【实测】返回体先到，任务后跑；`EVENTS` 里端点一定在任务之前"""
    EVENTS.append("endpoint")
    background.add_task(record, name)
    background.add_task(notify, name, channel)  # 位置参数与关键字参数都能传
    return {"status": "accepted", "name": name, "thread": threading.get_ident()}


@app.post("/orders/thread", tags=["订单"], summary="对比事件循环线程与任务线程")
async def create_thread(background: BackgroundTasks) -> dict[str, Any]:
    """【实测】`async def` 端点在事件循环线程；同步任务在线程池，
    两者线程 id 必然不同。而 `def` 端点与同步任务**共用同一个线程池**，
    可能拿到同一个 worker（不要依赖「一定不同」）。
    """
    RESULTS["loop_thread"] = threading.get_ident()
    background.add_task(record, "thread")
    return {"status": "accepted"}


@app.post("/orders/boom", tags=["订单"], summary="后台任务抛异常")
def create_boom(background: BackgroundTasks) -> dict[str, str]:
    """【实测】客户端拿到 200；异常在服务端冒出来"""
    background.add_task(boom)
    return {"status": "accepted"}


@app.post("/orders/slow", tags=["订单"], summary="耗时任务（证明客户端在等）")
def create_slow(background: BackgroundTasks) -> dict[str, str]:
    """【实测】`TestClient.get()` 会等后台任务跑完才返回"""
    background.add_task(slow)
    return {"status": "accepted"}


@app.post("/orders/three", tags=["订单"], summary="三个任务看顺序")
def create_three(background: BackgroundTasks) -> dict[str, str]:
    for index in range(3):
        background.add_task(record, f"t{index}")
    return {"status": "accepted"}


@app.post("/orders/state", tags=["订单"], summary="任务里访问 app.state")
def create_with_state(background: BackgroundTasks) -> dict[str, Any]:
    app.state.counter = getattr(app.state, "counter", 0) + 1
    background.add_task(record, "state")
    return {"status": "accepted", "counter": app.state.counter}


# ============================================================
# 依赖里添加任务
# ============================================================
def audit(background: BackgroundTasks) -> None:
    """【要点】依赖里也能 `add_task`，适合「无论成败都记一笔」的审计"""
    background.add_task(record, "from-dependency")


@app.get("/audited", tags=["审计"], summary="依赖里挂后台任务", dependencies=[Depends(audit)])
def audited() -> dict[str, str]:
    EVENTS.append("audited-endpoint")
    return {"status": "ok"}


# ============================================================
# 对比：create_task 是「立刻开始」
# ============================================================
async def patched(name: str) -> None:
    EVENTS.append(f"patched:{name}")


@app.post("/orders/fire-and-forget", tags=["对比"], summary="asyncio.create_task 立刻跑")
async def fire_and_forget(background: BackgroundTasks) -> dict[str, str]:
    """【要点】`create_task` 在返回前就开始执行，且**不被等待**"""
    asyncio.create_task(patched("now"))
    EVENTS.append("fire-endpoint")
    return {"status": "accepted"}


@app.get("/events", tags=["诊断"], summary="读取事件")
def events() -> dict[str, list[str]]:
    return {"events": list(EVENTS)}


@app.get("/results", tags=["诊断"], summary="读取任务结果")
def results() -> dict[str, Any]:
    return {"results": {key: str(value) for key, value in RESULTS.items()}}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)