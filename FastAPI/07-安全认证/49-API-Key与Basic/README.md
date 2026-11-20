# 49 API Key 与 Basic 认证

## 一句话结论

机器对机器用 **API Key**（`APIKeyHeader`/`APIKeyQuery`/`APIKeyCookie`），简单人类登录用 **HTTP Basic**（`HTTPBasic` + `HTTPBasicCredentials`）。两者共同的三条铁律：**用 `secrets.compare_digest` 比较**、**401 必带 `WWW-Authenticate`**、**密钥走环境变量**。

五个实测细节：

1. 缺 `X-API-Key` → 401 `Not authenticated` + **`WWW-Authenticate: APIKey`**（大写 `APIKey`，不是 `ApiKey`）。
2. `HTTPBasic(realm="ch49-demo")` 缺凭证 → 401 + `Basic realm="ch49-demo"`。
3. **`Security(scheme, auto_error=False)` 直接 `TypeError`**——`auto_error` 只能写在方案对象上。
4. API Key 支持**轮换**：新旧 key 映射到同一 owner（实测 `key-service-a-old` → `service-a`）。
5. Basic 只是 base64，**可逆**（实测解出 `alice:alice123`），必须走 HTTPS。

## 最小可运行案例

```python
import secrets
from typing import Annotated

from fastapi import FastAPI, HTTPException, Security
from fastapi.security import APIKeyHeader, HTTPBasic, HTTPBasicCredentials

app = FastAPI()
api_key_scheme = APIKeyHeader(name="X-API-Key")
basic_scheme = HTTPBasic(realm="demo")

KEYS = {"key-a": "service-a"}
USERS = {"alice": "alice123"}


def machine(key: Annotated[str, Security(api_key_scheme)]) -> str:
    for candidate, owner in KEYS.items():
        if secrets.compare_digest(candidate, key):
            return owner
    raise HTTPException(401, "X-API-Key 无效", headers={"WWW-Authenticate": "ApiKey"})


def human(creds: Annotated[HTTPBasicCredentials, Security(basic_scheme)]) -> str:
    expected = USERS.get(creds.username, "\x00invalid")     # 用户不存在也比一次
    if not secrets.compare_digest(creds.password, expected):
        raise HTTPException(
            401, "用户名或密码错误", headers={"WWW-Authenticate": 'Basic realm="demo"'}
        )
    return creds.username


@app.get("/machine")
def m(owner: Annotated[str, Security(machine)]) -> dict[str, str]:
    return {"owner": owner}


@app.get("/basic")
def b(user: Annotated[str, Security(human)]) -> dict[str, str]:
    return {"user": user}
```

完整版本（三种 key 位置、轮换、OR 组合）见 `examples/main.py`。

## 怎么跑

```powershell
cd "07-安全认证\49-API-Key与Basic\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 四种方案 -> schemes=['APIKeyCookie', 'APIKeyHeader', 'APIKeyQuery', 'BasicAuth']
[PASS] header key -> owner=service-a
[PASS] key 轮换 -> 旧 key → 同一 owner（可无缝轮换）
[PASS] 缺 key 401 -> 401 + WWW-Authenticate: APIKey
[PASS] 无效 key -> 401 X-API-Key 无效
[PASS] query key -> ?api_key=... → service-b
[PASS] cookie key -> cookie session_key 生效
[PASS] Basic 缺凭证 -> 401 Basic realm="ch49-demo"
[PASS] Basic 正确 -> user=alice
[PASS] Basic 错误 -> 401
[PASS] Basic 非加密 -> base64 可逆 → 必须走 HTTPS
[PASS] Security auto_error -> TypeError: Security() got an unexpected keyword argument 'auto_error'
[PASS] OR 组合 -> key→service:service-a, basic→user:alice, 无→401
[PASS] compare_digest -> main.py 使用 compare_digest

结果：14/14 通过
```

## 核心 API 速查

| 方案 | 取 key 位置 | OpenAPI |
| --- | --- | --- |
| `APIKeyHeader(name=...)` | header | `{"type":"apiKey","in":"header"}` |
| `APIKeyQuery(name=...)` | query | `in: query` |
| `APIKeyCookie(name=...)` | cookie | `in: cookie` |
| `HTTPBasic(realm=...)` | `Authorization: Basic b64` | `{"type":"http","scheme":"basic"}` |

| 对象 | 字段 |
| --- | --- |
| `HTTPBasicCredentials` | `.username` / `.password`（已 base64 解码）|

| 实测行为 | 结果 |
| --- | --- |
| 缺 API Key | 401 `Not authenticated` + `APIKey` |
| 缺 Basic | 401 + `Basic realm="ch49-demo"` |
| 轮换旧 key | 映射到同一 owner |
| `?api_key=` | 可用但不推荐 |
| `Security(..., auto_error=False)` | `TypeError` |
| Basic 解码 | `alice:alice123` 明文 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `Security(scheme, auto_error=False)` | `TypeError` | 方案对象上设 |
| 用 `==` 比 key/密码 | 时序侧信道 | `compare_digest` |
| 用户不存在提前 return | 时间差暴露账号 | 哨兵值也比一次 |
| 401 无 `WWW-Authenticate` | 浏览器不弹登录框 | 加上 |
| key 放 query | 进日志/Referer | header |
| key 写在代码/仓库 | 泄露 | 环境变量 |
| 单一 key 无法轮换 | 换 key 要停机 | 新旧并存 |
| Basic 上 HTTP | 明文泄露 | 必须 HTTPS |
| cookie 方案无 CSRF 防护 | 跨站伪造 | SameSite + token |
| 把 API Key 当前端登录态 | 泄露面大 | 会话/JWT |

## 毕业自查

- [ ] 能写出三种 key 位置的方案
- [ ] 能写出 Basic 校验并解释 `compare_digest`
- [ ] 能说出 `WWW-Authenticate` 的三种值
- [ ] 能解释为什么 Basic 必须 HTTPS
- [ ] 能设计 key 轮换
- [ ] 动手题一：把 key 存哈希（`sha256`）并校验
- [ ] 动手题二：加 `X-API-Key` 的速率限制

> 想看 Basic 的 RFC 细节、`realm` 的作用、API Key 的存储与轮换策略、CSRF 与 cookie 方案、18 条坑，继续读 [`base.md`](./base.md)。