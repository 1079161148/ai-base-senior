"""第 21 章 · 响应模型（response_model）。

核心：入参与出参用**不同模型**。`response_model` 决定「哪些字段能出去」，
      模型没声明的字段会被**静默丢弃**；返回类型不符合响应模型时是 500，不是 422。

启动：uvicorn main:app --reload
验收：python verify.py
"""

from decimal import Decimal
from types import SimpleNamespace
from typing import Any

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field

app = FastAPI(title="第 21 章 · 响应模型", version="0.1.0")


# ============================================================
# 1. 三个模型：入参 / 出参 / 内部
# ============================================================
class UserIn(BaseModel):
    """入参：含密码，只在请求方向存在。"""

    username: str = Field(min_length=2, max_length=20)
    password: str = Field(min_length=6)
    email: str
    nickname: str | None = None


class UserOut(BaseModel):
    """出参：**没有** password / hashed_password。

    【作用】这是唯一决定「客户端能看到什么」的地方
    【注意】漏写字段是安全的（不会泄露），多写字段才会泄露
    """

    username: str
    email: str
    nickname: str | None = None


class UserInDB(UserIn):
    """内部模型：比 UserIn 多存了哈希与内部备注。"""

    hashed_password: str
    internal_note: str = ""


class PartialOut(BaseModel):
    """可选字段版本：用于演示 `response_model_exclude_unset`。

    【为什么】`exclude_unset` 只影响**输出**，不影响**校验**：
               用必填的 `UserOut` 返回 `{"username": ...}` 会 500（实测）
    """

    username: str
    email: str | None = None
    nickname: str | None = None


class OrderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)  # 允许从对象属性读取

    id: int
    amount: Decimal
    note: str | None = None


_USERS: dict[int, UserInDB] = {}


# ============================================================
# 2. response_model 的四种用法
# ============================================================
@app.post("/users", response_model=UserOut, tags=["用户"], summary="创建用户")
def create_user(user: UserIn) -> Any:
    """【作用】返回的 dict 里故意多带 hashed_password / internal_note

    【实测】响应里只剩 `username` / `email` / `nickname`
           —— 响应模型是白名单，多余字段静默丢弃
    """
    user_id = len(_USERS) + 1
    _USERS[user_id] = UserInDB(
        **user.model_dump(),
        hashed_password="sha256:fake",
        internal_note="仅内部可见",
    )
    return {**_USERS[user_id].model_dump(), "id": user_id, "debug": "不该出现"}


@app.get("/users/{user_id}", response_model=UserOut, tags=["用户"], summary="读取用户")
def get_user(user_id: int) -> Any:
    if user_id not in _USERS:
        from fastapi import HTTPException

        raise HTTPException(status_code=404, detail="用户不存在")
    return _USERS[user_id]


@app.get(
    "/users/{user_id}/slim",
    response_model=UserOut,
    response_model_exclude={"email"},
    tags=["用户"],
    summary="排除某个字段",
)
def get_user_slim(user_id: int) -> Any:
    """【作用】`response_model_exclude` 在响应模型基础上再排除字段"""
    return _USERS[user_id]


@app.get(
    "/users/{user_id}/partial",
    response_model=PartialOut,
    response_model_exclude_unset=True,
    tags=["用户"],
    summary="只输出有值的字段",
)
def get_user_partial(user_id: int) -> Any:
    """【作用】`response_model_exclude_unset=True`：没被赋值过的字段不输出

    【实测】返回 `{"username": "a"}` 时，响应里**只有** username
    【关键】`exclude_unset` 不改变校验：模型里 email 若必填，缺了照样 500
    【注意】它对「返回值是 dict」同样生效，不只是模型实例
    """
    return {"username": _USERS[user_id].username}


@app.get(
    "/users/{user_id}/force-strict",
    response_model=UserOut,
    response_model_exclude_unset=True,
    tags=["反例"],
    summary="exclude_unset 不能免除校验",
)
def force_strict(user_id: int) -> Any:
    """【实测】`UserOut` 的 email 是必填，这里只返回 username → 500

    【结论】`response_model_exclude_unset` 只影响输出，不影响校验
    """
    return {"username": _USERS[user_id].username}


@app.get("/users", response_model=list[UserOut], tags=["用户"], summary="列表响应")
def list_users() -> Any:
    """【实测】`list[UserOut]` 逐元素过滤，元素同样只留白名单字段"""
    return list(_USERS.values())


# ============================================================
# 3. 参数与返回注解的优先级
# ============================================================
class TinyOut(BaseModel):
    username: str


@app.get("/users/{user_id}/priority", response_model=TinyOut, tags=["用户"], summary="参数优先")
def priority(user_id: int) -> UserOut:
    """【作用】函数返回注解是 `UserOut`，但 `response_model=TinyOut` 覆盖它

    【实测】响应只有 `{"username": ...}` —— **参数优先于返回注解**
    """
    return _USERS[user_id]


# ============================================================
# 4. from_attributes：从任意对象读字段（ORM 场景）
# ============================================================
@app.get("/orders/{order_id}", response_model=OrderOut, tags=["订单"], summary="从对象读取")
def get_order(order_id: int) -> Any:
    """【作用】返回普通对象（不是 dict、不是模型），靠 `from_attributes=True` 读取属性

    【实测】SimpleNamespace(id=1, amount=Decimal("19.90"), note=None) → 正常序列化
    【注意】`amount` 是 Decimal，响应里输出为字符串 "19.90"
    """
    return SimpleNamespace(id=order_id, amount=Decimal("19.90"), note=None, secret_token="不该出现")


# ============================================================
# 5. 反例：响应模型校验失败 → 500
# ============================================================
class StrictOut(BaseModel):
    count: int


@app.get("/broken", response_model=StrictOut, tags=["反例"], summary="响应模型校验失败")
def broken() -> Any:
    """【实测】返回 {"count": "abc"} → 500 Internal Server Error（ResponseValidationError）

    【为什么】响应模型校验失败是**服务端 bug**，不是客户端参数问题，所以不是 422
    """
    return {"count": "abc"}


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="127.0.0.1", port=8000)
