"""第 05 章 · 路径参数。

核心：URL 路径段里的变量如何进入函数、类型标注如何触发转换、失败时 404 还是 422。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from __future__ import annotations

import uuid
from datetime import date

from fastapi import FastAPI

app = FastAPI(title="第 05 章 · 路径参数", version="0.1.0")


# ============================================================
# 1. 最基本形态：一段路径，一个参数
# ============================================================
@app.get("/users/{user_id}", tags=["用户"], summary="按 ID 查用户")
def get_user(user_id: int) -> dict[str, object]:
    """`{user_id}` 是路径模板，函数参数同名即可注入。

    【作用】标注 `int` 后，FastAPI 会做两步：
           1) 路径正则匹配 `^/users/[^/]+$`
           2) 把匹配到的字符串交给 Pydantic 转成 int
    【注意】第二步失败返回 **422**，不是 404——因为路径确实匹配上了。
    【为什么】返回 `type` 是为了让你亲眼看到它真的变成了 int，不是字符串。
    """
    return {"user_id": user_id, "type": type(user_id).__name__}


@app.get("/ratings/{score}", tags=["示例"], summary="浮点路径参数")
def get_rating(score: float) -> dict[str, object]:
    """`3.14` 会转成 float；`abc` 返回 422 `float_parsing`。"""
    return {"score": score, "type": type(score).__name__}


# ============================================================
# 2. 转换器：在正则层面就不匹配
# ============================================================
@app.get("/products/{code:int}", tags=["商品"], summary="整数转换器")
def get_product(code: int) -> dict[str, int]:
    """`{code:int}` 与 `code: int` 的区别是本章最重要的一点。

    【作用】`{code:int}` 让路径正则变成 `^/products/[0-9]+$`
    【注意】因此 `/products/abc` **匹配不到路由**，直接返回 404 + `{"detail": "Not Found"}`
    【为什么】404 与 422 对前端意味着完全不同的处理：
           404 = 这个资源不存在；422 = 你的请求格式不对。
    """
    return {"code": code}


@app.get("/orders/{order_id:uuid}", tags=["订单"], summary="UUID 转换器")
def get_order(order_id: uuid.UUID) -> dict[str, str]:
    """UUID 也支持转换器写法，非法 UUID 直接 404。

    【注意】函数标注必须是 `uuid.UUID`，与转换器一致；
           写成 `str` 会拿到原始字符串，丢失校验能力。
    """
    return {"order_id": str(order_id)}


# ============================================================
# 3. 多段路径参数
# ============================================================
@app.get("/trips/{from_city}/to/{to_city}", tags=["示例"], summary="双路径参数")
def get_trip(from_city: str, to_city: str, day: date | None = None) -> dict[str, object]:
    """两个路径参数 + 一个查询参数混用。

    【作用】FastAPI 按「参数名是否出现在路径模板里」自动区分：
           出现在模板里 → 路径参数（必填）
           没出现在模板里 → 查询参数（有默认值则可选）
    【注意】`day` 没写进路径，所以它是查询参数，写法是 `/trips/A/to/B?day=2026-01-01`
    """
    return {
        "from": from_city,
        "to": to_city,
        # 【注意】date 未传时为 None；传了会按 ISO 8601 解析
        "day": day.isoformat() if day else None,
    }


# ============================================================
# 4. bool 路径参数的真实行为（反直觉，务必实测）
# ============================================================
@app.get("/flags/{flag}", tags=["示例"], summary="布尔路径参数")
def get_flag(flag: bool) -> dict[str, object]:
    """`bool` 路径参数接受的写法比你想的多。

    【实测】`true` / `1` / `yes` → True；`0` → False；`maybe` → 422
    【注意】这意味着 `/flags/1` 与 `/flags/true` 等价，缓存键却不同——
           对 CDN 与浏览器缓存是灾难。生产上几乎不该用 bool 路径参数。
    """
    return {"flag": flag, "type": type(flag).__name__}


# ============================================================
# 5. 路径参数写默认值 = 静默失效（实测，反直觉）
# ============================================================
# 【实测】下面这个函数**不会报错**，但 `= 1` 完全不起作用：
#   - GET /legacy/5   -> 200 {"user_id": 5}
#   - GET /legacy/abc -> 422 int_parsing（仍然必填、仍然校验）
#   - OpenAPI 里该参数仍是 required=true，且没有 default
# 【注意】所以「给路径参数写默认值」是一个纯粹的陷阱：读代码的人以为它可选，
#        实际调用方必须传，且传了才会覆盖——默认值永远不会被用到。
# 【正确做法】路径参数一律不写默认值；确实要可选就改成查询参数。
@app.get("/legacy/{user_id}", tags=["示例"], summary="错误的写法演示")
def legacy(user_id: int = 1) -> dict[str, object]:
    """演示陷阱：默认值被忽略，函数里的 `1` 永远不会生效。"""
    return {"user_id": user_id, "note": "默认值 1 从未生效"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
