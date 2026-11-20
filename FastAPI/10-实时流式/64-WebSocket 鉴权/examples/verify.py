"""第 64 章 · 自动验收。运行：python verify.py"""

import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402
from starlette.websockets import WebSocketDisconnect  # noqa: E402

import main  # noqa: E402

VALID = main.VALID_TOKEN


def client() -> TestClient:
    main.reset_stats()
    return TestClient(main.app)


def expect_reject(connect) -> tuple[int, str]:
    """【作用】断言握手被拒，返回 (code, reason)"""
    try:
        with connect() as websocket:
            websocket.receive_json()
    except WebSocketDisconnect as exc:
        return exc.code, exc.reason
    raise AssertionError("居然连上了")


def check_query_valid() -> str:
    """query 带正确 token → 连上并收到 ready。"""
    with client() as c:
        with c.websocket_connect(f"/ws/auth/query?token={VALID}") as ws:
            ready = ws.receive_json()
    assert ready == {"type": "ready", "user": "query-user"}, ready
    return "ready / query-user"


def check_query_missing() -> str:
    """query 缺 token → 1008。"""
    with client() as c:
        code, reason = expect_reject(lambda: c.websocket_connect("/ws/auth/query"))
    assert code == 1008, code
    assert reason == "invalid query token", reason
    return f"{code} / {reason}"


def check_query_invalid() -> str:
    """query token 错误 → 1008。"""
    with client() as c:
        code, reason = expect_reject(lambda: c.websocket_connect("/ws/auth/query?token=wrong"))
    assert code == 1008, code
    return f"{code} / {reason}"


def check_header_valid() -> str:
    """`Authorization: Bearer <token>` → 连上。"""
    with client() as c:
        with c.websocket_connect(
            "/ws/auth/header", headers={"Authorization": f"Bearer {VALID}"}
        ) as ws:
            ready = ws.receive_json()
    assert ready == {"type": "ready", "user": "header-user"}, ready
    return "ready / header-user"


def check_header_missing() -> str:
    """无 Authorization 头 → 1008。"""
    with client() as c:
        code, reason = expect_reject(lambda: c.websocket_connect("/ws/auth/header"))
    assert code == 1008, code
    assert reason == "invalid authorization header", reason
    return f"{code} / {reason}"


def check_cookie_valid() -> str:
    """cookie `session` 正确 → 连上。"""
    with client() as c:
        with c.websocket_connect("/ws/auth/cookie", cookies={"session": VALID}) as ws:
            ready = ws.receive_json()
    assert ready == {"type": "ready", "user": "cookie-user"}, ready
    return "ready / cookie-user"


def check_cookie_missing() -> str:
    """无 cookie → 1008。"""
    with client() as c:
        code, reason = expect_reject(lambda: c.websocket_connect("/ws/auth/cookie"))
    assert code == 1008, code
    assert reason == "invalid session cookie", reason
    return f"{code} / {reason}"


def check_first_frame_ok() -> str:
    """首帧带正确 token → ready，之后可正常业务。"""
    with client() as c:
        with c.websocket_connect("/ws/auth/first-frame") as ws:
            ws.send_json({"type": "auth", "token": VALID, "user": "alice"})
            assert ws.receive_json() == {"type": "ready", "user": "alice"}
            ws.send_json({"type": "ping"})
            assert ws.receive_json() == {"type": "pong"}
            ws.send_json({"type": "echo", "text": "hi"})
            echo = ws.receive_json()
    assert echo["type"] == "echo" and echo["payload"]["text"] == "hi", echo
    return "ready → pong → echo"


def check_first_frame_bad_token() -> str:
    """首帧 token 错 → 1008 invalid token。"""
    with client() as c:
        try:
            with c.websocket_connect("/ws/auth/first-frame") as ws:
                ws.send_json({"type": "auth", "token": "wrong"})
                ws.receive_json()
        except WebSocketDisconnect as exc:
            assert exc.code == 1008, exc.code
            assert exc.reason == "invalid token", exc.reason
            return f"{exc.code} / {exc.reason}"
    raise AssertionError("居然连上了")


