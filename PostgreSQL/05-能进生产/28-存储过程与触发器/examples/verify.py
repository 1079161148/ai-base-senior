"""第 28 章 · PL/pgSQL 函数与触发器。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(28)
c.sql("""
CREATE TABLE item (id SERIAL PRIMARY KEY, name TEXT, price NUMERIC(10,2), updated_at TIMESTAMPTZ);
CREATE TABLE audit_log (id SERIAL PRIMARY KEY, item_id INT, old_price NUMERIC(10,2), new_price NUMERIC(10,2), at TIMESTAMPTZ DEFAULT now());
""")

c.sql("""
CREATE FUNCTION add_items(a NUMERIC, b NUMERIC) RETURNS NUMERIC
LANGUAGE sql IMMUTABLE AS $$ SELECT a + b $$;
""")
c.equal("SQL 函数", c.scalar("SELECT add_items(2,3)"), 5)

c.sql("""
CREATE FUNCTION discount(p NUMERIC, rate NUMERIC DEFAULT 0.9) RETURNS NUMERIC
LANGUAGE plpgsql AS $$
DECLARE result NUMERIC;
BEGIN
  result := p * rate;
  RETURN round(result, 2);
END;
$$;
""")
c.equal("PL/pgSQL 函数带默认值", c.scalar("SELECT discount(100)"), 90)

c.sql("""
CREATE FUNCTION expensive_items(min_price NUMERIC) RETURNS SETOF item
LANGUAGE sql STABLE AS $$ SELECT * FROM item WHERE price > min_price ORDER BY id $$;
""")
c.sql("INSERT INTO item (name,price) VALUES ('A',100),('B',50)")
c.equal("返回行集函数", [r[0] for r in c.rows("SELECT name FROM expensive_items(60)")], ["A"])

c.sql("""
CREATE FUNCTION set_updated_at() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  NEW.updated_at := now();
  RETURN NEW;
END;
$$;
CREATE TRIGGER trg_updated BEFORE INSERT OR UPDATE ON item
FOR EACH ROW EXECUTE FUNCTION set_updated_at();
""")
c.sql("INSERT INTO item (name,price) VALUES ('C',30)")
c.ok("BEFORE 触发器填默认值", c.scalar("SELECT updated_at IS NOT NULL FROM item WHERE name='C'"))

c.sql("""
CREATE FUNCTION log_price() RETURNS TRIGGER LANGUAGE plpgsql AS $$
BEGIN
  IF OLD.price IS DISTINCT FROM NEW.price THEN
    INSERT INTO audit_log (item_id, old_price, new_price) VALUES (NEW.id, OLD.price, NEW.price);
  END IF;
  RETURN NEW;
END;
$$;
CREATE TRIGGER trg_audit AFTER UPDATE ON item
FOR EACH ROW EXECUTE FUNCTION log_price();
""")
c.sql("UPDATE item SET price=120 WHERE name='A'")
c.equal("AFTER 触发器写审计", c.scalar("SELECT count(*) FROM audit_log"), 1)
c.equal("审计旧值", c.scalar("SELECT old_price FROM audit_log"), 100)

c.sql("UPDATE item SET name='A2' WHERE name='A'")
c.equal("无关字段更新不写审计", c.scalar("SELECT count(*) FROM audit_log"), 1)

functions = c.rows("""
SELECT proname FROM pg_proc WHERE pronamespace='ch28'::regnamespace ORDER BY 1
""")
c.ok("函数元数据", len(functions) >= 3, str(len(functions)))

triggers = c.rows("""
SELECT tgname FROM pg_trigger WHERE tgrelid='item'::regclass AND NOT tgisinternal ORDER BY 1
""")
c.equal("触发器元数据", [r[0] for r in triggers], ["trg_audit", "trg_updated"])

c.sql("DROP TRIGGER trg_audit ON item")
c.sql("DROP FUNCTION log_price()")
c.ok("DROP 成功", c.scalar("""
SELECT count(*) FROM pg_trigger WHERE tgrelid='item'::regclass AND NOT tgisinternal
"""), 1)

raise SystemExit(c.finish())
