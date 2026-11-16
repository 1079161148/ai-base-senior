"""第 12 章示例：type 动态建类与最小自定义元类。"""

def run(self, argument):
    return self.name + ":" + argument

DynamicTool = type("DynamicTool", (), {"name": "search", "run": run})
print("动态类:", DynamicTool().run("AI news"))

class RegisterMeta(type):
    """记录被创建的类，仅用于演示机制 [R1]。"""
    created = []

    def __new__(mcls, name, bases, namespace):
        cls = super().__new__(mcls, name, bases, namespace)
        mcls.created.append(name)
        return cls

class Index(metaclass=RegisterMeta):
    pass

class Query(metaclass=RegisterMeta):
    pass

print("已注册:", RegisterMeta.created)
print("类的类型:", type(Query).__name__)
