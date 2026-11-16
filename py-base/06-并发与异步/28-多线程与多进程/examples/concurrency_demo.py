"""第 28 章示例：ThreadPoolExecutor 并行执行 I/O 型任务。"""

import concurrent.futures

def fetch(name):
    """模拟一次工具调用（无真实 I/O）[R3]。"""
    return name + ":ok"

with concurrent.futures.ThreadPoolExecutor(max_workers=3) as pool:
    results = list(pool.map(fetch, ["search", "cache", "translate"]))

print("结果:", results)
