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
import json
from collections.abc import AsyncGenerator

from fastapi import APIRouter, Query
from fastapi.responses import StreamingResponse

router = APIRouter(prefix="/demo", tags=["demo"])

DEFAULT_TEXT = "你好，我是流式输出的演示内容。注意看文字是一个一个出现的。"


def sse(payload: dict) -> str:
    """把 dict 编码成一条 SSE 消息。

    ensure_ascii=False：否则中文会变成 \\u4f60\\u597d，虽然浏览器能解，但调试时看不懂。
    """
    return f"data: {json.dumps(payload, ensure_ascii=False)}\n\n"


@router.get("/stream", summary="SSE 流式演示（假数据）")
async def stream(
    text: str = Query(
        default=DEFAULT_TEXT,
        max_length=200,  # 边界：不设上限的话，一个超长文本能把连接占用很久
        description="要逐字推送的文本",
    ),
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
