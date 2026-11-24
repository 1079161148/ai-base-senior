"""第 35 章 · 向量数据库认知与 embedding。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker, fake_embedding  # noqa: E402

c = Checker(35)

c.ok("pgvector 可用", c.scalar("SELECT count(*) FROM pg_available_extensions WHERE name='vector'") == 1)
c.sql("CREATE EXTENSION IF NOT EXISTS vector")
c.ok("扩展已安装", c.scalar("SELECT count(*) FROM pg_extension WHERE extname='vector'") == 1)

v1 = fake_embedding("华为手机", 8)
v2 = fake_embedding("华为手机壳", 8)
v3 = fake_embedding("Python编程入门", 8)

c.equal("embedding 确定性", v1, fake_embedding("华为手机", 8))
c.equal("向量维度正确", c.scalar("SELECT vector_dims(%s::vector)", (v1,)), 8)

d_near = c.scalar("SELECT %s::vector <-> %s::vector", (v1, v2))
d_far = c.scalar("SELECT %s::vector <-> %s::vector", (v1, v3))
c.ok("相似文本距离更近", d_near < d_far, f"相近={d_near:.4f} 相远={d_far:.4f}")

c.sql("CREATE TABLE docs (id SERIAL PRIMARY KEY, title TEXT, embedding vector(8))")
c.sql("INSERT INTO docs (title,embedding) VALUES ('华为手机',%s),('华为手机壳',%s),('Python编程入门',%s)",
      (v1, v2, v3))
c.equal("向量可入库", c.scalar("SELECT count(*) FROM docs"), 3)

ranked = c.rows("SELECT title FROM docs ORDER BY embedding <-> %s::vector", (v1,))
c.equal("最近邻是自身", ranked[0][0], "华为手机")

raise SystemExit(c.finish())
