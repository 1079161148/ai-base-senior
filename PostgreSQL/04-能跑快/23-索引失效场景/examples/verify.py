"""第 23 章 · 索引为什么会loss_demo。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(23)
c.sql("""
CREATE TABLE loss_demo (id SERIAL PRIMARY KEY, code TEXT, amount NUMERIC(10,2), created DATE);
INSERT INTO loss_demo (code,amount,created)
SELECT 'CODE-'||lpad(g::text,6,'0'), (g%1000)::numeric, date '2020-01-01'+(g%2000)
FROM generate_series(1,20000) g;
CREATE INDEX idx_code ON loss_demo(code);
CREATE INDEX idx_amount ON loss_demo(amount);
ANALYZE loss_demo;
""")

def scan(sql):
    text = "\n".join(r[0] for r in c.rows("EXPLAIN " + sql))
    return "Index" if "Index Scan" in text or "Bitmap" in text else "Seq"

c.equal("等值可用索引", scan("SELECT * FROM loss_demo WHERE code='CODE-000123'"), "Index")
c.equal("前缀 LIKE 查询可执行", c.scalar("SELECT count(*) FROM loss_demo WHERE code LIKE 'CODE-000123%'"), 1)
c.equal("前置通配符loss_demo", scan("SELECT * FROM loss_demo WHERE code LIKE '%000123'"), "Seq")

c.equal("列上套函数loss_demo", scan("SELECT * FROM loss_demo WHERE lower(code)='code-000123'"), "Seq")
c.sql("CREATE INDEX idx_lower_code ON loss_demo(lower(code))")
c.sql("ANALYZE loss_demo")
c.equal("表达式索引恢复", scan("SELECT * FROM loss_demo WHERE lower(code)='code-000123'"), "Index")

c.equal("列上运算loss_demo", scan("SELECT * FROM loss_demo WHERE amount+1=101"), "Seq")
c.sql("CREATE INDEX idx_amount_expr ON loss_demo((amount+1))")
c.equal("表达式索引救运算", scan("SELECT * FROM loss_demo WHERE amount+1=101"), "Index")

c.equal("OR 混合条件可能走 Seq", scan("SELECT * FROM loss_demo WHERE code='CODE-000123' OR amount=0") in ("Seq", "Index"), True)

c.sql("DROP INDEX idx_amount_expr")
c.sql("DELETE FROM loss_demo")
c.sql("ANALYZE loss_demo")
c.equal("空表已清空", c.scalar("SELECT count(*) FROM loss_demo"), 0)

c.sql("INSERT INTO loss_demo (code,amount,created) SELECT 'C-'||g, g::numeric, date '2024-01-01' FROM generate_series(1,20000) g")
c.sql("ANALYZE loss_demo")
c.equal("取全表大比例走 Seq", scan("SELECT * FROM loss_demo WHERE code LIKE 'C-%'"), "Seq")

raise SystemExit(c.finish())
