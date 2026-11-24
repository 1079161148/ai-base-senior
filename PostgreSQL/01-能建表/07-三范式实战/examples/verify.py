"""第 07 章 · 三范式：从一张乱表拆到 3NF。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(7)

# 1NF 反例：一列存多个电话
c.sql("CREATE TABLE bad_1nf (id SERIAL PRIMARY KEY, name TEXT, phones TEXT)")
c.sql("INSERT INTO bad_1nf (name, phones) VALUES ('张三', '111,222,333')")
c.ok("1NF 反例存在", "," in c.scalar("SELECT phones FROM bad_1nf"))

c.sql("CREATE TABLE good_student (id SERIAL PRIMARY KEY, name TEXT)")
c.sql("CREATE TABLE good_phone (student_id INT REFERENCES good_student(id), phone TEXT, PRIMARY KEY(student_id, phone))")
c.sql("INSERT INTO good_student (name) VALUES ('张三')")
c.sql("INSERT INTO good_phone VALUES (1,'111'), (1,'222'), (1,'333')")
c.equal("1NF 拆分后原子", c.scalar("SELECT count(*) FROM good_phone"), 3)

# 2NF 反例：复合主键下 product_name 只依赖 product_id
c.sql("""
CREATE TABLE bad_2nf (
    order_id INT, product_id INT, product_name TEXT, qty INT,
    PRIMARY KEY (order_id, product_id)
)
""")
c.sql("INSERT INTO bad_2nf VALUES (1, 10, '键盘', 2), (2, 10, '键盘', 1)")
c.equal("2NF 反例冗余", c.scalar("SELECT count(*) FROM bad_2nf WHERE product_name='键盘'"), 2)

c.sql("CREATE TABLE product (id INT PRIMARY KEY, name TEXT)")
c.sql("CREATE TABLE order_item (order_id INT, product_id INT, qty INT, PRIMARY KEY(order_id, product_id))")
c.sql("INSERT INTO product VALUES (10,'键盘')")
c.sql("INSERT INTO order_item VALUES (1,10,2), (2,10,1)")
c.equal("2NF 拆分后不冗余", c.scalar("SELECT count(*) FROM product WHERE name='键盘'"), 1)

# 3NF 反例：学生表里 dept_name 依赖 dept_id，而 dept_id 依赖主键
c.sql("CREATE TABLE bad_3nf (id SERIAL PRIMARY KEY, name TEXT, dept_id INT, dept_name TEXT)")
c.sql("INSERT INTO bad_3nf (name,dept_id,dept_name) VALUES ('张三',1,'研发'), ('李四',1,'研发')")
c.equal("3NF 反例传递依赖", c.scalar("SELECT count(DISTINCT dept_name) FROM bad_3nf WHERE dept_id=1"), 1)

c.sql("CREATE TABLE dept (id INT PRIMARY KEY, name TEXT)")
c.sql("CREATE TABLE student3 (id SERIAL PRIMARY KEY, name TEXT, dept_id INT REFERENCES dept(id))")
c.sql("INSERT INTO dept VALUES (1,'研发')")
c.sql("INSERT INTO student3 (name,dept_id) VALUES ('张三',1), ('李四',1)")
c.ok("3NF 拆分后无传递依赖",
     "dept_name" not in [r[0] for r in c.rows(
         "SELECT column_name FROM information_schema.columns WHERE table_schema='ch07' AND table_name='student3'")])

joined = c.rows("""
SELECT s.name, d.name FROM student3 s JOIN dept d ON s.dept_id = d.id ORDER BY s.id
""")
c.equal("JOIN 能查回完整信息", joined, [("张三", "研发"), ("李四", "研发")])

c.sql("UPDATE dept SET name='研发中心' WHERE id=1")
c.equal("拆表后只改一处", c.scalar("SELECT count(*) FROM student3 s JOIN dept d ON s.dept_id=d.id WHERE d.name='研发中心'"), 2)

c.sql("UPDATE bad_3nf SET dept_name='研发中心' WHERE dept_id=1")
c.equal("不拆表需改多行", c.scalar("SELECT count(*) FROM bad_3nf WHERE dept_name='研发中心'"), 2)

raise SystemExit(c.finish())
