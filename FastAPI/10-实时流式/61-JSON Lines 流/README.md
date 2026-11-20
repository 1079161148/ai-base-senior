# 61 JSON Lines 流

## 一句话结论

JSON 数组必须**整体**解析，客户端要等最后一个 `]` 才能处理第一条；JSON Lines 每行一个独立 JSON 对象，来一行处理一行。实测：普通数组响应 `Content-Type: application/json`、body **1 行**、带 `Content-Length`；JSONL 响应 `application/jsonl`、**无** `Content-Length`、逐行到达 **0/51/97ms**。中途出错时状态码已经发出去了，只能用一行 `{"error": ...}` 表达失败——实测 3 条数据 + 1 条错误，客户端照样能逐行解析。

## 最小可运行案例

```python
import json
from typing import AsyncIterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()


def to_line(item: dict) -> str:
    return json.dumps(item, ensure_ascii=False, separators=(",", ":")) + "\n"


@app.get("/search.jsonl")
def search() -> StreamingResponse:
    async def gen() -> AsyncIterator[str]:
        for i in range(1, 6):
            yield to_line({"id": i, "title": f"结果 {i}"})
        yield to_line({"error": "后面没了", "code": "END"})

    return StreamingResponse(gen(), media_type="application/jsonl")
```

客户端：

```python
with httpx.stream("GET", url) as response:
    for line in response.iter_lines():
        if line:
            item = json.loads(line)
            print(item)
```

## 怎么跑

```powershell
cd "10-实时流式\61-JSON Lines 流\examples"
uv sync
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] JSON 数组单行 -> 1 行 / 有 Content-Length
[PASS] JSONL 媒体类型 -> application/jsonl + 无 Content-Length
[PASS] 行数与换行 -> 6 行，每行 `\n` 结尾
[PASS] 逐行可解析 -> 5 行全部可独立解析
[PASS] 字段完整 -> id/title/score
[PASS] 中文不转义 -> 中文原样输出
[PASS] 逐行到达 -> 到达 0/51/97ms
[PASS] 数组是整体的 -> 1 行 = 1 个完整数组
[PASS] 中途异常截断 -> 200 + 3 行后截断
[PASS] 异常确实发生 -> 索引在第 4 条之后崩了
[PASS] 错误行表达 -> 3 条数据 + 1 条错误
[PASS] 错误行终止 -> 错误行是最后一行
[PASS] 禁缓冲头 -> X-Accel-Buffering: no + no-cache
[PASS] limit 边界 -> 0/201 → 422

结果：14/14 通过
```

## 核心 API 速查

| 项 | JSON 数组 | JSON Lines |
| --- | --- | --- |
| `Content-Type` | `application/json` | `application/jsonl` |
| body 行数 | 1 | N |
| `Content-Length` | 有 | 无 |
| 解析方式 | `json.loads(整个body)` | 逐行 `json.loads` |
| 首条延迟 | 等全部 | 立刻 |
| 中途错误 | 整体失败可改状态码 | 只能发错误行 |

| 媒体类型 | 常见度 |
| --- | --- |
| `application/jsonl` | FastAPI 官方教程用这个 |
| `application/x-ndjson` | 社区事实标准 |
| `application/jsonlines` | 少见 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 用 `application/json` 发多行 | 客户端 `res.json()` 直接报错 | `application/jsonl` |
| 行末不加 `\n` | 最后一行与下一行粘连 | 每条 `+ "\n"` |
| `ensure_ascii=True` | 中文变 `\uXXXX`，体积翻倍 | `ensure_ascii=False` |
| 手动拼 JSON 字符串 | 引号/换行注入 | `json.dumps` |
| 先 `fetchall()` 再逐行 yield | 失去流式意义 | 游标逐行 |
| 中途异常静默截断 | 客户端以为正常结束 | 发 `{"error": ...}` 行 |
| 错误行之后继续发 | 客户端状态混乱 | 发完错误行 `return` |
| 不舍 `Content-Length` 却想要进度 | 拿不到总量 | 用 `X-Total-Count` 头 |
| 按 `split("\n")` 解析 | 末尾空行、CRLF | `iter_lines()` |
| 忽略 `iter_lines` 的空行 | `json.loads("")` 报错 | 过滤空行 |
| 代理缓冲 | 客户端成批收到 | `X-Accel-Buffering: no` |
| 用 GET 发敏感检索词 | 进日志/历史 | POST + 流式响应 |
| 每行一个巨型对象 | 单块过大 | 控制对象大小 |
| 客户端不设超时 | 流挂住不返回 | 读超时 + 心跳 |
| 把 JSONL 当 SSE 用 | 没有事件语义 | 要事件用 SSE（62 章）|
| 逐行 yield 生产太慢 | 块太小、往返多 | 攒批（60 章）|
| 不记录已发送条数 | 断点无法续传 | 带 `id` 字段 |
| 用 `json.loads` 解析流式整体 | 只能等结束 | 逐行 |

## 毕业自查

- [ ] 能说出 JSON 数组与 JSONL 的三点区别
- [ ] 能写出 JSONL 端点与客户端消费代码
- [ ] 能解释为什么错误要用「一行」表达
- [ ] 知道 `application/jsonl` 不带 charset，必须按 UTF-8 解码
- [ ] 能解释 `ensure_ascii=False` 的价值
- [ ] 动手题一：给每行加 `seq` 字段，客户端据此统计丢包
- [ ] 动手题二：把 `/search/json` 改成用 `X-Total-Count` 头返回总数

> 想看 NDJSON 规范细节、`iter_lines` 的分块重组、CRLF 与空行的处理、断点续传设计、18 条坑，继续读 [`base.md`](./base.md)。