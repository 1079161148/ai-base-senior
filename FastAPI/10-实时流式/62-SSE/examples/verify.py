"""第 62 章 · 自动验收。运行：python verify.py"""

import json
import sys
import time
from pathlib import Path
from typing import Any

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402


def client(strict: bool = False) -> TestClient:
    return TestClient(main.app, raise_server_exceptions=strict)


def parse_sse(raw: str) -> tuple[list[dict[str, Any]], int | None, int]:
    """【作用】按规范解析 SSE：空行分隔事件，`:` 开头是注释，`retry` 是独立字段"""
    events: list[dict[str, Any]] = []
    retry: int | None = None
    comments = 0
    current: dict[str, Any] = {"event": "message", "id": None, "data": []}

    for line in raw.split("\n"):
        if line == "":
            if current["data"]:
                events.append(
                    {
                        "event": current["event"],
                        "id": current["id"],
                        "data": "\n".join(current["data"]),
                    }
                )
            current = {"event": "message", "id": None, "data": []}
            continue
        if line.startswith(":"):
            comments += 1
            continue
        field, _, value = line.partition(":")
        if value.startswith(" "):
            value = value[1:]
        if field == "event":
            current["event"] = value
        elif field == "id":
            current["id"] = value
        elif field == "data":
            current["data"].append(value)
        elif field == "retry":
            retry = int(value)
    return events, retry, comments


def check_media_type_and_headers() -> str:
    """`text/event-stream` + 禁缓存/禁缓冲，无 `Content-Length`。"""
    with client() as c:
        headers = c.get("/sse/chat", params={"text": "a", "delay_ms": 0}).headers
    assert headers["content-type"] == "text/event-stream; charset=utf-8", headers["content-type"]
    assert "content-length" not in headers, dict(headers)
    assert headers["cache-control"] == "no-cache", dict(headers)
    assert headers["x-accel-buffering"] == "no", dict(headers)
    return "text/event-stream; charset=utf-8 + no-cache + no-buffering"


def check_chat_events() -> str:
    """打字机：2 个字符事件 + 1 个 done 事件。"""
    with client() as c:
        raw = c.get("/sse/chat", params={"text": "你好", "delay_ms": 0}).text
    events, _, _ = parse_sse(raw)
    assert len(events) == 3, events
    assert events[0]["data"] == '{"index": 0, "text": "你"}', events[0]
    assert events[-1]["event"] == "done", events[-1]
    return f"{len(events)} 个事件"


def check_event_data_is_json() -> str:
    """每个事件的 data 都是合法 JSON。"""
    with client() as c:
        raw = c.get("/sse/chat", params={"text": "abc", "delay_ms": 0}).text
    events, _, _ = parse_sse(raw)
    payloads = [json.loads(event["data"]) for event in events]
    assert [item.get("index") for item in payloads[:3]] == [0, 1, 2], payloads
    return "3 条 JSON + done"


def check_blank_line_separator() -> str:
    """事件之间必须空行：`\\n\\n` 数量 = 事件数。"""
    with client() as c:
        raw = c.get("/sse/chat", params={"text": "ab", "delay_ms": 0}).text
    events, _, _ = parse_sse(raw)
    assert raw.endswith("\n\n"), repr(raw[-10:])
    assert raw.count("\n\n") == len(events), (raw.count("\n\n"), len(events))
    return f"{len(events)} 个事件 / {raw.count(chr(10) + chr(10))} 个空行"


def check_custom_event_names() -> str:
    """自定义 `event:` 名与递增 `id:`。"""
    with client() as c:
        raw = c.get("/sse/typed").text
    events, _, _ = parse_sse(raw)
    assert [event["event"] for event in events] == ["token", "token", "token", "done"], events
    assert [event["id"] for event in events[:3]] == ["1", "2", "3"], events
    assert events[0]["data"] == '{"text": "S"}', events[0]
    return "token×3 + done，id 1/2/3"


def check_ids_increase() -> str:
    """`id:` 从 1 到 5。"""
    with client() as c:
        raw = c.get("/sse/events", params={"total": 5}).text
    events, _, _ = parse_sse(raw)
    assert [event["id"] for event in events] == ["1", "2", "3", "4", "5"], events
    return "1..5"


