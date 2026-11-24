"""第 17 章 · 四类并发异常：哪些会发生、哪些被 PG 挡住。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import DSN, Checker  # noqa: E402
import psycopg  # noqa: E402

c = Checker(17)
c.sql("CREATE TABLE concurrent_demo (id INT PRIMARY KEY, balance INT)")
c.sql("INSERT INTO concurrent_demo VALUES (1, 1000), (2, 2000)")

# 脏读：PG 的 READ COMMITTED 看不到未提交修改
a = psycopg.connect(DSN, autocommit=True)
b = psycopg.connect(DSN, autocommit=True)
a.execute("SET search_path TO ch17")
b.execute("SET search_path TO ch17")
a.execute("BEGIN")
a.execute("UPDATE concurrent_demo SET balance=800 WHERE id=1")
dirty = b.execute("SELECT balance FROM concurrent_demo WHERE id=1").fetchone()[0]
a.execute("ROLLBACK")
c.equal("脏读不发生", dirty, 1000)

# 不可重复读：READ COMMITTED 下同一事务两次读到不同值
a.execute("BEGIN")
first = a.execute("SELECT balance FROM concurrent_demo WHERE id=1").fetchone()[0]
b.execute("UPDATE concurrent_demo SET balance=900 WHERE id=1")
second = a.execute("SELECT balance FROM concurrent_demo WHERE id=1").fetchone()[0]
a.execute("COMMIT")
c.ok("READ COMMITTED 不可重复读", (first, second) == (1000, 900), f"{first}->{second}")

# 幻读：READ COMMITTED 下两次范围查询结果集不同
a.execute("BEGIN")
before = a.execute("SELECT count(*) FROM concurrent_demo WHERE balance>500").fetchone()[0]
b.execute("INSERT INTO concurrent_demo VALUES (3, 600)")
after = a.execute("SELECT count(*) FROM concurrent_demo WHERE balance>500").fetchone()[0]
a.execute("COMMIT")
c.ok("READ COMMITTED 幻读", (before, after) == (2, 3), f"{before}->{after}")

# REPEATABLE READ 下不可重复读被阻止
b.execute("DELETE FROM concurrent_demo WHERE id=3")
a.execute("BEGIN")
a.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
a.execute("SELECT balance FROM concurrent_demo WHERE id=1")
b.execute("UPDATE concurrent_demo SET balance=700 WHERE id=1")
rr_second = a.execute("SELECT balance FROM concurrent_demo WHERE id=1").fetchone()[0]
a.execute("COMMIT")
c.equal("REPEATABLE READ 阻止不可重复读", rr_second, 900)

# REPEATABLE READ 下幻读被阻止
a.execute("BEGIN")
a.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
rr_before = a.execute("SELECT count(*) FROM concurrent_demo WHERE balance>500").fetchone()[0]
b.execute("INSERT INTO concurrent_demo VALUES (4, 650)")
rr_after = a.execute("SELECT count(*) FROM concurrent_demo WHERE balance>500").fetchone()[0]
a.execute("COMMIT")
c.equal("REPEATABLE READ 阻止幻读", rr_before, rr_after)

# 更新丢失：两个事务基于同一旧值更新
b.execute("DELETE FROM concurrent_demo WHERE id=4")
a.execute("BEGIN")
a.execute("SELECT balance FROM concurrent_demo WHERE id=2")
b.execute("UPDATE concurrent_demo SET balance=1900 WHERE id=2")
a.execute("UPDATE concurrent_demo SET balance=1800 WHERE id=2")
a.execute("COMMIT")
c.equal("READ COMMITTED 更新丢失", c.scalar("SELECT balance FROM concurrent_demo WHERE id=2"), 1800)

# SERIALIZABLE 下更新冲突被阻止
a.execute("BEGIN")
a.execute("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE")
a.execute("SELECT balance FROM concurrent_demo WHERE id=2")
b.execute("UPDATE concurrent_demo SET balance=1700 WHERE id=2")
serializable_blocked = False
try:
    a.execute("UPDATE concurrent_demo SET balance=1600 WHERE id=2")
    a.execute("COMMIT")
except psycopg.errors.SerializationFailure:
    serializable_blocked = True
    a.execute("ROLLBACK")
c.ok("SERIALIZABLE 阻止并发冲突", serializable_blocked)

a.close()
b.close()

levels = c.rows("SELECT name, setting FROM pg_settings WHERE name='default_transaction_isolation'")
c.equal("默认隔离级别元数据", levels[0][1], "read committed")

raise SystemExit(c.finish())
