# 62 SSE · 完整版（base.md）

> `README.md` 给你能跑的打字机；本文件把「SSE 的字节级格式、浏览器的重连算法、为什么不能带自定义头、和 WebSocket 怎么选」拆开。学完这章，你能判断一个「事件不触发/断线不续传/上线就被代理缓住」的问题出在哪。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0（本机实测） |
| 前置 | 第 60 章（`StreamingResponse`）、第 61 章（JSONL） |
| 覆盖范围 | SSE 格式、事件名、`id`/`Last-Event-ID`、`retry`、心跳、响应头 |
| 明确不覆盖 | `sse-starlette` 库、HTTP/2 推送、双向通信（63 章）|
| 学完验收 | 能跑通 `verify.py` 14/14、能手写 SSE 解析器 |

## 0. 怎么用这份文件

**依据约定**：`` `[En]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → SSE 是什么、和 WebSocket 的分工
2 机制（第 2 节）    → 字节格式与解析状态机
3 API（第 3 节）     → 字段逐个拆
4 边界（第 4 节）    → 重连、缓冲、连接数
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 事件协议设计
```

## 1. 概念：单向文本推送

| 能力 | SSE | WebSocket |
| --- | --- | --- |
| 方向 | 服务端 → 客户端 | 双向 |
| 协议 | 普通 HTTP | 升级协议 |
| 自动重连 | 浏览器内置 | 自己实现 |
| 自定义请求头 | 不支持（`EventSource`） | 支持 |
| 消息格式 | 文本（`data:`） | 文本 + 二进制 |
| 代理友好度 | 好（就是 HTTP） | 需支持 Upgrade |

**选择**：只需要服务端推送（打字机、进度、通知）→ SSE；需要客户端频繁发消息（聊天、协同编辑）→ WebSocket。

## 2. 机制：字节格式

### 2.1 一个事件的完整字节

```text
event: token\n
id: 3\n
data: {"text":"你"}\n
\n
```

实测原始响应：

```text
event: token\nid: 1\ndata: {"text": "S"}\n\nevent: token\nid: 2\ndata: {"text": "S"}\n\n
```

### 2.2 解析状态机

```text
读一行
 ├─ 空行        → 派发事件（若 data 非空），重置缓冲
 ├─ 以 ":" 开头 → 注释，忽略
 └─ "field: value" → 按字段名累积
```

| 字段 | 累积方式 |
| --- | --- |
| `data` | 追加到列表，派发时用 `\n` 连接 |
| `event` | 覆盖 |
| `id` | 覆盖 |
| `retry` | 覆盖（整数） |

**关键**：`data` 是**追加**，多行才是合法用法；`event`/`id` 是**覆盖**。

### 2.3 实测的多行行为

```text
data: 第一行\ndata: 第二行\n\n
```

客户端解析结果：`"第一行\n第二行"`。

## 3. API 逐个拆解

### 3.1 响应头（实测）

```text
content-type: text/event-stream; charset=utf-8
cache-control: no-cache
x-accel-buffering: no
（无 content-length）
```

| 头 | 缺失后果 |
| --- | --- |
| `no-cache` | 中间层缓存整个流 |
| `X-Accel-Buffering: no` | Nginx 攒包 |
| `Connection: keep-alive` | 部分老代理提前断 |

### 3.2 `event:`

| 值 | 客户端 API |
| --- | --- |
| 缺省（`message`）| `onmessage` |
| `token` | `addEventListener("token", ...)` |
| `error` | `addEventListener("error", ...)` |

**注意**：`error` 在浏览器里也是**连接错误**的事件名，容易混淆。建议用 `app-error` 之类的前缀，或统一走 `message` + 业务字段。

### 3.3 `id:` + `Last-Event-ID`

```text
服务端：id: 3
浏览器：lastEventId = "3"
断线重连：Last-Event-ID: 3
服务端：从 4 开始
```

实测：

| 请求头 | 返回 id |
| --- | --- |
| 无 | 1,2,3,4,5 |
| `Last-Event-ID: 3` | 4,5 |

**前提**：id 必须单调且服务端能据此定位。

### 3.4 `retry:`

```text
retry: 3000\n\n
```

- 单位毫秒
- 是**字段块**，不是事件（`data` 为空，客户端不派发）
- 浏览器收到后更新重连间隔

## 4. 边界条件

### 4.1 中途异常（实测）

| 观察者 | 结果 |
| --- | --- |
| 客户端 | 200 + 2 个事件，连接断开 |
| 浏览器 | 按 `retry` 自动重连 → 可能死循环重放 |
| 严格测试 | `RuntimeError` 暴露 |

**这就是必须用 `event: error` 的原因**：裸异常会让客户端以为「网络抖动」，无限重连。

### 4.2 浏览器重连算法（规范描述）

```text
断线 → 等待 retry（默认约 3s）→ 重新发起 GET，带 Last-Event-ID
```

**未实测**（需要真实浏览器）。文档标注为规范描述。

### 4.3 连接数

| 场景 | 限制 |
| --- | --- |
| 同域 SSE（HTTP/1.1）| 浏览器通常 6 个/域 |
| HTTP/2 | 多路复用，限制放宽 |

实践：一个页面只用 1 条 SSE 流，用 `event` 分流。

### 4.4 缓冲与压缩

| 中间层 | 行为 | 对策 |
| --- | --- | --- |
| Nginx 默认 | 缓冲 | `X-Accel-Buffering: no` |
| GZip | 块被攒 | 排除 SSE 端点 |
| CDN | 缓存 | `Cache-Control: no-cache` |

