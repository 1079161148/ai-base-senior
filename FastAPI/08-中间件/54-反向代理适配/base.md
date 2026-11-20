# 54 反向代理适配 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「`root_path` 到底存在哪、`/docs` 为什么能请求对地址、`servers` 是何时注入的、`X-Forwarded-*` 谁处理、信任边界怎么定」拆开。学完这章，你能在不看 Nginx 文档的情况下把「挂 `/api` 下」这件事配对。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / uvicorn（本机实测） |
| 前置 | 第 50 章（中间件）、第 53 章（Host 校验） |
| 覆盖范围 | `root_path`、`/docs` 地址、`servers` 注入、`ProxyHeadersMiddleware`、`X-Forwarded-*` |
| 明确不覆盖 | Nginx/Traefik 完整配置、mTLS、网关路由、K8s Ingress |
| 学完验收 | 能跑通 `verify.py` 16/16、能定位「/docs 404」的根因 |

## 0. 怎么用这份文件

**依据约定**：`` `[Pn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 两个独立问题
2 机制（第 2 节）    → root_path 存在哪
3 API（第 3 节）     → server 配置项
4 边界（第 4 节）    → docs/servers/XFH/信任
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ Nginx 模板 + 排查
```

## 1. 概念：URL 生成 vs 取值正确

| 问题 | 症状 | 解法 |
| --- | --- | --- |
| 生成的 URL 缺 `/api` | `/docs` 404、回调地址错 | `root_path` |
| 拿到的 IP/协议是反代的 | 限流按反代 IP、cookie 非 secure | `X-Forwarded-*` |
| 拿到的 Host 是内网名 | 生成的绝对 URL 是 `127.0.0.1` | `proxy_set_header Host` |

两件事**不能互相替代**：配了 `root_path` 也不会让 `client.host` 变。

## 2. 机制：`root_path` 在 scope 里

```text
浏览器 → Nginx(/api/xxx) → 去掉前缀 → uvicorn
                                      scope = {
                                        "path": "/xxx",
                                        "root_path": "/api",   ← server 填
                                      }
```

| 字段 | 实测值 |
| --- | --- |
| `scope["root_path"]` | `/api` |
| `request.url.path` | `/whoami` |
| `request.base_url` | `http://testserver/api/` |
| `str(request.url_for("whoami"))` | `http://testserver/api/whoami` |

**关键**：路由匹配只看 `path`，`root_path` 只参与 URL 生成。所以配错 `root_path` 不会导致 404，只会导致链接错。

## 3. API 逐个拆解

| 配置 | 位置 | 实测 |
| --- | --- | --- |
| `--root-path /api` | uvicorn | 生效 |
| `fastapi run --root-path` | FastAPI CLI | 生效（官方推荐写法）|
| `FastAPI(root_path=...)` | 代码 | **有 `FastAPIDeprecationWarning`** |
| `root_path_in_servers=False` | 代码 | 不再往 `servers` 注入 |
| `--proxy-headers` | uvicorn | 等价于加 `ProxyHeadersMiddleware` |
| `--forwarded-allow-ips 127.0.0.1` | uvicorn | 只信任这些来源 |

### 3.1 `/docs` 的地址从哪来

实测 HTML：

```text
url: '/api/openapi.json'
```

FastAPI 的 docs 端点会 `root_path + openapi_url`。所以只要 `root_path` 对，`/api/docs` 就能正常加载。

### 3.2 `servers` 是运行时注入的

```python
# 简化逻辑（FastAPI.openapi()）
root_path = req.scope.get("root_path", "").rstrip("/")
if root_path and self.root_path_in_servers:
    self.servers.insert(0, {"url": root_path})
```

| 条件 | `servers` |
| --- | --- |
| 有 `root_path` | `[{"url": "/api"}]` |
| 无 `root_path` | 无该字段 |
| `root_path_in_servers=False` | 无该字段 |

**副作用**：`insert(0, ...)` 修改的是 `self.servers`，重复调用 `openapi()` 可能累积。生产建议显式传 `servers=[...]` 并关掉自动注入。

