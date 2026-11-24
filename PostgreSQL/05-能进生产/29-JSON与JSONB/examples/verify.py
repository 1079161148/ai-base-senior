"""第 29 章 · JSON / JSONB 与 GIN 索引。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parents[3]))

from common import Checker  # noqa: E402

c = Checker(29)
c.sql("""
CREATE TABLE events (id SERIAL PRIMARY KEY, payload JSONB, raw JSON);
INSERT INTO events (payload, raw) VALUES
 ('{"user":"alice","tags":["a","b"],"meta":{"city":"北京"}}','{"user":"alice"}'),
 ('{"user":"bob","tags":["b"],"meta":{"city":"上海"}}','{"user":"bob"}');
""")

c.equal("-> 返回 JSONB", c.scalar("SELECT pg_typeof(payload->'user')::text FROM events WHERE id=1"), "jsonb")
c.equal("->> 返回文本", c.scalar("SELECT payload->>'user' FROM events WHERE id=1"), "alice")
c.equal("#> 路径取值", c.scalar("SELECT payload#>>'{meta,city}' FROM events WHERE id=1"), "北京")

c.equal("@> 顶层包含", c.scalar("SELECT count(*) FROM events WHERE payload @> '{\"user\":\"bob\"}'"), 1)
c.equal("@> 嵌套包含", c.scalar("SELECT count(*) FROM events WHERE payload @> '{\"meta\":{\"city\":\"北京\"}}'"), 1)
c.equal("? 键存在", c.scalar("SELECT count(*) FROM events WHERE payload ? 'tags'"), 2)
c.equal("?| 任一键", c.scalar("SELECT count(*) FROM events WHERE payload ?| array['nope','user']"), 2)
c.equal("?& 所有键", c.scalar("SELECT count(*) FROM events WHERE payload ?& array['user','tags']"), 2)

c.sql("CREATE INDEX idx_payload_gin ON events USING gin(payload)")
c.sql("SET enable_seqscan=off")
plan = "\n".join(r[0] for r in c.rows("EXPLAIN SELECT * FROM events WHERE payload @> '{\"user\":\"bob\"}'"))
c.sql("RESET enable_seqscan")
c.ok("GIN 可用于 @>", "Index" in plan or "Bitmap" in plan, plan[:60])

c.sql("UPDATE events SET payload=jsonb_set(payload,'{meta,city}','\"深圳\"') WHERE id=1")
c.equal("jsonb_set 嵌套更新", c.scalar("SELECT payload#>>'{meta,city}' FROM events WHERE id=1"), "深圳")

c.equal("数组包含", c.scalar("SELECT count(*) FROM events WHERE payload->'tags' @> '[\"a\"]'"), 1)

agg = c.scalar("SELECT jsonb_agg(u) FROM (SELECT payload->'user' AS u FROM events ORDER BY id) t")
c.ok("jsonb_agg", "alice" in str(agg) and "bob" in str(agg), str(agg))

types = c.rows("SELECT column_name,data_type FROM information_schema.columns WHERE table_schema='ch29' AND table_name='events' ORDER BY 1")
c.equal("类型区分", [r[1] for r in types], ["integer", "jsonb", "json"])

c.equal("JSONB 去重比较", c.scalar("""
SELECT count(*) FROM (SELECT DISTINCT payload FROM events) t
"""), 2)

raise SystemExit(c.finish())
