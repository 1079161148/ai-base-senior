"""第 12 章 · JOIN：INNER / LEFT / RIGHT / FULL。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker, setup_shop  # noqa: E402

c = Checker(12)
setup_shop(c)

inner = c.rows("""
SELECT u.username, o.order_no FROM users u
JOIN orders o ON u.id = o.user_id ORDER BY o.order_no
""")
c.equal("INNER JOIN", len(inner), 7)

left = c.rows("""
SELECT u.username, p.bio FROM users u
LEFT JOIN user_profiles p ON u.id = p.user_id ORDER BY u.id
""")
c.equal("LEFT JOIN 保留左表", len(left), 4)
c.ok("LEFT JOIN 未匹配补 NULL", left[2][1] is None, str(left[2]))

right = c.rows("""
SELECT u.username, p.user_id FROM user_profiles p
RIGHT JOIN users u ON u.id = p.user_id ORDER BY u.id
""")
c.equal("RIGHT JOIN 保留右表", len(right), 4)

full = c.rows("""
SELECT u.id, o.id FROM users u FULL JOIN orders o ON u.id=o.user_id
""")
c.equal("FULL JOIN", len(full), 7)

three = c.rows("""
SELECT u.username, o.order_no, s.sku_code
FROM users u
JOIN orders o ON u.id=o.user_id
JOIN order_items oi ON o.id=oi.order_id
JOIN skus s ON oi.sku_id=s.id
ORDER BY o.order_no
""")
c.equal("多表 JOIN", len(three), 7)

alias = c.rows("SELECT u.username FROM users AS u WHERE u.id=1")
c.equal("表别名", alias, [("alice",)])

self_join = c.rows("""
SELECT a.name AS 商品, b.name AS 同品牌
FROM products a JOIN products b ON a.brand_id=b.brand_id AND a.id<>b.id
WHERE a.id=1 ORDER BY b.id
""")
c.equal("自 JOIN", [r[1] for r in self_join], ["SQL 入门"])

with_agg = c.rows("""
SELECT u.username, count(o.id) FROM users u
LEFT JOIN orders o ON u.id=o.user_id GROUP BY u.id ORDER BY u.id
""")
c.equal("JOIN + 聚合", [r[1] for r in with_agg], [2, 2, 2, 1])

orphans = c.rows("""
SELECT u.username FROM users u LEFT JOIN user_profiles p ON u.id=p.user_id
WHERE p.user_id IS NULL
""")
c.equal("LEFT JOIN 找孤儿", [r[0] for r in orphans], ["carol", "dave"])

cross = c.rows("SELECT count(*) FROM categories CROSS JOIN brands")
c.equal("CROSS JOIN 笛卡尔积", cross[0][0], 9)

using = c.rows("""
SELECT count(*) FROM products p JOIN categories c ON p.category_id = c.id
""")
c.equal("ON 连接分类", using[0][0], 6)

left_on = c.rows("""
SELECT count(*) FROM users u LEFT JOIN orders o ON u.id=o.user_id AND o.status='cancelled'
""")
c.equal("ON 条件过滤右表", left_on[0][0], 4)

raise SystemExit(c.finish())
