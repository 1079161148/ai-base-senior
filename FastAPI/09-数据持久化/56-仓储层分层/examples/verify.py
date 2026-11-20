"""第 56 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402
from models import Item  # noqa: E402
from router import get_repository  # noqa: E402


def with_client():
    return TestClient(main.app)


def check_empty_list() -> str:
    """初始为空。"""
    with with_client() as c:
        assert c.get("/items").json() == []
    return "[]"


def check_create_201() -> str:
    """创建返回 201 + 实体。"""
    with with_client() as c:
        r = c.post("/items", json={"name": "键盘", "price": 299})
        assert r.status_code == 201, (r.status_code, r.text)
        assert r.json() == {"id": 1, "name": "键盘", "price": 299}, r.json()
    return "id=1"


def check_duplicate_409() -> str:
    """重名由 **service** 拒绝，翻译成 409。"""
    with with_client() as c:
        c.post("/items", json={"name": "k", "price": 1})
        r = c.post("/items", json={"name": "k", "price": 2})
        assert r.status_code == 409, (r.status_code, r.text)
        assert r.json()["detail"] == "名称已存在：k", r.json()
    return "409"


def check_get_detail() -> str:
    """详情能查到刚写的数据（说明跨请求可见）。"""
    with with_client() as c:
        c.post("/items", json={"name": "a", "price": 7})
        r = c.get("/items/1")
        assert r.status_code == 200 and r.json()["name"] == "a", (r.status_code, r.text)
    return r.json()


def check_not_found_404() -> str:
    """`ItemNotFoundError` 由 router 翻译成 404。"""
    with with_client() as c:
        r = c.get("/items/999")
        assert r.status_code == 404, (r.status_code, r.text)
        assert r.json()["detail"] == "条目不存在", r.json()
    return "404"


def check_delete_204_then_404() -> str:
    """删除成功 204，再删同一条 404。"""
    with with_client() as c:
        c.post("/items", json={"name": "d", "price": 1})
        assert c.delete("/items/1").status_code == 204
        assert c.delete("/items/1").status_code == 404
    return "204 → 404"


def check_route_order_trap() -> str:
    """`/items/count` 会被 `/{item_id}` 先匹配 → 422，不是 404。"""
    with with_client() as c:
        r = c.get("/items/count")
        assert r.status_code == 422, (r.status_code, r.text)
        assert r.json()["detail"][0]["type"] == "int_parsing", r.json()
    return "422 int_parsing（被 /{item_id} 吃掉）"


def check_count_endpoint() -> str:
    """避开冲突的写法：`/_/count`。"""
    with with_client() as c:
        for i in range(3):
            c.post("/items", json={"name": f"n{i}", "price": i})
        assert c.get("/items/_/count").json() == {"count": 3}
    return "count=3"


def check_repository_replaceable() -> str:
    """`dependency_overrides` 换仓储 → 路由与 service 代码一行不改。"""

    class FakeRepository:
        def list_all(self) -> list[Item]:
            return [Item(id=42, name="假数据", price=0)]

    with with_client() as c:
        main.app.dependency_overrides[get_repository] = FakeRepository
        try:
            body = c.get("/items").json()
            assert body == [{"id": 42, "name": "假数据", "price": 0}], body
        finally:
            main.app.dependency_overrides.clear()
    return "返回假数据，未碰数据库"


def check_repository_has_no_http() -> str:
    """仓储层不含 HTTP 概念。"""
    source = (HERE / "repository.py").read_text(encoding="utf-8")
    for token in ("HTTPException", "status_code", "APIRouter", "Depends"):
        assert token not in source, token
    return "无 HTTPException/status_code/APIRouter/Depends"


def check_service_has_no_sql_and_no_http() -> str:
    """服务层不含 SQL、不含 HTTP。"""
    source = (HERE / "service.py").read_text(encoding="utf-8")
    for token in ("SELECT", "INSERT", "DELETE FROM", "HTTPException", "status_code"):
        assert token not in source, token
    assert "DuplicateItemError" in source
    return "无 SQL、无 HTTP，只有领域异常"


def check_router_has_no_sql() -> str:
    """路由层不含 SQL。"""
    source = (HERE / "router.py").read_text(encoding="utf-8")
    for token in ("SELECT", "INSERT", "DELETE FROM", "UPDATE "):
        assert token not in source, token
    return "无任何 SQL 关键字"


def check_openapi_paths() -> str:
    """分层不影响文档生成。"""
    with with_client() as c:
        paths = sorted(c.get("/openapi.json").json()["paths"])
    assert paths == ["/items", "/items/_/count", "/items/{item_id}"], paths
    return ",".join(paths)


def check_response_model_used() -> str:
    """响应模型在路由层，不在仓储层拼 dict。"""
    with with_client() as c:
        c.post("/items", json={"name": "m", "price": 5})
        schema = c.get("/openapi.json").json()["components"]["schemas"]
    assert "Item" in schema, sorted(schema)
    return "Item 进入 components.schemas"


CHECKS = [
    ("空列表", check_empty_list),
    ("创建 201", check_create_201),
    ("重名 409", check_duplicate_409),
    ("详情", check_get_detail),
    ("不存在 404", check_not_found_404),
    ("删除 204→404", check_delete_204_then_404),
    ("路由顺序陷阱", check_route_order_trap),
    ("计数端点", check_count_endpoint),
    ("仓储可替换", check_repository_replaceable),
    ("仓储无 HTTP", check_repository_has_no_http),
    ("服务层纯净", check_service_has_no_sql_and_no_http),
    ("路由层无 SQL", check_router_has_no_sql),
    ("OpenAPI 路径", check_openapi_paths),
    ("响应模型", check_response_model_used),
]


def run() -> int:
    failures = 0
    for name, func in CHECKS:
        try:
            print(f"[PASS] {name} -> {func()}")
        except AssertionError as exc:
            failures += 1
            print(f"[FAIL] {name} -> {exc}")
    main.DB_FILE.unlink(missing_ok=True)
    print(f"\n结果：{len(CHECKS) - failures}/{len(CHECKS)} 通过")
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(run())