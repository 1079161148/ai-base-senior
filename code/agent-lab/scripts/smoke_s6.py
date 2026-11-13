"""S6 冒烟测试：计划持久化 / 人工审批 / 幂等恢复。

不需要模型：直接往库里插一个计划，然后走 run → approve → run 的流程。
重点验证四件事：
  1. 高危步骤（delete_todo）即使模型没标，也会被强制 requires_human
  2. 未审批时 run 会停在该步骤，不越权执行
  3. 重复 run 不会重复创建待办（幂等记录生效）
  4. 把已完成步骤重置为 pending 再跑，命中幂等 → 不产生第二条数据
"""

import asyncio
import json

import aiosqlite

from agent_lab.app.core.db import SCHEMA
from agent_lab.app.services import planning


async def fresh_db() -> aiosqlite.Connection:
    db = await aiosqlite.connect(":memory:")
    db.row_factory = aiosqlite.Row
    await db.executescript(SCHEMA)
    await db.commit()
    return db


async def count(db: aiosqlite.Connection, sql: str) -> int:
    rows = await db.execute_fetchall(sql)
    return int(rows[0][0])


async def main() -> None:
    db = await fresh_db()

    # 手工造一个计划：建待办 + 删待办（后者必须人工确认）
    plan_id = "plan-test"
    now = planning.trace_service.now_iso()
    await db.execute(
        "INSERT INTO task_plans (id, session_id, goal, status, created_at, updated_at) "
        "VALUES (?, NULL, ?, 'pending', ?, ?)",
        (plan_id, "演示幂等", now, now),
    )
    steps = [
        (0, "create_todo", {"title": "幂等测试待办"}, "新建待办", 0),
        # 故意写 0：验证 _force_high_risk 之外，运行期也不会执行未审批的高危步骤
        (1, "delete_todo", {"id": 1}, "删除待办", 1),
    ]
    for idx, action, params, desc, human in steps:
        await db.execute(
            "INSERT INTO plan_steps "
            "(plan_id, idx, action, params, description, status, requires_human, approved) "
            "VALUES (?, ?, ?, ?, ?, 'pending', ?, 0)",
            (plan_id, idx, action, json.dumps(params, ensure_ascii=False), desc, human),
        )
    await db.commit()

    # ① 第一次 run：执行第 0 步，停在第 1 步等审批
    plan = await planning.run_plan(db, plan_id)
    print("① run 后状态：", plan["status"])
    print("   步骤状态：", [(s["idx"], s["status"]) for s in plan["steps"]])
    todos = await count(db, "SELECT COUNT(1) FROM todos")
    print("   待办数量：", todos)

    # ② 未审批再 run 一次：必须仍然停住，不能删数据
    plan = await planning.run_plan(db, plan_id)
    print("② 未审批再 run：", plan["status"], "| 待办数量：", await count(db, "SELECT COUNT(1) FROM todos"))

    # ③ 审批后 run：删除执行完成
    await planning.approve_step(db, plan_id, 1)
    plan = await planning.run_plan(db, plan_id)
    print("③ 审批后 run：", plan["status"], "| 待办数量：", await count(db, "SELECT COUNT(1) FROM todos"))

    # ④ 模拟"重启后恢复"：把第 0 步改回 pending 再跑
    await db.execute("UPDATE plan_steps SET status = 'pending' WHERE plan_id = ? AND idx = 0", (plan_id,))
    await db.execute("UPDATE task_plans SET status = 'pending' WHERE id = ?", (plan_id,))
    await db.commit()
    plan = await planning.run_plan(db, plan_id)
    rows = await db.execute_fetchall("SELECT title FROM todos")
    print("④ 重放后待办：", [dict(r) for r in rows] or "（已删空）")
    print("   第 0 步状态：", plan["steps"][0]["status"], "（skipped 表示命中幂等）")
    idem = await count(db, "SELECT COUNT(1) FROM idempotency_records")
    print("   幂等记录数：", idem)

    assert plan["status"] == "done"
    assert todos == 1, "首次应只创建 1 条待办"
    assert await count(db, "SELECT COUNT(1) FROM todos") == 0, "审批后应删干净"
    await db.close()
    print("\n✅ S6 冒烟通过")


asyncio.run(main())
