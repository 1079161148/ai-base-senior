"""第 58 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from db import DB_FILE, TOTAL_ROWS, connect  # noqa: E402


def client() -> TestClient:
    return TestClient(main.app)


def check_rows_and_index() -> str:
    """10 万行 + 复合索引就绪。"""
    with client() as c:
        body = c.get("/events/stats").json()
    assert body["rows"] == TOTAL_ROWS, body
    assert "idx_events_created" in body["indexes"], body
    return f'{body["rows"]} 行，索引 {body["indexes"]}'


def check_offset_first_page() -> str:
    """偏移分页首页：id 从大到小。"""
    with client() as c:
        body = c.get("/events", params={"limit": 3}).json()
    assert [item["id"] for item in body["items"]] == [100000, 99999, 99998], body
    assert body["total"] == TOTAL_ROWS, body
    assert body["has_more"] is True, body
    return "100000,99999,99998"


def check_offset_deep_page() -> str:
    """偏移分页深页：能取到最后 3 条。"""
    with client() as c:
        body = c.get("/events", params={"limit": 3, "offset": TOTAL_ROWS - 3}).json()
    assert [item["id"] for item in body["items"]] == [3, 2, 1], body
    assert body["has_more"] is False, body
    return "3,2,1"


def check_cursor_first_equals_offset() -> str:
    """游标首页与偏移首页结果一致。"""
    with client() as c:
        cursor_page = c.get("/events/cursor", params={"limit": 5}).json()
        offset_page = c.get("/events", params={"limit": 5}).json()
    assert cursor_page["items"] == offset_page["items"], (cursor_page, offset_page)
    return "两页完全相同"


def check_cursor_pagination_no_gap() -> str:
    """用 `next_cursor` 翻 3 页，id 严格递减且无重复。"""
    seen: list[int] = []
    with client() as c:
        cursor = None
        for _ in range(3):
            params = {"limit": 5}
            if cursor:
                params["cursor"] = cursor
            body = c.get("/events/cursor", params=params).json()
            seen.extend(item["id"] for item in body["items"])
            cursor = body["next_cursor"]
    assert len(seen) == 15, seen
    assert len(set(seen)) == 15, seen
    assert seen == sorted(seen, reverse=True), seen
    return f"15 条连续：{seen[0]}…{seen[-1]}"


def check_cursor_last_page() -> str:
    """翻到最小记录之后：空页、`has_more=False`、`next_cursor=None`。"""
    conn = connect()
    try:
        first = conn.execute(
            "SELECT created_at, id FROM events ORDER BY created_at, id LIMIT 1"
        ).fetchone()
    finally:
        conn.close()
    cursor = f"{first['created_at']}|{first['id']}"
    with client() as c:
        body = c.get("/events/cursor", params={"cursor": cursor}).json()
    assert body["items"] == [], body
    assert body["has_more"] is False, body
    assert body["next_cursor"] is None, body
    return "空页，next_cursor=None"


def check_limit_bounds() -> str:
    """`limit` 必须在 1..100，否则 422。"""
    with client() as c:
        assert c.get("/events", params={"limit": 0}).status_code == 422
        assert c.get("/events", params={"limit": 101}).status_code == 422
        assert c.get("/events/cursor", params={"limit": 101}).status_code == 422
        assert c.get("/events", params={"limit": 100}).status_code == 200
    return "0/101 → 422，100 → 200"


def check_offset_negative() -> str:
    """`offset` 不能为负。"""
    with client() as c:
        assert c.get("/events", params={"offset": -1}).status_code == 422
    return "422"


def check_bad_cursor() -> str:
    """游标格式错误 → 400，不是 500。"""
    with client() as c:
        r = c.get("/events/cursor", params={"cursor": "not-a-cursor"})
    assert r.status_code == 400, (r.status_code, r.text)
    assert r.json()["detail"] == "游标格式错误", r.json()
    return "400 游标格式错误"


def check_explain_uses_index() -> str:
    """有索引排序：`USING INDEX`，且**没有**临时 B 树。"""
    with client() as c:
        plan = c.get("/events/explain", params={"mode": "indexed"}).json()["plan"]
    details = " | ".join(row["detail"] for row in plan)
    assert "USING INDEX idx_events_created" in details, details
    assert "TEMP B-TREE" not in details, details
    return details


def check_explain_unindexed() -> str:
    """按无索引列排序：`SCAN events` + `USE TEMP B-TREE FOR ORDER BY`。"""
    with client() as c:
        plan = c.get("/events/explain", params={"mode": "unindexed"}).json()["plan"]
    details = [row["detail"] for row in plan]
    assert "SCAN events" in details, details
    assert any("TEMP B-TREE" in detail for detail in details), details
    return " | ".join(details)


def check_offset_deep_is_slow() -> str:
    """深页 `OFFSET` 比首页慢一个数量级以上（实测约 100~200 倍）。"""
    with client() as c:
        body = c.get("/events/benchmark").json()
    first, deep = body["offset_first_ms"], body["offset_deep_ms"]
    assert deep > first * 10, body
    return f"首页 {first}ms → 深页 {deep}ms（{deep / first:.0f}×）"


def check_keyset_is_flat() -> str:
    """游标深页耗时与首页同量级。"""
    with client() as c:
        body = c.get("/events/benchmark").json()
    first, deep = body["keyset_first_ms"], body["keyset_deep_ms"]
    assert deep < first * 5 + 0.5, body
    return f"首页 {first}ms → 深页 {deep}ms"


def check_count_cost() -> str:
    """`COUNT(*)` 是全表扫描，有明显耗时（10 万行约 3~7ms）。"""
    with client() as c:
        body = c.get("/events/benchmark").json()
    assert body["count_ms"] > 0, body
    return f'{body["count_ms"]}ms'


CHECKS = [
    ("数据与索引", check_rows_and_index),
    ("偏移首页", check_offset_first_page),
    ("偏移深页", check_offset_deep_page),
    ("游标首页一致", check_cursor_first_equals_offset),
    ("游标翻页无缝", check_cursor_pagination_no_gap),
    ("游标最后一页", check_cursor_last_page),
    ("limit 边界", check_limit_bounds),
    ("offset 负数", check_offset_negative),
    ("非法游标", check_bad_cursor),
    ("索引执行计划", check_explain_uses_index),
    ("无索引执行计划", check_explain_unindexed),
    ("深页偏移变慢", check_offset_deep_is_slow),
    ("游标耗时恒定", check_keyset_is_flat),
    ("COUNT 代价", check_count_cost),
]


def run() -> int:
    failures = 0
    for name, func in CHECKS:
        try:
            print(f"[PASS] {name} -> {func()}")
        except Exception as exc:  # noqa: BLE001 - 验收脚本要报告任何失败
            failures += 1
            print(f"[FAIL] {name} -> {type(exc).__name__}: {exc}")
    DB_FILE.unlink(missing_ok=True)  # 11MB 的测试数据不留在临时目录
    print(f"\n结果：{len(CHECKS) - failures}/{len(CHECKS)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())