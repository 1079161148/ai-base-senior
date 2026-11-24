"""第 38 章 · 三种距离算子与相似度排序。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(38)

l2 = c.scalar("SELECT %s::vector <-> %s::vector", ('[1,0,0]', '[0,1,0]'))
c.ok("L2 距离", abs(float(l2) - 1.4142135623730951) < 1e-6, str(l2))

cos = c.scalar("SELECT %s::vector <=> %s::vector", ('[1,0,0]', '[0,1,0]'))
c.ok("余弦距离正交为 1", abs(float(cos) - 1.0) < 1e-6, str(cos))

cos_same = c.scalar("SELECT %s::vector <=> %s::vector", ('[1,0,0]', '[2,0,0]'))
c.ok("余弦距离同向为 0", float(cos_same) < 1e-6, str(cos_same))

neg_ip = c.scalar("SELECT %s::vector <#> %s::vector", ('[1,0,0]', '[0,1,0]'))
c.ok("负内积正交为 0", abs(float(neg_ip)) < 1e-6, str(neg_ip))

neg_ip_same = c.scalar("SELECT %s::vector <#> %s::vector", ('[1,0,0]', '[1,0,0]'))
c.ok("负内积同向为 -1", abs(float(neg_ip_same) + 1.0) < 1e-6, str(neg_ip_same))

c.sql("""
CREATE TABLE docs (id SERIAL PRIMARY KEY, title TEXT, embedding vector(3));
INSERT INTO docs (title,embedding) VALUES
 ('东', '[1,0,0]'),('西', '[0,1,0]'),('东北', '[0.9,0.1,0]');
""")

by_l2 = c.rows("SELECT title FROM docs ORDER BY embedding <-> %s::vector", ('[1,0,0]',))
c.equal("L2 最近邻是自身", by_l2[0][0], "东")

by_cos = c.rows("SELECT title FROM docs ORDER BY embedding <=> %s::vector", ('[1,0,0]',))
c.equal("余弦最近邻是自身", by_cos[0][0], "东")

distances = c.rows("""
SELECT title, embedding <-> %s::vector AS d FROM docs ORDER BY d
""", ('[1,0,0]',))
c.ok("距离升序排列", [r[1] for r in distances] == sorted(r[1] for r in distances), str(distances))

raise SystemExit(c.finish())
