"""第 42 章 · 自动验收。运行：python verify.py"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def check_defaults() -> str:
    """默认 page=1 size=5。"""
    r = client.get("/items")
    assert r.status_code == 200, (r.status_code, r.text)
    body = r.json()
    assert body["page"] == 1 and body["size"] == 5, body
    assert [i["id"] for i in body["items"]] == [1, 2, 3, 4, 5], body["items"]
    return f'total={body["total"]}, pages={body["pages"]}'


def check_second_page() -> str:
    """第二页切片正确。"""
    r = client.get("/items", params={"page": 2, "size": 5})
    body = r.json()
    assert [i["id"] for i in body["items"]] == [6, 7, 8, 9, 10], body["items"]
    return f'page=2 → ids={[i["id"] for i in body["items"]]}'


def check_total_and_pages() -> str:
    """total/pages 基于全量。"""
    body = client.get("/items", params={"size": 10}).json()
    assert body["total"] == 23, body["total"]
    assert body["pages"] == math.ceil(23 / 10) == 3, body["pages"]
    return f'total=23, pages={body["pages"]}'


def check_last_page_partial() -> str:
    """最后一页不满 size。"""
    body = client.get("/items", params={"page": 3, "size": 10}).json()
    assert len(body["items"]) == 3, body["items"]
    assert [i["id"] for i in body["items"]] == [21, 22, 23], body["items"]
    return "最后一页 3 条"


def check_out_of_range_returns_empty() -> str:
    """越界页：200 + 空 items，total 不变。"""
    body = client.get("/items", params={"page": 99}).json()
    assert body["items"] == [], body["items"]
    assert body["total"] == 23, body["total"]
    assert body["page"] == 99, body["page"]
    return "越界 → items=[] 且 total 不变"


def check_empty_dataset() -> str:
    """空结果集：pages=0。"""
    body = client.get("/items/empty").json()
    assert body["items"] == [] and body["total"] == 0, body
    assert body["pages"] == 0, body["pages"]
    return "total=0 → pages=0"


def check_size_upper_bound() -> str:
    """size 上限 50：超限 422。"""
    r = client.get("/items", params={"size": 51})
    assert r.status_code == 422, (r.status_code, r.text)
    err = r.json()["detail"][0]
    assert err["loc"] == ["query", "size"], err
    return "size=51 → 422"


def check_page_lower_bound() -> str:
    """page 下限 1：page=0 → 422。"""
    r = client.get("/items", params={"page": 0})
    assert r.status_code == 422, (r.status_code, r.text)
    assert r.json()["detail"][0]["loc"] == ["query", "page"], r.json()
    return "page=0 → 422"


def check_response_model_enforced() -> str:
    """响应模型过滤多余字段并保证结构。"""
    body = client.get("/items", params={"size": 1}).json()
    assert set(body) == {"items", "total", "page", "size", "pages"}, sorted(body)
    assert set(body["items"][0]) == {"id", "name", "price"}, sorted(body["items"][0])
    return f"字段={sorted(body)}"


def check_generic_schemas() -> str:
    """OpenAPI 里出现两个具体泛型 schema。"""
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    names = sorted(schemas)
    assert any(n.startswith("Page_ItemOut") for n in names), names
    assert any(n.startswith("Page_UserOut") for n in names), names
    return f"schemas={[n for n in names if n.startswith('Page_')]}"


def check_generic_schema_shape() -> str:
    """泛型 schema 的 items 指向具体模型。"""
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    name = next(n for n in schemas if n.startswith("Page_ItemOut"))
    props = schemas[name]["properties"]
    assert set(props) == {"items", "total", "page", "size", "pages"}, sorted(props)
    item_ref = props["items"]["items"]["$ref"].split("/")[-1]
    assert item_ref == "ItemOut", item_ref
    return f"{name}.items → {item_ref}"


def check_same_dependency_two_models() -> str:
    """同一分页依赖服务两个模型，参数一致。"""
    a = client.get("/openapi.json").json()["paths"]["/items"]["get"]["parameters"]
    b = client.get("/openapi.json").json()["paths"]["/users"]["get"]["parameters"]
    assert a == b, (a, b)
    body = client.get("/users", params={"page": 2, "size": 3}).json()
    assert [u["id"] for u in body["items"]] == [4, 5, 6], body
    return "两端点参数一致，用户分页正确"


CHECKS = [
    ("默认参数", check_defaults),
    ("第二页", check_second_page),
    ("total/pages", check_total_and_pages),
    ("最后一页", check_last_page_partial),
    ("越界空页", check_out_of_range_returns_empty),
    ("空数据集", check_empty_dataset),
    ("size 上限", check_size_upper_bound),
    ("page 下限", check_page_lower_bound),
    ("响应模型", check_response_model_enforced),
    ("泛型 schema", check_generic_schemas),
    ("泛型结构", check_generic_schema_shape),
    ("两模型复用", check_same_dependency_two_models),
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