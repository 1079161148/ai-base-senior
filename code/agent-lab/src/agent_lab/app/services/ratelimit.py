"""S8 · 资源护栏：限流 / 并发 / 日成本熔断。

**为什么三道都要**：
    限流（每分钟）   挡刷接口的脚本
    并发（同时在跑） 挡"开一堆长连接慢慢耗"的请求，也保护模型账号的并发上限
    日成本（每天）   挡"每个请求都很小但量极大" —— 这是单次成本上限唯一挡不住的

三道闸的位置都在**进入生成之前**：拦在模型调用前面才省钱，
生成到一半再拦，钱已经花出去了。
"""

import logging
import time
from dataclasses import dataclass

import aiosqlite

from ..core.config import settings
from ..core.errors import ApiError

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class _Bucket:
    tokens: float
    last: float


class TokenBucketLimiter:
    """内存令牌桶。

    单实例有效。多实例部署时换成 Redis（INCR + EXPIRE 或 Lua），
    这里不引依赖是为了让本地体验不被外部组件卡住。
    """

    def __init__(self, per_minute: int) -> None:
        self.per_minute = max(1, per_minute)
        # 允许一次突发 = 每分钟配额，这样正常用户连点几下不会被误伤
        self.burst = float(max(1, per_minute))
        self._buckets: dict[str, _Bucket] = {}

    def allow(self, key: str) -> tuple[bool, float]:
        """返回 (是否放行, 建议的 retry_after 秒数)。"""
        now = time.monotonic()
        rate = self.per_minute / 60.0

        bucket = self._buckets.get(key)
        if bucket is None:
            bucket = _Bucket(tokens=self.burst, last=now)
            self._buckets[key] = bucket

        bucket.tokens = min(self.burst, bucket.tokens + (now - bucket.last) * rate)
        bucket.last = now

        if bucket.tokens >= 1.0:
            bucket.tokens -= 1.0
            return True, 0.0

        wait = (1.0 - bucket.tokens) / rate
        return False, round(wait, 1)

    def prune(self, max_entries: int = 5000) -> None:
        """防止 key 无限增长（每个 IP 一个桶）。

        攻击者换 IP 刷会把字典撑大 —— 满了就整体清空，
        代价是限流状态短暂重置，比内存被吃光好。
        """
        if len(self._buckets) > max_entries:
            logger.warning("限流桶数量超过 %d，执行清空", max_entries)
            self._buckets.clear()


class ConcurrencyGuard:
    """同时在跑的生成任务计数。

    不用 asyncio.Semaphore 的原因：Semaphore 的 acquire 会排队等待，
    而我们要的是"满了立刻拒绝"—— 让请求卡在队列里，用户的 SSE 连接
    一样占着资源，还看不到任何反馈。
    """

    def __init__(self, limit: int) -> None:
        self.limit = max(1, limit)
        self._in_use = 0

    @property
    def in_use(self) -> int:
        return self._in_use

    def acquire(self) -> None:
        if self._in_use >= self.limit:
            raise ApiError(
                429,
                "TOO_MANY_CONCURRENT",
                f"同时处理的请求已达上限（{self.limit}），请稍后再试",
            )
        self._in_use += 1

    def release(self) -> None:
        self._in_use = max(0, self._in_use - 1)


async def daily_cost(db: aiosqlite.Connection) -> float:
    rows = await db.execute_fetchall(
        "SELECT SUM(cost_cny) AS c FROM trace_metrics "
        "WHERE substr(started_at, 1, 10) = date('now')"
    )
    return float(rows[0]["c"] or 0.0) if rows else 0.0


async def ensure_daily_budget(db: aiosqlite.Connection) -> None:
    """日成本熔断。超限直接拒绝，不做降级模型 —— 降级会让人以为"还能用"，
    结果第二天账单照收，问题被掩盖。"""
    spent = await daily_cost(db)
    if spent >= settings.DAILY_COST_LIMIT_CNY:
        raise ApiError(
            429,
            "DAILY_COST_LIMIT",
            f"今日成本已达上限 ¥{settings.DAILY_COST_LIMIT_CNY:.2f}（当前 ¥{spent:.4f}），请明天再试",
        )


# 进程级单例：把状态挂在模块上，而不是 app.state ——
# 这样 chat.py 不需要为了限流而多传一个参数。
limiter = TokenBucketLimiter(settings.RATE_LIMIT_PER_MINUTE)
concurrency = ConcurrencyGuard(settings.MAX_CONCURRENT_REQUESTS)
