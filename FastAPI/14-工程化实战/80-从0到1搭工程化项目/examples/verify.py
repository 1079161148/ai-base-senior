"""第 80 章 · 12 块积木验收。运行：python verify.py

每一块积木都能独立验证：从骨架、配置、迁移开始，到装配、交付物结束。
第 11 步跑架构守卫 —— 它是「分层没写乱」的唯一证据。
"""

import logging
import os
import re
import shutil
import sqlite3
import sys
import tempfile
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

TMP_DIR = tempfile.mkdtemp(prefix="ch80_")
DB_PATH = os.path.join(TMP_DIR, "verify.db")
os.environ["APP_DB_PATH"] = DB_PATH
os.environ["APP_TOKEN"] = "verify-token-80"
os.environ["APP_ENV"] = "test"
os.environ["APP_LOG_LEVEL"] = "ERROR"
os.environ["APP_SLOW_MS"] = "1"

from fastapi.testclient import TestClient  # noqa: E402

from app.core.config import Settings, get_settings  # noqa: E402
from app.core.exceptions import DuplicateTitle, NotFound  # noqa: E402
from app.db.migrate import applied_versions, migrate  # noqa: E402
from app.db.session import get_conn  # noqa: E402
from app.main import create_app  # noqa: E402
from app.repositories.note_repo import NoteRepo  # noqa: E402
from app.services.note_service import NoteService  # noqa: E402
from scripts.arch_guard import violations  # noqa: E402

BASE = "/api/v1/notes"
AUTH = {"Authorization": "Bearer verify-token-80"}
CTX: dict[str, Any] = {}


class ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def fresh_settings(path: str | None = None) -> Settings:
    return Settings(
        _env_file=None,
        db_path=path or DB_PATH,
        token="verify-token-80",
        env="test",
        log_level="ERROR",
        slow_ms=1,
    )


def reset(settings: Settings) -> None:
    with sqlite3.connect(settings.db_path) as conn:
        conn.execute("DELETE FROM notes")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'notes'")


def seed(client: TestClient, count: int = 3) -> None:
    for index in range(count):
        client.post(BASE, json={"title": f"笔记{index}", "body": "x"}, headers=AUTH)


# ============================================================
# 1 骨架
# ============================================================
EXPECTED = [
    "app/__init__.py",
    "app/main.py",
    "app/core/config.py",
    "app/core/errors.py",
    "app/core/exceptions.py",
    "app/core/logging.py",
    "app/core/middleware.py",
    "app/db/session.py",
    "app/db/migrate.py",
    "app/db/migrations/0001_init.sql",
    "app/db/migrations/0002_add_pinned.sql",
    "app/schemas/note.py",
    "app/repositories/note_repo.py",
    "app/services/note_service.py",
    "app/api/deps.py",
    "app/api/v1/router.py",
    "app/api/v1/notes.py",
    "tests/conftest.py",
    "tests/test_service.py",
    "tests/test_api.py",
    "tests/test_architecture.py",
    "scripts/arch_guard.py",
    "scripts/seed.py",
    "Makefile",
    "Dockerfile",
    ".env.example",
    "pyproject.toml",
]


def step_1_skeleton() -> str:
    missing = [name for name in EXPECTED if not (HERE / name).exists()]
    assert not missing, f"缺少 {len(missing)} 个文件：{missing[:3]}"
    layers = sorted({name.split("/")[1] for name in EXPECTED if name.startswith("app/") and name.count("/") > 1})
    return f"{len(EXPECTED)} 个文件 / {len(layers)} 层：{','.join(layers)}"


# ============================================================
# 2 配置
# ============================================================
def step_2_config() -> str:
    get_settings.cache_clear()
    loaded = get_settings()
    assert loaded.db_path == DB_PATH, loaded.db_path
    assert loaded.token.get_secret_value() == "verify-token-80"
    assert "verify-token-80" not in repr(loaded), "密钥未掩码"
    assert loaded.is_prod is False
    return f"env={loaded.env} / db={Path(loaded.db_path).name} / 密钥已掩码"


# ============================================================
# 3 迁移
# ============================================================
def step_3_migrate() -> str:
    settings = fresh_settings(os.path.join(TMP_DIR, "m3.db"))
    first = migrate(settings)
    second = migrate(settings)
    assert first == ["0001_init", "0002_add_pinned"], first
    assert second == [], second
    assert applied_versions(settings) == first
    return f"首次 {len(first)} 个 / 二次 {len(second)} 个 / 记录 {len(applied_versions(settings))} 条"


