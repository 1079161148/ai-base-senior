# 53 性能中间件（GZip / TrustedHost）

## 一句话结论

`GZipMiddleware` 只在三个条件同时满足时才压：客户端接受 gzip、响应体 ≥ `minimum_size`、响应自身没声明 `Content-Encoding`。压完补 `Vary: Accept-Encoding`，`Content-Length` 变成**压缩后**的字节数（实测 1600 字符中文 ≈ 3200 字节 → 82 字节）。`TrustedHostMiddleware` 校验 `Host`，不匹配直接 **400 `Invalid host header`**。

五个实测反直觉点：

1. **`image/png` 不压，但 `application/octet-stream` 会压**——别按「是不是二进制」判断。
2. `Accept-Encoding: identity` 才不压；不传头时 httpx/h11 会带 gzip，照样压。
3. `Content-Length` 不删除，而是**压缩后的大小**（82），与 `len(r.text)` 无关。
4. `TestClient` 默认 Host 是 `testserver`，配了 `TrustedHostMiddleware` 后**所有测试都会 400**，必须显式 `base_url`。
5. **`www_redirect=True` 实测没有产生 301**：`www` 在白名单里 → 200，不在 → 400。

## 最小可运行案例

```python
from fastapi import FastAPI
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import Response

app = FastAPI()
app.add_middleware(GZipMiddleware, minimum_size=500)
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["example.com", "*.example.com"],
    www_redirect=False,
)


@app.get("/big")
def big() -> Response:
    return Response(content="重复内容" * 200, media_type="text/plain")
```

## 怎么跑

```powershell
cd "08-中间件\53-性能中间件\examples"
uv sync
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 小响应不压 -> 无 Content-Encoding
[PASS] 大响应压 -> 1600B → 82B
[PASS] identity 不压 -> identity → 3200 字节原样（1600 字符）
[PASS] Vary: Accept-Encoding -> Vary: Accept-Encoding
[PASS] JSON 压 -> JSON → gzip
[PASS] text/csv 压 -> text/csv → gzip
[PASS] image/png 不压 -> image/png 保持原样
[PASS] octet-stream 压 -> octet-stream → gzip（反直觉）
[PASS] 已编码不重复压 -> 保持原 10 字节，未二次压缩
[PASS] Content-Length 语义 -> Content-Length=82（原文 1600）
[PASS] Host 允许 -> example.com → 200
[PASS] Host 拒绝 -> evil.com → 400
[PASS] testserver 被拒 -> testserver → 400（测试要显式 base_url）
[PASS] 通配 Host -> api.example.com → 200
[PASS] www_redirect 实测 -> 白名单含 www → 200；不含 → 400（无 301）

结果：15/15 通过
```

## 核心 API 速查

| 中间件 | 参数 | 作用 |
| --- | --- | --- |
| `GZipMiddleware` | `minimum_size=500` | 小于此值不压 |
| | `compresslevel=9` | 1 快 9 小 |
| `TrustedHostMiddleware` | `allowed_hosts=[...]` | 支持 `*` 前缀通配 |
| | `www_redirect=True` | 实测未产生 301，别依赖 |

| 实测压缩行为 | 结果 |
| --- | --- |
| `text/plain` 大 | gzip |
| `application/json` | gzip |
| `text/csv` | gzip |
| `application/octet-stream` | **gzip** |
| `image/png` | 不压 |
| 已带 `Content-Encoding` | 不重复压 |
| 小于 `minimum_size` | 不压 |
| `Accept-Encoding: identity` | 不压 |

| 实测 Host 行为 | 结果 |
| --- | --- |
| 白名单内 | 200 |
| `*.example.com` | 200 |
| 不在白名单 | 400 `Invalid host header` |
| `testserver`（TestClient 默认）| 400 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 加了 TrustedHost 后测试全 400 | 默认 Host 是 `testserver` | `TestClient(app, base_url="http://example.com")` |
| `minimum_size=0` | 连 204/空响应都尝试压 | 至少 500 |
| 以为 PNG/JPEG 会被压 | 不会（但 octet-stream 会）| 按 content-type 实测 |
| 重复压已压缩内容 | 变大 | 让响应自己带 `Content-Encoding` |
| 漏 `Vary: Accept-Encoding` | CDN 把压缩版发给不支持的客户端 | 框架已处理，别手写覆盖 |
| 用 `Content-Length` 判断原大小 | 是压缩后大小 | 解压后算 |
| 依赖 `www_redirect` | 实测不 301 | Nginx/显式路由 |
| `allowed_hosts=["*"]` | 等于关闭保护 | 列白名单 |
| 端口写进白名单 | `example.com:8000` 不匹配 | 只写主机名 |
| 只在应用层防 Host 注入 | 反代层可绕 | 网关/反代也配 |

## 毕业自查

- [ ] 能说出压缩的三个前提
- [ ] 能解释为什么 `image/png` 不压而 octet-stream 压
- [ ] 能解释 `Content-Length` 的语义变化
- [ ] 会配 `TrustedHostMiddleware` 并改测试 `base_url`
- [ ] 知道 `www_redirect` 不可靠
- [ ] 动手题一：测 `compresslevel=1` 与 `9` 的体积/耗时
- [ ] 动手题二：给 `allowed_hosts` 加环境变量配置

> 想看 `Vary` 与 CDN 的交互、压缩对 SSE/流式的影响、Host 头注入的真实攻击、`Content-Length` 缺失后的分块传输、18 条坑，继续读 [`base.md`](./base.md)。