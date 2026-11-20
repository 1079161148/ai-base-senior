# 53 性能中间件 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「压缩的判定条件、`Vary` 与缓存的耦合、Host 头注入的攻击面、`www_redirect` 为什么不可靠」拆开。学完这章，你要能判断一个响应会不会被压、测试为什么 400。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Starlette（本机实测） |
| 前置 | 第 50 章（中间件）、第 51 章（`Vary`） |
| 覆盖范围 | `GZipMiddleware`、`TrustedHostMiddleware`、压缩判定、Host 校验 |
| 明确不覆盖 | Brotli/zstd、CDN 压缩、Nginx 层配置、SSE 压缩行为 |
| 学完验收 | 能跑通 `verify.py` 15/15、能预测压缩结果、能配 Host 白名单 |

## 0. 怎么用这份文件

**依据约定**：`` `[Zn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 压什么、为何压
2 机制（第 2 节）    → 判定条件
3 API（第 3 节）     → 两个中间件
4 边界（第 4 节）    → media_type、Vary、Host、www
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 部署分层
```

## 1. 概念：压缩是「带宽换 CPU」

| 维度 | 现状 |
| --- | --- |
| 收益 | 文本类常压到 1/5 ~ 1/10 |
| 代价 | 每次请求的 CPU |
| 已压缩格式 | 再压几乎无收益，甚至变大 |
| 分层 | Nginx/CDN 做通常比应用层更省 |

应用层压缩适合「没有反代压缩」或「反代不压 application/json」的场景。

## 2. 机制：三个条件同时成立

```text
Accept-Encoding 含 gzip
  AND len(body) >= minimum_size
  AND 响应未自带 Content-Encoding
  AND content-type 不在「已压缩类型」黑名单
→ 压 → 加 Content-Encoding: gzip + Vary: Accept-Encoding
```

| 实测 | 结果 |
| --- | --- |
| 1600 字符中文（3200 字节）| → 82 字节 |
| `Content-Length` | 82（压缩后）|
| `Vary` | `Accept-Encoding` |

## 3. API 逐个拆解

### 3.1 `GZipMiddleware`

| 参数 | 默认 | 说明 |
| --- | --- | --- |
| `minimum_size` | 500 | 小于不压；调大省 CPU |
| `compresslevel` | 9 | 1 最快，9 最小 |

### 3.2 `TrustedHostMiddleware`

| 参数 | 说明 |
| --- | --- |
| `allowed_hosts` | 精确域名或 `*.example.com` |
| `www_redirect` | 实测未产生 301（见 4.4）|

实测 400 响应体就是纯文本 `Invalid host header`，不是 JSON。

## 4. 边界条件

### 4.1 media_type 判定（实测）

| Content-Type | 是否压 |
| --- | --- |
| `text/plain` | ✅ |
| `text/csv` | ✅ |
| `application/json` | ✅ |
| `application/octet-stream` | ✅（反直觉）|
| `image/png` | ❌ |
| 已带 `Content-Encoding` | ❌（不重复压）|

**结论**：不要用「是不是二进制」判断，要实测具体类型。

### 4.2 `Accept-Encoding`（实测）

| 客户端头 | 结果 |
| --- | --- |
| `gzip` | 压 |
| `identity` | 不压 |
| 不传（httpx/浏览器默认带 gzip）| 压 |

用 `curl` 手工测时，`curl` 不主动带 `Accept-Encoding`，会看到「没压」——容易误判。

### 4.3 `Vary` 与 CDN

如果 CDN 缓存了压缩版却没 `Vary: Accept-Encoding`，会把 gzip 字节发给不支持 gzip 的客户端。框架自动加了，**但如果你在反代层又覆盖了响应头，要补回来**。

### 4.4 `www_redirect` 实测偏差

| 配置 | 请求 Host | 实测 |
| --- | --- | --- |
| `allowed_hosts=["example.com","www.example.com"]`, `www_redirect=True` | `www.example.com` | **200**（不跳）|
| `allowed_hosts=["example.com"]`, `www_redirect=True` | `www.example.com` | **400**（不跳）|

**没有出现 301**。生产用 Nginx `return 301` 或应用内显式路由，不要依赖这个参数。

### 4.5 Host 头注入能做什么

| 攻击 | 利用点 |
| --- | --- |
| 密码重置链接投毒 | 用 Host 拼链接 |
| 缓存投毒 | 同一内容不同 Host |
| SSRF 绕过 | 白名单按 Host 判断 |

`TrustedHostMiddleware` 是最低成本的防线，但**不替代反代层的 server_name 限制**。

### 4.6 端口与大小写