def step_4_incremental() -> str:
    settings = fresh_settings(os.path.join(TMP_DIR, "m4.db"))
    migrate(settings)
    with sqlite3.connect(settings.db_path) as conn:
        columns = [row[1] for row in conn.execute("PRAGMA table_info(notes)")]
    assert "pinned" in columns, columns
    assert "title" in columns, columns
    return f"列：{','.join(columns)}"


# ============================================================
# 5 事务
# ============================================================
def step_5_transaction() -> str:
    settings = fresh_settings(os.path.join(TMP_DIR, "m5.db"))
    migrate(settings)

    # 正常路径：生成器自然结束 → commit
    generator = get_conn(settings)
    conn = next(generator)
    conn.execute("INSERT INTO notes (title, body, created_at) VALUES (?, ?, ?)", ("提交", "", "2026-01-01T00:00:00+00:00"))
    try:
        next(generator)
    except StopIteration:
        pass
    with sqlite3.connect(settings.db_path) as probe:
        committed = probe.execute("SELECT COUNT(*) FROM notes").fetchone()[0]
    assert committed == 1, committed

    # 异常路径：throw → rollback
    generator = get_conn(settings)
    conn = next(generator)
    conn.execute("INSERT INTO notes (title, body, created_at) VALUES (?, ?, ?)", ("回滚", "", "2026-01-01T00:00:00+00:00"))
    try:
        generator.throw(RuntimeError("boom"))
    except RuntimeError:
        pass
    with sqlite3.connect(settings.db_path) as probe:
        titles = [row[0] for row in probe.execute("SELECT title FROM notes")]
    assert titles == ["提交"], titles
    return "提交 1 条 / 回滚后仍 1 条"


# ============================================================
# 6 仓储
# ============================================================
def step_6_repository() -> str:
    settings = fresh_settings(os.path.join(TMP_DIR, "m6.db"))
    migrate(settings)
    with sqlite3.connect(settings.db_path) as conn:
        conn.row_factory = sqlite3.Row
        repo = NoteRepo(conn)
        created = repo.create(title="仓储", body="不碰 HTTP")
        fetched = repo.get(created["id"])
        rows, total = repo.list(limit=10, offset=0)
        assert fetched is not None and total == 1 and len(rows) == 1
        assert repo.exists_title("仓储") is True
        assert repo.exists_title("仓储", exclude_id=created["id"]) is False
        assert repo.delete(created["id"]) is True
        assert repo.get(created["id"]) is None
        conn.commit()
    return "create/get/list/exists/delete 全通"


# ============================================================
# 7 服务层
# ============================================================
def step_7_service() -> str:
    settings = fresh_settings(os.path.join(TMP_DIR, "m7.db"))
    migrate(settings)
    with sqlite3.connect(settings.db_path) as conn:
        conn.row_factory = sqlite3.Row
        service = NoteService(NoteRepo(conn))
        service.create(title="A")
        try:
            service.create(title="A")
            raise AssertionError("重复标题未拦截")
        except DuplicateTitle as exc:
            assert exc.status_code == 409
        try:
            service.get(999)
            raise AssertionError("缺失未拦截")
        except NotFound as exc:
            assert exc.status_code == 404
        assert service.toggle_pin(1)["pinned"] is True
        assert service.toggle_pin(1)["pinned"] is False
        conn.commit()
    return "409 / 404 / toggle_pin 全通"


# ============================================================
# 8 接口
# ============================================================
def step_8_api() -> str:
    settings = fresh_settings()
    migrate(settings)
    reset(settings)
    with TestClient(create_app(settings), raise_server_exceptions=False) as client:
        created = client.post(BASE, json={"title": "买牛奶", "body": "两盒"}, headers=AUTH)
        assert created.status_code == 201, created.status_code
        note_id = created.json()["id"]
        assert created.headers["location"] == f"{BASE}/{note_id}", created.headers
        seed(client, 2)
        listed = client.get(BASE, params={"size": 2}).json()
        assert (listed["total"], listed["pages"]) == (3, 2), listed
        assert client.get(f"{BASE}/{note_id}").json()["body"] == "两盒"
        patched = client.patch(f"{BASE}/{note_id}", json={"body": "改"}, headers=AUTH).json()
        assert patched["body"] == "改" and patched["title"] == "买牛奶"
        assert client.delete(f"{BASE}/{note_id}", headers=AUTH).status_code == 204
        assert client.get(f"{BASE}/{note_id}").status_code == 404
    return "201+Location / 分页 / 详情 / 部分更新 / 204"


