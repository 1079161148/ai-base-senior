"""第 32 章示例：只读获取调用栈信息。"""

import inspect

def tool_call(name):
    """返回当前栈帧中的函数名 [R3]。"""
    frame = inspect.currentframe()
    return {"function": frame.f_code.co_name, "argument": name}

print("栈帧:", tool_call("search"))
