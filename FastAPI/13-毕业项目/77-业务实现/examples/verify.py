"""第 77 章 · 自动验收。运行：python verify.py

21 项覆盖：CRUD 全路径、分页、三类过滤、鉴权边界、四种错误契约、文档完整性。
"""

import sys
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from security import DEMO_TOKEN  # noqa: E402
from store import store  # noqa: E402

TOKEN_HEADER = {"Authorization": f"Bearer {DEMO_TOKEN}"}
BASE = "/api/v1/todos"
SEED = 3  # `store.reset()` 预置 3 条


def client() -> TestClient:
    store.reset()
    return TestClient(main.app, raise_server_exceptions=False)


def check_create() -> str:
    """201 + Location + 完整 body。"""
    with client() as c:
        response = c.post(BASE, json={"title": "买牛奶", "priority": "high"}, headers=TOKEN_HEADER)
    body = response.json()
    assert response.status_code == 201, response.status_code
    assert response.headers["location"] == f"{BASE}/{body['id']}", response.headers
    assert body["title"] == "买牛奶", body
    assert body["done"] is False, body
    assert body["priority"] == "high", body
    return f"201 / id={body['id']} / Location"


def check_create_increments_total() -> str:
    """创建后 total +1。"""
    with client() as c:
        before = c.get(BASE).json()["total"]
        c.post(BASE, json={"title": "新任务"}, headers=TOKEN_HEADER)
        after = c.get(BASE).json()["total"]
    assert (before, after) == (SEED, SEED + 1), (before, after)
    return f"{before} → {after}"


def check_page_envelope() -> str:
    """分页信封 5 个键齐全。"""
    with client() as c:
        body = c.get(BASE).json()
    assert set(body) == {"items", "total", "page", "size", "pages"}, body.keys()
    assert (body["page"], body["size"], body["total"], body["pages"]) == (1, 10, SEED, 1), body
    return "items/total/page/size/pages"


def check_pagination() -> str:
    """size=2 → pages=2，第二页 1 条。"""
    with client() as c:
        first = c.get(BASE, params={"page": 1, "size": 2}).json()
        second = c.get(BASE, params={"page": 2, "size": 2}).json()
    assert first["pages"] == 2, first
    assert len(first["items"]) == 2, first
    assert len(second["items"]) == 1, second
    assert [item["id"] for item in first["items"]] == [1, 2], first
    return "1,2 | 3"


def check_page_out_of_range() -> str:
    """越界页返回空列表但不报错。"""
    with client() as c:
        body = c.get(BASE, params={"page": 99}).json()
    assert body["items"] == [], body
    assert body["total"] == SEED, body
    return f"items=[] / total={SEED}"


def check_filter_done() -> str:
    """`?done=true` 只返回已完成的。"""
    with client() as c:
        body = c.get(BASE, params={"done": True}).json()
    assert [item["id"] for item in body["items"]] == [2], body
    assert all(item["done"] for item in body["items"]), body
    return "只剩 id=2"


def check_filter_priority() -> str:
    """`?priority=high` 只返回高优先级。"""
    with client() as c:
        body = c.get(BASE, params={"priority": "high"}).json()
    assert {item["priority"] for item in body["items"]} == {"high"}, body
    return f"{len(body['items'])} 条 high"


def check_filter_q_case_insensitive() -> str:
    """`?q=` 关键字不区分大小写。"""
    with client() as c:
        lower = c.get(BASE, params={"q": "verify"}).json()
        upper = c.get(BASE, params={"q": "VERIFY"}).json()
    assert [item["id"] for item in lower["items"]] == [2], lower
    assert [item["id"] for item in upper["items"]] == [2], upper
    return "verify / VERIFY 同结果"


def check_detail() -> str:
    """详情 200 + 字段齐全。"""
    with client() as c:
        body = c.get(f"{BASE}/1").json()
    assert set(body) == {"id", "title", "done", "priority", "created_at"}, body
    assert body["id"] == 1, body
    return body["title"]


def check_detail_404_contract() -> str:
    """404 走统一契约。"""
    with client() as c:
        response = c.get(f"{BASE}/999")
    body = response.json()
    assert response.status_code == 404, response.status_code
    assert body["error"]["code"] == "not_found", body
    assert "999" in body["error"]["message"], body
    return body["error"]["code"]


def check_patch_partial() -> str:
    """部分更新：只改 done，title 不变。"""
    with client() as c:
        before = c.get(f"{BASE}/1").json()
        after = c.patch(f"{BASE}/1", json={"done": True}, headers=TOKEN_HEADER).json()
    assert after["done"] is True, after
    assert after["title"] == before["title"], (before, after)
    assert after["priority"] == before["priority"], (before, after)
    return "done 变、其余不变"


def check_patch_404() -> str:
    with client() as c:
        response = c.patch(f"{BASE}/999", json={"done": True}, headers=TOKEN_HEADER)
    assert response.status_code == 404, response.status_code
    assert response.json()["error"]["code"] == "not_found", response.json()
    return "404 not_found"


def check_delete_204() -> str:
    """204 无 body。"""
    with client() as c:
        response = c.delete(f"{BASE}/1", headers=TOKEN_HEADER)
        remaining = c.get(f"{BASE}/1")
    assert response.status_code == 204, response.status_code
    assert response.text == "", repr(response.text)
    assert remaining.status_code == 404, remaining.status_code
    return "204 + 后续 404"


