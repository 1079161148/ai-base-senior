"""S8 回归用例：限流 / 并发 / 日成本熔断。

这三道闸平时不可见，一旦失效就是"账号被刷爆"，
所以必须有用例锁住行为。
"""

import pytest

from agent_lab.app.core.config import settings
from agent_lab.app.core.errors import ApiError
from agent_lab.app.services.ratelimit import (
    ConcurrencyGuard,
    TokenBucketLimiter,
    daily_cost,
    ensure_daily_budget,
)
from agent_lab.app.services.trace import Trace


def test_token_bucket_allows_burst_then_blocks():
    limiter = TokenBucketLimiter(per_minute=2)
    assert limiter.allow("1.1.1.1")[0]
    assert limiter.allow("1.1.1.1")[0]
    allowed, retry = limiter.allow("1.1.1.1")
    assert not allowed
    assert retry > 0


def test_token_bucket_isolated_per_key():
    limiter = TokenBucketLimiter(per_minute=1)
    assert limiter.allow("a")[0]
    # 另一个来源不该被 a 的配额拖累
    assert limiter.allow("b")[0]


def test_concurrency_guard_blocks_when_full():
    guard = ConcurrencyGuard(limit=2)
    guard.acquire()
    guard.acquire()
    with pytest.raises(ApiError) as exc:
        guard.acquire()
    assert exc.value.code == "TOO_MANY_CONCURRENT"

    guard.release()
    guard.acquire()  # 释放后可以再进


async def test_daily_budget(db):
    assert await daily_cost(db) == 0.0
    await ensure_daily_budget(db)  # 没花钱，应该放行

    t = Trace(
        trace_id="t1",
        started_at="2026-11-12T10:00:00+00:00",
        model="m",
        question="q",
        duration_ms=100,
    )
    t.usage = {"cost_cny": settings.DAILY_COST_LIMIT_CNY + 1}
    # 直接写表：只关心熔断逻辑，不关心 record 的字段细节
    await db.execute(
        "INSERT INTO trace_metrics (trace_id, model, config_fingerprint, prompt_version, "
        "tool_version, started_at, duration_ms, cost_cny, status) "
        "VALUES ('t1', 'm', 'fp', 'p', 't', date('now'), 100, ?, 'completed')",
        (t.usage["cost_cny"],),
    )
    await db.commit()

    with pytest.raises(ApiError) as exc:
        await ensure_daily_budget(db)
    assert exc.value.code == "DAILY_COST_LIMIT"
