# 11 Header 参数 · 完整版（base.md）

> `README.md` 给你能跑的示例；本文件把「下划线怎么变连字符、`convert_underscores=False` 为什么反直觉、重复头怎么取、代理头为什么不能信」拆开。学完这章，你要能设计出一套前后端都不会用错的头部契约。

| 项 | 内容 |
| --- | --- |
| 适用版本 | FastAPI 0.146.0 / Starlette 1.9.0 / Python 3.12.8（本机实测） |
| 前置 | 第 07–10 章（查询参数、Cookie） |
| 覆盖范围 | `Header()` 声明、下划线转换、大小写、重复头、必填头 `loc`、幂等键、代理头安全 |
| 明确不覆盖 | 鉴权头方案（44–49）、CORS 预检头（51）、追踪中间件（52） |
| 学完验收 | 能跑通 `verify.py` 9/9、能说出 `convert_underscores=False` 的后果、能写出幂等键 |

## 0. 怎么用这份文件

**依据约定**：`` `[Hn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 请求头与 Cookie/查询参数的差异
2 机制（第 2 节）    → 名字转换链路（重点）
3 API（第 3 节）     → Header() 全参数
4 边界（第 4 节）    → 大小写、重复头、空值、代理头、编码
5 注意事项（第 5 节）→ 22 条对照
6 最佳实践（第 6 节）→ 头部契约模板
```

## 1. 概念：请求头是元数据通道

| 维度 | 查询参数 | 请求头 | Cookie |
| --- | --- | --- | --- |
| 前端可读 | ✅ | ✅ | ⚠️ 受 httponly 限制 |
| 自动携带 | ❌ | ❌（除 UA/Accept 等） | ✅ |
| 进访问日志 | 是 | 通常**不**（更安全） | 通常不 |
| 大小写 | 敏感 | **不敏感** | 敏感 |
| 长度 | 长 | 通常 8KB 上限 | 4KB |
| 典型用途 | 过滤 | 鉴权/追踪/幂等/内容协商 | 会话 |

| 常见自定义头 | 用途 |
| --- | --- |
| `Authorization` | 凭证（标准） |
| `X-Request-Id` / `X-Trace-Id` | 链路追踪 |
| `Idempotency-Key` | 幂等（支付/下单） |
| `X-Api-Key` | 机器调用凭证 |
| `If-None-Match` / `If-Modified-Since` | 条件请求 |

## 2. 机制：名字转换链路

```python
user_agent: Annotated[str | None, Header()] = None
```

```text
① 参数名 user_agent
② convert_underscores=True（默认）→ 转成 user-agent
③ HTTP 头名大小写不敏感 → 匹配 User-Agent / user-agent / USER-AGENT
④ 取值注入
```

实测：

```text
headers={"User-Agent": "pytest/1.0"}  -> {"user_agent": "pytest/1.0"}
headers={"user-agent": "lower/1.0"}   -> {"user_agent": "lower/1.0"}
headers={"USER-AGENT": "x/1"}         -> {"user_agent": "x/1"}
```

| 结论 | 说明 | 依据 |
| --- | --- | --- |
| 下划线→连字符默认开 | `x_token` → `X-Token` | `[H1]` |
| 头名大小写不敏感 | 由 HTTP 规范保证 | `[H2]` |

### 2.1 `convert_underscores=False` 的实测行为（反直觉）

```python
user_agent: Annotated[str | None, Header(convert_underscores=False)] = None
```

实测：

```text
headers={"user_agent": "raw/1.0"}  -> {"user_agent": "raw/1.0"}   ✅ 读到
headers={"User-Agent": "ua/1.0"}   -> {"user_agent": null}        ❌ 读不到
```

| 事实 | 说明 |
| --- | --- |
| `False` 不是「两者都认」 | 而是「只认字面下划线头名」 |
| 标准 `User-Agent` 反而不匹配 | 因为找的是 `user_agent` |
| 生产风险 | 大多数代理会剥离下划线头 → 永远读不到 |

> 注意：`convert_underscores=False` 的适用场景极少。要精确指定头名，用 `alias="X-Custom"`，不要动这个开关。`[H1]`

### 2.2 必填头的 `loc` 命名（实测）

```text
GET /secure（没有 X-Api-Key）
-> 422 {"detail":[{"type":"missing","loc":["header","x-api-key"],"msg":"Field required"}]}
```

| 观察 | 说明 |
| --- | --- |
| `loc` 用**连字符**形式 | `x-api-key` 而非 `x_api_key` |
| 全小写 | 即使发送时用 `X-Api-Key` |
| 原因 | `loc` 反映的是 HTTP 层的名字，不是 Python 参数名 |

> 注意：前端按 `loc` 做字段高亮时，要按连字符名匹配，否则永远匹配不上。

