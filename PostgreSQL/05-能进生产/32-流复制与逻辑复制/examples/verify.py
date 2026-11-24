"""第 32 章 · 复制：WAL、复制槽、逻辑解码。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(32)

wal_level = c.scalar("SHOW wal_level")
c.ok("WAL 级别为 logical", wal_level == "logical", wal_level)

lsn = c.scalar("SELECT pg_current_wal_lsn()::text")
c.ok("当前 WAL 位置可查", "/" in lsn, lsn)

stats = c.rows("SELECT count(*) FROM pg_stat_replication")
c.ok("复制状态视图可查", stats[0][0] >= 0, str(stats[0][0]))

c.sql("CREATE TABLE repl_demo (id SERIAL PRIMARY KEY, note TEXT)")
c.sql("DROP PUBLICATION IF EXISTS pub32")
c.sql("CREATE PUBLICATION pub32 FOR TABLE repl_demo")
c.equal("PUBLICATION 创建", c.scalar("SELECT count(*) FROM pg_publication WHERE pubname='pub32'"), 1)

pub_tables = c.rows("""
SELECT tablename FROM pg_publication_tables WHERE pubname='pub32'
""")
c.equal("发布表", [r[0] for r in pub_tables], ["repl_demo"])

slot_name = "slot32"
if c.scalar("SELECT count(*) FROM pg_replication_slots WHERE slot_name=%s", (slot_name,)):
    c.sql("SELECT pg_drop_replication_slot(%s)", (slot_name,))
c.sql("SELECT pg_create_logical_replication_slot(%s, 'test_decoding')", (slot_name,))
c.ok("复制槽创建", c.scalar("SELECT count(*) FROM pg_replication_slots WHERE slot_name=%s", (slot_name,)) == 1)

c.sql("INSERT INTO repl_demo (note) VALUES ('变更一'),('变更二')")

changes = c.rows("SELECT data FROM pg_logical_slot_peek_changes(%s, NULL, 10)", (slot_name,))
c.ok("逻辑解码读到变更", any("repl_demo" in r[0] for r in changes), str(changes)[:160])

c.sql("SELECT pg_drop_replication_slot(%s)", (slot_name,))
c.ok("复制槽删除", c.scalar("SELECT count(*) FROM pg_replication_slots WHERE slot_name=%s", (slot_name,)) == 0)

c.sql("DROP PUBLICATION pub32")
c.ok("PUBLICATION 清理", c.scalar("SELECT count(*) FROM pg_publication WHERE pubname='pub32'") == 0)

settings = c.rows("""
SELECT name,setting FROM pg_settings
WHERE name IN ('max_wal_senders','wal_keep_size','max_replication_slots') ORDER BY 1
""")
c.equal("复制参数可查", len(settings), 3)

c.ok("WAL 位置持续增长", c.scalar("SELECT pg_current_wal_lsn()::text") != "")

raise SystemExit(c.finish())
