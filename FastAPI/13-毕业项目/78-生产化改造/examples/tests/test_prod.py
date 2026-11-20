"""第 78 章 · pytest 用例。"""

import sqlite3

import main

BASE = "/api/v1/todos"


def seed(client, n: int = 2) -> None:
    for index in range(n):
        client.post(BASE, json={"title": f"任务{index}"}, headers={"Authorization": "Bearer test-token"})


def test_healthz_does_not_touch_db(client):
    assert client.get("/healthz").status_code == 200


def test_create_and_persist(client, auth):
    response = client.post(BASE, json={"title": "买牛奶"}, headers=auth)

    assert response.status_code == 201
    with sqlite3.connect(main.settings.db_path) as conn:
        titles = [row[0] for row in conn.execute("SELECT title FROM todos")]
    assert titles == ["买牛奶"]


def test_transaction_rolls_back(client, auth):
    seed(client, 1)
    response = client.post(f"{BASE}/_tx", headers=auth)

    assert response.status_code == 409
    assert client.get(f"{BASE}/stats").json()["total"] == 1


def test_token_comes_from_config(client):
    response = client.post(BASE, json={"title": "x"}, headers={"Authorization": "Bearer demo-token"})

    assert response.status_code == 401


def test_pagination(client, auth):
    seed(client, 3)
    body = client.get(BASE, params={"size": 2}).json()

    assert (body["total"], body["pages"]) == (3, 2)


def test_not_found_contract(client):
    response = client.get(f"{BASE}/999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_internal_error_hides_details(client):
    response = client.get("/boom")

    assert response.status_code == 500
    assert "内部炸了" not in response.text


def test_observability_headers(client):
    response = client.get(BASE, headers={"X-Request-ID": "trace-1"})

    assert response.headers["x-request-id"] == "trace-1"
    assert response.headers["x-app-version"] == main.settings.version