## 3. API 逐一拆解

| 参数 | 默认 | 作用 | 依据 |
| --- | --- | --- | --- |
| `default` | 必填标记 | 决定可选性 | `[H1]` |
| `alias` | `None` | 精确指定头名 | `[H1]` |
| `convert_underscores` | `True` | 下划线→连字符 | `[H1]` |
| `title` / `description` | `None` | 文档 | `[H1]` |
| `deprecated` | `False` | 废弃标记 | `[H1]` |
| `include_in_schema` | `True` | 是否进文档 | `[H1]` |
| 校验参数 | 同 `Query` | `min_length` / `pattern` | 第 08 章 |

| 声明 | 对应头 |
| --- | --- |
| `Annotated[str, Header()]`（参数名 `x_token`） | `X-Token` |
| `Annotated[str, Header(alias="X-Token")]`（参数名 `t`） | `X-Token` |
| `Annotated[list[str], Header()]` | 同名头多次 |
| `Annotated[str \| None, Header()] = None` | 可选 |

## 4. 边界条件

### 4.1 重复头

实测：

```text
headers=[("X-Tag","a"), ("X-Tag","b")] -> {"x_tag": ["a","b"], "count": 2}
```

| 声明 | 结果 |
| --- | --- |
| `list[str]` | 全部收集 |
| `str` | 只取其中一个（不保证顺序） |
| `list[str] \| None` | 没有头时为 `None` |

### 4.2 空值头 vs 缺失

| 请求 | `str \| None` 参数 |
| --- | --- |
| 不带头 | `None` |
| `X-Token:`（空值） | `""` |

### 4.3 编码限制

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 头值传统上仅 latin-1 | 中文需编码 | `[H2]` |
| 现代实践允许 UTF-8 但支持不一 | 代理可能损坏 | `[H2]` |
| 中文放头 | 用 URL 编码 / Base64 | `[H3]` |
| 头名只允许 token 字符 | 不能有空格、中文 | `[H2]` |

### 4.4 代理头与 IP 伪造

```text
X-Forwarded-For: 1.2.3.4, 10.0.0.1
```

| 风险 | 说明 |
| --- | --- |
| 客户端可自带 `X-Forwarded-For` | 若直接信任，日志里的 IP 全是假的 |
| 必须限定可信代理 | `--forwarded-allow-ips`（第 54 章） |
| 取 IP 用 `request.client.host` | 让 Uvicorn 处理代理头 |

> 注意：`X-Forwarded-For` 是逗号链，最左边是客户端但可伪造，最右边是最近一跳。正确取值依赖可信代理配置，不要自己 `split(",")[0]`。

### 4.5 头名大小写在 OpenAPI 里

实测：

```text
/mixed/{item_id} [('item_id','path',True), ('q','query',False), ('x-trace','header',False), ('sid','cookie',False)]
/headers         [('user-agent','header',False), ('x-token','header',False), ('accept-language','header',False)]
```

| 观察 | 说明 |
| --- | --- |
| 文档里统一转小写 | 与实际发送时的大小写无关 |
| `alias="Idempotency-Key"` 时 | 文档保留 alias 的写法 |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `convert_underscores=False` 后发标准头 | 读不到（实测 None） | 保持默认或 `alias` | 实测 |
| 以为头名区分大小写 | 实际不敏感 | 无需关心 | `[H2]` |
| 用 `str` 读重复头 | 只拿到一个 | `list[str]` | 实测 |
| 按函数参数名查 `loc` | 找不到（是连字符） | 按 `x-api-key` | 实测 |
| 用头传大 JSON | 8KB 上限 | 用 body | `[H2]` |
| 用头传中文不编码 | 乱码/被拒 | URL 编码或 Base64 | `[H3]` |
| 信任 `X-Forwarded-For` | IP 可伪造 | 限定可信代理 | `[H4]` |
| 自己 `split(",")[0]` 取 IP | 拿到伪造值 | 用 `request.client.host` | `[H4]` |
| 自定义头不加前缀 | 与标准头冲突 | `X-` / `Trace-` | `[H5]` |
| 必填头缺失返回 422 | 前端体验差 | 可选 + 401 | 第 46 章 |
| 用 `Authorization` 又自定义一套 | 客户端难兼容 | 遵循标准 | `[H5]` |
| 头名用下划线 | 部分代理剥离 | 用连字符 | `[H2]` |
| 幂等键用内存存 | 多进程失效 | Redis | 第 02 章 |
| 幂等键不设过期 | 无限增长 | 设 TTL | `[H6]` |
| 用 `Header()` 读 body 字段 | 位置错 | 第 13 章 | `[H1]` |
| 忽略 `Content-Type` 校验 | 解析出意外结果 | 显式校验 | 第 27 章 |
| 头值带前后空格 | 不 strip | 自己 `.strip()` | `[H2]` |
| `X-Request-Id` 不校验格式 | 日志注入 | 白名单正则 | `[H3]` |
| 把 token 打进访问日志 | 泄露 | 日志脱敏 | 第 52 章 |
| 用头做业务数据传递 | 语义混乱 | 用 body | `[H5]` |
| 忽略 OPTIONS 预检 | CORS 失败 | 配 CORS 中间件 | 第 51 章 |
| 多个服务头命名不统一 | 联调成本高 | 统一契约 | `[H5]` |

