"""第 05 章 · 自动验收。运行：python verify.py"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def check_int() -> str:
    r = client.get("/users/42")
    assert r.status_code == 200, r.text
    assert r.json() == {"user_id": 42, "type": "int"}, r.json()
    return str(r.json())


def check_negative_int() -> str:
    """负号也是合法 int，转换不应失败。"""
    r = client.get("/users/-7")
    assert r.json()["user_id"] == -7, r.json()
    return str(r.json()["user_id"])


def check_float() -> str:
    r = client.get("/ratings/3.14")
    assert r.json()["score"] == 3.14, r.json()
    return str(r.json()["score"])


def check_bool_variants() -> str:
    """bool 接受 true/1/yes，拒绝 maybe。"""
    assert client.get("/flags/true").json()["flag"] is True
    assert client.get("/flags/1").json()["flag"] is True
    assert client.get("/flags/yes").json()["flag"] is True
    assert client.get("/flags/0").json()["flag"] is False
    assert client.get("/flags/maybe").status_code == 422
    return "true/1/yes→True, 0→False, maybe→422"


def check_422_detail() -> str:
    """非法 int 返回 422，且 detail 里能定位到 path 参数。"""
    r = client.get("/users/abc")
    assert r.status_code == 422, r.status_code
    item = r.json()["detail"][0]
    assert item["type"] == "int_parsing", item
    assert item["loc"] == ["path", "user_id"], item
    return f"422 {item['type']} loc={item['loc']}"


def check_converter_404() -> str:
    """{code:int} 在正则层不匹配 → 404，不进函数。"""
    assert client.get("/products/5").status_code == 200
    r = client.get("/products/abc")
    assert r.status_code == 404, r.status_code
    assert r.json() == {"detail": "Not Found"}, r.json()
    # 对比：标注 int 的接口是 422
    assert client.get("/users/abc").status_code == 422
    return "/products/abc→404 而 /users/abc→422"


def check_uuid() -> str:
    """UUID 转换器。"""
    ok = "123e4567-e89b-12d3-a456-426614174000"
    assert client.get(f"/orders/{ok}").status_code == 200
    assert client.get("/orders/not-a-uuid").status_code == 404
    return f"{ok} → 200；not-a-uuid → 404"


def check_multi_path() -> str:
    """双路径参数 + 查询参数。"""
    r = client.get("/trips/北京/to/上海")
    assert r.json() == {"from": "北京", "to": "上海", "day": None}, r.json()
    r = client.get("/trips/北京/to/上海", params={"day": "2026-01-01"})
    assert r.json()["day"] == "2026-01-01", r.json()
    return str(r.json())


def check_default_is_ignored() -> str:
    """路径参数写默认值不报错，但默认值被静默忽略、参数仍然必填。"""
    from fastapi import FastAPI

    fresh = FastAPI()

    @fresh.get("/bad/{user_id}")
    def bad(user_id: int = 1) -> dict[str, int]:
        return {"user_id": user_id}

    c = TestClient(fresh)
    # 传了值就用传入的，默认值 1 不生效
    assert c.get("/bad/5").json() == {"user_id": 5}
    # 不传（不可能）→ 路径不匹配 404，而不是用默认值
    assert c.get("/bad").status_code == 404
    # 传了非法值仍然 422，说明它没被降级成查询参数
    assert c.get("/bad/abc").status_code == 422
    param = c.get("/openapi.json").json()["paths"]["/bad/{user_id}"]["get"]["parameters"][0]
    assert param["required"] is True, param
    assert "default" not in param["schema"], param
    return "默认值被忽略；仍 required=true 且无 default"


def check_openapi_path_params() -> str:
    """路径参数在 OpenAPI 里必须是 required=true、in=path。"""
    schema = client.get("/openapi.json").json()
    param = schema["paths"]["/users/{user_id}"]["get"]["parameters"][0]
    assert param["in"] == "path" and param["required"] is True, param
    assert param["schema"]["type"] == "integer", param
    return f"in={param['in']} required={param['required']} type={param['schema']['type']}"


CHECKS = [
    ("int 转换", check_int),
    ("负数也是 int", check_negative_int),
    ("float 转换", check_float),
    ("bool 的四种写法", check_bool_variants),
    ("非法值 422 结构", check_422_detail),
    ("转换器 404 vs 标注 422", check_converter_404),
    ("UUID 转换器", check_uuid),
    ("多路径参数 + 查询参数", check_multi_path),
    ("路径参数默认值被忽略", check_default_is_ignored),
    ("OpenAPI 参数声明", check_openapi_path_params),
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
