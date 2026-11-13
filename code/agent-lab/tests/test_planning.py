"""S6 回归用例：计划的持久化 / 审批闸门 / 幂等。

这四条断言对应 S6 的四条验收标准，任何一条被破坏都说明
"计划即数据"退化成了"计划即对话"。
"""

import json

import pytest

from agent_lab.app.core.errors import ApiError
from agent_lab.app.services import planning


async def _seed_plan(db, steps: list[tuple[int, str, dict, bool]]) -> str:
    plan_id = "plan-test"
    now = planning.trace_service.now_iso()
    await db.execute(
        "INSERT INTO task_plans (id, session_id, goal, status, created_at, updated_at) "
        "VALUES (?, NULL, '测试目标', 'pending', ?, ?)",
        (plan_id, now, now),
    )
    for idx, action, params, human in steps:
        await db.execute(
            "INSERT INTO plan_steps "
            "(plan_id, idx, action, params, description, status, requires_human, approved) "
            "VALUES (?, ?, ?, ?, '', 'pending', ?, 0)",
            (plan_id, idx, action, json.dumps(params, ensure_ascii=False), 1 if human else 0),
        )
    await db.commit()
    return plan_id


async def test_high_risk_step_pauses_for_approval(db):
    plan_id = await _seed_plan(
        db,
        [
            (0, "create_todo", {"title": "会被创建的待办"}, False),
            (1, "delete_todo", {"id": 1}, True),
        ],
    )

    plan = await planning.run_plan(db, plan_id)

    assert plan["status"] == "awaiting_approval"
    assert plan["steps"][0]["status"] == "done"
    assert plan["steps"][1]["status"] == "pending", "未审批的高危步骤绝不能执行"
    assert (await db.execute_fetchall("SELECT COUNT(1) FROM todos"))[0][0] == 1


async def test_run_again_without_approval_stays_paused(db):
    plan_id = await _seed_plan(db, [(0, "delete_todo", {"id": 1}, True)])
    await planning.run_plan(db, plan_id)
    plan = await planning.run_plan(db, plan_id)

    assert plan["status"] == "awaiting_approval"
    assert plan["steps"][0]["status"] == "pending"


async def test_approve_then_run_completes(db):
    plan_id = await _seed_plan(db, [(0, "list_todos", {}, True)])

    await planning.run_plan(db, plan_id)
    await planning.approve_step(db, plan_id, 0)
    plan = await planning.run_plan(db, plan_id)

    assert plan["status"] == "done"
    assert plan["steps"][0]["status"] == "done"


async def test_replay_does_not_duplicate_side_effect(db):
    """幂等的核心断言：重放同一计划，待办数量不能变多。"""
    plan_id = await _seed_plan(db, [(0, "create_todo", {"title": "只应存在一条"}, False)])

    await planning.run_plan(db, plan_id)
    first = (await db.execute_fetchall("SELECT COUNT(1) FROM todos"))[0][0]

    # 模拟"服务重启后把步骤状态丢了"：重置为 pending 再跑
    await db.execute("UPDATE plan_steps SET status='pending' WHERE plan_id=?", (plan_id,))
    await db.execute("UPDATE task_plans SET status='pending' WHERE id=?", (plan_id,))
    await db.commit()

    plan = await planning.run_plan(db, plan_id)
    second = (await db.execute_fetchall("SELECT COUNT(1) FROM todos"))[0][0]

    assert first == 1
    assert second == 1, "重放不得产生第二条待办"
    assert plan["steps"][0]["status"] == "skipped"
    assert plan["status"] == "done"


async def test_edit_params_invalidates_idempotency(db):
    """失败后改参数必须真的重新执行，而不是命中旧的幂等记录。

    这是最容易被写错的一条：如果幂等键里不含参数，
    改完参数再跑会直接复用"上次失败/成功"的结果，用户以为改了其实没生效。
    """
    plan_id = await _seed_plan(db, [(0, "create_todo", {}, False)])  # 缺 title，必然失败

    plan = await planning.run_plan(db, plan_id)
    assert plan["steps"][0]["status"] == "failed"

    await planning.edit_step(db, plan_id, 0, params={"title": "改过的标题"})
    plan = await planning.run_plan(db, plan_id)

    assert plan["steps"][0]["status"] == "done"
    titles = [r["title"] for r in await db.execute_fetchall("SELECT title FROM todos ORDER BY id")]
    assert titles == ["改过的标题"]


async def test_cannot_edit_executed_step(db):
    plan_id = await _seed_plan(db, [(0, "list_todos", {}, False)])
    await planning.run_plan(db, plan_id)

    with pytest.raises(ApiError) as exc:
        await planning.edit_step(db, plan_id, 0, params={"x": 1})
    assert exc.value.code == "STEP_NOT_EDITABLE"


async def test_force_high_risk_overrides_model_judgement(db):
    """模型说"不用确认"不算数，服务端必须强制。"""
    steps = [
        {"idx": 0, "action": "delete_todo", "params": {"id": 1}, "requires_human": False},
    ]
    planning._force_high_risk(steps)
    assert steps[0]["requires_human"] is True


async def test_idempotency_key_depends_on_params():
    a = planning.idempotency_key("p1", 0, "create_todo", {"title": "x"})
    b = planning.idempotency_key("p1", 0, "create_todo", {"title": "y"})
    c = planning.idempotency_key("p1", 0, "create_todo", {"title": "x"})

    assert a != b
    assert a == c
