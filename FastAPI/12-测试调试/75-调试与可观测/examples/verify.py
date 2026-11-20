"""第 75 章 · 自动验收。运行：python verify.py"""

import logging
import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

EXPECTED_PATHS = ["/boom", "/items", "/login", "/missing", "/slow"]
EXPECTED_IDS = [
    "boom_boom_get",
    "list_items_items_get",
    "login_login_post",
    "missing_missing_get",
    "slow_slow_get",
]


class ListHandler(logging.Handler):
    """【作用】把日志收进 list，替代 caplog"""

    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def collected():
    handler = ListHandler()
    main.LOGGER.addHandler(handler)
    main.LOGGER.setLevel(logging.DEBUG)
    return handler


def client() -> TestClient:
    return TestClient(main.app, raise_server_exceptions=False)


def check_request_id() -> str:
    """响应头带 8 位请求 ID。"""
    with client() as c:
        response = c.get("/items")
    request_id = response.headers["x-request-id"]
    assert len(request_id) == 8, request_id
    return request_id


def check_request_id_propagated() -> str:
    """客户端传入的 ID 被沿用。"""
    with client() as c:
        response = c.get("/items", headers={"X-Request-ID": "trace-42"})
    assert response.headers["x-request-id"] == "trace-42", response.headers
    return "trace-42"


def check_elapsed_header() -> str:
    """`X-Elapsed-Ms` 是可解析的浮点数。"""
    with client() as c:
        response = c.get("/items")
    value = float(response.headers["x-elapsed-ms"])
    assert value >= 0, value
    return f"{value}ms"


def check_one_line_log() -> str:
    """每个请求一行，含方法/路径/状态码。"""
    handler = collected()
    try:
        with client() as c:
            c.get("/items")
        messages = [record.getMessage() for record in handler.records]
        assert any(
            "method=GET" in message and "path=/items" in message and "status=200" in message
            for message in messages
        ), messages
        return "method/path/status 齐全"
    finally:
        main.LOGGER.removeHandler(handler)


def check_correlation_id() -> str:
    """日志记录带 `request_id` 属性。"""
    handler = collected()
    try:
        with client() as c:
            c.get("/items", headers={"X-Request-ID": "trace-42"})
        matched = [
            record for record in handler.records if getattr(record, "request_id", None) == "trace-42"
        ]
        assert matched, [(record.request_id, record.getMessage()) for record in handler.records]
        return "trace-42 出现在日志"
    finally:
        main.LOGGER.removeHandler(handler)


def check_slow_is_warning() -> str:
    """耗时超过阈值 → WARNING。"""
    handler = collected()
    try:
        with client() as c:
            c.get("/slow", params={"ms": 80})
        slow = [
            record
            for record in handler.records
            if "/slow" in record.getMessage() and record.levelno >= logging.WARNING
        ]
        assert slow, [(record.levelname, record.getMessage()) for record in handler.records]
        return f"WARNING / {slow[0].getMessage()[:40]}"
    finally:
        main.LOGGER.removeHandler(handler)


def check_fast_is_info() -> str:
    """快请求 → INFO。"""
    handler = collected()
    try:
        with client() as c:
            c.get("/items")
        fast = [
            record
            for record in handler.records
            if "/items" in record.getMessage() and record.levelno == logging.INFO
        ]
        assert fast, [(record.levelname, record.getMessage()) for record in handler.records]
        return "INFO"
    finally:
        main.LOGGER.removeHandler(handler)


def check_500_carries_request_id() -> str:
    """500 响应既带头也带 body 里的 `request_id`。"""
    with client() as c:
        response = c.get("/boom")
    body = response.json()
    assert response.status_code == 500, response.status_code
    assert body["detail"] == "internal server error", body
    assert response.headers["x-request-id"] == body["request_id"], (response.headers, body)
    return body["request_id"]


def check_500_logged_as_error() -> str:
    """异常路径用 `LOGGER.exception` → ERROR。"""
    handler = collected()
    try:
        with client() as c:
            c.get("/boom")
        errors = [record for record in handler.records if record.levelno >= logging.ERROR]
        assert errors, [(record.levelname, record.getMessage()) for record in handler.records]
        return errors[0].getMessage()[:40]
    finally:
        main.LOGGER.removeHandler(handler)


def check_debug_leaks_traceback() -> str:
    """**反例**：`debug=True` 返回 traceback。"""
    lenient = TestClient(main.debug_app, raise_server_exceptions=False)
    response = lenient.get("/boom")
    assert response.status_code == 500, response.status_code
    assert "Traceback" in response.text, response.text[:100]
    return f"暴露 {len(response.text)} 字节"


def check_prod_hides_traceback() -> str:
    """`debug=False` 不暴露内部细节。"""
    with client() as c:
        response = c.get("/boom")
    assert "Traceback" not in response.text, response.text[:100]
    assert "内部炸了" not in response.text, response.text[:100]
    return "只有通用错误信息"


def check_404_normal() -> str:
    """业务 404 不被中间件吞掉。"""
    with client() as c:
        response = c.get("/missing")
    assert response.status_code == 404, response.status_code
    assert response.json()["detail"] == "not here", response.json()
    return "404 / not here"


def check_openapi_paths_stable() -> str:
    """契约快照：路径集合不变。"""
    with client() as c:
        paths = sorted(c.get("/openapi.json").json()["paths"])
    assert paths == EXPECTED_PATHS, paths
    return f"{len(paths)} 条"


def check_operation_ids_stable() -> str:
    """契约快照：operationId 集合不变。"""
    with client() as c:
        schema = c.get("/openapi.json").json()
    ids = sorted(
        operation["operationId"]
        for path in schema["paths"].values()
        for operation in path.values()
    )
    assert ids == EXPECTED_IDS, ids
    return f"{len(ids)} 个"


def check_every_operation_has_summary() -> str:
    """每个 operation 都有 `summary`。"""
    with client() as c:
        schema = c.get("/openapi.json").json()
    missing = [
        f"{method} {path}"
        for path, operations in schema["paths"].items()
        for method, operation in operations.items()
        if not operation.get("summary")
    ]
    assert not missing, missing
    return "5 个 operation 全有"


def check_password_masked() -> str:
    """日志里不出现明文密码。"""
    handler = collected()
    try:
        with client() as c:
            c.post("/login", json={"username": "u", "password": "hunter2"})
        joined = " ".join(record.getMessage() for record in handler.records)
        assert "hunter2" not in joined, joined
        assert "***" in joined, joined
        return "password → ***"
    finally:
        main.LOGGER.removeHandler(handler)


CHECKS = [
    ("请求 ID", check_request_id),
    ("ID 透传", check_request_id_propagated),
    ("耗时头", check_elapsed_header),
    ("一行日志", check_one_line_log),
    ("日志关联 ID", check_correlation_id),
    ("慢请求 WARNING", check_slow_is_warning),
    ("快请求 INFO", check_fast_is_info),
    ("500 带 ID", check_500_carries_request_id),
    ("500 记 ERROR", check_500_logged_as_error),
    ("debug 泄露 traceback", check_debug_leaks_traceback),
    ("生产隐藏细节", check_prod_hides_traceback),
    ("404 正常", check_404_normal),
    ("契约路径", check_openapi_paths_stable),
    ("契约 operationId", check_operation_ids_stable),
    ("summary 齐全", check_every_operation_has_summary),
    ("密码脱敏", check_password_masked),
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