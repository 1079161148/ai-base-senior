"""混合检索：pgvector 向量 + BM25 关键词 → RRF 融合 → 可选 rerank。

检索流程（对应教材 7.1 四层架构）：
  ① 粗筛：向量 HNSW top-50 + BM25 top-50
  ② 融合：RRF 去重
  ③ 重排：可选 cross-encoder / LLM
  ④ 取数：保留 top-k，用于组装 prompt

pgvector 的连接由内部自己管理 —— 调用方不需要传 pg 连接。
这样 search_docs 工具和其他调用方不用关心底层是 SQLite 还是 PostgreSQL。
"""

import asyncio
import logging
import time
from functools import lru_cache
from pathlib import Path

from ...core.config import settings
from . import embedder, store
from .bm25 import BM25Index
from .store import StoredChunk

logger = logging.getLogger(__name__)

RRF_K = 60
VECTOR_TOP = 50
KEYWORD_TOP = 50
FINAL_K = 5


def _rrf(
    vec: list[tuple[int, float]],
    kw: list[tuple[int, float]],
    k: int = RRF_K,
    top: int = FINAL_K,
) -> list[int]:
    scores: dict[int, float] = {}
    for rank, (idx, _) in enumerate(vec):
        scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
    for rank, (idx, _) in enumerate(kw):
        scores[idx] = scores.get(idx, 0.0) + 1.0 / (k + rank + 1)
    merged = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [idx for idx, _ in merged[:top]]


async def retrieve(
    query: str,
    top_k: int = FINAL_K,
    *,
    user_id: str | None = "",
) -> tuple[list[StoredChunk], float]:
    """混合检索：向量 + BM25 → RRF → top_k。

    返回 (按相关性排序的 chunk 列表, 耗时毫秒)。
    """
    from ...core.pg import _pool_for_fastapi as _pg_pool

    started = time.perf_counter()

    pg_pool = _pg_pool
    if pg_pool is None:
        raise RuntimeError("pg pool 尚未创建")

    async with pg_pool.acquire() as pg:
        qv = await embedder.embed_query(query)

        # ① 向量粗筛（HNSW 索引）：只返回最像的 50 块
        vec_chunks = await store.vector_search(pg, qv, top_k=VECTOR_TOP, user_id=user_id)

        # ② 全量 chunk 用于 BM25。同时建好 id→index 映射，
        #    因为向量结果和 BM25 结果是两套索引空间，
        #    不映射的话 RRF 按各自索引合并会指到完全不相关的块。
        all_chunks = await store.load_all_tokens(pg, user_id=user_id)
        id_to_index: dict[str, int] = {c.id: i for i, c in enumerate(all_chunks)}

        # ③ 关键词粗筛（BM25）
        bm25 = BM25Index([c.tokens for c in all_chunks])
        kw_hits = bm25.search(query, top_k=KEYWORD_TOP)  # idx in all_chunks

        # ④ 把向量结果的局部索引映射到全局（all_chunks）索引
        vec_hits_global: list[tuple[int, float]] = []
        for rank, c in enumerate(vec_chunks):
            gidx = id_to_index.get(c.id)
            if gidx is not None:
                vec_hits_global.append((gidx, float(VECTOR_TOP - rank) / VECTOR_TOP))

        # ⑤ RRF 融合
        # 开启 rerank 时先取一个更大的候选池交给 cross-encoder 精排；
        # 关闭时只取 top_k —— 多算出来的那部分注定会被丢掉，纯属浪费。
        pool = (
            max(top_k, settings.RERANK_CANDIDATES) if settings.RERANK_ENABLED else top_k
        )
        merged = _rrf(vec_hits_global, kw_hits, top=pool)
        result = [all_chunks[i] for i in merged]

    # ⑥ 重排。放在连接池外面：cross-encoder 是纯 CPU 计算，
    #    抱着数据库连接做几百毫秒推理，等于把连接池当算力池用。
    result = await rerank(query, result, top_k=top_k)

    elapsed_ms = (time.perf_counter() - started) * 1000
    logger.info(
        "检索完成：%s → 向量 %d / 关键词 %d → 输出 %d (%.0f ms)",
        query[:30], len(vec_chunks), len(kw_hits), len(result), elapsed_ms,
    )
    return result, elapsed_ms