`allowed_hosts=["example.com"]`，请求 `Host: example.com:8000` → Starlette 会 `split(":")[0]`，仍匹配。但 `EXAMPLE.COM` 大小写不同 → 不匹配（Host 名比较是大小写敏感的字符串比较）。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 加 TrustedHost 后测试全 400 | `testserver` 不在白名单（实测）| `base_url` 指定 | 实测 |
| 以为二进制不压 | octet-stream 会压（实测）| 按 content-type 实测 | 实测 |
| 重复压已压缩内容 | 体积变大 | 响应带 `Content-Encoding` | 实测 |
| `minimum_size=0` | 空响应也尝试压 | ≥500 | `[Z1]` |
| 漏 `Vary` | CDN 串缓存 | 框架已加，别覆盖 | `[Z2]` |
| 用 `Content-Length` 算原大小 | 是压缩后大小（实测 82）| 解压后算 | 实测 |
| 依赖 `www_redirect` | 实测不 301 | Nginx/显式路由 | 实测 |
| `allowed_hosts=["*"]` | 等于关闭保护 | 列白名单 | `[Z1]` |
| 同时开应用层与 Nginx 压缩 | 双重压缩/无收益 | 二选一 | `[Z3]` |
| 对 SSE/流式响应压 | 缓冲导致延迟 | 排除流式端点 | `[Z3]` |
| 白名单写端口 | 可能不匹配 | 只写主机名 | 实测 |
| 白名单写大写 | 大小写不匹配 | 小写 | 实测 |
| 用 Host 拼重置链接却不校验 | 投毒 | 固定配置域名 | `[Z3]` |
| 压缩图片/视频 | CPU 白烧 | 排除 | `[Z2]` |
| 只在应用层防 Host | 反代可绕 | 网关也配 | `[Z3]` |
| `compresslevel=9` 用于高 QPS | CPU 打满 | 1~4 | `[Z2]` |
| 测试里断言 `len(r.content)` 等于原文 | httpx 已解压 | 断言 `content-length` | 实测 |
| 只测 200 | 400/testserver 未覆盖 | 三种都测 | 第 71 章 |
| 对 SSE/流式响应开压缩 | 首字节延迟、流被缓冲 | 排除流式端点 | `[Z3]` |

## 6. 最佳实践与编码建议

### 6.1 压缩分层

| 层 | 是否压 | 理由 |
| --- | --- | --- |
| 应用（GZip）| 可选 | 简单但吃应用 CPU |
| Nginx | 推荐 | 高效、可配 `gzip_types` |
| CDN | 推荐 | 就近压 |

三者只开一层，否则重复压。

### 6.2 测试要点

```python
# 【要点】TrustedHost 生效后，所有 TestClient 都要指定 base_url
client = TestClient(app, base_url="http://example.com")

# 【要点】httpx 会自动解压，`r.text` 是原文，`content-length` 是压缩后
assert r.headers["content-encoding"] == "gzip"
assert int(r.headers["content-length"]) < len(r.text.encode())
```

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[Z1]` | 文档 | https://www.starlette.io/middleware/ | 两个中间件参数 |
| `[Z2]` | 规范 | https://www.rfc-editor.org/rfc/rfc9110#field.vary | `Vary` 语义 |
| `[Z3]` | 指南 | https://cheatsheetseries.owasp.org/cheatsheets/HTTP_Headers_Cheat_Sheet.html | Host 头安全 |

> **核对状态**：`[Z1]`–`[Z3]` 为文档/规范/指南链接，**本次未逐页直连复核**；小/大响应、identity、`Vary`、json/csv/png/octet 的压缩结果、已编码不重复压、`Content-Length=82`、Host 三种结果、`testserver` 400、通配、`www_redirect` 无 301 均为本机实测，`examples/verify.py` 复现 15/15 通过。真实 CDN、SSE 压缩、Brotli **未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 压缩的四个判定条件
- [ ] 为什么 octet-stream 压、png 不压
- [ ] `Vary` 缺失的后果
- [ ] Host 头注入的三种利用
- [ ] `www_redirect` 为什么不可靠

**能写出（代码层）**：

- [ ] `GZipMiddleware(minimum_size=500)`
- [ ] `TrustedHostMiddleware` 白名单
- [ ] `base_url` 的测试写法
- [ ] 排除流式端点
- [ ] 分层压缩选择

**能判断（避坑层）**：

- [ ] 看到测试全 400 → 指出 testserver
- [ ] 看到「二进制不压」→ 指出 octet-stream 会压
- [ ] 看到用 `Content-Length` 算原大小 → 指出语义
- [ ] 看到依赖 `www_redirect` → 指出实测不生效
- [ ] 看到双层压缩 → 指出浪费

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 15/15
- [ ] `curl -H "Accept-Encoding: gzip" -i /big`
- [ ] `curl -H "Host: evil.com" -i /ping` 看 400

## 9. 下一章衔接

M08 到此收尾（50–53）。第 54 章 `反向代理适配`：`--root-path`、`X-Forwarded-Proto`/`X-Forwarded-For`、`ProxyHeadersMiddleware`，讲「Nginx 后面 `/api` 前缀怎么让 `/docs` 正确」「`request.client.host` 拿到的是不是真实 IP」。

本章留下的伏笔：

1. `Vary` 与反代缓存（51/53）。
2. Host 与 `root_path` 的关系（54）。
3. 中间件顺序在最外层（50）→ `ProxyHeadersMiddleware` 也要靠外。