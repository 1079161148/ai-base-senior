"""第 31 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from starlette.exceptions import HTTPException as StarletteHTTPException  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)
# 【作用】不把服务端异常直接抛给断言，方便观察 500
strict = TestClient(main.app, raise_server_exceptions=False)


def check_404_string_detail() -> str:
    """404 + 字符串 detail。"""
    r = client.get("/items/99")
    assert r.status_code == 404, (r.status_code, r.text)
    assert r.json() == {"detail": "item 99 不存在"}, r.json()
    return f'404 detail={r.json()["detail"]}'


def check_200_ok() -> str:
    """存在的资源正常返回。"""
    r = client.get("/items/1")
    assert r.status_code == 200, r.text
    assert r.json()["name"] == "机械键盘", r.json()
    return "200 机械键盘"


def check_structured_detail() -> str:
    """detail 可以是 dict。"""
    r = client.get("/items/99/structured")
    assert r.status_code == 404, r.text
    detail = r.json()["detail"]
    assert detail["reason"] == "not_found", detail
    assert detail["item_id"] == 99, detail
    return f"结构化 detail keys={sorted(detail)}"


def check_401_with_www_authenticate() -> str:
    """401 必须带 WWW-Authenticate。"""
    r = client.get("/me")
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.headers["www-authenticate"] == "Bearer", dict(r.headers)
    return f'www-authenticate={r.headers["www-authenticate"]}'


def check_401_invalid_token() -> str:
    """无效凭据：401 + 更具体的 challenge。"""
    r = client.get("/me", headers={"Authorization": "bad-token"})
    assert r.status_code == 401, r.text
    assert 'error="invalid_token"' in r.headers["www-authenticate"], dict(r.headers)
    return r.headers["www-authenticate"]


def check_200_with_token() -> str:
    """有效凭据返回用户。"""
    r = client.get("/me", headers={"Authorization": "valid-token"})
    assert r.status_code == 200, r.text
    assert r.json() == {"user": "alice"}, r.json()
    return "user=alice"


def check_409_conflict() -> str:
    """409：名称冲突。"""
    r = client.post("/items", params={"name": "机械键盘"})
    assert r.status_code == 409, (r.status_code, r.text)
    assert "已存在" in r.json()["detail"], r.json()
    return r.json()["detail"]


def check_429_with_retry_after() -> str:
    """429 带 Retry-After。"""
    user = "bob"
    codes = [client.post("/login", params={"username": user}).status_code for _ in range(3)]
    assert codes == [200, 200, 429], codes
    r = client.post("/login", params={"username": user})
    assert r.status_code == 429, r.text
    assert r.headers["retry-after"] == "30", dict(r.headers)
    return "第 3 次起 429 + retry-after=30"


def check_dependency_raises() -> str:
    """依赖里抛 401：路由不执行。"""
    r = client.get("/secure/items")
    assert r.status_code == 401, (r.status_code, r.text)
    assert r.json() == {"detail": "X-Token 无效"}, r.json()
    ok = client.get("/secure/items", headers={"X-Token": "valid-token"})
    assert ok.status_code == 200, ok.text
    return "缺 token → 401；有 token → 200"


def check_uncaught_exception_500() -> str:
    """未捕获异常 → 500，body 不泄露细节。"""
    r = strict.get("/boom")
    assert r.status_code == 500, (r.status_code, r.text)
    assert "ValueError" not in r.text, r.text
    assert "内部错误" not in r.text, r.text
    return f"500 body={r.text[:40]!r}"


def check_background_http_exception() -> str:
    """后台任务里抛 HTTPException：不会变成 404。"""
    try:
        r = strict.post("/background")
    except Exception as exc:  # noqa: BLE001
        return f"异常冒出：{type(exc).__name__}"
    return f"状态码 {r.status_code}（响应已发出，404 不生效）"


def check_unknown_route_404() -> str:
    """不存在的路由：框架默认 404。"""
    r = client.get("/no-such-route")
    assert r.status_code == 404, r.text
    assert r.json() == {"detail": "Not Found"}, r.json()
    return f'默认 detail={r.json()["detail"]}'


def check_405_method_not_allowed() -> str:
    """方法不允许：405 + Allow 头。"""
    r = client.delete("/items/1")
    assert r.status_code == 405, (r.status_code, r.text)
    assert "GET" in r.headers.get("allow", ""), dict(r.headers)
    return f'405 allow={r.headers.get("allow")}'


def check_openapi_does_not_list_404() -> str:
    """OpenAPI 不会自动记录 404。"""
    responses = client.get("/openapi.json").json()["paths"]["/items/{item_id}"]["get"]["responses"]
    assert set(responses) == {"200", "422"}, sorted(responses)
    return f"responses={sorted(responses)}"


def check_header_with_chinese_500() -> str:
    """响应头写中文：编码失败 → 500。"""
    probe = FastAPI()

    @probe.get("/cn")
    def cn() -> dict[str, str]:  # noqa: ANN202
        raise HTTPException(status_code=400, detail="x", headers={"X-Note": "中文"})

    r = TestClient(probe, raise_server_exceptions=False).get("/cn")
    assert r.status_code == 500, (r.status_code, r.text)
    return "头值含中文 → 500（latin-1 编码失败）"


def check_is_starlette_subclass() -> str:
    """FastAPI 的 HTTPException 是 Starlette 的子类。"""
    exc = HTTPException(status_code=404)
    assert isinstance(exc, StarletteHTTPException), type(exc)
    assert exc.detail == "Not Found", exc.detail
    return "isinstance(starlette.HTTPException) = True"


CHECKS = [
    ("404 字符串 detail", check_404_string_detail),
    ("200 正常", check_200_ok),
    ("结构化 detail", check_structured_detail),
    ("401 + WWW-Authenticate", check_401_with_www_authenticate),
    ("401 无效凭据", check_401_invalid_token),
    ("200 有效凭据", check_200_with_token),
    ("409 冲突", check_409_conflict),
    ("429 + Retry-After", check_429_with_retry_after),
    ("依赖里抛 401", check_dependency_raises),
    ("未捕获异常 500", check_uncaught_exception_500),
    ("后台任务异常", check_background_http_exception),
    ("不存在的路由", check_unknown_route_404),
    ("405 方法不允许", check_405_method_not_allowed),
    ("OpenAPI 不含 404", check_openapi_does_not_list_404),
    ("头值中文 500", check_header_with_chinese_500),
    ("Starlette 子类", check_is_starlette_subclass),
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