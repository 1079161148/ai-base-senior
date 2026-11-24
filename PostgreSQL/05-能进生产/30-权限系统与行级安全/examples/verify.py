"""第 30 章 · 角色、GRANT/REVOKE、行级安全 RLS。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

import psycopg  # noqa: E402

from common import DSN, Checker  # noqa: E402

c = Checker(30)
c.sql("""
CREATE TABLE salary_data (id SERIAL PRIMARY KEY, dept TEXT, name TEXT, amount NUMERIC(10,2));
INSERT INTO salary_data (dept,name,amount) VALUES ('研发','张三',100),('销售','李四',200);
DROP ROLE IF EXISTS r30_reader;
DROP ROLE IF EXISTS r30_rls;
CREATE ROLE r30_reader LOGIN PASSWORD 'reader123';
CREATE ROLE r30_rls LOGIN PASSWORD 'rls123';
""")

c.ok("角色已创建", c.scalar("SELECT count(*) FROM pg_roles WHERE rolname LIKE 'r30_%'") == 2)

with c.conn.cursor() as cur:
    cur.execute("GRANT USAGE ON SCHEMA ch30 TO r30_reader")
    cur.execute("GRANT SELECT ON salary_data TO r30_reader")
c.ok("GRANT 生效", c.scalar("SELECT has_table_privilege('r30_reader','ch30.salary_data','SELECT')"))

with c.conn.cursor() as cur:
    cur.execute("REVOKE SELECT ON salary_data FROM r30_reader")
c.ok("REVOKE 生效", not c.scalar("SELECT has_table_privilege('r30_reader','ch30.salary_data','SELECT')"))

c.sql("GRANT SELECT (name) ON salary_data TO r30_reader")
c.ok("列级权限", c.scalar("SELECT has_column_privilege('r30_reader','ch30.salary_data','name','SELECT')"))

with psycopg.connect(DSN) as conn:
    with conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("SET LOCAL ROLE r30_reader")
        denied = False
        try:
            cur.execute("SELECT amount FROM ch30.salary_data")
        except psycopg.Error:
            denied = True
        conn.rollback()
c.ok("无权限列被拒绝", denied)

c.sql("""
GRANT SELECT ON salary_data TO r30_rls;
GRANT USAGE ON SCHEMA ch30 TO r30_rls;
ALTER TABLE salary_data ENABLE ROW LEVEL SECURITY;
CREATE POLICY dept_isolation ON salary_data
  FOR SELECT TO r30_rls USING (dept = '研发');
""")
c.ok("RLS 已启用", c.scalar("SELECT relrowsecurity FROM pg_class WHERE oid='salary_data'::regclass"))

with psycopg.connect(DSN) as conn:
    with conn.cursor() as cur:
        cur.execute("BEGIN")
        cur.execute("SET LOCAL ROLE r30_rls")
        visible = cur.execute("SELECT count(*) FROM ch30.salary_data").fetchone()[0]
        conn.rollback()
c.equal("策略限制可见行", visible, 1)

policies = c.rows("SELECT polname FROM pg_policy WHERE polrelid='salary_data'::regclass")
c.equal("策略元数据", [r[0] for r in policies], ["dept_isolation"])

c.sql("ALTER TABLE salary_data DISABLE ROW LEVEL SECURITY")
c.ok("RLS 可关闭", not c.scalar("SELECT relrowsecurity FROM pg_class WHERE oid='salary_data'::regclass"))

c.sql("DROP OWNED BY r30_reader CASCADE")
c.sql("DROP OWNED BY r30_rls CASCADE")
c.sql("DROP ROLE r30_reader")
c.sql("DROP ROLE r30_rls")
c.ok("角色清理完成", c.scalar("SELECT count(*) FROM pg_roles WHERE rolname LIKE 'r30_%'") == 0)

raise SystemExit(c.finish())
