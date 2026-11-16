"""第 05 章示例：函数定义、参数与返回值。"""

def build_report(tool_name, results, limit=3):
    """返回工具结果摘要；limit 控制保留条数。"""
    selected = results[:limit]
    return {"tool": tool_name, "count": len(selected), "items": selected}

def append_result(item, collected=None):
    """默认值为 None，避免可变默认值在多次调用间共享 [R1]。"""
    if collected is None:
        collected = []
    collected.append(item)
    return collected

print("报告:", build_report("search", ["a", "b", "c", "d"]))
print("关键字参数:", build_report(results=["x"], tool_name="cache", limit=1))
print("第一次:", append_result("a"))
print("第二次:", append_result("b"))
