"""第 27 章 · 视图与物化视图。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(27)
c.sql("CREATE TABLE employee (id SERIAL PRIMARY KEY, name TEXT, dept TEXT, salary NUMERIC(10,2))")
c.sql("INSERT INTO employee (name,dept,salary) VALUES ('张三','研发',10000),('李四','研发',12000),('王五','销售',8000)")

c.sql("CREATE VIEW v_research AS SELECT id,name,salary FROM employee WHERE dept='研发'")
c.equal("视图查询", [r[1] for r in c.rows("SELECT * FROM v_research ORDER BY id")], ["张三", "李四"])

c.sql("UPDATE v_research SET salary=salary+100 WHERE name='张三'")
c.equal("简单视图可更新", c.scalar("SELECT salary FROM employee WHERE name='张三'"), 10100)

c.sql("CREATE MATERIALIZED VIEW mv_dept AS SELECT dept, count(*) n, sum(salary) total FROM employee GROUP BY dept")
c.equal("物化视图有数据", c.scalar("SELECT count(*) FROM mv_dept"), 2)

c.sql("INSERT INTO employee (name,dept,salary) VALUES ('赵六','研发',9000)")
c.equal("物化视图不自动更新", c.scalar("SELECT n FROM mv_dept WHERE dept='研发'"), 2)

c.sql("REFRESH MATERIALIZED VIEW mv_dept")
c.equal("REFRESH 后更新", c.scalar("SELECT n FROM mv_dept WHERE dept='研发'"), 3)

c.equal("总薪资正确", c.scalar("SELECT total FROM mv_dept WHERE dept='研发'"), 31100)

c.sql("CREATE UNIQUE INDEX idx_mv_dept ON mv_dept(dept)")
c.sql("REFRESH MATERIALIZED VIEW CONCURRENTLY mv_dept")
c.ok("CONCURRENTLY 刷新", c.scalar("SELECT count(*) FROM mv_dept") == 2)

views = c.rows("SELECT viewname FROM pg_views WHERE schemaname='ch27' ORDER BY 1")
c.equal("视图元数据", [r[0] for r in views], ["v_research"])

mviews = c.rows("SELECT matviewname FROM pg_matviews WHERE schemaname='ch27'")
c.equal("物化视图元数据", [r[0] for r in mviews], ["mv_dept"])

c.sql("CREATE VIEW v_checked AS SELECT * FROM employee WHERE dept='研发' WITH CHECK OPTION")
checked_failed = False
try:
    c.sql("INSERT INTO v_checked (name,dept,salary) VALUES ('违规','销售',1)")
except Exception:
    checked_failed = True
c.ok("WITH CHECK OPTION 拦截", checked_failed)

c.sql("DROP VIEW v_checked")
c.sql("DROP MATERIALIZED VIEW mv_dept")
c.ok("DROP 成功", c.scalar("SELECT to_regclass('mv_dept') IS NULL"))

raise SystemExit(c.finish())
