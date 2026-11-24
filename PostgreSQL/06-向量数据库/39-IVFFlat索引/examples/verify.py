"""第 39 章 · IVFFlat 倒排索引。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(39)

c.sql("""
CREATE TABLE docs (id SERIAL PRIMARY KEY, title TEXT, embedding vector(3));
INSERT INTO docs (title,embedding)
SELECT 'doc-'||g, ('['||(g%10)||','||((g*3)%10)||','||((g*7)%10)||']')::vector
FROM generate_series(1,500) g;
""")
c.equal("样本已生成", c.scalar("SELECT count(*) FROM docs"), 500)

c.sql("CREATE INDEX idx_ivf ON docs USING ivfflat (embedding vector_l2_ops) WITH (lists=10)")
idx = c.scalar("""
SELECT indexdef FROM pg_indexes WHERE indexname='idx_ivf'
""")
c.ok("IVFFlat 索引建成", "ivfflat" in idx, idx[:60])

c.sql("SET ivfflat.probes=5")
probes = c.scalar("SHOW ivfflat.probes")
c.equal("probes 可调", probes, "5")

exact = c.rows("SELECT id FROM docs ORDER BY embedding <-> '[0,0,0]'::vector LIMIT 10")
c.sql("SET enable_seqscan=off")
approx = c.rows("SELECT id FROM docs ORDER BY embedding <-> '[0,0,0]'::vector LIMIT 10")
c.ok("索引查询返回结果", len(approx) == 10, str(approx[:3]))
c.ok("索引召回与精确一致", exact == approx, f"精确={exact[:3]} 近似={approx[:3]}")

idx_scan = c.scalar("""
SELECT count(*) FROM pg_indexes WHERE indexname='idx_ivf' AND indexdef LIKE '%ivfflat%'
""")
c.ok("索引元数据一致", idx_scan == 1, str(idx_scan))

relsize = c.scalar("SELECT pg_relation_size('idx_ivf'::regclass)")
c.ok("索引占用空间", relsize > 0, str(relsize))

raise SystemExit(c.finish())