## 4. 边界条件

### 4.1 `X-Forwarded-For`（实测）

| 对端 IP | 结果 |
| --- | --- |
| `127.0.0.1`（在 `trusted_hosts`）| `client.host = 1.2.3.4` |
| `8.8.8.8`（不在）| `client.host = 8.8.8.8`（头被忽略）|

注意 `X-Forwarded-For` 可能是逗号列表（`1.2.3.4, 10.0.0.1`），uvicorn 取的是**最后**一个非信任项，链路长时要确认。

### 4.2 `X-Forwarded-Proto`（实测）

信任时 `url.scheme = https`。这影响：

- `request.url_for()` 生成的绝对 URL 协议
- 依赖 `url.scheme` 判断的安全 cookie
- 重定向的 `Location`

### 4.3 `X-Forwarded-Host`（实测不处理）

`ProxyHeadersMiddleware` 只改 `client` 和 `scheme`，**不改 Host**。实测 `host` 仍是 `testserver`。

所以 Host 一定要在反代层设：

```nginx
proxy_set_header Host $host;
```

### 4.4 `X-Forwarded-Prefix`（实测不内置）

Starlette 不读这个头。想用必须自己写：

```python
class ForwardedPrefixMiddleware:
    async def __call__(self, scope, receive, send):
        for key, value in scope["headers"]:
            if key == b"x-forwarded-prefix":
                scope["root_path"] = value.decode("latin-1").rstrip("/")
        await self.app(scope, receive, send)
```

**风险**：让客户端控制 `root_path` → 生成任意前缀的链接（钓鱼、缓存投毒、开放重定向）。生产用固定前缀。

### 4.5 信任边界

`--forwarded-allow-ips "*"` 的含义是「信任任何人发的 `X-Forwarded-For`」，客户端可伪造 `127.0.0.1` 绕过 IP 白名单/限流。

| 部署 | 正确值 |
| --- | --- |
| 同机 Nginx | `127.0.0.1` |
| Docker 网络 | 网段，如 `172.17.0.0/16` |
| 公网直连 | 不要开 `--proxy-headers` |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 用 `FastAPI(root_path=)` | 废弃警告（实测）| `--root-path` | 实测 |
| 剥前缀但没配 `root_path` | `/docs` 拉 `/openapi.json` 404 | 配 server 前缀 | 实测 |
| `proxy_pass` 漏末尾斜杠 | 后端收到 `/api/xxx` → 404 | `/api/` → `/` | `[P1]` |
| `forwarded-allow-ips "*"` | XFF 可伪造 | 只列反代 IP | 实测 |
| 以为 XFH 会改 Host | 不生效（实测）| `proxy_set_header Host` | 实测 |
| 以为 X-Forwarded-Prefix 内置 | 不生效（实测）| 自写或固定前缀 | 实测 |
| 用 `request.url.path` 拼外链 | 缺前缀 | `url_for()` | 实测 |
| 用 `request.base_url` 拼重定向 | 反代下变内网地址 | `url_for()` + 配置域名 | `[P1]` |
| 重复调 `openapi()` | `servers` 累积 | 显式传 `servers` | 源码 |
| 只在应用配前缀 | 静态资源仍 404 | 反代也配 | `[P2]` |
| 用 Host 头拼密码重置链接 | 投毒 | 固定配置域名 | 第 53 章 |
| `root_path` 带尾斜杠 | 出现 `//` | 不带尾斜杠 | 实测 |
| 多级代理只配一层 | 前缀错 | 每层都对齐 | `[P2]` |
| 用 `X-Real-IP` 而不配 ProxyHeaders | 拿到反代 IP | 用 XFF 或自读 | `[P3]` |
| 生产用 `--reload` | 性能与稳定问题 | 关掉 | `[P3]` |
| 反代超时短于慢接口 | 502/504 | 调 `proxy_read_timeout` | `[P2]` |
| 只测本机直连 | 前缀问题漏测 | 用 `/api` 路径测 | 第 71 章 |
| 信任 `X-Forwarded-Proto` 却不校验 | cookie 被降级 | 固定 https | `[P3]` |
| 直接把 `X-Forwarded-For` 当限流 key | 多级代理下可伪造/取错段 | 只取最后一个可信项 | `[P3]` |

