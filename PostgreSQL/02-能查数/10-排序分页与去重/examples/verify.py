"""第 10 章 · ORDER BY / LIMIT / DISTINCT。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker, setup_shop  # noqa: E402

c = Checker(10)
setup_shop(c)

asc = [r[0] for r in c.rows("SELECT price FROM skus ORDER BY price")]
c.ok("升序默认", asc == sorted(asc), str(asc[:3]))

desc = [r[0] for r in c.rows("SELECT price FROM skus ORDER BY price DESC")]
c.ok("降序", desc == sorted(desc, reverse=True), str(desc[:3]))

multi = c.rows("""
SELECT p.category_id, s.price FROM skus s JOIN products p ON s.product_id=p.id
ORDER BY p.category_id, s.price DESC
""")
c.ok("多列排序", len(multi) == 8, str(len(multi)))

c.sql("INSERT INTO skus (product_id,sku_code,price,stock) VALUES (1,'NULL-PRICE',NULL,1)")
nulls_default = c.rows("SELECT sku_code FROM skus ORDER BY price NULLS LAST")
c.equal("NULLS LAST", nulls_default[-1][0], "NULL-PRICE")

limited = [r[0] for r in c.rows("SELECT id FROM skus ORDER BY id LIMIT 3")]
c.equal("LIMIT", limited, [1, 2, 3])

offset = [r[0] for r in c.rows("SELECT id FROM skus ORDER BY id LIMIT 3 OFFSET 3")]
c.equal("OFFSET", offset, [4, 5, 6])

pages = [
    [r[0] for r in c.rows("SELECT id FROM skus ORDER BY id LIMIT 3 OFFSET %s", (page * 3,))]
    for page in range(3)
]
c.equal("分页不重不漏", sorted(sum(pages, [])), list(range(1, 10)))

brands = [r[0] for r in c.rows("SELECT DISTINCT brand_id FROM products ORDER BY brand_id")]
c.equal("DISTINCT", brands, [1, 2, 3])

pairs = c.rows("SELECT DISTINCT category_id, brand_id FROM products ORDER BY 1,2")
c.equal("DISTINCT 多列", len(pairs), 6)

first_per_cat = c.rows("""
SELECT DISTINCT ON (category_id) category_id, id, name
FROM products ORDER BY category_id, id
""")
c.equal("DISTINCT ON 每组取一", [r[1] for r in first_per_cat], [1, 4, 6])

aliased = c.rows("SELECT price AS p FROM skus WHERE price IS NOT NULL ORDER BY p LIMIT 2")
c.ok("ORDER BY 用别名", aliased[0][0] <= aliased[1][0], str(aliased))

raise SystemExit(c.finish())