### 4.5 鉴权

`EventSource` **不能**带自定义头。可选方案：

| 方案 | 说明 |
| --- | --- |
| Cookie | 同域自动带，最简单 |
| Query token | `?token=...`（会进日志，慎用）|
| Fetch + 手写解析 | 绕开 `EventSource`，可带 Authorization |

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 忘空行 | 事件不触发 | `\n\n` | 实测 |
| 用 `\r\n\r\n` | 解析异常 | `\n\n` | `[E1]` |
| `data` 里放裸换行 | 被拆成多事件 | 单行 JSON | 实测 |
| 无 `no-cache` | 被缓存 | 加头 | 实测 |
| 无 `X-Accel-Buffering` | Nginx 缓冲 | 加头 | 实测 |
| 裸抛异常 | 无限重连 | `event: error` | 实测 |
| 无 `id` | 重放 | 带 `id` | 实测 |
| 无心跳 | 空闲被断 | `: ping` | `[E2]` |
| `EventSource` 带 Authorization | 不支持 | cookie | `[E2]` |
| 用 POST 开流 | `EventSource` 只 GET | GET | `[E2]` |
| 开 GZip | 失去实时 | 排除 | 第 53 章 |
| 同域 >6 条流 | 连接占满 | 单流 + `event` | `[E2]` |
| `retry` 当事件字段 | 进 data | 独立块 | 实测 |
| 每个 token 一个连接 | 连接爆炸 | 复用 | 实测 |
| 用 SSE 传二进制 | 只能文本 | base64 / WebSocket | `[E1]` |
| 不 `close()` | 连接泄漏 | 客户端关闭 | `[E2]` |
| `error` 事件名冲突 | 与连接错误混淆 | 加前缀 | 实测 |
| SSE 里做长事务 | 锁到流结束 | 先查后流 | 第 57 章 |
| SSE 端点没排除在 GZip 之外 | 压缩缓冲导致成批到达 | 按路径排除压缩 | 第 53 章 |

## 6. 最佳实践与编码建议

### 6.1 事件协议

```json
{"seq": 3, "type": "token", "text": "你"}
{"seq": 4, "type": "done"}
{"seq": 5, "type": "error", "code": "INDEX_DOWN", "message": "..."}
```

| 字段 | 作用 |
| --- | --- |
| `seq` | 与 `id:` 一致，便于对账 |
| `type` | 业务分流（代替 `event:`）|
| `code` | 机器可读错误码 |

### 6.2 心跳

```python
async def gen():
    while True:
        yield ": ping\n\n"
        await asyncio.sleep(20)
```

| 参数 | 建议 |
| --- | --- |
| 间隔 | 15~30s |
| 形式 | 注释行（不产生事件）|

### 6.3 服务端模板

```python
async def gen():
    last = start
    try:
        async for item in source():
            last = item["seq"]
            yield sse(json.dumps(item, ensure_ascii=False), event_id=last)
    except Exception as exc:
        yield sse(
            json.dumps({"type": "error", "message": str(exc)}, ensure_ascii=False),
            event="app-error",
        )
```

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[E1]` | 规范 | https://html.spec.whatwg.org/multipage/server-sent-events.html | SSE 格式与解析 |
| `[E2]` | 文档 | https://developer.mozilla.org/zh-CN/docs/Web/API/EventSource | 浏览器 API 与重连 |
| `[E3]` | 官方文档 | https://fastapi.tiangolo.com/zh/tutorial/server-sent-events/ | FastAPI SSE |

> **核对状态**：`[E1]`–`[E3]` 为规范/文档链接，**本次未逐页直连复核**；媒体类型与响应头、事件结构、空行分隔、自定义事件名、`id` 递增、`Last-Event-ID` 续传、多行 `data`、注释行、`retry` 字段、`error` 事件、逐条到达时间、中途异常两种模式均为本机实测，`examples/verify.py` 复现 14/14 通过。真实浏览器重连算法、6 连接上限、`EventSource` 鉴权、Nginx 缓冲**未实测**（文档中标注为规范/经验值）。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] SSE 与 WebSocket 的分工
- [ ] 四类字段与空行规则
- [ ] `data` 追加 vs `event` 覆盖
- [ ] `id` 与 `Last-Event-ID` 的配合
- [ ] 为什么必须用 `event: error`

**能写出（代码层）**：

- [ ] `sse()` 拼接函数
- [ ] 打字机生成器
- [ ] 心跳
- [ ] 续传逻辑
- [ ] 客户端解析器

**能判断（避坑层）**：

- [ ] 看到没空行 → 指出事件不触发
- [ ] 看到裸异常 → 指出重连死循环
- [ ] 看到无 `X-Accel-Buffering` → 指出代理缓冲
- [ ] 看到 `EventSource` 带 token → 指出不支持
- [ ] 看到多条 SSE 流 → 指出连接数上限

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 14/14
- [ ] 浏览器 `EventSource` 看到逐字出现
- [ ] 手工 `curl -H "Last-Event-ID: 3"` 验证续传

## 9. 下一章衔接

第 63 章 `WebSocket 基础`：`@app.websocket`、`accept/receive/send`、双向通信、心跳与断连、`WebSocketDisconnect`。

本章留下的伏笔：

1. SSE 只能服务端推（62）→ 63 解决双向。
2. 断线重连（62）→ 63 需要自己实现。
3. 连接数上限（62）→ 63 一条连接搞定多路。