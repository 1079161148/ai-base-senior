"""第 73 章 · pytest 写法示范。

跑法：uv run pytest -q

【要点】覆盖放在 fixture 里，`finally`（或 `yield` 之后）必须 `clear()`：
        覆盖是**全局**的，漏清理会污染后面的用例。
"""

import pytest
from fastapi.testclient import TestClient

import main


def fake_db() -> dict:
    return {"users": {9: {"id": 9, "name": "假用户"}}, "next_id": 10}


@pytest.fixture
def client():
    main.app.dependency_overrides[main.get_db] = fake_db
    main.app.dependency_overrides[main.get_current_user] = lambda: "tester"
    try:
        with TestClient(main.app) as test_client:
            yield test_client
    finally:
        main.app.dependency_overrides.clear()


def test_list_uses_fake_db(client):
    response = client.get("/users")

    assert response.status_code == 200
    assert response.json() == [{"id": 9, "name": "假用户"}]


def test_detail_from_fake_db(client):
    assert client.get("/users/9").json()["name"] == "假用户"
    assert client.get("/users/1").status_code == 404


def test_write_goes_to_fake_db(client):
    response = client.post("/users", json={"name": "新用户"})

    assert response.status_code == 201
    assert response.json() == {"id": 10, "name": "新用户"}
    assert sorted(main.REAL_DB["users"]) == [1, 2]


def test_auth_bypassed(client):
    """覆盖 `get_current_user` 后不再需要令牌"""
    assert client.get("/me").json() == {"user": "tester"}


def test_settings_can_be_overridden(client):
    main.app.dependency_overrides[main.get_settings] = lambda: main.Settings(max_items=1)

    assert client.get("/config").json()["max_items"] == 1
    assert len(client.get("/users").json()) == 1


def test_validation_still_real(client):
    """数据层是假的，参数校验是真的"""
    assert client.post("/users", json={"name": ""}).status_code == 422


def test_schema_unaffected(client):
    paths = client.get("/openapi.json").json()["paths"]

    assert "/users" in paths
    assert main.app.dependency_overrides, "覆盖应该在生效"


def test_overrides_cleared_after_fixture():
    """【提示】本用例依赖上面 fixture 已退出——pytest 按文件顺序执行"""
    assert main.app.dependency_overrides == {}