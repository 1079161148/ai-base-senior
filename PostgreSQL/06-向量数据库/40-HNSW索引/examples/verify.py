"""第 40 章 · HNSW 索引。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(40)

c.sql("""
CREATE TABLE docs (id SERIAL PRIMARY KEY, embedding vector(3));
INSERT INTO docs (embedding)
SELECT ('['||(g%10)||','||((g*3)%10)||','||((g*7)%10)||']')::vector
FROM generate_series(1,500) g;
""")

c.sql("""
CREATE INDEX idx_hnsw ON docs USING hnsw (embedding vector_cosine_ops)
WITH (m=16, ef_construction=64);
""")
idx = c.scalar("SELECT indexdef FROM pg_indexes WHERE indexname='idx_hnsw'")
c.ok("HNSW 索引建成", "hnsw" in idx and "ef_construction" in idx and "64" in idx, idx[:100])

c.sql("SET hnsw.ef_search=40")
c.equal("ef_search 可调", c.scalar("SHOW hnsw.ef_search"), "40")

result = c.rows("""
SELECT id FROM docs ORDER BY embedding <=> '[0,0,0]'::vector LIMIT 10
""")
c.equal("Top-10 返回", len(result), 10)

exact = c.rows("""
SELECT id FROM docs ORDER BY embedding <=> '[0,0,0]'::vector LIMIT 10
""")
c.equal("查询可重复", result, exact)

params = c.rows("""
SELECT name FROM pg_settings WHERE name LIKE 'hnsw.%' ORDER BY name
""")
c.ok("HNSW 参数可查", any("ef_search" in r[0] for r in params), str(params))

small = c.scalar("SELECT id FROM docs ORDER BY embedding <=> '[0,0,0]'::vector LIMIT 1")
c.ok("最近邻可定位", small is not None, str(small))

c.ok("索引空间 nonzero", c.scalar("SELECT pg_relation_size('idx_hnsw'::regclass)") > 0)

raise SystemExit(c.finish())
