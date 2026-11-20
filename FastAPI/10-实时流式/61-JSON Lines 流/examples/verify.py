"""第 61 章 · 自动验收。运行：python verify.py"""

import json
import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402


def client(strict: bool = False) -> TestClient:
    return TestClient(main.app, raise_server_exceptions=strict)


def check_json_array_is_single_line() -> str:
    """普通 JSON 数组：整个 body 只有 1 行，带 `Content-Length`。"""
    with client() as c:
        response = c.get("/search/json", params={"limit": 5})
    assert response.headers["content-type"] == "application/json", response.headers
    assert len(response.text.splitlines()) == 1, response.text
    assert "content-length" in response.headers, dict(response.headers)
    assert isinstance(json.loads(response.text), list), response.text
    return "1 行 / 有 Content-Length"


def check_jsonl_media_type() -> str:
    """JSONL 的 `Content-Type` 是 `application/jsonl`，**不带 charset**。"""
    with client() as c:
        response = c.get("/search/jsonl", params={"limit": 3})
    assert response.headers["content-type"] == "application/jsonl", response.headers["content-type"]
    assert "content-length" not in response.headers, dict(response.headers)
    return "application/jsonl + 无 Content-Length"


def check_jsonl_line_count() -> str:
    """行数 = 记录数，且每行以 `\\n` 结尾。"""
    with client() as c:
        body = c.get("/search/jsonl", params={"limit": 6}).text
    assert body.count("\n") == 6, body.count("\n")
    assert body.endswith("\n"), body[-20:]
    return "6 行，每行 `\\n` 结尾"


def check_each_line_parses() -> str:
    """每行独立 `json.loads` 成功，且是 dict。"""
    with client() as c:
        body = c.get("/search/jsonl", params={"limit": 5}).text
    items = [json.loads(line) for line in body.splitlines()]
    assert len(items) == 5, items
    assert all(isinstance(item, dict) for item in items), items
    assert [item["id"] for item in items] == [1, 2, 3, 4, 5], items
    return "5 行全部可独立解析"


def check_fields_complete() -> str:
    """字段完整：`id` / `title` / `score`。"""
    with client() as c:
        item = json.loads(c.get("/search/jsonl", params={"limit": 1}).text.splitlines()[0])
    assert set(item) == {"id", "title", "score"}, item
    assert item["title"] == "结果 001", item
    return "id/title/score"


def check_chinese_not_escaped() -> str:
    """`ensure_ascii=False`：中文原样，不是 `\\uXXXX`。"""
    with client() as c:
        body = c.get("/search/jsonl", params={"limit": 1}).text
    assert "结果 001" in body, body
    assert "\\u" not in body, body
    return "中文原样输出"


def check_lines_arrive_one_by_one() -> str:
    """逐行到达：3 行间隔 ≈ 50ms，证明不是攒完再发。"""
    stamps: list[float] = []
    lines: list[str] = []
    with client().stream("GET", "/search/jsonl", params={"limit": 3, "delay_ms": 50}) as response:
        started = time.perf_counter()
        for line in response.iter_lines():
            if line:
                lines.append(line)
                stamps.append((time.perf_counter() - started) * 1000)
    assert len(lines) == 3, lines
    assert stamps[1] - stamps[0] > 25, stamps
    assert stamps[2] - stamps[1] > 25, stamps
    return f'到达 {stamps[0]:.0f}/{stamps[1]:.0f}/{stamps[2]:.0f}ms'


def check_array_is_all_or_nothing() -> str:
    """对照：JSON 数组按行解析只能拿到整体（1 行 → 1 个 list）。"""
    with client() as c:
        body = c.get("/search/json", params={"limit": 5}).text
    lines = body.splitlines()
    assert len(lines) == 1, lines
    parsed = json.loads(lines[0])
    assert isinstance(parsed, list) and len(parsed) == 5, parsed
    return "1 行 = 1 个完整数组"


def check_broken_midway_partial() -> str:
    """中途抛异常：200 + 已发出的 3 行，第 4 行永远不来。"""
    with client() as c:
        response = c.get("/search/jsonl/broken", params={"limit": 5})
    assert response.status_code == 200, response.status_code
    lines = [line for line in response.text.splitlines() if line]
    assert len(lines) == 3, lines
    assert [json.loads(line)["id"] for line in lines] == [1, 2, 3], lines
    return "200 + 3 行后截断"


def check_broken_raises_in_strict() -> str:
    """严格模式能看到真实异常，证明转发中断不是客户端问题。"""
    try:
        with client(strict=True) as c:
            c.get("/search/jsonl/broken", params={"limit": 5})
    except RuntimeError as exc:
        assert "第 4 条" in str(exc), exc
        return str(exc)
    raise AssertionError("异常被吞了")


def check_error_line() -> str:
    """用一行 `{"error": ...}` 表达失败，仍是合法 JSONL。"""
    with client() as c:
        body = c.get("/search/jsonl/error-line", params={"limit": 5}).text
    items = [json.loads(line) for line in body.splitlines()]
    assert len(items) == 4, items
    assert [item.get("id") for item in items[:3]] == [1, 2, 3], items
    assert items[-1]["error"] == "索引在第 4 条之后不可用", items[-1]
    assert items[-1]["code"] == "INDEX_DOWN", items[-1]
    return "3 条数据 + 1 条错误"


def check_error_line_terminates() -> str:
    """错误行之后不再有数据（不会既报错又继续）。"""
    with client() as c:
        body = c.get("/search/jsonl/error-line", params={"limit": 10}).text
    items = [json.loads(line) for line in body.splitlines()]
    assert items[-1].get("error"), items
    assert all("error" not in item for item in items[:-1]), items
    return "错误行是最后一行"


def check_headers_probe() -> str:
    """关掉代理缓冲与缓存。"""
    with client() as c:
        headers = c.get("/search/jsonl/headers").headers
    assert headers["x-accel-buffering"] == "no", dict(headers)
    assert headers["cache-control"] == "no-cache", dict(headers)
    return "X-Accel-Buffering: no + no-cache"


def check_limit_bounds() -> str:
    """`limit` 越界 → 422。"""
    with client() as c:
        assert c.get("/search/jsonl", params={"limit": 0}).status_code == 422
        assert c.get("/search/jsonl", params={"limit": 201}).status_code == 422
    return "0/201 → 422"


CHECKS = [
    ("JSON 数组单行", check_json_array_is_single_line),
    ("JSONL 媒体类型", check_jsonl_media_type),
    ("行数与换行", check_jsonl_line_count),
    ("逐行可解析", check_each_line_parses),
    ("字段完整", check_fields_complete),
    ("中文不转义", check_chinese_not_escaped),
    ("逐行到达", check_lines_arrive_one_by_one),
    ("数组是整体的", check_array_is_all_or_nothing),
    ("中途异常截断", check_broken_midway_partial),
    ("异常确实发生", check_broken_raises_in_strict),
    ("错误行表达", check_error_line),
    ("错误行终止", check_error_line_terminates),
    ("禁缓冲头", check_headers_probe),
    ("limit 边界", check_limit_bounds),
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