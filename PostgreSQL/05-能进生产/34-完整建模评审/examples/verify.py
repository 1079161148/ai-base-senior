"""第 34 章 · 完整建模评审：从反例到规范模型。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(34)
c.sql("""
CREATE TABLE bad_orders (
    order_no TEXT,
    customer_name TEXT,
    customer_phone TEXT,
    product_names TEXT,
    total_price TEXT,
    created TEXT
);
INSERT INTO bad_orders VALUES ('O-001','张三','111','手机,电脑','6000','2025-01-01');
""")

bad_pk = c.scalar("""
SELECT count(*) FROM information_schema.table_constraints
WHERE table_schema='ch34' AND table_name='bad_orders' AND constraint_type='PRIMARY KEY'
""")
c.ok("反例无主键", bad_pk == 0, str(bad_pk))

bad_fk = c.scalar("""
SELECT count(*) FROM information_schema.table_constraints
WHERE table_schema='ch34' AND table_name='bad_orders' AND constraint_type='FOREIGN KEY'
""")
c.ok("反例无外键", bad_fk == 0, str(bad_fk))

bad_types = c.rows("""
SELECT data_type FROM information_schema.columns
WHERE table_schema='ch34' AND table_name='bad_orders' ORDER BY ordinal_position
""")
c.ok("反例金额与时间为文本", [r[0] for r in bad_types].count("text") >= 4, str(bad_types))

c.sql("""
CREATE TABLE customers (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    phone TEXT UNIQUE
);
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    name TEXT NOT NULL,
    price NUMERIC(10,2) CHECK (price >= 0)
);
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    customer_id INT NOT NULL REFERENCES customers(id),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY,
    order_id INT NOT NULL REFERENCES orders(id) ON DELETE CASCADE,
    product_id INT NOT NULL REFERENCES products(id),
    quantity INT CHECK (quantity > 0),
    unit_price NUMERIC(10,2) CHECK (unit_price >= 0),
    UNIQUE (order_id, product_id)
);
""")

pk_tables = c.rows("""
SELECT table_name FROM information_schema.table_constraints
WHERE table_schema='ch34' AND constraint_type='PRIMARY KEY'
  AND table_name <> 'bad_orders' ORDER BY table_name
""")
c.equal("规范模型四表有主键", [r[0] for r in pk_tables],
        ["customers", "order_items", "orders", "products"])

fks = c.rows("""
SELECT ccu.table_name FROM information_schema.table_constraints tc
JOIN information_schema.constraint_column_usage ccu
  ON ccu.constraint_name=tc.constraint_name AND ccu.table_schema=tc.table_schema
WHERE tc.table_schema='ch34' AND tc.constraint_type='FOREIGN KEY'
  AND tc.table_name='order_items'
""")
c.equal("订单明细两条外键", sorted(r[0] for r in fks), ["orders", "products"])

c.ok("NOT NULL 约束存在", c.scalar("""
SELECT count(*) FROM information_schema.columns
WHERE table_schema='ch34' AND is_nullable='NO' AND table_name IN ('orders','order_items')
""") >= 5)

checks = c.scalar("""
SELECT count(*) FROM information_schema.table_constraints
WHERE table_schema='ch34' AND constraint_type='CHECK'
""")
c.ok("CHECK 约束存在", checks >= 4, str(checks))

price_type = c.scalar("""
SELECT data_type FROM information_schema.columns
WHERE table_schema='ch34' AND table_name='products' AND column_name='price'
""")
c.equal("金额用 NUMERIC", price_type, "numeric")

unique_phone = c.scalar("""
SELECT count(*) FROM information_schema.table_constraints
WHERE table_schema='ch34' AND table_name='customers' AND constraint_type='UNIQUE'
""")
c.ok("手机号唯一约束", unique_phone == 1, str(unique_phone))

c.sql("""
INSERT INTO customers (name,phone) VALUES ('张三','111'),('李四','222');
INSERT INTO products (name,price) VALUES ('手机',3000),('电脑',6000);
INSERT INTO orders (customer_id) VALUES (1);
INSERT INTO order_items (order_id,product_id,quantity,unit_price) VALUES (1,1,1,3000);
""")
c.equal("规范模型可写入", c.scalar("SELECT count(*) FROM order_items"), 1)

joined = c.rows("""
SELECT cu.name, pr.name, oi.quantity
FROM order_items oi
JOIN orders o ON o.id=oi.order_id
JOIN customers cu ON cu.id=o.customer_id
JOIN products pr ON pr.id=oi.product_id
""")
c.equal("JOIN 可还原业务语义", joined, [("张三", "手机", 1)])

duplicate_rejected = False
try:
    c.sql("INSERT INTO order_items (order_id,product_id,quantity,unit_price) VALUES (1,1,1,3000)")
except Exception:
    duplicate_rejected = True
c.ok("UNIQUE 拦截重复明细", duplicate_rejected)

cascade_ok = False
try:
    c.sql("INSERT INTO order_items (order_id,product_id,quantity,unit_price) VALUES (1,2,1,6000)")
    c.sql("DELETE FROM orders WHERE id=1")
    cascade_ok = c.scalar("SELECT count(*) FROM order_items") == 0
except Exception:
    cascade_ok = False
c.ok("ON DELETE CASCADE 生效", cascade_ok)

cascade_check = False
try:
    c.sql("INSERT INTO products (name,price) VALUES ('耳机',500)")
    c.sql("INSERT INTO order_items (order_id,product_id,quantity,unit_price) VALUES (1,4,1,500)")
    cascade_check = True
except Exception:
    cascade_check = False
c.ok("订单已删后明细无法插回", not cascade_check)

raise SystemExit(c.finish())
