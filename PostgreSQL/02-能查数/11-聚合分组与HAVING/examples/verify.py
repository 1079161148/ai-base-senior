"""第 11 章 · 聚合函数、GROUP BY、HAVING。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker, setup_shop  # noqa: E402

c = Checker(11)
setup_shop(c)

c.equal("COUNT(*)", c.scalar("SELECT count(*) FROM users"), 4)
c.equal("COUNT(列) 排除 NULL", c.scalar("SELECT count(phone) FROM user_profiles"), 2)

stats = c.rows("SELECT sum(price), avg(price), max(price), min(price) FROM skus")[0]
c.ok("SUM/AVG/MAX/MIN", stats[0] > stats[2] >= stats[1] >= stats[3], str(stats))

grouped = c.rows("SELECT brand_id, count(*) FROM skus s JOIN products p ON s.product_id=p.id GROUP BY brand_id ORDER BY brand_id")
c.equal("GROUP BY", grouped, [(1, 3), (2, 3), (3, 2)])

having = c.rows("""
SELECT p.brand_id, count(*) FROM skus s JOIN products p ON s.product_id=p.id
GROUP BY p.brand_id HAVING count(*) >= 2 ORDER BY 1
""")
c.equal("HAVING 分组后过滤", len(having), 3)

no_match = c.rows("""
SELECT p.brand_id, count(*) FROM skus s JOIN products p ON s.product_id=p.id
GROUP BY p.brand_id HAVING count(*) > 10
""")
c.equal("HAVING 零结果", no_match, [])

where_vs_having = c.scalar("""
SELECT count(*) FROM skus WHERE price > 1000
""")
c.equal("WHERE 分组前过滤", where_vs_having, 5)

ordered = c.rows("""
SELECT p.category_id, count(*) AS n FROM skus s JOIN products p ON s.product_id=p.id
GROUP BY p.category_id ORDER BY n DESC, p.category_id
""")
c.ok("分组结果排序", [r[1] for r in ordered] == [5, 2, 1], str(ordered))

two_keys = c.rows("""
SELECT p.category_id, p.brand_id, count(*) FROM skus s JOIN products p ON s.product_id=p.id
GROUP BY 1,2 ORDER BY 1,2
""")
c.equal("多列分组", len(two_keys), 6)

c.equal("COUNT(DISTINCT)", c.scalar("SELECT count(DISTINCT status) FROM orders"), 5)

c.sql("INSERT INTO skus (product_id,sku_code,price,stock) VALUES (1,'FREE',NULL,1)")
c.equal("聚合忽略 NULL", c.scalar("SELECT count(price) FROM skus"), 8)
c.equal("COUNT(*) 计入 NULL 行", c.scalar("SELECT count(*) FROM skus"), 9)

raise SystemExit(c.finish())
