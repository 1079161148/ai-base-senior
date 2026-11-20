"""第 63 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

import main  # noqa: E402


def client() -> TestClient:
    main.manager.reset()
    return TestClient(main.app)


def check_text_echo() -> str:
    """文本回声：发什么回什么（加前缀）。"""
    with client() as c:
        with c.websocket_connect("/ws/echo") as ws:
            ws.send_text("hi")
            assert ws.receive_text() == "echo: hi"
            ws.send_text("中文")
            assert ws.receive_text() == "echo: 中文"
    return "两轮往返正常"


def check_json_echo() -> str:
    """JSON 回声：`receive_json` / `send_json` 自动编解码。"""
    with client() as c:
        with c.websocket_connect("/ws/json") as ws:
            ws.send_json({"a": 1, "b": [2, 3], "中文": "值"})
            reply = ws.receive_json()
    assert reply == {"type": "echo", "payload": {"a": 1, "b": [2, 3], "中文": "值"}}, reply
    return "嵌套结构原样返回"


def check_bytes_echo() -> str:
    """二进制帧：`send_bytes` / `receive_bytes`。"""
    with client() as c:
        with c.websocket_connect("/ws/bytes") as ws:
            ws.send_bytes(b"\x00\x01\xff")
            reply = ws.receive_bytes()
    assert reply == b"echo:\x00\x01\xff", reply
    return f"{len(reply)} 字节"


def check_server_close_code() -> str:
    """服务端主动关闭：客户端拿到 code + reason。"""
    with client() as c:
        with c.websocket_connect("/ws/echo-once") as ws:
            ws.send_text("x")
            assert ws.receive_text() == "only: x"
            try:
                ws.receive_text()
            except WebSocketDisconnect as exc:
                assert exc.code == 1000, exc.code
                assert exc.reason == "done", exc.reason
                return f"关闭码 {exc.code} / {exc.reason}"
    raise AssertionError("没有收到关闭")


def check_heartbeat_interleaved() -> str:
    """心跳：服务端 tick 与客户端 ping 的 pong 交错到达。"""
    with client() as c:
        with c.websocket_connect("/ws/heartbeat") as ws:
            first = ws.receive_json()
            ws.send_text("ping")
            second = ws.receive_json()
            third = ws.receive_json()
            fourth = ws.receive_json()
    sequence = [first, second, third, fourth]
    assert first == {"type": "tick", "n": 1}, sequence
    assert second == {"type": "pong"}, sequence
    assert third == {"type": "tick", "n": 2}, sequence
    assert fourth == {"type": "tick", "n": 3}, sequence
    return "tick1 → pong → tick2 → tick3"


def check_broadcast_fanout() -> str:
    """广播：一个连接发的消息，两个连接都收到。"""
    with client() as c:
        with c.websocket_connect("/ws/broadcast") as first:
            with c.websocket_connect("/ws/broadcast") as second:
                assert first.receive_json() == {"type": "joined", "id": 1}
                assert first.receive_json() == {"type": "joined", "id": 2}
                assert second.receive_json() == {"type": "joined", "id": 2}
                first.send_text("hello")
                from_first = first.receive_json()
                from_second = second.receive_json()
    expected = {"type": "message", "from": 1, "text": "hello"}
    assert from_first == expected, from_first
    assert from_second == expected, from_second
    return "双方都收到 from=1"


def check_leave_event() -> str:
    """离开事件：一个连接关闭，另一个收到 `left`。"""
    with client() as c:
        with c.websocket_connect("/ws/broadcast") as first:
            with c.websocket_connect("/ws/broadcast") as second:
                assert first.receive_json() == {"type": "joined", "id": 1}
                assert first.receive_json() == {"type": "joined", "id": 2}
                assert second.receive_json() == {"type": "joined", "id": 2}
            left = first.receive_json()
    assert left == {"type": "left", "id": 2}, left
    return "收到 left id=2"


def check_stats_lifecycle() -> str:
    """连接统计：断开后 active 归零，closed 累加。"""
    with client() as c:
        with c.websocket_connect("/ws/broadcast") as ws:
            assert ws.receive_json() == {"type": "joined", "id": 1}
            during = c.get("/ws/stats").json()
        after = c.get("/ws/stats").json()
    assert during["active"] == 1, during
    assert after["active"] == 0, after
    assert after["total_connected"] == 1, after
    assert after["total_closed"] == 1, after
    return f'active {during["active"]} → {after["active"]}'


def check_reject_without_accept() -> str:
    """不 `accept` 直接关闭：客户端连不上，拿到 1008。"""
    with client() as c:
        try:
            with c.websocket_connect("/ws/reject") as ws:
                ws.receive_text()
        except WebSocketDisconnect as exc:
            assert exc.code == 1008, exc.code
            assert exc.reason == "not allowed", exc.reason
            return f"{exc.code} / {exc.reason}"
    raise AssertionError("居然连上了")


def check_custom_close_code() -> str:
    """自定义关闭码 4001 能透传到客户端。"""
    with client() as c:
        with c.websocket_connect("/ws/server-close") as ws:
            assert ws.receive_text() == "bye"
            try:
                ws.receive_text()
            except WebSocketDisconnect as exc:
                assert exc.code == 4001, exc.code
                assert exc.reason == "server shutdown", exc.reason
                return f"{exc.code} / {exc.reason}"
    raise AssertionError("没有关闭")


def check_client_disconnect_cleanup() -> str:
    """客户端自己 `close()`：服务端 finally 清理，active 归零。"""
    with client() as c:
        ws = c.websocket_connect("/ws/broadcast")
        session = ws.__enter__()
        assert session.receive_json() == {"type": "joined", "id": 1}
        session.close()
        ws.__exit__(None, None, None)
        after = c.get("/ws/stats").json()
    assert after["active"] == 0, after
    assert after["total_closed"] == 1, after
    return "active=0, closed=1"


def check_large_message() -> str:
    """1MB 文本往返：WebSocket 不像 HTTP 那样有 header 开销。"""
    payload = "x" * 1_000_000
    with client() as c:
        with c.websocket_connect("/ws/echo") as ws:
            ws.send_text(payload)
            reply = ws.receive_text()
    assert reply == "echo: " + payload, len(reply)
    return f"{len(reply):,} 字符"


def check_message_order() -> str:
    """同一连接上消息严格有序：100 条不乱序、不丢失。"""
    with client() as c:
        with c.websocket_connect("/ws/echo") as ws:
            for index in range(100):
                ws.send_text(str(index))
            replies = [ws.receive_text() for _ in range(100)]
    assert replies == [f"echo: {index}" for index in range(100)], replies[:5]
    return "100 条顺序一致"


def check_multi_connections() -> str:
    """三个并发连接：active 计数正确。"""
    with client() as c:
        with c.websocket_connect("/ws/echo") as a, c.websocket_connect(
            "/ws/echo"
        ) as b, c.websocket_connect("/ws/echo") as cc:
            a.send_text("a")
            b.send_text("b")
            cc.send_text("c")
            assert a.receive_text() == "echo: a"
            assert b.receive_text() == "echo: b"
            assert cc.receive_text() == "echo: c"
    return "3 条连接互不干扰"


CHECKS = [
    ("文本回声", check_text_echo),
    ("JSON 回声", check_json_echo),
    ("二进制帧", check_bytes_echo),
    ("服务端关闭码", check_server_close_code),
    ("心跳交错", check_heartbeat_interleaved),
    ("广播分发", check_broadcast_fanout),
    ("离开事件", check_leave_event),
    ("连接统计", check_stats_lifecycle),
    ("未 accept 拒绝", check_reject_without_accept),
    ("自定义关闭码", check_custom_close_code),
    ("客户端断开清理", check_client_disconnect_cleanup),
    ("1MB 消息", check_large_message),
    ("消息有序", check_message_order),
    ("三条并发连接", check_multi_connections),
]


def run() -> int:
    failures = 0
    for name, func in CHECKS:
        try:
            print(f"[PASS] {name} -> {func()}")
        except Exception as exc:  # noqa: BLE001 - 验收脚本要报告任何失败
            failures += 1
            print(f"[FAIL] {name} -> {type(exc).__name__}: {exc}")
    print(f"\n结果：{len(CHECKS) - failures}/{len(CHECKS)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())