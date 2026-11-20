# 24 响应头

## 一句话结论

响应头**不能**写进 Pydantic 模型，只有两条路：注入 `Response` 后 `response.headers[...]`，或直接返回 `JSONResponse(...)`/`PlainTextResponse(...)`。装饰器 `responses={200: {"headers": ...}}` 只写进 `/openapi.json`，**不会**真的发送。头值必须是 ASCII（中文会 500）。

学完这一章，你能：加自定义头、下发 Cookie、设媒体类型、把响应头写进文档、避开「文档有、实际没有」的坑。

## 最小可运行案例

```python
from typing import Any

from fastapi import FastAPI, Response
from fastapi.responses import JSONResponse
from pydantic import BaseModel

app = FastAPI()


class ItemOut(BaseModel):
    id: int
    name: str


@app.get("/items/1", response_model=ItemOut)
def get_item(response: Response) -> ItemOut:
    response.headers["X-Request-Id"] = "req-abc-123"
    response.headers["X-RateLimit-Remaining"] = "99"
    return ItemOut(id=1, name="机械键盘")


@app.get("/raw")
def raw() -> Any:
    return JSONResponse({"id": 1}, headers={"X-Cache": "HIT"})


@app.post("/login")
def login(response: Response) -> dict[str, str]:
    response.set_cookie("session", "token", max_age=3600, httponly=True, samesite="lax")
    return {"status": "ok"}
```

完整版本（OpenAPI 头文档、多 Cookie、中文头、Content-Length）见 `examples/main.py`。

## 怎么跑

```powershell
cd "03-响应\24-响应头\examples"
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 注入 Response 加头 -> X-Request-Id=req-abc-123
[PASS] 头名大小写不敏感 -> 大小写三种写法都能取到
[PASS] JSONResponse 带头 -> 自定义头 + 字段未被过滤
[PASS] 媒体类型 -> content-type=text/plain; charset=utf-8
[PASS] Set-Cookie -> Set-Cookie 含 HttpOnly/Max-Age/SameSite
[PASS] 多个 Set-Cookie -> 两条 Set-Cookie（get_list 可用）
[PASS] OpenAPI 头文档 -> 文档声明了 X-RateLimit-Remaining
[PASS] 文档头不会真发 -> 文档有、实际无（需自己 set）
[PASS] 中文头值 -> 500（latin-1 编码失败）—— 头值必须纯 ASCII
[PASS] Content-Length 被重算 -> 声明 999 → 实际头 '7, 999'（多值合并，别手改）

结果：10/10 通过
```

## 核心 API 速查

| 目的 | 写法 | 注意 |
| --- | --- | --- |
| 加自定义头 | `def f(response: Response): response.headers["X-A"] = "1"` | 不参与请求解析 |
| 返回时带头 | `JSONResponse(content, headers={...})` | 绕过响应模型 |
| 设 Cookie | `response.set_cookie(key, value, max_age, httponly, secure, samesite)` | 生产必须 `httponly+secure` |
| 删 Cookie | `response.delete_cookie(key)` | 需同 `path`/`domain` |
| 改媒体类型 | `PlainTextResponse("ok")` / `media_type="application/xml"` | 与 `Content-Type` 一致 |
| 文档声明头 | `responses={200: {"headers": {...}}}` | 纯文档 |
| 读响应头（客户端） | `r.headers["x-a"]` / `r.headers.get_list("set-cookie")` | 大小写不敏感 |

| 头 | 谁写 | 能不能手改 |
| --- | --- | --- |
| `Content-Type` | 响应类 | 可，但要用对媒体类型 |
| `Content-Length` | 框架 | **不要**手改（会被拼成多值）|
| `Set-Cookie` | `set_cookie` | 可多值 |
| `Server`/`Date` | 服务器 | 一般不碰 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 想用响应模型声明头 | 模型只能描述 body | 注入 `Response` |
| 只写 `responses.headers` 文档 | 实际没有头 | 文档 + `set` 都要做 |
| 头值写中文 | 500（latin-1 编码失败）| 用 ASCII 或 URL 编码 |
| 手改 `Content-Length` | 变成多值 `'7, 999'`，客户端可能解析失败 | 交给框架 |
| `set_cookie` 不设 `httponly` | XSS 可读 | 生产固定 `httponly=True`、`secure=True` |
| 以为头会自动小写 | 实际保留写法，读取不区分大小写 | 读时统一小写比较 |
| 用头传大量数据 | 头有大小限制（常 8KB）| 放 body |
| `JSONResponse` + `response_model` | 文档骗人 | 去掉 `response_model` |

## 毕业自查

- [ ] 能说出响应头为什么不能用模型声明
- [ ] 能写出注入 `Response` 加头
- [ ] 能写出 `set_cookie` 的安全参数组合
- [ ] 能说出 `responses.headers` 的真实作用
- [ ] 能解释中文头值为什么失败
- [ ] 能说出哪些头不该手改
- [ ] 动手题一：给所有响应加一个 `X-Request-Id`（提示：中间件，第 51 章）
- [ ] 动手题二：把 `/raw` 改成 `PlainTextResponse` 并保留自定义头

> 想看头的编码规则、多值头、CORS 与缓存头、19 条坑，继续读 [`base.md`](./base.md)。
