"""第 34 章 · 自动验收。运行：python verify.py"""

import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)
strict = TestClient(main.app, raise_server_exceptions=False)

# 【作用】验收时静音应用日志：`logger.exception` 的堆栈只在实际运行时需要看
_app_logger = logging.getLogger("app.errors")
_app_logger.addHandler(logging.NullHandler())
_app_logger.propagate = False


def check_route_404_contract() -> str:
    """不存在的路由 → 统一结构。"""
    r = client.get("/no-such-route")
    assert r.status_code == 404, (r.status_code, r.text)
    body = r.json()
    assert body["code"] == "NOT_FOUND", body
    assert body["message"] == "Not Found", body
    assert body["trace_id"], body
    return f'404 code={body["code"]}, trace_id={body["trace_id"][:8]}…'


def check_http_exception_contract() -> str:
    """HTTPException → 统一结构 + 原 headers 保留。"""
    r = client.get("/manual")
    assert r.status_code == 401, (r.status_code, r.text)
    body = r.json()
    assert body["code"] == "UNAUTHORIZED", body
    assert body["message"] == "需要登录", body
    assert r.headers["www-authenticate"] == "Bearer", dict(r.headers)
    return f'401 code={body["code"]}'


def check_business_exception_contract() -> str:
    """业务异常 → 统一结构，额外字段进 details。"""
    r = client.get("/orders/99")
    assert r.status_code == 404, r.text
    body = r.json()
    assert body["code"] == "ORDER_NOT_FOUND", body
    assert body["details"] == {"order_id": 99}, body
    return f'details={body["details"]}'


def check_validation_contract() -> str:
    """校验错误 → 统一结构，details 是字段级列表。"""
    r = client.get("/echo", params={"age": "abc"})
    assert r.status_code == 422, r.text
    body = r.json()
    assert body["code"] == "VALIDATION_ERROR", body
    assert body["details"][0]["field"] == "age", body
    assert body["details"][0]["code"] == "int_parsing", body
    return f'code={body["code"]}, field={body["details"][0]["field"]}'


def check_unhandled_contract() -> str:
    """未捕获异常 → 500 + 统一结构，不泄露内部信息。"""
    r = strict.get("/crash")
    assert r.status_code == 500, (r.status_code, r.text)
    body = r.json()
    assert body["code"] == "INTERNAL_ERROR", body
    assert "RuntimeError" not in r.text, r.text
    assert "数据库" not in body["message"], body
    assert body["trace_id"], body
    return f'500 code={body["code"]}，无堆栈泄露'


def check_trace_id_header() -> str:
    """响应头带 X-Trace-Id，且与 body 一致。"""
    r = client.get("/orders/99")
    header = r.headers["x-trace-id"]
    assert header == r.json()["trace_id"], (header, r.json())
    return f"header == body == {header[:8]}…"


def check_trace_id_passthrough() -> str:
    """客户端 X-Request-Id 被沿用。"""
    r = client.get("/orders/99", headers={"X-Request-Id": "abc123"})
    assert r.json()["trace_id"] == "abc123", r.json()
    assert r.headers["x-trace-id"] == "abc123", dict(r.headers)
    return "沿用客户端 trace_id=abc123"


def check_trace_id_unique() -> str:
    """未传时每次生成不同的 trace_id。"""
    ids = {client.get("/orders/99").json()["trace_id"] for _ in range(3)}
    assert len(ids) == 3, ids
    return f"3 次请求 3 个不同 id（长度 {len(next(iter(ids)))}）"


def check_same_field_set() -> str:
    """四条路径的字段集合一致（details 可有可无）。"""
    bodies = [
        client.get("/no-such-route").json(),
        client.get("/manual").json(),
        client.get("/orders/99").json(),
        client.get("/echo", params={"age": "x"}).json(),
        strict.get("/crash").json(),
    ]
    required = {"code", "message", "trace_id"}
    for body in bodies:
        assert required <= set(body), body
        assert set(body) <= required | {"details"}, body
    return "5 条路径都是 {code, message, trace_id} + 可选 details"


def check_405_contract() -> str:
    """方法不允许 → 统一结构 + Allow 头。"""
    r = client.post("/orders/1")
    assert r.status_code == 405, (r.status_code, r.text)
    assert r.json()["code"] == "METHOD_NOT_ALLOWED", r.json()
    assert "GET" in r.headers.get("allow", ""), dict(r.headers)
    return f'405 code={r.json()["code"]}'


class _ListHandler(logging.Handler):
    """把日志记录收进列表，供断言使用（替代 pytest 的 caplog）。"""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def check_log_contains_trace_id() -> str:
    """日志里能用 trace_id 串起来。"""
    error_logger = logging.getLogger("app.errors")
    handler = _ListHandler()
    previous_level = error_logger.level
    error_logger.addHandler(handler)
    error_logger.setLevel(logging.WARNING)
    try:
        r = client.get("/orders/77", headers={"X-Request-Id": "trace-for-log"})
    finally:
        error_logger.removeHandler(handler)
        error_logger.setLevel(previous_level)

    assert r.status_code == 404, r.text
    records = [rec for rec in handler.records if getattr(rec, "trace_id", None) == "trace-for-log"]
    assert records, [rec.getMessage() for rec in handler.records]
    assert getattr(records[-1], "code", None) == "ORDER_NOT_FOUND", records[-1].__dict__
    return f"日志命中 {len(records)} 条 trace_id=trace-for-log"


CHECKS = [
    ("路由 404 统一结构", check_route_404_contract),
    ("HTTPException 统一结构", check_http_exception_contract),
    ("业务异常统一结构", check_business_exception_contract),
    ("校验错误统一结构", check_validation_contract),
    ("未捕获 500 统一结构", check_unhandled_contract),
    ("X-Trace-Id 响应头", check_trace_id_header),
    ("沿用客户端 id", check_trace_id_passthrough),
    ("trace_id 唯一", check_trace_id_unique),
    ("字段集合一致", check_same_field_set),
    ("405 统一结构", check_405_contract),
    ("日志可串 trace_id", check_log_contains_trace_id),
]


def run() -> int:
    failures = 0
    for name, func in CHECKS:
        try:
            print(f"[PASS] {name} -> {func()}")
        except AssertionError as exc:
            failures += 1
            print(f"[FAIL] {name} -> {exc}")
        except TypeError as exc:
            failures += 1
            print(f"[FAIL] {name} -> 需要 caplog：{exc}")
    print(f"\n结果：{len(CHECKS) - failures}/{len(CHECKS)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())