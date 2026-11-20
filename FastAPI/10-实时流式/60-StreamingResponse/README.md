# 60 StreamingResponse

## 一句话结论

`StreamingResponse` 把生成器交给 ASGI 边产边发：实测 3 块间隔 **0/77/139ms** 到达，响应头**没有 `Content-Length`**。代价是响应一旦开始就改不了状态码——生成器中途抛 `RuntimeError`，客户端拿到的是 **200 + 前两块 + 截断**。另一个大坑是**块大小**：同步生成器每 `yield` 一次要走一趟线程池（约 0.37ms），20 万行逐行 yield 要 **74 秒**，改成每 1000 行一块只需 **0.14 秒**。

## 最小可运行案例

```python
from typing import Iterator

from fastapi import FastAPI
from fastapi.responses import StreamingResponse

app = FastAPI()


@app.get("/export.csv")
def export() -> StreamingResponse:
    def rows() -> Iterator[str]:
        yield "id,name\n"
        for i in range(1000):
            yield f"{i},row-{i}\n"

    return StreamingResponse(
        rows(),
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="export.csv"'},
    )
```

## 怎么跑

```powershell
cd "10-实时流式\60-StreamingResponse\examples"
uv sync
uv run uvicorn main:app --reload
uv run python verify.py
```

预期输出：

```text
[PASS] CSV 响应头 -> text/csv; charset=utf-8 + 无 Content-Length
[PASS] CSV 内容 -> 3 行数据
[PASS] 同步生成器可用 -> 同步 yield 可用（线程池迭代）
[PASS] 分块到达 -> 块间隔 0/77/139ms
[PASS] 二进制大小 -> 200000 字节 / 4 块
[PASS] str/bytes 混用 -> str + bytes 混用正常
[PASS] 中途异常截断 -> 200 + 2 块后截断
[PASS] 中途异常确实发生 -> 第 3 块之前炸了
[PASS] 正常结束清理 -> gen:start → gen:yield:0 → gen:yield:1 → gen:yield:2 → gen:close
[PASS] 提前断开清理 -> gen:start → gen:yield:0 → gen:yield:1 → gen:close
[PASS] 逐行块数 -> 2001 块
[PASS] 批量块数 -> 3 块
[PASS] 批量更快 -> 逐行 770ms → 批量 1ms
[PASS] 无 Content-Length -> /download/csv, /download/binary, /stream/slow, /stream/headers

结果：14/14 通过
```

## 核心 API 速查

| 参数 | 作用 | 实测 |
| --- | --- | --- |
| `content` | 同步/异步生成器、可迭代对象 | 同步生成器会被丢进线程池 |
| `media_type` | 主类型，自动加 `charset=utf-8` | `text/csv; charset=utf-8` |
| `headers` | 附加头，如 `Content-Disposition` | 生效 |
| `status_code` | **发送前**有效 | 中途改不了 |

| 场景 | 写法 |
| --- | --- |
| 大文件下载 | 分块读文件，每块 64KB |
| 边查边发 | 异步生成器 + `await` |
| 二进制 | `yield b"..."` |
| 文本 | `yield "..."`（自动 UTF-8）|
| 清理资源 | 生成器里 `try/finally` |

| 实测 | 值 |
| --- | --- |
| 3 块到达时间 | 0 / 77 / 139ms |
| `Content-Length` | 不存在 |
| 中途异常 | 200 + 前两块 |
| 严格模式 | `RuntimeError` 暴露 |
| 提前断开 | `gen:close` 仍执行 |
| 逐行 2000 行 | 2001 块 / 770ms |
| 批量 2000 行 | 3 块 / 1ms |
| 逐行 20 万行 | 74 秒 |
| 批量 20 万行 | 0.14 秒 |

## 最容易踩的坑

| 错误写法 | 现象 | 正确写法 |
| --- | --- | --- |
| 逐行 `yield` | 20 万行 74 秒 | 攒批再 yield |
| 想用 `Content-Length` | 流式响应没有长度 | 去掉，或改普通 `Response` |
| 生成器里 `raise` 想返 500 | 状态码已发出，只能截断 | 先校验再开流 |
| 生成器里不写 `finally` | 连接/文件句柄泄漏 | `try/finally` 关闭 |
| 同步生成器里跑阻塞 IO | 占线程池 | 异步生成器 + `to_thread` |
| 一次 `yield` 整个文件 | 内存爆炸，失去流式意义 | 分块 |
| 混用 `str`/`bytes` 担心出错 | 实测可以 | 但建议统一 |
| 流式响应开 GZip | 缓冲导致失去流式 | 排除流式端点（第 53 章）|
| 依赖 `TestClient.get` 测流 | 一次性读完，看不到分块 | `client.stream` + `iter_raw` |
| 用 `.text` 断言二进制 | 解码错误 | `.content` |
| 在生成器里 `commit` | 事务边界错乱 | 事务放依赖 |
| 流式里做长事务 | 锁持有到发送完 | 先查完再开流 |
| 忘记 `X-Accel-Buffering: no` | Nginx 缓冲，客户端收不到实时块 | 加该头 |
| 用 `StreamingResponse` 返 JSON | 没必要，还丢 `Content-Length` | 普通响应模型 |
| 生成器返回 `None` | `TypeError` | 只 yield `str`/`bytes` |
| 中途异常不打日志 | 客户端只看到截断 | `try/except` 记日志再抛 |
| 空生成器 | 200 + 空 body | 先校验是否有数据 |
| 以为断开能触发业务回滚 | 生成器不在事务里 | 别依赖 |

## 毕业自查

- [ ] 能写出 CSV 下载端点
- [ ] 能解释为什么没有 `Content-Length`
- [ ] 能说清中途异常为什么改不了状态码
- [ ] 能用 `client.stream` 观察分块
- [ ] 知道为什么逐行 yield 会慢 500 倍
- [ ] 动手题一：把 `/download/csv` 改成读磁盘文件分块发送
- [ ] 动手题二：给流式端点加 `X-Accel-Buffering: no` 并用 Nginx 验证

> 想看 ASGI 的 `http.response.body` 消息、断开时的取消传播、`iterate_in_threadpool` 的开销、文件句柄清理、18 条坑，继续读 [`base.md`](./base.md)。