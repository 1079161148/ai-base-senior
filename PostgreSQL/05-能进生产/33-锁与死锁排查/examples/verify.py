"""第 33 章 · 锁与死锁排查。"""

import sys
import threading
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

import psycopg  # noqa: E402

from common import DSN, Checker  # noqa: E402

c = Checker(33)
c.sql("""
CREATE TABLE accounts (id INT PRIMARY KEY, name TEXT, balance NUMERIC(10,2));
INSERT INTO accounts VALUES (1,'甲',1000),(2,'乙',1000);
""")

locks_view = c.rows("SELECT pid FROM pg_locks LIMIT 0")
c.ok("pg_locks 可查", locks_view == [], str(locks_view))

timeout = c.scalar("SHOW deadlock_timeout")
c.ok("死锁检测超时可查", "ms" in timeout or "s" in timeout, timeout)

c.sql("SELECT pg_advisory_lock(3301)")
advisory = c.scalar("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND pid=pg_backend_pid()")
c.ok("咨询锁可获取", advisory >= 1, str(advisory))
c.sql("SELECT pg_advisory_unlock(3301)")
released = c.scalar("SELECT count(*) FROM pg_locks WHERE locktype='advisory' AND pid=pg_backend_pid()")
c.ok("咨询锁可释放", released == 0, str(released))

with psycopg.connect(DSN) as holder:
    with holder.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("UPDATE ch33.accounts SET balance=balance+100 WHERE id=1")
        holder_pid = cur.execute("SELECT pg_backend_pid()").fetchone()[0]
        tx_locks = c.rows("""
        SELECT locktype, mode FROM pg_locks
        WHERE pid=%s AND locktype IN ('transactionid','virtualxid')
        """, (holder_pid,))
        c.ok("UPDATE 事务持有事务锁", len(tx_locks) >= 1, str(tx_locks[:3]))
        relation_locks = c.rows("""
        SELECT mode, granted FROM pg_locks
        WHERE relation='ch33.accounts'::regclass AND locktype='relation' AND pid <> pg_backend_pid()
        """)
        c.ok("UPDATE 持有表级 RowExclusiveLock",
             any(r[0] == "RowExclusiveLock" and r[1] for r in relation_locks), str(relation_locks[:3]))

        blocked = {}

        def try_blocked() -> None:
            try:
                with psycopg.connect(DSN) as conn2:
                    with conn2.cursor() as cur2:
                        cur2.execute("SET statement_timeout='3s'")
                        cur2.execute("UPDATE ch33.accounts SET balance=balance+2 WHERE id=1")
                blocked["ok"] = True
            except psycopg.Error as exc:
                blocked["error"] = type(exc).__name__

        worker = threading.Thread(target=try_blocked)
        worker.start()
        time.sleep(0.5)
        waiters = c.rows("""
        SELECT pid, pg_blocking_pids(pid) AS blockers
        FROM pg_stat_activity
        WHERE wait_event_type='Lock' AND datname='study' AND pid <> pg_backend_pid()
        """)
        c.ok("可定位锁等待者", len(waiters) >= 1 and len(waiters[0][1]) >= 1, str(waiters))
        worker.join(timeout=6)
        c.ok("超时后阻塞解除", blocked.get("error") == "QueryCanceled", str(blocked))
        holder.rollback()

barrier = threading.Barrier(2)
results: dict[str, str] = {}


def tx_a() -> None:
    try:
        with psycopg.connect(DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE ch33.accounts SET balance=balance+1 WHERE id=1")
                barrier.wait(timeout=5)
                cur.execute("UPDATE ch33.accounts SET balance=balance+1 WHERE id=2")
            conn.commit()
        results["a"] = "ok"
    except psycopg.Error as exc:
        results["a"] = type(exc).__name__


def tx_b() -> None:
    try:
        with psycopg.connect(DSN) as conn:
            with conn.cursor() as cur:
                cur.execute("UPDATE ch33.accounts SET balance=balance+1 WHERE id=2")
                barrier.wait(timeout=5)
                cur.execute("UPDATE ch33.accounts SET balance=balance+1 WHERE id=1")
            conn.commit()
        results["b"] = "ok"
    except psycopg.Error as exc:
        results["b"] = type(exc).__name__


thread_a = threading.Thread(target=tx_a)
thread_b = threading.Thread(target=tx_b)
thread_a.start()
thread_b.start()
thread_a.join(timeout=10)
thread_b.join(timeout=10)

c.ok("死锁被自动检测并终止一方", "DeadlockDetected" in results.values(), str(results))
c.ok("死锁后另一方提交成功", "ok" in results.values(), str(results))
c.ok("死锁后数据仍一致", c.scalar("SELECT count(*) FROM ch33.accounts") == 2)
balances = c.rows("SELECT id,balance FROM ch33.accounts ORDER BY id")
c.ok("提交一方事务完整生效", [int(r[1]) for r in balances] == [1001, 1001], str(balances))

raise SystemExit(c.finish())
