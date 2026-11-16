"""第 16 章示例：try/except/else/finally 与具体异常。"""

def parse_limit(value):
    """把字符串转为正整数；非法输入抛 ValueError [R1]。"""
    number = int(value)
    if number <= 0:
        raise ValueError("limit 必须为正数")
    return number

for raw in ["5", "0", "abc"]:
    try:
        limit = parse_limit(raw)
    except ValueError as error:
        print("输入无效:", raw, "->", type(error).__name__)
    else:
        print("解析成功:", limit)
    finally:
        print("清理:", raw)
