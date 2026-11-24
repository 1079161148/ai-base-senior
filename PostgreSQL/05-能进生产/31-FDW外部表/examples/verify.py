"""第 31 章 · postgres_fdw：像查本地表一样查外部库。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(31)
c.sql("CREATE TABLE local_source (id INT PRIMARY KEY, name TEXT)")
c.sql("INSERT INTO local_source VALUES (1,'外部数据A'), (2,'外部数据B')")

c.sql("CREATE EXTENSION IF NOT EXISTS postgres_fdw")
c.ok("扩展已安装", c.scalar("SELECT count(*) FROM pg_extension WHERE extname='postgres_fdw'") == 1)

c.sql("""
CREATE SERVER loopback FOREIGN DATA WRAPPER postgres_fdw
OPTIONS (host '127.0.0.1', port '5432', dbname 'study');
""")
c.ok("SERVER 创建", c.scalar("SELECT count(*) FROM pg_foreign_server WHERE srvname='loopback'") == 1)

c.sql("""
CREATE USER MAPPING FOR admin SERVER loopback
OPTIONS (user 'admin', password 'study123');
""")
c.equal("USER MAPPING", c.scalar("SELECT count(*) FROM pg_user_mappings WHERE srvname='loopback'"), 1)

c.sql("""
CREATE FOREIGN TABLE remote_source (id INT, name TEXT) SERVER loopback
OPTIONS (schema_name 'ch31', table_name 'local_source');
""")
remote = c.rows("SELECT id,name FROM remote_source ORDER BY id")
c.equal("外部表查询", remote, [(1, "外部数据A"), (2, "外部数据B")])

joined = c.rows("""
SELECT l.id, r.name FROM local_source l JOIN remote_source r ON l.id=r.id ORDER BY l.id
""")
c.equal("本地表 JOIN 外部表", len(joined), 2)

imported = c.rows("""
SELECT count(*) FROM postgres_fdw_get_connections()
""")
c.ok("连接可查", imported[0][0] >= 0, str(imported[0][0]))

c.sql("IMPORT FOREIGN SCHEMA ch31 LIMIT TO (local_source) FROM SERVER loopback INTO public")
c.equal("IMPORT FOREIGN SCHEMA", c.scalar("""
SELECT count(*) FROM pg_foreign_table ft JOIN pg_class c ON c.oid=ft.ftrelid
WHERE c.relname='local_source'
""") >= 1, True)

wrappers = c.rows("SELECT fdwname FROM pg_foreign_data_wrapper")
c.ok("FDW 元数据", "postgres_fdw" in [r[0] for r in wrappers], str(wrappers))

c.sql("DROP FOREIGN TABLE remote_source")
c.sql("DROP FOREIGN TABLE IF EXISTS public.local_source")
c.sql("DROP USER MAPPING FOR admin SERVER loopback")
c.sql("DROP SERVER loopback")
c.ok("清理完成", c.scalar("SELECT count(*) FROM pg_foreign_server WHERE srvname='loopback'") == 0)

raise SystemExit(c.finish())
