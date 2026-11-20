"""第 11 章 · Header 参数。

核心：下划线↔连字符自动转换、大小写不敏感、重复头成列表、必填头的 loc 命名。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from __future__ import annotations

from typing import Annotated

from fastapi import FastAPI, Header

app = FastAPI(title="第 11 章 · Header 参数", version="0.1.0")


# ============================================================
# 1. 标准头与自定义头
# ============================================================
@app.get("/me", tags=["示例"], summary="读标准头与自定义头")
def me(
    # 【作用】默认 convert_underscores=True：`user_agent` ↔ `User-Agent`
    # 【注意】头名大小写不敏感，`user-agent` 与 `USER-AGENT` 都能读到
    user_agent: Annotated[str | None, Header()] = None,
    # 【作用】`x_token` ↔ `X-Token`：下划线自动转连字符
    x_token: Annotated[str | None, Header()] = None,
    accept_language: Annotated[str | None, Header()] = None,
) -> dict[str, str | None]:
    """三个头都声明为可选。

    【注意】可选头缺失时是 `None`；但「头存在但值为空」是 `""`，两者不同。
    """
    return {"user_agent": user_agent, "x_token": x_token, "accept_language": accept_language}


# ============================================================
# 2. convert_underscores=False 的双向陷阱（实测）
# ============================================================
@app.get("/no-convert", tags=["示例"], summary="关闭下划线转换")
def no_convert(
    user_agent: Annotated[str | None, Header(convert_underscores=False)] = None,
) -> dict[str, str | None]:
    """关闭转换后，FastAPI **只认**下划线形式的头名 `user_agent`。

    【实测】发 `user_agent: raw/1.0` → 读到 "raw/1.0"
    【实测】发 `User-Agent: ua/1.0` → 读到 **None**（因为找的是 `user_agent`）
    【为什么】HTTP 头名规范允许下划线，但很多代理会拒绝/改写下划线头，
           所以生产上通常**保持默认 True**，需要特殊头名时用 `alias`。
    """
    return {"user_agent": user_agent}


# ============================================================
# 3. 重复头 → list[str]
# ============================================================
@app.get("/tags", tags=["示例"], summary="重复头解析成列表")
def header_tags(
    x_tag: Annotated[list[str] | None, Header()] = None,
) -> dict[str, object]:
    """同名头出现多次时，用 `list[str]` 能全部收到。

    【实测】`X-Tag: a` + `X-Tag: b` → `["a", "b"]`
    【注意】用 `str` 接收时只会拿到其中一个（且不保证是第一个）。
    """
    return {"x_tag": x_tag, "count": len(x_tag) if x_tag else 0}


# ============================================================
# 4. 必填头与 loc 命名
# ============================================================
@app.get("/secure", tags=["示例"], summary="必填 API Key 头")
def secure(
    x_api_key: Annotated[str, Header(description="调用方 API Key")],
) -> dict[str, str]:
    """没有默认值 → 必填。

    【实测】缺失时 422：
           {"type":"missing","loc":["header","x-api-key"],"msg":"Field required"}
    【注意】`loc` 里用的是**连字符形式** `x-api-key`，不是函数参数名 `x_api_key`。
           前端/日志按 `loc` 定位时要注意这个转换。
    """
    return {"key_prefix": x_api_key[:3] + "***"}


# ============================================================
# 5. 真实场景：幂等键与追踪 id
# ============================================================
_DEDUP: dict[str, str] = {}


@app.post("/orders", tags=["订单"], summary="用 Idempotency-Key 做幂等")
def create_order(
    # 【作用】幂等键放头里：body 相同、键相同的重复请求只执行一次
    idempotency_key: Annotated[str | None, Header(alias="Idempotency-Key")] = None,
    x_trace_id: Annotated[str | None, Header(alias="X-Trace-Id")] = None,
) -> dict[str, object]:
    """幂等键的典型用法（这里用内存字典演示，生产用 Redis）。

    【注意】本章在单进程内存里演示，`--workers` 多进程会失效（第 02 章 2.5）。
    【注意】`alias` 用来保留头名大小写风格；HTTP 头本身大小写不敏感，
           但文档里显示成什么样子由 alias 决定。
    """
    if idempotency_key and idempotency_key in _DEDUP:
        return {"status": "cached", "order_id": _DEDUP[idempotency_key], "trace_id": x_trace_id}

    order_id = f"ord-{len(_DEDUP) + 1}"
    if idempotency_key:
        _DEDUP[idempotency_key] = order_id
    return {"status": "created", "order_id": order_id, "trace_id": x_trace_id}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
