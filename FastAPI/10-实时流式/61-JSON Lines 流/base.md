# 61 JSON Lines 流 · 完整版（base.md）

> `README.md` 给你能跑的检索流；本文件把「为什么数组不能流式解析、行边界与编码怎么处理、中途失败怎么表达、断点续传怎么设计」拆开。学完这章，你能判断一个「客户端 JSON 解析失败/最后一条丢失/中文变乱码」的问题出在哪。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0（本机实测） |
| 前置 | 第 60 章（`StreamingResponse`） |
| 覆盖范围 | JSONL 格式、媒体类型、逐行消费、错误行、禁缓冲头 |
| 明确不覆盖 | JSON 流式解析器（如 `ijson`）、SSE（62 章）、gRPC streaming |
| 学完验收 | 能跑通 `verify.py` 14/14、能解释错误行为什么必须是一行 |

## 0. 怎么用这份文件

**依据约定**：`` `[Jn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 整体解析 vs 逐行解析
2 机制（第 2 节）    → 行边界与编码
3 API（第 3 节）     → 服务端与客户端写法
4 边界（第 4 节）    → 错误行、断点、缓冲
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 事件设计
```

## 1. 概念：为什么数组不能流式

```text
[{"id":1},{"id":2},{"id":3}]
                          ↑ 必须读到 `]` 才知道数组结束
```

| 格式 | 首条可处理时机 |
| --- | --- |
| JSON 数组 | 收到最后一个 `]` |
| JSON Lines | 收到第一个 `\n` |

实测对比：

| 端点 | 响应体行数 | `Content-Length` |
| --- | --- | --- |
| `/search/json` | 1 | 有（129）|
| `/search/jsonl` | 5 | 无 |

## 2. 机制：行边界与编码

### 2.1 行边界

| 分隔符 | 是否推荐 |
| --- | --- |
| `\n` | 推荐（统一）|
| `\r\n` | 兼容，但服务端别发 |
| 无分隔 | 不可解析 |

**关键**：`json.dumps` 会把字符串里的换行转义成 `\\n`，所以对象内部**不会**产生裸换行，行边界天然安全。手拼字符串则不保证。

### 2.2 编码（实测）

`application/jsonl` **不带 `charset`**（`text/plain` 才会带）：

```text
content-type: application/jsonl
```

JSON 规范要求 UTF-8，客户端必须自己按 UTF-8 解码。`httpx` 的 `iter_lines()` 默认按 UTF-8 处理。

`ensure_ascii=False` 的效果：

| 设置 | `"结果 001"` 的体积 |
| --- | --- |
| `True`（默认）| `"\u7ed3\u679c 001"`（约 18 字节）|
| `False` | `"结果 001"`（10 字节）|

中文场景差近一倍。

## 3. API 逐个拆解

### 3.1 服务端

```python
StreamingResponse(gen(), media_type="application/jsonl")
```

| 要做 | 原因 |
| --- | --- |
| 每行 `json.dumps(...) + "\n"` | 行边界 |
| `ensure_ascii=False` | 体积 |
| `separators=(",", ":")` | 去掉空格，体积再降 |
| `X-Accel-Buffering: no` | 防 Nginx 缓冲 |
| `Cache-Control: no-cache` | 防中间缓存 |

### 3.2 客户端

```python
with httpx.stream("GET", url) as response:
    for line in response.iter_lines():
        if not line:
            continue
        item = json.loads(line)
```

| 细节 | 说明 |
| --- | --- |
| `iter_lines()` 会重组跨 chunk 的半行 | 不需要自己缓冲 |
| 末尾可能有空行 | 过滤 |
| 必须设读超时 | 否则可能永久挂住 |
| 逐行 `json.loads` | 单行失败不影响前面已处理的 |

### 3.3 与 SSE 的分工

| 需求 | 用哪个 |
| --- | --- |
| 一次性检索结果分批返回 | JSONL |
| 服务端主动持续推送事件 | SSE |
| 双向通信 | WebSocket |

## 4. 边界条件

### 4.1 中途异常（实测）

| 观察者 | 结果 |
| --- | --- |
| 客户端（宽松）| 200 + 前 3 行 |
| 客户端（严格）| `RuntimeError: 索引在第 4 条之后崩了` |

客户端视角：看起来「正常结束」，因为连接关闭与正常结束在 HTTP 层没有区别（除非用 chunked 终止符——很多服务器直接断 TCP）。

**这正是不推荐裸异常的原因**：客户端无法区分「查完了」和「崩了」。

### 4.2 错误行（实测）

```python
yield to_line({"error": "索引在第 4 条之后不可用", "code": "INDEX_DOWN"})
return
```

实测客户端收到：

```text
{"id":1,...}
{"id":2,...}
{"id":3,...}
{"error":"索引在第 4 条之后不可用","code":"INDEX_DOWN"}
```

| 优点 | 代价 |
| --- | --- |
| 客户端能区分 | 每行要判 `error` 字段 |
| 仍是合法 JSONL | 数据行与错误行混在同一流 |

**设计建议**：数据行用固定 schema，错误行用 `{"error": str, "code": str}`，客户端按 `"error" in item` 分流。

### 4.3 断点续传

| 需求 | 做法 |
| --- | --- |
| 客户端记录已收到多少条 | 每行带 `seq` |
| 重连从断点开始 | 请求带 `?after=<seq>` |
| 服务端确认 | 首行回 `{"resumed_from": seq}` |

