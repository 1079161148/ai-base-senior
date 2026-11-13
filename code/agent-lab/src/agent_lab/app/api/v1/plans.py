"""S6 · 任务计划接口（S9 起按用户隔离）。

设计上刻意不把计划执行做成 SSE：
    计划是**可暂停、可编辑、可恢复**的数据结构，调用方按需推进即可。
    用一条长连接把整个计划跑完，反而没法在中途插人工审批。

S9 补充：执行改由 `/run-async` 在后台跑，`/run` 保留同步语义给脚本与测试。
长计划（12 步 × 每步数秒）用同步接口会把 HTTP 连接占满一分钟，
网关早就超时了，而计划其实还在跑 —— 用户看到超时，数据却在变，最难排查。
"""

from typing import Annotated, cast

import aiosqlite
import httpx
from fastapi import APIRouter, BackgroundTasks, Depends, Request
from pydantic import BaseModel, Field

from ...core.config import settings
from ...core.db import get_db
from ...core.errors import ApiError
from ...core.security import CurrentUserDep
from ...services import planning

router = APIRouter(prefix="/plans", tags=["plans"])

DbDep = Annotated[aiosqlite.Connection, Depends(get_db)]


class PlanCreate(BaseModel):
    goal: str = Field(min_length=1, max_length=500)
    session_id: str | None = Field(default=None, max_length=50)


class StepPatch(BaseModel):
    """人工编辑：只允许改参数和描述，不允许改 action。

    改 action 等于换了一件事，幂等键的语义会变得含糊 ——
    这种情况应该重新生成计划，而不是原地改。
    """

    params: dict[str, object] | None = None
    description: str | None = Field(default=None, max_length=120)


def _client(request: Request) -> httpx.AsyncClient:
    return cast(httpx.AsyncClient, request.app.state.http)


def _require_llm() -> None:
    if not settings.llm_configured:
        raise ApiError(503, "LLM_NOT_CONFIGURED", "还没有配置模型，无法生成计划")


@router.post("")
async def create_plan(
    user: CurrentUserDep,
    payload: PlanCreate,
    request: Request,
    db: DbDep,
) -> dict[str, object]:
    """把一句目标拆成计划（结构化输出 + Pydantic 二次校验，失败自动重试）。"""
    _require_llm()
    return await planning.decompose(
        payload.goal,
        client=_client(request),
        db=db,
        session_id=payload.session_id,
        user_id=user.id,
    )


@router.get("")
async def list_plans(
    user: CurrentUserDep,
    db: DbDep,
    session_id: str | None = None,
    limit: int = 30,
) -> list[dict[str, object]]:
    return await planning.list_plans(
        db,
        user_id=user.id,
        session_id=session_id,
        limit=min(limit, 100),
    )


@router.get("/{plan_id}")
async def get_plan(plan_id: str, user: CurrentUserDep, db: DbDep) -> dict[str, object]:
    plan = await planning.get_plan(db, plan_id, user_id=user.id)
    if plan is None:
        raise ApiError(404, "PLAN_NOT_FOUND", f"计划 {plan_id} 不存在")
    return plan


@router.post("/{plan_id}/run")
async def run_plan(plan_id: str, user: CurrentUserDep, db: DbDep) -> dict[str, object]:
    """同步执行：一直跑到"需要人工确认"或"全部完成"才返回。

    适合脚本和测试；前端请用 `/run-async`，否则长计划会顶住连接。
    重复调用是安全的：已完成的步骤不会再执行，幂等记录也会拦住重复副作用。
    """
    return await planning.run_plan(db, plan_id, user_id=user.id)


@router.post("/{plan_id}/run-async")
async def run_plan_async(
    plan_id: str,
    user: CurrentUserDep,
    db: DbDep,
    background: BackgroundTasks,
) -> dict[str, object]:
    """立即返回，执行交给后台任务；前端轮询 GET /plans/{id} 看进度。

    **为什么用 BackgroundTasks 而不是 asyncio.create_task**：
    FastAPI 会保证后台任务在响应发出后执行，且异常不会静默吞掉。
    裸 create_task 拿不到引用，任务可能在 GC 时被回收，出问题也没有日志。
    """
    plan = await planning.get_plan(db, plan_id, user_id=user.id)
    if plan is None:
        raise ApiError(404, "PLAN_NOT_FOUND", f"计划 {plan_id} 不存在")

    if plan["status"] == "running":
        # 重复点击不该派发第二个执行器：两个 runner 会同时推进同一份计划，
        # 幂等记录只能防住"重复副作用"，防不住"状态被写乱"
        return {"accepted": False, "reason": "计划正在执行中", "plan": plan}

    async def _runner() -> None:
        # 后台任务必须自己开连接：请求级连接在响应结束后已关闭
        from ...core.db import get_db as _get_db

        gen = _get_db()
        bg_db = await anext(gen)
        try:
            await planning.run_plan(bg_db, plan_id, user_id=user.id)
        finally:
            await gen.aclose()

    background.add_task(_runner)
    return {"accepted": True, "plan_id": plan_id}


@router.post("/{plan_id}/steps/{idx}/approve")
async def approve_step(
    plan_id: str,
    idx: int,
    user: CurrentUserDep,
    db: DbDep,
) -> dict[str, object]:
    return await planning.approve_step(db, plan_id, idx, user_id=user.id)


@router.patch("/{plan_id}/steps/{idx}")
async def patch_step(
    plan_id: str,
    idx: int,
    payload: StepPatch,
    user: CurrentUserDep,
    db: DbDep,
) -> dict[str, object]:
    return await planning.edit_step(
        db,
        plan_id,
        idx,
        params=payload.params,
        description=payload.description,
        user_id=user.id,
    )


@router.post("/{plan_id}/cancel")
async def cancel_plan(plan_id: str, user: CurrentUserDep, db: DbDep) -> dict[str, object]:
    return await planning.cancel_plan(db, plan_id, user_id=user.id)