def check_delete_404() -> str:
    with client() as c:
        response = c.delete(f"{BASE}/999", headers=TOKEN_HEADER)
    assert response.status_code == 404, response.status_code
    return "404"


def check_write_requires_token() -> str:
    """写操作无令牌 → 401 + 契约 + WWW-Authenticate。"""
    with client() as c:
        response = c.post(BASE, json={"title": "x"})
    assert response.status_code == 401, response.status_code
    assert response.json()["error"]["code"] == "unauthorized", response.json()
    assert "bearer" in response.headers.get("www-authenticate", "").lower(), response.headers
    return "401 / unauthorized"


def check_write_rejects_bad_token() -> str:
    """错误令牌同样 401。"""
    with client() as c:
        response = c.post(BASE, json={"title": "x"}, headers={"Authorization": "Bearer nope"})
    assert response.status_code == 401, response.status_code
    return "401"


def check_read_is_public() -> str:
    """读操作不需要令牌。"""
    with client() as c:
        assert c.get(BASE).status_code == 200
        assert c.get(f"{BASE}/1").status_code == 200
        assert c.get(f"{BASE}/stats").status_code == 200
    return "列表/详情/统计 全 200"


def check_422_contract() -> str:
    """422 收敛成 `details.fields`。"""
    with client() as c:
        response = c.post(BASE, json={"title": ""}, headers=TOKEN_HEADER)
    body = response.json()
    assert response.status_code == 422, response.status_code
    assert body["error"]["code"] == "validation_error", body
    fields = body["error"]["details"]["fields"]
    assert fields[0]["loc"] == "body.title", fields
    assert fields[0]["type"] == "string_too_short", fields
    return "validation_error / body.title"


def check_query_validation() -> str:
    """query 越界也走同一契约。"""
    with client() as c:
        for params in ({"page": 0}, {"size": 101}):
            response = c.get(BASE, params=params)
            assert response.status_code == 422, (params, response.status_code)
            locs = [field["loc"] for field in response.json()["error"]["details"]["fields"]]
            assert any(loc.startswith("query.") for loc in locs), locs
    return "page=0 / size=101 → 422"


def check_stats() -> str:
    """统计端点不被 `/{todo_id}` 吞掉。"""
    with client() as c:
        body = c.get(f"{BASE}/stats").json()
    assert body["total"] == SEED, body
    assert (body["done"], body["pending"]) == (1, 2), body
    assert set(body["by_priority"]) == {"low", "medium", "high"}, body
    return f"total={body['total']} done={body['done']}"


def check_500_contract() -> str:
    """500 不泄露内部信息。"""
    with client() as c:
        response = c.get("/boom")
    body = response.json()
    assert response.status_code == 500, response.status_code
    assert body["error"]["code"] == "internal_error", body
    assert "内部炸了" not in response.text, response.text
    assert "RuntimeError" not in response.text, response.text
    return "internal_error / 无堆栈"


def check_docs_complete() -> str:
    """`/docs` 可用，5 条路径，每操作有 summary。"""
    with client() as c:
        assert c.get("/docs").status_code == 200
        schema = c.get("/openapi.json").json()
    paths = sorted(schema["paths"])
    assert paths == ["/api/v1/todos", "/api/v1/todos/stats", "/api/v1/todos/{todo_id}", "/events", "/healthz"], paths
    missing = [
        f"{method} {path}"
        for path, operations in schema["paths"].items()
        for method, operation in operations.items()
        if not operation.get("summary")
    ]
    assert not missing, missing
    return f"{len(paths)} 条路径 / summary 齐全"


CHECKS: list[tuple[str, Any]] = [
    ("创建 201", check_create),
    ("创建后 total+1", check_create_increments_total),
    ("分页信封", check_page_envelope),
    ("分页切分", check_pagination),
    ("越界页", check_page_out_of_range),
    ("过滤 done", check_filter_done),
    ("过滤 priority", check_filter_priority),
    ("过滤 q", check_filter_q_case_insensitive),
    ("详情", check_detail),
    ("详情 404 契约", check_detail_404_contract),
    ("部分更新", check_patch_partial),
    ("更新 404", check_patch_404),
    ("删除 204", check_delete_204),
    ("删除 404", check_delete_404),
    ("写操作要令牌", check_write_requires_token),
    ("错令牌 401", check_write_rejects_bad_token),
    ("读操作公开", check_read_is_public),
    ("422 契约", check_422_contract),
    ("query 校验", check_query_validation),
    ("统计", check_stats),
    ("500 契约", check_500_contract),
    ("文档完整", check_docs_complete),
]


def run() -> int:
    store.reset()
    failures = 0
    for name, func in CHECKS:
        try:
            print(f"[PASS] {name} -> {func()}")
        except Exception as exc:  # noqa: BLE001 - 验收脚本要报告任何失败
            failures += 1
            print(f"[FAIL] {name} -> {type(exc).__name__}: {exc}")
    store.reset()
    print(f"\n结果：{len(CHECKS) - failures}/{len(CHECKS)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())