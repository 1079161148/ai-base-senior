"""第 26 章示例：协程对象与 await。"""

import asyncio

async def fetch(name):
    """模拟一次异步工具调用 [R1]。"""
    await asyncio.sleep(0)
    return name + ":ok"

async def main():
    """展示协程对象与执行时机。"""
    coro = fetch("search")
    print("协程对象:", type(coro).__name__)
    print("结果:", await coro)

asyncio.run(main())
