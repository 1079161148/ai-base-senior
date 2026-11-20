"""第 19 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path
from typing import Annotated  # noqa: E402

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402
from pydantic import BaseModel, Field, ValidationError  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)

VALID = {"name": "机械键盘", "price": "399.00", "tags": ["数码"]}


def first_error(r) -> dict:
    assert r.status_code == 422, (r.status_code, r.text)
    return r.json()["detail"][0]


def create(payload: dict | None = None) -> dict:
    r = client.post("/products", json=VALID if payload is None else payload)
    assert r.status_code == 200, r.text
    return r.json()


def check_inherit_fields() -> str:
    """子类继承字段：Read 比 Create 多 id/created_at。"""
    assert set(main.ProductCreate.model_fields) == {"name", "price", "tags"}
    assert set(main.ProductRead.model_fields) == {"name", "price", "tags", "id", "created_at"}
    assert set(main.ProductPatch.model_fields) == {"name", "price", "tags"}
    return "Create=3；Read=5；Patch=3"


def check_inherit_config() -> str:
    """子类继承 model_config：extra=forbid 与 strip 都生效。"""
    assert main.ProductCreate.model_config["extra"] == "forbid"
    assert main.ProductRead.model_config["extra"] == "forbid"
    err = first_error(client.post("/products", json={**VALID, "hack": 1}))
    assert err["type"] == "extra_forbidden", err
    return "extra_forbidden 来自继承的配置"


def check_inherit_alias_constraints() -> str:
    """类型别名的约束在三个模型里都生效。"""
    err = first_error(client.post("/products", json={**VALID, "price": "0"}))
    assert err["type"] == "greater_than", err
    err = first_error(client.post("/products", json={**VALID, "price": "1.234"}))
    assert err["type"] == "decimal_max_places", err
    err = first_error(client.patch("/products/1", json={"tags": ["a", "b", "c", "d", "e", "f"]}))
    assert err["type"] == "too_long", err
    return "Money/Tags 别名约束在 Create 与 Patch 同时生效"


def check_strip_from_base() -> str:
    """`str_strip_whitespace` 也是继承来的。"""
    data = create({"name": "  无线鼠标  ", "price": "99", "tags": []})
    assert data["name"] == "无线鼠标", data
    return f'name={data["name"]!r}'


def check_create_returns_read_shape() -> str:
    """创建接口返回 Read 形态：有 id 与 created_at，price 是字符串。"""
    data = create()
    assert set(data) == {"name", "price", "tags", "id", "created_at"}, data
    assert isinstance(data["id"], int), data
    assert data["price"] == "399.00", data
    return f'id={data["id"]} price={data["price"]!r}'


def check_patch_uses_base_config() -> str:
    """Patch 复用 StrictModel：可选、禁多余字段、仍校验。"""
    created = create()
    pid = created["id"]

    r = client.patch(f"/products/{pid}", json={"name": "静音键盘"})
    assert r.status_code == 200, r.text
    assert r.json()["updates"] == ["name"], r.json()
    assert r.json()["product"]["price"] == "399.00", r.json()

    err = first_error(client.patch(f"/products/{pid}", json={"nmae": "x"}))
    assert err["type"] == "extra_forbidden", err
    return 'updates=["name"]，price 未变'


def check_subclass_is_subclass() -> str:
    """继承关系可断言：Create/Read 都是 Base 的子类，Patch 不是。"""
    assert issubclass(main.ProductCreate, main.ProductBase)
    assert issubclass(main.ProductRead, main.ProductBase)
    assert not issubclass(main.ProductPatch, main.ProductBase)
    assert issubclass(main.ProductBase, BaseModel)
    return "Create/Read ⊂ ProductBase；Patch 独立"


def check_field_override() -> str:
    """子类重定义字段：覆盖父类约束，且不污染父类。"""

    class TighterCreate(main.ProductCreate):
        # 【作用】子类把长度下限从 1 收紧到 5
        name: Annotated[str, Field(min_length=5, max_length=8)]

    try:
        TighterCreate(name="abc", price="1")
    except ValidationError as exc:
        assert exc.errors()[0]["type"] == "string_too_short", exc.errors()[0]
    else:
        raise AssertionError("应当校验失败")

    assert main.ProductCreate.model_fields["name"].metadata != TighterCreate.model_fields["name"].metadata
    return "子类覆盖生效，父类不变"


def check_mro_override() -> str:
    """多继承同名字段：MRO 里靠前的父类生效。"""

    class WithNote(BaseModel):
        note: str = "from-first"

    class WithOtherNote(BaseModel):
        note: str = "from-second"

    class Merged(WithNote, WithOtherNote):
        pass

    assert Merged().note == "from-first"
    return "MRO 第一个父类优先"


def check_openapi_components() -> str:
    """OpenAPI：两个模型各自独立成组件，字段集合不同。"""
    schemas = client.get("/openapi.json").json()["components"]["schemas"]
    assert set(schemas["ProductCreate"]["properties"]) == {"name", "price", "tags"}, schemas["ProductCreate"]
    assert set(schemas["ProductRead"]["properties"]) == {
        "name",
        "price",
        "tags",
        "id",
        "created_at",
    }, schemas["ProductRead"]
    assert schemas["ProductRead"]["required"] == ["name", "price", "id", "created_at"], schemas["ProductRead"]
    return "两个组件字段集合与 required 都不同"


CHECKS = [
    ("子类继承字段", check_inherit_fields),
    ("子类继承配置", check_inherit_config),
    ("别名约束复用", check_inherit_alias_constraints),
    ("strip 来自基类", check_strip_from_base),
    ("创建返回 Read 形态", check_create_returns_read_shape),
    ("Patch 复用基类配置", check_patch_uses_base_config),
    ("继承关系", check_subclass_is_subclass),
    ("子类覆盖字段", check_field_override),
    ("多继承覆盖顺序", check_mro_override),
    ("OpenAPI 组件", check_openapi_components),
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