# ============================================================
# 9 错误契约
# ============================================================
def step_9_errors() -> str:
    settings = fresh_settings()
    migrate(settings)
    reset(settings)
    app = create_app(settings)

    def boom() -> None:
        raise RuntimeError("内部炸了：不该出现在响应里")

    app.add_api_route("/__boom", boom, include_in_schema=False)

    with TestClient(app, raise_server_exceptions=False) as client:
        client.post(BASE, json={"title": "同名"}, headers=AUTH)
        not_found = client.get(f"{BASE}/999")
        conflict = client.post(BASE, json={"title": "同名"}, headers=AUTH)
        invalid = client.post(BASE, json={"title": ""}, headers=AUTH)
        crashed = client.get("/__boom")

    for response, code in ((not_found, "not_found"), (conflict, "duplicate_title"), (invalid, "validation_error")):
        body = response.json()
        assert set(body) == {"error"}, body
        assert body["error"]["code"] == code, body
    assert invalid.json()["error"]["details"]["fields"][0]["loc"] == "body.title"
    assert crashed.status_code == 500
    assert crashed.json()["error"]["code"] == "internal_error"
    assert "内部炸了" not in crashed.text and "RuntimeError" not in crashed.text
    return "404 / 409 / 422 / 500 同一信封"


# ============================================================
# 10 可观测
# ============================================================
def step_10_observability() -> str:
    settings = fresh_settings()
    migrate(settings)
    reset(settings)
    handler = ListHandler()
    logger = logging.getLogger("app.request")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        with TestClient(create_app(settings)) as client:
            auto = client.get(BASE).headers
            echoed = client.get(BASE, headers={"X-Request-ID": "trace-80"}).headers
    finally:
        logger.removeHandler(handler)

    assert len(auto["x-request-id"]) == 8, auto
    assert echoed["x-request-id"] == "trace-80"
    assert echoed["x-app-version"] == settings.version
    assert float(echoed["x-elapsed-ms"]) >= 0
    messages = [record.getMessage() for record in handler.records]
    assert any("method=GET" in m and f"path={BASE}" in m and "status=200" in m for m in messages), messages
    assert any(getattr(r, "request_id", "-") != "-" for r in handler.records)
    return "请求 ID / 版本头 / 耗时头 / 一行日志"


# ============================================================
# 11 架构守卫
# ============================================================
def step_11_arch() -> str:
    problems = violations()
    assert problems == [], problems
    for name in ("test_service.py", "test_api.py", "test_architecture.py"):
        assert (HERE / "tests" / name).exists(), name
    return f"{len(list((HERE / 'app').rglob('*.py')))} 个源文件依赖方向合法"


# ============================================================
# 12 交付物
# ============================================================
def step_12_delivery() -> str:
    makefile = (HERE / "Makefile").read_text(encoding="utf-8")
    for target in ("install:", "run:", "test:", "verify:", "migrate:", "seed:"):
        assert target in makefile, target

    dockerfile = (HERE / "Dockerfile").read_text(encoding="utf-8")
    assert "--reload" not in dockerfile, "镜像里不能有热重载"
    assert re.search(r"^USER\s+\S+", dockerfile, re.MULTILINE), "缺少非 root USER"
    assert "HEALTHCHECK" in dockerfile, "缺少 HEALTHCHECK"
    assert "--workers" in dockerfile, "缺少多 worker"

    env_example = (HERE / ".env.example").read_text(encoding="utf-8")
    assert "APP_TOKEN" in env_example, ".env.example 缺少 APP_TOKEN"
    assert not (HERE / ".env").exists(), ".env 不应进仓库"
    return "Makefile 6 目标 / 镜像非 root+探针 / .env.example 齐全"


STEPS: list[tuple[str, str, Callable[[], str]]] = [
    ("1", "骨架", step_1_skeleton),
    ("2", "配置", step_2_config),
    ("3", "迁移", step_3_migrate),
    ("4", "增量迁移", step_4_incremental),
    ("5", "事务", step_5_transaction),
    ("6", "仓储", step_6_repository),
    ("7", "服务", step_7_service),
    ("8", "接口", step_8_api),
    ("9", "错误契约", step_9_errors),
    ("10", "可观测", step_10_observability),
    ("11", "架构守卫", step_11_arch),
    ("12", "交付物", step_12_delivery),
]


def run() -> int:
    failures = 0
    try:
        for number, name, step in STEPS:
            try:
                print(f"[PASS] 积木 {number} {name} -> {step()}")
            except Exception as exc:  # noqa: BLE001 - 验收脚本要报告任何失败
                failures += 1
                print(f"[FAIL] 积木 {number} {name} -> {type(exc).__name__}: {exc}")
    finally:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    print(f"\n结果：{len(STEPS) - failures}/{len(STEPS)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())