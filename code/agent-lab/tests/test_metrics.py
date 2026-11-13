"""S7 回归用例：指标落库与聚合。

重点不是"能算出来"，而是"P95 取的是真实那一次"——
样本少时插值会给出一个不存在的延迟值，排查时对不上号。
"""

from agent_lab.app.services import metrics
from agent_lab.app.services.trace import Trace, fingerprint


def _trace(trace_id: str, duration_ms: float, status: str, cost: float, day: str) -> Trace:
    t = Trace(
        trace_id=trace_id,
        started_at=f"{day}T10:00:00+00:00",
        model="deepseek-chat",
        question="q",
        duration_ms=duration_ms,
        stopped_reason=status,
        config_fingerprint=fingerprint(
            model="deepseek-chat",
            temperature=0.7,
            max_tokens=2048,
            prompt_version="p1",
            tool_version="t1",
        ),
        prompt_version="p1",
        tool_version="t1",
    )
    t.usage = {"prompt_tokens": 100, "completion_tokens": 50, "total_tokens": 150, "cost_cny": cost}
    return t


async def test_record_and_summary(db):
    for i in range(10):
        await metrics.record(db, _trace(f"t{i}", 1000 + i * 100, "completed", 0.001, "2026-11-12"))

    data = await metrics.summary(db, days=3650)

    assert data["requests"] == 10
    assert data["success_rate"] == 1.0
    # 1000..1900 的 P95 应落在靠后的真实点上
    assert 1700 <= data["p95_ms"] <= 1900
    assert data["total_cost_cny"] == round(0.01, 6)


async def test_success_rate_counts_failures(db):
    for i in range(4):
        await metrics.record(db, _trace(f"ok{i}", 500, "completed", 0.001, "2026-11-12"))
    await metrics.record(db, _trace("bad", 500, "cost_limit", 0.002, "2026-11-12"))

    data = await metrics.summary(db, days=3650)

    assert data["requests"] == 5
    assert data["success_rate"] == 0.8
    assert data["by_status"]["cost_limit"] == 1


async def test_recent_failures(db):
    await metrics.record(db, _trace("ok", 100, "completed", 0.001, "2026-11-12"))
    await metrics.record(db, _trace("bad", 100, "max_steps", 0.002, "2026-11-12"))

    failures = await metrics.recent_failures(db)

    assert len(failures) == 1
    assert failures[0]["trace_id"] == "bad"


async def test_record_is_idempotent_by_trace_id(db):
    t = _trace("same", 100, "completed", 0.001, "2026-11-12")
    await metrics.record(db, t)
    await metrics.record(db, t)

    data = await metrics.summary(db, days=3650)
    assert data["requests"] == 1, "同一条 trace 重写不该变成两条指标"
