# 62 SSE

## 一句话结论

SSE 就是「按格式写的纯文本流」：`event:` / `id:` / `retry:` / `data:` 四类字段，**空行**表示事件结束，`Content-Type` 是 `text/event-stream; charset=utf-8`。实测打字机效果逐条到达 **0/65/127/189ms**；带 `id` 时浏览器断线会自动重连并带上 `Last-Event-ID`，服务端实测 **`Last-Event-ID: 3` → 从第 4 条继续**。中途抛异常仍然是 200 + 已发出的事件，浏览器会按 `retry` 自动重连——所以错误要用 `event: error` 表达，不要裸抛。

## 最小可运行案例

```python
import json
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()


def sse(data: str, event: str | None = None, event_id: int | None = None) -> str:
    lines = []
    if event:
        lines.append(f"event: {event}")
    if event_id is not None:
        lines.append(f"id: {event_id}")
    for line in data.split("\n"):
        lines.append(f"data: {line}")
    return "\n".join(lines) + "\n\n"   # 空行结束事件


@app.get("/sse/chat")
def chat() -> StreamingResponse:
    async def gen() -> AsyncIterator[str]:
        for char in "你好":
            yield sse(json.dumps({"text": char}, ensure_ascii=False))
        yield sse(json.dumps({"done": True}), event="done")

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )
```

客户端（浏览器）：

```javascript
const source = new EventSource("/sse/chat");
source.onmessage = (event) => console.log(JSON.parse(event.data));
source.addEventListener("done", () => source.close());
```

## 怎么跑

```powershell
cd "10-实时流式\62-SSE\examples"
uv sync
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] 媒体类型与头 -> text/event-stream; charset=utf-8 + no-cache + no-buffering
[PASS] 打字机事件 -> 3 个事件
[PASS] data 是 JSON -> 3 条 JSON + done
[PASS] 空行分隔 -> 3 个事件 / 3 个空行
[PASS] 自定义事件名 -> token×3 + done，id 1/2/3
[PASS] id 递增 -> 1..5
[PASS] Last-Event-ID 续传 -> 从 4 续传
[PASS] 多行 data -> '第一行\n第二行'
[PASS] 注释行不出事件 -> 2 条注释被忽略，2 个事件
[PASS] retry 字段 -> retry=3000，2 个事件
[PASS] error 事件 -> 索引不可用
[PASS] 逐条到达 -> 到达 0/65/127/189ms
[PASS] 中途异常截断 -> 200 + 2 个事件后断开
[PASS] 异常确实发生 -> 第 3 条之前崩了

结果：14/14 通过
```

## 核心 API 速查

| 字段 | 必需 | 作用 |
| --- | --- | --- |
| `data:` | 是 | 载荷，多行会被拼成 `\n` |
| `event:` | 否 | 事件名，默认 `message` |
| `id:` | 否 | 浏览器记为 `lastEventId`，重连时回传 |
| `retry:` | 否 | 重连间隔（毫秒） |
| `: xxx` | 否 | 注释，客户端忽略，用于心跳 |

| 响应头 | 值 | 原因 |
| --- | --- | --- |
| `Content-Type` | `text/event-stream` | SSE 协议 |
| `Cache-Control` | `no-cache` | 防缓存 |
| `X-Accel-Buffering` | `no` | 防 Nginx 缓冲 |
| `Connection` | `keep-alive` | 长连接 |

| 实测 | 值 |
| --- | --- |
| 4 个事件到达 | 0 / 65 / 127 / 189ms |
| `Last-Event-ID: 3` | 从 4 开始 |
| 多行 data | `第一行\n第二行` |
| 注释行 | 不产生事件 |
| 中途异常 | 200 + 2 个事件 |
| `Content-Length` | 无 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 忘空行 | 事件一个都不触发 | `+ "\n\n"` |
| 用 `\r\n\r\n` | 部分客户端解析异常 | 统一 `\n\n` |
| `data` 里放裸 JSON 含换行 | 事件被拆成多个 | `json.dumps` 后单行 |
| 忘 `no-cache` | 中间层缓存，收到旧流 | 加头 |
| 忘 `X-Accel-Buffering` | Nginx 攒够才发 | 加头 |
| 裸抛异常 | 浏览器自动重连死循环 | `event: error` + 正常结束 |
| 无 `id` | 断线后重复推送 | 带 `id` + `Last-Event-ID` |
| 无心跳 | 中间设备断开空闲连接 | `: ping` 每 15~30s |
| 用 `EventSource` 带 `Authorization` | 不支持自定义头 | cookie 或 query token |
| 用 POST 开 SSE | `EventSource` 只支持 GET | GET + 参数 |
| 开 GZip | 缓冲，失去实时性 | 排除该端点 |
| 同域开 >6 个 SSE | 浏览器连接数上限 | 复用一条流、分事件类型 |
| 在 SSE 里做长事务 | 锁持有到流结束 | 先查后流 |
| 客户端不处理重连 | 断线后数据缺失 | 用 `Last-Event-ID` |
| `retry` 写成事件字段 | 被当成 data | 独立一行 |
| 每个 token 一个连接 | 连接爆炸 | 一条流 + `event` 分流 |
| 用 SSE 传二进制 | 只能文本 | base64 或改 WebSocket |
| 忘了关闭事件源 | 页面切走后连接泄漏 | `source.close()` |

## 毕业自查

- [ ] 能默写 SSE 的四类字段与空行规则
- [ ] 能解释 `id` 与 `Last-Event-ID` 的配合
- [ ] 能说清为什么要加三个响应头
- [ ] 能用注释行做心跳
- [ ] 能对比 SSE 与 WebSocket 的取舍
- [ ] 动手题一：用浏览器 `EventSource` 跑通打字机
- [ ] 动手题二：断网 3 秒后看 `Last-Event-ID` 是否续传

> 想看 SSE 规范的字段细节、浏览器重连算法、HTTP/1.1 连接数限制、鉴权方案、18 条坑，继续读 [`base.md`](./base.md)。