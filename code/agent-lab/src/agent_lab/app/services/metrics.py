"""S7 · 指标：把"每次对话发生了什么"变成"一屏能看懂的数字"。

**为什么不直接统计 traces/*.json**：
    JSON 文件适合回放单次对话（人看），不适合聚合（SQL 算）。
    一个月几百上千个文件，每次看板都要全量 parse，慢且没法按维度分组。
    所以这里落一张窄表：一行一次对话，只存聚合需要的标量。

**四个指标一起看**（缺一个就会做出错误决策）：
    - 成功率   ：只看准确率，可能把一半请求超时了都不知道
    - P95 延迟 ：均值 2s 但 P95 30s，用户体验是后者
    - 单任务成本：成本涨了 20% 而准确率只涨 1%，这波改动不值
    - 失败归类 ：知道"错在哪一类"才有下一步动作
"""

import logging
from typing import cast

import aiosqlite

from .trace import Trace

logger = logging.getLogger(__name__)


async def record(db: aiosqlite.Connection, trace: Trace) -> None:
    """把一次对话的标量指标写进 trace_metrics。

    这里**必须吞异常**：指标是旁路，不能因为统计写失败就让用户拿不到回答。
    """
    usage = trace.usage or {}
    try:
        await db.execute(
            "INSERT OR REPLACE INTO trace_metrics "
            "(trace_id, user_id, session_id, model, config_fingerprint, prompt_version, tool_version, "
            " question, started_at, duration_ms, prompt_tokens, completion_tokens, total_tokens, "
            " cost_cny, steps, tool_calls, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                trace.trace_id,
                trace.user_id,
                trace.session_id,
                trace.model,
                trace.config_fingerprint or "unknown",
                trace.prompt_version,
                trace.tool_version,
                trace.question[:200],
                trace.started_at,
                trace.duration_ms,
                int(cast(int, usage.get("prompt_tokens", 0))),
                int(cast(int, usage.get("completion_tokens", 0))),
                int(cast(int, usage.get("total_tokens", 0))),
                float(cast(float, usage.get("cost_cny", 0.0))),
                len(trace.steps),
                int(cast(int, usage.get("tool_calls", 0))),
                trace.stopped_reason,
            ),
        )
        await db.commit()
    except Exception:
        logger.exception("写入指标失败（不影响主流程）：%s", trace.trace_id)


def _percentile(sorted_values: list[float], p: float) -> float:
    """取分位值。列表必须已升序。

    用最近秩法（nearest-rank）：样本少时插值会给出一个"谁都没遇到过"的中间值，
    不如直接取真实的那个点 —— 排查问题时能对得上具体某次请求。
    """
    if not sorted_values:
        return 0.0
    idx = min(len(sorted_values) - 1, max(0, int(round(len(sorted_values) * p)) - 1))
    return round(sorted_values[idx], 1)


