"""第 14 章 · UNION 集合运算与窗口函数。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker, setup_shop  # noqa: E402

c = Checker(14)
setup_shop(c)

union = c.rows("SELECT name FROM products WHERE category_id=1 UNION SELECT name FROM products WHERE brand_id=1")
c.equal("UNION 去重", sorted(r[0] for r in union), sorted(["Dell XPS 15", "Mate 60", "SQL 入门", "小米电视"]))

union_all = c.rows("SELECT id FROM orders WHERE user_id=1 UNION ALL SELECT id FROM orders WHERE status='completed'")
c.equal("UNION ALL 保留重复", len(union_all), 5)

inter = c.rows("SELECT name FROM products WHERE category_id=1 INTERSECT SELECT name FROM products WHERE brand_id=1")
c.equal("INTERSECT", [r[0] for r in inter], ["Mate 60"])

except_ = c.rows("SELECT name FROM products WHERE category_id=1 EXCEPT SELECT name FROM products WHERE brand_id=1")
c.equal("EXCEPT", [r[0] for r in except_], ["Dell XPS 15", "小米电视"])

c.sql("INSERT INTO skus (product_id,sku_code,price,stock) VALUES (4,'BOOK-SQL2',89,10)")
ranked = c.rows("""
SELECT sku_code, price,
       row_number() OVER (ORDER BY price),
       rank() OVER (ORDER BY price),
       dense_rank() OVER (ORDER BY price)
FROM skus ORDER BY price, sku_code
""")
price_rows = [r for r in ranked if r[1] == 89]
c.ok("row_number 唯一序号", len({r[2] for r in ranked}) == len(ranked), str(len(ranked)))
c.ok("rank 并列跳号", len({r[3] for r in price_rows}) == 1 and price_rows[0][3] == 1, str(price_rows))
c.ok("dense_rank 并列不跳", max(r[4] for r in ranked) < max(r[3] for r in ranked), str(ranked[-1]))

lag_lead = c.rows("""
SELECT id, lag(id) OVER (ORDER BY id), lead(id) OVER (ORDER BY id)
FROM skus ORDER BY id LIMIT 3
""")
c.equal("lag/lead", lag_lead, [(1, None, 2), (2, 1, 3), (3, 2, 4)])

partitioned = c.rows("""
SELECT product_id, id, row_number() OVER (PARTITION BY product_id ORDER BY id)
FROM skus ORDER BY product_id, id
""")
partition_ok = all(
    [r[2] for r in partitioned if r[0] == pid] == list(range(1, len([r for r in partitioned if r[0] == pid]) + 1))
    for pid in {r[0] for r in partitioned}
)
c.ok("PARTITION BY 分组编号", partition_ok, str(partitioned[:4]))

running = c.rows("""
SELECT id, sum(price) OVER (ORDER BY id ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW)
FROM skus ORDER BY id LIMIT 3
""")
c.equal("累计求和", [r[1] for r in running], [5999, 12998, 25997])

frame = c.rows("""
SELECT id, avg(price) OVER (ORDER BY id ROWS BETWEEN 1 PRECEDING AND CURRENT ROW)
FROM skus ORDER BY id LIMIT 1
""")
c.ok("滑动窗口", frame[0][1] == 5999, str(frame))

raise SystemExit(c.finish())
