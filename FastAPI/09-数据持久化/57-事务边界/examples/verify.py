"""第 57 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402

import db  # noqa: E402
import main  # noqa: E402


def names(client: TestClient) -> list[str]:
    return [item["name"] for item in client.get("/items").json()]


def check_create_commits() -> str:
    """成功路径：commit 后数据可见。"""
    db.EVENTS.clear()
    with TestClient(main.app) as c:
        assert c.post("/items", json={"name": "a", "price": 1}).status_code == 201
    assert db.EVENTS[:3] == ["db:begin", "db:commit", "db:close"], db.EVENTS
    return "begin → commit → close"


def check_batch_all_ok() -> str:
    """批量全部合法 → 全部落库。"""
    with TestClient(main.app) as c:
        r = c.post(
            "/items/batch",
            json=[{"name": "b", "price": 2}, {"name": "c", "price": 3}],
        )
        assert r.status_code == 201, (r.status_code, r.text)
        assert names(c) == ["b", "c"], names(c)
    return "b,c"


def check_batch_atomic_rollback() -> str:
    """批量中途冲突 → 409，**前面写的也回滚**（原子）。"""
    db.EVENTS.clear()
    with TestClient(main.app, raise_server_exceptions=False) as c:
        c.post("/items", json={"name": "a", "price": 1})
        db.EVENTS.clear()
        r = c.post(
            "/items/batch",
            json=[{"name": "d", "price": 4}, {"name": "a", "price": 5}],
        )
        assert r.status_code == 409, (r.status_code, r.text)
        events = list(db.EVENTS)
        remaining = names(c)
    assert remaining == ["a"], remaining
    assert "db:rollback" in events, events
    return f"409，d 被回滚，剩余 {remaining}"


def check_batch_rollback_events() -> str:
    """失败路径走 rollback，不走 commit。"""
    db.EVENTS.clear()
    with TestClient(main.app) as c:
        c.post("/items/batch", json=[{"name": "x", "price": 1}])
        db.EVENTS.clear()
        c.post("/items/batch", json=[{"name": "y", "price": 1}, {"name": "x", "price": 1}])
        events = list(db.EVENTS)
    assert events[:3] == ["db:begin", "db:rollback", "db:close"], events
    assert "db:commit" not in events, events
    return "begin → rollback → close"


def check_uncaught_exception_rollback() -> str:
    """未捕获异常 → 500 + 回滚。"""
    with TestClient(main.app, raise_server_exceptions=False) as c:
        c.post("/items", json={"name": "keep", "price": 1})
        r = c.post("/items/crash", json={"name": "vanish", "price": 9})
        assert r.status_code == 500, (r.status_code, r.text)
        assert names(c) == ["keep"], names(c)
    return "500，vanish 未落库"


def check_http_exception_rollback() -> str:
    """`HTTPException(418)` 同样触发回滚。"""
    with TestClient(main.app, raise_server_exceptions=False) as c:
        r = c.post("/items/teapot", json={"name": "cup", "price": 1})
        assert r.status_code == 418, (r.status_code, r.text)
        assert r.json() == {"detail": "我是茶壶"}, r.json()
        assert names(c) == [], names(c)
    return "418，cup 未落库"


def check_domain_handler_409() -> str:
    """领域异常由全局 handler 翻译，不在路由里 try/except。"""
    with TestClient(main.app) as c:
        c.post("/items", json={"name": "dup", "price": 1})
        r = c.post("/items", json={"name": "dup", "price": 2})
        assert r.status_code == 409, (r.status_code, r.text)
        assert r.json()["detail"] == "名称已存在：dup", r.json()
    return "409 来自 exception_handler"


def check_audit_same_transaction() -> str:
    """主表与审计表在同一事务里写，数量一致。"""
    with TestClient(main.app) as c:
        c.post("/items", json={"name": "a", "price": 1})
        c.post("/items", json={"name": "b", "price": 2})
        assert c.get("/items/_/audit").json()["notes"] == ["create:a", "create:b"]
    return "2 条审计"


def check_audit_rollback() -> str:
    """回滚时审计也不留。"""
    with TestClient(main.app, raise_server_exceptions=False) as c:
        c.post("/items", json={"name": "a", "price": 1})
        c.post("/items/batch", json=[{"name": "z", "price": 1}, {"name": "a", "price": 1}])
        assert c.get("/items/_/audit").json()["notes"] == ["create:a"]
    return "审计只剩成功那条"


def check_repository_has_no_commit() -> str:
    """仓储层不提交事务（边界在依赖层）。"""
    source = (HERE / "repository.py").read_text(encoding="utf-8")
    assert ".commit()" not in source, "仓储里出现了 commit"
    assert "rollback" not in source, "仓储里出现了 rollback"
    return "无 commit / rollback"


def check_get_db_has_all_three() -> str:
    """`get_db` 三件事齐全。"""
    source = (HERE / "db.py").read_text(encoding="utf-8")
    for token in ("conn.commit()", "conn.rollback()", "conn.close()"):
        assert token in source, token
    return "commit / rollback / close"


def check_isolation_between_connections() -> str:
    """未提交前另一连接看不到；提交后可见。"""
    db.init_db()
    writer = db.connect()
    reader = db.connect()
    try:
        writer.execute("DELETE FROM items")
        writer.commit()
        writer.execute("INSERT INTO items (name, price) VALUES ('tx', 1)")
        invisible = reader.execute("SELECT COUNT(*) FROM items WHERE name = 'tx'").fetchone()[0]
        assert invisible == 0, invisible
        writer.commit()
        reader.rollback()  # 结束读事务，拿到新快照
        visible = reader.execute("SELECT COUNT(*) FROM items WHERE name = 'tx'").fetchone()[0]
        assert visible == 1, visible
    finally:
        writer.close()
        reader.close()
    return "提交前 0，提交后 1"


def check_yield_cleanup_order() -> str:
    """两个 `yield` 依赖：后进先出（marker 先 close，db 后 close）。"""
    db.EVENTS.clear()
    with TestClient(main.app) as c:
        assert c.get("/items/_/marker").status_code == 200
        events = list(db.EVENTS)
    assert events == [
        "db:begin",
        "marker:begin",
        "marker:end",
        "marker:close",
        "db:commit",
        "db:close",
    ], events
    return " → ".join(events)


def check_dependency_cache_single_connection() -> str:
    """同一请求里 `get_db` 只执行一次（依赖缓存）。"""
    db.EVENTS.clear()
    with TestClient(main.app) as c:
        c.get("/items/_/marker")
        events = list(db.EVENTS)
    assert events.count("db:begin") == 1, events
    return "db:begin 出现 1 次"


CHECKS = [
    ("成功提交", check_create_commits),
    ("批量全成功", check_batch_all_ok),
    ("批量原子回滚", check_batch_atomic_rollback),
    ("失败走 rollback", check_batch_rollback_events),
    ("未捕获异常回滚", check_uncaught_exception_rollback),
    ("HTTPException 回滚", check_http_exception_rollback),
    ("领域异常 handler", check_domain_handler_409),
    ("审计同事务", check_audit_same_transaction),
    ("审计随事务回滚", check_audit_rollback),
    ("仓储无 commit", check_repository_has_no_commit),
    ("get_db 三要素", check_get_db_has_all_three),
    ("连接间隔离", check_isolation_between_connections),
    ("yield 清理顺序", check_yield_cleanup_order),
    ("依赖缓存单连接", check_dependency_cache_single_connection),
]


def run() -> int:
    failures = 0
    for name, func in CHECKS:
        try:
            print(f"[PASS] {name} -> {func()}")
        except Exception as exc:  # noqa: BLE001 - 验收脚本要报告任何失败
            failures += 1
            print(f"[FAIL] {name} -> {type(exc).__name__}: {exc}")
    db.DB_FILE.unlink(missing_ok=True)
    print(f"\n结果：{len(CHECKS) - failures}/{len(CHECKS)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())