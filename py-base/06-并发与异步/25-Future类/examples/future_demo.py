"""第 25 章示例：Future 的结果与状态。"""

import concurrent.futures

def fetch(name):
    """模拟一次工具调用 [R1]。"""
    return name + ":ok"

with concurrent.futures.ThreadPoolExecutor(max_workers=2) as pool:
    future = pool.submit(fetch, "search")
    print("结果:", future.result())
    print("是否完成:", future.done())
    print("异常:", future.exception())
