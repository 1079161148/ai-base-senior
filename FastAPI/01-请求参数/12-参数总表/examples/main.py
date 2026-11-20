"""第 12 章 · 参数总表。

核心：路径 / 查询 / 请求头 / Cookie 四类参数是**四个不同的取值位置**，不是四种数据类型。
      同名不会互相覆盖；`Request` 直取是「绕过校验」的旁路。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Annotated

from fastapi import Cookie, FastAPI, Header, Path, Query, Request

app = FastAPI(title="第 12 章 · 参数总表", version="0.1.0")


# ============================================================
# 1. 四类参数放进同一个接口
# ============================================================
@app.get("/summary/{item_id}", tags=["示例"], summary="同一个接口收四类参数")
def summary(
    # 【作用】名字出现在路由模板 `{item_id}` 里 → 路径参数（in=path）
    # 【注意】路径参数天然必填：URL 里没有这一段，路由根本匹配不上（404）
    item_id: Annotated[int, Path(ge=1, description="路径参数：URL 路径的一段")],
    # 【作用】注入原始 Request 对象：可以读任何位置的值，但**不做校验**
    # 【注意】它不参与 OpenAPI，也不会出现在 /docs 的参数表里
    request: Request,
    # 【作用】名字不在模板里 + 有默认值 → 查询参数（in=query），可选
    q: Annotated[str | None, Query(description="查询参数：?q=xxx")] = None,
    # 【作用】参数名 `x_token` 默认转成头名 `X-Token`（in=header）
    x_token: Annotated[str | None, Header(description="请求头：X-Token")] = None,
    # 【作用】从 Cookie 里取值（in=cookie）；名字对应 cookie 键 `sid`
    sid: Annotated[str | None, Cookie(description="Cookie：sid")] = None,
) -> dict[str, object]:
    """typed（已校验）与 raw（原始字符串）对照。

    【实测】/summary/7?q=hello + X-Token: tk + Cookie sid=s1 返回：
           typed.item_id == 7      （int，已转换）
           raw.path_params == {"item_id": "7"}   （永远是字符串）
    【为什么】raw 侧不经过 Pydantic，所以类型、格式、范围全部要自己判断。
    """
    return {
        "typed": {"item_id": item_id, "q": q, "x_token": x_token, "sid": sid},
        "raw": {
            "path_params": dict(request.path_params),
            "query_params": dict(request.query_params),
            "headers_x_token": request.headers.get("x-token"),
            "cookies": dict(request.cookies),
            "method": request.method,
        },
    }


# ============================================================
# 2. 同名不冲突：四个 q 各取各的位置
# ============================================================
@app.get("/conflict/{q}", tags=["示例"], summary="同名参数在不同位置互不干扰")
def conflict(
    # 【作用】路径里的 q
    q: Annotated[str, Path(description="路径里的 q")],
    # 【作用】查询串里的 q；因为 Python 参数名不能重复，用 alias 指回 "q"
    q_as_query: Annotated[str | None, Query(alias="q")] = None,
    # 【作用】请求头里的 q（HTTP 头名不区分大小写）
    q_as_header: Annotated[str | None, Header(alias="q")] = None,
    # 【作用】Cookie 里的 q
    q_as_cookie: Annotated[str | None, Cookie(alias="q")] = None,
) -> dict[str, str | None]:
    """四个来源同名，各自取值。

    【实测】GET /conflict/path?q=query，头 q=header，Cookie q=cookie
           → {"path": "path", "query": "query", "header": "header", "cookie": "cookie"}
    【注意】不存在「谁覆盖谁」的优先级链——FastAPI 是按**声明的位置**去对应容器里取，
           四个容器本来就是分开的。真正会冲突的是「声明位置」和「路径模板」不一致（见第 3 节）。
    """
    return {"path": q, "query": q_as_query, "header": q_as_header, "cookie": q_as_cookie}


# ============================================================
# 3. 陷阱一：声明位置与路径模板冲突 → 启动期直接报错
# ============================================================
# 【注意】下面这种写法**不要出现在业务代码里**，它在导入模块时就会 AssertionError，
#       服务根本起不来。verify.py 用临时 app 复现三条错误信息：
#       - 模板里的参数声明成 Query() → Cannot use `Query` for path param 'item_id'
#       - 模板里的参数声明成 Header() → Cannot use `Header` for path param 'token'
#       - 模板里的参数给默认值       → Path parameters cannot have default values
#       结论：**参数名一旦出现在路由模板里，就只能按路径参数处理**。


# ============================================================
# 4. 陷阱二：Path() 用在不在模板里的参数 → 不报错，但永远 422
# ============================================================
@app.get("/ghost", tags=["陷阱"], summary="幽灵路径参数：永远无法满足")
def ghost(
    x: Annotated[int, Path(description="这个名字不在 /ghost 的模板里")],
) -> dict[str, int]:
    """声明成路径参数，但路由里没有 `{x}` 这一段。

    【实测】启动**不报错**；GET /ghost?x=1 依然 422：
           {"type":"missing","loc":["path","x"],"msg":"Field required"}
    【为什么】路径参数只能从 URL 路径里取，而这条路由的路径里没有 x，
           所以这个值永远取不到。OpenAPI 里却会显示 `in: path, required: true`，
           前端照着文档传也没用——这类 bug 极难排查。
    【正确做法】参数名必须与 `{x}` 完全一致，或改用 Query()。
    """
    return {"x": x}


# ============================================================
# 5. 只用 Request 直取：不校验、不转换
# ============================================================
@app.get("/raw", tags=["示例"], summary="只用 Request 直取原始值")
def raw(request: Request) -> dict[str, object]:
    """演示「绕过校验」的代价。

    【实测】/raw?limit=abc&q=1&q=2 依然 200：
           limit 拿到的是字符串 "abc"（不会 422）
           query_params.get("q") == "2"（取最后一个）
           query_params.getlist("q") == ["1", "2"]
    【注意】headers.get() 取重复头是**第一个**，query_params.get() 取重复键是**最后一个**，
           两者行为相反，且属于实现细节，不要依赖。
    """
    return {
        "limit_raw": request.query_params.get("limit"),
        "q_get": request.query_params.get("q"),
        "q_getlist": request.query_params.getlist("q"),
        "x_token": request.headers.get("x-token"),
        "has_sid": "sid" in request.cookies,
        "client": request.client.host if request.client else None,
    }


# ============================================================
# 6. 错误聚合：一次请求把所有非法参数都报出来
# ============================================================
@app.get("/aggregate/{item_id}", tags=["示例"], summary="多个参数同时非法时错误聚合")
def aggregate(
    item_id: int,
    # 【注意】必填参数（无默认值）必须写在有默认值的参数前面，否则是 Python 语法错误
    x_token: Annotated[str, Header(min_length=8, description="至少 8 位")],
    limit: Annotated[int, Query(ge=1, le=100, description="1–100")] = 20,
) -> dict[str, object]:
    """【实测】/aggregate/abc?limit=999 + X-Token: abc → 一个 422 里含三条错误：
    loc = ["path","item_id"] / ["query","limit"] / ["header","x-token"]
    【为什么】校验在进入函数之前统一做，不在函数体里逐行判断；所以**函数体永远拿到合法值**。
    """
    return {"item_id": item_id, "limit": limit, "token_length": len(x_token)}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
