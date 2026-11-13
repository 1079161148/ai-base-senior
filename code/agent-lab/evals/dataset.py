"""评测集加载与校验。

**为什么要校验**：评测集本身出错，比 Agent 出错更隐蔽 ——
一条 expected 拼错的样本会永远判失败，然后你会去改提示词，越改越糟。
所以加载时就断言：分类数量、id 唯一、必填字段齐全。
"""

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Literal

Category = Literal["standard", "subjective", "adversarial"]

# 分层配比来自 S7 任务 2：20 / 20 / 10
EXPECTED_COUNTS: dict[str, int] = {
    "standard": 20,
    "subjective": 20,
    "adversarial": 10,
}


@dataclass(slots=True)
class Case:
    id: str
    category: Category
    question: str
    expected: dict[str, object] = field(default_factory=dict)
    rubric: str = ""


def load_suite(path: str | Path) -> list[Case]:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"评测集不存在：{p}")

    data = json.loads(p.read_text(encoding="utf-8"))
    raw_cases = data.get("cases") if isinstance(data, dict) else data
    if not isinstance(raw_cases, list) or not raw_cases:
        raise ValueError("评测集格式错误：需要一个非空的 cases 数组")

    cases: list[Case] = []
    seen: set[str] = set()
    for i, raw in enumerate(raw_cases):
        if not isinstance(raw, dict):
            raise ValueError(f"第 {i} 条不是对象")
        cid = str(raw.get("id") or "").strip()
        category = raw.get("category")
        question = str(raw.get("question") or "").strip()

        if not cid:
            raise ValueError(f"第 {i} 条缺少 id")
        if cid in seen:
            raise ValueError(f"id 重复：{cid}")
        if category not in ("standard", "subjective", "adversarial"):
            raise ValueError(f"{cid} 的 category 非法：{category!r}")
        if not question:
            raise ValueError(f"{cid} 的 question 为空")

        expected = raw.get("expected") or {}
        if not isinstance(expected, dict):
            raise ValueError(f"{cid} 的 expected 必须是对象")
        if category == "subjective" and not raw.get("rubric"):
            raise ValueError(f"{cid} 是主观题，必须给 rubric（否则无从判分）")

        seen.add(cid)
        cases.append(
            Case(
                id=cid,
                category=category,
                question=question,
                expected=expected,
                rubric=str(raw.get("rubric") or ""),
            )
        )

    return cases


def check_distribution(cases: list[Case], strict: bool = False) -> dict[str, int]:
    """统计分层数量。

    strict=True 用于 CI（必须 20/20/10），
    日常小样本回归（--limit）时不强制。
    """
    counts: dict[str, int] = {}
    for c in cases:
        counts[c.category] = counts.get(c.category, 0) + 1

    if strict:
        for name, want in EXPECTED_COUNTS.items():
            got = counts.get(name, 0)
            if got != want:
                raise ValueError(f"{name} 应有 {want} 条，实际 {got} 条")
    return counts
