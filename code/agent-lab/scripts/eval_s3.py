"""S3 检索评测：跑 20 条评测集，算 Recall@5。

评测集格式（对应 plan 任务 4）：
  {"qid": 1, "question": "...", "expected_doc_ids": ["abc123#0003"]}

Recall@5 = top-5 中至少有一个 chunk.id 在 expected_doc_ids 里。
"""

import asyncio
import json
from pathlib import Path

from agent_lab.app.core import pg as pg_core
from agent_lab.app.services.rag import embedder, ingest, retriever

EVAL_PATH = Path(__file__).resolve().parents[1] / "data" / "eval_s3.json"
DOC_PATH = Path(__file__).resolve().parents[3] / "docs" / "RAG完整链路.md"


async def main() -> None:
    embedder.warm_up()

    pool = await pg_core.create_pool()
    pg_core.set_pool(pool)
    await pg_core.init_pg()

    # 确保评测用文档已摄入（幂等：重复摄入会覆盖）
    text = DOC_PATH.read_text(encoding="utf-8")
    meta = await ingest.ingest_text(
        text=text,
        title="RAG完整链路",
        source="RAG完整链路.md",
        doc_type="md",
    )
    print(f"摄入完成: {meta['chunk_count']} 块, doc_id={meta['id']}\n")

    questions = json.loads(EVAL_PATH.read_text(encoding="utf-8"))
    print(f"评测集: {len(questions)} 条\n")

    hits = 0
    total_ms = 0.0

    for item in questions:
        qid = item["qid"]
        question = str(item["question"])
        expected_ids = [str(i) for i in item.get("expected_doc_ids", [])]
        expected_sections = [str(s) for s in item.get("expected_sections", [])]
        keywords = [str(k) for k in item.get("expected_keywords", [])]

        chunks, ms = await retriever.retrieve(question, top_k=5)
        total_ms += ms

        # 命中规则：
        # 1. chunk.id 在 expected_doc_ids 里（精确匹配）
        # 2. heading 包含 expected_sections 中的一个
        # 3. raw 包含 ≥60% 的 expected_keywords
        found = any(c.id in expected_ids for c in chunks)
        if not found and expected_sections:
            found = any(
                any(exp in c.heading for exp in expected_sections)
                for c in chunks
            )
        if not found and keywords:
            for c in chunks:
                matched = sum(1 for kw in keywords if kw.lower() in c.raw.lower())
                if matched >= max(3, len(keywords) * 0.6):
                    found = True
                    break

        if found:
            hits += 1

        status = "✓" if found else "✗"
        top_headings = [c.heading[:60] for c in chunks[:3]]
        print(f"  {status} q{qid:02d}: {question[:45]}…")
        if not found:
            print(f"     预期: {expected_ids or expected_sections}  实际: {top_headings}")

    recall = hits / len(questions) * 100
    avg_ms = total_ms / max(1, len(questions))
    print(f"\nRecall@5 = {hits}/{len(questions)} = {recall:.1f}%")
    print(f"平均耗时 = {avg_ms:.0f} ms")
    if recall >= 80:
        print("\n[✓] 达到验收标准（≥80%）")
    else:
        print("\n[✗] 未达标，需要调分块/检索/嵌入参数")

    # 不在这里关池，让进程退出时自然清理
    # 跑完脚本就退出了，pool.close() 的 IO 不重要


asyncio.run(main())