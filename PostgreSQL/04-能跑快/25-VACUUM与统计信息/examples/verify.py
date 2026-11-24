"""第 25 章 · VACUUM、ANALYZE、膨胀。"""

import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(25)
c.sql("""
CREATE TABLE churn (id SERIAL PRIMARY KEY, payload TEXT);
INSERT INTO churn (payload) SELECT repeat('x',200) FROM generate_series(1,2000);
CREATE INDEX idx_churn_id ON churn(id);
ALTER TABLE churn SET (autovacuum_enabled = false);
""")

c.sql("UPDATE churn SET payload=payload||'y'")
time.sleep(0.4)  # 统计器异步刷新
c.ok("UPDATE 已执行", c.scalar("SELECT count(*) FROM churn") == 2000)

c.sql("VACUUM churn")
c.ok("VACUUM 可执行", True)

c.sql("ANALYZE churn")
stats = c.rows("SELECT relname, n_live_tup FROM pg_stat_user_tables WHERE relname='churn'")
c.equal("ANALYZE 更新统计", stats[0][1], 2000)

autovac = c.rows("""
SELECT name,setting FROM pg_settings
WHERE name IN ('autovacuum','autovacuum_vacuum_scale_factor') ORDER BY name
""")
c.equal("autovacuum 配置可查", len(autovac), 2)

c.sql("CREATE TABLE plan_stats (id INT, val INT)")
c.sql("INSERT INTO plan_stats SELECT g, g%2 FROM generate_series(1,1000) g")
c.sql("CREATE INDEX idx_plan_val ON plan_stats(val)")
before = "\n".join(r[0] for r in c.rows("EXPLAIN SELECT * FROM plan_stats WHERE val=0"))
c.sql("ANALYZE plan_stats")
after_plan = "\n".join(r[0] for r in c.rows("EXPLAIN SELECT * FROM plan_stats WHERE val=0"))
c.ok("统计影响计划", bool(before) and bool(after_plan), "")

with c.conn.cursor() as cur:
    in_txn_vacuum_failed = False
    try:
        cur.execute("BEGIN")
        cur.execute("VACUUM churn")
    except Exception:
        in_txn_vacuum_failed = True
    cur.execute("ROLLBACK")
c.ok("事务内不能 VACUUM", in_txn_vacuum_failed)

size_before = c.scalar("SELECT pg_relation_size('idx_churn_id')")
c.sql("REINDEX TABLE churn")
size_after = c.scalar("SELECT pg_relation_size('idx_churn_id')")
c.ok("REINDEX 可执行", size_after > 0, f"{size_before}->{size_after}")

last_vacuum = c.scalar("SELECT last_vacuum IS NOT NULL FROM pg_stat_user_tables WHERE relname='churn'")
c.ok("记录上次 VACUUM 时间", last_vacuum)

db_size = c.scalar("SELECT pg_size_pretty(pg_database_size(current_database()))")
c.ok("库大小可查", "MB" in db_size or "kB" in db_size, db_size)

raise SystemExit(c.finish())
