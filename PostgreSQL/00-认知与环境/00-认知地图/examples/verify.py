"""第 00 章 · 认知地图：先证明「连得上、看得到、隔离得住」。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(0)

c.ok("连上 PostgreSQL", c.scalar("SELECT 1") == 1)

version = c.scalar("SHOW server_version")
major = int(version.split(".")[0])
c.ok("主版本 16", major == 16, version)

c.equal("当前库", c.scalar("SELECT current_database()"), "study")
c.equal("当前用户", c.scalar("SELECT current_user"), "admin")

databases = c.rows("SELECT datname FROM pg_database WHERE datistemplate = false ORDER BY 1")
c.ok("能看到用户数据库", "study" in [row[0] for row in databases], str(databases))

schema = c.scalar("SELECT current_schema()")
c.equal("schema 隔离", schema, "ch00")

settings = c.rows(
    "SELECT name, setting FROM pg_settings WHERE name IN ('max_connections','server_encoding') ORDER BY 1"
)
c.ok("关键参数可查", len(settings) == 2, str(settings))

extensions = c.rows(
    "SELECT name FROM pg_available_extensions WHERE name IN ('pgvector','plpgsql') ORDER BY 1"
)
c.ok("扩展机制可见", ("plpgsql",) in extensions, str(extensions))

c.sql("CREATE TABLE isolation_probe (id int)")
c.equal("本章建表落在独立 schema", c.scalar("SELECT count(*) FROM ch00.isolation_probe"), 0)

raise SystemExit(c.finish())
