"""第 44 章 · 安全总览（Security / securitySchemes）。

核心：`Security(方案)` 与 `Depends(fn)` 执行方式相同，区别在**文档侧**——
      `Security` 会把方案登记进 OpenAPI 的 `components.securitySchemes`，
      并让 `/docs` 出现 Authorize 按钮；`Depends` 不登记。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Annotated, Any

from fastapi import Depends, FastAPI, HTTPException, Security, status
from fastapi.security import (
    APIKeyHeader,
    HTTPAuthorizationCredentials,
    HTTPBearer,
)

app = FastAPI(title="第 44 章 · 安全总览", version="0.1.0")

_VALID_KEYS = {"key-alice": "alice", "key-bob": "bob"}

# ============================================================
# 1. 两种方案对象：它们只负责「从请求里取出凭证」
# ============================================================
api_key_scheme = APIKeyHeader(
    name="X-API-Key",
    description="机器调用用的静态密钥",
    auto_error=True,
)

bearer_scheme = HTTPBearer(
    scheme_name="BearerAuth",
    description="用户调用用的 Bearer token",
    auto_error=True,
)


# ============================================================
# 2. `Security` 注入 + 自己校验
# ============================================================
def verify_key(key: Annotated[str, Security(api_key_scheme)]) -> str:
    """【实测】缺 `X-API-Key` 时由方案自己抛 **403**（不是 401），
           走到这里说明头存在，只可能因值不对抛 401
    """
    user = _VALID_KEYS.get(key)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="X-API-Key 无效",
            headers={"WWW-Authenticate": "ApiKey"},
        )
    return user


def verify_bearer(
    creds: Annotated[HTTPAuthorizationCredentials, Security(bearer_scheme)],
) -> str:
    """【实测】`HTTPAuthorizationCredentials` 有 `.scheme` / `.credentials` 两个字段"""
    if creds.scheme.lower() != "bearer":
        raise HTTPException(status_code=401, detail="scheme 必须是 bearer")
    if creds.credentials != "token-1":
        raise HTTPException(
            status_code=401,
            detail="token 无效",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return "alice"


# ============================================================
# 3. 端点：三种登记方式
# ============================================================
@app.get("/key", tags=["Security 注入"], summary="参数位置 Security")
def read_by_key(
    user: Annotated[str, Security(verify_key)],
) -> dict[str, str]:
    """【实测】`Security(依赖函数)` 同样能注入返回值，OpenAPI 记录底层的 scheme"""
    return {"user": user}


@app.get("/bearer", tags=["Security 注入"], summary="HTTPBearer")
def read_by_bearer(user: Annotated[str, Security(verify_bearer)]) -> dict[str, str]:
    return {"user": user}


@app.get("/either", tags=["Security 注入"], summary="默认值不跳过依赖")
def read_either(
    key_user: Annotated[str | None, Security(verify_key)] = None,
) -> dict[str, Any]:
    """【实测】给参数默认值 `= None` **不会**让依赖跳过：仍是必需，无头照样 401

    【关键】要「可以没有」必须用方案对象的 `auto_error=False`（见 `/either-or`）
    """
    return {"user": key_user}


# ============================================================
# 3.1 「或」语义：两个 auto_error=False 方案自己合并
# ============================================================
api_key_soft = APIKeyHeader(name="X-API-Key", auto_error=False)
bearer_soft = HTTPBearer(scheme_name="BearerAuth", auto_error=False)


def either_auth(
    key: Annotated[str | None, Security(api_key_soft)] = None,
    creds: Annotated[HTTPAuthorizationCredentials | None, Security(bearer_soft)] = None,
) -> str:
    """【实测】OpenAPI 里会写成 `[{"APIKeyHeader": []}, {"BearerAuth": []}]` = OR 语义

    【注意】「AND」（两个都要）OpenAPI 需写成同一个对象 `[{"a": [], "b": []}]`，
           FastAPI 不会自动这么生成，得手改 `openapi()`
    """
    if key and key in _VALID_KEYS:
        return _VALID_KEYS[key]
    if creds and creds.credentials == "token-1":
        return "alice"
    raise HTTPException(
        status_code=401,
        detail="需要 X-API-Key 或 Bearer token 之一",
        headers={"WWW-Authenticate": "Bearer"},
    )


@app.get("/either-or", tags=["Security 注入"], summary="OR 语义")
def read_either_or(user: Annotated[str, Security(either_auth)]) -> dict[str, str]:
    return {"user": user}


# ============================================================
# 4. 装饰器位置：只要校验、不要返回值
# ============================================================
@app.get(
    "/audit",
    tags=["装饰器位置"],
    summary="dependencies=[Security(...)]",
    dependencies=[Security(api_key_scheme)],
)
def audit() -> dict[str, str]:
    """【实测】`security` 字段同样出现在 OpenAPI，但端点拿不到 key 值"""
    return {"ok": "true"}


# ============================================================
# 5. 反例：用 Depends 取 header，不会进 securitySchemes
# ============================================================
from fastapi import Header  # noqa: E402


@app.get("/plain", tags=["对比"], summary="Depends + Header（无 securitySection）")
def plain(key: Annotated[str | None, Header(alias="X-API-Key")] = None) -> dict[str, Any]:
    """【实测】OpenAPI 里它只是普通 header 参数，没有 `security`，/docs 无锁图标"""
    return {"key_present": key is not None}


# ============================================================
# 6. 全局依赖里放 Security
# ============================================================
def global_guard(key: Annotated[str, Security(api_key_scheme)]) -> None:
    if key not in _VALID_KEYS:
        raise HTTPException(status_code=401, detail="全局校验失败")


probe_app = FastAPI(dependencies=[Security(global_guard)])


@probe_app.get("/g")
def g() -> dict[str, str]:
    return {"g": "1"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)