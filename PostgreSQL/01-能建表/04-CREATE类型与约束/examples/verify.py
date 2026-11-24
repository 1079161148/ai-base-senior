"""第 04 章 · CREATE：类型、约束、主键。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import DSN, Checker  # noqa: E402
import psycopg  # noqa: E402

c = Checker(4)

c.sql("""
CREATE TABLE students (
    id SERIAL PRIMARY KEY,
    name VARCHAR(50) NOT NULL,
    age INTEGER CHECK (age > 0),
    score NUMERIC(5,2) DEFAULT 0.00,
    email VARCHAR(100) UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    uid UUID DEFAULT gen_random_uuid(),
    profile JSONB DEFAULT '{}'::jsonb
);
""")
c.ok("CREATE TABLE", c.scalar("SELECT to_regclass('students') IS NOT NULL"))

columns = {row[0]: row[1] for row in c.rows(
    "SELECT column_name, data_type FROM information_schema.columns "
    "WHERE table_schema='ch04' AND table_name='students'"
)}
c.equal("INT 类型", columns["age"], "integer")
c.equal("NUMERIC 类型", columns["score"], "numeric")
c.equal("UUID 类型", columns["uid"], "uuid")
c.equal("JSONB 类型", columns["profile"], "jsonb")

c.sql("INSERT INTO students (name, age, email) VALUES ('张三', 22, 'z@example.com')")
row = c.rows("SELECT id, score, uid, profile FROM students")[0]
c.ok("SERIAL 自增", row[0] == 1, str(row[0]))
c.equal("DEFAULT 数值", str(row[1]), "0.00")
c.ok("UUID 自动生成", str(row[2]) != "", str(row[2]))
c.equal("JSONB 默认值", row[3], {})

with psycopg.connect(DSN) as bad:
    bad.execute("SET search_path TO ch04")
    try:
        bad.execute("INSERT INTO students (name, age) VALUES ('坏数据', -1)")
        bad.rollback()
        check_ok = False
    except psycopg.errors.CheckViolation:
        check_ok = True
c.ok("CHECK 生效", check_ok)

with psycopg.connect(DSN) as bad:
    bad.execute("SET search_path TO ch04")
    try:
        bad.execute("INSERT INTO students (name, email) VALUES ('李四', 'z@example.com')")
        bad.rollback()
        unique_ok = False
    except psycopg.errors.UniqueViolation:
        unique_ok = True
c.ok("UNIQUE 生效", unique_ok)

c.sql("""
CREATE TABLE enrollments (
    student_id INT,
    course_id INT,
    PRIMARY KEY (student_id, course_id)
);
""")
c.sql("INSERT INTO enrollments VALUES (1, 10), (1, 11)")
c.equal("复合主键允许部分重复", c.scalar("SELECT count(*) FROM enrollments"), 2)

with psycopg.connect(DSN) as bad:
    bad.execute("SET search_path TO ch04")
    try:
        bad.execute("INSERT INTO enrollments VALUES (1, 10)")
        bad.rollback()
        pk_ok = False
    except psycopg.errors.UniqueViolation:
        pk_ok = True
c.ok("复合主键拒绝完全重复", pk_ok)

raise SystemExit(c.finish())
