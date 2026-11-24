"""47 章共用的验收工具：每章一个独立 schema，互不污染。

默认连接教程容器 pg16-study（127.0.0.1:54321）。
也可通过环境变量 PG_DSN 覆盖。
"""

import os
from typing import Any

import psycopg

DEFAULT_DSN = "host=127.0.0.1 port=54321 dbname=study user=admin password=study123"
DSN = os.getenv("PG_DSN", DEFAULT_DSN)


class Checker:
    def __init__(self, chapter: int) -> None:
        self.schema = f"ch{chapter:02d}"
        self.conn = psycopg.connect(DSN, autocommit=True)
        self.conn.execute(f"DROP SCHEMA IF EXISTS {self.schema} CASCADE")
        self.conn.execute(f"CREATE SCHEMA {self.schema}")
        self.conn.execute(f"SET search_path TO {self.schema}, public")
        self.passed = 0
        self.failed = 0

    def sql(self, statement: str, params: tuple[Any, ...] | None = None) -> psycopg.Cursor:
        return self.conn.execute(statement, params)

    def scalar(self, statement: str, params: tuple[Any, ...] | None = None) -> Any:
        row = self.conn.execute(statement, params).fetchone()
        assert row is not None, f"查询无结果：{statement}"
        return row[0]

    def rows(self, statement: str, params: tuple[Any, ...] | None = None) -> list[tuple[Any, ...]]:
        return [tuple(row) for row in self.conn.execute(statement, params).fetchall()]

    def ok(self, label: str, condition: bool, detail: str = "") -> None:
        if condition:
            self.passed += 1
            print(f"[PASS] {label}" + (f" -> {detail}" if detail else ""))
        else:
            self.failed += 1
            print(f"[FAIL] {label}" + (f" -> {detail}" if detail else ""))

    def equal(self, label: str, actual: Any, expected: Any) -> None:
        self.ok(label, actual == expected, f"实际={actual!r} 期望={expected!r}")

    def finish(self) -> int:
        total = self.passed + self.failed
        print(f"\n结果：{self.passed}/{total} 通过")
        self.conn.close()
        return 1 if self.failed else 0


SHOP_SCHEMA = """
CREATE TABLE users (
    id SERIAL PRIMARY KEY, username TEXT NOT NULL, email TEXT UNIQUE,
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE user_profiles (
    user_id INT PRIMARY KEY REFERENCES users(id), bio TEXT, phone TEXT
);
CREATE TABLE categories (
    id SERIAL PRIMARY KEY, name TEXT NOT NULL, description TEXT
);
CREATE TABLE brands (
    id SERIAL PRIMARY KEY, name TEXT NOT NULL
);
CREATE TABLE products (
    id SERIAL PRIMARY KEY, name TEXT NOT NULL, category_id INT REFERENCES categories(id),
    brand_id INT REFERENCES brands(id), description TEXT
);
CREATE TABLE skus (
    id SERIAL PRIMARY KEY, product_id INT REFERENCES products(id),
    sku_code TEXT UNIQUE, price NUMERIC(10,2), stock INT
);
CREATE TABLE orders (
    id SERIAL PRIMARY KEY, user_id INT REFERENCES users(id), order_no TEXT UNIQUE,
    status TEXT, total_amount NUMERIC(10,2),
    created_at TIMESTAMPTZ DEFAULT CURRENT_TIMESTAMP
);
CREATE TABLE order_items (
    id SERIAL PRIMARY KEY, order_id INT REFERENCES orders(id),
    sku_id INT REFERENCES skus(id), quantity INT, unit_price NUMERIC(10,2)
);
"""

SHOP_DATA = """
INSERT INTO users (username,email,created_at) VALUES
 ('alice','alice@example.com','2024-01-15'),('bob','bob@example.com','2024-03-20'),
 ('carol','carol@example.com','2025-02-10'),('dave','dave@example.com','2025-06-05');
INSERT INTO user_profiles VALUES (1,'喜欢数码','111'),(2,'喜欢图书','222');
INSERT INTO categories (name,description) VALUES ('数码','电子设备'),('图书','纸质书'),('家居','居家用品');
INSERT INTO brands (name) VALUES ('华为'),('Dell'),('小米');
INSERT INTO products (name,category_id,brand_id,description) VALUES
 ('Mate 60',1,1,'华为手机'),('Dell XPS 15',1,2,'戴尔笔记本'),('小米电视',1,3,'小米电视'),
 ('SQL 入门',2,1,'数据库书'),('Python 进阶',2,2,'编程书'),('台灯',3,3,'护眼台灯');
INSERT INTO skus (product_id,sku_code,price,stock) VALUES
 (1,'HW-M60-256',5999,120),(1,'HW-M60-512',6999,80),
 (2,'DELL-XPS15-I7',12999,30),(2,'DELL-XPS15-I9',15999,15),
 (3,'MI-TV-55',2999,200),(4,'BOOK-SQL',89,500),
 (5,'BOOK-PY',99,300),(6,'LAMP-LED',199,400);
INSERT INTO orders (user_id,order_no,status,total_amount,created_at) VALUES
 (1,'O-001','completed',5999,'2024-05-01'),(1,'O-002','paid',89,'2025-01-10'),
 (2,'O-003','completed',12999,'2024-08-20'),(2,'O-004','pending',199,'2025-03-15'),
 (3,'O-005','shipped',2999,'2025-04-02'),(3,'O-006','completed',99,'2025-07-08'),
 (4,'O-007','cancelled',6999,'2025-09-12');
INSERT INTO order_items (order_id,sku_id,quantity,unit_price) VALUES
 (1,1,1,5999),(2,6,1,89),(3,3,1,12999),(4,8,1,199),
 (5,5,1,2999),(6,7,1,99),(7,2,1,6999);
"""


def setup_shop(c: "Checker") -> None:
    """在当前章节 schema 内建立简化电商库（M02 八章共用）。"""
    c.sql(SHOP_SCHEMA)
    c.sql(SHOP_DATA)


def fake_embedding(text: str, dim: int = 3) -> str:
    """生成确定性的教学用向量字面量，格式可直接喂给 pgvector。

    真实项目应调用 embedding 模型；这里刻意用字符分布构造，保证相同文本
    得到相同向量、共享字符多的文本距离更近，便于真实验证距离与索引行为。
    """
    values = [0.0] * dim
    for char in text:
        bucket = ord(char) % dim
        values[bucket] += 1.0
    norm = sum(value * value for value in values) ** 0.5 or 1.0
    return "[" + ",".join(f"{value / norm:.6f}" for value in values) + "]"
