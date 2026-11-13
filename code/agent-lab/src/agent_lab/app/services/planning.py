"""S6 · 任务规划：**计划是数据，不是对话**。

为什么不用「让模型一口气把活干完」：
    对话里的计划只存在于上下文里 —— 看不见、改不了、断了就没了。
    存成表之后才有三件事：可暂停、可编辑参数、可重启恢复。

四道保险（对应 S6 的四条验收）：
    1. 结构化输出 + 二次校验  —— 见 services/structured.py
    2. 计划持久化              —— task_plans / plan_steps 两张表
    3. 高危步骤人工确认        —— requires_human + approved 两个字段
    4. 重复执行不重复副作用    —— idempotency_records 表

**幂等怎么做**：每一步执行前先算 key = sha256(plan_id|idx|action|规范化参数)，
    命中记录就直接复用上次结果、标记 skipped。
    注意 key 里带参数 —— 人工把参数改了，key 就变了，理应重新执行。
"""

import hashlib
import json
import logging
import time
from typing import cast

import aiosqlite
import httpx

from ..core.errors import ApiError
from ..models.schemas import PlanDraft
from . import structured, tools
from . import trace as trace_service

logger = logging.getLogger(__name__)

# 无论模型怎么标 requires_human，这些动作一律强制人工确认。
# 靠提示词约束"删除前要问用户"是不可靠的 —— 提示注入一句话就能绕过。
HIGH_RISK_ACTIONS: frozenset[str] = frozenset({"delete_todo"})

# 单次 run 最多执行的步骤数，防止一个畸形计划把库刷爆
MAX_STEPS_PER_RUN = 12

PLANNER_SYSTEM = """你是一个任务规划器，把用户目标拆成可执行步骤。

可用动作（action）只能从下面选，参数必须与对应工具一致：
- list_todos      {}                                   查看全部待办
- create_todo     {"title": "..."}                     新建待办
- update_todo     {"id": 1, "title": "...", "done": true}  修改待办
- delete_todo     {"id": 1}                            删除待办（高危）
- search_docs     {"query": "..."}                     检索知识库文档
- calculator      {"expression": "1+1"}                精确计算

要求：
1. 步骤数 1~8 步，按执行顺序排列，不要重复。
2. 每步只做一件事；需要先查数据再改的，把查询单独列一步。
3. 删除类操作必须标记 requires_human = true。
4. 只输出 JSON，不要解释。"""

# user_id 必须在列里：run_plan 执行步骤时要用它去调工具，
# 从库里的计划行取比自己传参更可靠（调用方传错就会串租户）。
_PLAN_COLUMNS = "id, user_id, session_id, goal, status, created_at, updated_at"


def _now() -> str:
    return trace_service.now_iso()


