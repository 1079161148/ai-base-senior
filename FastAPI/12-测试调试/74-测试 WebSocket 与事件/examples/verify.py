"""第 74 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

import main  # noqa: E402


def client() -> TestClient:
    main.reset()
    return TestClient(main.app)


def check_echo() -> str:
    """文本回声。"""
    with client() as c, c.websocket_connect("/ws/echo") as ws:
        ws.send_text("hi")
        assert ws.receive_text() == "echo: hi"
    return "echo: hi"


def check_order() -> str:
    """同一连接上消息严格有序。"""
    with client() as c, c.websocket_connect("/ws/echo") as ws:
        for index in range(3):
            ws.send_text(str(index))
        replies = [ws.receive_text() for _ in range(3)]
    assert replies == ["echo: 0", "echo: 1", "echo: 2"], replies
    return "0 → 1 → 2"


def check_json() -> str:
    """JSON 往返。"""
    with client() as c, c.websocket_connect("/ws/json") as ws:
        ws.send_json({"a": [1, 2]})
        body = ws.receive_json()
    assert body == {"received": {"a": [1, 2]}, "type": "json"}, body
    return "结构原样返回"


def check_close_code() -> str:
    """服务端 `close(4001)`：先收到消息，再抛 Disconnect。"""
    with client() as c:
        with c.websocket_connect("/ws/close") as ws:
            assert ws.receive_json() == {"bye": True}
            try:
                ws.receive_json()
            except WebSocketDisconnect as exc:
                assert exc.code == 4001, exc.code
                assert exc.reason == "server shutdown", exc.reason
                return f"{exc.code} / {exc.reason}"
    raise AssertionError("没有收到 Disconnect")


def check_reject() -> str:
    """不 accept 直接 close：连接建立就失败。"""
    with client() as c:
        try:
            with c.websocket_connect("/ws/reject") as ws:
                ws.receive_json()
        except WebSocketDisconnect as exc:
            assert exc.code == 1008, exc.code
            assert exc.reason == "not allowed", exc.reason
            return f"{exc.code} / {exc.reason}"
    raise AssertionError("居然连上了")


def check_broadcast() -> str:
    """同房间两条连接都收到广播。"""
    with client() as c:
        with c.websocket_connect("/ws/room/a") as first, c.websocket_connect("/ws/room/a") as second:
            first.send_text("hello")
            one = first.receive_text()
            two = second.receive_text()
    assert one == two == "[a] hello", (one, two)
    return "两条连接都收到"


def check_broadcast_back() -> str:
    """第二方发消息，第一方也能收到。"""
    with client() as c:
        with c.websocket_connect("/ws/room/a") as first, c.websocket_connect("/ws/room/a") as second:
            second.send_text("from2")
            assert first.receive_text() == "[a] from2"
    return "双向广播"


def check_dependency_real() -> str:
    """WebSocket 端点用真实依赖。"""
    with client() as c, c.websocket_connect("/ws/user/1") as ws:
        body = ws.receive_json()
    assert body == {"id": 1, "name": "真实用户"}, body
    return body["name"]


def check_unknown_user() -> str:
    """依赖返回 None → close(1008)。"""
    with client() as c:
        try:
            with c.websocket_connect("/ws/user/99") as ws:
                ws.receive_json()
        except WebSocketDisconnect as exc:
            assert exc.code == 1008, exc.code
            assert exc.reason == "user not found", exc.reason
            return f"{exc.code} / {exc.reason}"
    raise AssertionError("没有拒绝")


def check_dependency_override() -> str:
    """**要点**：覆盖 `get_db` 后 WebSocket 也立刻用假库。"""
    fake = {9: {"id": 9, "name": "假用户"}}
    main.app.dependency_overrides[main.get_db] = lambda: fake
    try:
        with client() as c, c.websocket_connect("/ws/user/9") as ws:
            body = ws.receive_json()
        assert body == {"id": 9, "name": "假用户"}, body
        return body["name"]
    finally:
        main.app.dependency_overrides.clear()


def check_override_hides_real() -> str:
    """覆盖之后真实 id 反而查不到。"""
    fake = {9: {"id": 9, "name": "假用户"}}
    main.app.dependency_overrides[main.get_db] = lambda: fake
    try:
        with client() as c:
            try:
                with c.websocket_connect("/ws/user/1") as ws:
                    ws.receive_json()
            except WebSocketDisconnect as exc:
                assert exc.code == 1008, exc.code
                return "真实 id 1 → 1008"
    finally:
        main.app.dependency_overrides.clear()
    raise AssertionError("覆盖没生效")


def check_restore_after_clear() -> str:
    """`clear()` 后恢复真实库。"""
    main.app.dependency_overrides[main.get_db] = lambda: {9: {"id": 9, "name": "假用户"}}
    main.app.dependency_overrides.clear()
    with client() as c, c.websocket_connect("/ws/user/1") as ws:
        body = ws.receive_json()
    assert body["name"] == "真实用户", body
    return "恢复真实用户"


def check_stats_active() -> str:
    """连接中 `active` 有值，断开后清零。"""
    with client() as c:
        with c.websocket_connect("/ws/echo") as ws:
            ws.send_text("x")
            ws.receive_text()
            inside = c.get("/stats").json()
        after = c.get("/stats").json()
    assert inside["active"] == ["conn-1"], inside
    assert inside["messages"] == 1, inside
    assert after["active"] == [], after
    assert after["closed"] == 1, after
    return "active 1 → 0，closed=1"


def check_multi_room_isolated() -> str:
    """不同房间互不干扰。"""
    with client() as c:
        with c.websocket_connect("/ws/room/a") as a, c.websocket_connect("/ws/room/b") as b:
            a.send_text("only-a")
            got = a.receive_text()
            assert got == "[a] only-a", got
            b.send_text("only-b")
            assert b.receive_text() == "[b] only-b"
    return "a / b 隔离"


CHECKS = [
    ("文本回声", check_echo),
    ("消息有序", check_order),
    ("JSON 往返", check_json),
    ("服务端关闭码", check_close_code),
    ("拒绝连接", check_reject),
    ("广播", check_broadcast),
    ("双向广播", check_broadcast_back),
    ("真实依赖", check_dependency_real),
    ("未知用户", check_unknown_user),
    ("覆盖依赖", check_dependency_override),
    ("覆盖隐藏真实", check_override_hides_real),
    ("清理后恢复", check_restore_after_clear),
    ("连接统计", check_stats_active),
    ("房间隔离", check_multi_room_isolated),
]


def run() -> int:
    failures = 0
    for name, func in CHECKS:
        try:
            print(f"[PASS] {name} -> {func()}")
        except Exception as exc:  # noqa: BLE001 - 验收脚本要报告任何失败
            failures += 1
            print(f"[FAIL] {name} -> {type(exc).__name__}: {exc}")
    main.app.dependency_overrides.clear()
    print(f"\n结果：{len(CHECKS) - failures}/{len(CHECKS)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())