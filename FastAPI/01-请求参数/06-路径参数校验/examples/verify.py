"""第 06 章 · 自动验收。运行：python verify.py"""

import sys
from pathlib import Path
from typing import Annotated

sys.path.insert(0, str(Path(__file__).parent))

from fastapi import Path  # noqa: E402
from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import main  # noqa: E402

client = TestClient(main.app)

# 【注意】用于对比「两种写法」的两个 app 必须定义在**模块级**：
#   - verify.py 里如果在函数内定义带 Annotated 的路由，且文件顶部有
#     `from __future__ import annotations`，注解会变成 ForwardRef 字符串，
#     FastAPI 解析时会抛 PydanticUserError: not fully defined
#   - 所以本文件不使用 `from __future__ import annotations`
_new_style_app = FastAPI()


@_new_style_app.get("/{v}")
def _new_style(v: Annotated[int, Path(gt=0, le=10)]) -> dict[str, int]:
    return {"v": v}


_old_style_app = FastAPI()


@_old_style_app.get("/{v}")
def _old_style(v: int = Path(gt=0, le=10)) -> dict[str, int]:
    return {"v": v}


def check_numeric_range() -> str:
    """gt=0, le=100：1 和 100 通过，0 和 101 拒绝。"""
    assert client.get("/items/1").json() == {"item_id": 1}
    assert client.get("/items/100").json() == {"item_id": 100}
    assert client.get("/items/0").status_code == 422
    assert client.get("/items/101").status_code == 422
    return "1/100 通过，0/101 拒绝"


def check_error_types() -> str:
    """越界时 detail[].type 精确对应用户违反的约束。"""
    zero = client.get("/items/0").json()["detail"][0]
    high = client.get("/items/101").json()["detail"][0]
    assert zero["type"] == "greater_than", zero
    assert zero["ctx"] == {"gt": 0}, zero
    assert high["type"] == "less_than_equal", high
    assert high["ctx"] == {"le": 100}, high
    return f"0→{zero['type']} 101→{high['type']}"


def check_float_interval() -> str:
    """ge=0, lt=10000：0 通过，10000 拒绝。"""
    assert client.get("/prices/0").json() == {"price": 0.0}
    assert client.get("/prices/9999.99").status_code == 200
    r = client.get("/prices/10000")
    assert r.status_code == 422, r.status_code
    assert r.json()["detail"][0]["type"] == "less_than", r.json()
    return "0 通过 / 10000 拒绝（less_than）"


def check_string_length() -> str:
    """min_length=3, max_length=8。"""
    assert client.get("/slugs/abc").json() == {"slug": "abc"}
    short = client.get("/slugs/ab").json()["detail"][0]
    long_ = client.get("/slugs/abcdefghi").json()["detail"][0]
    assert short["type"] == "string_too_short", short
    assert long_["type"] == "string_too_long", long_
    return f"ab→{short['type']} abcdefghi→{long_['type']}"


def check_pattern() -> str:
    """pattern 是整串匹配，ABC 不通过小写字母规则。"""
    r = client.get("/slugs/ABC")
    assert r.status_code == 422, r.status_code
    item = r.json()["detail"][0]
    assert item["type"] == "string_pattern_mismatch", item
    return f"{item['type']} pattern={item['ctx']['pattern']}"


def check_single_error_only() -> str:
    """同时违反 max_length 与 pattern，只返回 1 条。"""
    r = client.get("/slugs/ABCDEF")  # 长度 6（超 8？没超）这里用 9 位大写 + 超长
    r2 = client.get("/slugs/ABCDEFGHI")
    assert r2.status_code == 422
    count = len(r2.json()["detail"])
    assert count == 1, r2.json()
    return f"违反 2 条只返回 {count} 条"


def check_two_styles_equal() -> str:
    """在**相同约束**下，Annotated 与默认值写法的 422 完全一致。

    【注意】不能拿本章两个真实接口比较——它们的约束本来就不同
           （/items 是 gt=0，/legacy-style 是 ge=1），比出来的类型码必然不同。
    """
    c1, c2 = TestClient(_new_style_app), TestClient(_old_style_app)
    for bad in ("0", "11"):
        t1 = c1.get(f"/{bad}").json()["detail"][0]["type"]
        t2 = c2.get(f"/{bad}").json()["detail"][0]["type"]
        assert t1 == t2, (bad, t1, t2)
    # 正常值两边也一致
    assert c1.get("/5").json() == c2.get("/5").json() == {"v": 5}
    assert client.get("/legacy-style/5").json() == {"v": 5}
    return "同约束下两种写法 422 类型完全一致（greater_than / less_than_equal）"


def check_openapi_constraints() -> str:
    """约束必须出现在 OpenAPI schema 里，且 gt/ge 映射不同的键。"""
    schema = client.get("/openapi.json").json()
    item = schema["paths"]["/items/{item_id}"]["get"]["parameters"][0]["schema"]
    assert item["exclusiveMinimum"] == 0, item
    assert item["maximum"] == 100, item

    price = schema["paths"]["/prices/{price}"]["get"]["parameters"][0]["schema"]
    assert price["minimum"] == 0, price
    assert price["exclusiveMaximum"] == 10000, price

    slug = schema["paths"]["/slugs/{slug}"]["get"]["parameters"][0]["schema"]
    assert slug["minLength"] == 3 and slug["maxLength"] == 8, slug
    assert slug["pattern"] == "^[a-z]+$", slug
    return "exclusiveMinimum/minimum/exclusiveMaximum/minLength/pattern 全部就位"


def check_doc_meta() -> str:
    """description 与 deprecated 进 OpenAPI。"""
    schema = client.get("/openapi.json").json()
    param = schema["paths"]["/v1/codes/{code}"]["get"]["parameters"][0]
    assert param["schema"]["deprecated"] is True, param
    assert "旧版编码" in param["description"], param
    assert param["schema"]["title"] == "编码", param
    return f"title={param['schema']['title']} deprecated={param['schema']['deprecated']}"


def check_alias() -> str:
    """alias 让路径变量名与函数参数名不同。"""
    r = client.get("/alias-demo/7")
    assert r.status_code == 200, r.text
    assert r.json() == {"internal_id": 7}, r.json()
    schema = client.get("/openapi.json").json()
    name = schema["paths"]["/alias-demo/{real_id}"]["get"]["parameters"][0]["name"]
    assert name == "real_id", name
    return f"URL 用 real_id，函数用 internal_id，OpenAPI name={name}"


CHECKS = [
    ("数值范围边界", check_numeric_range),
    ("越界错误类型", check_error_types),
    ("浮点开闭区间", check_float_interval),
    ("字符串长度", check_string_length),
    ("正则整串匹配", check_pattern),
    ("多约束只报一条", check_single_error_only),
    ("两种写法等效", check_two_styles_equal),
    ("OpenAPI 约束表示", check_openapi_constraints),
    ("文档元信息", check_doc_meta),
    ("alias 用法", check_alias),
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
