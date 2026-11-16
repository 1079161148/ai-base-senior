"""第 24 章示例：asyncio.run 与事件循环回调。"""

import asyncio

async def main():
    """展示当前循环与 call_soon 调度 [R2]。"""
    loop = asyncio.get_running_loop()
    print("事件循环:", type(loop).__name__)
    loop.call_soon(print, "call_soon 回调已执行")
    await asyncio.sleep(0)
    print("让出控制权后继续")

asyncio.run(main())
