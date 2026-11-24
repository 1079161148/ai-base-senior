"""第 36 章 · 安装 pgvector 与第一个向量表。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker, fake_embedding  # noqa: E402

c = Checker(36)
c.sql("CREATE EXTENSION IF NOT EXISTS vector")

c.ok("扩展安装", c.scalar("SELECT count(*) FROM pg_extension WHERE extname='vector'") == 1)
c.ok("vector 类型可见", c.scalar("SELECT count(*) FROM pg_type WHERE typname='vector'") >= 1)

c.sql("CREATE TABLE docs (id SERIAL PRIMARY KEY, title TEXT NOT NULL, embedding vector(3))")
col_type = c.scalar("""
SELECT format_type(a.atttypid,a.atttypmod) FROM pg_attribute a
WHERE a.attrelid='docs'::regclass AND a.attname='embedding'
""")
c.equal("列类型为 vector(3)", col_type, "vector(3)")

c.sql("INSERT INTO docs (title,embedding) VALUES ('A',%s),('B',%s),('C',%s)",
      (fake_embedding("apple", 3), fake_embedding("banana", 3), fake_embedding("cherry", 3)))
c.equal("三行入库", c.scalar("SELECT count(*) FROM docs"), 3)

first = c.scalar("SELECT embedding::text FROM docs WHERE title='A'")
c.ok("向量可读回", first.startswith("[") and first.endswith("]"), first)

query = fake_embedding("apple", 3)
nearest = c.scalar("SELECT title FROM docs ORDER BY embedding <-> %s::vector LIMIT 1", (query,))
c.equal("最近邻查询", nearest, "A")

ops = c.rows("""
SELECT oprname FROM pg_operator o JOIN pg_type t ON t.oid=o.oprleft
WHERE t.typname='vector' AND oprname IN ('<->','<=>','<#>') ORDER BY oprname
""")
c.ok("距离算子存在", {r[0] for r in ops} >= {"<->", "<=>", "<#>"}, str(ops))

raise SystemExit(c.finish())
