"""第 79 章 · 79 条验收。运行：python verify.py

【要点】本章不复制业务代码，直接验收第 78 章的产物：
        `sys.path` 指向 `../78-生产化改造/examples`。
        改了 78 章的代码，这里立即反映出来 —— 这才是「验收」而不是「另写一份」。

分类：A 业务(20) / B 错误契约(12) / C 鉴权安全(15)
      D 数据事务(10) / E 可观测(8) / F 配置部署(8) / G 文档卫生(6)
"""

import logging
import os
import re
import shutil
import sqlite3
import sys
import tempfile
import time
from pathlib import Path
from typing import Any, Callable

HERE = Path(__file__).parent
PROJECT = HERE.parent.parent / "78-生产化改造" / "examples"
sys.path.insert(0, str(PROJECT))

# ------------------------------------------------------------
# 环境变量必须先于 import main
# ------------------------------------------------------------
TMP_DIR = tempfile.mkdtemp(prefix="ch79_")
DB_PATH = os.path.join(TMP_DIR, "accept.db")
TOKEN = "accept-token-79"
os.environ["APP_DB_PATH"] = DB_PATH
os.environ["APP_TOKEN"] = TOKEN
os.environ["APP_LOG_LEVEL"] = "ERROR"
os.environ["APP_SLOW_MS"] = "1"
os.environ["APP_ENV"] = "test"

from fastapi.testclient import TestClient  # noqa: E402
from pydantic import ValidationError  # noqa: E402

import main  # noqa: E402
from config import Settings  # noqa: E402
from db import init_db  # noqa: E402

AUTH = {"Authorization": f"Bearer {TOKEN}"}
BASE = "/api/v1/todos"

CTX: dict[str, Any] = {"client": None, "logs": []}


class ListHandler(logging.Handler):
    def __init__(self) -> None:
        super().__init__()
        self.records: list[logging.LogRecord] = []

    def emit(self, record: logging.LogRecord) -> None:
        self.records.append(record)


def reset_db() -> None:
    init_db(main.settings)
    with sqlite3.connect(main.settings.db_path) as conn:
        conn.execute("DELETE FROM todos")
        conn.execute("DELETE FROM sqlite_sequence WHERE name = 'todos'")


def seed(n: int = 3) -> None:
    payloads = [("写代码", "high"), ("跑验收", "medium"), ("写复盘", "low")]
    for index in range(n):
        title, priority = payloads[index % len(payloads)]
        CTX["client"].post(BASE, json={"title": title, "priority": priority}, headers=AUTH)


def fresh(n: int = 3) -> TestClient:
    reset_db()
    if n:
        seed(n)
    return CTX["client"]


def rows() -> list[tuple]:
    with sqlite3.connect(main.settings.db_path) as conn:
        return conn.execute("SELECT id, title, done, priority FROM todos ORDER BY id").fetchall()


def body_has_error_keys(response) -> bool:
    payload = response.json()
    return set(payload) == {"error"} and set(payload["error"]) <= {"code", "message", "details"}


# ============================================================
# A 业务正确性（20）
# ============================================================
def a01() -> str:
    c = fresh(0)
    assert c.post(BASE, json={"title": "x"}, headers=AUTH).status_code == 201
    return "201"


def a02() -> str:
    c = fresh(0)
    response = c.post(BASE, json={"title": "x"}, headers=AUTH)
    assert response.headers["location"] == f"{BASE}/{response.json()['id']}"
    return response.headers["location"]


def a03() -> str:
    c = fresh(0)
    body = c.post(BASE, json={"title": "x"}, headers=AUTH).json()
    assert set(body) == {"id", "title", "done", "priority", "created_at"}, body
    return ",".join(body)


def a04() -> str:
    c = fresh(0)
    assert c.post(BASE, json={"title": "x"}, headers=AUTH).json()["priority"] == "medium"
    return "medium"


