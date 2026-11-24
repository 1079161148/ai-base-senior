"""第 13 章 · 子查询、EXISTS、CTE、递归 CTE。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker, setup_shop  # noqa: E402

c = Checker(13)
setup_shop(c)

avg_price = c.scalar("SELECT avg(price) FROM skus")
above = c.scalar("SELECT count(*) FROM skus WHERE price > (SELECT avg(price) FROM skus)")
c.ok("标量子查询", above > 0, f"均价={avg_price} 高于均价={above}")

row_match = c.rows("""
SELECT id FROM products WHERE (category_id, brand_id) = (SELECT category_id, brand_id FROM products WHERE id=1)
""")
c.equal("行子查询", [r[0] for r in row_match], [1])

in_sub = c.scalar("""
SELECT count(*) FROM orders WHERE user_id IN (SELECT id FROM users WHERE username IN ('alice','bob'))
""")
c.equal("IN 子查询", in_sub, 4)

c.sql("INSERT INTO orders (user_id,order_no,status,total_amount) VALUES (1,'NULL-USER',NULL,NULL)")
null_in = c.scalar("SELECT count(*) FROM users WHERE id NOT IN (SELECT user_id FROM orders)")
c.equal("NOT IN 遇 NULL 返回空", null_in, 0)

exists_ok = c.scalar("SELECT count(*) FROM users u WHERE EXISTS (SELECT 1 FROM orders o WHERE o.user_id=u.id)")
c.equal("EXISTS", exists_ok, 4)

not_exists = c.rows("SELECT username FROM users u WHERE NOT EXISTS (SELECT 1 FROM user_profiles p WHERE p.user_id=u.id)")
c.equal("NOT EXISTS 找孤儿", [r[0] for r in not_exists], ["carol", "dave"])

from_sub = c.rows("SELECT max(n) FROM (SELECT user_id, count(*) n FROM orders GROUP BY user_id) t")
c.equal("FROM 子查询", from_sub[0][0], 3)

cte = c.rows("""
WITH expensive AS (SELECT id FROM skus WHERE price > 5000)
SELECT count(*) FROM expensive
""")
c.equal("CTE", cte[0][0], 4)

multi_cte = c.rows("""
WITH a AS (SELECT id FROM users WHERE id<=2),
     b AS (SELECT id FROM orders WHERE user_id IN (SELECT id FROM a))
SELECT count(*) FROM b
""")
c.equal("多个 CTE", multi_cte[0][0], 5)

c.sql("""
CREATE TABLE tree (id INT PRIMARY KEY, parent_id INT, name TEXT);
INSERT INTO tree VALUES (1,NULL,'根'),(2,1,'A'),(3,1,'B'),(4,2,'A1'),(5,2,'A2');
""")
recursive = c.rows("""
WITH RECURSIVE t AS (
    SELECT id,parent_id,name,1 AS depth FROM tree WHERE parent_id IS NULL
    UNION ALL
    SELECT c.id,c.parent_id,c.name,t.depth+1 FROM tree c JOIN t ON c.parent_id=t.id
)
SELECT name, depth FROM t ORDER BY depth, name
""")
c.equal("递归 CTE", [r[0] for r in recursive], ["根", "A", "B", "A1", "A2"])

materialized = c.rows("WITH x AS MATERIALIZED (SELECT 1 AS n) SELECT n FROM x")
c.equal("MATERIALIZED", materialized, [(1,)])

not_materialized = c.rows("WITH x AS NOT MATERIALIZED (SELECT 2 AS n) SELECT n FROM x")
c.equal("NOT MATERIALIZED", not_materialized, [(2,)])

raise SystemExit(c.finish())
