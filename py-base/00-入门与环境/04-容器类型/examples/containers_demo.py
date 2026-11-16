"""第 04 章示例：容器类型综合演练。

用到第 03 章的控制流与本章容器，不含函数 / 类 / import。
运行（在本章目录下）：
    python examples/containers_demo.py
"""

# 1. list：索引、切片、追加、成员测试 [R1] [R2]
tool_names = ["search", "summarize", "translate"]
tool_names.append("cache")
print("工具列表:", tool_names)
print("第一个:", tool_names[0], "最后两个:", tool_names[-2:])
print("是否包含 search:", "search" in tool_names)

# 2. 就地修改的方法返回 None，这是官方说明的设计原则 [R1]
returned = tool_names.sort()
print("sort 返回值:", returned)
print("排序后:", tool_names)

# 3. 赋值不复制数据，两个名字指向同一个列表 [R2]
alias = tool_names
alias.append("audit")
print("原列表也被改动:", tool_names)

# 4. 切片返回浅拷贝，改副本不影响原列表 [R2]
snapshot = tool_names[:]
snapshot.append("only_in_snapshot")
print("快照长度:", len(snapshot), "原列表长度:", len(tool_names))

# 5. list 推导式：映射与过滤 [R1]
lengths = [len(name) for name in tool_names]
long_names = [name for name in tool_names if len(name) > 7]
print("名称长度:", lengths)
print("长名称:", long_names)

# 6. tuple：不可变、序列解包、单元素必须有逗号 [R1]
endpoint = ("api.example.com", 443)
host, port = endpoint
print("主机:", host, "端口:", port)
single = ("only",)
print("单元素元组:", single)

# 7. dict：键唯一、插入顺序、in、items() [R1]
tool_params = {"query": "AI news", "limit": 3, "lang": "zh"}
tool_params["limit"] = 5
print("参数:", tool_params)
print("所有键:", list(tool_params))
for key, value in tool_params.items():
    print(" ", key, "=", value)
print("是否有 query 键:", "query" in tool_params)

# 8. dict 推导式 [R1]
name_lengths = {name: len(name) for name in tool_names}
print("名称长度映射:", name_lengths)

# 9. set：去重与差集；用 sorted 保证输出顺序可预期 [R1]
success = {"search", "summarize", "search"}
all_tools = set(tool_names)
print("成功工具（排序后）:", sorted(success))
print("未完成工具（排序后）:", sorted(all_tools - success))

# 10. 遍历时不要修改原集合，改成遍历副本 [R3]
active_tools = {"search": True, "translate": False}
for name in list(active_tools):
    if not active_tools[name]:
        del active_tools[name]
print("筛选后:", active_tools)