def a05() -> str:
    c = fresh(0)
    assert c.post(BASE, json={"title": "x"}, headers=AUTH).json()["done"] is False
    return "false"


def a06() -> str:
    body = fresh().get(BASE).json()
    assert set(body) == {"items", "total", "page", "size", "pages"}, body
    return "5 键"


def a07() -> str:
    assert fresh(3).get(BASE).json()["total"] == 3
    return "3"


def a08() -> str:
    body = fresh(3).get(BASE, params={"page": 1, "size": 2}).json()
    assert len(body["items"]) == 2
    return "2 条"


def a09() -> str:
    body = fresh(3).get(BASE, params={"page": 2, "size": 2}).json()
    assert len(body["items"]) == 1
    return "1 条"


def a10() -> str:
    body = fresh(3).get(BASE, params={"size": 2}).json()
    assert body["pages"] == 2, body
    return "ceil(3/2)=2"


def a11() -> str:
    body = fresh(3).get(BASE, params={"page": 99}).json()
    assert body["items"] == []
    return "[]"


def a12() -> str:
    body = fresh(3).get(BASE, params={"page": 99}).json()
    assert body["total"] == 3
    return "3"


def a13() -> str:
    c = fresh(3)
    c.patch(f"{BASE}/1", json={"done": True}, headers=AUTH)
    items = c.get(BASE, params={"done": True}).json()["items"]
    assert [item["id"] for item in items] == [1], items
    return "id=1"


def a14() -> str:
    c = fresh(3)
    c.patch(f"{BASE}/1", json={"done": True}, headers=AUTH)
    items = c.get(BASE, params={"done": False}).json()["items"]
    assert [item["id"] for item in items] == [2, 3], items
    return "id=2,3"


def a15() -> str:
    items = fresh(3).get(BASE, params={"priority": "high"}).json()["items"]
    assert [item["id"] for item in items] == [1], items
    return "id=1"


def a16() -> str:
    items = fresh(3).get(BASE, params={"q": "验收"}).json()["items"]
    assert [item["id"] for item in items] == [2], items
    return "id=2"


def a17() -> str:
    c = fresh(3)
    c.post(BASE, json={"title": "ABC"}, headers=AUTH)
    items = c.get(BASE, params={"q": "abc"}).json()["items"]
    assert len(items) == 1, items
    return "大小写不敏感"


def a18() -> str:
    body = fresh(3).get(f"{BASE}/1").json()
    assert set(body) == {"id", "title", "done", "priority", "created_at"}
    return "字段齐全"


def a19() -> str:
    c = fresh(3)
    before = c.get(f"{BASE}/1").json()
    after = c.patch(f"{BASE}/1", json={"done": True}, headers=AUTH).json()
    assert after["title"] == before["title"] and after["priority"] == before["priority"]
    assert after["done"] is True
    return "仅 done"


def a20() -> str:
    c = fresh(3)
    assert c.delete(f"{BASE}/1", headers=AUTH).status_code == 204
    assert c.get(f"{BASE}/1").status_code == 404
    return "204 → 404"


# ============================================================
# B 错误契约（12）
# ============================================================
def b01() -> str:
    response = fresh(3).get(f"{BASE}/999")
    assert response.json()["error"]["code"] == "not_found"
    return "not_found"


def b02() -> str:
    response = fresh(3).get(f"{BASE}/999")
    assert "999" in response.json()["error"]["message"]
    return "含 id"


def b03() -> str:
    assert body_has_error_keys(fresh(3).get(f"{BASE}/999"))
    return "顶层仅 error"


def b04() -> str:
    response = fresh(3).post(BASE, json={"title": "x"})
    assert response.status_code == 401 and response.json()["error"]["code"] == "unauthorized"
    return "unauthorized"


def b05() -> str:
    response = fresh(3).post(BASE, json={"title": "x"})
    assert "bearer" in response.headers["www-authenticate"].lower()
    return "WWW-Authenticate"


