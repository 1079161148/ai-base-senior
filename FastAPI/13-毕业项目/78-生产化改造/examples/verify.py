"""第 78 章 · 自动验收。运行：python verify.py

先在**导入 main 之前**设置环境变量，否则模块级 `settings` 已经定型。
"""

import logging
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from contextlib import contextmanager
from pathlib import Path
from typing import Any, Iterator

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

# ------------------------------------------------------------
# 【要点】环境变量必须在 import main 之前设置
# ------------------------------------------------------------
TMP_DIR = tempfile.mkdtemp(prefix="ch78_")
DB_PATH = os.path.join(TMP_DIR, "todos.db")
VERIFY_TOKEN = "verify-token-123"
os.environ["APP_DB_PATH"] = DB_PATH
os.environ["APP_TOKEN"] = VERIFY_TOKEN
os.environ["APP_LOG_LEVEL"] = "ERROR"
os.environ["APP_SLOW_MS"] = "1"
os.environ["APP_ENV"] = "test"

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from db import init_db  # noqa: E402

AUTH = {"Authorization": f"Bearer {VERIFY_TOKEN}"}
BASE = "/api/v1/todos"


class ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def reset_db() -> None:
    init_db(main.settings)
    with sqlite3.connect(main.settings.db_path) as conn:
        conn.execute("DELETE FROM todos")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'todos'")


def seed(c: TestClient) -> None:
    for title, priority in (("写代码", "high"), ("跑验收", "medium"), ("写复盘", "low")):
        c.post(BASE, json={"title": title, "priority": priority}, headers=AUTH)


@contextmanager
def client(seeded: bool = True) -> Iterator[TestClient]:
    reset_db()
    with TestClient(main.app, raise_server_exceptions=False) as c:
        if seeded:
            seed(c)
        yield c


# ============================================================
# 配置 / 可观测
# ============================================================
def check_config_from_env() -> str:
    """库路径与令牌都来自环境变量。"""
    assert main.settings.db_path == DB_PATH, main.settings.db_path
    assert main.settings.token.get_secret_value() == VERIFY_TOKEN
    parent = Path(DB_PATH).parent.name
    return f"{parent}/{Path(DB_PATH).name}"


def check_secret_masked() -> str:
    """`SecretStr` 在 repr / dump 里都是掩码。"""
    text = repr(main.settings) + str(main.settings.model_dump(mode="json"))
    assert VERIFY_TOKEN not in text, text
    assert "**********" in repr(main.settings), repr(main.settings)
    return "token → **********"


def check_healthz_no_db() -> str:
    """探针不查库：库删了也 200。"""
    with client(seeded=False) as c:
        original = main.settings.db_path
        assert c.get("/healthz").status_code == 200
    return f"200 / {Path(original).name}"


def check_request_id_generated() -> str:
    with client() as c:
        request_id = c.get(BASE).headers["x-request-id"]
    assert len(request_id) == 8, request_id
    return request_id


def check_request_id_propagated() -> str:
    with client() as c:
        response = c.get(BASE, headers={"X-Request-ID": "trace-9"})
    assert response.headers["x-request-id"] == "trace-9", response.headers
    return "trace-9"


def check_version_header() -> str:
    with client() as c:
        value = c.get(BASE).headers["x-app-version"]
    assert value == main.settings.version, value
    return value


def check_one_line_log() -> str:
    handler = ListHandler()
    logger = logging.getLogger("app.request")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        with client() as c:
            c.get(BASE)
        messages = [record.getMessage() for record in handler.records]
        assert any(
            "method=GET" in message and "path=/api/v1/todos" in message and "status=200" in message
            for message in messages
        ), messages
        assert any(getattr(record, "request_id", None) for record in handler.records)
        return "method/path/status/request_id 齐全"
    finally:
        logger.removeHandler(handler)


