"""第 77 章 · pytest 用例。

跑法：uv run pytest -q

【要点】每个用例前 `store.reset()`，否则用例之间互相污染。
"""

import pytest
from fastapi.testclient import TestClient

import main
from security import DEMO_TOKEN
from store import store

BASE = "/api/v1/todos"
AUTH = {"Authorization": f"Bearer {DEMO_TOKEN}"}


@pytest.fixture
def client():
    store.reset()
    with TestClient(main.app, raise_server_exceptions=False) as test_client:
        yield test_client
    store.reset()


def test_create(client):
    response = client.post(BASE, json={"title": "买牛奶"}, headers=AUTH)

    assert response.status_code == 201
    assert response.headers["location"].startswith(BASE)
    assert response.json()["title"] == "买牛奶"


def test_pagination(client):
    body = client.get(BASE, params={"page": 2, "size": 2}).json()

    assert body["total"] == 3
    assert body["pages"] == 2
    assert len(body["items"]) == 1


def test_filter_combined(client):
    body = client.get(BASE, params={"done": False, "priority": "high"}).json()

    assert [item["id"] for item in body["items"]] == [1]


def test_detail_not_found(client):
    response = client.get(f"{BASE}/999")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"


def test_update_partial(client):
    response = client.patch(f"{BASE}/1", json={"done": True}, headers=AUTH)

    assert response.status_code == 200
    assert response.json()["done"] is True
    assert response.json()["title"] == "写第 77 章代码"


def test_delete_then_gone(client):
    assert client.delete(f"{BASE}/1", headers=AUTH).status_code == 204
    assert client.get(f"{BASE}/1").status_code == 404


def test_authentication_required_for_writes(client):
    assert client.post(BASE, json={"title": "x"}).status_code == 401
    assert client.patch(f"{BASE}/1", json={"done": True}).status_code == 401
    assert client.delete(f"{BASE}/1").status_code == 401


def test_validation_error_shape(client):
    response = client.post(BASE, json={"title": ""}, headers=AUTH)

    assert response.status_code == 422
    assert response.json()["error"]["details"]["fields"][0]["loc"] == "body.title"


def test_internal_error_hides_details(client):
    response = client.get("/boom")

    assert response.status_code == 500
    assert "内部炸了" not in response.text