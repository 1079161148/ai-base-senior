"""S4 · 上下文预算管理器。

核心职责：数 token + 按优先级裁剪。

教材要求（Context Engineering.md 第四节）：
    超预算时裁剪优先级（从低到高）：
        早期原文 > 摘要 > 检索结果 > 当前问题 > 系统提示

实现要点：
    - 用 tiktoken 数 token（o200k_base 是 gpt-4o 的 tokenizer，中文也兼容）
    - 裁剪是"删"不是"截断"——从最早的原文开始整段删，不把一句话撕成两半
    - system prompt 是最后底线，绝不裁剪
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

import tiktoken

from ...core.config import settings

logger = logging.getLogger(__name__)

# gpt-4o 的 tokenizer。中文一个汉字 ≈ 1~3 个 token，
# 英文 ≈ 0.5~1 token。对预算管理的目的来说精度足够。
_ENCODER = tiktoken.get_encoding("o200k_base")


def count_tokens(text: str) -> int:
    """返回一段文本的 token 数。"""
    return len(_ENCODER.encode(text))


def count_tokens_batch(texts: list[str]) -> list[int]:
    """批量统计，避免多次调用。"""
    return [len(_ENCODER.encode(t)) for t in texts]


@dataclass
class ContextBudget:
    """上下文预算管理器：追踪各组件 token 占用，超限时按优先级裁剪。

    用法：
        budget = ContextBudget()
        budget.add("system", system_prompt, priority=0)
        budget.add("memories", long_term_text, priority=2)
        budget.add("working", user_msg, priority=3)
        if budget.is_over():
            budget.trim()
        context = budget.assemble()
    """

    budget: int = settings.CONTEXT_BUDGET
    items: list[_BudgetItem] = field(default_factory=list)
    _total: int = 0

    def add(self, component: str, text: str, priority: int = 0) -> None:
        """添加一个上下文组件。

        priority 越小越不能删：
            0 = system prompt（绝不裁剪）
            1 = 当前用户问题
            2 = RAG 检索结果
            3 = 长期记忆 + 摘要记忆
            4 = 早期原文（最先被裁）
        """
        tokens = count_tokens(text) if text else 0
        self.items.append(_BudgetItem(component, text, tokens, priority))
        self._total += tokens

    def is_over(self) -> bool:
        return self._total > self.budget

    def get_usage(self) -> dict:
        """返回各组件 token 占用，用于 done 帧。"""
        breakdown: dict[str, int] = {}
        ratio = self._total / self.budget if self.budget > 0 else 0
        for item in self.items:
            key = item.component
            breakdown[key] = breakdown.get(key, 0) + item.tokens
        return {
            "used_tokens": self._total,
            "budget_tokens": self.budget,
            "ratio": round(ratio, 3),
            "breakdown": breakdown,
        }

    def trim(self) -> None:
        """超预算时按优先级从低到高删除（priority 大的先删）。

        删除策略：每条完整删除——不截断文本，保留语义完整性。
        删到预算以下或只剩 priority 0/1 时停止。
        """
        if not self.is_over():
            return

        # 只考虑可裁剪的（priority >= 4）
        trimmable = [i for i in self.items if i.priority >= 4]
        trimmable.sort(key=lambda i: (-i.priority, i.tokens))

        logger.info(
            "超预算 %d/%d，开始裁剪…", self._total, self.budget
        )

        for item in trimmable:
            if not self.is_over():
                break
            self._total -= item.tokens
            item.tokens = 0
            item.text = "[已裁剪]"
            logger.debug("  裁剪 %s（priority=%d, %d tokens）", item.component, item.priority, item.tokens)

        # 如果还是超（摘要 + 长期记忆也太多了），从 priority >= 3 开始裁
        if self.is_over():
            logger.warning("裁剪早期原文后仍超预算，开始裁剪摘要和记忆…")
            upper = [i for i in self.items if i.priority == 3]
            for item in sorted(upper, key=lambda i: i.tokens, reverse=True):
                if not self.is_over():
                    break
                self._total -= item.tokens
                item.tokens = 0
                item.text = "[已裁剪]"

        logger.info("裁剪后：%d/%d token", self._total, self.budget)

    def assemble(self) -> str:
        """把所有有效组件拼回一段完整 prompt 文本。"""
        return "\n\n".join(
            item.text for item in self.items if item.tokens > 0
        )


@dataclass
class _BudgetItem:
    component: str
    text: str
    tokens: int
    priority: int