def b06() -> str:
    response = fresh(3).post(BASE, json={"title": ""}, headers=AUTH)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    return "validation_error"


def b07() -> str:
    fields = fresh(3).post(BASE, json={"title": ""}, headers=AUTH).json()["error"]["details"]["fields"]
    assert fields[0]["loc"] == "body.title", fields
    return "body.title"


def b08() -> str:
    fields = fresh(3).post(BASE, json={"title": ""}, headers=AUTH).json()["error"]["details"]["fields"]
    assert fields[0]["type"] == "string_too_short", fields
    return "string_too_short"


def b09() -> str:
    assert fresh(3).get(BASE, params={"page": 0}).status_code == 422
    return "page=0"


def b10() -> str:
    """静态上限 `le=1000`；业务上限由 `page_size_max` clamp"""
    assert fresh(3).get(BASE, params={"size": 1001}).status_code == 422
    return "size=1001"


def b11() -> str:
    response = fresh(3).get("/boom")
    assert response.status_code == 500 and response.json()["error"]["code"] == "internal_error"
    return "internal_error"


def b12() -> str:
    text = fresh(3).get("/boom").text
    assert "Traceback" not in text and "内部炸了" not in text and "RuntimeError" not in text
    return "无堆栈/无文案"


# ============================================================
# C 鉴权与安全（15）
# ============================================================
def c01() -> str:
    assert fresh(3).post(BASE, json={"title": "x"}).status_code == 401
    return "POST 401"


def c02() -> str:
    assert fresh(3).patch(f"{BASE}/1", json={"done": True}).status_code == 401
    return "PATCH 401"


def c03() -> str:
    assert fresh(3).delete(f"{BASE}/1").status_code == 401
    return "DELETE 401"


def c04() -> str:
    assert fresh(3).get(BASE).status_code == 200
    return "列表 200"


def c05() -> str:
    assert fresh(3).get(f"{BASE}/1").status_code == 200
    return "详情 200"


def c06() -> str:
    assert fresh(3).get(f"{BASE}/stats").status_code == 200
    return "统计 200"


def c07() -> str:
    response = fresh(3).post(BASE, json={"title": "x"}, headers={"Authorization": "Bearer wrong"})
    assert response.status_code == 401
    return "错令牌 401"


def c08() -> str:
    response = fresh(3).post(BASE, json={"title": "x"}, headers={"Authorization": "Bearer demo-token"})
    assert response.status_code == 401
    return "demo-token 失效"


def c09() -> str:
    assert "RuntimeError" not in fresh(3).get("/boom").text
    return "无异常类名"


def c10() -> str:
    assert "不该出现" not in fresh(3).get("/boom").text
    return "无内部消息"


def c11() -> str:
    paths = fresh(3).get("/openapi.json").json()["paths"]
    assert "/boom" not in paths
    return "不在文档"


def c12() -> str:
    paths = fresh(3).get("/openapi.json").json()["paths"]
    assert f"{BASE}/_tx" not in paths
    return "不在文档"


def c13() -> str:
    assert TOKEN not in repr(main.settings)
    return "repr 掩码"


def c14() -> str:
    handler = ListHandler()
    logger = logging.getLogger("app.request")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        fresh(3).get(BASE, headers=AUTH)
        joined = " ".join(record.getMessage() for record in handler.records)
        for record in handler.records:
            joined += repr(getattr(record, "__dict__", ""))
        assert TOKEN not in joined, "令牌进了日志"
        return f"{len(handler.records)} 条日志无令牌"
    finally:
        logger.removeHandler(handler)


def source_files() -> list[Path]:
    """业务源码：排除验收脚本，否则它自己被扫出问题"""
    return [
        path
        for path in PROJECT.glob("*.py")
        if path.name not in {"verify.py"} and not path.name.startswith("test")
    ]


