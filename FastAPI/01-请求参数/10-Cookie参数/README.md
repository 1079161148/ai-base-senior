# 10 Cookie 参数

## 一句话结论

`Cookie()` 读浏览器自动携带的 `Cookie` 头；写 Cookie 要通过 `Response` 对象的 `set_cookie()`。Cookie 是**浏览器存储**，不是安全边界——`httponly` 挡 XSS 读、`secure` 挡明文传输、`samesite` 挡 CSRF，三者缺一不可。

学完这一章，你能：正确读/写 Cookie、说清 6 个安全属性的作用、判断哪些数据不该放 Cookie。

## 最小可运行案例

```python
from typing import Annotated

from fastapi import Cookie, FastAPI, Response

app = FastAPI()


@app.get("/me")
def me(session_id: Annotated[str | None, Cookie()] = None) -> dict[str, str | None]:
    # 【作用】浏览器请求时自动带 Cookie: session_id=xxx
    return {"session_id": session_id}


@app.get("/login")
def login(response: Response) -> dict[str, str]:
    # 【关键】必须通过 Response 参数写入，直接 return 不会设置 Cookie
    response.set_cookie("session_id", "abc123", httponly=True, samesite="lax", max_age=3600)
    return {"ok": "1"}
```

完整版本（多 Cookie、安全属性对比）见 `examples/main.py`。

## 怎么跑

```powershell
cd "01-请求参数\10-Cookie参数\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 无 Cookie 时为 None -> {'session_id': None, 'theme': None}
[PASS] 读取 Cookie -> {'session_id': 'xyz', 'theme': 'dark'}
[PASS] set_cookie 响应头 -> session_id=sess-alice; HttpOnly; Max-Age=3600; Path=/; SameSite=lax
[PASS] 多个 Cookie 多条头 -> 2 条：['a=1; Path=/; SameSite=lax', 'b=2; HttpOnly; Path=/; SameSite=lax']
[PASS] delete_cookie -> session_id=""; expires=...; Max-Age=0; Path=/; SameSite=lax
[PASS] Cookie 名大小写敏感 -> Session_Id 不会被 session_id 读到
[PASS] Cookie 值不解码 -> a%20b 原样返回（未解码）
[PASS] 必填 Cookie 422 -> 422 missing loc=['cookie', 'tenant']
[PASS] OpenAPI in=cookie -> session_id in=cookie required=false

结果：9/9 通过
```

## 核心 API 速查

| API | 作用 |
| --- | --- |
| `Cookie()` | 声明入参来自 Cookie |
| `Cookie(default=...)` | 可选 + 默认值 |
| `Annotated[str, Cookie()]` | 必填（无默认值） |
| `response.set_cookie(key, value)` | 写 Cookie |
| `response.delete_cookie(key)` | 删 Cookie |

| `set_cookie` 参数 | 默认 | 作用 | 安全建议 |
| --- | --- | --- | --- |
| `key` / `value` | — | 键值 | — |
| `max_age` | `None` | 存活秒数 | 会话 Cookie 不设，持久登录设 |
| `expires` | `None` | 绝对过期时间 | 与 `max_age` 二选一 |
| `path` | `"/"` | 生效路径 | 尽量收窄（如 `/api`） |
| `domain` | `None` | 生效域 | 不要随便设顶级域 |
| `secure` | `False` | 仅 HTTPS 传输 | **生产必须 True** |
| `httponly` | `False` | 禁止 JS 读取 | **必须 True**（防 XSS 偷 token） |
| `samesite` | `"lax"` | CSRF 防护 | `lax` 起步，跨站需求才 `none` |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `return {"x": 1}` 里想设 Cookie | 不生效 | 用 `response: Response` 参数 |
| `httponly=False` 存 token | XSS 可读走 | `httponly=True` |
| `secure=False` 上生产 | 明文 HTTP 泄露 | `secure=True` |
| `samesite="none"` 但 `secure=False` | 浏览器直接拒绝 | `none` 必须配 `secure=True` |
| 用 Cookie 存大量数据 | 每请求都带，浪费带宽（上限约 4KB） | 只存 session id |
| 以为 Cookie 名大小写不敏感 | 实测敏感 | 统一小写 |
| 用 Cookie 做鉴权就不用 CSRF 防护 | 跨站请求自动带 Cookie | `samesite` + CSRF token |
| 忘记 `path` 导致 Cookie 范围过大 | 全站都带 | 收窄 `path` |
| 在响应里返回 Cookie 值 | 泄露给前端 JS | 只返回状态 |

## 毕业自查

- [ ] 能说出 Cookie 与 Header 的关系
- [ ] 能写出读 Cookie 与写 Cookie 的完整代码
- [ ] 能说出 `httponly` / `secure` / `samesite` 分别防什么
- [ ] 能说出 `max_age` 与 `expires` 的区别
- [ ] 能说出为什么 Cookie 不能存大量数据
- [ ] 能解释「有 Cookie 鉴权为什么还要 CSRF 防护」
- [ ] 动手题一：登录接口设置 Cookie，另一个接口读出来
- [ ] 动手题二：把 `samesite` 改成 `none` 且不设 `secure`，观察浏览器行为

> 想看安全属性全表、CSRF 原理、24 条坑，继续读 [`base.md`](./base.md)。
