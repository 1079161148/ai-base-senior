"""第 16 章 · 事务：BEGIN/COMMIT/ROLLBACK/SAVEPOINT 与 ACID。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import DSN, Checker  # noqa: E402
import psycopg  # noqa: E402

c = Checker(16)
c.sql("""
CREATE TABLE accounts (
    id VARCHAR(10) PRIMARY KEY,
    name TEXT NOT NULL,
    balance NUMERIC(12,2) NOT NULL CHECK (balance >= 0)
);
INSERT INTO accounts VALUES ('A','张三',500.00), ('B','李四',1000.00);
""")

c.equal("初始总额", c.scalar("SELECT sum(balance) FROM accounts"), 1500)

with psycopg.connect(DSN) as tx:
    tx.execute("SET search_path TO ch16")
    tx.execute("BEGIN")
    tx.execute("UPDATE accounts SET balance=balance+100 WHERE id='B'")
    tx.execute("UPDATE accounts SET balance=balance-100 WHERE id='A'")
    tx.execute("COMMIT")
c.equal("COMMIT 后转账生效", c.scalar("SELECT balance FROM accounts WHERE id='A'"), 400)

with psycopg.connect(DSN) as tx:
    tx.execute("SET search_path TO ch16")
    tx.execute("BEGIN")
    tx.execute("UPDATE accounts SET balance=balance+100 WHERE id='B'")
    tx.execute("ROLLBACK")
c.equal("ROLLBACK 后不变", c.scalar("SELECT balance FROM accounts WHERE id='B'"), 1100)

with psycopg.connect(DSN) as tx:
    tx.execute("SET search_path TO ch16")
    tx.execute("BEGIN")
    tx.execute("UPDATE accounts SET balance=balance-100 WHERE id='A'")
    tx.execute("SAVEPOINT s1")
    tx.execute("UPDATE accounts SET balance=balance-100 WHERE id='A'")
    tx.execute("ROLLBACK TO SAVEPOINT s1")
    tx.execute("COMMIT")
c.equal("ROLLBACK TO SAVEPOINT", c.scalar("SELECT balance FROM accounts WHERE id='A'"), 300)

with psycopg.connect(DSN) as bad:
    bad.execute("SET search_path TO ch16")
    try:
        bad.execute("UPDATE accounts SET balance=-1 WHERE id='A'")
        bad.rollback()
        consistent = False
    except psycopg.errors.CheckViolation:
        consistent = True
c.ok("一致性约束", consistent)

with psycopg.connect(DSN) as tx:
    tx.execute("SET search_path TO ch16")
    tx.execute("BEGIN")
    tx.execute("UPDATE accounts SET balance=balance+1 WHERE id='B'")
    hidden = c.scalar("SELECT balance FROM accounts WHERE id='B'")
    tx.execute("ROLLBACK")
c.equal("隔离性：未提交不可见", hidden, 1100)

with psycopg.connect(DSN) as tx:
    tx.execute("SET search_path TO ch16")
    tx.execute("BEGIN")
    tx.execute("UPDATE accounts SET balance=balance+1 WHERE id='B'")
    tx.execute("COMMIT")
c.equal("持久性：提交后可见", c.scalar("SELECT balance FROM accounts WHERE id='B'"), 1101)

c.sql("INSERT INTO accounts VALUES ('C','王五',100)")
c.equal("单语句自动事务", c.scalar("SELECT count(*) FROM accounts"), 3)

pid = c.scalar("SELECT pg_backend_pid()")
c.ok("backend pid 可查", isinstance(pid, int) and pid > 0, str(pid))

isolation = c.scalar("SHOW transaction_isolation")
c.equal("默认隔离级别", isolation, "read committed")

raise SystemExit(c.finish())
