"""第 74 章 · pytest 写法示范。

跑法：uv run pytest -q

【要点】`websocket_connect` 的上下文管理器退出时会关闭连接；
        服务端主动 `close(code, reason)` 后，客户端 `receive_*` 抛
        `WebSocketDisconnect`，用 `.code` 与 `.reason` 断言。
"""

import pytest
from fastapi.testclient import TestClient
from starlette.websockets import WebSocketDisconnect

import main


@pytest.fixture
def client():
    main.reset()
    with TestClient(main.app) as test_client:
        yield test_client


def test_echo(client):
    with client.websocket_connect("/ws/echo") as ws:
        ws.send_text("hi")

        assert ws.receive_text() == "echo: hi"


def test_message_order(client):
    with client.websocket_connect("/ws/echo") as ws:
        for index in range(3):
            ws.send_text(str(index))
        replies = [ws.receive_text() for _ in range(3)]

    assert replies == ["echo: 0", "echo: 1", "echo: 2"]


def test_json_roundtrip(client):
    with client.websocket_connect("/ws/json") as ws:
        ws.send_json({"a": [1, 2]})

        assert ws.receive_json() == {"received": {"a": [1, 2]}, "type": "json"}


def test_server_close_code(client):
    with client.websocket_connect("/ws/close") as ws:
        assert ws.receive_json() == {"bye": True}

        with pytest.raises(WebSocketDisconnect) as excinfo:
            ws.receive_json()

    assert excinfo.value.code == 4001
    assert excinfo.value.reason == "server shutdown"


def test_reject_before_accept(client):
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("/ws/reject") as ws:
            ws.receive_json()

    assert excinfo.value.code == 1008


def test_broadcast_to_both(client):
    with client.websocket_connect("/ws/room/a") as first, client.websocket_connect("/ws/room/a") as second:
        first.send_text("hello")

        assert first.receive_text() == "[a] hello"
        assert second.receive_text() == "[a] hello"


def test_disconnect_updates_stats(client):
    with client.websocket_connect("/ws/echo") as ws:
        ws.send_text("x")
        ws.receive_text()
        assert client.get("/stats").json()["active"] == ["conn-1"]

    stats = client.get("/stats").json()
    assert stats["active"] == []
    assert stats["closed"] == 1


def test_dependency_can_be_overridden(client):
    fake = {9: {"id": 9, "name": "假用户"}}
    main.app.dependency_overrides[main.get_db] = lambda: fake
    try:
        with client.websocket_connect("/ws/user/9") as ws:
            assert ws.receive_json() == {"id": 9, "name": "假用户"}
    finally:
        main.app.dependency_overrides.clear()


def test_unknown_user_closes(client):
    with pytest.raises(WebSocketDisconnect) as excinfo:
        with client.websocket_connect("/ws/user/99") as ws:
            ws.receive_json()

    assert excinfo.value.code == 1008
    assert excinfo.value.reason == "user not found"