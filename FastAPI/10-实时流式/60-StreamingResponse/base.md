# 60 StreamingResponse · 完整版（base.md）

> `README.md` 给你能跑的下载与推送示例；本文件把「ASGI 怎么一块块发、为什么没有 Content-Length、断开时生成器收到什么、块大小为什么能差 500 倍」拆开。学完这章，你能判断一个「下载卡住/内存爆了/首字节很慢」的流式接口到底错在哪。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 / FastAPI 0.146.0（本机实测） |
| 前置 | 第 53 章（GZip 与流式）、第 59 章（阻塞与线程池） |
| 覆盖范围 | `StreamingResponse`、同步/异步生成器、分块、断开清理、中途异常 |
| 明确不覆盖 | HTTP/2 多路复用、Range 断点续传、CDN 分片、WebSocket（63 章）|
| 学完验收 | 能跑通 `verify.py` 14/14、能解释 500 倍差距 |

## 0. 怎么用这份文件

**依据约定**：`` `[Sn]` `` 指向第 7 节；标「实测」的是本机真实输出。

**推荐顺序**：

```text
1 概念（第 1 节）    → 拼好再发 vs 边产边发
2 机制（第 2 节）    → ASGI body 消息
3 API（第 3 节）     → 参数与生成器形态
4 边界（第 4 节）    → 中途异常、断开、块大小
5 注意事项（第 5 节）→ 18 条对照
6 最佳实践（第 6 节）→ 分块策略
```

## 1. 概念：两种 body 发送方式

| 方式 | 时机 | `Content-Length` | 内存 |
| --- | --- | --- | --- |
| `Response(content=...)` | 全部准备好再发 | 有 | O(body) |
| `StreamingResponse(iterator)` | 边产边发 | **无** | O(chunk) |

实测头对比：

```text
普通 Response:  content-length: 1234
流式 Response:  （无 content-length）
```

没有长度意味着：浏览器不知道总大小、不能显示精确进度、无法做 Range 请求。

## 2. 机制：ASGI 的 body 消息

```text
send({"type": "http.response.start", "status": 200, "headers": [...]})
send({"type": "http.response.body", "body": b"chunk-0\n", "more_body": True})
send({"type": "http.response.body", "body": b"chunk-1\n", "more_body": True})
send({"type": "http.response.body", "body": b"chunk-2\n", "more_body": True})
send({"type": "http.response.body", "body": b"", "more_body": False})
```

**关键**：`http.response.start` 一旦发出，状态码和头就固定了。

### 2.1 同步 vs 异步生成器

| 形态 | Starlette 处理 | 开销 |
| --- | --- | --- |
| `async def` + `yield` | 直接 `async for` | 低 |
| `def` + `yield` | `iterate_in_threadpool` | 每次 next 一趟线程池 |

实测：同步生成器逐行 yield，每块约 **0.37ms**（线程池往返）。

### 2.2 分块到达证据（实测）

```
chunk 0ms  b'chunk-0\n'
chunk 73ms b'chunk-1\n'
chunk 135ms b'chunk-2\n'
```

服务端 `await asyncio.sleep(0.06)` 的间隔被如实反映到客户端。

## 3. API 逐个拆解

| 参数 | 说明 |
| --- | --- |
| `content` | 生成器 / 迭代器 / 异步生成器 |
| `status_code=200` | 发送前有效 |
| `headers` | `Content-Disposition`、`X-Accel-Buffering` |
| `media_type` | 自动补 `charset=utf-8` |
| `background` | 响应发完后的任务 |

### 3.1 文本与二进制（实测）

| yield 的类型 | 行为 |
| --- | --- |
| `str` | UTF-8 编码后发送 |
| `bytes` | 原样发送 |
| 混用 | 可以，实测正常 |

建议统一，避免长度计算混乱。

### 3.2 下载头

```python
headers={"Content-Disposition": 'attachment; filename="items.csv"'}
```

