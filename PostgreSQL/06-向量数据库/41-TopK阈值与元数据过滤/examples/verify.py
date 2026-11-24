"""第 41 章 · Top-K、距离阈值与元数据过滤。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(41)

c.sql("""
CREATE TABLE products (
  id SERIAL PRIMARY KEY, name TEXT, category TEXT, price NUMERIC(10,2), embedding vector(3)
);
INSERT INTO products (name,category,price,embedding) VALUES
 ('手机A','数码',5999,'[1,0,0]'),
 ('手机B','数码',3999,'[0.9,0.1,0]'),
 ('电脑C','数码',8999,'[0.8,0.2,0]'),
 ('小说D','图书',39,'[0,1,0]'),
 ('教材E','图书',99,'[0.1,0.9,0]'),
 ('台灯F','家居',199,'[0,0,1]');
""")

query = "[1,0,0]"

top3 = c.rows("SELECT name FROM products ORDER BY embedding <-> %s::vector LIMIT 3", (query,))
c.equal("Top-K 数量", len(top3), 3)
c.ok("Top-K 按距离排序", top3[0][0] == "手机A", str(top3))

threshold = c.rows("""
SELECT name FROM products WHERE embedding <-> %s::vector < 0.2
ORDER BY embedding <-> %s::vector
""", (query, query))
c.ok("阈值过滤生效", len(threshold) >= 1 and all(n != "台灯F" for n, in threshold), str(threshold))

filtered = c.rows("""
SELECT name FROM products WHERE category='图书'
ORDER BY embedding <-> %s::vector LIMIT 2
""", (query,))
c.equal("元数据过滤只留图书", sorted(n for n, in filtered), sorted(["教材E", "小说D"]))

combined = c.rows("""
SELECT name FROM products
WHERE category='数码' AND price < 6000 AND embedding <-> %s::vector < 0.5
ORDER BY embedding <-> %s::vector
""", (query, query))
c.ok("多条件组合过滤", all(n in ("手机A", "手机B", "电脑C") for n, in combined), str(combined))

score = c.rows("""
SELECT name, 1/(1 + (embedding <-> %s::vector)) AS score
FROM products ORDER BY score DESC LIMIT 3
""", (query,))
c.ok("相似度分数可计算", score[0][1] >= score[-1][1], str(score))

with_dist = c.rows("""
SELECT name, embedding <-> %s::vector AS d FROM products ORDER BY d LIMIT 1
""", (query,))
c.ok("距离可展示", with_dist[0][1] >= 0, str(with_dist))

raise SystemExit(c.finish())