def check_last_event_id_resume() -> str:
    """`Last-Event-ID: 3` → 从第 4 条继续。"""
    with client() as c:
        raw = c.get("/sse/events", params={"total": 5}, headers={"Last-Event-ID": "3"}).text
    events, _, _ = parse_sse(raw)
    assert [event["id"] for event in events] == ["4", "5"], events
    return "从 4 续传"


def check_multiline_data() -> str:
    """多个 `data:` 行拼成 `\\n` 连接的字符串。"""
    with client() as c:
        raw = c.get("/sse/multiline").text
    assert raw == "data: 第一行\ndata: 第二行\n\n", repr(raw)
    events, _, _ = parse_sse(raw)
    assert events[0]["data"] == "第一行\n第二行", events
    return repr(events[0]["data"])


def check_comment_not_event() -> str:
    """`:` 注释行不产生事件。"""
    with client() as c:
        raw = c.get("/sse/heartbeat", params={"beats": 2}).text
    events, _, comments = parse_sse(raw)
    assert comments == 2, comments
    assert len(events) == 2, events
    assert [json.loads(event["data"])["beat"] for event in events] == [1, 2], events
    return "2 条注释被忽略，2 个事件"


def check_retry_field() -> str:
    """`retry: 3000` 是独立字段，不属于任何事件。"""
    with client() as c:
        raw = c.get("/sse/retry").text
    events, retry, _ = parse_sse(raw)
    assert retry == 3000, retry
    assert len(events) == 2, events
    assert events[0]["data"] == '{"ok": true}', events[0]
    return f"retry={retry}，{len(events)} 个事件"


def check_error_event() -> str:
    """`event: error` 表达业务失败，中文不转义。"""
    with client() as c:
        raw = c.get("/sse/retry").text
    events, _, _ = parse_sse(raw)
    assert events[-1]["event"] == "error", events[-1]
    payload = json.loads(events[-1]["data"])
    assert payload["reason"] == "索引不可用", payload
    assert "\\u" not in raw, raw
    return payload["reason"]


def check_events_arrive_streaming() -> str:
    """逐条到达：4 个 data 行间隔 ≈ 60ms。"""
    stamps: list[float] = []
    with client().stream("GET", "/sse/chat", params={"text": "abc", "delay_ms": 60}) as response:
        started = time.perf_counter()
        for line in response.iter_lines():
            if line.startswith("data:"):
                stamps.append((time.perf_counter() - started) * 1000)
    assert len(stamps) == 4, stamps
    assert stamps[1] - stamps[0] > 30, stamps
    assert stamps[-1] > 150, stamps
    return f'到达 {"/".join(f"{s:.0f}" for s in stamps)}ms'


def check_broken_partial() -> str:
    """中途异常：200 + 已发出的 2 个事件。"""
    with client() as c:
        response = c.get("/sse/broken")
    assert response.status_code == 200, response.status_code
    events, _, _ = parse_sse(response.text)
    assert [event["id"] for event in events] == ["1", "2"], events
    return "200 + 2 个事件后断开"


def check_broken_raises_in_strict() -> str:
    """严格模式能看到真实异常。"""
    try:
        with client(strict=True) as c:
            c.get("/sse/broken")
    except RuntimeError as exc:
        assert "第 3 条" in str(exc), exc
        return str(exc)
    raise AssertionError("异常被吞了")


CHECKS = [
    ("媒体类型与头", check_media_type_and_headers),
    ("打字机事件", check_chat_events),
    ("data 是 JSON", check_event_data_is_json),
    ("空行分隔", check_blank_line_separator),
    ("自定义事件名", check_custom_event_names),
    ("id 递增", check_ids_increase),
    ("Last-Event-ID 续传", check_last_event_id_resume),
    ("多行 data", check_multiline_data),
    ("注释行不出事件", check_comment_not_event),
    ("retry 字段", check_retry_field),
    ("error 事件", check_error_event),
    ("逐条到达", check_events_arrive_streaming),
    ("中途异常截断", check_broken_partial),
    ("异常确实发生", check_broken_raises_in_strict),
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