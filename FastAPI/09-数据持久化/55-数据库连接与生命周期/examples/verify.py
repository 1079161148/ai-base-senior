"""第 55 章 · 自动验收。运行：python verify.py"""

import asyncio
import sqlite3
import sys
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402


def check_with_triggers_lifespan() -> str:
    """`with TestClient(app)` 才会触发 lifespan。"""
    with TestClient(main.app) as c:
        body = c.get("/state").json()
        assert body["opened"] is True, body
    return "opened=True"


def check_schema_created_on_startup() -> str:
    """启动时 `CREATE TABLE IF NOT EXISTS` 已执行。"""
    with TestClient(main.app) as c:
        r = c.get("/items")
        assert r.status_code == 200, (r.status_code, r.text)
        assert r.json() == [], r.json()
    return "空表可查"


def check_create_item() -> str:
    """POST 返回 201 + 自增 id。"""
    with TestClient(main.app) as c:
        r = c.post("/items", json={"name": "键盘", "price": 299})
        assert r.status_code == 201, (r.status_code, r.text)
        body = r.json()
        assert body["id"] == 1 and body["name"] == "键盘", body
    return f'id={body["id"]}'


def check_list_items() -> str:
    """写入后能查到，且按 id 升序。"""
    with TestClient(main.app) as c:
        c.post("/items", json={"name": "a", "price": 1})
        c.post("/items", json={"name": "b", "price": 2})
        rows = c.get("/items").json()
        assert [row["name"] for row in rows] == ["a", "b"], rows
    return f"{len(rows)} 条"


def check_unique_violation_mapped_to_409() -> str:
    """`IntegrityError` 被翻译成 409，而不是 500。"""
    with TestClient(main.app) as c:
        c.post("/items", json={"name": "dup", "price": 1})
        r = c.post("/items", json={"name": "dup", "price": 2})
        assert r.status_code == 409, (r.status_code, r.text)
        assert "名称已存在" in r.json()["detail"], r.json()
    return "409 名称已存在"


def check_price_negative_422() -> str:
    """`Field(ge=0)` 在入库前就拦住。"""
    with TestClient(main.app) as c:
        r = c.post("/items", json={"name": "x", "price": -1})
        assert r.status_code == 422, (r.status_code, r.text)
    return "422"


def check_health_hits_db() -> str:
    """健康检查真的查了一次库。"""
    with TestClient(main.app) as c:
        c.post("/items", json={"name": "h", "price": 1})
        body = c.get("/health").json()
        assert body["status"] == "ok" and body["items"] == 1, body
    return f'items={body["items"]}'


def check_count_matches_list() -> str:
    """两个端点走同一连接，结果一致。"""
    with TestClient(main.app) as c:
        for i in range(3):
            c.post("/items", json={"name": f"n{i}", "price": i})
        assert c.get("/items/count").json()["count"] == 3
        assert len(c.get("/items").json()) == 3
    return "count=3"


def check_connection_closed_after_shutdown() -> str:
    """lifespan 退出后连接已关闭，再用抛 `ProgrammingError`。"""
    with TestClient(main.app) as c:
        c.get("/items")
        db = main.app.state.db
    assert main.app.state.db_opened is False
    try:
        db.execute("SELECT 1")
    except sqlite3.ProgrammingError as exc:
        assert "closed" in str(exc).lower(), exc
        return str(exc)
    raise AssertionError("连接未关闭")


def check_thread_affinity_error() -> str:
    """默认 `check_same_thread=True`：换线程用会抛 `ProgrammingError`。"""
    conn = sqlite3.connect(main.DB_FILE)

    def query() -> None:
        conn.execute("SELECT 1").fetchone()

    try:
        asyncio.run(asyncio.to_thread(query))
    except sqlite3.ProgrammingError as exc:
        assert "same thread" in str(exc), exc
        return str(exc)
    finally:
        conn.close()
    raise AssertionError("没有触发线程亲和错误")


def check_check_same_thread_false_works() -> str:
    """`check_same_thread=False` 时线程池里可用。"""
    conn = main.connect()
    try:
        value = asyncio.run(asyncio.to_thread(lambda: conn.execute("SELECT 1+1").fetchone()[0]))
        assert value == 2, value
        return f"线程池内 SELECT 1+1 = {value}"
    finally:
        conn.close()


def check_memory_db_not_shared() -> str:
    """`:memory:` 每个连接一个独立库，不是共享的。"""
    first = sqlite3.connect(":memory:")
    first.execute("CREATE TABLE t (x INTEGER)")
    second = sqlite3.connect(":memory:")
    try:
        second.execute("SELECT * FROM t")
    except sqlite3.OperationalError as exc:
        assert "no such table" in str(exc), exc
        return str(exc)
    finally:
        first.close()
        second.close()
    raise AssertionError("两个 :memory: 居然共享表")


def check_no_with_no_lifespan() -> str:
    """不用 `with` 时 lifespan 不执行：`started` 为 False，连接不会新建。"""
    probe = TestClient(main.app)
    body = probe.get("/state").json()
    assert body["opened"] is False, body
    assert main.app.state.started is False, main.app.state.started
    return f'opened=False, started=False'


def check_on_event_deprecated() -> str:
    """`@app.on_event` 已废弃，`lifespan` 是唯一推荐写法。"""
    legacy = FastAPI()

    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")

        @legacy.on_event("startup")
        def _legacy_hook() -> None:  # noqa: ANN202
            return None

    messages = [str(item.message) for item in caught]
    assert any("deprecated" in msg.lower() for msg in messages), messages
    return messages[0][:70] + "..."


CHECKS = [
    ("with 触发 lifespan", check_with_triggers_lifespan),
    ("启动建表", check_schema_created_on_startup),
    ("新增", check_create_item),
    ("列表", check_list_items),
    ("唯一冲突 → 409", check_unique_violation_mapped_to_409),
    ("负数 → 422", check_price_negative_422),
    ("健康检查碰库", check_health_hits_db),
    ("计数一致", check_count_matches_list),
    ("关闭后连接失效", check_connection_closed_after_shutdown),
    ("线程亲和报错", check_thread_affinity_error),
    ("check_same_thread=False", check_check_same_thread_false_works),
    (":memory: 不共享", check_memory_db_not_shared),
    ("无 with 无 lifespan", check_no_with_no_lifespan),
    ("on_event 已废弃", check_on_event_deprecated),
]


def run() -> int:
    failures = 0
    for name, func in CHECKS:
        try:
            print(f"[PASS] {name} -> {func()}")
        except AssertionError as exc:
            failures += 1
            print(f"[FAIL] {name} -> {exc}")
    main.DB_FILE.unlink(missing_ok=True)
    print(f"\n结果：{len(CHECKS) - failures}/{len(CHECKS)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())