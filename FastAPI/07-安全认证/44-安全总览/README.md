# 44 安全总览（Security / securitySchemes）

## 一句话结论

`Security(方案)` 与 `Depends(fn)` 的**执行方式完全一样**，区别只在文档侧：`Security` 会把方案登记进 `components.securitySchemes`，路由上出现 `security` 字段，`/docs` 出现 Authorize 按钮；`Depends` + `Header` 只是个普通 header 参数（实测 `/plain` 的 `security` 为 `None`）。

三条最容易记错的实测结论：

1. **缺凭证返回 401**（`{"detail":"Not authenticated"}`），不是 403——网上大量旧文章写 403。
2. `securitySchemes` 的键名来自 `scheme_name`，不传就用类名（`APIKeyHeader`）。实测传 `scheme_name="BearerAuth"` 后键名变成 `BearerAuth`，`HTTPBearer` 不再出现。
3. **多个 `Security` 生成 OR 语义**：`[{"APIKeyHeader": []}, {"BearerAuth": []}]`，任一满足即可；AND 需要手改 OpenAPI（未实测）。

## 最小可运行案例

```python
from typing import Annotated

from fastapi import FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader

app = FastAPI()
api_key_scheme = APIKeyHeader(name="X-API-Key", description="机器调用密钥")

VALID = {"key-alice": "alice"}


def verify_key(key: Annotated[str, Security(api_key_scheme)]) -> str:
    user = VALID.get(key)
    if user is None:
        raise HTTPException(401, "X-API-Key 无效", headers={"WWW-Authenticate": "ApiKey"})
    return user


@app.get("/me")
def me(user: Annotated[str, Security(verify_key)]) -> dict[str, str]:
    return {"user": user}
```

`/docs` 里会出现 Authorize 按钮，`openapi.json` 里 `components.securitySchemes.APIKeyHeader = {"type": "apiKey", "in": "header", "name": "X-API-Key"}`。

完整版本（HTTPBearer、装饰器位置、OR 语义、全局 Security）见 `examples/main.py`。

## 怎么跑

```powershell
cd "07-安全认证\44-安全总览\examples"
uv run uvicorn main:app --reload     # 打开 http://127.0.0.1:8000/docs
uv run python verify.py
```

预期输出：

```text
[PASS] securitySchemes -> schemes=['APIKeyHeader', 'BearerAuth']
[PASS] scheme_name -> scheme_name=BearerAuth（非默认类名）
[PASS] 路由 security -> /key → APIKeyHeader, /bearer → BearerAuth
[PASS] 装饰器位置 -> dependencies=[Security(...)] 也登记
[PASS] Depends 不登记 -> 只是普通 header 参数，无 security、无锁图标
[PASS] 缺 key 401 -> 401 Not authenticated（纠正「403」的旧印象）
[PASS] 缺 bearer 401 -> 401 Not authenticated
[PASS] 错 scheme -> scheme 不符 → 方案层直接 401
[PASS] 正确 key -> user=alice
[PASS] 错 key -> 401 + WWW-Authenticate: ApiKey
[PASS] OR 语义 -> security=[{APIKeyHeader},{BearerAuth}]，任一满足即可
[PASS] 默认值不跳过 -> 默认值不跳过依赖
[PASS] 全局 Security -> 全局依赖也进 security
[PASS] /docs -> /docs 200，含 swagger-ui

结果：14/14 通过
```

## 核心 API 速查

| 方案对象 | 从哪取 | OpenAPI `type` |
| --- | --- | --- |
| `APIKeyHeader(name="X-API-Key")` | header | `apiKey` |
| `APIKeyQuery(name="key")` | query | `apiKey` |
| `APIKeyCookie(name="session")` | cookie | `apiKey` |
| `HTTPBearer()` | `Authorization: Bearer x` | `http` + `scheme: bearer` |
| `HTTPBasic()` | `Authorization: Basic x` | `http` + `scheme: basic` |
| `OAuth2PasswordBearer(tokenUrl=...)` | `Authorization: Bearer x` | `oauth2`（第 45 章）|

| 写法 | 登记 security | 能拿返回值 |
| --- | --- | --- |
| `key: Annotated[str, Security(scheme)]` | 是 | 是（凭证字符串）|
| `dependencies=[Security(scheme)]` | 是 | 否 |
| `key: Annotated[str \| None, Header(alias=...)]` | **否** | 是 |
| `Depends(verify_key)` | 否（但子依赖里的 `Security` 仍会登记）| 是 |

| 实测行为 | 结果 |
| --- | --- |
| 缺 `X-API-Key`（`auto_error=True`）| 401 `Not authenticated` |
| 缺 `Authorization` | 401 `Not authenticated` |
| `Authorization: Basic xxx` 打到 bearer 端点 | 401，自定义函数**未被调用** |
| `scheme_name` | 决定 `securitySchemes` 键名 |
| 两个 `Security` | `[{"a":[]},{"b":[]}]` = OR |
| 参数默认值 `= None` | **不会**让依赖可选，无头仍 401 |
| 全局 `FastAPI(dependencies=[Security(...)])` | 同样登记到 securitySchemes |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 以为缺凭证是 403 | 断言写错、客户端处理错 | 实测 401 |
| 用 `Depends` + `Header` 想有锁图标 | 文档里没有 security | 用 `Security` |
| 参数写 `= None` 以为可选 | 仍 401 | 方案对象 `auto_error=False` |
| 以为多个 `Security` 是 AND | 实际 OR，任一即可 | 要 AND 手改 OpenAPI |
| 不传 `scheme_name` 后又改类名 | 键名漂移，客户端配置失效 | 显式命名 |
| 在方案对象上做业务校验 | 方案只取凭证 | 另写依赖函数 |
| 401 不带 `WWW-Authenticate` | 客户端不知道用什么认证 | 加头 |
| 把 token 塞进 query（`APIKeyQuery`）| 进日志/浏览器历史 | 优先 header |
| 方案名与前端约定不一致 | Authorize 填错位置 | 文档里写清 |
| 用 OR 方案却只测一种 | 另一条路径没覆盖 | 两条都测 |

## 毕业自查

- [ ] 能说出 `Security` 与 `Depends` 的唯一差别
- [ ] 能解释 `securitySchemes` 的键名来源
- [ ] 能实测出缺凭证是 401 而不是 403
- [ ] 能写出 OR 语义并解释为什么
- [ ] 能区分「方案对象」与「校验函数」的职责
- [ ] 动手题一：加一个 `APIKeyCookie` 方案并让两个端点共用
- [ ] 动手题二：把 AND 语义写进 `openapi()` 并验证

> 想看 `securitySchemes` 的完整字段、`auto_error` 的差异、多方案组合的 OpenAPI 语义、18 条坑，继续读 [`base.md`](./base.md)。