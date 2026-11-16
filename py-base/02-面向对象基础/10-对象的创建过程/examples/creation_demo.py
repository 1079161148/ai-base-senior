"""第 10 章示例：__new__ 与 __init__ 的调用顺序。"""

class Traced:
    """打印创建过程的顺序。"""
    def __new__(cls, name):
        print("1 __new__:", name)
        instance = super().__new__(cls)
        return instance

    def __init__(self, name):
        print("2 __init__:", name)
        self.name = name

obj = Traced("search")
print("3 结果:", isinstance(obj, Traced), obj.name)
