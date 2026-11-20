"""第 69 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

HERE = Path(__file__).parent
sys.path.insert(0, str(HERE))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402


def schema() -> dict:
    with TestClient(main.app) as c:
        return c.get("/openapi.json").json()


def check_openapi_version() -> str:
    """OpenAPI 版本字段存在。"""
    body = schema()
    assert body["openapi"].startswith("3."), body["openapi"]
    return body["openapi"]


def check_info_core() -> str:
    """`title` / `version` / `termsOfService`。"""
    info = schema()["info"]
    assert info["title"] == "订单服务", info
    assert info["version"] == "1.2.3", info
    assert info["termsOfService"] == "https://example.com/tos", info
    return f'{info["title"]} v{info["version"]}'


def check_contact_and_license() -> str:
    """`contact` 与 `license`。"""
    info = schema()["info"]
    assert info["contact"]["name"] == "API 团队", info["contact"]
    assert info["contact"]["email"] == "api@example.com", info["contact"]
    assert info["license"]["name"] == "MIT", info["license"]
    return "contact + MIT"


def check_tags_metadata() -> str:
    """`openapi_tags` 的 name 与描述都进顶层 `tags`。"""
    tags = schema()["tags"]
    names = [tag["name"] for tag in tags]
    assert names == ["items", "internal"], names
    items_tag = next(tag for tag in tags if tag["name"] == "items")
    assert "金额单位为分" in items_tag["description"], items_tag
    assert items_tag["externalDocs"]["url"] == "https://example.com/items", items_tag
    return "items / internal"


def check_servers() -> str:
    """`servers` 两条，顺序保留。"""
    servers = schema()["servers"]
    assert [server["url"] for server in servers] == [
        "https://api.example.com",
        "https://staging-api.example.com",
    ], servers
    return "生产 + 预发"


def check_custom_extensions() -> str:
    """自定义 `x-` 扩展被保留。"""
    body = schema()
    assert body["x-owner"] == "team-order", body.get("x-owner")
    assert body["x-api-tier"] == "internal", body.get("x-api-tier")
    assert body["info"]["x-audience"] == "frontend-contract", body["info"].get("x-audience")
    return "x-owner / x-api-tier / x-audience"


def check_paths() -> str:
    """三条业务路径，内部端点不在。"""
    paths = schema()["paths"]
    assert sorted(paths) == ["/items", "/items/legacy", "/items/{item_id}"], sorted(paths)
    return f"{len(paths)} 条"


def check_hidden_endpoint() -> str:
    """`include_in_schema=False`：文档没有，路径可用。"""
    with TestClient(main.app) as c:
        assert "/internal/debug" not in c.get("/openapi.json").json()["paths"]
        assert c.get("/internal/debug").status_code == 200
    return "隐藏但仍可调用"


def check_deprecated() -> str:
    """`deprecated=True` 进文档。"""
    operation = schema()["paths"]["/items/legacy"]["get"]
    assert operation["deprecated"] is True, operation
    return "deprecated=True"


def check_summary_and_description() -> str:
    """端点级 `summary` 与 docstring 描述都进文档。"""
    operation = schema()["paths"]["/items"]["get"]
    assert operation["summary"] == "商品列表", operation["summary"]
    assert "不分页" in operation["description"], operation["description"]
    return "summary + description"


def check_shared_responses() -> str:
    """`responses` 合并进 operation。"""
    paths = schema()["paths"]
    post = list(paths["/items"]["post"]["responses"])
    get = list(paths["/items/{item_id}"]["get"]["responses"])
    assert post == ["201", "409", "422"], post
    assert get == ["200", "404", "422"], get
    return "409 / 404 均在"

def check_operation_ids() -> str:
    """`operationId` 自动生成且唯一。"""
    body = schema()
    ids = [op["operationId"] for item in body["paths"].values() for op in item.values()]
    assert len(ids) == len(set(ids)), ids
    assert all(ids), ids
    return f"{len(ids)} 个唯一 operationId"


def check_models_in_schema() -> str:
    """`response_model` 进 `components.schemas`。"""
    schemas = schema()["components"]["schemas"]
    assert {"Item", "ItemCreate", "HTTPValidationError", "ValidationError"} <= set(schemas), schemas
    item = schemas["Item"]["properties"]
    assert item["price"]["description"] == "单位：分", item["price"]
    return "Item / ItemCreate / 校验错误"


def check_export_matches() -> str:
    """导出的 schema 与在线完全一致。"""
    with TestClient(main.app) as c:
        online = c.get("/openapi.json").json()
        exported = c.get("/openapi/export").json()
    assert exported == online, "导出与在线不一致"
    return "一字不差"


def check_cached() -> str:
    """`app.openapi()` 缓存同一对象。"""
    first = main.app.openapi()
    second = main.app.openapi()
    assert first is second, (id(first), id(second))
    return "同一 dict 对象"


def check_no_docs_app() -> str:
    """`docs_url=None`：`/docs` 404，schema 仍在。"""
    with TestClient(main.no_docs_app) as c:
        assert c.get("/docs").status_code == 404
        assert c.get("/redoc").status_code == 404
        assert c.get("/openapi.json").status_code == 200
    return "/docs 404 / schema 200"


def check_no_openapi_app() -> str:
    """`openapi_url=None`：schema 与 docs 全 404。"""
    with TestClient(main.no_openapi_app) as c:
        assert c.get("/openapi.json").status_code == 404
        assert c.get("/docs").status_code == 404
    return "全 404"


CHECKS = [
    ("OpenAPI 版本", check_openapi_version),
    ("info 核心", check_info_core),
    ("contact/license", check_contact_and_license),
    ("tags 元数据", check_tags_metadata),
    ("servers", check_servers),
    ("x- 扩展", check_custom_extensions),
    ("路径清单", check_paths),
    ("隐藏端点", check_hidden_endpoint),
    ("deprecated", check_deprecated),
    ("summary/description", check_summary_and_description),
    ("共享 responses", check_shared_responses),
    ("operationId", check_operation_ids),
    ("模型 schema", check_models_in_schema),
    ("导出一致", check_export_matches),
    ("缓存", check_cached),
    ("只关 docs", check_no_docs_app),
    ("全关", check_no_openapi_app),
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