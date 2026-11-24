"""第 22 章 · B-tree、联合索引、部分索引、表达式索引。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(22)
c.sql("""
CREATE TABLE idx_demo (id SERIAL PRIMARY KEY, dept INT, age INT, name TEXT, active BOOLEAN DEFAULT true);
INSERT INTO idx_demo (dept,age,name)
SELECT g%10, 18+(g%50), 'name'||g FROM generate_series(1,10000) g;
ANALYZE idx_demo;
""")

def plan(sql):
    return "\n".join(r[0] for r in c.rows("EXPLAIN " + sql))


def scan(sql):
    text = plan(sql)
    return "Index" if "Index Scan" in text or "Bitmap" in text else "Seq"

c.sql("CREATE INDEX idx_age ON idx_demo(age)")
c.ok("等值走 B-tree", "Index Scan" in plan("SELECT * FROM idx_demo WHERE age=30") or "Bitmap" in plan("SELECT * FROM idx_demo WHERE age=30"))

c.ok("范围走 B-tree", "Index Scan" in plan("SELECT * FROM idx_demo WHERE age BETWEEN 20 AND 25") or "Bitmap" in plan("SELECT * FROM idx_demo WHERE age BETWEEN 20 AND 25"))

c.sql("CREATE INDEX idx_dept_age ON idx_demo(dept, age)")
leftmost = plan("SELECT * FROM idx_demo WHERE dept=3")
c.ok("联合索引最左前缀", "idx_dept_age" in leftmost, leftmost[:80])

no_prefix = plan("SELECT * FROM idx_demo WHERE age=30")
c.ok("跳过最左列用另一索引", "idx_age" in no_prefix or "Bitmap" in no_prefix, no_prefix[:80])

c.sql("VACUUM ANALYZE idx_demo")
covered = plan("SELECT age FROM idx_demo WHERE age=30")
c.ok("覆盖索引 Index Only", "Index Only Scan" in covered, covered[:80])

c.sql("CREATE UNIQUE INDEX idx_name_unique ON idx_demo(name)")
c.equal("唯一索引元数据", c.scalar("SELECT count(*) FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid WHERE c.relname='idx_name_unique' AND i.indisunique"), 1)

c.sql("CREATE INDEX idx_active_part ON idx_demo(id) WHERE active")
c.equal("部分索引元数据", c.scalar("SELECT count(*) FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid WHERE c.relname='idx_active_part' AND pg_get_expr(i.indpred,i.indrelid) <> ''"), 1)

c.sql("CREATE INDEX idx_lower_name ON idx_demo(lower(name))")
c.ok("表达式索引元数据", c.scalar("SELECT count(*) FROM pg_index i JOIN pg_class c ON c.oid=i.indexrelid WHERE c.relname='idx_lower_name'"), 1)

c.equal("唯一索引等值查询", scan("SELECT * FROM idx_demo WHERE name='name123'"), "Index")

sizes = c.rows("SELECT indexrelname, pg_relation_size(indexrelid) FROM pg_stat_user_indexes WHERE relname='idx_demo' ORDER BY 1")
c.ok("索引大小可查", len(sizes) >= 5, str(len(sizes)))

raise SystemExit(c.finish())
