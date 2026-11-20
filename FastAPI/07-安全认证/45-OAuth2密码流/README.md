# 45 OAuth2 密码流

## 一句话结论

两个对象分工：`OAuth2PasswordRequestForm` 负责**收表单**（`username`/`password`/`grant_type`/`scope`/`client_id`/`client_secret`），`OAuth2PasswordBearer(tokenUrl="token")` 负责**收 header**（`Authorization: Bearer x`，自动剥前缀）。`/token` 必须用 `application/x-www-form-urlencoded`——实测发 JSON → 422，`loc` 为 `["body","username"]`。

五个实测细节：

1. `tokenUrl` **按原样**写进 OpenAPI（`"token"` 不带前导 `/`，客户端按当前 base 解析）。
2. 缺 token → 401 + `WWW-Authenticate: Bearer`；`Authorization: abc`（无 `Bearer ` 前缀）也是 401。
3. 表单 `scope="read write"` → `form.scopes == ["read","write"]`（空格分隔）。
4. 不传的可选字段：`grant_type=None`、`scopes=[]`、`client_id=None`。
5. 请求体 schema 是 `$ref` 到 `Body_login_token_post`，**不是内联对象**（写断言时别找 `properties`）。

## 最小可运行案例

```python
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

app = FastAPI()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")

USERS = {"alice": {"password": "alice123", "disabled": False}}


@app.post("/token")
def login(form: Annotated[OAuth2PasswordRequestForm, Depends()]) -> dict[str, str]:
    user = USERS.get(form.username)
    if user is None or user["password"] != form.password:
        raise HTTPException(400, "用户名或密码错误")      # OAuth2 规范：400，不是 401
    if user["disabled"]:
        raise HTTPException(400, "用户已停用")
    return {"access_token": f"token-for-{form.username}", "token_type": "bearer"}


@app.get("/users/me")
def me(token: Annotated[str, Depends(oauth2_scheme)]) -> dict[str, str]:
    return {"token": token}
```

依赖需要 `python-multipart`（表单解析）。

## 怎么跑

```powershell
cd "07-安全认证\45-OAuth2密码流\examples"
uv sync
uv run uvicorn main:app --reload     # /docs → Authorize 填 alice/alice123
uv run python verify.py
```

预期输出：

```text
[PASS] oauth2 方案结构 -> type=oauth2, tokenUrl='token', scopes={}
[PASS] tokenUrl 相对路径 -> tokenUrl='token'（相对路径，客户端按当前 base 解析）
[PASS] 受保护路由 security -> security=[{'OAuth2PasswordBearer': []}]
[PASS] 缺 token 401 -> 401 + WWW-Authenticate: Bearer
[PASS] 缺 Bearer 前缀 -> 缺前缀被方案层拒绝
[PASS] token 注入 -> token=abc（前缀已剥离）
[PASS] 表单登录 -> access_token=token-for-alice, token_type=bearer
[PASS] JSON 登录 422 -> 422, locs=[['body', 'username'], ['body', 'password']]
[PASS] 密码错 400 -> 400 用户名或密码错误
[PASS] 停用用户 400 -> 400 用户已停用
[PASS] 可选登录 -> 无 token → None；有 token → 't'
[PASS] scope 解析 -> scopes=['read', 'write'], grant_type=password
[PASS] 表单默认值 -> grant_type=None, scopes=[]
[PASS] token 端点是 form -> content=['application/x-www-form-urlencoded'], schema=Body_login_token_post, required=username/password
[PASS] /docs -> /docs 200

结果：15/15 通过
```

## 核心 API 速查

| 对象 | 从哪取 | 关键参数 |
| --- | --- | --- |
| `OAuth2PasswordRequestForm` | form body | — |
| `OAuth2PasswordBearer` | `Authorization: Bearer` | `tokenUrl`、`auto_error`、`scheme_name` |

| `form` 字段 | 类型 | 未传时 |
| --- | --- | --- |
| `username` | `str` | **必填**（422）|
| `password` | `str` | **必填**（422）|
| `grant_type` | `str \| None` | `None` |
| `scopes` | `list[str]` | `[]`（由 `scope` 空格分隔解析）|
| `client_id` / `client_secret` | `str \| None` | `None` |

| 实测行为 | 结果 |
| --- | --- |
| 缺 token | 401 `Not authenticated` + `WWW-Authenticate: Bearer` |
| `Authorization: abc` | 401（方案层拒绝）|
| `Bearer abc` | 注入 `"abc"`（前缀剥离）|
| JSON 打 `/token` | 422，`loc=["body","username"]` |
| 表单成功 | `{"access_token": "...", "token_type": "bearer"}` |
| 密码错 / 停用 | 我写成 400（OAuth2 规范建议）|
| OpenAPI 请求体 | 只有 `application/x-www-form-urlencoded` |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 前端发 JSON 到 `/token` | 422 | `application/x-www-form-urlencoded` |
| 响应键写成 `accessToken` | 客户端解析不到 | 必须是 `access_token` |
| 漏 `token_type` | OAuth2 客户端报错 | `"bearer"` |
| 密码错返回 401 | 前端误判为「token 过期」 | 400（OAuth2 规范）|
| `tokenUrl` 写成相对路径又部署在子路径 | Authorize 打错地址 | 明确写 `/token` 或 `../token` |
| 忘了 `python-multipart` | 启动报错/表单不可用 | 加依赖 |
| 以为 `token` 参数是 dict | 直接 `token["sub"]` 报错 | 它是裸字符串（第 46 章再解析）|
| 用 `scope` 参数名取 scopes | `form.scope` 不存在 | 是 `form.scopes` |
| 把密码写日志 | 泄露 | 脱敏 |
| 生产用密码流 + 明文比对 | 泄露/撞库 | 哈希校验（第 47 章）|

## 毕业自查

- [ ] 能写出 `/token` 与受保护端点
- [ ] 能解释表单 vs JSON 的 422 差异
- [ ] 能说出 `access_token`/`token_type` 的规范要求
- [ ] 能解释 `Authorization: abc` 为什么 401
- [ ] 能用 `auto_error=False` 做可选登录
- [ ] 动手题一：加 `expires_in` 字段并在客户端处理
- [ ] 动手题二：把密码换成 bcrypt 哈希校验

> 想看 `OAuth2PasswordRequestForm` 的字段定义、`tokenUrl` 与反代子路径、表单解析原理、18 条坑，继续读 [`base.md`](./base.md)。