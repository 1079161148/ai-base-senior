"""第 52 章 · 自动验收。运行：python verify.py"""

import asyncio
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

import httpx  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


class Capture(logging.Handler):
    """把日志行收进 list，便于断言 trace_id 是否出现"""

    def __init__(self) -> None:
        super().__init__()
        self.lines: list[str] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.lines.append(self.format(record))


capture = Capture()
capture.setFormatter(logging.Formatter("%(trace_id)s|%(message)s"))
capture.addFilter(main.TraceFilter())
# 【作用】去掉示例自带的终端 handler，让验收输出不被日志淹没
main.logger.handlers.clear()
main.logger.addHandler(capture)


def check_trace_id_generated() -> str:
    """无入参时生成 12 位 hex，并回写响应头。"""
    r = client.get("/work")
    tid = r.json()["trace_id"]
    assert len(tid) == 12 and all(c in "0123456789abcdef" for c in tid), tid
    assert r.headers["x-request-id"] == tid, dict(r.headers)
    return f"trace_id={tid}"


def check_trace_id_passthrough() -> str:
    """客户端传了 `X-Request-ID` 就透传。"""
    r = client.get("/work", headers={"X-Request-ID": "my-123"})
    assert r.json()["trace_id"] == "my-123", r.json()
    assert r.headers["x-request-id"] == "my-123"
    return "X-Request-ID: my-123 透传"


def check_state_matches_contextvar() -> str:
    """`request.state` 与 contextvar 一致。"""
    body = client.get("/work").json()
    assert body["trace_id"] == body["state"], body
    return f"trace_id == state == {body['trace_id']}"


def check_context_reset_after_request() -> str:
    """请求结束后 contextvar 回到默认值（`reset(token)` 生效）。"""
    client.get("/work")
    assert main.trace_id_var.get() == "", repr(main.trace_id_var.get())
    return "请求后 contextvar == ''"


def check_log_contains_trace_id() -> str:
    """日志行里的 trace_id == 响应头里的。"""
    capture.lines.clear()
    r = client.get("/work")
    tid = r.headers["x-request-id"]
    lines = [line for line in capture.lines if line.startswith(f"{tid}|")]
    assert len(lines) >= 3, capture.lines
    messages = [line.split("|", 1)[1] for line in lines]
    assert "请求开始" in messages[0], messages
    assert "业务处理中" in " ".join(messages), messages
    return f"{len(lines)} 行日志都带 [{tid}]"


def check_deep_call_reads_context() -> str:
    """三层嵌套函数不用传参就能读。"""
    r = client.get("/deep")
    assert r.json()["level3"].startswith("trace="), r.json()
    assert len(r.json()["level3"]) == len("trace=") + 12, r.json()
    return r.json()["level3"]


def check_background_task_context() -> str:
    """`BackgroundTasks` 里仍能读到同一个 trace_id。"""
    capture.lines.clear()
    r = client.get("/background")
    tid = r.json()["trace_id"]
    assert tid, r.json()
    bg = [line for line in capture.lines if "后台任务" in line]
    assert bg and bg[0].startswith(f"{tid}|"), (capture.lines, tid)
    return f"后台任务读到 {tid}"


def check_concurrent_isolation() -> str:
    """并发时 contextvar 各自正确，全局变量被覆盖。"""
    async def run() -> tuple[dict, dict]:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as ac:
            a, b = await asyncio.gather(
                ac.get("/race", headers={"X-Request-ID": "AAA"}),
                ac.get("/race", headers={"X-Request-ID": "BBB"}),
            )
        return a.json(), b.json()

    a, b = asyncio.run(run())
    assert {a["ctx_before"], b["ctx_before"]} == {"AAA", "BBB"}, (a, b)
    assert a["ctx_after"] == a["ctx_before"], (a, b)
    assert b["ctx_after"] == b["ctx_before"], (a, b)
    # 全局变量被后到的请求覆盖：两个响应读到同一个值，且与自己的 id 不同
    assert a["global_after"] == b["global_after"], (a, b)
    return f'ctx={a["ctx_before"]}/{b["ctx_before"]}，global 都被覆盖成 {a["global_after"]}'


def check_no_global_leak_into_log() -> str:
    """日志的 trace_id 用的是 contextvar，不是全局变量（并发时仍各自正确）。"""
    capture.lines.clear()

    async def run() -> None:
        transport = httpx.ASGITransport(app=main.app)
        async with httpx.AsyncClient(transport=transport, base_url="http://t") as ac:
            await asyncio.gather(
                ac.get("/work", headers={"X-Request-ID": "C1"}),
                ac.get("/work", headers={"X-Request-ID": "C2"}),
            )

    asyncio.run(run())
    starts = [line for line in capture.lines if "请求开始" in line]
    assert any(line.startswith("C1|") for line in starts), capture.lines
    assert any(line.startswith("C2|") for line in starts), capture.lines
    return "并发两个请求的日志各带自己的 id"


def check_filter_has_default() -> str:
    """没有设置过 trace_id 时，日志里显示 `-` 而不是报错。"""
    capture.lines.clear()
    main.logger.info("裸日志")
    assert capture.lines and capture.lines[-1].startswith("-|"), capture.lines
    return "无上下文时显示 '-'"


def check_request_state_available_in_route() -> str:
    """`request.state` 也能拿到（与 contextvar 双保险）。"""
    body = client.get("/work", headers={"X-Request-ID": "state-1"}).json()
    assert body["state"] == "state-1", body
    return "state-1"


CHECKS = [
    ("生成 trace_id", check_trace_id_generated),
    ("透传 trace_id", check_trace_id_passthrough),
    ("state 与 contextvar 一致", check_state_matches_contextvar),
    ("请求后 reset", check_context_reset_after_request),
    ("日志带 trace_id", check_log_contains_trace_id),
    ("嵌套调用可读", check_deep_call_reads_context),
    ("后台任务上下文", check_background_task_context),
    ("并发隔离", check_concurrent_isolation),
    ("并发日志不串", check_no_global_leak_into_log),
    ("无上下文兜底", check_filter_has_default),
    ("request.state 可用", check_request_state_available_in_route),
]


def run() -> int:
    failures = 0
    for name, func in CHECKS:
        try:
            print(f"[PASS] {name} -> {func()}")
        except AssertionError as exc:
            failures += 1
            print(f"[FAIL] {name} -> {exc}")
    print(f"\n结果：{len(CHECKS) - failures}/{len(CHECKS)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())