"""第 54 章 · 反向代理适配。

核心：反向代理（Nginx/Traefik）把 `/api/xxx` 转发成 `/xxx`，应用必须知道
      「我挂在 `/api` 下」才能生成正确的文档地址和绝对 URL。这靠两件事：
      1) `root_path`：告诉应用前缀（`uvicorn --root-path /api`）
      2) `X-Forwarded-*`：告诉应用原始协议/客户端 IP/Host
      前者管「URL 生成」，后者管「取值正确」，互不替代。

【实测】`FastAPI(root_path=...)` 在当前版本已触发 `FastAPIDeprecationWarning`
      （官方要求由 server 配置），所以这里用一个 ASGI 中间件模拟 server 的行为，
      效果与 `uvicorn --root-path` 完全一致。

启动：uvicorn main:app --root-path /api --proxy-headers --reload
验收：python verify.py
"""

from typing import Any

import uvicorn
from fastapi import FastAPI, Request
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

ROOT_PATH = "/api"


# ============================================================
# 0. 模拟 server 注入 root_path（等价于 `--root-path /api`）
# ============================================================
class RootPathMiddleware:
    """【作用】把固定前缀写进 `scope["root_path"]`

    【要点】这是 ASGI server 该做的事；应用层只读 `scope`，不自己猜前缀
    """

    def __init__(self, app: Any, root_path: str) -> None:
        self.app = app
        self.root_path = root_path

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            scope = dict(scope)
            scope["root_path"] = self.root_path
        await self.app(scope, receive, send)


app = FastAPI(title="第 54 章 · 反向代理适配", version="0.1.0")
app.add_middleware(RootPathMiddleware, root_path=ROOT_PATH)


@app.get("/whoami", tags=["代理"], summary="看应用眼里的自己")
def whoami(request: Request) -> dict[str, Any]:
    """【实测】`root_path` 来自 scope；`request.url.path` 仍不含前缀

    【要点】前缀只出现在 `base_url`、`url_for()`、`/docs`、`servers` 里
    """
    return {
        "root_path": request.scope.get("root_path", ""),
        "path": request.url.path,
        "base_url": str(request.base_url),
        "url_for": str(request.url_for("whoami")),
        "client": request.client.host if request.client else None,
        "scheme": request.url.scheme,
        "xff": request.headers.get("x-forwarded-for"),
        "xfp": request.headers.get("x-forwarded-proto"),
        "xfh": request.headers.get("x-forwarded-host"),
    }


@app.get("/items/{item_id}", tags=["代理"], summary="路径参数不受前缀影响")
def read_item(item_id: int, request: Request) -> dict[str, Any]:
    """【实测】路由匹配用的是去掉前缀后的路径"""
    return {"item_id": item_id, "url_for": str(request.url_for("read_item", item_id=item_id))}


# ============================================================
# 1. 对照：不注入 root_path
# ============================================================
plain_app = FastAPI(title="对照 · 无 root_path")


@plain_app.get("/whoami")
def plain_whoami(request: Request) -> dict[str, Any]:
    return {
        "root_path": request.scope.get("root_path", ""),
        "base_url": str(request.base_url),
        "url_for": str(request.url_for("plain_whoami")),
    }


# ============================================================
# 2. 关闭 `servers` 注入
# ============================================================
no_servers_app = FastAPI(
    title="对照 · root_path_in_servers=False",
    root_path_in_servers=False,
)
no_servers_app.add_middleware(RootPathMiddleware, root_path=ROOT_PATH)


@no_servers_app.get("/ping")
def no_servers_ping() -> dict[str, str]:
    return {"ok": "true"}


# ============================================================
# 3. 让应用认 X-Forwarded-*
# ============================================================
# 【要点】ProxyHeadersMiddleware 是 **uvicorn 的**，不在 Starlette 里；
#         `uvicorn --proxy-headers` 就是加它
inner_app = FastAPI(title="ProxyHeaders 演示")


@inner_app.get("/whoami")
def proxy_whoami(request: Request) -> dict[str, Any]:
    return {
        "client": request.client.host if request.client else None,
        "scheme": request.url.scheme,
        "host": request.url.hostname,
        "port": request.url.port,
    }


# 【注意】`trusted_hosts` 必须是反代自己的 IP，写 `"*"` 等于信任任何来源
proxied_app = ProxyHeadersMiddleware(inner_app, trusted_hosts=["127.0.0.1"])


# ============================================================
# 4. `X-Forwarded-Prefix`：Starlette 不内置，要自己写
# ============================================================
class ForwardedPrefixMiddleware:
    """【作用】从 `X-Forwarded-Prefix` 读前缀写进 scope

    【注意】Starlette 只认 scope 里的 `root_path`，不会自动读这个头；
            生产更推荐固定前缀，别让请求头改变 URL 生成（缓存/开放重定向风险）
    """

    def __init__(self, app: Any) -> None:
        self.app = app

    async def __call__(self, scope: dict, receive: Any, send: Any) -> None:
        if scope["type"] == "http":
            for key, value in scope["headers"]:
                if key == b"x-forwarded-prefix":
                    scope = dict(scope)
                    scope["root_path"] = value.decode("latin-1").rstrip("/")
                    break
        await self.app(scope, receive, send)


prefix_app = ForwardedPrefixMiddleware(plain_app)


if __name__ == "__main__":
    # 【要点】命令行等价写法：
    # uvicorn main:app --root-path /api --proxy-headers --forwarded-allow-ips 127.0.0.1
    uvicorn.run(app, host="127.0.0.1", port=8000)