"""第 13 章示例：最小装饰器与 functools.wraps。"""

import functools

def log_call(func):
    """记录被装饰函数的调用，并保留其元数据 [R3]。"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print("调用:", func.__name__)
        return func(*args, **kwargs)
    return wrapper

@log_call
def search(query):
    """返回模拟搜索结果。"""
    return ["result:" + query]

print("结果:", search("AI news"))
print("保留的函数名:", search.__name__)
print("保留的文档:", search.__doc__)
