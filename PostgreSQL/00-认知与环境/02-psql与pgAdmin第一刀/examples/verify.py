"""第 02 章 · psql 第一刀：建表、插入、查询、回滚。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(2)

# \l 的 SQL 等价写法
databases = [row[0] for row in c.rows("SELECT datname FROM pg_database ORDER BY 1")]
c.ok("\\l 等价查询", "study" in databases, f"{len(databases)} 个库")

# \conninfo 的 SQL 等价写法
info = c.scalar("SELECT current_user || '@' || current_database()")
c.equal("\\conninfo 等价查询", info, "admin@study")

c.sql("""
-- 带注释的 SQL 也必须能执行
CREATE TABLE first_table (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    created_at TIMESTAMPTZ DEFAULT now()
);
""")
c.ok("CREATE TABLE 成功", c.scalar("SELECT to_regclass('first_table') IS NOT NULL"))

c.sql("INSERT INTO first_table (name) VALUES ('张三'), ('李四')")
c.equal("批量插入", c.scalar("SELECT count(*) FROM first_table"), 2)

columns = c.rows(
    "SELECT column_name FROM information_schema.columns "
    "WHERE table_schema = 'ch02' AND table_name = 'first_table' ORDER BY ordinal_position"
)
c.equal("列元数据", [row[0] for row in columns], ["id", "name", "created_at"])

# 注释与默认值的实际效果
c.equal("SERIAL 自增", c.scalar("SELECT min(id) FROM first_table"), 1)
c.ok("默认值已填", c.scalar("SELECT count(*) FROM first_table WHERE created_at IS NOT NULL") == 2)

# 事务回滚：Checker 是 autocommit，需要独立连接
import psycopg  # noqa: E402
from common import DSN  # noqa: E402

with psycopg.connect(DSN) as rollback_conn:
    rollback_conn.execute("SET search_path TO ch02")
    rollback_conn.execute("INSERT INTO first_table (name) VALUES ('会回滚')")
    rollback_conn.rollback()
c.equal("ROLLBACK 后未落库", c.scalar("SELECT count(*) FROM first_table"), 2)

c.sql("DELETE FROM first_table WHERE name = '李四'")
c.equal("DELETE 生效", c.scalar("SELECT count(*) FROM first_table"), 1)

c.sql("DROP TABLE first_table")
c.ok("DROP TABLE 成功", c.scalar("SELECT to_regclass('first_table') IS NULL"))

raise SystemExit(c.finish())
