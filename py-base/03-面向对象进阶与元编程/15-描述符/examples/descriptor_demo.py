"""第 15 章示例：一个最小数据描述符。"""

class Logged:
    """把值存在实例字典里，并打印读写 [R1]。"""
    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__.get("_value")

    def __set__(self, instance, value):
        print("写入:", value)
        instance.__dict__["_value"] = value

class Tool:
    name = Logged()

tool = Tool()
tool.name = "search"
print("读取:", tool.name)
print("实例字典:", tool.__dict__)