def check_first_frame_wrong_type() -> str:
    """首帧不是 auth → 1008 first frame must be auth。"""
    with client() as c:
        try:
            with c.websocket_connect("/ws/auth/first-frame") as ws:
                ws.send_json({"type": "echo", "text": "直接发业务"})
                ws.receive_json()
        except WebSocketDisconnect as exc:
            assert exc.code == 1008, exc.code
            assert exc.reason == "first frame must be auth", exc.reason
            return f"{exc.code} / {exc.reason}"
    raise AssertionError("居然连上了")


def check_first_frame_timeout() -> str:
    """首帧超时 → 1008 auth timeout，且耗时接近设定值。"""
    with client() as c:
        started = time.perf_counter()
        try:
            with c.websocket_connect("/ws/auth/first-frame?timeout=0.15") as ws:
                ws.receive_json()
        except WebSocketDisconnect as exc:
            elapsed = time.perf_counter() - started
            assert exc.code == 1008, exc.code
            assert exc.reason == "auth timeout", exc.reason
            assert 0.1 < elapsed < 1.0, elapsed
            return f'{exc.reason}，{elapsed * 1000:.0f}ms'
    raise AssertionError("居然连上了")


def check_rejected_not_counted() -> str:
    """鉴权失败只累加 `rejected`，不进 `connected`。"""
    with client() as c:
        expect_reject(lambda: c.websocket_connect("/ws/auth/query"))
        expect_reject(lambda: c.websocket_connect("/ws/auth/cookie"))
        with c.websocket_connect(f"/ws/auth/query?token={VALID}") as ws:
            ws.receive_json()
        stats = c.get("/stats").json()
    assert stats["rejected"] == 2, stats
    assert stats["connected"] == 1, stats
    return f'rejected={stats["rejected"]} connected={stats["connected"]}'


def check_cleanup_on_disconnect() -> str:
    """鉴权成功后断开：`active` 清空，`closed` 累加。"""
    with client() as c:
        with c.websocket_connect(f"/ws/auth/query?token={VALID}") as ws:
            ws.receive_json()
            during = c.get("/stats").json()
        after = c.get("/stats").json()
    assert during["active"] == ["query-user"], during
    assert after["active"] == [], after
    assert after["closed"] == 1, after
    return f'active {during["active"]} → {after["active"]}, closed={after["closed"]}'


def check_two_users_isolated() -> str:
    """两个用户同时在线，互不影响，`active` 两人都在。"""
    with client() as c:
        with c.websocket_connect("/ws/auth/first-frame") as alice:
            alice.send_json({"type": "auth", "token": VALID, "user": "alice"})
            assert alice.receive_json()["user"] == "alice"
            with c.websocket_connect("/ws/auth/first-frame") as bob:
                bob.send_json({"type": "auth", "token": VALID, "user": "bob"})
                assert bob.receive_json()["user"] == "bob"
                stats = c.get("/stats").json()
                assert stats["active"] == ["alice", "bob"], stats
                alice.send_json({"type": "echo", "to": "alice"})
                bob.send_json({"type": "echo", "to": "bob"})
                assert alice.receive_json()["payload"]["to"] == "alice"
                assert bob.receive_json()["payload"]["to"] == "bob"
    return "alice/bob 各自收到自己的回声"


CHECKS = [
    ("query 有效", check_query_valid),
    ("query 缺失", check_query_missing),
    ("query 错误", check_query_invalid),
    ("header 有效", check_header_valid),
    ("header 缺失", check_header_missing),
    ("cookie 有效", check_cookie_valid),
    ("cookie 缺失", check_cookie_missing),
    ("首帧有效", check_first_frame_ok),
    ("首帧 token 错", check_first_frame_bad_token),
    ("首帧类型错", check_first_frame_wrong_type),
    ("首帧超时", check_first_frame_timeout),
    ("拒绝不计连接", check_rejected_not_counted),
    ("断开清理", check_cleanup_on_disconnect),
    ("双用户隔离", check_two_users_isolated),
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