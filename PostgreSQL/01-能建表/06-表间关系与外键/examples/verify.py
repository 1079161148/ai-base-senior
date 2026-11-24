"""第 06 章 · 表间关系：1:1 / 1:N / M:N 与外键行为。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import DSN, Checker  # noqa: E402
import psycopg  # noqa: E402

c = Checker(6)

c.sql("CREATE TABLE users (id SERIAL PRIMARY KEY, username TEXT NOT NULL)")
c.sql("""
CREATE TABLE profiles (
    id SERIAL PRIMARY KEY,
    user_id INT UNIQUE NOT NULL REFERENCES users(id),
    bio TEXT
)
""")
c.sql("INSERT INTO users (username) VALUES ('alice'), ('bob')")
c.sql("INSERT INTO profiles (user_id, bio) VALUES (1, 'hi')")
c.ok("1:1 建表", c.scalar("SELECT count(*) FROM profiles") == 1)

with psycopg.connect(DSN) as bad:
    bad.execute("SET search_path TO ch06")
    try:
        bad.execute("INSERT INTO profiles (user_id) VALUES (1)")
        bad.rollback()
        one_to_one_ok = False
    except psycopg.errors.UniqueViolation:
        one_to_one_ok = True
c.ok("1:1 UNIQUE 拒绝第二条", one_to_one_ok)

c.sql("CREATE TABLE departments (id SERIAL PRIMARY KEY, name TEXT)")
c.sql("""
CREATE TABLE employees (
    id SERIAL PRIMARY KEY,
    name TEXT,
    dept_id INT REFERENCES departments(id)
)
""")
c.sql("INSERT INTO departments (name) VALUES ('研发')")
c.sql("INSERT INTO employees (name, dept_id) VALUES ('张三',1), ('李四',1)")
c.equal("1:N 多个子行指向同一父行", c.scalar("SELECT count(*) FROM employees WHERE dept_id=1"), 2)

with psycopg.connect(DSN) as bad:
    bad.execute("SET search_path TO ch06")
    try:
        bad.execute("INSERT INTO employees (name, dept_id) VALUES ('脏',999)")
        bad.rollback()
        fk_ok = False
    except psycopg.errors.ForeignKeyViolation:
        fk_ok = True
c.ok("外键拒绝孤儿行", fk_ok)

c.sql("CREATE TABLE courses (id SERIAL PRIMARY KEY, title TEXT)")
c.sql("""
CREATE TABLE enrollments (
    student_id INT REFERENCES users(id),
    course_id INT REFERENCES courses(id),
    enroll_date DATE,
    PRIMARY KEY (student_id, course_id)
)
""")
c.sql("INSERT INTO courses (title) VALUES ('SQL'), ('PG')")
c.sql("INSERT INTO enrollments VALUES (1,1,'2026-01-01'), (1,2,'2026-02-01'), (2,1,'2026-03-01')")
c.equal("M:N 中间表", c.scalar("SELECT count(*) FROM enrollments"), 3)
c.ok("中间表附加属性", c.scalar("SELECT enroll_date FROM enrollments WHERE student_id=1 AND course_id=2").isoformat() == "2026-02-01")

fks = c.rows(
    "SELECT count(*) FROM pg_constraint WHERE contype='f' AND connamespace='ch06'::regnamespace"
)
c.equal("外键元数据", fks[0][0], 4)

c.sql("CREATE TABLE parent_cascade (id SERIAL PRIMARY KEY)")
c.sql("CREATE TABLE child_cascade (id SERIAL PRIMARY KEY, pid INT REFERENCES parent_cascade(id) ON DELETE CASCADE)")
c.sql("INSERT INTO parent_cascade DEFAULT VALUES")
c.sql("INSERT INTO child_cascade (pid) VALUES (1)")
c.sql("DELETE FROM parent_cascade WHERE id=1")
c.equal("ON DELETE CASCADE", c.scalar("SELECT count(*) FROM child_cascade"), 0)

c.sql("CREATE TABLE parent_setnull (id SERIAL PRIMARY KEY)")
c.sql("CREATE TABLE child_setnull (id SERIAL PRIMARY KEY, pid INT REFERENCES parent_setnull(id) ON DELETE SET NULL)")
c.sql("INSERT INTO parent_setnull DEFAULT VALUES")
c.sql("INSERT INTO child_setnull (pid) VALUES (1)")
c.sql("DELETE FROM parent_setnull WHERE id=1")
c.ok("ON DELETE SET NULL", c.scalar("SELECT pid FROM child_setnull") is None)

c.sql("CREATE TABLE parent_restrict (id SERIAL PRIMARY KEY)")
c.sql("CREATE TABLE child_restrict (id SERIAL PRIMARY KEY, pid INT REFERENCES parent_restrict(id) ON DELETE RESTRICT)")
c.sql("INSERT INTO parent_restrict DEFAULT VALUES")
c.sql("INSERT INTO child_restrict (pid) VALUES (1)")
with psycopg.connect(DSN) as bad:
    bad.execute("SET search_path TO ch06")
    try:
        bad.execute("DELETE FROM parent_restrict WHERE id=1")
        bad.rollback()
        restrict_ok = False
    except psycopg.errors.ForeignKeyViolation:
        restrict_ok = True
c.ok("ON DELETE RESTRICT 阻止删除", restrict_ok)

raise SystemExit(c.finish())
