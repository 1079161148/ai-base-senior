# 46 获取当前用户

## 一句话结论

token 只是字符串，要换成用户对象得自己写依赖链：`oauth2_scheme`（取 token）→ `get_current_user`（查用户，失败 401）→ `get_current_active_user`（判停用，失败 400）。实测这条链在**同一请求内各执行一次**（`CALLS == ["get_current_user", "get_current_active_user"]`），两次请求变四条（缓存不跨请求）。

四个实测要点：

1. 无 token 401 `Not authenticated`；token 查不到 401 `无效的 token` + `WWW-Authenticate: Bearer error="invalid_token"`（**不是 404**，避免暴露用户是否存在）。
2. 停用用户 400 `Inactive user`（官方示例约定；也可 403，但要与前端统一）。
3. **内部 `User` 模型不会进 `components.schemas`**，schema 里只有 `UserOut`——`response_model` 决定对外契约。
4. 不加 `response_model` 直接 `model_dump()`，`hashed_password` 就在里面（实测字段列表含它）。

## 最小可运行案例

```python
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


class User(BaseModel):
    username: str
    email: str
    full_name: str | None = None
    hashed_password: str
    disabled: bool = False


class UserOut(BaseModel):
    username: str
    email: str
    full_name: str | None = None


TOKENS = {"token-alice": "alice"}
DB = {"alice": User(username="alice", email="a@x.com", hashed_password="h", disabled=False)}


def unauthorized(detail: str) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail=detail,
        headers={"WWW-Authenticate": 'Bearer error="invalid_token"'},
    )


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]) -> User:
    username = TOKENS.get(token)
    if username is None:
        raise unauthorized("无效的 token")
    return DB[username]


async def get_current_active_user(user: Annotated[User, Depends(get_current_user)]) -> User:
    if user.disabled:
        raise HTTPException(status_code=400, detail="Inactive user")
    return user


@app.get("/users/me", response_model=UserOut)
async def me(user: Annotated[User, Depends(get_current_active_user)]):
    return user
```

完整版本（登录、可选用户、反例对比）见 `examples/main.py`。

## 怎么跑

```powershell
cd "07-安全认证\46-获取当前用户\examples"
uv sync
uv run uvicorn main:app --reload     # /docs → Authorize: alice / alice123
uv run python verify.py
```

预期输出：

```text
[PASS] 登录发 token -> access_token=token-alice
[PASS] 当前用户 -> keys=['email', 'full_name', 'username']
[PASS] 缺 token 401 -> 401 Not authenticated
[PASS] 无效 token 401 -> 401 无效的 token（不暴露用户是否存在）
[PASS] 停用用户 400 -> 400 Inactive user
[PASS] 密码错 400 -> 两种失败同文案（防枚举）
[PASS] 依赖链缓存 -> calls=['get_current_user', 'get_current_active_user']
[PASS] response_model 过滤 -> dumped_fields=['disabled', 'email', 'full_name', 'hashed_password', 'username']（反例：必须用 response_model）
[PASS] 内部模型不进 schema -> schemas=['Body_login_token_post', 'HTTPValidationError', 'Token', 'UserOut', 'ValidationError']
[PASS] security 引用 -> security=[{'OAuth2PasswordBearer': []}]
[PASS] 可选用户 -> 匿名→游客；登录→Alice Chen
[PASS] 缓存不跨请求 -> CALLS=[...]（两次请求各一次）

结果：12/12 通过
```

## 核心 API 速查

| 层 | 函数 | 失败 |
| --- | --- | --- |
| 取 token | `oauth2_scheme` | 401 `Not authenticated` |
| token→用户 | `get_current_user` | 401 `无效的 token` |
| 判停用 | `get_current_active_user` | 400 `Inactive user` |

| 模型 | 用途 | 含 `hashed_password` |
| --- | --- | --- |
| `User` | 内部 | 是 |
| `UserOut` | 对外 | 否 |
| `Token` | `/token` 响应 | — |

| 实测行为 | 结果 |
| --- | --- |
| 有效 token | 200，只 3 个字段 |
| 无效 token | 401 + `error="invalid_token"` |
| 停用账号 | 400 `Inactive user` |
| 用户不存在 / 密码错 | 同一 400 文案 |
| 依赖链 | 同请求各 1 次 |
| `components.schemas` | 只有 `UserOut`，无 `User` |
| 可选登录 | 匿名→游客，登录→名字 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| token 无效返回 404 | 暴露用户存在性 | 401 |
| 停用返回 401 | 前端反复重登 | 400 或 403 |
| 直接返回 `User` 模型 | 泄露 `hashed_password` | `response_model=UserOut` |
| 用户名不存在单独文案 | 账号枚举 | 与密码错同文案 |
| 401 不带 `WWW-Authenticate` | 客户端无指引 | 加头 |
| 依赖里 `print` 密码 | 泄露 | 只记用户 id |
| 把用户信息全塞 token | token 变大且可伪造 | 只放 `sub`（第 47 章）|
| `get_current_user` 里再 `Depends(oauth2_scheme)` 两次 | 不必要 | 复用缓存 |
| 用 `dict` 当用户对象 | 拼错字段名不报错 | 用 `BaseModel` |
| `EmailStr` 忘了 `email-validator` | 启动报错 | 加依赖 |

## 毕业自查

- [ ] 能写出两级依赖链
- [ ] 能说出 401/400 的分工
- [ ] 能解释为什么 token 无效不用 404
- [ ] 能证明 `response_model` 过滤了哈希
- [ ] 能指出 `User` 不进 schema 这件事
- [ ] 动手题一：加 `require_admin` 依赖（角色来自 `User`）
- [ ] 动手题二：把 `_TOKENS` 换成 JWT 解码（第 47 章）

> 想看依赖链的缓存与覆盖、`CurrentUser` 别名的组织方式、防枚举的完整错误码表、18 条坑，继续读 [`base.md`](./base.md)。