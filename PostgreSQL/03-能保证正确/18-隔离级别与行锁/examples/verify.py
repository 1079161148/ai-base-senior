"""第 18 章 · 隔离级别选型与 FOR UPDATE 行锁。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import DSN, Checker  # noqa: E402
import psycopg  # noqa: E402

c = Checker(18)
c.sql("CREATE TABLE stock (id INT PRIMARY KEY, qty INT)")
c.sql("INSERT INTO stock VALUES (1, 10), (2, 20)")

c.equal("默认隔离", c.scalar("SHOW transaction_isolation"), "read committed")

with psycopg.connect(DSN) as tx:
    tx.execute("SET search_path TO ch18")
    tx.execute("BEGIN")
    tx.execute("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ")
    level = tx.execute("SHOW transaction_isolation").fetchone()[0]
    tx.execute("COMMIT")
c.equal("事务内设置生效", level, "repeatable read")

with psycopg.connect(DSN) as tx:
    tx.execute("SET search_path TO ch18")
    tx.execute("SET SESSION CHARACTERISTICS AS TRANSACTION ISOLATION LEVEL SERIALIZABLE")
    session_level = tx.execute("SHOW default_transaction_isolation").fetchone()[0]
    tx.execute("SET SESSION CHARACTERISTICS AS TRANSACTION ISOLATION LEVEL READ COMMITTED")
c.equal("会话级设置", session_level, "serializable")

locker = psycopg.connect(DSN, autocommit=False)
locker.execute("SET search_path TO ch18")
locker.execute("BEGIN")
locker.execute("SELECT qty FROM stock WHERE id=1 FOR UPDATE")

other = psycopg.connect(DSN, autocommit=True)
other.execute("SET search_path TO ch18")
other.execute("SET lock_timeout = '200ms'")
blocked = False
try:
    other.execute("UPDATE stock SET qty=qty-1 WHERE id=1")
except psycopg.errors.LockNotAvailable:
    blocked = True
c.ok("FOR UPDATE 阻塞并发写", blocked)
locker.execute("ROLLBACK")
other.execute("UPDATE stock SET qty=qty-1 WHERE id=1")
c.equal("锁释放后可写", c.scalar("SELECT qty FROM stock WHERE id=1"), 9)

locker.execute("BEGIN")
locker.execute("SET search_path TO ch18")  # ROLLBACK 会撤销事务内的 SET
locker.execute("SELECT qty FROM stock WHERE id=1 FOR UPDATE NOWAIT")
nowait_blocked = False
try:
    other.execute("SELECT qty FROM stock WHERE id=1 FOR UPDATE NOWAIT")
except psycopg.errors.LockNotAvailable:
    nowait_blocked = True
c.ok("NOWAIT 立即失败", nowait_blocked)
locker.execute("ROLLBACK")

locker.execute("BEGIN")
locker.execute("SET search_path TO ch18")
locker.execute("SELECT qty FROM stock WHERE id=1 FOR UPDATE")
skip = other.execute("SELECT id FROM stock FOR UPDATE SKIP LOCKED").fetchall()
c.equal("SKIP LOCKED 跳过锁定行", [r[0] for r in skip], [2])
locker.execute("ROLLBACK")

shared = c.rows("SELECT qty FROM stock WHERE id=2 FOR SHARE")
c.equal("FOR SHARE", [r[0] for r in shared], [20])

locks = c.rows("SELECT count(*) FROM pg_locks WHERE pid = pg_backend_pid()")
c.ok("pg_locks 可查", locks[0][0] >= 0, str(locks[0][0]))

locker.close()
other.close()

raise SystemExit(c.finish())
