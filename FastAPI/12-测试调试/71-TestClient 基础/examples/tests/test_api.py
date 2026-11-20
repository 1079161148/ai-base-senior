"""第 71 章 · pytest 写法示范。

跑法：uv run pytest -q

【要点】fixture 里用 `with TestClient(app)`：
        进入时跑 lifespan，退出时跑 shutdown，
        并且每个用例拿到的是**干净状态**。
"""

import pytest
from fastapi.testclient import TestClient

import main


@pytest.fixture
def client():
    """【要点】每个用例前重置数据，避免顺序依赖"""
    main.ITEMS.clear()
    main.ITEMS[1] = {"id": 1, "name": "键盘", "price": 19900}
    main.STATE.update(next_id=2, started=False)
    with TestClient(main.app) as test_client:
        yield test_client


def test_create_item(client):
    response = client.post("/items", json={"name": "鼠标", "price": 9900})

    assert response.status_code == 201
    assert response.json() == {"id": 2, "name": "鼠标", "price": 9900}
    assert response.headers["content-type"] == "application/json"


def test_list_items(client):
    response = client.get("/items")

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_read_item(client):
    response = client.get("/items/1")

    assert response.status_code == 200
    assert response.json()["name"] == "键盘"


def test_item_not_found(client):
    """【要点】404 只断言 detail 文案，不要断言整个错误体结构"""
    response = client.get("/items/999")

    assert response.status_code == 404
    assert response.json()["detail"] == "item not found"


def test_create_item_invalid_body(client):
    """【要点】422 断言 `type` 与 `loc`，不要断言 `msg` 全文（会随 pydantic 版本变）"""
    response = client.post("/items", json={"name": "", "price": -1})

    assert response.status_code == 422
    errors = response.json()["detail"]
    types = {error["type"] for error in errors}
    assert types == {"string_too_short", "greater_than_equal"}
    locs = {tuple(error["loc"]) for error in errors}
    assert locs == {("body", "name"), ("body", "price")}


@pytest.mark.parametrize("limit", [0, 51, "abc"])
def test_list_items_invalid_limit(client, limit):
    """【要点】参数化把同一断言的多个边界一次覆盖"""
    assert client.get("/items", params={"limit": limit}).status_code == 422


def test_redirect_followed_by_default(client):
    response = client.get("/redirect")

    assert response.status_code == 200
    assert response.url.path == "/items"


def test_redirect_not_followed(client):
    strict = TestClient(main.app, follow_redirects=False)
    response = strict.get("/redirect")

    assert response.status_code == 307
    assert response.headers["location"] == "/items"


def test_lifespan_runs_inside_context(client):
    """【要点】`with TestClient` 才触发 lifespan"""
    assert client.get("/state").json() == {"started": True}


def test_cookie_persists(client):
    client.cookies.set("session", "abc123")

    assert client.get("/cookie/read").json() == {"session": "abc123"}


def test_server_error_is_raised_by_default():
    """【要点】默认把服务端异常原样抛出，避免「500 也算通过」"""
    with pytest.raises(RuntimeError, match="故意炸了"):
        TestClient(main.app).get("/boom")


def test_server_error_can_be_inspected():
    lenient = TestClient(main.app, raise_server_exceptions=False)
    response = lenient.get("/boom")

    assert response.status_code == 500