"""第 09 章示例：类型、身份与 isinstance。"""

class ToolCall:
    """一次工具调用。"""
    def __init__(self, name):
        self.name = name

call = ToolCall("search")
print("对象类型:", type(call).__name__)
print("类的类型:", type(ToolCall).__name__)
print("isinstance:", isinstance(call, ToolCall))
print("继承链:", [item.__name__ for item in ToolCall.__mro__])
print("身份不同:", id(call) != id(ToolCall("search")))
