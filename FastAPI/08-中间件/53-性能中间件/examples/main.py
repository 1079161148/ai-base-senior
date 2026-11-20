"""第 53 章 · 性能中间件（GZip + TrustedHost）。

核心：`GZipMiddleware(minimum_size=N)` 只在「客户端接受 gzip」且「响应体 ≥ N 字节」
      且「响应没有自己声明 Content-Encoding」时才压；压完会补 `Vary: Accept-Encoding`
      并**删掉 Content-Length**（变成分块）。
      `TrustedHostMiddleware` 校验 `Host` 头，不匹配直接 **400**，用于防 Host 头注入。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Any

from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import Response

# ============================================================
# 1. 压缩：阈值 500 字节
# ============================================================
app = FastAPI(title="第 53 章 · GZip", version="0.1.0")
app.add_middleware(GZipMiddleware, minimum_size=500)

BIG_TEXT = "FastAPI 中间件压缩演示。" * 100  # 远超 500 字节


@app.get("/small", tags=["GZip"], summary="小于阈值：不压")
def small() -> dict[str, str]:
    return {"msg": "hi"}


@app.get("/big", tags=["GZip"], summary="超过阈值：压缩")
def big() -> Response:
    """【实测】响应带 `Content-Encoding: gzip`、`Vary: Accept-Encoding`，
    且 `Content-Length` 被移除
    """
    return Response(content=BIG_TEXT, media_type="text/plain")


@app.get("/big-json", tags=["GZip"], summary="大 JSON 也压")
def big_json() -> dict[str, Any]:
    return {"items": [{"id": i, "name": f"商品-{i}"} for i in range(80)]}


@app.get("/already-encoded", tags=["GZip"], summary="已声明编码：不重复压")
def already_encoded() -> Response:
    """【实测】响应自己带 `Content-Encoding` 时，GZip 中间件不会再压"""
    return Response(
        content=b"\x1f\x8b\x08\x00\x00\x00\x00\x00\x00\x03",
        media_type="application/octet-stream",
        headers={"Content-Encoding": "gzip"},
    )


@app.get("/png", tags=["GZip"], summary="image/* 不压")
def png() -> Response:
    """【实测】`image/png` 这类**不会被压**（框架按 content-type 过滤）

    【原因】对 JPEG/PNG/MP4 等已压缩数据再压无收益，甚至变大
    """
    return Response(content=b"\x89PNG\r\n\x1a\n" + b"\x00" * 2000, media_type="image/png")


@app.get("/octet", tags=["GZip"], summary="application/octet-stream 也不压")
def octet() -> Response:
    """【实测】二进制流不压（实测 `content-encoding` 为空）"""
    return Response(content=b"\x00" * 2000, media_type="application/octet-stream")


@app.get("/csv", tags=["GZip"], summary="text/csv 会压")
def csv_data() -> Response:
    """【实测】`text/*` 一律压"""
    return Response(content="a,b,c\n" * 500, media_type="text/csv")


# ============================================================
# 2. Host 校验
# ============================================================
host_app = FastAPI(title="第 53 章 · TrustedHost", version="0.1.0")
host_app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["example.com", "*.example.com"],
    www_redirect=False,
)


@host_app.get("/ping")
def host_ping() -> dict[str, str]:
    """【实测】Host 不在白名单 → 400 `Invalid host header`"""
    return {"ok": "true"}


redirect_app = FastAPI(title="第 53 章 · www 重定向", version="0.1.0")
redirect_app.add_middleware(
    TrustedHostMiddleware,
    # 【注意】`www` 子域也要在白名单里，否则直接 400，轮不到重定向
    allowed_hosts=["example.com", "www.example.com"],
    www_redirect=True,
)


@redirect_app.get("/ping")
def redirect_ping() -> dict[str, str]:
    return {"ok": "true"}


# 【对照】白名单只写 `example.com`，看 `www` 子域到底 301 还是 400
redirect2_app = FastAPI(title="第 53 章 · www 重定向对照")
redirect2_app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["example.com"],
    www_redirect=True,
)


@redirect2_app.get("/ping")
def redirect2_ping() -> dict[str, str]:
    return {"ok": "true"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)