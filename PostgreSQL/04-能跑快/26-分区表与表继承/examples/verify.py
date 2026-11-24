"""第 26 章 · 声明式分区与表继承。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(26)
c.sql("""
CREATE TABLE logs (
    id BIGSERIAL, created DATE NOT NULL, level TEXT, message TEXT
) PARTITION BY RANGE (created);
CREATE TABLE logs_2024 PARTITION OF logs FOR VALUES FROM ('2024-01-01') TO ('2025-01-01');
CREATE TABLE logs_2025 PARTITION OF logs FOR VALUES FROM ('2025-01-01') TO ('2026-01-01');
CREATE TABLE logs_other PARTITION OF logs DEFAULT;
INSERT INTO logs (created,level,message)
SELECT date '2024-01-01' + (g % 700),
       CASE WHEN g%2=0 THEN 'info' ELSE 'error' END,
       'msg'||g
FROM generate_series(1,1000) g;
ANALYZE logs;
""")

partitions = c.rows("""
SELECT c.relname FROM pg_inherits i JOIN pg_class c ON c.oid=i.inhrelid
WHERE i.inhparent='logs'::regclass ORDER BY 1
""")
c.equal("分区数量", [r[0] for r in partitions], ["logs_2024", "logs_2025", "logs_other"])

c.equal("总行数", c.scalar("SELECT count(*) FROM logs"), 1000)
c.ok("数据自动路由 2024", c.scalar("SELECT count(*) FROM logs_2024") > 0)
c.ok("默认分区接收越界", c.scalar("SELECT count(*) FROM logs WHERE created < '2024-01-01'") == 0)

pruned = "\n".join(r[0] for r in c.rows("EXPLAIN SELECT * FROM logs WHERE created >= '2025-01-01' AND created < '2025-06-01'"))
c.ok("分区剪枝", "logs_2025" in pruned and "logs_2024" not in pruned, pruned[:120])

all_scan = "\n".join(r[0] for r in c.rows("EXPLAIN SELECT * FROM logs WHERE level='error'"))
c.ok("无分区键扫所有分区", "logs_2024" in all_scan and "logs_2025" in all_scan, all_scan[:80])

c.sql("CREATE INDEX idx_logs_level ON logs(level)")
c.ok("父表建索引传播到分区", c.scalar("""
SELECT count(*) FROM pg_indexes WHERE schemaname='ch26' AND tablename LIKE 'logs_%' AND indexdef LIKE '%level%'
""") >= 3)

c.sql("ALTER TABLE logs DETACH PARTITION logs_other")
c.equal("DETACH 后父表少一个分区", c.scalar("""
SELECT count(*) FROM pg_inherits WHERE inhparent='logs'::regclass
"""), 2)

c.sql("ALTER TABLE logs ATTACH PARTITION logs_other DEFAULT")
c.equal("ATTACH 恢复", c.scalar("""
SELECT count(*) FROM pg_inherits WHERE inhparent='logs'::regclass
"""), 3)

meta = c.scalar("SELECT count(*) FROM pg_partitioned_table WHERE partrelid='logs'::regclass")
c.equal("分区元数据", meta, 1)

c.sql("""
CREATE TABLE parent_inherit (id INT, note TEXT);
CREATE TABLE child_inherit (extra TEXT) INHERITS (parent_inherit);
INSERT INTO child_inherit VALUES (1,'子表','扩展');
""")
c.equal("表继承查询父表可见子表行", c.scalar("SELECT count(*) FROM parent_inherit"), 1)

raise SystemExit(c.finish())