async def summary(
    db: aiosqlite.Connection,
    *,
    days: int = 7,
    user_id: str | None = "",
) -> dict[str, object]:
    """一屏看板需要的全部数字。

    `user_id=None` 表示**跨用户汇总**，只给 Prometheus 抓取用。
    其余场景必须传具体 id —— 看板上会显示问题原文，不隔离就是数据泄露。
    """
    since = f"datetime('now', '-{int(days)} days')"
    time_cond = f"started_at >= strftime('%Y-%m-%dT%H:%M:%S', {since})"
    if user_id is None:
        where = time_cond
        params: tuple[object, ...] = ()
    else:
        where = f"{time_cond} AND user_id = ?"
        params = (user_id,)

    totals = await db.execute_fetchall(
        "SELECT COUNT(1) AS n, "
        "       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS ok, "
        "       SUM(cost_cny) AS cost, AVG(cost_cny) AS avg_cost, "
        "       AVG(duration_ms) AS avg_ms, SUM(tool_calls) AS tools "
        f"FROM trace_metrics WHERE {where}",
        params,
    )
    row = totals[0]
    n = int(row["n"] or 0)
    ok = int(row["ok"] or 0)

    durations = [
        float(r["duration_ms"])
        for r in await db.execute_fetchall(
            f"SELECT duration_ms FROM trace_metrics WHERE {where} ORDER BY duration_ms",
            params,
        )
    ]

    by_status = {
        str(r["status"]): int(r["n"])
        for r in await db.execute_fetchall(
            f"SELECT status, COUNT(1) AS n FROM trace_metrics WHERE {where} GROUP BY status",
            params,
        )
    }

    by_day = [
        {
            "date": str(r["d"]),
            "requests": int(r["n"]),
            "success_rate": round(int(r["ok"]) / int(r["n"]), 4) if int(r["n"]) else 0.0,
            "p95_ms": 0.0,  # 下面补
            "cost_cny": round(float(r["cost"] or 0), 6),
        }
        for r in await db.execute_fetchall(
            "SELECT substr(started_at, 1, 10) AS d, COUNT(1) AS n, "
            "       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS ok, "
            "       SUM(cost_cny) AS cost "
            f"FROM trace_metrics WHERE {where} GROUP BY d ORDER BY d",
            params,
        )
    ]
    # 按天 P95：每天单独算，样本少时就是该天最慢那次
    for day in by_day:
        day_rows = await db.execute_fetchall(
            "SELECT duration_ms FROM trace_metrics "
            f"WHERE {where} AND substr(started_at, 1, 10) = ? ORDER BY duration_ms",
            (*params, day["date"]),
        )
        day["p95_ms"] = _percentile([float(r["duration_ms"]) for r in day_rows], 0.95)

    by_fingerprint = [
        {
            "fingerprint": str(r["fp"]),
            "model": str(r["model"]),
            "requests": int(r["n"]),
            "success_rate": round(int(r["ok"]) / int(r["n"]), 4) if int(r["n"]) else 0.0,
            "avg_cost_cny": round(float(r["avg_cost"] or 0), 6),
        }
        for r in await db.execute_fetchall(
            "SELECT config_fingerprint AS fp, model, COUNT(1) AS n, "
            "       SUM(CASE WHEN status = 'completed' THEN 1 ELSE 0 END) AS ok, "
            "       AVG(cost_cny) AS avg_cost "
            f"FROM trace_metrics WHERE {where} GROUP BY fp, model ORDER BY n DESC",
            params,
        )
    ]

    return {
        "window_days": days,
        "requests": n,
        "success_rate": round(ok / n, 4) if n else 0.0,
        "p50_ms": _percentile(durations, 0.50),
        "p95_ms": _percentile(durations, 0.95),
        "p99_ms": _percentile(durations, 0.99),
        "avg_duration_ms": round(float(row["avg_ms"] or 0), 1),
        "avg_cost_cny": round(float(row["avg_cost"] or 0), 6),
        "total_cost_cny": round(float(row["cost"] or 0), 6),
        "total_tool_calls": int(row["tools"] or 0),
        "by_status": by_status,
        "by_day": by_day,
        "by_fingerprint": by_fingerprint,
    }


async def recent_failures(
    db: aiosqlite.Connection, *, limit: int = 20, user_id: str | None = ""
) -> list[dict[str, object]]:
    """最近的失败请求 —— 看板上的"失败 3 条"点进去要看得到具体是哪三条。"""
    sql = (
        "SELECT trace_id, question, status, model, duration_ms, cost_cny, started_at "
        "FROM trace_metrics WHERE status != 'completed'"
    )
    args: tuple[object, ...]
    if user_id is None:
        args = (limit,)
    else:
        sql += " AND user_id = ?"
        args = (user_id, limit)
    rows = await db.execute_fetchall(f"{sql} ORDER BY started_at DESC LIMIT ?", args)
    return [dict(r) for r in rows]