实测未覆盖，标注为**未实测设计**。

### 4.4 缓冲

| 中间层 | 行为 |
| --- | --- |
| Nginx 默认 | `proxy_buffering on`，攒够才发 |
| 加 `X-Accel-Buffering: no` | 透传 |
| CDN | 通常会缓存，需 `no-cache` |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 用 `application/json` 发多行 | 客户端解析失败 | `application/jsonl` | 实测 |
| 行末不加 `\n` | 行粘连 | 每行 `+ "\n"` | 实测 |
| `ensure_ascii=True` | 体积翻倍 | `False` | 实测 |
| 手拼 JSON | 注入/转义错 | `json.dumps` | `[J1]` |
| 先 `fetchall` 再 yield | 失去流式 | 游标 | 第 58 章 |
| 裸异常截断 | 客户端以为正常 | 错误行 | 实测 |
| 错误行后继续发 | 状态混乱 | `return` | 实测 |
| 用 `split("\n")` | 空行/CRLF | `iter_lines` | `[J1]` |
| 不设读超时 | 永久挂住 | 超时 + 心跳 | `[J1]` |
| 代理缓冲 | 成批到达 | `X-Accel-Buffering` | `[J2]` |
| 无 `Content-Length` 却要进度 | 拿不到总量 | `X-Total-Count` | 实测 |
| 用 GET 传敏感查询 | 进日志 | POST | 第 47 章 |
| 把 JSONL 当 SSE | 无事件语义 | SSE | 第 62 章 |
| 逐行 yield 太慢 | 线程池往返 | 攒批 | 第 60 章 |
| 不记录序号 | 无法断点 | `seq` 字段 | 实测未覆盖 |
| 单行巨型对象 | 单块过大 | 控制大小 | 第 60 章 |
| 客户端用 `.json()` | 只解析一次 | 逐行 | 实测 |
| 混用两类错误格式 | 客户端难判 | 统一 `{error, code}` | 实测 |
| 服务端行尾用 `\r\n` | 客户端 `split` 后残留 `\r`，JSON 解析失败 | 统一发 `\n` | 实测 |

## 6. 最佳实践与编码建议

### 6.1 行结构

```json
{"seq":1,"type":"result","data":{...}}
{"seq":2,"type":"result","data":{...}}
{"seq":3,"type":"error","error":"...","code":"..."}
```

| 字段 | 作用 |
| --- | --- |
| `seq` | 断点、丢包检测 |
| `type` | 分流（`result`/`meta`/`error`） |
| `data` | 业务载荷 |

### 6.2 服务端模板

```python
async def gen():
    sent = 0
    try:
        for row in cursor:
            yield to_line({"seq": sent, "type": "result", "data": row})
            sent += 1
    except Exception as exc:
        yield to_line({"seq": sent, "type": "error", "error": str(exc), "code": "INTERNAL"})
```

### 6.3 客户端模板

```python
errors: list[dict] = []
with httpx.stream("GET", url, timeout=30) as response:
    for line in response.iter_lines():
        if not line:
            continue
        item = json.loads(line)
        if item.get("type") == "error":
            errors.append(item)
            break
        handle(item["data"])
```

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[J1]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/stream-json-lines/ | JSON Lines 流 |
| `[J2]` | 文档 | https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_buffering | 代理缓冲 |
| `[J3]` | 规范 | https://jsonlines.org/ | JSONL 格式 |

> **核对状态**：`[J1]`–`[J3]` 为官方文档/规范链接，**本次未逐页直连复核**；媒体类型、行数、换行、逐行解析、中文不转义、逐行到达时间、中途异常两种模式、错误行、禁缓冲头、参数边界均为本机实测，`examples/verify.py` 复现 14/14 通过。真实 Nginx 缓冲、断点续传、CRLF 服务端、丢包检测**未实测**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 为什么 JSON 数组不能逐条处理
- [ ] JSONL 的行边界为什么天然安全
- [ ] 为什么 `application/jsonl` 不带 charset
- [ ] 为什么错误必须用一行表达
- [ ] `X-Accel-Buffering` 解决什么

**能写出（代码层）**：

- [ ] 服务端 `to_line` + 生成器
- [ ] 客户端 `iter_lines` 消费
- [ ] 错误行与 `return`
- [ ] `seq` 字段设计
- [ ] 断点续传参数

**能判断（避坑层）**：

- [ ] 看到 `application/json` + 多行 → 指出错
- [ ] 看到 `ensure_ascii=True` → 指出体积
- [ ] 看到裸异常 → 指出客户端无法区分
- [ ] 看到 `split("\n")` → 指出空行
- [ ] 看到无超时 → 指出挂死风险

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 14/14
- [ ] `curl -N` 观察逐行输出
- [ ] 用 Python 脚本逐行打印，确认首行立刻到达

## 9. 下一章衔接

第 62 章 `SSE`：`text/event-stream` 的事件格式、`event`/`id`/`retry` 字段、浏览器断线自动重连、`Last-Event-ID` 续传、心跳注释行。

本章留下的伏笔：

1. 逐行推送（61）→ 62 在行内加 `event:`/`data:` 语义。
2. 错误行（61）→ 62 用 `event: error` 表达。
3. 断点续传设计（61）→ 62 用 `Last-Event-ID` 标准化。