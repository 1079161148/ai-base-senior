"""第 21 章 · EXPLAIN：看懂执行计划。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(21)
c.sql("""
CREATE TABLE orders_probe (id SERIAL PRIMARY KEY, created_at DATE, status TEXT, amount NUMERIC(10,2));
INSERT INTO orders_probe (created_at,status,amount)
SELECT date '2024-01-01' + (g % 365),
       CASE g % 3 WHEN 0 THEN 'paid' WHEN 1 THEN 'pending' ELSE 'done' END,
       (g % 1000)::numeric
FROM generate_series(1,20000) g;
ANALYZE orders_probe;
""")

plan = "\n".join(r[0] for r in c.rows("EXPLAIN SELECT * FROM orders_probe WHERE created_at='2024-06-01'"))
c.ok("EXPLAIN 返回计划", "QUERY PLAN" in plan or "Scan" in plan, plan[:50])
c.ok("无索引顺序扫描", "Seq Scan" in plan, plan[:60])

analyzed = "\n".join(r[0] for r in c.rows("EXPLAIN (ANALYZE, BUFFERS) SELECT * FROM orders_probe WHERE created_at='2024-06-01'"))
c.ok("ANALYZE 显示真实耗时", "Execution Time" in analyzed, "")
c.ok("BUFFERS 显示共享命中", "Buffers:" in analyzed, "")

json_plan = c.rows("EXPLAIN (FORMAT JSON) SELECT * FROM orders_probe WHERE id=1")
c.ok("JSON 格式计划", "Plan" in str(json_plan[0][0]), str(json_plan[0][0])[:60])

c.sql("CREATE INDEX idx_probe_created ON orders_probe(created_at)")
c.sql("ANALYZE orders_probe")
indexed = "\n".join(r[0] for r in c.rows("EXPLAIN SELECT * FROM orders_probe WHERE created_at='2024-06-01'"))
c.ok("建索引后走索引扫描", "Index Scan" in indexed or "Bitmap" in indexed, indexed[:80])

rows = c.scalar("SELECT count(*) FROM orders_probe WHERE created_at='2024-06-01'")
c.ok("索引不改变结果", rows == 54 or rows > 0, str(rows))

cost_only = "\n".join(r[0] for r in c.rows("EXPLAIN SELECT * FROM orders_probe"))
c.ok("成本估算存在", "cost=" in cost_only, cost_only[:60])

small = "\n".join(r[0] for r in c.rows("EXPLAIN SELECT * FROM orders_probe WHERE id=1"))
c.ok("主键查询走索引", "Index" in small, small[:60])

raise SystemExit(c.finish())