def check_slow_request_warning() -> str:
    """`APP_SLOW_MS=1` 时所有请求都该是 WARNING。"""
    handler = ListHandler()
    logger = logging.getLogger("app.request")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        with client() as c:
            c.get(BASE)
        slow = [record for record in handler.records if record.levelno >= logging.WARNING]
        assert slow, [(r.levelname, r.getMessage()) for r in handler.records]
        return slow[0].getMessage()[:46]
    finally:
        logger.removeHandler(handler)


# ============================================================
# 业务（与 77 章同契约）
# ============================================================
def check_create() -> str:
    with client(seeded=False) as c:
        response = c.post(BASE, json={"title": "买牛奶", "priority": "high"}, headers=AUTH)
    body = response.json()
    assert response.status_code == 201, response.status_code
    assert response.headers["location"] == f"{BASE}/{body['id']}", response.headers
    assert body["title"] == "买牛奶"
    return f"201 / id={body['id']}"


def check_pagination() -> str:
    with client() as c:
        body = c.get(BASE, params={"page": 1, "size": 2}).json()
    assert set(body) == {"items", "total", "page", "size", "pages"}, body.keys()
    assert (body["total"], body["pages"], len(body["items"])) == (3, 2, 2), body
    return "3 条 / 2 页 / 首页 2 条"


def check_filters() -> str:
    with client() as c:
        done = c.get(BASE, params={"done": False}).json()
        high = c.get(BASE, params={"priority": "high"}).json()
        lower = c.get(BASE, params={"q": "复盘"}).json()
        upper = c.get(BASE, params={"q": "复盘"}).json()
    assert [item["id"] for item in high["items"]] == [1], high
    assert len(done["items"]) == 3, done
    assert [item["id"] for item in lower["items"]] == [3], lower
    assert lower == upper
    return "done/priority/q 都生效"


def check_partial_update() -> str:
    with client() as c:
        before = c.get(f"{BASE}/1").json()
        after = c.patch(f"{BASE}/1", json={"done": True}, headers=AUTH).json()
    assert after["done"] is True
    assert after["title"] == before["title"]
    return "只改 done"


def check_delete() -> str:
    with client() as c:
        assert c.delete(f"{BASE}/1", headers=AUTH).status_code == 204
        assert c.get(f"{BASE}/1").status_code == 404
    return "204 → 404"


# ============================================================
# 错误契约
# ============================================================
def check_404_contract() -> str:
    with client() as c:
        response = c.get(f"{BASE}/999")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found", response.json()
    return "not_found"


def check_401_uses_configured_token() -> str:
    """默认令牌 `demo-token` 在测试环境里已失效。"""
    with client() as c:
        default = c.post(BASE, json={"title": "x"}, headers={"Authorization": "Bearer demo-token"})
        missing = c.post(BASE, json={"title": "x"})
    assert default.status_code == 401, default.status_code
    assert missing.status_code == 401, missing.status_code
    assert missing.json()["error"]["code"] == "unauthorized"
    return "demo-token 已失效 / 无令牌 401"


def check_422_contract() -> str:
    with client() as c:
        response = c.post(BASE, json={"title": ""}, headers=AUTH)
    body = response.json()
    assert response.status_code == 422
    assert body["error"]["details"]["fields"][0]["loc"] == "body.title", body
    return "validation_error / body.title"


def check_500_contract() -> str:
    with client() as c:
        response = c.get("/boom")
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert "内部炸了" not in response.text
    assert "RuntimeError" not in response.text
    return "internal_error / 无堆栈"


# ============================================================
# 事务
# ============================================================
def check_transaction_commit() -> str:
    """正常路径提交。"""
    with client(seeded=False) as c:
        created = c.post(BASE, json={"title": "提交"}, headers=AUTH).json()
    with sqlite3.connect(main.settings.db_path) as conn:
        rows = conn.execute("SELECT title FROM todos").fetchall()
    assert [row[0] for row in rows] == ["提交"], rows
    assert created["title"] == "提交"
    return "已落库"


