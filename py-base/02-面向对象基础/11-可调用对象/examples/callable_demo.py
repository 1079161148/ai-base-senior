"""第 11 章示例：__call__ 让实例像函数一样调用。"""

class Tool:
    """带名字的工具，实例可直接调用。"""
    def __init__(self, name):
        self.name = name
        self.call_count = 0

    def __call__(self, argument):
        self.call_count = self.call_count + 1
        return self.name + ":" + argument

search = Tool("search")
print("实例可调用:", callable(search))
print("调用结果:", search("AI news"))
print("调用次数:", search.call_count)
print("函数可调用:", callable(len))
print("类可调用:", callable(Tool))