## 6. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 保持 `convert_underscores` 默认 | 标准头才能读到 | 实测 |
| 需要精确头名用 `alias` | 不改开关 | `[H1]` |
| 自定义头统一 `X-` 前缀 | 避免冲突 | `[H5]` |
| 幂等键走头 + 服务端 TTL | 防重复下单 | `[H6]` |
| 追踪 id 全链路透传 | 便于排查 | 第 52 章 |
| 必填头走「可选 + 401」 | 错误语义更准 | 第 46 章 |
| 头值校验加 `pattern` | 防注入 | 第 08 章 |
| 日志脱敏 `Authorization` | 防泄露 | 第 52 章 |

**头部契约模板**：

```python
from typing import Annotated

from fastapi import FastAPI, Header

app = FastAPI()


@app.post("/payments")
def create_payment(
    # 幂等键：同一键重复提交只处理一次
    idempotency_key: Annotated[str, Header(alias="Idempotency-Key", min_length=8, max_length=64)],
    # 链路追踪：由网关生成并透传
    trace_id: Annotated[str | None, Header(alias="X-Trace-Id", pattern=r"^[a-f0-9\-]{36}$")] = None,
    # 客户端版本：便于灰度与兼容
    client_version: Annotated[str | None, Header(alias="X-Client-Version", pattern=r"^\d+\.\d+\.\d+$")] = None,
) -> dict[str, str | None]:
    return {"idempotency_key": idempotency_key, "trace_id": trace_id, "client_version": client_version}
```

**边界**：

- 头的大小限制由服务器与代理决定（常见 8KB），不是 FastAPI 限制。
- `Authorization` 的解析由安全方案接管（第 44 章），本章只讲通用头。
- `X-Forwarded-*` 的正确用法依赖部署拓扑，第 54 章展开。

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[H1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/header-params/ | `Header()`、`convert_underscores` |
| `[H2]` | 规范 | https://www.rfc-editor.org/rfc/rfc9110#section-5 | 头名大小写、字符集、字段语义 |
| `[H3]` | 规范 | https://www.rfc-editor.org/rfc/rfc3986 | 编码 |
| `[H4]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/behind-a-proxy/ | 代理头信任 |
| `[H5]` | 规范 | https://restfulapi.net/resource-naming/ | 命名约定 |
| `[H6]` | 规范 | https://datatracker.ietf.org/doc/draft-ietf-httpapi-idempotency-key-header/ | 幂等键语义 |

> **核对状态**：`[H2]`–`[H6]` 为规范/官方文档类来源，**本次未逐页直连复核**。文中「实测」为本机 FastAPI 0.146.0 / Starlette 1.9.0 输出，`examples/verify.py` 可复现 9/9 通过。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 请求头与查询参数/Cookie 的差异
- [ ] 名字转换链路 4 步
- [ ] `convert_underscores=False` 的真实行为
- [ ] 必填头 `loc` 为什么是连字符
- [ ] 头名大小写规则
- [ ] 代理头伪造的原理

**能写出（代码层）**：

- [ ] 读标准头的接口
- [ ] 读自定义头的接口
- [ ] 多值头接口
- [ ] 幂等键接口

**能判断（避坑层）**：

- [ ] 看到 `convert_underscores=False` 能指出标准头读不到
- [ ] 看到 `str` 读重复头能指出只拿一个
- [ ] 看到按参数名找 `loc` 能指出命名转换
- [ ] 看到 `X-Forwarded-For` 直取能指出伪造风险
- [ ] 看到中文进头能指出编码问题

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 9/9
- [ ] 复现「标准头 + convert_underscores=False → None」
- [ ] 用 `/docs` 看到 `in=header`

## 9. 下一章衔接

第 12 章 `参数总表`：把路径、查询、Cookie、Header 四类参数放在同一个接口里，讲清「同名冲突」「解析优先级」「`Request` 直取」「OpenAPI 里 `in` 的四种取值」，作为 M01 的收束。

本章留下的伏笔：

1. `Authorization` 头在第 44–49 章由安全方案接管。
2. 追踪 id 中间件化在第 52 章。
3. 代理头配置在第 54 章。
