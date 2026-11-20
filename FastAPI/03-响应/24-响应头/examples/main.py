"""第 24 章 · 响应头。

核心：响应头不能写进 Pydantic 模型，必须通过「注入 Response」或「直接返回 Response」设置。
      装饰器里的 `responses={200: {"headers": ...}}` 只影响文档，不会真的发头。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Any

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse, PlainTextResponse
from pydantic import BaseModel

app = FastAPI(title="第 24 章 · 响应头", version="0.1.0")


class ItemOut(BaseModel):
    id: int
    name: str


_ITEM = ItemOut(id=1, name="机械键盘")


# ============================================================
# 1. 注入 Response 设置头
# ============================================================
@app.get("/headers/basic", response_model=ItemOut, tags=["响应头"], summary="注入 Response 加头")
def basic(response: Response) -> ItemOut:
    """【作用】`response.headers[...]` 就是最终响应的头

    【实测】大小写不敏感：写 `X-Request-Id`，客户端用 `x-request-id` 也能取到
    【注意】`Response` 参数不参与请求解析，只是给你一个可写的响应对象
    """
    response.headers["X-Request-Id"] = "req-abc-123"
    response.headers["X-RateLimit-Remaining"] = "99"
    return _ITEM


# ============================================================
# 2. 直接返回带 headers 的 Response
# ============================================================
@app.get("/headers/direct", tags=["响应头"], summary="JSONResponse 带头")
def direct() -> Any:
    """【作用】完全自定义头与媒体类型

    【注意】返回 `Response` 会绕过 `response_model`（第 23 章）
    """
    return JSONResponse(
        {"id": 1, "name": "机械键盘", "extra": "不会被过滤"},
        headers={"X-Cache": "HIT", "X-Edge": "sh-01"},
    )


# ============================================================
# 3. 媒体类型
# ============================================================
@app.get("/headers/text", tags=["响应头"], summary="自定义 Content-Type")
def text() -> Any:
    """【实测】`PlainTextResponse` 的 `Content-Type` 是 `text/plain; charset=utf-8`"""
    return PlainTextResponse("ok", headers={"X-Format": "plain"})


# ============================================================
# 4. Cookie
# ============================================================
@app.post("/headers/login", tags=["响应头"], summary="下发 Set-Cookie")
def login(response: Response) -> dict[str, str]:
    """【作用】`set_cookie` 帮你拼 `Set-Cookie` 头

    【实测】默认带 `Path=/`、`HttpOnly`？—— 不传 `httponly=True` 时**不会**加
    【注意】生产必须 `httponly=True` + `secure=True` + `samesite="lax"`
    """
    response.set_cookie(
        key="session",
        value="token-123",
        max_age=3600,
        httponly=True,
        samesite="lax",
    )
    return {"status": "ok"}


@app.post("/headers/multi-cookie", tags=["响应头"], summary="下发多个 Cookie")
def multi_cookie(response: Response) -> dict[str, str]:
    """【实测】同一个响应里可以有多个 `Set-Cookie`，客户端拿到的 headers 会合并显示"""
    response.set_cookie("a", "1")
    response.set_cookie("b", "2")
    return {"status": "ok"}


# ============================================================
# 5. 文档里的响应头（只影响 OpenAPI）
# ============================================================
@app.get(
    "/headers/documented",
    response_model=ItemOut,
    responses={
        200: {
            "description": "带限流信息的成功响应",
            "headers": {
                "X-RateLimit-Remaining": {
                    "description": "剩余配额",
                    "schema": {"type": "integer", "example": 99},
                }
            },
        }
    },
    tags=["响应头"],
    summary="文档中声明响应头",
)
def documented() -> ItemOut:
    """【实测】`responses[200].headers` 只出现在 `/openapi.json`，**不会**真的发这个头

    【结论】文档要写、头也要自己 set，两边都不能忘
    """
    return _ITEM


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
