"""第 42 章 · 关键词 + 向量混合检索。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(42)

c.sql("""
CREATE TABLE docs (
  id SERIAL PRIMARY KEY, title TEXT, body TEXT, embedding vector(3),
  tsv TSVECTOR GENERATED ALWAYS AS (to_tsvector('simple', title || ' ' || body)) STORED
);
INSERT INTO docs (title,body,embedding) VALUES
 ('数据库教程','PostgreSQL 向量检索入门','[1,0,0]'),
 ('数据库进阶','索引与查询优化','[0.9,0.1,0]'),
 ('做饭菜谱','番茄炒蛋的做法','[0,1,0]');
""")
c.sql("CREATE INDEX idx_docs_tsv ON docs USING gin(tsv)")
c.sql("CREATE INDEX idx_docs_vec ON docs USING hnsw (embedding vector_cosine_ops)")

kw = c.rows("SELECT id FROM docs WHERE title ILIKE '%数据库%' ORDER BY id")
c.equal("关键词命中两篇", [r[0] for r in kw], [1, 2])

vec = c.rows("""
SELECT id FROM docs ORDER BY embedding <=> '[1,0,0]'::vector LIMIT 2
""")
c.equal("向量命中相关两篇", sorted(r[0] for r in vec), [1, 2])

c.sql("""
CREATE VIEW hybrid AS
SELECT id,
       CASE WHEN title ILIKE '%数据库%' THEN 1 ELSE 2 END AS kw_rank,
       ROW_NUMBER() OVER (ORDER BY embedding <=> '[1,0,0]'::vector) AS vec_rank
FROM docs
""")
rrf = c.rows("""
SELECT id, 1.0/(60+kw_rank) + 1.0/(60+vec_rank) AS score
FROM hybrid ORDER BY score DESC
""")
c.ok("RRF 融合可计算", len(rrf) == 3 and rrf[0][1] >= rrf[-1][1], str(rrf))

top = [r[0] for r in rrf[:2]]
c.ok("融合结果相关文档靠前", 1 in top and 2 in top, str(top))

filtered = c.rows("""
SELECT id FROM docs
WHERE title ILIKE '%数据库%'
ORDER BY embedding <=> '[1,0,0]'::vector LIMIT 1
""")
c.equal("关键词过滤+向量排序", filtered[0][0], 1)

c.ok("GIN 索引存在", c.scalar("SELECT count(*) FROM pg_indexes WHERE indexname='idx_docs_tsv'") == 1)
c.ok("HNSW 索引存在", c.scalar("SELECT count(*) FROM pg_indexes WHERE indexname='idx_docs_vec'") == 1)

raise SystemExit(c.finish())
