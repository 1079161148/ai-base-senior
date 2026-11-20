"""第 75 章 · pytest 写法示范。

跑法：uv run pytest -q

【要点】用 `caplog` 断言日志，不要断言 stdout 文本。
        `caplog.set_level` 决定能捕获哪些级别。
"""

import logging

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def client():
    with TestClient(main.app) as test_client:
        yield test_client


@pytest.fixture
def logs(caplog):
    caplog.set_level(logging.INFO, logger="app.request")
    return caplog


def test_request_id_generated(client):
    response = client.get("/items")

    assert len(response.headers["x-request-id"]) == 8
    assert float(response.headers["x-elapsed-ms"]) >= 0


def test_request_id_propagated(client):
    response = client.get("/items", headers={"X-Request-ID": "trace-42"})

    assert response.headers["x-request-id"] == "trace-42"


def test_one_line_per_request(client, logs):
    client.get("/items")

    messages = [record.getMessage() for record in logs.records]
    assert any("method=GET" in message and "path=/items" in message for message in messages)


def test_correlation_id_in_log(client, logs):
    client.get("/items", headers={"X-Request-ID": "trace-42"})

    assert any(getattr(record, "request_id", None) == "trace-42" for record in logs.records)


def test_slow_request_is_warning(client, logs):
    client.get("/slow", params={"ms": 80})

    slow = [
        record
        for record in logs.records
        if "/slow" in record.getMessage() and record.levelno >= logging.WARNING
    ]
    assert slow, "慢请求应该是 WARNING"


def test_password_is_masked(client, logs):
    client.post("/login", json={"username": "u", "password": "hunter2"})

    joined = " ".join(record.getMessage() for record in logs.records)
    assert "hunter2" not in joined
    assert "***" in joined


def test_500_has_request_id(client):
    client_without_raise = TestClient(main.app, raise_server_exceptions=False)
    response = client_without_raise.get("/boom")

    assert response.status_code == 500
    assert "request_id" in response.json()
    assert response.headers["x-request-id"] == response.json()["request_id"]


def test_debug_mode_leaks_traceback():
    """【反例】`debug=True` 把 traceback 给客户端，生产绝对不能开"""
    lenient = TestClient(main.debug_app, raise_server_exceptions=False)
    response = lenient.get("/boom")

    assert response.status_code == 500
    assert "Traceback" in response.text


def test_openapi_contract(client):
    """【要点】契约快照：路径与 operationId 变了就该有人 review"""
    schema = client.get("/openapi.json").json()

    assert sorted(schema["paths"]) == ["/boom", "/items", "/login", "/missing", "/slow"]
    operation_ids = sorted(
        operation["operationId"] for path in schema["paths"].values() for operation in path.values()
    )
    assert operation_ids == [
        "boom_boom_get",
        "list_items_items_get",
        "login_login_post",
        "missing_missing_get",
        "slow_slow_get",
    ]


def test_every_operation_has_summary(client):
    schema = client.get("/openapi.json").json()

    for path, operations in schema["paths"].items():
        for method, operation in operations.items():
            assert operation.get("summary"), f"{method} {path} 缺 summary"