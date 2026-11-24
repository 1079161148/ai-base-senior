"""第 03 章 · SQL 分类：DDL / DML / DCL / TCL。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker, DSN  # noqa: E402
import psycopg  # noqa: E402

c = Checker(3)

# DDL：定义结构
c.sql("CREATE TABLE t03 (id int PRIMARY KEY, val text)")
c.ok("DDL CREATE", c.scalar("SELECT to_regclass('t03') IS NOT NULL"))

# DML：操作数据
c.sql("INSERT INTO t03 VALUES (1, 'a'), (2, 'b')")
c.sql("UPDATE t03 SET val = 'A' WHERE id = 1")
c.sql("DELETE FROM t03 WHERE id = 2")
c.equal("DML 增删改查", c.rows("SELECT id, val FROM t03 ORDER BY id"), [(1, "A")])

# DCL：权限（查系统目录，不真的授权）
acl = c.rows(
    "SELECT has_schema_privilege(current_user, 'ch03', 'CREATE'), "
    "has_table_privilege(current_user, 'ch03.t03', 'SELECT')"
)
c.equal("DCL 权限可查", acl, [(True, True)])

# TCL：事务控制
with psycopg.connect(DSN) as tx:
    tx.execute("SET search_path TO ch03")
    tx.execute("INSERT INTO t03 VALUES (3, '会回滚')")
    tx.rollback()
c.equal("TCL ROLLBACK", c.scalar("SELECT count(*) FROM t03"), 1)

# TRUNCATE 归类为 DDL：会重置 sequence
c.sql("CREATE TABLE t03_seq (id SERIAL PRIMARY KEY)")
c.sql("INSERT INTO t03_seq DEFAULT VALUES")
c.sql("DELETE FROM t03_seq")
c.equal("DELETE 不重置序列", c.scalar("SELECT nextval('t03_seq_id_seq'::regclass)"), 2)
c.sql("TRUNCATE TABLE t03_seq RESTART IDENTITY")
c.equal("TRUNCATE 重置序列", c.scalar("SELECT nextval('t03_seq_id_seq'::regclass)"), 1)

# SQL 是声明式：优化器可以改写执行方式
plan = c.scalar("EXPLAIN SELECT * FROM t03 WHERE id = 1")
c.ok("声明式 SQL 有执行计划", "QUERY PLAN" in plan or "Seq Scan" in plan or "Index" in plan, str(plan)[:40])

c.sql("DROP TABLE t03, t03_seq")
c.ok("DDL DROP", c.scalar("SELECT to_regclass('t03') IS NULL"))

raise SystemExit(c.finish())