def c15() -> str:
    offenders = [
        path.name
        for path in source_files()
        if path.name != "config.py" and "demo-token" in path.read_text(encoding="utf-8")
    ]
    assert not offenders, offenders
    return f"{len(source_files())} 个文件，仅 config 有默认值"


# ============================================================
# D 数据与事务（10）
# ============================================================
def d01() -> str:
    c = fresh(0)
    c.post(BASE, json={"title": "落库"}, headers=AUTH)
    assert [row[1] for row in rows()] == ["落库"]
    return "1 行"


def d02() -> str:
    c = fresh(0)
    c.post(BASE, json={"title": "提交"}, headers=AUTH)
    c.get(BASE)  # 触发另一个请求/事务
    assert len(rows()) == 1
    return "提交后仍在"


def d03() -> str:
    response = fresh(0).post(f"{BASE}/_tx", headers=AUTH)
    assert response.status_code == 409, response.status_code
    assert response.json()["error"]["code"] == "tx_demo"
    return "409"


def d04() -> str:
    c = fresh(1)
    before = len(rows())
    c.post(f"{BASE}/_tx", headers=AUTH)
    assert len(rows()) == before, (before, len(rows()))
    return f"{before} → {before}"


def d05() -> str:
    fresh(0).post(f"{BASE}/_tx", headers=AUTH)
    titles = [row[1] for row in rows()]
    assert "这条不该留在库里" not in titles, titles
    return "无残留标题"


def d06() -> str:
    c = fresh(1)
    c.patch(f"{BASE}/1", json={"title": "改名"}, headers=AUTH)
    assert rows()[0][1] == "改名"
    return "已持久化"


def d07() -> str:
    c = fresh(1)
    c.delete(f"{BASE}/1", headers=AUTH)
    assert rows() == []
    return "已删除"


def d08() -> str:
    c = fresh(0)
    ids = [c.post(BASE, json={"title": "x"}, headers=AUTH).json()["id"] for _ in range(3)]
    assert ids == [1, 2, 3], ids
    return "1,2,3"


def d09() -> str:
    c = fresh(3)
    c.patch(f"{BASE}/1", json={"done": True}, headers=AUTH)
    stats = c.get(f"{BASE}/stats").json()
    assert (stats["total"], stats["done"], stats["pending"]) == (3, 1, 2), stats
    return "3/1/2"


def d10() -> str:
    stats = fresh(0).get(f"{BASE}/stats").json()
    assert stats["total"] == 0 and stats["pending"] == 0, stats
    return "0"


# ============================================================
# E 可观测（8）
# ============================================================
def e01() -> str:
    value = fresh(3).get(BASE).headers["x-request-id"]
    assert len(value) == 8, value
    return value


def e02() -> str:
    value = fresh(3).get(BASE, headers={"X-Request-ID": "trace-79"}).headers["x-request-id"]
    assert value == "trace-79"
    return value


def e03() -> str:
    assert float(fresh(3).get(BASE).headers["x-elapsed-ms"]) >= 0
    return "可解析"


def e04() -> str:
    value = fresh(3).get(BASE).headers["x-app-version"]
    assert value == main.settings.version
    return value


def _capture(path: str) -> list[logging.LogRecord]:
    handler = ListHandler()
    logger = logging.getLogger("app.request")
    logger.addHandler(handler)
    logger.setLevel(logging.DEBUG)
    try:
        fresh(3).get(path)
        return list(handler.records)
    finally:
        logger.removeHandler(handler)


def e05() -> str:
    assert any("method=GET" in record.getMessage() for record in _capture(BASE))
    return "method=GET"


def e06() -> str:
    assert any(f"path={BASE}" in record.getMessage() for record in _capture(BASE))
    return f"path={BASE}"


def e07() -> str:
    assert any("status=200" in record.getMessage() for record in _capture(BASE))
    return "status=200"


def e08() -> str:
    records = _capture(BASE)
    assert any(getattr(record, "request_id", None) not in (None, "-") for record in records)
    return "有 request_id"


