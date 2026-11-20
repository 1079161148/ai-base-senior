# 54 反向代理适配

## 一句话结论

反代把 `/api/xxx` 转成 `/xxx` 后，应用必须知道前缀，否则 `/docs`、`url_for()`、`openapi` 的 `servers` 全错。靠 `root_path`（管 URL 生成）+ `X-Forwarded-*`（管取值正确），两者互不替代。三个实测关键点：**`FastAPI(root_path=...)` 已触发 `FastAPIDeprecationWarning`**（改由 server 配置）；**`X-Forwarded-Host` 不会被 uvicorn 处理**（仍要 `proxy_set_header Host`）；**`X-Forwarded-Prefix` 完全不内置**，得自己写中间件。

## 最小可运行案例

```python
from typing import Any

from fastapi import FastAPI, Request

app = FastAPI()


@app.get("/whoami")
def whoami(request: Request) -> dict[str, Any]:
    return {
        "root_path": request.scope.get("root_path", ""),
        "path": request.url.path,          # 不含前缀
        "base_url": str(request.base_url), # 含前缀
        "url_for": str(request.url_for("whoami")),
    }
```

启动时由 server 注入前缀：

```powershell
uvicorn main:app --root-path /api --proxy-headers --forwarded-allow-ips 127.0.0.1
```

Nginx 侧：

```nginx
location /api/ {
    proxy_pass http://127.0.0.1:8000/;      # 末尾斜杠 = 剥掉 /api
    proxy_set_header Host $host;
    proxy_set_header X-Real-IP $remote_addr;
    proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
    proxy_set_header X-Forwarded-Proto $scheme;
}
```

## 怎么跑

```powershell
cd "08-中间件\54-反向代理适配\examples"
uv sync
uv run uvicorn main:app --root-path /api --reload
uv run python verify.py
```

预期输出：

```text
[PASS] root_path 来自 scope -> root_path=/api
[PASS] path 不含前缀 -> path=/whoami
[PASS] base_url 含前缀 -> http://testserver/api/
[PASS] url_for 含前缀 -> http://testserver/api/whoami
[PASS] 带路径参数的 url_for -> http://testserver/api/items/7
[PASS] /docs 的 openapi 地址 -> url: '/api/openapi.json',
[PASS] openapi servers 注入 -> [{"url": "/api"}]
[PASS] servers 关闭 -> servers 字段缺失/为 None
[PASS] 无前缀对照 -> 无前缀
[PASS] XFF 信任 -> client=1.2.3.4
[PASS] XFP 协议 -> scheme=https
[PASS] 不信任则忽略 -> client=8.8.8.8, scheme=http
[PASS] XFH 不被处理 -> Host 仍为 testserver（要靠 Nginx `proxy_set_header Host`）
[PASS] X-Forwarded-Prefix 自写 -> http://testserver/v1/whoami
[PASS] XFP 无中间件不生效 -> 无中间件 → root_path 仍为空
[PASS] root_path 参数已废弃 -> The `root_path` parameter is deprecated...

结果：16/16 通过
```

## 核心 API 速查

| 渠道 | 写法 | 归属 |
| --- | --- | --- |
| 固定前缀 | `uvicorn --root-path /api` | server |
| | `fastapi run --root-path /api` | server |
| | `FastAPI(root_path="/api")` | **已废弃** |
| 原始协议/IP | `--proxy-headers --forwarded-allow-ips 127.0.0.1` | uvicorn |
| | `ProxyHeadersMiddleware(app, trusted_hosts=[...])` | uvicorn 库 |
| 原始 Host | Nginx `proxy_set_header Host $host` | 反代 |
| 前缀头 | 自己写中间件读 `X-Forwarded-Prefix` | 应用 |

| 实测行为 | 结果 |
| --- | --- |
| `scope["root_path"]` | `/api` |
| `request.url.path` | `/whoami`（不含前缀）|
| `request.base_url` | `http://testserver/api/` |
| `url_for()` | `http://testserver/api/whoami` |
| `/docs` 里的 openapi 地址 | `/api/openapi.json` |
| `openapi.json` 的 `servers` | `[{"url": "/api"}]`（动态注入）|
| `root_path_in_servers=False` | 不注入 |
| `X-Forwarded-For`（信任 IP）| `client.host` 变成该值 |
| `X-Forwarded-Proto`（信任 IP）| `url.scheme` 变成 `https` |
| 不信任的 IP 发同样的头 | 全部忽略 |
| `X-Forwarded-Host` | **不处理** |
| `X-Forwarded-Prefix` | **不处理**（要自己写）|

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 用 `FastAPI(root_path=)` | 有废弃警告，将来会移除 | `--root-path` |
| 反代剥前缀但没配 `root_path` | `/docs` 请求 `/openapi.json` → 404 | 配 `--root-path` |
| `proxy_pass` 末尾漏斜杠 | 前缀被带进后端路径 → 404 | `/api/` 配 `/` |
| 开了 `--proxy-headers` 但 `forwarded-allow-ips` 写 `*` | 客户端可伪造 IP | 只列反代 IP |
| 指望 `X-Forwarded-Host` 改 Host | 不生效 | `proxy_set_header Host $host` |
| 指望 `X-Forwarded-Prefix` 自动生效 | 不生效 | 自写中间件或固定前缀 |
| 用 `request.url.path` 拼回调地址 | 缺前缀 | `url_for()` |
| 用 `Host` 头拼重置链接 | Host 注入 | 配固定域名 |
| 只改应用不改反代 | 静态资源 404 | 两边对齐 |
| 用请求头决定 `root_path` | 缓存投毒/开放重定向 | 固定前缀 |

## 毕业自查

- [ ] 能解释 `root_path` 与 `X-Forwarded-*` 的分工
- [ ] 能写出该配的 Nginx `location` 与四个 `proxy_set_header`
- [ ] 能解释 `/docs` 的 openapi 地址怎么来的
- [ ] 知道 `servers` 是动态注入的、怎么关
- [ ] 知道 `X-Forwarded-Host`/`Prefix` 不被处理
- [ ] 动手题一：用 `--root-path /v1` 起服务，验证 `/v1/docs`
- [ ] 动手题二：写 `X-Forwarded-Prefix` 中间件并说明风险

> 想看 `servers` 注入源码路径、`root_path` 与重定向的关系、`--forwarded-allow-ips` 的信任链、`url_for` 在 root_path 下的拼装、18 条坑，继续读 [`base.md`](./base.md)。