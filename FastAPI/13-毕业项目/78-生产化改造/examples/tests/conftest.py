"""【要点】环境变量必须在导入 `main` 之前设置，conftest 是最早的钩子。"""

import atexit
import os
import shutil
import sqlite3
import tempfile

TMP_DIR = tempfile.mkdtemp(prefix="ch78_test_")
atexit.register(shutil.rmtree, TMP_DIR, ignore_errors=True)

os.environ["APP_DB_PATH"] = os.path.join(TMP_DIR, "test.db")
os.environ["APP_TOKEN"] = "test-token"
os.environ["APP_LOG_LEVEL"] = "ERROR"
os.environ["APP_ENV"] = "test"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from db import init_db  # noqa: E402

AUTH = {"Authorization": "Bearer test-token"}


def reset_db() -> None:
    init_db(main.settings)
    with sqlite3.connect(main.settings.db_path) as conn:
        conn.execute("DELETE FROM todos")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'todos'")


@pytest.fixture
def client():
    reset_db()
    with TestClient(main.app, raise_server_exceptions=False) as test_client:
        yield test_client
    reset_db()


@pytest.fixture
def auth() -> dict[str, str]:
    return dict(AUTH)