# ---- Rerank ----
# 教材 7.1 要求 cross-encoder rerank：对合并后的候选块逐条打分。
# bge-reranker-base ONNX 版约 1.1GB，首次加载 5-10s，之后常驻内存。
# Cross-encoder 和 bi-encoder（嵌入用）的根本区别：
#   bi-encoder 分别编码 query 和 passage，算余弦做近似匹配（快但粗糙）
#   cross-encoder 把 query+passage 拼一起全文编码（准但慢，只适合 top-k 候选）
#
# 由 settings.RERANK_ENABLED 控制，默认关闭。
# 本项目实测（5 份文档 / 25 个 chunk，"怎么部署到服务器"）：
#   关闭 23ms → 开启 2917ms，首位结果并没有变好。
# 结论：小知识库上是纯亏的 —— 延迟涨两个数量级，质量没动。
# 值得打开的场景是候选池本身就有几十上百条、RRF 排序明显失准时。

_RERANKER_MODEL = "BAAI/bge-reranker-base"

# 加载失败后熔断。
# 不加这个标志的话，每次检索都会重试一次 1.1GB 下载 ——
# 网络不通时表现为"每问一句卡 30 秒"，比直接不用 rerank 糟糕得多。
_rerank_unavailable = False


@lru_cache(maxsize=1)
def _load_reranker():
    """进程级单例。首次调用加载模型（含可能的下载），之后直接复用。"""
    from fastembed.rerank.cross_encoder import TextCrossEncoder

    cache_dir = Path(settings.MODEL_CACHE_DIR)
    cache_dir.mkdir(parents=True, exist_ok=True)
    logger.info("加载重排模型 %s（缓存目录 %s）…", _RERANKER_MODEL, cache_dir)
    return TextCrossEncoder(model_name=_RERANKER_MODEL, cache_dir=str(cache_dir))


def _reranker():
    """取重排模型，失败则熔断后续调用。"""
    global _rerank_unavailable

    if _rerank_unavailable:
        raise RuntimeError("reranker 此前加载失败，已熔断")

    try:
        return _load_reranker()
    except Exception:
        _rerank_unavailable = True
        raise


async def rerank(
    query: str,
    candidates: list[StoredChunk],
    top_k: int = FINAL_K,
) -> list[StoredChunk]:
    """Cross-encoder 重排序。候选 ≤ top_k 时不调，直接返回。

    注意：这比 LLM rerank 大约快 100×（本地 ONNX vs 调远程 API），
    而且分数是基于真实语义理解的，不是模型猜的。

    **失败必须降级而不是抛**：rerank 是"锦上添花"的一步，
    模型没下下来、内存不够、ONNX 跑不起来 —— 任何一种都不该让
    整个 RAG 检索挂掉。退回 RRF 的顺序，效果差一点但功能还在。
    """
    if not settings.RERANK_ENABLED:
        return candidates[:top_k]
    if len(candidates) <= top_k:
        return candidates[:top_k]

    pairs = [(query, c.content[:512]) for c in candidates]

    try:
        model = _reranker()
        # cross-encoder 推理是 CPU bound，放到线程池避免阻塞事件循环
        scores: list[float] = await asyncio.to_thread(
            lambda: list(model.rerank_pairs(pairs, batch_size=len(pairs)))
        )
    except Exception:  # noqa: BLE001 - 重排是可选步骤，任何问题都只降级
        logger.warning("rerank 不可用，本次退回 RRF 顺序", exc_info=True)
        return candidates[:top_k]

    if len(scores) != len(candidates):
        # 防御：分数条数对不上就没法一一对应排序，宁可退回也不拼错
        logger.warning("rerank 分数条数异常（%d vs %d），退回 RRF", len(scores), len(candidates))
        return candidates[:top_k]

    scored = list(zip(candidates, scores))
    scored.sort(key=lambda x: x[1], reverse=True)
    return [c for c, _ in scored[:top_k]]