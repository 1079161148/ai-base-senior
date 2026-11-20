"""第 06 章 · 路径参数校验（Path）。

核心：用 Path() 给路径参数加约束与文档信息；约束失败统一 422。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, Path

app = FastAPI(title="第 06 章 · 路径参数校验", version="0.1.0")


# ============================================================
# 1. 数值约束：gt / ge / lt / le
# ============================================================
@app.get("/items/{item_id}", tags=["商品"], summary="商品详情（1–100）")
def get_item(
    item_id: Annotated[int, Path(gt=0, le=100, description="商品 ID，取值 1–100")],
) -> dict[str, int]:
    """数值约束演示。

    【作用】gt=0 表示「> 0」（不含 0）；le=100 表示「≤ 100」（含 100）
    【注意】`gt` 进 OpenAPI 是 `exclusiveMinimum`，`ge` 才是 `minimum`。
           两者语义不同，前端生成的校验代码也不同。
    【实测】1 和 100 通过；0 报 `greater_than`；101 报 `less_than_equal`
    """
    return {"item_id": item_id}


@app.get("/prices/{price}", tags=["示例"], summary="价格（0 ≤ x < 10000）")
def get_price(
    price: Annotated[float, Path(ge=0, lt=10000, description="价格，0 ≤ x < 10000")],
) -> dict[str, float]:
    """开区间与闭区间混用：ge（含）0，lt（不含）10000。

    【注意】金额在真实业务中应使用 Decimal 而非 float（会丢精度），
           这里为了演示 float 路径参数而简化，第 17 章给 Decimal 方案。
    """
    return {"price": price}


# ============================================================
# 2. 字符串约束：min_length / max_length / pattern
# ============================================================
@app.get("/slugs/{slug}", tags=["示例"], summary="短链 slug（3–8 位小写字母）")
def get_slug(
    slug: Annotated[
        str,
        Path(
            min_length=3,
            max_length=8,
            pattern="^[a-z]+$",
            description="3–8 位小写字母",
        ),
    ],
) -> dict[str, str]:
    """字符串约束演示。

    【作用】pattern 使用正则，**匹配整串**（相当于自动加 ^...$，但仍建议显式写）
    【实测】`ab` → string_too_short；`abcdefghi` → string_too_long；`ABC` → string_pattern_mismatch
    【注意】多条约束同时违反时，**只返回第一条错误**，不是全部列出。
    """
    return {"slug": slug}


# ============================================================
# 3. 两种写法：Annotated 与默认值风格
# ============================================================
@app.get("/legacy-style/{v}", tags=["示例"], summary="旧风格：默认值写法")
def legacy_style(v: int = Path(ge=1, le=10, description="1–10")) -> dict[str, int]:
    """这是 FastAPI 早期文档的写法：用 `= Path(...)` 代替默认值。

    【作用】与 Annotated 写法在**运行时行为完全一致**（实测 422 类型码相同）
    【为什么】Annotated 更符合 Python 类型系统、可被静态检查工具识别；
            而且依赖注入与校验可解耦。新代码建议统一用 Annotated。
    【注意】路径参数不存在「默认值」，这里的 `= Path(...)` 只是「声明校验规则」的位置。
    """
    return {"v": v}


# ============================================================
# 4. 文档元信息：title / description / deprecated
# ============================================================
@app.get("/v1/codes/{code}", tags=["兼容"], summary="旧版编码查询（已废弃）")
def get_old_code(
    code: Annotated[
        str,
        Path(
            title="编码",
            description="旧版编码，仅保留兼容；新业务请用 /slugs/{slug}",
            deprecated=True,
        ),
    ],
) -> dict[str, str]:
    """`deprecated=True` 会在 OpenAPI 里标记该参数已废弃，文档 UI 会划掉它。

    【注意】废弃的是**参数**，不是整个接口。要废弃整个接口，
           用 `@app.get(..., deprecated=True)`（第 26 章）。
    """
    return {"code": code}


# ============================================================
# 5. alias：路径里的变量名与函数参数名不一致
# ============================================================
@app.get("/alias-demo/{real_id}", tags=["示例"], summary="alias 用法")
def alias_demo(
    # 【注意】这里把「路径模板里的名字」显式写给 alias，
    #        函数参数名可以不同。实测 OpenAPI 里 name 仍是 real_id。
    internal_id: Annotated[int, Path(alias="real_id", ge=1)],
) -> dict[str, int]:
    """一般不建议用 alias——名字不一致会让排查变难。仅在兼容旧 URL 时使用。"""
    return {"internal_id": internal_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
