"""第 09 章 · SELECT 与 WHERE。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker, setup_shop  # noqa: E402

c = Checker(9)
setup_shop(c)

c.equal("SELECT *", len(c.rows("SELECT * FROM users")), 4)
c.equal("指定列", len(c.rows("SELECT username, email FROM users")), 4)

named = c.rows("SELECT username AS 姓名, email 邮箱 FROM users WHERE id=1")[0]
c.equal("列别名", named, ("alice", "alice@example.com"))

c.equal("等值", c.scalar("SELECT count(*) FROM users WHERE username='alice'"), 1)
c.equal("范围", c.scalar("SELECT count(*) FROM skus WHERE price > 5000"), 4)
c.equal("AND 多条件", c.scalar("SELECT count(*) FROM skus WHERE price>5000 AND stock>=50"), 2)
c.equal("OR", c.scalar("SELECT count(*) FROM users WHERE username='alice' OR username='bob'"), 2)
c.equal("IN", c.scalar("SELECT count(*) FROM users WHERE username IN ('alice','bob')"), 2)
c.equal("BETWEEN", c.scalar("SELECT count(*) FROM skus WHERE price BETWEEN 100 AND 3000"), 2)
c.equal("LIKE 前缀", c.scalar("SELECT count(*) FROM users WHERE email LIKE 'a%'"), 1)
c.equal("LIKE 包含", c.scalar("SELECT count(*) FROM products WHERE name LIKE '%XPS%'"), 1)
c.equal("下划线单字符", c.scalar("SELECT count(*) FROM brands WHERE name LIKE '华_'"), 1)

c.sql("INSERT INTO user_profiles (user_id,bio,phone) VALUES (3,NULL,NULL)")
c.equal("IS NULL", c.scalar("SELECT count(*) FROM user_profiles WHERE phone IS NULL"), 1)
c.equal("IS NOT NULL", c.scalar("SELECT count(*) FROM user_profiles WHERE phone IS NOT NULL"), 2)

c.equal("NULL 与 = 不成立", c.scalar("SELECT count(*) FROM user_profiles WHERE phone = NULL"), 0)

c.equal("先建库再查", c.scalar("SELECT count(*) FROM categories WHERE name IN ('数码','图书','家居')"), 3)

raise SystemExit(c.finish())
