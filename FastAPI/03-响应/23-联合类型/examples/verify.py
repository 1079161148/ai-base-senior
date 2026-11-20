"""第 23 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)


def check_anyof_in_openapi() -> str:
    """联合响应模型在 OpenAPI 里是 anyOf。"""
    schema = client.get("/openapi.json").json()
    content = schema["paths"]["/result/{kind}"]["get"]["responses"]["200"]["content"]
    body = content["application/json"]["schema"]
    assert "anyOf" in body, body
    refs = [item["$ref"].split("/")[-1] for item in body["anyOf"]]
    assert refs == ["SuccessOut", "ErrorOut"], refs
    return f"anyOf={refs}"


def check_success_branch() -> str:
    """成功分支：返回 SuccessOut 结构。"""
    data = client.get("/result/success").json()
    assert data == {"ok": True, "data": {"id": 1, "name": "机械键盘"}}, data
    return f'ok={data["ok"]}，data.id={data["data"]["id"]}'


def check_error_branch() -> str:
    """失败分支：返回 ErrorOut 结构。"""
    data = client.get("/result/failure").json()
    assert data == {"ok": False, "message": "查无此项"}, data
    return f'message={data["message"]!r}'


def check_responses_per_status() -> str:
    """不同状态码挂不同模型：200 与 404 各是各的组件。"""
    schema = client.get("/openapi.json").json()
    responses = schema["paths"]["/item-or-error/{item_id}"]["get"]["responses"]
    ok_ref = responses["200"]["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
    err_ref = responses["404"]["content"]["application/json"]["schema"]["$ref"].split("/")[-1]
    assert ok_ref == "ItemOut", ok_ref
    assert err_ref == "ErrorOut", err_ref
    assert responses["404"]["description"] == "商品不存在", responses["404"]
    return f"200→{ok_ref}，404→{err_ref}"


def check_404_returns_jsonresponse() -> str:
    """失败分支直接返回 JSONResponse：状态码与 body 都按你写的来。"""
    r = client.get("/item-or-error/999")
    assert r.status_code == 404, (r.status_code, r.text)
    assert r.json() == {"ok": False, "message": "商品不存在"}, r.json()
    return "404 + ErrorOut 结构"


def check_jsonresponse_bypasses_model() -> str:
    """直接返回 JSONResponse：不校验、不过滤。"""
    data = client.get("/raw").json()
    assert data["secret"] == "不该出现", data
    assert data["count"] == "不是数字", data
    return "多余字段与非法类型原样输出"


def check_union_order_a_first() -> str:
    """A | B：返回符合 A 的 dict 时匹配 A。"""
    data = client.get("/order-ab").json()
    assert data == {"ok": True, "name": "x"}, data
    return f'匹配 A：{data}'


def check_union_order_b_first() -> str:
    """B | A：返回符合 B 的 dict 时匹配 B。"""
    data = client.get("/order-ba").json()
    assert data == {"ok": True, "message": "y"}, data
    return f'匹配 B：{data}'


def check_union_no_match_is_500() -> str:
    """联合里一个都不匹配 → 500（响应模型校验失败）。"""
    from fastapi import FastAPI

    probe = FastAPI()

    @probe.get("/bad", response_model=main.A | main.B)
    def bad():  # noqa: ANN202
        return {"ok": True}

    c = TestClient(probe, raise_server_exceptions=False)
    r = c.get("/bad")
    assert r.status_code == 500, (r.status_code, r.text)
    return "两者都不匹配 → 500"


def check_response_model_none() -> str:
    """`response_model=None`：完全不过滤。"""
    from fastapi import FastAPI

    probe = FastAPI()

    @probe.get("/free", response_model=None)
    def free():  # noqa: ANN202
        return {"a": 1, "secret": "x"}

    data = TestClient(probe).get("/free").json()
    assert data == {"a": 1, "secret": "x"}, data
    return "不过滤，原样输出"


CHECKS = [
    ("OpenAPI anyOf", check_anyof_in_openapi),
    ("成功分支", check_success_branch),
    ("失败分支", check_error_branch),
    ("按状态码挂模型", check_responses_per_status),
    ("404 返回 JSONResponse", check_404_returns_jsonresponse),
    ("JSONResponse 绕过模型", check_jsonresponse_bypasses_model),
    ("A|B 匹配 A", check_union_order_a_first),
    ("B|A 匹配 B", check_union_order_b_first),
    ("联合全不匹配 500", check_union_no_match_is_500),
    ("response_model=None", check_response_model_none),
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
