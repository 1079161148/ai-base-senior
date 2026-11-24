"""第 19 章 · UPDATE / DELETE / RETURNING / UPDATE FROM。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(19)
c.sql("""
CREATE TABLE people (id SERIAL PRIMARY KEY, name TEXT, age INT, score NUMERIC(5,2));
INSERT INTO people (name,age,score) VALUES ('张三',22,80),('李四',25,90),('王五',19,70);
CREATE TABLE exam (name TEXT, score NUMERIC(5,2));
INSERT INTO exam VALUES ('张三',95),('李四',88);
""")

c.sql("UPDATE people SET score=98 WHERE name='张三'")
c.equal("单列更新", c.scalar("SELECT score FROM people WHERE name='张三'"), 98)

c.sql("UPDATE people SET age=23, score=99 WHERE name='张三'")
c.equal("多列更新", c.rows("SELECT age,score FROM people WHERE name='张三'"), [(23, 99)])

c.sql("UPDATE people SET score=score+5 WHERE age<20")
c.equal("表达式更新", c.scalar("SELECT score FROM people WHERE name='王五'"), 75)

returned = c.scalar("UPDATE people SET score=100 WHERE name='李四' RETURNING score")
c.equal("UPDATE RETURNING", returned, 100)

c.sql("UPDATE people p SET score=e.score FROM exam e WHERE p.name=e.name")
c.equal("UPDATE FROM 跨表", c.scalar("SELECT score FROM people WHERE name='张三'"), 95)

multi = c.rows("UPDATE people SET age=age+1 WHERE age>=20 RETURNING name, age")
c.equal("多行 RETURNING", sorted(r[0] for r in multi), ["张三", "李四"])

deleted = c.scalar("DELETE FROM people WHERE name='王五' RETURNING name")
c.equal("DELETE RETURNING", deleted, "王五")

c.equal("DELETE 后行数", c.scalar("SELECT count(*) FROM people"), 2)

c.sql("DELETE FROM people")
c.equal("不带 WHERE 清空", c.scalar("SELECT count(*) FROM people"), 0)

c.sql("INSERT INTO people (name,age,score) VALUES ('新学生',20,60)")
c.equal("DELETE 不重置序列", c.scalar("SELECT id FROM people"), 4)

c.sql("TRUNCATE TABLE people RESTART IDENTITY")
c.sql("INSERT INTO people (name,age,score) VALUES ('重新开始',20,60)")
c.equal("TRUNCATE 重置序列", c.scalar("SELECT id FROM people"), 1)

updated = c.scalar("""
UPDATE people SET score=(SELECT avg(score) FROM exam) WHERE name='重新开始' RETURNING score
""")
c.ok("子查询更新", float(updated) == 91.5, str(updated))

raise SystemExit(c.finish())
