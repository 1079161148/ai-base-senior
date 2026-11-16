"""第 20 章示例：类型标注只是元数据。"""

def build_report(tool_name: str, results: list[str], limit: int = 3) -> dict:
    """返回工具结果摘要 [R1]。"""
    return {"tool": tool_name, "items": results[:limit]}

report: dict = build_report("search", ["a", "b", "c", "d"])
print("结果:", report)
print("注解:", build_report.__annotations__)
