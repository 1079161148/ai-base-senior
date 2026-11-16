"""第 01 章示例：一个 Agent 回合的数据流骨架。

只使用变量、字符串与 print()。本章尚未讲到函数、类与 import，
因此这里用「数据」而不是「逻辑」表达分层；后续章节会逐步把
这些占位替换成真实实现。

运行：
    python examples/agent_round.py
"""

# 1. 输入：来自客户端（TypeScript / 浏览器 / CLI）
user_message = "帮我查一下今天的 AI 新闻"

# 2. 计划：模型决定下一步动作（第 05 章函数、第 27 章异步编排）
plan = "调用 search 工具"

# 3. 工具结果：服务端执行工具后回填（第 11 章可调用对象、第 22/23 章库）
tool_result = "3 条相关新闻"

# 4. 输出：返回给客户端（第 21 章模块化、第 27 章异步 I/O）
answer = "找到 " + tool_result

print("用户输入:", user_message)
print("模型计划:", plan)
print("工具结果:", tool_result)
print("最终回答:", answer)
