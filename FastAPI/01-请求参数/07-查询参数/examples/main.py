"""第 07 章 · 查询参数。

核心：`?key=value` 形式的参数如何声明、可选性由什么决定、多值与 bool 的真实行为。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from __future__ import annotations

from fastapi import FastAPI, Query

app = FastAPI(title="第 07 章 · 查询参数", version="0.1.0")


# ============================================================
# 1. 可选参数：默认值决定一切
# ============================================================
@app.get("/search", tags=["搜索"], summary="搜索（可选参数）")
def search(
    q: str | None = None,
    limit: int = 10,
) -> dict[str, object]:
    """两个参数都没有写进路径 → 都是查询参数。

    【作用】`q: str | None = None` 表示「可选的字符串」：
           不传时是 None，OpenAPI 里生成 `anyOf: [{type: string}, {type: null}]`
    【注意】不要写 `q: str = None`——3.10+ 的静态检查会报类型不符，
           运行时虽能跑，但文档会显示 `type: string` 而不是可空。
    【实测】不传 → {"q": null, "limit": 10}；传 → 覆盖默认值
    """
    return {"q": q, "limit": limit}


# ============================================================
# 2. 必填参数：没有默认值
# ============================================================
@app.get("/reports", tags=["报表"], summary="月度报表（必填）")
def reports(month: str) -> dict[str, str]:
    """`month` 没有默认值 → 必填。

    【实测】不传时返回 422：
           {"detail":[{"type":"missing","loc":["query","month"],"msg":"Field required"}]}
    【注意】必填与「业务上必须有值」是两件事：必填只是「URL 里必须有这个键」，
           值是空字符串 `?month=` 也算传了（会得到 ""）。
    """
    return {"month": month}


# ============================================================
# 3. 多值参数：list[str]
# ============================================================
@app.get("/tags", tags=["搜索"], summary="多值参数")
def by_tags(
    tag: list[str] = Query(default=[]),
) -> dict[str, object]:
    """`list[str]` 用**重复键**接收多值。

    【作用】`?tag=a&tag=b` → `["a", "b"]`
    【注意】`?tag=a,b` **不会**被拆成两个，而是得到 `["a,b"]` 一个元素。
           这是本章最容易踩的坑：很多人以为会按逗号分割。
    【为什么】HTTP 查询串没有「数组」的官方约定，FastAPI 选择「重复键」这种最直白的解析。
    【注意】`Query(default=[])` 里的默认值不要写成 `Query(default=None)` 再判断，
           直接用空列表更简单（但注意可变默认值在 Pydantic 模型里会被复制，这里是安全的）。
    """
    return {"tag": tag, "count": len(tag)}


@app.get("/tags-csv", tags=["搜索"], summary="逗号分隔的自解析")
def by_tags_csv(tag: str | None = None) -> dict[str, object]:
    """如果前端只会传 `?tag=a,b,c`，就自己 split。

    【作用】把「逗号分隔」这种非标准写法显式处理，比依赖框架猜测更可控。
    【注意】要处理空值：`?tag=` 会得到 `[""]`，应过滤掉空串。
    """
    if not tag:
        return {"tag": []}
    items = [t.strip() for t in tag.split(",") if t.strip()]
    return {"tag": items}


# ============================================================
# 4. bool 查询参数
# ============================================================
@app.get("/flags", tags=["示例"], summary="布尔查询参数")
def flags(flag: bool = False) -> dict[str, object]:
    """bool 的可选参数是查询参数里**最适合**用 bool 的场景（有默认值可兜底）。

    【实测】true / 1 / yes / on → True；false / 0 / no / off → False；maybe → 422
    【注意】前端传 `?flag`（键存在但无值）会得到 422，不是 True。
           需要「开关式」语义时用 `?flag=1` 或自己写 `str` 解析。
    """
    return {"flag": flag, "type": type(flag).__name__}


# ============================================================
# 5. 中文与空格
# ============================================================
@app.get("/greet", tags=["示例"], summary="中文与空格")
def greet(name: str = "世界", note: str | None = None) -> dict[str, str | None]:
    """查询参数的值会做 URL 解码。

    【作用】`?name=%E5%8C%97%E4%BA%AC` 会被解码成「北京」
    【注意】空格要编码成 `%20` 或 `+`；裸空格会让请求行非法。
    """
    return {"name": name, "note": note}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