# ============================================================
# F 配置与部署（8）
# ============================================================
def f01() -> str:
    assert main.settings.db_path == DB_PATH
    return "来自 env"


def f02() -> str:
    assert main.settings.token.get_secret_value() == TOKEN
    return "来自 env"


def f03() -> str:
    assert main.settings.env == "test"
    return "test"


def f04() -> str:
    try:
        Settings(_env_file=None, env="staging")  # type: ignore[arg-type]
    except ValidationError as exc:
        assert exc.errors()[0]["type"] == "literal_error"
        return "literal_error"
    raise AssertionError("非法 env 竟然通过了")


def f05() -> str:
    assert fresh(3).get("/healthz").status_code == 200
    return "200"


def f06() -> str:
    body = fresh(3).get("/healthz").json()
    assert "db" not in str(body).lower(), body
    return "不查库"


def f07() -> str:
    assert fresh(3).get("/docs").status_code == 200
    return "200"


def f08() -> str:
    paths = sorted(fresh(3).get("/openapi.json").json()["paths"])
    assert paths == [BASE, f"{BASE}/stats", f"{BASE}/{{todo_id}}", "/healthz"], paths
    return f"{len(paths)} 条"


# ============================================================
# G 文档与代码卫生（6）
# ============================================================
def g01() -> str:
    schema = fresh(3).get("/openapi.json").json()
    missing = [
        f"{method} {path}"
        for path, ops in schema["paths"].items()
        for method, op in ops.items()
        if not op.get("summary")
    ]
    assert not missing, missing
    return "全有 summary"


def g02() -> str:
    schema = fresh(3).get("/openapi.json").json()
    missing = [
        f"{method} {path}"
        for path, ops in schema["paths"].items()
        for method, op in ops.items()
        if not op.get("tags")
    ]
    assert not missing, missing
    return "全有 tags"


def g03() -> str:
    offenders = [
        path.name
        for path in source_files()
        if re.search(r"except\s*:", path.read_text(encoding="utf-8"))
    ]
    assert not offenders, offenders
    return f"{len(source_files())} 个文件无裸 except"


def g04() -> str:
    text = (PROJECT / "repo.py").read_text(encoding="utf-8")
    assert "%s" not in text and ".format(" not in text and "?" in text
    return "全 ? 占位"


def g05() -> str:
    offenders = [
        path.name
        for path in source_files()
        if re.search(r"^\s*print\(", path.read_text(encoding="utf-8"), flags=re.MULTILINE)
    ]
    assert not offenders, offenders
    return "无 print"


def g06() -> str:
    schema = fresh(3).get("/openapi.json").json()
    missing = [
        f"{method} {path}"
        for path, ops in schema["paths"].items()
        for method, op in ops.items()
        if not ({"200", "201", "204"} & set(op["responses"]))
    ]
    assert not missing, missing
    return "响应已声明"