- `attachment` 触发下载；`inline` 让浏览器直接打开
- 文件名含中文需 `filename*=UTF-8''...`
- 不能设 `Content-Length`（除非你自己先算好）

## 4. 边界条件

### 4.1 中途异常（实测）

```python
async def gen():
    yield "part-1\n"
    yield "part-2\n"
    raise RuntimeError("炸了")
```

| 观察者 | 结果 |
| --- | --- |
| 客户端 | 200 + `part-1\npart-2\n`，连接截断 |
| TestClient（宽松）| 同上，异常被记录 |
| TestClient（严格）| 抛出 `RuntimeError: 炸了` |

**结论**：业务失败必须在**开流之前**判断完（参数、权限、数据存在性），开流后只能记日志 + 截断。

### 4.2 客户端断开（实测）

| 场景 | `gen:close` |
| --- | --- |
| 正常消费完 | 执行 |
| 提前 `break` | **执行** |

实测提前断开的事件序列：

```text
gen:start → gen:yield:0 → gen:yield:1 → gen:close   （gen:yield:2 不会执行）
```

所以 `try/finally` 是可靠的清理点：关文件、关数据库连接都放这里。

### 4.3 块大小（实测）

| 写法 | 块数（2000 行）| 耗时 |
| --- | --- | --- |
| 逐行 yield | 2001 | 770ms |
| 每 1000 行一块 | 3 | 1ms |

放大到 20 万行：

| 写法 | 耗时 |
| --- | --- |
| 逐行 yield | **74.4 秒** |
| 批量 yield | **0.14 秒** |

差 500 倍，全部花在线程池往返上。

**经验值**：

| 场景 | 块大小 |
| --- | --- |
| 文本行（CSV/JSONL）| 500~2000 行 或 32~64KB |
| 二进制文件 | 64KB~1MB |
| 实时事件（SSE）| 单条即一块，别攒 |

### 4.4 `await` 点与取消

异步生成器里的 `await` 是取消的响应点。客户端断开时：

| 生成器类型 | 收到什么 |
| --- | --- |
| `async def` + `yield` | `GeneratorExit` / `CancelledError` |
| `def` + `yield` | `GeneratorExit`（线程池里）|

两者的 `finally` 都会执行，但**不要**在 `except GeneratorExit` 里再 `yield`（会 `RuntimeError`）。

## 5. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 逐行 yield | 20 万行 74s（实测）| 攒批 | 实测 |
| 设 `Content-Length` | 长度不符导致截断 | 流式不设 | 实测 |
| 开流后再校验参数 | 只能截断 | 先校验 | 实测 |
| 生成器无 `finally` | 句柄泄漏 | `try/finally` | 实测 |
| 同步生成器跑阻塞 IO | 占线程池 | 异步 + `to_thread` | 第 59 章 |
| 一次 yield 全文件 | 内存爆 | 分块 | `[S2]` |
| 流式端点开 GZip | 缓冲，失去实时性 | 排除 | 第 53 章 |
| Nginx 默认缓冲 | 客户端收不到实时块 | `X-Accel-Buffering: no` | `[S3]` |
| 用 `.get()` 测流 | 看不到分块 | `client.stream` | 实测 |
| 用 `.text` 断言二进制 | 解码错 | `.content` | 实测 |
| 生成器里提交事务 | 事务跨发送期 | 依赖层管 | 第 57 章 |
| 流式里做长事务 | 锁持有时间长 | 先查后流 | 第 57 章 |
| 流式返回 JSON | 丢长度、无收益 | 普通响应 | `[S1]` |
| `yield None` | `TypeError` | 只 yield `str`/`bytes` | 实测 |
| 中途异常不记日志 | 线上只有截断 | 记日志再抛 | 实测 |
| 空生成器 | 200 + 空 body | 先判空 | `[S1]` |
| 依赖断开做回滚 | 生成器不在事务里 | 别依赖 | 实测 |
| 大 chunk（100MB）| 首字节延迟高 | 64KB~1MB | `[S2]` |
| `try/except` 吞掉生成器异常 | 客户端只看到截断，日志也没有 | 记录后继续抛 | 实测 |

