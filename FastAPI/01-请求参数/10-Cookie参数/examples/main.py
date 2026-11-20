"""第 10 章 · Cookie 参数。

核心：Cookie() 读入参，response.set_cookie() 写出参，6 个安全属性怎么配。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from __future__ import annotations

from typing import Annotated

from fastapi import Cookie, FastAPI, Response

app = FastAPI(title="第 10 章 · Cookie 参数", version="0.1.0")


# ============================================================
# 1. 读 Cookie
# ============================================================
@app.get("/me", tags=["会话"], summary="读取会话 Cookie")
def me(
    # 【作用】浏览器请求时自动带 `Cookie: session_id=xxx`，这里直接取值
    # 【注意】`str | None = None` → 可选；不传时为 None（不会 422）
    #        要必填就写 `Annotated[str, Cookie()]`，缺失会 422 missing
    session_id: Annotated[str | None, Cookie()] = None,
    theme: Annotated[str | None, Cookie()] = None,
) -> dict[str, str | None]:
    """读取两个 Cookie。

    【注意】Cookie 名**大小写敏感**：`Session_Id` 与 `session_id` 是两个不同的 Cookie。
    【注意】Cookie 值不会自动 URL 解码，需要时自己 `urllib.parse.unquote`。
    """
    return {"session_id": session_id, "theme": theme}


# ============================================================
# 2. 写 Cookie：必须通过 Response
# ============================================================
@app.get("/login", tags=["会话"], summary="登录并种 Cookie")
def login(response: Response, user: str = "alice") -> dict[str, str]:
    """设置会话 Cookie。

    【关键】必须把 `response: Response` 声明为参数，FastAPI 会注入真正的响应对象。
           直接 `return {"session_id": ...}` 不会产生 Set-Cookie 头。
    【实测】响应头为：
           session_id=abc123; HttpOnly; Max-Age=3600; Path=/; SameSite=lax
    【注意】`secure=False` 时**不会**出现 `Secure` 属性（本机是 HTTP 环境）。
           生产必须 `secure=True`，否则 HTTPS 降级时 Cookie 明文传输。
    """
    response.set_cookie(
        key="session_id",
        value=f"sess-{user}",
        max_age=3600,          # 1 小时后过期（秒）
        httponly=True,         # 禁止 JS 读（防 XSS 偷 token）
        secure=False,          # 【生产改 True】仅 HTTPS 传输
        samesite="lax",        # CSRF 防护：同站请求才带
        path="/",              # 生效路径，尽量收窄
    )
    return {"login": "ok", "user": user}


@app.get("/logout", tags=["会话"], summary="退出并删 Cookie")
def logout(response: Response) -> dict[str, str]:
    """删除 Cookie 的标准做法。

    【注意】删除不是「清空值」，而是让浏览器立刻过期：
           `delete_cookie` 实际发送 `Max-Age=0` 的 Set-Cookie。
    【注意】`path`/`domain` 必须与设置时一致，否则删不掉。
    """
    response.delete_cookie("session_id", path="/")
    return {"logout": "ok"}


@app.get("/set-many", tags=["会话"], summary="一次设多个 Cookie")
def set_many(response: Response) -> dict[str, str]:
    """多次调用 `set_cookie` 会生成多条 Set-Cookie 头（不是合并成一条）。

    【注意】HTTP 规范里 Set-Cookie 不能合并，所以必须用 `headers.get_list("set-cookie")`
           读取多条；普通 `headers["set-cookie"]` 只会拿到一条。
    """
    response.set_cookie("a", "1")
    response.set_cookie("b", "2", httponly=True)
    return {"ok": "2 cookies"}


# ============================================================
# 3. 必填 Cookie
# ============================================================
@app.get("/must-have", tags=["会话"], summary="必填 Cookie")
def must_have(tenant: Annotated[str, Cookie()]) -> dict[str, str]:
    """没有默认值 → Cookie 必填；缺失返回 422，`loc` 是 ["cookie","tenant"]。

    【注意】这很少用：浏览器没带 Cookie 就报 422，对用户体验不好。
           更常见的是「可选 + 业务层校验后返回 401」（第 46 章）。
    """
    return {"tenant": tenant}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
