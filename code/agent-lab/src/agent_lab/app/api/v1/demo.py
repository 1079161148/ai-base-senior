"""演示用 SSE 流式接口（假数据）。

**为什么先做假的**：S0 不引入 LLM，先把「流」这条链路打通 ——

    Python 异步生成器 → StreamingResponse → 浏览器 ReadableStream → 逐字渲染

链路通了，S1 只需要把 `yield` 的内容换成模型返回的 delta，其余一行不用改。

**SSE 协议只要记住三条**：

1. 每条消息是 `data: <payload>` + **两个换行**；少一个 `\\n` 浏览器就不会触发事件
2. 响应头必须是 `Content-Type: text/event-stream`
3. 有代理（Nginx / 网关）时要关缓冲，否则前端会"沉默几秒后一次性收到全部内容"
"""

import asyncio
from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

from ...core.sse import encode as sse

router = APIRouter(prefix="/demo", tags=["demo"])

DEFAULT_TEXT = "你好，我是流式输出的演示内容。注意看文字是一个一个出现的。"


@router.get("/stream", summary="SSE 流式演示（假数据）")
async def stream(
    # 用 Annotated 而不是 `text: str = Query(default=...)`：
    #
    # Python 的默认参数「在函数定义时求值一次」，所以 `= Query(...)` 属于
    # 「默认值位置调用函数」—— 检查器 reportCallInDefaultInitializer 会拦这种模式。
    # 这次能跑通是因为 FastAPI 只把它当元数据读取，但模式本身容易埋雷
    # （同一份元数据被所有调用共享）。
    #
    # Annotated 把元数据放进「类型标注」，默认值仍由签名提供，语义如实反映：
    #   类型是 str，约束是 max_length=200，默认值是 DEFAULT_TEXT。
    # 这也是 FastAPI 当前官方推荐的写法。
    text: Annotated[
        str,
        Query(
            max_length=200,  # 边界：不设上限的话，一个超长文本能把连接占用很久
            description="要逐字推送的文本",
        ),
    ] = DEFAULT_TEXT,
) -> StreamingResponse:
    async def event_generator() -> AsyncGenerator[str, None]:
        for index, char in enumerate(text):
            # 注意是 asyncio.sleep，不是 time.sleep ——
            # 后者会阻塞整个事件循环，期间所有请求都排队
            await asyncio.sleep(0.06)
            yield sse({"delta": char, "index": index})

        # 最后一条携带元信息：前端据此结束"生成中"状态并显示用量
        yield sse(
            {
                "done": True,
                "usage": {"chars": len(text), "cost_cny": round(0.0001 * len(text), 6)},
            }
        )

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # 关键：关掉 Nginx 一类代理的响应缓冲
        },
    )
