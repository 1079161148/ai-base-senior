"""第 07 章示例：lambda 作为一次性小函数。"""

tool_costs = [("search", 3), ("cache", 1), ("translate", 2)]
by_cost = sorted(tool_costs, key=lambda item: item[1])
by_name = sorted(tool_costs, key=lambda item: item[0])
print("按成本:", by_cost)
print("按名称:", by_name)

def make_multiplier(factor):
    """lambda 可引用包含作用域的变量 [R1]。"""
    return lambda value: value * factor

double = make_multiplier(2)
print("倍增:", double(5))