def _canonical(params: dict[str, object]) -> str:
    """参数规范化：键排序 + 稳定分隔符，保证同一份参数永远得到同一个 key。"""
    return json.dumps(params, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def idempotency_key(plan_id: str, idx: int, action: str, params: dict[str, object]) -> str:
    raw = f"{plan_id}|{idx}|{action}|{_canonical(params)}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _force_high_risk(steps: list[dict[str, object]]) -> None:
    """强制把高危动作标成需要人工确认，覆盖模型的判断。"""
    for step in steps:
        if step.get("action") in HIGH_RISK_ACTIONS:
            step["requires_human"] = True


async def decompose(
    goal: str,
    *,
    client: httpx.AsyncClient,
    db: aiosqlite.Connection,
    session_id: str | None = None,
    user_id: str = "",
) -> dict[str, object]:
    """把一句目标拆成计划并落库。

    失败会抛 ApiError(502, STRUCTURED_OUTPUT_INVALID) —— 重试逻辑在 structured 层，
    这里不再包一层，否则错误码会被稀释成"未知错误"。
    """
    goal = goal.strip()
    if not goal:
        raise ApiError(400, "INVALID_GOAL", "目标不能为空")

    result = await structured.complete_object(
        f"用户目标：{goal}\n\n请拆解成执行计划。",
        client=client,
        schema=PlanDraft,
        system=PLANNER_SYSTEM,
    )
    draft = result.value

    steps: list[dict[str, object]] = [
        {
            "idx": i,
            "action": s.action,
            "params": dict(s.params),
            "description": s.description,
            "requires_human": s.requires_human,
        }
        for i, s in enumerate(draft.steps)
    ]
    _force_high_risk(steps)

    plan_id = f"plan-{trace_service.new_id()}"
    now = _now()
    await db.execute(
        "INSERT INTO task_plans (id, user_id, session_id, goal, status, created_at, updated_at) "
        "VALUES (?, ?, ?, ?, 'pending', ?, ?)",
        (plan_id, user_id, session_id, draft.goal, now, now),
    )
    for step in steps:
        await db.execute(
            "INSERT INTO plan_steps "
            "(plan_id, idx, action, params, description, status, requires_human, approved) "
            "VALUES (?, ?, ?, ?, ?, 'pending', ?, 0)",
            (
                plan_id,
                step["idx"],
                step["action"],
                _canonical(cast(dict[str, object], step["params"])),
                step["description"],
                1 if step["requires_human"] else 0,
            ),
        )
    await db.commit()

    logger.info(
        "计划已生成：%s（%d 步，%d 个需人工确认，结构化重试 %d 次）",
        plan_id,
        len(steps),
        sum(1 for s in steps if s["requires_human"]),
        result.attempts,
    )
    plan = await get_plan(db, plan_id, user_id=user_id)
    assert plan is not None
    plan["structured_attempts"] = result.attempts
    return plan


async def get_plan(
    db: aiosqlite.Connection,
    plan_id: str,
    *,
    user_id: str = "",
) -> dict[str, object] | None:
    rows = await db.execute_fetchall(
        f"SELECT {_PLAN_COLUMNS} FROM task_plans WHERE id = ? AND user_id = ?",
        (plan_id, user_id),
    )
    if not rows:
        return None
    plan = dict(rows[0])

    step_rows = await db.execute_fetchall(
        "SELECT idx, action, params, description, status, requires_human, approved, "
        "result, error, attempts, duration_ms, finished_at "
        "FROM plan_steps WHERE plan_id = ? ORDER BY idx",
        (plan_id,),
    )
    steps: list[dict[str, object]] = []
    for row in step_rows:
        s = dict(row)
        s["params"] = _loads(s.get("params"), {})
        s["result"] = _loads(s.get("result"), None)
        s["requires_human"] = bool(s["requires_human"])
        s["approved"] = bool(s["approved"])
        steps.append(s)
    plan["steps"] = steps
    return plan


async def list_plans(
    db: aiosqlite.Connection,
    *,
    user_id: str = "",
    session_id: str | None = None,
    limit: int = 30,
) -> list[dict[str, object]]:
    if session_id:
        rows = await db.execute_fetchall(
            f"SELECT {_PLAN_COLUMNS} FROM task_plans WHERE user_id = ? AND session_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (user_id, session_id, limit),
        )
    else:
        rows = await db.execute_fetchall(
            f"SELECT {_PLAN_COLUMNS} FROM task_plans WHERE user_id = ? "
            "ORDER BY created_at DESC LIMIT ?",
            (user_id, limit),
        )

    plans: list[dict[str, object]] = []
    for row in rows:
        plan = dict(row)
        counts = await db.execute_fetchall(
            "SELECT status, COUNT(1) AS n FROM plan_steps WHERE plan_id = ? GROUP BY status",
            (plan["id"],),
        )
        plan["counts"] = {str(r["status"]): int(r["n"]) for r in counts}
        plans.append(plan)
    return plans


async def edit_step(
    db: aiosqlite.Connection,
    plan_id: str,
    idx: int,
    *,
    params: dict[str, object] | None = None,
    description: str | None = None,
    user_id: str = "",
) -> dict[str, object]:
    """人工编辑某一步的参数（必须在执行前）。

    已经执行过的步骤不允许改：改了也不会重跑（幂等键已固化），
    允许改只会让人误以为改动生效了。
    """
    await _require_own_plan(db, plan_id, user_id)
    step = await _get_step(db, plan_id, idx)
    if step is None:
        raise ApiError(404, "STEP_NOT_FOUND", f"计划 {plan_id} 没有第 {idx} 步")
    if step["status"] not in ("pending", "failed"):
        raise ApiError(
            409,
            "STEP_NOT_EDITABLE",
            f"第 {idx} 步状态为 {step['status']}，只有未执行/已失败的步骤可以编辑",
        )

    if params is not None:
        await db.execute(
            "UPDATE plan_steps SET params = ? WHERE plan_id = ? AND idx = ?",
            (_canonical(params), plan_id, idx),
        )
    if description is not None:
        await db.execute(
            "UPDATE plan_steps SET description = ? WHERE plan_id = ? AND idx = ?",
            (description, plan_id, idx),
        )
    await db.execute(
        "UPDATE task_plans SET status = 'pending', updated_at = ? WHERE id = ?",
        (_now(), plan_id),
    )
    await db.commit()

    plan = await get_plan(db, plan_id, user_id=user_id)
    assert plan is not None
    return plan


async def approve_step(
    db: aiosqlite.Connection,
    plan_id: str,
    idx: int,
    *,
    user_id: str = "",
) -> dict[str, object]:
    """人工点确认：标记 approved，后续 run 才会真正执行这一步。"""
    await _require_own_plan(db, plan_id, user_id)
    step = await _get_step(db, plan_id, idx)
    if step is None:
        raise ApiError(404, "STEP_NOT_FOUND", f"计划 {plan_id} 没有第 {idx} 步")
    if step["status"] == "done":
        raise ApiError(409, "STEP_ALREADY_DONE", f"第 {idx} 步已经执行过了")

    await db.execute(
        "UPDATE plan_steps SET approved = 1 WHERE plan_id = ? AND idx = ?",
        (plan_id, idx),
    )
    await db.execute(
        "UPDATE task_plans SET status = 'pending', updated_at = ? WHERE id = ?",
        (_now(), plan_id),
    )
    await db.commit()

    plan = await get_plan(db, plan_id)
    assert plan is not None
    return plan


async def run_plan(
    db: aiosqlite.Connection,
    plan_id: str,
    *,
    user_id: str = "",
) -> dict[str, object]:
    """顺序执行计划，遇到未确认的高危步骤就停下。

    停下不抛异常 —— 暂停是**正常状态**，不是错误。
    前端据此渲染"等待确认"，用户点确认后再次调用 run 接着跑。

    **注意 user_id 的取法**：先按调用方身份校验归属，再用**计划行里的**
    user_id 去执行工具。后者才是权威值 —— 如果调用方传空串（脚本/测试），
    校验会通过（空租户的 legacy 数据），工具也仍然只动空租户的数据。
    """
    plan = await get_plan(db, plan_id, user_id=user_id)
    if plan is None:
        raise ApiError(404, "PLAN_NOT_FOUND", f"计划 {plan_id} 不存在")
    if plan["status"] == "done":
        return plan

    owner_id = str(plan.get("user_id") or user_id)
    await _set_plan_status(db, plan_id, "running")

    executed = 0
    for step in cast(list[dict[str, object]], plan["steps"]):
        idx = cast(int, step["idx"])
        if step["status"] in ("done", "skipped"):
            continue

        if step["requires_human"] and not step["approved"]:
            logger.info("计划 %s 第 %d 步需要人工确认，暂停", plan_id, idx)
            await _set_plan_status(db, plan_id, "awaiting_approval")
            paused = await get_plan(db, plan_id)
            assert paused is not None
            return paused

        if executed >= MAX_STEPS_PER_RUN:
            logger.warning("计划 %s 单次执行已达 %d 步上限，暂停", plan_id, MAX_STEPS_PER_RUN)
            await _set_plan_status(db, plan_id, "pending")
            paused = await get_plan(db, plan_id)
            assert paused is not None
            return paused

        executed += 1
        await _execute_step(db, plan_id, step, owner_id)

    await _refresh_status(db, plan_id)
    final = await get_plan(db, plan_id, user_id=user_id)
    assert final is not None
    return final


async def cancel_plan(
    db: aiosqlite.Connection,
    plan_id: str,
    *,
    user_id: str = "",
) -> dict[str, object]:
    await _require_own_plan(db, plan_id, user_id)
    await _set_plan_status(db, plan_id, "cancelled")
    plan = await get_plan(db, plan_id, user_id=user_id)
    if plan is None:
        raise ApiError(404, "PLAN_NOT_FOUND", f"计划 {plan_id} 不存在")
    return plan


async def _require_own_plan(
    db: aiosqlite.Connection,
    plan_id: str,
    user_id: str,
) -> dict[str, object]:
    """确认计划属于当前用户，否则 404。

    抽成一个函数是因为 5 个入口（get/run/approve/edit/cancel）都要查一次，
    漏掉任何一个就是越权。写成公共函数，漏掉会很明显。
    """
    plan = await get_plan(db, plan_id, user_id=user_id)
    if plan is None:
        raise ApiError(404, "PLAN_NOT_FOUND", f"计划 {plan_id} 不存在")
    return plan


async def _execute_step(
    db: aiosqlite.Connection,
    plan_id: str,
    step: dict[str, object],
    user_id: str = "",
) -> None:
    idx = cast(int, step["idx"])
    action = cast(str, step["action"])
    params = cast(dict[str, object], step["params"])
    key = idempotency_key(plan_id, idx, action, params)

    # ① 幂等检查：重放时直接复用上次结果，绝不再执行一次
    cached = await _get_idempotent(db, key)
    if cached is not None:
        logger.info("第 %d 步命中幂等记录，跳过执行（%s）", idx, action)
        await db.execute(
            "UPDATE plan_steps SET status = 'skipped', result = ?, error = NULL, "
            "finished_at = ? WHERE plan_id = ? AND idx = ?",
            (_canonical(cast(dict[str, object], cached)) if isinstance(cached, dict) else json.dumps(cached, ensure_ascii=False), _now(), plan_id, idx),
        )
        await db.commit()
        return

    await db.execute(
        "UPDATE plan_steps SET status = 'running', attempts = attempts + 1 "
        "WHERE plan_id = ? AND idx = ?",
        (plan_id, idx),
    )
    await db.commit()

    started = time.perf_counter()
    error: str | None = None
    parsed: object = None
    try:
        raw = await tools.execute(db, action, _canonical(params), user_id=user_id)
        parsed = _loads(raw, raw)
        if isinstance(parsed, dict) and "error" in parsed:
            error = str(cast(dict[str, object], parsed)["error"])
    except Exception as exc:  # 工具层承诺不抛，但计划执行不能因为一个异常整批崩
        logger.exception("计划步骤执行异常：%s#%d %s", plan_id, idx, action)
        error = f"执行异常：{exc}"
    duration_ms = round((time.perf_counter() - started) * 1000, 1)

    if error:
        await db.execute(
            "UPDATE plan_steps SET status = 'failed', error = ?, duration_ms = ?, "
            "finished_at = ? WHERE plan_id = ? AND idx = ?",
            (error, duration_ms, _now(), plan_id, idx),
        )
        await db.commit()
        return

    payload = parsed if isinstance(parsed, dict) else {"value": parsed}
    await db.execute(
        "UPDATE plan_steps SET status = 'done', result = ?, error = NULL, "
        "duration_ms = ?, finished_at = ? WHERE plan_id = ? AND idx = ?",
        (_canonical(cast(dict[str, object], payload)), duration_ms, _now(), plan_id, idx),
    )
    # ② 只有成功的步骤才写幂等记录 —— 失败的必须允许重试
    await db.execute(
        "INSERT OR REPLACE INTO idempotency_records "
        "(key, plan_id, step_idx, action, result, created_at) VALUES (?, ?, ?, ?, ?, ?)",
        (key, plan_id, idx, action, _canonical(cast(dict[str, object], payload)), _now()),
    )
    await db.commit()


async def _refresh_status(db: aiosqlite.Connection, plan_id: str) -> None:
    rows = await db.execute_fetchall(
        "SELECT status FROM plan_steps WHERE plan_id = ?", (plan_id,)
    )
    statuses = [str(r["status"]) for r in rows]
    if any(s == "failed" for s in statuses):
        await _set_plan_status(db, plan_id, "failed")
    elif statuses and all(s in ("done", "skipped") for s in statuses):
        await _set_plan_status(db, plan_id, "done")
    else:
        await _set_plan_status(db, plan_id, "pending")


async def _set_plan_status(db: aiosqlite.Connection, plan_id: str, status: str) -> None:
    await db.execute(
        "UPDATE task_plans SET status = ?, updated_at = ? WHERE id = ?",
        (status, _now(), plan_id),
    )
    await db.commit()


async def _get_step(
    db: aiosqlite.Connection, plan_id: str, idx: int
) -> dict[str, object] | None:
    rows = await db.execute_fetchall(
        "SELECT idx, action, params, description, status, requires_human, approved "
        "FROM plan_steps WHERE plan_id = ? AND idx = ?",
        (plan_id, idx),
    )
    if not rows:
        return None
    step = dict(rows[0])
    step["params"] = _loads(step.get("params"), {})
    step["requires_human"] = bool(step["requires_human"])
    step["approved"] = bool(step["approved"])
    return step


async def _get_idempotent(db: aiosqlite.Connection, key: str) -> object | None:
    rows = await db.execute_fetchall(
        "SELECT result FROM idempotency_records WHERE key = ?", (key,)
    )
    if not rows:
        return None
    return _loads(rows[0]["result"], None)


def _loads(value: object, default: object) -> object:
    if value is None:
        return default
    if isinstance(value, (dict, list)):
        return value
    try:
        return json.loads(str(value))
    except json.JSONDecodeError:
        return default
