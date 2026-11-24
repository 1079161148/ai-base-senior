"""第 37 章 · vector(n) 类型与维度约束。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(37)

c.sql("CREATE TABLE v3 (id SERIAL PRIMARY KEY, embedding vector(3))")
col_type = c.scalar("""
SELECT format_type(a.atttypid,a.atttypmod) FROM pg_attribute a
WHERE a.attrelid='v3'::regclass AND a.attname='embedding'
""")
c.equal("维度写进类型", col_type, "vector(3)")

c.sql("INSERT INTO v3 (embedding) VALUES ('[1,2,3]')")
c.equal("合法维度入库", c.scalar("SELECT vector_dims(embedding) FROM v3"), 3)

mismatch = False
try:
    c.sql("INSERT INTO v3 (embedding) VALUES ('[1,2]')")
except Exception:
    mismatch = True
c.ok("维度不匹配被拒绝", mismatch)

c.sql("CREATE TABLE vmax (embedding vector)")
c.sql("INSERT INTO vmax VALUES ('[1,2,3,4,5]')")
c.equal("无维度声明可存任意维度", c.scalar("SELECT vector_dims(embedding) FROM vmax"), 5)

parsed = c.rows("SELECT '[1.5,2.5]'::vector::real[]")
c.equal("向量可转数组", [round(float(x), 1) for x in parsed[0][0]], [1.5, 2.5])

texts = c.rows("SELECT embedding::text FROM v3")
c.ok("向量文本表示", texts[0][0].startswith("["), str(texts))

c.sql("CREATE INDEX idx_v3_l2 ON v3 USING hnsw (embedding vector_l2_ops)")
c.ok("向量索引可建", c.scalar("SELECT count(*) FROM pg_indexes WHERE indexname='idx_v3_l2'") == 1)

raise SystemExit(c.finish())
