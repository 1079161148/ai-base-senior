"""重排（rerank）的测试。

**这个文件要证明的不是"排序更准"，而是"不管出什么问题都别把检索搞挂"**：

rerank 是检索链路上的可选增强，模型有 1.1GB，加载要下载、要内存。
线上最常见的失败恰恰不是"排得不准"，而是：
  · 开关关着却仍然去加载模型（白白下载 1.1GB）
  · 模型没下下来，每次检索都重试一次（每问一句卡 30 秒）
  · 加载失败把整个 search_docs 拖成 500

所以这里的用例集中在开关、降级、熔断三件事上。
"""

import pytest

from agent_lab.app.core.config import settings
from agent_lab.app.services.rag import retriever
from agent_lab.app.services.rag.store import StoredChunk


def make_chunk(i: int) -> StoredChunk:
    return StoredChunk(
        id=f"c{i}",
        doc_id="d1",
        chunk_index=i,
        heading=f"标题 {i}",
        content=f"正文 {i}",
        raw=f"原文 {i}",
        tokens=["正文", str(i)],
    )


@pytest.fixture
def candidates() -> list[StoredChunk]:
    """10 个候选，模拟 RRF 融合后的池子。"""
    return [make_chunk(i) for i in range(10)]


def _clear_model_cache() -> None:
    """清掉 lru_cache。

    要判断 cache_clear 是否存在：某些用例会把 `_load_reranker` 换成普通函数
    （模拟加载失败），而 fixture 的 teardown 跑在 monkeypatch 还原**之前**，
    那时它还没有 cache_clear 属性。
    """
    fn = retriever._load_reranker
    if hasattr(fn, "cache_clear"):
        fn.cache_clear()


@pytest.fixture(autouse=True)
def reset_breaker(monkeypatch):
    """每条用例前后都重置熔断标志和模型缓存，避免用例之间互相污染。"""
    monkeypatch.setattr(retriever, "_rerank_unavailable", False)
    _clear_model_cache()
    yield
    monkeypatch.setattr(retriever, "_rerank_unavailable", False)
    _clear_model_cache()


class TestSwitch:
    async def test_disabled_returns_original_order(self, monkeypatch, candidates) -> None:
        monkeypatch.setattr(settings, "RERANK_ENABLED", False)

        # 模型不该被碰到：这里让加载直接抛错，一旦被调用用例就失败
        monkeypatch.setattr(
            retriever, "_reranker", lambda: pytest.fail("开关关闭时不该加载模型")
        )

        result = await retriever.rerank("查询", candidates, top_k=3)
        assert [c.id for c in result] == ["c0", "c1", "c2"]

    async def test_fewer_candidates_than_top_k_skips_model(
        self, monkeypatch, candidates
    ) -> None:
        monkeypatch.setattr(settings, "RERANK_ENABLED", True)
        monkeypatch.setattr(
            retriever, "_reranker", lambda: pytest.fail("候选不足时不该调用模型")
        )

        # 只有 10 个候选，要 20 条 —— 没有可排序的余地
        result = await retriever.rerank("查询", candidates, top_k=20)
        assert len(result) == 10


class FakeReranker:
    """假模型：按 chunk 编号倒序打分，方便断言"顺序真的变了"。"""

    def __init__(self, scores: list[float] | None = None, *, raise_on_use: bool = False):
        self._scores = scores
        self._raise = raise_on_use

    def rerank_pairs(self, pairs, batch_size=None):
        if self._raise:
            raise RuntimeError("ONNX session 创建失败")
        if self._scores is not None:
            return iter(self._scores)
        # 默认：越靠后分越高，迫使排序反转
        return iter([float(i) for i in range(len(pairs))])


class TestRerankBehavior:
    async def test_reorders_by_score(self, monkeypatch, candidates) -> None:
        monkeypatch.setattr(settings, "RERANK_ENABLED", True)
        monkeypatch.setattr(retriever, "_reranker", lambda: FakeReranker())

        result = await retriever.rerank("查询", candidates, top_k=3)
        # 分数随位置递增，排序后应变成 c9, c8, c7
        assert [c.id for c in result] == ["c9", "c8", "c7"]

    async def test_truncates_to_top_k(self, monkeypatch, candidates) -> None:
        monkeypatch.setattr(settings, "RERANK_ENABLED", True)
        monkeypatch.setattr(retriever, "_reranker", lambda: FakeReranker())

        result = await retriever.rerank("查询", candidates, top_k=4)
        assert len(result) == 4

    async def test_falls_back_when_model_raises(self, monkeypatch, candidates) -> None:
        """推理阶段炸了 —— 退回原顺序，绝不能抛给调用方。"""
        monkeypatch.setattr(settings, "RERANK_ENABLED", True)
        monkeypatch.setattr(retriever, "_reranker", lambda: FakeReranker(raise_on_use=True))

        result = await retriever.rerank("查询", candidates, top_k=3)
        assert [c.id for c in result] == ["c0", "c1", "c2"]

    async def test_falls_back_when_load_fails(self, monkeypatch, candidates) -> None:
        """加载阶段炸了（没网、没内存）—— 同样只降级。"""

        def boom():
            raise OSError("模型下载失败")

        monkeypatch.setattr(settings, "RERANK_ENABLED", True)
        monkeypatch.setattr(retriever, "_reranker", boom)

        result = await retriever.rerank("查询", candidates, top_k=3)
        assert [c.id for c in result] == ["c0", "c1", "c2"]

    async def test_score_length_mismatch_falls_back(self, monkeypatch, candidates) -> None:
        """模型只返回 3 个分数时要退回，而不是拿错位的分数排序。"""
        monkeypatch.setattr(settings, "RERANK_ENABLED", True)
        monkeypatch.setattr(
            retriever, "_reranker", lambda: FakeReranker(scores=[0.1, 0.2, 0.3])
        )

        result = await retriever.rerank("查询", candidates, top_k=3)
        assert [c.id for c in result] == ["c0", "c1", "c2"]


class TestBreaker:
    """熔断：加载失败一次之后，后续请求必须立刻跳过。

    没有熔断时，网络不通的表现是"每问一句都卡 30 秒等超时"，
    用户会以为整个系统挂了。
    """

    def test_second_call_does_not_retry(self, monkeypatch) -> None:
        monkeypatch.setattr(retriever, "_rerank_unavailable", False)

        attempts = 0

        def failing_load():
            nonlocal attempts
            attempts += 1
            raise OSError("下载失败")

        monkeypatch.setattr(retriever, "_load_reranker", failing_load)

        for _ in range(3):
            with pytest.raises((OSError, RuntimeError)):
                retriever._reranker()

        assert attempts == 1, "失败后应熔断，不能每次都重试下载"

    async def test_after_breaker_rerank_still_returns_results(
        self, monkeypatch, candidates
    ) -> None:
        monkeypatch.setattr(settings, "RERANK_ENABLED", True)
        monkeypatch.setattr(retriever, "_rerank_unavailable", True)
        monkeypatch.setattr(
            retriever, "_load_reranker", lambda: pytest.fail("熔断后不该再尝试加载")
        )

        result = await retriever.rerank("查询", candidates, top_k=3)
        assert [c.id for c in result] == ["c0", "c1", "c2"]
