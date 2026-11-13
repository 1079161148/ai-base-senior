"""评测报告：四个指标一起看，再加门禁判断。

**只看通过率会翻车**：
    通过率 96% 但 P95 从 4s 涨到 20s，这个版本不该发；
    通过率涨 2% 但成本涨 80%，这个改动不值。
    所以 report 必须同时给出四个数，并支持"任一维度劣化就报警"。
"""

from collections import Counter
from dataclasses import dataclass, field


@dataclass(slots=True)
class CaseResult:
    case_id: str
    category: str
    passed: bool
    score: float
    reason: str
    failure_type: str = ""
    needs_human: bool = False
    duration_ms: float = 0.0
    cost_cny: float = 0.0
    tools: list[str] = field(default_factory=list)


def _percentile(values: list[float], p: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    idx = min(len(ordered) - 1, max(0, int(round(len(ordered) * p)) - 1))
    return round(ordered[idx], 1)


def summarize(results: list[CaseResult]) -> dict[str, object]:
    total = len(results)
    passed = sum(1 for r in results if r.passed)

    by_category: dict[str, dict[str, object]] = {}
    for cat in ("standard", "subjective", "adversarial"):
        items = [r for r in results if r.category == cat]
        if not items:
            continue
        ok = sum(1 for r in items if r.passed)
        by_category[cat] = {
            "count": len(items),
            "passed": ok,
            "pass_rate": round(ok / len(items), 4),
            "avg_score": round(sum(i.score for i in items) / len(items), 4),
        }

    durations = [r.duration_ms for r in results]
    costs = [r.cost_cny for r in results]
    failure_types = Counter(r.failure_type for r in results if not r.passed and r.failure_type)

    failures = [
        {
            "case_id": r.case_id,
            "category": r.category,
            "type": r.failure_type or "unknown",
            "reason": r.reason,
        }
        for r in results
        if not r.passed
    ]

    return {
        "total": total,
        "passed": passed,
        "pass_rate": round(passed / total, 4) if total else 0.0,
        "by_category": by_category,
        "p50_ms": _percentile(durations, 0.50),
        "p95_ms": _percentile(durations, 0.95),
        "avg_cost_cny": round(sum(costs) / len(costs), 6) if costs else 0.0,
        "total_cost_cny": round(sum(costs), 6),
        "failure_types": dict(failure_types),
        "failures": failures,
        "needs_human": [r.case_id for r in results if r.needs_human],
    }


def check_gates(
    summary: dict[str, object],
    *,
    min_pass_rate: float = 0.80,
    max_p95_ms: float = 60_000,
    max_avg_cost_cny: float = 0.05,
) -> list[str]:
    """返回违规项列表。空列表 = 全部达标（可以合并）。

    阈值故意设得宽松：这是学习项目，卡太死会让人习惯性绕过门禁 ——
    那还不如不设。
    """
    problems: list[str] = []

    rate = float(summary.get("pass_rate") or 0.0)
    if rate < min_pass_rate:
        problems.append(f"通过率 {rate:.1%} 低于门限 {min_pass_rate:.0%}")

    p95 = float(summary.get("p95_ms") or 0.0)
    if p95 > max_p95_ms:
        problems.append(f"P95 延迟 {p95:.0f}ms 超过门限 {max_p95_ms:.0f}ms")

    avg_cost = float(summary.get("avg_cost_cny") or 0.0)
    if avg_cost > max_avg_cost_cny:
        problems.append(f"单任务成本 ¥{avg_cost:.4f} 超过门限 ¥{max_avg_cost_cny:.4f}")

    std = summary.get("by_category", {}).get("standard", {})  # type: ignore[union-attr]
    if isinstance(std, dict) and std.get("pass_rate", 1.0) < 0.7:
        problems.append(f"标准答案类通过率 {std['pass_rate']:.1%} 低于 70%")

    adv = summary.get("by_category", {}).get("adversarial", {})  # type: ignore[union-attr]
    if isinstance(adv, dict) and adv.get("pass_rate", 1.0) < 0.9:
        problems.append(f"对抗类通过率 {adv['pass_rate']:.1%} 低于 90%（安全问题不允许放行）")

    return problems
