"""第 31 章 · HTTPException。

核心：业务上「可预期」的失败用 `HTTPException` 抛出，框架转成
      `{"detail": ...}` + 指定状态码；`detail` 可以是任意可 JSON 化结构。
      `headers` 用来带 `WWW-Authenticate`、`Retry-After` 等协议头。
      不可预期的异常不要捕获成 500 手写——交给兜底处理器（第 34 章）。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Annotated, Any

from fastapi import BackgroundTasks, Depends, FastAPI, Header, HTTPException, status

app = FastAPI(title="第 31 章 · HTTPException", version="0.1.0")

_ITEMS: dict[int, dict[str, Any]] = {1: {"id": 1, "name": "机械键盘", "price": 399}}
_TOKENS: dict[str, str] = {"valid-token": "alice"}
_LOGIN_ATTEMPTS: dict[str, int] = {}


# ============================================================
# 1. 最常见的 404
# ============================================================
@app.get("/items/{item_id}", tags=["HTTPException"], summary="资源不存在")
def get_item(item_id: int) -> dict[str, Any]:
    """【作用】`raise HTTPException(404, detail=...)` 立即中断并返回错误

    【实测】响应体是 `{"detail": "item 99 不存在"}`，状态码 404
    【注意】`detail` 不要泄露内部路径、SQL、堆栈
    """
    item = _ITEMS.get(item_id)
    if item is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"item {item_id} 不存在",
        )
    return item


# ============================================================
# 2. detail 可以是结构化数据
# ============================================================
@app.get("/items/{item_id}/structured", tags=["HTTPException"], summary="结构化 detail")
def get_item_structured(item_id: int) -> dict[str, Any]:
    """【作用】`detail` 可以是 dict/list，客户端能按字段处理

    【实测】返回 `{"detail": {"reason": "not_found", "item_id": 99}}`
    【注意】结构一旦对外就是契约，改动要版本化；第 34 章统一契约会把它换掉
    """
    if item_id not in _ITEMS:
        raise HTTPException(
            status_code=404,
            detail={"reason": "not_found", "item_id": item_id, "hint": "GET /items 查看可用 ID"},
        )
    return _ITEMS[item_id]


# ============================================================
# 3. 401 必须带 WWW-Authenticate
# ============================================================
@app.get("/me", tags=["HTTPException"], summary="401 与协议头")
def read_me(
    authorization: Annotated[str | None, Header(description="Bearer token")] = None,
) -> dict[str, str]:
    """【作用】401 用 `headers={"WWW-Authenticate": "Bearer"}` 告诉客户端怎么认证

    【实测】缺凭据 → 401 + `www-authenticate: Bearer`
    【注意】`headers` 的值必须是 latin-1 可编码字符，写中文会 500（实测）
    """
    if not authorization:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="缺少凭据",
            headers={"WWW-Authenticate": "Bearer"},
        )
    user = _TOKENS.get(authorization)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="凭据无效",
            headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
        )
    return {"user": user}


# ============================================================
# 4. 409 / 429：冲突与限流
# ============================================================
@app.post("/items", status_code=201, tags=["HTTPException"], summary="名称冲突 409")
def create_item(name: str) -> dict[str, Any]:
    """【作用】409 表示「请求合法但与当前状态冲突」

    【实测】重复名称 → 409 `{"detail": "名称已存在: 机械键盘"}`
    """
    if any(item["name"] == name for item in _ITEMS.values()):
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=f"名称已存在: {name}")
    new_id = max(_ITEMS, default=0) + 1
    _ITEMS[new_id] = {"id": new_id, "name": name, "price": 0}
    return _ITEMS[new_id]


@app.post("/login", tags=["HTTPException"], summary="限流 429")
def login(username: str) -> dict[str, str]:
    """【作用】429 配 `Retry-After` 告诉客户端多久后可重试

    【实测】同一用户第 3 次失败 → 429 + `retry-after: 30`
    """
    attempts = _LOGIN_ATTEMPTS.get(username, 0) + 1
    _LOGIN_ATTEMPTS[username] = attempts
    if attempts >= 3:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="尝试过于频繁，请稍后再试",
            headers={"Retry-After": "30"},
        )
    return {"username": username, "attempt": str(attempts)}


# ============================================================
# 5. 在依赖里抛：整条链路一起失败
# ============================================================
def require_token(
    token: Annotated[str | None, Header(alias="X-Token")] = None,
) -> str:
    """【作用】依赖里抛 `HTTPException`，路由函数不会被调用

    【实测】缺 `X-Token` → 401，响应体来自依赖，不是路由
    """
    if token not in _TOKENS:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-Token 无效",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return token


@app.get("/secure/items", tags=["HTTPException"], summary="依赖里抛 401")
def secure_items(token: Annotated[str, Depends(require_token)]) -> dict[str, str]:
    return {"user": _TOKENS[token]}


# ============================================================
# 6. 不可预期异常：不要包装成 HTTPException
# ============================================================
@app.get("/boom", tags=["反例"], summary="未捕获异常 → 500")
def boom() -> dict[str, str]:
    """【作用】非 `HTTPException` 的异常由服务器兜底成 500

    【实测】`TestClient(raise_server_exceptions=False)` 下状态码 500，body 只有 `Internal Server Error`
    【注意】不要把 `ZeroDivisionError` 之类捕获后 `raise HTTPException(500, str(e))`：
           泄露内部信息，还丢了日志与 trace
    """
    raise ValueError("数据库连接串写错了之类的内部错误")


# ============================================================
# 7. 后台任务里抛 HTTPException：不会变成 404
# ============================================================
def _fail_in_background() -> None:
    raise HTTPException(status_code=404, detail="后台任务里的 404")


@app.post("/background", tags=["反例"], summary="后台任务抛 HTTPException")
def background_fail(background_tasks: BackgroundTasks) -> dict[str, str]:
    """【实测】响应已经发出，后台任务里抛 `HTTPException` → 连接异常/500，不会变成 404

    【结论】`HTTPException` 只在「请求-响应」阶段有效，后台任务里必须自己记日志
    """
    background_tasks.add_task(_fail_in_background)
    return {"scheduled": "true"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)