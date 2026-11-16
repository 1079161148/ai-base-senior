"""第 19 章示例：ABC 强制子类实现接口。"""

import abc

class Tool(abc.ABC):
    """工具接口。"""
    @abc.abstractmethod
    def run(self, argument):
        """执行工具并返回结果。"""

class Search(Tool):
    """搜索工具。"""
    def run(self, argument):
        return "result:" + argument

print("结果:", Search().run("AI news"))
print("isinstance:", isinstance(Search(), Tool))
print("未实现的抽象方法:", Tool.__abstractmethods__)
