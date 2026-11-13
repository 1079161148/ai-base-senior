"""S7 回归用例：评测集本身的体检。

评测集出错比 Agent 出错更隐蔽 —— 一条 expected 拼错的样本会永远失败，
然后你以为是模型的问题，越改越糟。
"""

import json

import pytest

from evals.dataset import EXPECTED_COUNTS, check_distribution, load_suite


def test_real_suite_is_valid():
    cases = load_suite("data/eval/suite.json")
    assert len(cases) == 50
    counts = check_distribution(cases, strict=True)
    assert counts == EXPECTED_COUNTS


def test_duplicate_id_rejected(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text(
        json.dumps(
            {
                "cases": [
                    {"id": "x", "category": "standard", "question": "q"},
                    {"id": "x", "category": "standard", "question": "q2"},
                ]
            },
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="id 重复"):
        load_suite(p)


def test_subjective_requires_rubric(tmp_path):
    p = tmp_path / "bad2.json"
    p.write_text(
        json.dumps(
            {"cases": [{"id": "s1", "category": "subjective", "question": "怎么评价"}]},
            ensure_ascii=False,
        ),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="rubric"):
        load_suite(p)


def test_invalid_category_rejected(tmp_path):
    p = tmp_path / "bad3.json"
    p.write_text(
        json.dumps({"cases": [{"id": "c1", "category": "unknown", "question": "q"}]}),
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="category"):
        load_suite(p)
