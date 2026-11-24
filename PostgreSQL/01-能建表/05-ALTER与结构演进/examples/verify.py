"""第 05 章 · ALTER / DROP / TRUNCATE：结构演进。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(5)

c.sql("CREATE TABLE evolve (id SERIAL PRIMARY KEY, score NUMERIC(5,2), email TEXT)")
c.sql("INSERT INTO evolve (score, email) VALUES (88.5, 'a@x.com')")

c.sql("ALTER TABLE evolve ADD COLUMN phone VARCHAR(20)")
c.ok("ADD COLUMN", "phone" in [r[0] for r in c.rows(
    "SELECT column_name FROM information_schema.columns WHERE table_schema='ch05' AND table_name='evolve'")])

c.sql("ALTER TABLE evolve DROP COLUMN phone")
c.ok("DROP COLUMN", "phone" not in [r[0] for r in c.rows(
    "SELECT column_name FROM information_schema.columns WHERE table_schema='ch05' AND table_name='evolve'")])

c.sql("ALTER TABLE evolve ALTER COLUMN score TYPE INTEGER USING score::INTEGER")
c.equal("ALTER TYPE USING", str(c.scalar("SELECT score FROM evolve")), "89")

c.sql("ALTER TABLE evolve ALTER COLUMN score SET DEFAULT 0")
c.sql("INSERT INTO evolve (email) VALUES ('b@x.com')")
c.equal("SET DEFAULT", c.scalar("SELECT score FROM evolve WHERE email='b@x.com'"), 0)

c.sql("ALTER TABLE evolve ALTER COLUMN score DROP DEFAULT")
defaults = c.scalar(
    "SELECT column_default FROM information_schema.columns "
    "WHERE table_schema='ch05' AND table_name='evolve' AND column_name='score'"
)
c.ok("DROP DEFAULT", defaults is None, str(defaults))

c.sql("ALTER TABLE evolve ALTER COLUMN email SET NOT NULL")
is_nullable = c.scalar(
    "SELECT is_nullable FROM information_schema.columns "
    "WHERE table_schema='ch05' AND table_name='evolve' AND column_name='email'"
)
c.equal("SET NOT NULL", is_nullable, "NO")

c.sql("ALTER TABLE evolve ADD CONSTRAINT email_check CHECK (email LIKE '%@%')")
c.ok("ADD CONSTRAINT", c.scalar(
    "SELECT count(*) FROM pg_constraint WHERE conname='email_check'") == 1)

c.sql("ALTER TABLE evolve RENAME COLUMN email TO mail")
c.ok("RENAME COLUMN", c.scalar(
    "SELECT count(*) FROM information_schema.columns WHERE column_name='mail'") == 1)

c.sql("ALTER TABLE evolve RENAME TO evolved")
c.ok("RENAME TABLE", c.scalar("SELECT to_regclass('evolved') IS NOT NULL"))

c.sql("DROP TABLE IF EXISTS not_exists")
c.ok("DROP IF EXISTS 幂等", True)

c.sql("TRUNCATE TABLE evolved RESTART IDENTITY")
c.equal("TRUNCATE 保留结构且重置序列", c.scalar("SELECT count(*) FROM evolved"), 0)
c.sql("INSERT INTO evolved (mail) VALUES ('c@x.com')")
c.equal("序列从 1 开始", c.scalar("SELECT id FROM evolved"), 1)

raise SystemExit(c.finish())
