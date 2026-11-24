"""第 08 章 · INSERT：多行、RETURNING、ON CONFLICT。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker, setup_shop  # noqa: E402

c = Checker(8)
setup_shop(c)

c.sql("CREATE TABLE insert_demo (id SERIAL PRIMARY KEY, name TEXT, age INT, score NUMERIC(5,2) DEFAULT 0)")
c.sql("INSERT INTO insert_demo (name, age) VALUES ('张三', 22)")
c.ok("单行插入", c.scalar("SELECT count(*) FROM insert_demo") == 1)

c.sql("INSERT INTO insert_demo (name, age) VALUES ('李四',23), ('王五',24)")
c.equal("多行插入", c.scalar("SELECT count(*) FROM insert_demo"), 3)

c.sql("INSERT INTO insert_demo (name) VALUES ('赵六')")
row = c.rows("SELECT age, score FROM insert_demo WHERE name='赵六'")[0]
c.ok("省略列用默认值/NULL", row[0] is None and str(row[1]) == "0.00", str(row))

c.sql("CREATE TABLE backup_students (name TEXT, age INT)")
c.sql("INSERT INTO backup_students VALUES ('钱七', 25)")
c.sql("INSERT INTO insert_demo (name, age) SELECT name, age FROM backup_students WHERE age > 18")
c.ok("INSERT ... SELECT", c.scalar("SELECT count(*) FROM insert_demo WHERE name='钱七'") == 1)

inserted = c.scalar("INSERT INTO insert_demo (name, age) VALUES ('孙八',26) RETURNING id")
c.ok("RETURNING 返回主键", isinstance(inserted, int) and inserted > 0, str(inserted))

c.sql("ALTER TABLE insert_demo ADD CONSTRAINT name_unique UNIQUE (name)")
c.sql("""
INSERT INTO insert_demo (name, age) VALUES ('张三', 99)
ON CONFLICT (name) DO UPDATE SET age = EXCLUDED.age
""")
c.equal("ON CONFLICT DO UPDATE", c.scalar("SELECT age FROM insert_demo WHERE name='张三'"), 99)

c.sql("""
INSERT INTO insert_demo (name, age) VALUES ('张三', 100)
ON CONFLICT (name) DO NOTHING
""")
c.equal("ON CONFLICT DO NOTHING", c.scalar("SELECT age FROM insert_demo WHERE name='张三'"), 99)

updated = c.scalar("""
INSERT INTO insert_demo (name, age) VALUES ('张三', 101)
ON CONFLICT (name) DO UPDATE SET age = EXCLUDED.age RETURNING age
""")
c.equal("UPSERT 也能 RETURNING", updated, 101)

raise SystemExit(c.finish())
