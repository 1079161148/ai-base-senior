"""第 76 章 · pytest 写法示范。

跑法：uv run pytest -q

【要点】探针测试要覆盖「依赖挂了」的分支，
        否则 503 分支永远没被验证过。
"""

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def client():
    main.reset()
    with TestClient(main.app) as test_client:
        yield test_client
    main.reset()


def test_healthz_alive(client):
    response = client.get("/healthz")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "version": "1.0.0"}


def test_healthz_ignores_dependency(client):
    """【要点】liveness 不查依赖，否则数据库抖动会引发全量重启"""
    main.set_db_ok(False)

    assert client.get("/healthz").status_code == 200


def test_readyz_ok(client):
    assert client.get("/readyz").status_code == 200


def test_readyz_503_when_dependency_down(client):
    main.set_db_ok(False)
    response = client.get("/readyz")

    assert response.status_code == 503
    assert response.json()["db_ok"] is False


def test_version_header(client):
    assert client.get("/items").headers["x-app-version"] == "1.0.0"


def test_lifespan_sets_and_clears_ready():
    main.reset()
    with TestClient(main.app) as c:
        assert c.get("/readyz").json()["ready"] is True

    assert main.STATE["shutdown_done"] is True


def test_prod_app_hides_docs():
    prod = TestClient(main.prod_app)

    assert prod.get("/docs").status_code == 404
    assert prod.get("/openapi.json").status_code == 404
    assert prod.get("/items").status_code == 200