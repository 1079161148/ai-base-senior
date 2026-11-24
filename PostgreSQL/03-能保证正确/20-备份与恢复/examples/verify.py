"""第 20 章 · 备份与恢复：CTAS、COPY、事务回滚。"""

import sys
from io import StringIO
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import DSN, Checker  # noqa: E402
import psycopg  # noqa: E402

c = Checker(20)
c.sql("CREATE TABLE src (id INT PRIMARY KEY, name TEXT, note TEXT)")
c.sql("INSERT INTO src SELECT g, '名称'||g, repeat('x', 100) FROM generate_series(1,50) g")

c.sql("CREATE TABLE backup_ctas AS TABLE src")
c.equal("CTAS 备份行数", c.scalar("SELECT count(*) FROM backup_ctas"), 50)

c.sql("DELETE FROM src WHERE id <= 20")
c.equal("模拟数据丢失", c.scalar("SELECT count(*) FROM src"), 30)

c.sql("INSERT INTO src SELECT * FROM backup_ctas ON CONFLICT (id) DO NOTHING")
c.equal("从 CTAS 恢复", c.scalar("SELECT count(*) FROM src"), 50)

buffer = StringIO()
with c.conn.cursor() as cur:
    with cur.copy("COPY (SELECT id,name FROM src ORDER BY id) TO STDOUT WITH CSV") as copy:
        for chunk in copy:
            buffer.write(bytes(chunk).decode("utf-8"))
csv_data = buffer.getvalue()
c.ok("COPY 导出", len(csv_data.splitlines()) == 50 and "1,名称1" in csv_data, f"{len(csv_data)} 字节")

c.sql("CREATE TABLE restored (id INT, name TEXT)")
with c.conn.cursor() as cur:
    with cur.copy("COPY restored (id,name) FROM STDIN WITH CSV") as copy:
        copy.write(csv_data)
c.equal("COPY 导入", c.scalar("SELECT count(*) FROM restored"), 50)
c.equal("COPY 内容一致", c.scalar("SELECT name FROM restored WHERE id=25"), "名称25")

with psycopg.connect(DSN) as tx:
    tx.execute("SET search_path TO ch20")
    tx.execute("BEGIN")
    tx.execute("TRUNCATE TABLE restored")
    tx.execute("ROLLBACK")
c.equal("TRUNCATE 可回滚", c.scalar("SELECT count(*) FROM restored"), 50)

c.sql("CREATE TABLE snapshot (n INT, at TIMESTAMPTZ DEFAULT now())")
c.sql("INSERT INTO snapshot (n) SELECT count(*) FROM src")
c.ok("备份时间点记录", c.scalar("SELECT at IS NOT NULL FROM snapshot"))

with psycopg.connect(DSN) as tx:
    tx.execute("SET search_path TO ch20")
    tx.execute("BEGIN")
    tx.execute("CREATE TABLE ddl_in_tx (id int)")
    tx.execute("ROLLBACK")
c.ok("DDL 也可回滚", c.scalar("SELECT to_regclass('ddl_in_tx') IS NULL"))

c.sql("DROP TABLE backup_ctas, restored, snapshot")
c.ok("清理备份表", c.scalar("SELECT to_regclass('backup_ctas') IS NULL"))

raise SystemExit(c.finish())
