"""第 17 章示例：生成器惰性产出。"""

def tool_names(names, prefix=None):
    """按可选前缀过滤工具名，惰性产出 [R1]。"""
    for name in names:
        if prefix is None or name.startswith(prefix):
            yield name

source = ["search", "cache", "summarize"]
print("全部:", list(tool_names(source)))
print("前缀 s:", list(tool_names(source, "s")))

upper = (name.upper() for name in source)
print("第一个:", next(upper))
print("剩余:", list(upper))
