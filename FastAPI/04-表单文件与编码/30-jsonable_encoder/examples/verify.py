"""第 30 章 · 自动验收。运行：python verify.py"""

import sys
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from enum import Enum
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.encoders import jsonable_encoder  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def check_basic_types() -> str:
    """基础类型：datetime/Decimal/set/UUID/Enum/Path/bytes。

    【实测】裸 dict 里的 `Decimal` 被转成 **float**（399.9），
           而 Pydantic 模型里的 `Decimal` 被转成 **str**（"99.50"）——两者不一致
    """
    data = client.get("/encode/basic").json()["encoded"]
    assert data["dt"].startswith("2026-11-17T12:00:00"), data["dt"]
    assert data["day"] == "2026-11-17", data["day"]
    assert data["amount"] == 399.9 and isinstance(data["amount"], float), data["amount"]
    assert sorted(data["tags"]) == ["a", "b"], data["tags"]
    assert data["id"] == "12345678-1234-5678-1234-567812345678", data["id"]
    assert data["status"] == "active", data["status"]
    assert data["path"] == str(Path("var/uploads/a.txt")), data["path"]
    assert data["raw"] == "hello", data["raw"]
    return "裸 dict 的 Decimal → float 399.9；其余为 str/list"


def check_types_are_json_native() -> str:
    """转换结果里没有非 JSON 原生类型。"""
    types = client.get("/encode/basic").json()["types"]
    allowed = {"str", "int", "float", "bool", "NoneType", "list", "dict"}
    bad = {key: value for key, value in types.items() if value not in allowed}
    assert not bad, bad
    return f"types={sorted(set(types.values()))}"


def check_model_to_dict() -> str:
    """模型实例转 dict，Decimal 变字符串。"""
    data = client.get("/encode/model").json()
    assert data == {
        "id": 1,
        "amount": "99.50",
        "created_at": "2026-11-17T12:00:00Z",
        "status": "disabled",
    }, data
    return "Decimal='99.50'，status='disabled'"


def check_plain_object() -> str:
    """普通对象（SimpleNamespace）转 dict。

    【实测】同样因为不走 Pydantic，`Decimal` 变 float（399.0）
    """
    data = client.get("/encode/object").json()
    assert data == {"id": 7, "name": "机械键盘", "price": 399.0}, data
    return "SimpleNamespace → dict，Decimal 变 float"


def check_exclude_include() -> str:
    """exclude / include 裁剪字段。"""
    data = client.get("/encode/filter").json()
    assert "password" not in data["excluded"], data["excluded"]
    assert data["included"] == {"id": 1, "username": "alice"}, data["included"]
    assert data["excluded"]["email"] == "a@example.com", data["excluded"]
    return "exclude 去掉 password；include 只剩 id/username"


def check_custom_encoder() -> str:
    """custom_encoder 覆盖 datetime 默认行为。"""
    data = client.get("/encode/custom").json()
    assert isinstance(data["encoded"]["created_at"], int), data
    assert data["types"]["created_at"] == "int", data["types"]
    assert data["encoded"]["amount"] == 1.5, data
    return "datetime → int 时间戳，Decimal 仍走默认 float"


def check_compare_with_model_dump() -> str:
    """jsonable_encoder 与 model_dump(mode='json') 结果一致。"""
    data = client.get("/encode/compare").json()
    assert data["same"] is True, data
    assert data["via_encoder"]["amount"] == "12.30", data
    assert data["via_encoder"]["status"] == "active", data
    return "两条路结果相同（Decimal 均为字符串）"


def check_enum_path_param() -> str:
    """路径参数枚举：入参转换、出参编码都由框架做。"""
    ok = client.get("/orders/active")
    assert ok.status_code == 200, ok.text
    assert ok.json() == {"status": "active", "enum_name": "ACTIVE"}, ok.json()

    bad = client.get("/orders/nope")
    assert bad.status_code == 422, (bad.status_code, bad.text)
    return "active → ACTIVE；非法值 422"


def check_encoder_is_recursive() -> str:
    """嵌套结构递归转换。"""
    payload = {"outer": [{"dt": datetime(2026, 1, 2, tzinfo=timezone.utc)}], "n": Decimal("0.1")}
    encoded = jsonable_encoder(payload)
    assert encoded["outer"][0]["dt"].startswith("2026-01-02"), encoded
    assert encoded["n"] == 0.1, encoded
    return "嵌套 dict/list 内也被转换"


def check_bytes_decode() -> str:
    """bytes 默认按 utf-8 解码；非法字节会怎样。"""
    assert jsonable_encoder(b"hello") == "hello"
    try:
        jsonable_encoder(b"\xff\xfe")
    except (UnicodeDecodeError, ValueError) as exc:
        return f"非法字节抛 {type(exc).__name__}"
    return "非法字节未抛错（实现相关）"


def check_non_serializable_object() -> str:
    """没有 __dict__ 的对象：行为（自定义 __slots__/不可哈希）。"""
    class Slotted:
        __slots__ = ("a",)

        def __init__(self) -> None:
            self.a = 1

    try:
        encoded = jsonable_encoder(Slotted())
    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}: {str(exc)[:50]}"
    return f"未抛错，结果={encoded!r}"


def check_plain_class() -> str:
    """无属性的普通类实例 → 空 dict（走 __dict__）。"""
    class Plain:
        pass

    encoded = jsonable_encoder(Plain())
    assert encoded == {}, encoded
    return "Plain() → {}"


CHECKS = [
    ("基础类型转换", check_basic_types),
    ("结果均为 JSON 原生", check_types_are_json_native),
    ("模型转 dict", check_model_to_dict),
    ("普通对象转 dict", check_plain_object),
    ("exclude/include", check_exclude_include),
    ("custom_encoder", check_custom_encoder),
    ("与 model_dump 对比", check_compare_with_model_dump),
    ("路径枚举", check_enum_path_param),
    ("递归转换", check_encoder_is_recursive),
    ("bytes 解码", check_bytes_decode),
    ("__slots__ 对象", check_non_serializable_object),
    ("空普通类", check_plain_class),
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