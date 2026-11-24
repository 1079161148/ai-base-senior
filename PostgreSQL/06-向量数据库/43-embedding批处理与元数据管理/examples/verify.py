"""第 43 章 · embedding 批处理与元数据管理。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker, fake_embedding  # noqa: E402

c = Checker(43)

c.sql("""
CREATE TABLE docs (
  id SERIAL PRIMARY KEY, title TEXT, model TEXT, dim INT,
  embedding vector(16), updated_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
""")

texts = [f"文档{i}" for i in range(1, 21)]
with c.conn.cursor() as cur:
    for title in texts:
        cur.execute(
            "INSERT INTO docs (title,model,dim,embedding) VALUES (%s,%s,%s,%s)",
            (title, "fake-v1", 16, fake_embedding(title, 16)),
        )

c.equal("批量写入 20 行", c.scalar("SELECT count(*) FROM docs"), 20)
c.equal("维度元数据一致", c.scalar("SELECT count(*) FROM docs WHERE dim=16"), 20)
c.equal("模型版本记录", c.scalar("SELECT count(*) FROM docs WHERE model='fake-v1'"), 20)

all_dims = c.rows("SELECT DISTINCT vector_dims(embedding) FROM docs")
c.equal("向量维度全部一致", [r[0] for r in all_dims], [16])

c.sql("UPDATE docs SET embedding=%s, model='fake-v2' WHERE id=1", (fake_embedding("文档1-改", 16),))
c.equal("单条重新 embed", c.scalar("SELECT model FROM docs WHERE id=1"), "fake-v2")

mixed = c.scalar("SELECT count(*) FROM docs WHERE model <> 'fake-v2'")
c.ok("新旧版本可共存", mixed == 19, str(mixed))

c.sql("CREATE INDEX idx_docs_hnsw ON docs USING hnsw (embedding vector_cosine_ops)")
c.ok("批量后建索引", c.scalar("SELECT count(*) FROM pg_indexes WHERE schemaname='ch43' AND indexname='idx_docs_hnsw'") == 1)

query_vec = fake_embedding("文档5", 16)
top5 = c.rows("SELECT title FROM docs ORDER BY embedding <=> %s::vector LIMIT 5", (query_vec,))
c.equal("批量数据可检索", len(top5), 5)
c.equal("最近邻是自身", top5[0][0], "文档5")

with_ts = c.scalar("SELECT count(*) FROM docs WHERE updated_at IS NOT NULL")
c.equal("时间戳齐全", with_ts, 20)

raise SystemExit(c.finish())
