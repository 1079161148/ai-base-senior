"""第 08 章示例：类、实例与 __init__。"""

class ToolCall:
    """一次工具调用的记录。"""

    kind = "tool"

    def __init__(self, name, arguments):
        self.name = name
        self.arguments = arguments

    def describe(self):
        """返回可读描述。"""
        return self.kind + ":" + self.name + "=" + str(self.arguments)

call = ToolCall("search", {"query": "AI news"})
print("实例属性:", call.name, call.arguments)
print("类属性:", call.kind)
print("方法:", call.describe())
