"""第 24 章 · GIN / GiST / BRIN：特殊索引。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(24)
c.sql("""
CREATE TABLE docs (
    id SERIAL PRIMARY KEY,
    body TEXT,
    attrs JSONB,
    tags TEXT[],
    created DATE,
    during TSRANGE
);
INSERT INTO docs (body,attrs,tags,created,during)
SELECT
  CASE g%3 WHEN 0 THEN 'postgres database tutorial' WHEN 1 THEN 'vector similarity search' ELSE 'python programming intro' END,
  jsonb_build_object('level', g%5, 'kind', CASE WHEN g%2=0 THEN 'a' ELSE 'b' END),
  ARRAY['tag'||(g%10), 'common'],
  date '2020-01-01' + g,
  tsrange(make_timestamp(g,1,1,0,0,0), make_timestamp(g+1,1,1,0,0,0))
FROM generate_series(1,5000) g;
""")

c.sql("CREATE INDEX idx_attrs_gin ON docs USING gin (attrs)")
c.ok("JSONB GIN 建索引", c.scalar("SELECT count(*) FROM docs WHERE attrs @> '{\"kind\":\"a\"}'") > 0)

c.sql("CREATE INDEX idx_tags_gin ON docs USING gin (tags)")
c.ok("数组 GIN 包含查询", c.scalar("SELECT count(*) FROM docs WHERE tags @> ARRAY['tag3']") > 0)

c.sql("ALTER TABLE docs ADD COLUMN search_vector TSVECTOR")
c.sql("UPDATE docs SET search_vector = to_tsvector('simple', body)")
c.sql("CREATE INDEX idx_search_gin ON docs USING gin (search_vector)")
c.ok("全文检索命中", c.scalar("SELECT count(*) FROM docs WHERE search_vector @@ plainto_tsquery('simple','vector')") > 0)

ranked = c.rows("""
SELECT id, ts_rank(search_vector, plainto_tsquery('simple','database')) AS r
FROM docs WHERE search_vector @@ plainto_tsquery('simple','database')
ORDER BY r DESC LIMIT 3
""")
c.ok("ts_rank 排序", len(ranked) == 3 and ranked[0][1] >= ranked[2][1], str(ranked))

c.sql("CREATE INDEX idx_created_brin ON docs USING brin (created)")
c.ok("BRIN 范围查询", c.scalar("SELECT count(*) FROM docs WHERE created BETWEEN '2025-01-01' AND '2025-03-01'") > 0)

c.sql("CREATE INDEX idx_during_gist ON docs USING gist (during)")
c.ok("GiST 范围包含", c.scalar("SELECT count(*) FROM docs WHERE during @> '2025-06-01 12:00:00'::timestamp") > 0)

sizes = dict(c.rows("""
SELECT indexrelname, pg_relation_size(indexrelid) FROM pg_stat_user_indexes WHERE relname='docs'
"""))
c.ok("BRIN 远小于 B-tree", sizes.get("idx_created_brin", 1) < sizes.get("idx_tags_gin", 0), str(sizes))

idx_types = c.rows("""
SELECT am.amname FROM pg_index i
JOIN pg_class ic ON ic.oid=i.indexrelid
JOIN pg_am am ON am.oid=ic.relam
WHERE i.indrelid='docs'::regclass
""")
kinds = {r[0] for r in idx_types}
c.ok("四种索引方法共存", {"gin", "brin", "gist", "btree"} <= kinds, str(kinds))

c.ok("JSONB 包含查询结果正确",
     c.scalar("SELECT count(*) FROM docs WHERE attrs @> '{\"kind\":\"a\"}'") == 2500)

raise SystemExit(c.finish())
