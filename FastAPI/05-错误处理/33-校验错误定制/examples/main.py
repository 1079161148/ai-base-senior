"""第 33 章 · 校验错误定制（RequestValidationError）。

核心：参数校验失败时框架抛 `RequestValidationError`，默认输出 422 +
      `{"detail": [{type, loc, msg, input, url}]}`。这套结构对机器友好、对人难读。
      用 `@app.exception_handler(RequestValidationError)` 接管，翻译成字段级结构。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Annotated, Any

from fastapi import FastAPI, Path, Query, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field

app = FastAPI(title="第 33 章 · 校验错误定制", version="0.1.0")

# 【作用】把 Pydantic 的 `type` 翻成中文；未收录的退回原始 msg
_TYPE_MESSAGES: dict[str, str] = {
    "missing": "必填字段缺失",
    "string_too_short": "长度不足",
    "string_too_long": "长度超出",
    "greater_than_equal": "数值太小",
    "less_than_equal": "数值太大",
    "int_parsing": "必须是整数",
    "float_parsing": "必须是数字",
    "bool_parsing": "必须是布尔值",
    "json_invalid": "请求体不是合法 JSON",
    "string_pattern_mismatch": "格式不符合要求",
    "model_attributes_type": "需要对象结构",
}


def _translate(error: dict[str, Any]) -> str:
    """把单条错误翻成「可给用户看」的句子。"""
    base = _TYPE_MESSAGES.get(error["type"], error["msg"])
    ctx = error.get("ctx") or {}
    if error["type"] == "greater_than_equal" and "ge" in ctx:
        return f"{base}（最小 {ctx['ge']}）"
    if error["type"] == "less_than_equal" and "le" in ctx:
        return f"{base}（最大 {ctx['le']}）"
    if error["type"] == "string_too_short" and "min_length" in ctx:
        return f"{base}（至少 {ctx['min_length']} 个字符）"
    if error["type"] == "string_too_long" and "max_length" in ctx:
        return f"{base}（最多 {ctx['max_length']} 个字符）"
    return base


def _field_path(loc: tuple[Any, ...]) -> str:
    """`("body", "addr", "city")` → `addr.city`；去掉来源前缀。

    【为什么】`body`/`query`/`path` 是框架加的来源标记，前端只关心字段名；
               但同一字段可能来自不同来源，所以另存 `source` 字段。
    """
    parts = [str(item) for item in loc]
    if parts and parts[0] in {"body", "query", "path", "header", "cookie"}:
        return ".".join(parts[1:]) or parts[0]
    return ".".join(parts)


def _source(loc: tuple[Any, ...]) -> str:
    return loc[0] if loc and loc[0] in {"body", "query", "path", "header", "cookie"} else "unknown"


# ============================================================
# 1. 自定义校验错误处理器
# ============================================================
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """【作用】把 422 改成 `{code, message, errors: [{field, source, message, type}]}`

    【实测】缺必填字段 → 422，`errors[0].field == "username"`，`source == "body"`
    【注意】状态码仍是 422；改成 400 也可以，但要全站统一
    """
    errors = []
    for error in exc.errors():
        loc = tuple(error["loc"])
        errors.append(
            {
                "field": _field_path(loc),
                "source": _source(loc),
                "message": _translate(error),
                "type": error["type"],
            }
        )
    return JSONResponse(
        status_code=422,
        content={
            "code": "VALIDATION_ERROR",
            "message": "请求参数校验失败",
            "errors": errors,
            "path": request.url.path,
        },
    )


# ============================================================
# 2. 被校验的端点
# ============================================================
class Address(BaseModel):
    city: Annotated[str, Field(min_length=2, max_length=20)]
    zipcode: Annotated[str, Field(pattern=r"^\d{6}$")]


class UserIn(BaseModel):
    username: Annotated[str, Field(min_length=3, max_length=20)]
    age: Annotated[int, Field(ge=18, le=120)]
    email: Annotated[str, Field(pattern=r"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
    address: Address


@app.post("/users", tags=["校验"], summary="创建用户（body 校验）")
def create_user(user: UserIn) -> dict[str, Any]:
    """【实测】`age=10` → `errors[0]` 是 `{"field": "age", "message": "数值太小（最小 18）"}`"""
    return {"username": user.username, "city": user.address.city}


@app.get("/search", tags=["校验"], summary="查询参数校验")
def search(
    q: Annotated[str, Query(min_length=2, max_length=10, description="搜索词")],
    page: Annotated[int, Query(ge=1, le=100)] = 1,
) -> dict[str, Any]:
    """【实测】`q` 太短 → `source == "query"`，`field == "q"`"""
    return {"q": q, "page": page}


@app.get("/items/{item_id}", tags=["校验"], summary="路径参数校验")
def get_item(item_id: Annotated[int, Path(ge=1, le=999)]) -> dict[str, int]:
    """【实测】`/items/0` → `source == "path"`，`field == "item_id"`"""
    return {"item_id": item_id}


@app.post("/nested", tags=["校验"], summary="多字段同时出错")
def nested(address: Address, tags: Annotated[list[str], Query(max_length=2)] = []) -> dict[str, Any]:
    """【实测】city 太短 + zipcode 格式错 → `errors` 有 2 条"""
    return {"city": address.city, "tags": tags}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)