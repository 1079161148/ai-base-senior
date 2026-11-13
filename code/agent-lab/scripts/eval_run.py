"""S7 · 评测入口。

用法：
    uv run python scripts/eval_run.py --limit 5              # 先跑 5 条看看
    uv run python scripts/eval_run.py                        # 全量 50 条
    uv run python scripts/eval_run.py --judge                 # 主观题启用 LLM 打分
    uv run python scripts/eval_run.py --min-pass-rate 0.9     # CI 门禁

退出码：0 达标，1 有维度劣化（CI 里直接卡住合并）。
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path

import httpx

# 允许 `python scripts/eval_run.py` 直接跑（项目根加入 sys.path）
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from evals import dataset, judge as judge_mod, report, runner  # noqa: E402


async def llm_score(
    client: httpx.AsyncClient,
    question: str,
    answer: str,
    rubric: str,
) -> int | None:
    """LLM-as-Judge：让另一个模型按 rubric 打 1~5 分。

    加 try/except 是因为判分服务本身也可能挂 —— 判分失败不该让整批结果作废，
    标记成"待人工"更诚实。
    """
    from agent_lab.app.models.schemas import JudgeScore
    from agent_lab.app.services import structured

    system = (
        "你是严格的评审。按 rubric 给回答打分（1=完全不符合，5=完全符合）。"
        "只输出 JSON，字段 score(1-5 的整数) 和 reason(一句话)。"
    )
    prompt = f"问题：{question}\n\n评分标准：{rubric}\n\n待评回答：\n{answer[:2000]}"
    try:
        result = await structured.complete_object(
            prompt, client=client, schema=JudgeScore, system=system
        )
        return int(result.value.score)
    except Exception as exc:
        print(f"    [judge 失败] {type(exc).__name__}: {exc}")
        return None


async def main() -> int:
    parser = argparse.ArgumentParser(description="S7 评测：50 条分层回归集")
    parser.add_argument("--suite", default="data/eval/suite.json")
    parser.add_argument("--base-url", default="http://127.0.0.1:8001")
    parser.add_argument("--limit", type=int, default=0, help="只跑前 N 条（0=全部）")
    parser.add_argument("--offset", type=int, default=0, help="跳过前 N 条（配合 limit 分批跑）")
    parser.add_argument("--category", default="", help="只跑某一层：standard/subjective/adversarial")
    parser.add_argument("--judge", action="store_true", help="主观题启用 LLM-as-Judge")
    parser.add_argument("--min-pass-rate", type=float, default=0.80)
    parser.add_argument("--max-p95-ms", type=float, default=60000)
    parser.add_argument("--max-avg-cost", type=float, default=0.05)
    parser.add_argument("--strict-counts", action="store_true", help="校验 20/20/10 配比")
    parser.add_argument("--out", default="data/eval/last_report.json")
    parser.add_argument("--keep-sessions", action="store_true", help="保留评测产生的会话（默认删除）")
    args = parser.parse_args()

    cases = dataset.load_suite(args.suite)
    counts = dataset.check_distribution(cases, strict=args.strict_counts)
    print(f"评测集：{len(cases)} 条  {counts}")

    if args.category:
        cases = [c for c in cases if c.category == args.category]
        print(f"  过滤后：{len(cases)} 条（{args.category}）")
    if args.offset > 0:
        cases = cases[args.offset :]
        print(f"  跳过前 {args.offset} 条")
    if args.limit > 0:
        cases = cases[: args.limit]
        print(f"  本次跑 {len(cases)} 条")

    if not cases:
        print("没有可跑的用例")
        return 1

    results: list[report.CaseResult] = []

    async with httpx.AsyncClient(timeout=180) as client:
        # 先确认服务在跑，避免 50 条全部失败刷屏
        try:
            health = await client.get(f"{args.base_url}/api/v1/health", timeout=10)
            health.raise_for_status()
        except Exception as exc:
            print(f"后端不可用（{args.base_url}）：{exc}")
            return 2

        for i, case in enumerate(cases, 1):
            run = await runner.run_case(client, args.base_url, case.id, case.question)

            score = None
            if args.judge and case.category == "subjective" and not run.error:
                score = await llm_score(client, case.question, run.answer, case.rubric)

            verdict = judge_mod.judge(
                case_id=case.id,
                category=case.category,
                expected=case.expected,
                rubric=case.rubric,
                run=run,
                llm_score=score,
            )

            results.append(
                report.CaseResult(
                    case_id=case.id,
                    category=case.category,
                    passed=verdict.passed,
                    score=verdict.score,
                    reason=verdict.reason,
                    failure_type=verdict.failure_type,
                    needs_human=verdict.needs_human,
                    duration_ms=run.duration_ms,
                    cost_cny=run.cost_cny,
                    tools=run.tools,
                )
            )

            mark = "✅" if verdict.passed else "❌"
            print(
                f"[{i:02d}/{len(cases)}] {mark} {case.id:<10} "
                f"{run.duration_ms:>7.0f}ms ¥{run.cost_cny:.5f} "
                f"{verdict.reason[:50]}"
            )

            if not args.keep_sessions:
                await runner.cleanup_session(client, args.base_url, run.session_id)

    summary = report.summarize(results)
    problems = report.check_gates(
        summary,
        min_pass_rate=args.min_pass_rate,
        max_p95_ms=args.max_p95_ms,
        max_avg_cost_cny=args.max_avg_cost,
    )
    summary["gates"] = {"passed": not problems, "problems": problems}

    print("\n" + "=" * 60)
    print(f"通过率   {summary['pass_rate']:.1%}  ({summary['passed']}/{summary['total']})")
    for cat, stat in summary["by_category"].items():  # type: ignore[union-attr]
        print(f"  {cat:<12} {stat['passed']}/{stat['count']}  {stat['pass_rate']:.1%}")
    print(f"P50/P95  {summary['p50_ms']}ms / {summary['p95_ms']}ms")
    print(f"成本     均 ¥{summary['avg_cost_cny']:.6f}  合计 ¥{summary['total_cost_cny']:.6f}")
    if summary["failure_types"]:
        print(f"失败归类 {summary['failure_types']}")
    if summary["needs_human"]:
        print(f"待人工   {summary['needs_human']}")
    print("=" * 60)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"报告已写入 {out}")

    if problems:
        print("\n❌ 门禁未通过：")
        for p in problems:
            print(f"   - {p}")
        return 1

    print("\n✅ 全部门禁通过")
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
