"""第 15 章 · 原仓库 33 道电商题实战（简化数据集）。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker, setup_shop  # noqa: E402

c = Checker(15)
setup_shop(c)


def count(label: str, sql: str, expected: int) -> None:
    c.equal(label, c.scalar(sql), expected)


c.sql("INSERT INTO users (username,email,created_at) VALUES ('huahua','h@x.com','2024-06-01')")
c.sql("INSERT INTO products (name,category_id,brand_id) VALUES ('未售商品',1,1)")
c.sql("INSERT INTO skus (product_id,sku_code,price,stock) VALUES (7,'UNSOLD',50,5)")

count("01 分类名和描述", "SELECT count(*) FROM categories WHERE description IS NOT NULL", 3)
count("02 用户三项", "SELECT count(*) FROM users WHERE email IS NOT NULL", 5)
count("03 华为商品", "SELECT count(*) FROM products p JOIN brands b ON p.brand_id=b.id WHERE b.name='华为'", 3)
count("04 低于500 SKU", "SELECT count(*) FROM skus WHERE price<500", 4)
count("05 库存>300", "SELECT count(*) FROM skus WHERE stock>300", 2)
count("06 2024注册", "SELECT count(*) FROM users WHERE created_at >= '2024-01-01' AND created_at < '2025-01-01'", 3)
count("07 completed订单", "SELECT count(*) FROM orders WHERE status='completed'", 3)
count("08 不同品牌", "SELECT count(DISTINCT brand_id) FROM products", 3)
count("09 不同状态", "SELECT count(DISTINCT status) FROM orders", 5)
count("10 最贵5个", "SELECT count(*) FROM (SELECT id FROM skus ORDER BY price DESC LIMIT 5) t", 5)
count("11 最新10用户", "SELECT count(*) FROM (SELECT id FROM users ORDER BY created_at DESC LIMIT 10) t", 5)
count("12 三类总数", "SELECT (SELECT count(*) FROM users)+(SELECT count(*) FROM products)+(SELECT count(*) FROM skus)", 21)
count("13 价格聚合", "SELECT count(*) FROM (SELECT avg(price),max(price),min(price) FROM skus) t", 1)
count("14 每分类商品数", "SELECT count(*) FROM (SELECT category_id FROM products GROUP BY category_id) t", 3)
count("15 品牌商品>2", "SELECT count(*) FROM (SELECT brand_id FROM products GROUP BY brand_id HAVING count(*)>2) t", 1)
count("16 每用户订单数", "SELECT count(*) FROM (SELECT user_id FROM orders GROUP BY user_id) t", 4)
count("17 状态数量", "SELECT count(*) FROM (SELECT status FROM orders GROUP BY status) t", 5)
count("18 每商品均价", "SELECT count(*) FROM (SELECT product_id FROM skus GROUP BY product_id) t", 7)
count("19 最便宜/最贵差价", "SELECT count(*) FROM (SELECT product_id FROM skus GROUP BY product_id) t", 7)
count("20 分类库存价值", "SELECT count(*) FROM (SELECT p.category_id FROM skus s JOIN products p ON s.product_id=p.id GROUP BY p.category_id) t", 3)
count("21 商品+分类名", "SELECT count(*) FROM products p JOIN categories c ON p.category_id=c.id", 7)
count("22 用户+资料", "SELECT count(*) FROM users u LEFT JOIN user_profiles p ON u.id=p.user_id", 5)
count("23 订单明细第3页", "SELECT count(*) FROM (SELECT id FROM order_items ORDER BY id LIMIT 10 OFFSET 20) t", 0)
count("24 消费>10000", "SELECT count(*) FROM (SELECT user_id FROM orders GROUP BY user_id HAVING sum(total_amount)>10000) t", 1)
count("25 从未被购买商品", """
SELECT count(*) FROM products p WHERE NOT EXISTS (
  SELECT 1 FROM skus s JOIN order_items oi ON s.id=oi.sku_id WHERE s.product_id=p.id
)""", 1)
count("26 下单<5次用户", "SELECT count(*) FROM (SELECT user_id FROM orders GROUP BY user_id HAVING count(*)<5) t", 4)
count("27 买过XPS的人", """
SELECT count(DISTINCT o.user_id) FROM orders o
JOIN order_items oi ON o.id=oi.order_id JOIN skus s ON oi.sku_id=s.id
JOIN products p ON s.product_id=p.id WHERE p.name='Dell XPS 15'""", 1)
count("28 高于均价SKU", "SELECT count(*) FROM skus WHERE price>(SELECT avg(price) FROM skus)", 4)
count("29 种类最多前5订单", "SELECT count(*) FROM (SELECT order_id FROM order_items GROUP BY order_id ORDER BY count(DISTINCT sku_id) DESC LIMIT 5) t", 5)
count("30 2024各月注册", """
SELECT count(*) FROM (SELECT date_trunc('month',created_at) m FROM users
WHERE created_at<'2025-01-01' GROUP BY m) t""", 3)
count("31 每月订单", "SELECT count(*) FROM (SELECT date_trunc('month',created_at) m FROM orders GROUP BY m) t", 7)
count("32 用户名含hua", "SELECT count(*) FROM users WHERE username LIKE '%hua%'", 1)
count("33 2025下单前三", """
SELECT count(*) FROM (SELECT user_id FROM orders
WHERE created_at>='2025-01-01' GROUP BY user_id ORDER BY count(*) DESC LIMIT 3) t""", 3)

raise SystemExit(c.finish())
