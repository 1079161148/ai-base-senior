"""第 03 章示例：基本语法综合演练。

只用本章语法：字面量、变量、运算符、字符串、条件、循环、print()。
函数 / 类 / import 分别在第 05 / 08 / 21 章展开。

运行（在本章目录下）：
    python examples/basics_demo.py
"""

# 1. 字面量与变量：模拟一次 Agent 回合的原始记录 [R1]
user_message = "查一下今天的 AI 新闻"
tool_call_count = 3
response_seconds = 1.5

print("用户输入:", user_message)
print("工具调用次数:", tool_call_count)
print("单次耗时:", response_seconds, "秒")

# 2. 算术与比较运算 [R1]
total_seconds = response_seconds * tool_call_count
print("估算总耗时:", total_seconds, "秒")
print("是否需要重试:", total_seconds > 10)

# 3. 字符串：切片、长度、不可变 [R1]
prefix = user_message[:3]
print("开头三个字符:", prefix)
print("消息长度:", len(user_message))

# 4. 条件分支 [R2]
if tool_call_count == 0:
    status = "未调用工具"
elif tool_call_count < 5:
    status = "正常"
else:
    status = "调用过多"
print("状态:", status)

# 5. for + continue：统计非空格字符 [R2]
non_space_chars = 0
for char in user_message:
    if char == " ":
        continue
    non_space_chars = non_space_chars + 1
print("非空格字符数:", non_space_chars)

# 6. range + break + 循环 else；break 触发时 else 不执行 [R2]
for attempt in range(1, 4):
    print("第", attempt, "次尝试")
    if attempt == 2:
        print("达到上限，提前结束")
        break
else:
    print("全部尝试完成")

# 7. while：倒计数 [R1]
remaining = tool_call_count
while remaining > 0:
    print("剩余待处理:", remaining)
    remaining = remaining - 1

# 8. 与 None 比较用 is，不用 == [R3]
missing_value = None
print("用 is None 判定:", missing_value is None)
