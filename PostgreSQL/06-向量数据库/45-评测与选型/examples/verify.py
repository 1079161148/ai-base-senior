"""第 45 章 · 向量检索评测与选型。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker, fake_embedding  # noqa: E402

c = Checker(45)

c.sql("""
CREATE TABLE docs (
  id SERIAL PRIMARY KEY, title TEXT, topic TEXT, embedding vector(8)
);
""")

corpus = [
    ("关系型数据库", "db"), ("索引与查询优化", "db"), ("事务与锁", "db"),
    ("番茄炒蛋", "food"), ("红烧肉做法", "food"), ("面包烘焙", "food"),
]
with c.conn.cursor() as cur:
    for title, topic in corpus:
        cur.execute(
            "INSERT INTO docs (title,topic,embedding) VALUES (%s,%s,%s)",
            (title, topic, fake_embedding(title, 8)),
        )

c.equal("语料入库", c.scalar("SELECT count(*) FROM docs"), 6)

query = "数据库索引"
qvec = fake_embedding(query, 8)
top3 = [r[0] for r in c.rows("SELECT id FROM docs ORDER BY embedding <=> %s::vector LIMIT 3", (qvec,))]
relevant = [r[0] for r in c.rows("SELECT id FROM docs WHERE topic='db' ORDER BY id")]
recall = len(set(top3) & set(relevant)) / len(relevant)
c.ok("Recall@3 可计算", 0 < recall <= 1, f"recall={recall:.2f}")

precision = len(set(top3) & set(relevant)) / 3
c.ok("Precision@3 可计算", 0 < precision <= 1, f"precision={precision:.2f}")

c.sql("CREATE INDEX idx_docs_hnsw ON docs USING hnsw (embedding vector_cosine_ops)")
ann = [r[0] for r in c.rows("SELECT id FROM docs ORDER BY embedding <=> %s::vector LIMIT 3", (qvec,))]
c.ok("近似检索有结果", len(ann) == 3, str(ann))

overlap = len(set(top3) & set(ann))
c.ok("精确与 ANN 结果可比", overlap >= 1, f"重合={overlap}")

quality = c.rows("""
SELECT topic, avg(embedding <=> %s::vector) AS avg_dist
FROM docs GROUP BY topic ORDER BY avg_dist
""", (qvec,))
c.ok("按主题统计距离", len(quality) == 2 and quality[0][1] <= quality[1][1], str(quality))

c.ok("HNSW 参数存在", c.scalar("SELECT count(*) FROM pg_settings WHERE name='hnsw.ef_search'") == 1)
c.ok("IVFFlat 参数存在", c.scalar("SELECT count(*) FROM pg_settings WHERE name='ivfflat.probes'") == 1)

raise SystemExit(c.finish())
