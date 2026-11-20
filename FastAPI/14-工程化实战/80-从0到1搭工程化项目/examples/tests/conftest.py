"""测试夹具：每个用例一个独立库，互不污染。

【要点】`_env_file=None` 让测试不受开发者本地 `.env` 影响。
"""

import sqlite3
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.core.config import Settings
from app.db.migrate import migrate
from app.main import create_app
from app.repositories.note_repo import NoteRepo
from app.services.note_service import NoteService

AUTH = {"Authorization": "Bearer test-token"}


@pytest.fixture
def settings(tmp_path: Path) -> Settings:
    resolved = Settings(
        _env_file=None,
        db_path=str(tmp_path / "test.db"),
        token="test-token",
        env="test",
        log_level="ERROR",
    )
    migrate(resolved)
    return resolved


@pytest.fixture
def conn(settings: Settings):
    connection = sqlite3.connect(settings.db_path)
    connection.row_factory = sqlite3.Row
    yield connection
    connection.close()


@pytest.fixture
def service(conn) -> NoteService:
    return NoteService(NoteRepo(conn))


@pytest.fixture
def client(settings: Settings):
    with TestClient(create_app(settings), raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def auth() -> dict[str, str]:
    return dict(AUTH)