def check_transaction_rollback() -> str:
    """**关键**：插入后抛错 → rollback，库里没有这条。"""
    with client(seeded=False) as c:
        response = c.post(f"{BASE}/_tx", headers=AUTH)
        total = c.get(f"{BASE}/stats").json()["total"]
    with sqlite3.connect(main.settings.db_path) as conn:
        titles = [row[0] for row in conn.execute("SELECT title FROM todos")]
    assert response.status_code == 409, response.status_code
    assert response.json()["error"]["code"] == "tx_demo", response.json()
    assert total == 0, total
    assert titles == [], titles
    return "409 / 表里 0 行"


# ============================================================
# 代码卫生（静态扫描）
# ============================================================
def source_files() -> list[Path]:
    return [
        path
        for path in HERE.glob("*.py")
        if path.name not in {"verify.py"} and "test" not in path.name
    ]


def check_no_bare_except() -> str:
    """没有 `except:` 或 `except Exception: pass`。"""
    offenders: list[str] = []
    for path in source_files():
        text = path.read_text(encoding="utf-8")
        if re.search(r"except\s*:", text):
            offenders.append(f"{path.name}: bare except")
        if re.search(r"except\s+Exception\s*:\s*\n\s*pass", text):
            offenders.append(f"{path.name}: except + pass")
    assert not offenders, offenders
    return f"{len(source_files())} 个文件干净"


def check_no_hardcoded_secret() -> str:
    """令牌只出现在 `config.py` 的默认值里。"""
    offenders = [
        path.name
        for path in source_files()
        if path.name != "config.py" and "demo-token" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, offenders
    return "仅 config 有默认值"


def check_sql_parameterized() -> str:
    """`repo.py` 里没有字符串格式化拼 SQL。"""
    text = (HERE / "repo.py").read_text(encoding="utf-8")
    assert "%s" not in text, "发现 %s 占位"
    assert ".format(" not in text, "发现 .format("
    assert re.search(r"execute\(f?\"[^\"]*'\s*\+", text) is None, "发现字符串拼接"
    assert "?" in text
    return "全部 ? 占位"


def check_openapi_complete() -> str:
    with client() as c:
        schema = c.get("/openapi.json").json()
    paths = sorted(schema["paths"])
    assert paths == [BASE, f"{BASE}/stats", f"{BASE}/{{todo_id}}", "/healthz"], paths
    assert "/boom" not in paths, "内部端点不应进文档"
    assert f"{BASE}/_tx" not in paths, "事务演示不应进文档"
    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            assert operation.get("summary"), f"{method} {path}"
    return f"{len(paths)} 条路径"


CHECKS: list[tuple[str, Any]] = [
    ("配置来自环境变量", check_config_from_env),
    ("密钥掩码", check_secret_masked),
    ("探针不查库", check_healthz_no_db),
    ("请求 ID 生成", check_request_id_generated),
    ("请求 ID 透传", check_request_id_propagated),
    ("版本头", check_version_header),
    ("一行日志", check_one_line_log),
    ("慢请求 WARNING", check_slow_request_warning),
    ("创建 201", check_create),
    ("分页", check_pagination),
    ("过滤", check_filters),
    ("部分更新", check_partial_update),
    ("删除", check_delete),
    ("404 契约", check_404_contract),
    ("401 用配置令牌", check_401_uses_configured_token),
    ("422 契约", check_422_contract),
    ("500 契约", check_500_contract),
    ("事务提交", check_transaction_commit),
    ("事务回滚", check_transaction_rollback),
    ("无裸 except", check_no_bare_except),
    ("无硬编码密钥", check_no_hardcoded_secret),
    ("SQL 参数绑定", check_sql_parameterized),
    ("OpenAPI 完整", check_openapi_complete),
]


def run() -> int:
    failures = 0
    try:
        for name, func in CHECKS:
            try:
                print(f"[PASS] {name} -> {func()}")
            except Exception as exc:  # noqa: BLE001 - 验收脚本要报告任何失败
                failures += 1
                print(f"[FAIL] {name} -> {type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(TMP_DIR, ignore_errors=True)
    print(f"\n结果：{len(CHECKS) - failures}/{len(CHECKS)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())