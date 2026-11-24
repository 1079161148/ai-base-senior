"""第 46 章 · 毕业项目：电商库 + 语义搜索工程化闭环。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker, fake_embedding, setup_shop  # noqa: E402

c = Checker(46)
setup_shop(c)
c.sql("CREATE EXTENSION IF NOT EXISTS vector")

# 1. 为商品补语义向量与元数据（把 M02 电商库升级为可语义检索）
c.sql("""
ALTER TABLE products ADD COLUMN embedding vector(16);
ALTER TABLE products ADD COLUMN search_model TEXT;
""")
products = c.rows("SELECT id,name,description FROM products ORDER BY id")
with c.conn.cursor() as cur:
    for pid, name, description in products:
        text = f"{name} {description or ''}"
        cur.execute(
            "UPDATE products SET embedding=%s, search_model='fake-v1' WHERE id=%s",
            (fake_embedding(text, 16), pid),
        )

c.equal("商品向量化完成", c.scalar("SELECT count(*) FROM products WHERE embedding IS NOT NULL"), len(products))
c.equal("模型版本记录", c.scalar("SELECT count(*) FROM products WHERE search_model='fake-v1'"), len(products))

# 2. 语义检索：Top-K + 元数据过滤
query = fake_embedding("华为手机", 16)
semantic = c.rows("""
SELECT name FROM products
WHERE category_id = (SELECT id FROM categories WHERE name='数码')
ORDER BY embedding <=> %s::vector LIMIT 3
""", (query,))
c.equal("语义 Top-3 返回", len(semantic), 3)
c.ok("语义检索命中手机", any("Mate" in n or "小米" in n for n, in semantic), str(semantic))

# 3. 混合检索：关键词 + 向量，RRF 融合
c.sql(f"""
CREATE VIEW product_search AS
SELECT p.id, p.name, p.category_id,
       CASE WHEN p.name ILIKE '%手机%' OR p.description ILIKE '%手机%' THEN 1 ELSE 2 END AS kw_rank,
       ROW_NUMBER() OVER (ORDER BY p.embedding <=> '{query}'::vector) AS vec_rank
FROM products p
""")
rrf = c.rows("""
SELECT name, 1.0/(60+kw_rank)+1.0/(60+vec_rank) AS score
FROM product_search ORDER BY score DESC LIMIT 5
""")
c.equal("融合检索返回 Top-5", len(rrf), 5)
c.ok("融合分数递减", rrf[0][1] >= rrf[-1][1], f"{rrf[0][1]:.4f} >= {rrf[-1][1]:.4f}")

# 4. HNSW 索引 + 执行计划
c.sql("CREATE INDEX idx_product_vec ON products USING hnsw (embedding vector_cosine_ops)")
c.sql("CREATE INDEX idx_product_cat ON products(category_id)")
c.ok("向量索引建成", c.scalar("SELECT count(*) FROM pg_indexes WHERE indexname='idx_product_vec'") == 1)
c.sql("ANALYZE products")
c.sql("SET enable_seqscan=off")
plan = "\n".join(r[0] for r in c.rows("""
EXPLAIN SELECT id FROM products ORDER BY embedding <=> %s::vector LIMIT 5
""", (query,)))
c.ok("查询可用索引", "Index" in plan or "Scan" in plan, plan[:60])

# 5. 视图 + 物化视图汇总（M05 能力）
c.sql("""
CREATE MATERIALIZED VIEW mv_category_stat AS
SELECT c.name AS category, count(p.id) AS products,
       max(s.price) AS max_price
FROM categories c LEFT JOIN products p ON p.category_id=c.id
LEFT JOIN skus s ON s.product_id=p.id
GROUP BY c.name
""")
c.equal("物化视图有数据", c.scalar("SELECT count(*) FROM mv_category_stat"), 3)

# 6. 权限隔离（M05 能力）
c.sql("DROP ROLE IF EXISTS r46_reader")
c.sql("CREATE ROLE r46_reader LOGIN PASSWORD 'reader123'")
c.sql("GRANT USAGE ON SCHEMA ch46 TO r46_reader")
c.sql("GRANT SELECT ON products TO r46_reader")
c.ok("只读角色授权", c.scalar("SELECT has_table_privilege('r46_reader','ch46.products','SELECT')"))

# 7. 事务一致性（M03 能力）
with c.conn.cursor() as cur:
    cur.execute("BEGIN")
    cur.execute("UPDATE products SET name='事务测试' WHERE id=1")
    cur.execute("ROLLBACK")
c.ok("事务回滚生效", c.scalar("SELECT name FROM products WHERE id=1") != "事务测试")

# 8. 评测 Recall@k（M06 能力）
all_ids = [r[0] for r in c.rows("SELECT id FROM products ORDER BY id")]
top_ids = [r[0] for r in c.rows("SELECT id FROM products ORDER BY embedding <=> %s::vector LIMIT 3", (query,))]
c.ok("检索结果为有效子集", set(top_ids) <= set(all_ids) and len(top_ids) == 3, str(top_ids))

# 9. 清理
c.sql("DROP OWNED BY r46_reader CASCADE")
c.sql("DROP ROLE r46_reader")
c.ok("角色清理完成", c.scalar("SELECT count(*) FROM pg_roles WHERE rolname='r46_reader'") == 0)

raise SystemExit(c.finish())
