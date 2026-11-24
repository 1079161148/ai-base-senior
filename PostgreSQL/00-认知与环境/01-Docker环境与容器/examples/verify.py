"""第 01 章 · Docker 环境：确认版本、端口、目录、权限。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(1)

version = c.scalar("SHOW server_version")
c.ok("镜像是 PostgreSQL 16", version.startswith("16."), version)

data_dir = c.scalar("SHOW data_directory")
c.ok("数据目录已挂载", "/var/lib/postgresql/data" in data_dir, data_dir)

c.equal("服务端编码", c.scalar("SHOW server_encoding"), "UTF8")

timezone = c.scalar("SHOW TimeZone")
c.ok("时区可查", bool(timezone), timezone)

max_conn = int(c.scalar("SHOW max_connections"))
c.ok("连接数上限有效", max_conn >= 100, str(max_conn))

roles = c.rows("SELECT rolname FROM pg_roles WHERE rolcanlogin ORDER BY 1")
c.ok("admin 角色存在", ("admin",) in roles, str(roles))

c.sql("CREATE TABLE write_probe (id int PRIMARY KEY, note text)")
c.sql("INSERT INTO write_probe VALUES (1, '可写')")
c.equal("写权限正常", c.scalar("SELECT note FROM write_probe WHERE id = 1"), "可写")

databases = [row[0] for row in c.rows("SELECT datname FROM pg_database WHERE datistemplate = false")]
c.ok("study 库存在", "study" in databases, str(databases))

raise SystemExit(c.finish())