CASES: list[tuple[str, str, Callable[[], str]]] = [
    ("A01", "创建 201", a01),
    ("A02", "Location 头", a02),
    ("A03", "创建 body 字段", a03),
    ("A04", "默认 priority", a04),
    ("A05", "默认 done", a05),
    ("A06", "分页信封 5 键", a06),
    ("A07", "total 正确", a07),
    ("A08", "首页 2 条", a08),
    ("A09", "第二页 1 条", a09),
    ("A10", "pages 向上取整", a10),
    ("A11", "越界页空列表", a11),
    ("A12", "越界页 total 不变", a12),
    ("A13", "过滤 done=true", a13),
    ("A14", "过滤 done=false", a14),
    ("A15", "过滤 priority", a15),
    ("A16", "过滤 q", a16),
    ("A17", "q 不区分大小写", a17),
    ("A18", "详情字段", a18),
    ("A19", "部分更新", a19),
    ("A20", "删除后 404", a20),
    ("B01", "404 code", b01),
    ("B02", "404 含 id", b02),
    ("B03", "顶层仅 error", b03),
    ("B04", "401 code", b04),
    ("B05", "401 WWW-Authenticate", b05),
    ("B06", "422 code", b06),
    ("B07", "422 loc 格式", b07),
    ("B08", "422 type", b08),
    ("B09", "query page 校验", b09),
    ("B10", "query size 校验", b10),
    ("B11", "500 code", b11),
    ("B12", "500 无堆栈", b12),
    ("C01", "POST 需令牌", c01),
    ("C02", "PATCH 需令牌", c02),
    ("C03", "DELETE 需令牌", c03),
    ("C04", "列表公开", c04),
    ("C05", "详情公开", c05),
    ("C06", "统计公开", c06),
    ("C07", "错令牌", c07),
    ("C08", "默认令牌失效", c08),
    ("C09", "无异常类名", c09),
    ("C10", "无内部消息", c10),
    ("C11", "/boom 不在文档", c11),
    ("C12", "/_tx 不在文档", c12),
    ("C13", "repr 掩码", c13),
    ("C14", "日志无令牌", c14),
    ("C15", "无硬编码令牌", c15),
    ("D01", "创建落库", d01),
    ("D02", "提交后仍在", d02),
    ("D03", "事务 409", d03),
    ("D04", "回滚行数不变", d04),
    ("D05", "回滚无残留", d05),
    ("D06", "更新持久化", d06),
    ("D07", "删除持久化", d07),
    ("D08", "id 自增", d08),
    ("D09", "统计与库一致", d09),
    ("D10", "空库统计", d10),
    ("E01", "请求 ID", e01),
    ("E02", "ID 透传", e02),
    ("E03", "耗时头", e03),
    ("E04", "版本头", e04),
    ("E05", "日志 method", e05),
    ("E06", "日志 path", e06),
    ("E07", "日志 status", e07),
    ("E08", "日志 request_id", e08),
    ("F01", "库路径来自 env", f01),
    ("F02", "令牌来自 env", f02),
    ("F03", "env 来自 env", f03),
    ("F04", "非法 env 启动失败", f04),
    ("F05", "healthz 200", f05),
    ("F06", "healthz 不查库", f06),
    ("F07", "docs 200", f07),
    ("F08", "OpenAPI 路径数", f08),
    ("G01", "summary 齐全", g01),
    ("G02", "tags 齐全", g02),
    ("G03", "无裸 except", g03),
    ("G04", "SQL 参数绑定", g04),
    ("G05", "无 print", g05),
    ("G06", "响应已声明", g06),
]


def performance_smoke() -> str:
    """性能烟测：100 次 GET 的总耗时与 P95（不计入 79 条）。"""
    c = fresh(3)
    durations: list[float] = []
    for _ in range(100):
        started = time.perf_counter()
        c.get(BASE)
        durations.append((time.perf_counter() - started) * 1000)
    durations.sort()
    p95 = durations[int(len(durations) * 0.95) - 1]
    return f"100 次 / P95 {p95:.2f}ms / 总 {sum(durations):.0f}ms"


def run() -> int:
    if not (PROJECT / "main.py").exists():
        print(f"[FAIL] 找不到第 78 章产物：{PROJECT}")
        return 1

    failures = 0
    try:
        with TestClient(main.app, raise_server_exceptions=False) as client:
            CTX["client"] = client
            reset_db()
            for code, title, func in CASES:
                try:
                    print(f"[PASS] {code} {title} -> {func()}")
                except Exception as exc:  # noqa: BLE001 - 验收脚本要报告任何失败
                    failures += 1
                    print(f"[FAIL] {code} {title} -> {type(exc).__name__}: {exc}")
            if failures == 0:
                print(f"\n[性能] {performance_smoke()}")
    finally:
        shutil.rmtree(TMP_DIR, ignore_errors=True)

    print(f"\n结果：{len(CASES) - failures}/{len(CASES)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())