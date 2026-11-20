# 51 CORS

## 一句话结论

CORS 是**浏览器的**同源策略，服务端只是声明「允许谁读」。`CORSMiddleware` 干三件事：给真实响应回声 `Access-Control-Allow-Origin`、应答预检 `OPTIONS`、写对 `Vary: Origin`。三个实测结论：**非法 origin 仍然 200 并返回数据**（只是没有 CORS 头，浏览器才拦）；**预检失败是 400**（`Disallowed CORS origin/method/headers`）；**`allow_origins=["*"]` + `allow_credentials=True` 时会回声具体 origin 而不是 `*`**。

## 最小可运行案例

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000"],   # 协议+主机+端口，不能带路径
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["X-Token"],
    expose_headers=["X-Total"],
    max_age=600,
)


@app.get("/data")
def read_data() -> dict[str, list[int]]:
    return {"items": [1, 2, 3]}
```

## 怎么跑

```powershell
cd "08-中间件\51-CORS\examples"
uv sync
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 允许的 origin -> ACAO=echo, credentials=true, expose=X-Total
[PASS] Vary: Origin -> 两个响应的 Vary 都是 Origin
[PASS] 非法 origin 仍 200 -> 200 但无 ACAO（服务端不拒绝，浏览器拒绝）
[PASS] 无 Origin 无头 -> 无 Origin → 无 CORS 头
[PASS] 预检通过 -> 200, methods=GET, POST, max-age=600
[PASS] 预检默认头白名单 -> allow-headers=Accept, Accept-Language, Content-Language, Content-Type, X-Token
[PASS] 预检非法 origin -> 400 Disallowed CORS origin
[PASS] 预检非法 method -> 400 Disallowed CORS method
[PASS] 预检非法 header -> 400 Disallowed CORS headers
[PASS] 404 也带 CORS -> 404 也带 ACAO
[PASS] * + credentials -> ACAO=http://any.com（不是 *）
[PASS] CORS 不是鉴权 -> 数据照样返回——CORS 只约束浏览器
[PASS] expose 白名单 -> expose=X-Total
[PASS] 星号模式 -> 任意 origin 回声

结果：14/14 通过
```

## 核心 API 速查

| 参数 | 作用 | 常见错 |
| --- | --- | --- |
| `allow_origins` | 允许的源列表 | 写 `http://a.com/api`（带路径）|
| `allow_origin_regex` | 正则匹配源 | 写成贪婪 `.*` |
| `allow_credentials` | 允许带 cookie | 与 `*` 同用 |
| `allow_methods` | 允许的方法 | 漏 `OPTIONS`（框架自动放行）|
| `allow_headers` | 允许的请求头 | 漏自定义头 → 预检 400 |
| `expose_headers` | 允许 JS 读的响应头 | 以为所有头都能读 |
| `max_age` | 预检缓存秒数 | 设 0 导致每次都预检 |

| 实测行为 | 结果 |
| --- | --- |
| 允许 origin | 回声 + `credentials: true` + `expose` |
| 非法 origin（真实请求）| **200 且返回数据**，无 `ACAO` |
| 非法 origin（预检）| **400 `Disallowed CORS origin`** |
| 非法 method（预检）| 400 `Disallowed CORS method` |
| 非法 header（预检）| 400 `Disallowed CORS headers` |
| 无 `Origin` | 不加任何 CORS 头 |
| 404 | 也带 `ACAO`（中间件覆盖）|
| `*` + credentials | 回声具体 origin |
| `Vary` | 两种情况都是 `Origin` |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| `allow_origins=["http://a.com/"]` | 永不匹配 | 去掉尾斜杠 |
| `allow_origins=["http://a.com/api"]` | 永不匹配 | 只写源 |
| 以为 CORS 能防未授权访问 | 非浏览器客户端照样读 | CORS 不是鉴权 |
| 生产用 `allow_origins=["*"]` + credentials | 回声任意 origin，等于全放开 | 白名单 |
| `allow_headers` 漏自定义头 | 预检 400 | 列全 |
| 漏 `expose_headers` | 前端读不到自定义响应头 | 显式列出 |
| 前端用代理绕过 CORS | 线上仍跨域 | 生产也配 |
| 只看预检 200 就以为通了 | 真实请求可能缺 `ACAO` | 两种都测 |
| 把 CORS 头写进 Nginx 又配中间件 | 头重复（`ACAO: a, b`）| 只在一处 |
| 用 `allow_origin_regex=".*"` | 等价全放开 | 精确正则 |

## 毕业自查

- [ ] 能解释「简单请求」与「预检请求」的触发条件
- [ ] 能说出非法 origin 为什么还是 200
- [ ] 能解释 `*` + credentials 的处理
- [ ] 能配置 `expose_headers` 与 `max_age`
- [ ] 知道 CORS 不是鉴权
- [ ] 动手题一：给前端 3000/5173 两个 origin
- [ ] 动手题二：用 `allow_origin_regex` 放行 `*.example.com`

> 想看预检的完整报文、`Vary: Origin` 与 CDN 的关系、`allow_credentials` 的安全含义、Nginx 双层配置冲突、18 条坑，继续读 [`base.md`](./base.md)。