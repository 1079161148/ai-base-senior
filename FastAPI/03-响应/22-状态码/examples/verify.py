"""第 22 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, status  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def new_item(name: str = "键盘") -> tuple[int, dict]:
    r = client.post("/items", json={"name": name})
    assert r.status_code == 201, (r.status_code, r.text)
    data = r.json()
    return data["id"], data


def check_decorator_status() -> str:
    """装饰器 status_code=201：创建返回 201。"""
    _, data = new_item()
    assert "id" in data, data
    return f'201 Created，id={data["id"]}'


def check_created_constant() -> str:
    """status 常量就是整数，可直接用。"""
    assert status.HTTP_201_CREATED == 201
    assert status.HTTP_204_NO_CONTENT == 204
    assert status.HTTP_202_ACCEPTED == 202
    return "201/202/204 常量值正确"


def check_openapi_201() -> str:
    """OpenAPI：POST 的 responses 里是 201 而不是 200。"""
    schema = client.get("/openapi.json").json()
    responses = schema["paths"]["/items"]["post"]["responses"]
    assert "201" in responses, responses
    assert "200" not in responses, responses
    assert responses["201"]["content"]["application/json"]["schema"]["$ref"].endswith("/ItemOut")
    return f'responses={sorted(responses)}'


def check_response_injection() -> str:
    """注入 Response 改码：函数里的设置覆盖装饰器。"""
    r = client.post("/items/async", json={"name": "异步"})
    assert r.status_code == 202, (r.status_code, r.text)
    return "装饰器 201 被函数内 202 覆盖"


def check_204_no_body() -> str:
    """204：状态码正确且 body 为空。"""
    item_id, _ = new_item("待删")
    r = client.delete(f"/items/{item_id}")
    assert r.status_code == 204, (r.status_code, r.text)
    assert r.content == b"", r.content
    return "204，body 长度 0"


def check_204_in_openapi() -> str:
    """OpenAPI：204 响应没有 content。"""
    schema = client.get("/openapi.json").json()
    resp = schema["paths"]["/items/{item_id}"]["delete"]["responses"]["204"]
    assert "content" not in resp, resp
    return "204 响应无 content 字段"


def check_204_with_body_rejected_at_import() -> str:
    """声明 204 却给返回注解 dict：导入期 AssertionError。"""
    probe = FastAPI()
    try:

        @probe.delete("/bad", status_code=204)
        def bad() -> dict[str, int]:
            return {"deleted": 1}

    except AssertionError as exc:
        return f"AssertionError: {exc}"
    raise AssertionError("204 + dict 返回注解应当被拒绝")


def check_http_exception_overrides() -> str:
    """HTTPException 覆盖装饰器状态码。"""
    r = client.get("/items/424242")
    assert r.status_code == 404, (r.status_code, r.text)
    assert r.json()["detail"] == "商品不存在", r.json()
    return "404 覆盖默认 200"


def check_custom_code() -> str:
    """自定义状态码 299 可用。"""
    r = client.get("/custom-code")
    assert r.status_code == 299, (r.status_code, r.text)
    return "299 正常返回"


def check_invalid_status_code_at_import() -> str:
    """非法状态码（99）在注册路由时就报错。"""
    probe = FastAPI()

    try:

        @probe.get("/bad", status_code=99)
        def bad() -> dict[str, str]:
            return {}

    except Exception as exc:  # noqa: BLE001
        return f"{type(exc).__name__}: {str(exc)[:60]}"
    raise AssertionError("99 应当被拒绝")


def check_201_with_location_header() -> str:
    """201 常配 Location 头，FastAPI 不会自动加。"""
    r = client.post("/items", json={"name": "带头"})
    assert r.status_code == 201
    assert "location" not in {k.lower() for k in r.headers}, "FastAPI 不会自动加 Location"
    return "默认无 Location 头（需要自己加）"


CHECKS = [
    ("装饰器改码", check_decorator_status),
    ("status 常量", check_created_constant),
    ("OpenAPI 201", check_openapi_201),
    ("Response 注入改码", check_response_injection),
    ("204 无 body", check_204_no_body),
    ("OpenAPI 204 无 content", check_204_in_openapi),
    ("204 带 body 定义期报错", check_204_with_body_rejected_at_import),
    ("HTTPException 覆盖", check_http_exception_overrides),
    ("自定义状态码", check_custom_code),
    ("非法状态码报错", check_invalid_status_code_at_import),
    ("201 无 Location", check_201_with_location_header),
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
