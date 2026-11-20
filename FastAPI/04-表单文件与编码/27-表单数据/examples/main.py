"""第 27 章 · 表单数据（Form）。

核心：表单（`application/x-www-form-urlencoded` 或 `multipart/form-data`）不是 JSON。
      用 `Form()` 声明字段，FastAPI 会自动从表单体里取值并做类型转换与校验。
      代价：必须装 `python-multipart`，且**不能**与 JSON 请求体模型同时声明。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from typing import Annotated, Any

from fastapi import FastAPI, Form, Query

app = FastAPI(title="第 27 章 · 表单数据", version="0.1.0")

_USERS: dict[str, str] = {"alice": "secret123"}


# ============================================================
# 1. 最常用的表单登录
# ============================================================
@app.post("/login", tags=["表单"], summary="表单登录")
def login(
    username: Annotated[
        str, Form(min_length=3, max_length=20, description="用户名", examples=["alice"])
    ],
    password: Annotated[str, Form(min_length=6, description="密码")],
    remember: Annotated[bool, Form(description="记住我")] = False,
) -> dict[str, Any]:
    """【作用】三个参数都来自表单体，`remember` 有默认值所以可选

    【实测】`data={"username": "alice", ...}` 以 `application/x-www-form-urlencoded` 发送
    【实测】缺 `remember` 时取默认值 False，不报 422
    【注意】`Form()` 里的约束（min_length 等）与 `Query()` 完全一致
    """
    ok = _USERS.get(username) == password
    return {"username": username, "authenticated": ok, "remember": remember}


# ============================================================
# 2. 表单字段的类型转换与约束
# ============================================================
@app.post("/signup", tags=["表单"], summary="带数字与范围校验")
def signup(
    username: Annotated[str, Form(min_length=3)],
    age: Annotated[int, Form(ge=18, le=120, description="年龄")],
    score: Annotated[float, Form(ge=0, le=100)] = 60.0,
) -> dict[str, Any]:
    """【实测】表单值以字符串到达，`age="30"` 会被转成 int 30

    【实测】`age="abc"` → 422，`type` 是 `int_parsing`
    【注意】转换失败与校验失败都是 422，但 `type` 不同（第 33 章细讲）
    """
    return {"username": username, "age": age, "score": score}


# ============================================================
# 3. 别名：表单字段名与参数名不一致
# ============================================================
@app.post("/signup/alias", tags=["表单"], summary="字段别名")
def signup_alias(
    username: Annotated[str, Form(alias="user-name", min_length=3)],
) -> dict[str, str]:
    """【作用】`alias="user-name"` 让表单里用连字符字段名，Python 侧仍是合法标识符

    【实测】表单字段必须叫 `user-name`；传 `username` 会被当成缺字段 → 422
    【注意】响应用的是参数名（`username`），别把内部名和外部名搞混
    """
    return {"username": username}


# ============================================================
# 4. Form 与 Query 混用
# ============================================================
@app.post("/search", tags=["表单"], summary="表单 + 查询参数")
def search(
    keyword: Annotated[str, Form(min_length=1, description="搜索词（表单体）")],
    page: Annotated[int, Query(ge=1, description="页码（URL 查询串）")] = 1,
) -> dict[str, Any]:
    """【作用】`Form` 取请求体，`Query` 取 URL 查询串，两者可以同时出现

    【实测】`POST /search?page=2` + 表单 `keyword=键盘` 都能取到
    【注意】别把该放查询串的字段（分页）塞进表单，URL 里看不到不利于排障
    """
    return {"keyword": keyword, "page": page}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)