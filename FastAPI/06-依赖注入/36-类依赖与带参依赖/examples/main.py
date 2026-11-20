"""第 36 章 · 类依赖与带参依赖。

核心：依赖不必是函数。凡是「可调用对象」都行：
      1. 类 `Depends(Cls)` → 框架解析 `__init__` 签名并构造实例；
      2. 实例 `Depends(obj)` → 框架调用 `obj.__call__`；
      3. 工厂 `Depends(make_dep(x))` → 用闭包把配置「焊死」，不再出现在 OpenAPI。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Annotated, Any

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, status

app = FastAPI(title="第 36 章 · 类依赖与带参依赖", version="0.1.0")

_ITEMS = [{"id": i, "name": f"商品 {i}"} for i in range(1, 21)]


# ============================================================
# 1. 类依赖：__init__ 的参数就是查询参数
# ============================================================
class CommonQueryParams:
    """【作用】把分页参数装进对象，端点里用属性访问

    【实测】`Depends(CommonQueryParams)` 或 `Annotated[Cls, Depends()]`
           都会把 `__init__` 的 q/skip/limit 变成 query 参数
    """

    def __init__(
        self,
        q: Annotated[str | None, Query(max_length=50, description="搜索词")] = None,
        skip: Annotated[int, Query(ge=0, description="跳过条数")] = 0,
        limit: Annotated[int, Query(ge=1, le=100, description="每页条数")] = 10,
    ) -> None:
        self.q = q
        self.skip = skip
        self.limit = limit


@app.get("/items", tags=["类依赖"], summary="类作依赖")
def list_items(commons: Annotated[CommonQueryParams, Depends()]) -> dict[str, Any]:
    """【实测】不传参 → `limit=10`；传 `limit=200` → 422"""
    data = _ITEMS[commons.skip : commons.skip + commons.limit]
    return {"q": commons.q, "count": len(data), "ids": [item["id"] for item in data]}


# ============================================================
# 2. 实例作依赖：调用 __call__，__init__ 参数被「焊死」
# ============================================================
class FixedPage:
    """带固定配置的分页器。"""

    def __init__(self, size: int) -> None:
        self.size = size

    def __call__(self) -> dict[str, int]:
        return {"size": self.size}


FIXED_SMALL = FixedPage(3)


@app.get("/fixed/small", tags=["实例依赖"], summary="实例作依赖（无参数）")
def fixed_small(page: Annotated[dict[str, int], Depends(FIXED_SMALL)]) -> dict[str, int]:
    """【实测】`Depends(实例)` 只调 `__call__`：`size` 固定 3，OpenAPI 里**没有** size 参数"""
    return page


class ConfigurablePage:
    """类作依赖时，`__init__` 的参数会成为查询参数。"""

    def __init__(self, size: Annotated[int, Query(ge=1, le=50)] = 10) -> None:
        self.size = size

    def __call__(self) -> dict[str, int]:
        return {"size": self.size}


@app.get("/fixed/class", tags=["实例依赖"], summary="类作依赖（__init__ 参数可配）")
def fixed_class(page: Annotated[ConfigurablePage, Depends(ConfigurablePage)]) -> dict[str, int]:
    """【实测】`Depends(类)` 返回**实例**（不自动调 `__call__`）：
           参数注解写 `dict` 会因返回对象而 500（ResponseValidationError）

    【关键】`Depends(Cls)` → 构造实例；`Depends(obj)` → 调 `obj.__call__()`
    """
    return {"size": page.size}


# ============================================================
# 3. __call__ 里做副作用：限流器
# ============================================================
class RateLimiter:
    """按客户端 IP 计数的简易限流器。

    【注意】计数存在实例里，多进程部署时每个 worker 各一份 —— 生产要用 Redis。
    """

    def __init__(self, times: int = 2, seconds: int = 60) -> None:
        self.times = times
        self.seconds = seconds
        self.calls: dict[str, int] = {}

    def __call__(self, request: Request) -> None:
        key = request.client.host if request.client else "unknown"
        count = self.calls.get(key, 0) + 1
        self.calls[key] = count
        if count > self.times:
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail=f"超过 {self.times} 次/{self.seconds}s 限制",
                headers={"Retry-After": str(self.seconds)},
            )

    def reset(self) -> None:
        self.calls.clear()


limiter = RateLimiter(times=2, seconds=60)


@app.get("/limited", tags=["类依赖"], summary="限流器（__call__）")
def limited(_: Annotated[None, Depends(limiter)]) -> dict[str, str]:
    """【实测】第 3 次请求 → 429 + `Retry-After: 60`；`__call__` 的参数 `request` 不出现"""
    return {"ok": "true"}


# ============================================================
# 4. 带参依赖工厂：把配置焊进闭包
# ============================================================
def require_header(name: str, expected: str = "ok") -> Any:
    """【作用】`Depends(require_header("X-Api-Key"))` 生成一个专用依赖

    【实测】每个端点只出现自己那个头的参数，配置值不出现在 OpenAPI 里
    """

    def dependency(
        value: Annotated[str | None, Header(alias=name)] = None,
    ) -> str:
        if value != expected:
            raise HTTPException(status_code=400, detail=f"{name} 缺失或错误")
        return value

    return dependency


@app.get("/factory/a", tags=["工厂依赖"], summary="工厂依赖 A")
def factory_a(key: Annotated[str, Depends(require_header("X-Api-Key"))]) -> dict[str, str]:
    return {"key": key}


@app.get("/factory/b", tags=["工厂依赖"], summary="工厂依赖 B")
def factory_b(token: Annotated[str, Depends(require_header("X-Admin-Token", "admin"))]) -> dict[str, str]:
    return {"token": token}


# ============================================================
# 5. 类依赖也能组合别的依赖
# ============================================================
class CurrentPage:
    """【作用】类依赖里再声明一个依赖，构成依赖链（第 37 章展开）"""

    def __init__(self, page: Annotated[int, Query(ge=1, le=10)] = 1) -> None:
        self.page = page


def make_slice(max_size: int) -> Any:
    def dep(commons: Annotated[CommonQueryParams, Depends()]) -> dict[str, Any]:
        size = min(commons.limit, max_size)
        return {"start": commons.skip, "size": size, "page": commons.skip // size + 1}

    return dep


@app.get("/pages", tags=["工厂依赖"], summary="工厂 + 类依赖组合")
def pages(
    slice_: Annotated[dict[str, Any], Depends(make_slice(max_size=5))],
) -> dict[str, Any]:
    """【实测】`limit=100` 被截到 5（`max_size`），说明工厂配置生效"""
    return slice_


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)