## 6. 最佳实践与编码建议

### 6.1 导出大文件

```python
def export_rows() -> Iterator[str]:
    buffer: list[str] = []
    for row in query_rows():          # 数据库游标
        buffer.append(to_csv_line(row))
        if len(buffer) >= 1000:
            yield "".join(buffer)
            buffer.clear()
    if buffer:
        yield "".join(buffer)
```

### 6.2 回调式实时推送

```python
async def gen():
    queue: asyncio.Queue[str] = asyncio.Queue()
    ...
    while True:
        yield await queue.get()
```

配 `X-Accel-Buffering: no`、`Cache-Control: no-cache`。

### 6.3 检查清单

| 检查项 | 原因 |
| --- | --- |
| 块大小 ≥ 32KB | 避免线程池往返 |
| `try/finally` | 释放资源 |
| 先校验后开流 | 状态码改不了 |
| 无 `Content-Length` | 流式没有总长度 |
| 日志记中途异常 | 客户端看不到 |
| `X-Accel-Buffering: no` | 反向代理会缓冲 |

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[S1]` | 官方文档 | https://fastapi.tiangolo.com/zh/advanced/custom-response/#streamingresponse | `StreamingResponse` |
| `[S2]` | 文档 | https://www.starlette.io/responses/#streamingresponse | 生成器与分块 |
| `[S3]` | 文档 | https://nginx.org/en/docs/http/ngx_http_proxy_module.html#proxy_buffering | 代理缓冲 |

> **核对状态**：`[S1]`–`[S3]` 为官方文档链接，**本次未逐页直连复核**；响应头、无 `Content-Length`、分块到达时间、二进制字节数、`str`/`bytes` 混用、中途异常两种模式、正常/断开清理、逐行与批量块数与耗时均为本机实测，`examples/verify.py` 复现 14/14 通过。真实 Nginx 缓冲、Range 续传、HTTP/2、`GeneratorExit` 的具体异常类型细节**未实测**（文档中标为推导）；耗时是单机中位数，**绝对值随机器变化**。

## 8. 毕业自查清单

**能说清（概念层）**：

- [ ] 为什么流式响应没有 `Content-Length`
- [ ] 为什么中途异常改不了状态码
- [ ] 断开时 `finally` 为什么一定会跑
- [ ] 块大小为什么影响吞吐 500 倍
- [ ] 同步生成器的线程池开销从哪来

**能写出（代码层）**：

- [ ] CSV 下载端点
- [ ] 二进制分块端点
- [ ] 攒批生成器
- [ ] `try/finally` 清理
- [ ] `client.stream` 验收

**能判断（避坑层）**：

- [ ] 看到逐行 yield → 指出性能问题
- [ ] 看到开流后校验 → 指出改不了状态码
- [ ] 看到无 `finally` → 指出泄漏
- [ ] 看到流式 + GZip → 指出缓冲
- [ ] 看到 `.text` 测二进制 → 指出解码错

**能跑通（验收层）**：

- [ ] `uv run python verify.py` 输出 14/14
- [ ] 用 `uvicorn` 起服务，`curl -N` 观察逐块输出
- [ ] 把 `/download/csv` 改成批量，块数从 2001 降到 3

## 9. 下一章衔接

第 61 章 `JSON Lines 流`：把「一行一个 JSON」做成可消费的接口、`application/x-ndjson`、客户端逐行解析、中途错误怎么用一行表达、和普通 JSON 数组的区别。

本章留下的伏笔：

1. 流式 chunk（60）→ 61 的每一行就是一个 chunk。
2. 中途异常只能截断（60）→ 61 用 `{"error": ...}` 行表达。
3. 块大小（60）→ 61 单行即一块，别攒。