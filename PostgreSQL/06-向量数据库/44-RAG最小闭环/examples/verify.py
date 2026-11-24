"""第 44 章 · RAG 最小闭环：切块、入库、检索、拼上下文。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker, fake_embedding  # noqa: E402

c = Checker(43 + 1)

c.sql("""
CREATE TABLE chunks (
  id SERIAL PRIMARY KEY, doc_id INT, chunk_no INT, content TEXT, embedding vector(8)
);
""")

chunks = [
    (1, 1, "PostgreSQL 是关系型数据库"),
    (1, 2, "pgvector 扩展支持向量检索"),
    (1, 3, "HNSW 索引适合高维向量"),
    (2, 1, "番茄炒蛋需要鸡蛋和番茄"),
    (2, 2, "先把鸡蛋炒熟再放番茄"),
]
with c.conn.cursor() as cur:
    for doc_id, chunk_no, content in chunks:
        cur.execute(
            "INSERT INTO chunks (doc_id,chunk_no,content,embedding) VALUES (%s,%s,%s,%s)",
            (doc_id, chunk_no, content, fake_embedding(content, 8)),
        )

c.equal("切块入库", c.scalar("SELECT count(*) FROM chunks"), 5)

query = fake_embedding("pgvector 向量检索", 8)
hits = c.rows("""
SELECT doc_id,chunk_no,content FROM chunks ORDER BY embedding <=> %s::vector LIMIT 3
""", (query,))
c.equal("召回 Top-3", len(hits), 3)
c.ok("最相关块命中", any("pgvector" in h[2] or "向量检索" in h[2] for h in hits), str(hits))

context = "\n".join(f"[文档{h[0]} 块{h[1]}] {h[2]}" for h in hits)
c.ok("上下文可拼装", "文档" in context and "pgvector" in context, context[:60])

within_doc = c.rows("""
SELECT chunk_no FROM chunks WHERE doc_id=1
ORDER BY embedding <=> %s::vector
""", (query,))
c.ok("按文档过滤检索", len(within_doc) == 3 and all(n in (1, 2, 3) for n, in within_doc), str(within_doc))

c.ok("距离可计算", all(
    isinstance(r[0], (int, float)) and r[0] >= 0
    for r in c.rows("SELECT embedding <=> %s::vector FROM chunks", (query,))
))

threshold_hits = c.rows("""
SELECT content FROM chunks WHERE embedding <=> %s::vector < 0.5
ORDER BY embedding <=> %s::vector
""", (query, query))
c.ok("阈值过滤可执行", isinstance(len(threshold_hits), int), str(len(threshold_hits)))

c.sql("CREATE INDEX idx_chunks_vec ON chunks USING hnsw (embedding vector_cosine_ops)")
c.ok("检索索引存在", c.scalar("SELECT count(*) FROM pg_indexes WHERE indexname='idx_chunks_vec'") == 1)

raise SystemExit(c.finish())