## 6. 最佳实践与编码建议

### 6.1 Nginx 模板

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8000/;
    proxy_http_version 1.1;
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
    proxy_read_timeout 60s;
}
```

### 6.2 应用侧

```python
app = FastAPI(servers=[{"url": "/api"}]) if settings.behind_proxy else FastAPI()
```

| 建议 | 说明 |
| --- | --- |
| 前缀由部署决定 | 代码不写死 |
| `servers` 显式配置 | 避免累积 |
| 外链一律 `url_for` | 自动带前缀 |
| 关掉 `--reload` | 生产 |

### 6.3 排查流程

```text
1. /docs 打不开？
   → 浏览器 Network 看请求的是 /openapi.json 还是 /api/openapi.json
   → 是前者：没配 root_path
2. /api/xxx 404？
   → 看 Nginx proxy_pass 末尾有没有斜杠
   → 看 uvicorn 日志里的 path 是否带 /api
3. client.host 是 127.0.0.1？
   → 没开 --proxy-headers 或 allow-ips 不含反代
4. 生成的链接是 http://127.0.0.1:8000？
   → 没设 Host / 没设 X-Forwarded-Proto
```

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[P1]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/behind-a-proxy/ | root_path 与 servers |
| `[P2]` | 文档 | https://nginx.org/en/docs/http/ngx_http_proxy_module.html | `proxy_set_header` |
| `[P3]` | 文档 | https://www.uvicorn.org/settings/ | `--proxy-headers` |

> **核对状态**：`[P1]`–`[P3]` 为官方文档链接，**本次未逐页直连复核**；root_path 在 scope、path 不含前缀、base_url/url_for 含前缀、docs 的 openapi 地址、servers 注入与关闭、无前缀对照、XFF/XFP 信任与不信任、XFH 不处理、X-Forwarded-Prefix 需自写、`root_path` 参数废弃均为本机实测，`examples/verify.py` 复现 16/16 通过。真实 Nginx、多级代理、`servers` 累积**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] `root_path` 与 `X-Forwarded-*` 的分工
- [ ] 为什么 `path` 不含前缀
- [ ] `/docs` 的 openapi 地址怎么拼
- [ ] `servers` 何时注入
- [ ] 谁在信任 `X-Forwarded-For`

**能写出（代码层）**：

- [ ] 正确的 `uvicorn` 启动参数
- [ ] Nginx `location` 模板
- [ ] `X-Forwarded-Prefix` 中间件
- [ ] 显式 `servers` 配置

**能判断（避坑层）**：

- [ ] 看到 `/docs` 404 → 指出 root_path
- [ ] 看到 `proxy_pass` 无尾斜杠 → 指出路径重复
- [ ] 看到 `allow-ips "*"` → 指出伪造风险
- [ ] 看到依赖 XFH → 指出不处理
- [ ] 看到用 Host 拼链接 → 指出投毒

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 16/16
- [ ] `uvicorn main:app --root-path /api` 后访问 `/api/docs`
- [ ] 加 `-H "X-Forwarded-Proto: https"` 看 `scheme`

## 9. 下一章衔接

第 55 章 `数据库连接与生命周期`：`lifespan` 建连接、关闭释放，用标准库 `sqlite3` + `to_thread` 避免阻塞事件循环，讲「模块级连接为什么不能跨线程」「`lifespan` 与 `startup` 事件的取舍」。

本章留下的伏笔：

1. 中间件/ASGI 包装（50/54）→ 55 的 `lifespan` 也是 ASGI 层。
2. `url_for` 生成外链（54）→ 55 的仓库层不拼 URL。
3. 请求级资源（52 contextvars）→ 55 的连接生命周期。