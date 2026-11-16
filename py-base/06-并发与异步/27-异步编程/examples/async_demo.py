"""第 27 章示例：gather 并发执行多个协程。"""

import asyncio

async def fetch(name, delay):
    """模拟不同耗时的工具调用 [R1]。"""
    await asyncio.sleep(delay)
    return name + ":ok"

async def main():
    """并发取回结果，按输入顺序汇总。"""
    results = await asyncio.gather(
        fetch("search", 0.02),
        fetch("cache", 0.01),
    )
    print("结果:", results)

asyncio.run(main())
