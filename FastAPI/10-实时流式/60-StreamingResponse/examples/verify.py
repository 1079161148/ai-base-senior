"""第 60 章 · 自动验收。运行：python verify.py"""

import sys
import time
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402


def client(strict: bool = False) -> TestClient:
    return TestClient(main.app, raise_server_exceptions=strict)


def read_chunks(path: str, params: dict | None = None) -> tuple[list[bytes], list[float]]:
    """【作用】记录每一块的到达时刻，用来证明「边产边发」"""
    chunks: list[bytes] = []
    stamps: list[float] = []
    with client().stream("GET", path, params=params or {}) as response:
        assert response.status_code == 200, response.status_code
        started = time.perf_counter()
        for chunk in response.iter_raw():
            chunks.append(chunk)
            stamps.append((time.perf_counter() - started) * 1000)
    return chunks, stamps


def check_csv_headers() -> str:
    """流式响应的头：有 `Content-Disposition`，**没有** `Content-Length`。"""
    with client() as c:
        response = c.get("/download/csv", params={"rows": 3})
    headers = response.headers
    assert headers["content-type"] == "text/csv; charset=utf-8", headers["content-type"]
    assert headers["content-disposition"] == 'attachment; filename="items.csv"', headers
    assert "content-length" not in headers, dict(headers)
    return f'{headers["content-type"]} + 无 Content-Length'


def check_csv_content() -> str:
    """内容正确：表头 + N 行。"""
    with client() as c:
        body = c.get("/download/csv", params={"rows": 3}).text
    lines = body.strip().split("\n")
    assert lines[0] == "id,name,price", lines
    assert len(lines) == 4, lines
    assert lines[3] == "2,商品0002,20", lines
    return f"{len(lines) - 1} 行数据"


def check_sync_generator_supported() -> str:
    """同步生成器也能用：Starlette 会丢进线程池迭代。"""
    with client() as c:
        body = c.get("/download/csv", params={"rows": 1000}).text
    assert body.count("\n") == 1001, body.count("\n")
    return "同步 yield 可用（线程池迭代）"


def check_chunks_arrive_separately() -> str:
    """3 块分别到达：首块 ~0ms，后续各等 60ms。"""
    chunks, stamps = read_chunks("/stream/slow", {"chunks": 3, "delay_ms": 60})
    assert len(chunks) == 3, chunks
    assert chunks == [b"chunk-0\n", b"chunk-1\n", b"chunk-2\n"], chunks
    assert stamps[1] - stamps[0] > 40, stamps
    assert stamps[2] - stamps[1] > 40, stamps
    return f'块间隔 {stamps[0]:.0f}/{stamps[1]:.0f}/{stamps[2]:.0f}ms'


def check_binary_size() -> str:
    """二进制流字节数精确。"""
    chunks, _ = read_chunks("/download/binary", {"size": 200_000})
    total = sum(len(chunk) for chunk in chunks)
    assert total == 200_000, total
    return f"{total} 字节 / {len(chunks)} 块"


def check_mixed_types() -> str:
    """`str` 与 `bytes` 混用：前者 UTF-8 编码，后者原样。"""
    with client() as c:
        response = c.get("/stream/str-and-bytes")
    assert response.status_code == 200, response.status_code
    assert response.text == "中文\nraw-bytes\n", response.text
    assert response.content == "中文\n".encode() + b"raw-bytes\n", response.content
    return "str + bytes 混用正常"


def check_broken_midway_partial() -> str:
    """中途抛异常：客户端仍收到 200 + 已发出的两块。"""
    with client() as c:
        response = c.get("/stream/broken")
    assert response.status_code == 200, response.status_code
    assert response.text == "part-1\npart-2\n", response.text
    return "200 + 2 块后截断"


def check_broken_midway_raises() -> str:
    """严格模式下能看到真实异常：证明生成器确实炸了，只是改不了状态码。"""
    try:
        with client(strict=True) as c:
            c.get("/stream/broken")
    except RuntimeError as exc:
        assert str(exc) == "第 3 块之前炸了", exc
        return str(exc)
    raise AssertionError("异常被吞了")


def check_cleanup_on_complete() -> str:
    """正常消费完：`finally` 执行（`gen:close`）。"""
    main.EVENTS.clear()
    with client() as c:
        c.get("/stream/tracked")
    events = list(main.EVENTS)
    assert events[0] == "gen:start", events
    assert events[-1] == "gen:close", events
    assert events.count("gen:yield:0") == 1, events
    return " → ".join(events)


def check_cleanup_on_disconnect() -> str:
    """客户端提前断开：`finally` 同样执行。"""
    main.EVENTS.clear()
    with client().stream("GET", "/stream/tracked") as response:
        for _ in response.iter_raw():
            break  # 只读一块就断
    time.sleep(0.1)
    events = list(main.EVENTS)
    assert "gen:close" in events, events
    assert "gen:yield:2" not in events, events
    return " → ".join(events)


def check_per_line_chunk_count() -> str:
    """逐行 yield：块数 = 行数 + 1（表头）。"""
    chunks, _ = read_chunks("/download/csv", {"rows": 2000})
    assert len(chunks) == 2001, len(chunks)
    return f"{len(chunks)} 块"


def check_batched_chunk_count() -> str:
    """批量 yield：2000 行 / 1000 = 3 块（表头 + 2）。"""
    chunks, _ = read_chunks("/download/csv-batched", {"rows": 2000, "batch": 1000})
    assert len(chunks) == 3, len(chunks)
    return f"{len(chunks)} 块"


def check_batching_is_faster() -> str:
    """批量 yield 比逐行快一个数量级以上。"""
    _, per_line = read_chunks("/download/csv", {"rows": 2000})
    _, batched = read_chunks("/download/csv-batched", {"rows": 2000, "batch": 1000})
    line_ms = per_line[-1]
    batch_ms = batched[-1]
    assert line_ms > batch_ms * 10, (line_ms, batch_ms)
    return f"逐行 {line_ms:.0f}ms → 批量 {batch_ms:.0f}ms"


def check_no_content_length_everywhere() -> str:
    """所有流式端点都不带 `Content-Length`。"""
    checked = []
    with client() as c:
        for path, params in [
            ("/download/csv", {"rows": 10}),
            ("/download/binary", {"size": 1000}),
            ("/stream/slow", {"chunks": 1}),
            ("/stream/headers", None),
        ]:
            response = c.get(path, params=params)
            assert "content-length" not in response.headers, (path, dict(response.headers))
            checked.append(path)
    return ", ".join(checked)


CHECKS = [
    ("CSV 响应头", check_csv_headers),
    ("CSV 内容", check_csv_content),
    ("同步生成器可用", check_sync_generator_supported),
    ("分块到达", check_chunks_arrive_separately),
    ("二进制大小", check_binary_size),
    ("str/bytes 混用", check_mixed_types),
    ("中途异常截断", check_broken_midway_partial),
    ("中途异常确实发生", check_broken_midway_raises),
    ("正常结束清理", check_cleanup_on_complete),
    ("提前断开清理", check_cleanup_on_disconnect),
    ("逐行块数", check_per_line_chunk_count),
    ("批量块数", check_batched_chunk_count),
    ("批量更快", check_batching_is_faster),
    ("无 Content-Length", check_no_content_length_everywhere),
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