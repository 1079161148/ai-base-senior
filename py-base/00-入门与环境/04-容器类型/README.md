# 04 容器类型

> 承接第 03 章：`for` 已经能遍历序列，本章把「被遍历的东西」讲透。第 01 章 Agent 示例里那些「工具参数与结果」，到这里才有合适的载体。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 03 章（变量、条件、循环、`print()`） |
| 本章目标 | 四类内置容器的取舍、可变性与可哈希、别名与浅拷贝、推导式、循环技巧 |
| 毕业标准 | 能按场景选容器；能解释「赋值不复制数据」与浅拷贝的边界；能说出遍历时修改集合的正确做法 |
| 编码要求 | 能运行 `examples/containers_demo.py` 并解释 `sort()` 返回 `None`、别名、浅拷贝三段输出 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 索引**仅在本章有效**，完整链接见第 7 节；标注「实测」的是本机运行结果，不是官方依据。来源为 `python.org` 官方教程、PEP 与 CPython 官方仓库。

## 1. 概念

### 1.1 四类内置容器怎么选

| 容器 | 写法 | 有序 | 可变 | 典型用途 | 依据 |
| --- | --- | --- | --- | --- | --- |
| `list` | `[1, 2]` | 是 | 是 | 有序集合、需要增删；元素通常同构、靠迭代访问 | `[R1]` `[R2]` |
| `tuple` | `(1, 2)` | 是 | 否 | 异构记录、靠解包或索引访问；可做 `dict` 键 | `[R1]` |
| `dict` | `{"k": 1}` | 插入顺序 | 是 | 按键取值；键唯一 | `[R1]` |
| `set` | `{1, 2}` | 否 | 是 | 去重、成员测试、集合运算 | `[R1]` |

> `{}` 创建的是**空字典**；空集合必须写 `set()`。`[R1]`

### 1.2 可变、不可变、可哈希

- 字符串与 tuple 是 **immutable**，list 是 **mutable**；官方用「能否给索引位置赋值」区分二者。`[R1]` `[R2]`
- `dict` 的键可以是**任意不可变类型**；含可变对象（直接或间接）的 tuple 不能做键，list 也不能。`[R1]`
- tuple 不可变，但**可以包含可变对象**（如 `([1,2,3], [3,2,1])`）——「不可变」指容器本身的元素引用不变，不等于内部对象不变。`[R1]`

### 1.3 序列通用操作

索引、负索引、切片、`+` 拼接、`*` 重复、`len()` 都适用于字符串与 list。`[R2]` 切片规则（含起点不含终点、越界优雅截断）见第 03 章。

切片的关键性质：**所有切片操作都返回新 list**，即一个**浅拷贝**（`a[:]`）。`[R2]`

### 1.4 list 方法与「就地修改返回 None」

官方给出的 list 方法：`append` / `extend` / `insert` / `remove` / `pop` / `clear` / `index` / `count` / `sort` / `reverse` / `copy`。`[R1]`

- 只修改列表的方法（`insert`、`remove`、`sort` 等）**返回默认的 `None`**，官方称这是所有可变数据结构的设计原则。`[R1]`
- `list.copy()` 返回浅拷贝，等价于 `a[:]`。`[R1]`
- list 可作栈（`append()` + `pop()`）；**作队列低效**——头部插入/删除要移动所有元素，官方建议改用 `collections.deque`（需 `import`，属第 21 章，本章示例不用）。`[R1]`

### 1.5 tuple：打包与解包

- `t = 12345, 54321, 'hello!'` 是 tuple packing；`x, y, z = t` 是 sequence unpacking，要求两侧数量一致。多重赋值其实就是打包 + 解包。`[R1]`
- 空 tuple 写 `()`；**单元素 tuple 必须有尾随逗号** `('hello',)`，只用括号不够。`[R1]`
- tuple 通常承载异构数据、list 通常承载同构数据，这是官方给出的用途区分。`[R1]`

### 1.6 dict

- 以键索引，键唯一；用已存在的键赋值会覆盖旧值；取不存在的键是错误；`del` 删除键值对。`[R1]`
- `list(d)` 按**插入顺序**返回所有键，排序用 `sorted(d)`；成员测试用 `in`。`[R1]`
- `dict()` 可从键值对序列构造；也存在 dict 推导式 `{x: x**2 for x in (2, 4, 6)}`。`[R1]`
- 遍历时同时取键值用 `items()`。`[R1]`

### 1.7 set

- 无序、无重复元素的集合；主要用途是成员测试与去重，支持并 `|`、交 `&`、差 `-`、对称差 `^`。`[R1]`
- 支持 set 推导式 `{x for x in 'abracadabra' if x not in 'abc'}`。`[R1]`

### 1.8 推导式

list / set / dict 推导式提供简洁的构造方式：方括号（或花括号）内一个表达式，后跟 `for` 子句，再跟零到多个 `for` / `if` 子句。`[R1]`

- 官方指出手写循环的等价形式，并强调推导式的 `for` / `if` 顺序与展开后的语句顺序一致。`[R1]`
- 元组作为结果元素时**必须加括号**。`[R1]`
- 嵌套推导式能转置矩阵，但官方明确建议：现实场景**优先用内置函数**，例如 `list(zip(*matrix))` 比手写嵌套更合适。`[R1]`

### 1.9 赋值不复制数据（本章最重要的认知）

官方原文：*"Simple assignment in Python never copies data."* 把 list 赋给另一个变量，只是让新名字**引用同一个对象**；任一名字的修改都会被另一个看到。`[R2]`

需要独立副本时用切片 `a[:]` 或 `list.copy()`，但它们是**浅拷贝**：只复制最外层容器，嵌套的可变对象仍然共享。`[R1]` `[R2]`

### 1.10 循环技巧

| 需求 | 官方写法 | 依据 |
| --- | --- | --- |
| 同时取键值 | `for k, v in d.items()` | `[R1]` |
| 同时取索引与值 | `for i, v in enumerate(seq)` | `[R1]` `[R3]` |
| 并行遍历多序列 | `for q, a in zip(questions, answers)` | `[R1]` |
| 逆序 / 排序遍历 | `reversed(seq)` / `sorted(seq)`（后者返回新 list，不改源） | `[R1]` |
| 去重后排序遍历 | `for f in sorted(set(seq))` | `[R1]` |
| 遍历中要删元素 | 先 `list(d)` / `d.copy()` 取副本，或构建新集合 | `[R3]` `[R1]` |

## 2. 注意事项

1. **`{}` 是空 dict，不是空 set**。`[R1]`
2. **`sort()` / `reverse()` / `append()` 返回 `None`**，别写 `x = lst.sort()`。`[R1]`
3. **赋值不复制**：`b = a` 后改 `b` 就是改 `a`。`[R2]`
4. **浅拷贝只复制一层**，嵌套 list 仍共享。`[R2]`
5. **单元素 tuple 要写尾随逗号**。`[R1]`
6. **不要在遍历时增删正在遍历的集合**，官方给出的替代是遍历副本或新建集合。`[R3]` `[R1]`
7. **set 无序**，不要依赖迭代顺序；需要确定顺序用 `sorted()`。`[R1]`
8. **dict 键必须不可变**，list 或含 list 的 tuple 不能做键。`[R1]`
9. **不是所有数据都能排序比较**：`[None, 'hello', 10]` 会因类型间无法比较而失败。`[R1]`
10. **可变默认值是坑**：官方明确警告默认值只求值一次，`def f(a, L=[])` 会在多次调用间累积；正确写法是 `L=None` 再在函数内初始化。这属于第 05 章，此处只作提前预警。`[R3]`

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 浅拷贝的边界 | `a[:]` / `copy()` 只复制最外层；嵌套可变对象共享，需深拷贝请看 `copy` 模块（第 22 章） | `[R1]` `[R2]` |
| 不可变容器 ≠ 内容不可变 | tuple 可包含 list，内部仍可被修改 | `[R1]` |
| 键的可哈希要求 | 键须不可变；含可变对象的 tuple 也不能作键 | `[R1]` |
| 序列比较 | 同类型序列按字典序比较；序列元素是序列时递归比较；不同类型用 `<` 比较可能抛 `TypeError` | `[R1]` |
| 遍历时修改 | 遍历中删除当前字典的键会出错，官方建议 `for k, v in d.copy().items()` 或构造新字典 | `[R3]` |
| `deque` 与 list 的成本 | list 头部插入/删除需搬移全部元素，`collections.deque` 两端操作都快 | `[R1]` |
| 空容器为假 | `if not seq` 优于 `if len(seq)`；注意 `if x` 与 `if x is not None` 语义不同 | `[R4]` |
| `import` 缺席 | 本章不引入 `collections` / `copy`；相关标准库在第 21–22 章 | 课程边界 |

## 4. 最佳实践

1. **按访问方式选容器**：要顺序且常改 → `list`；不希望被改或要作键 → `tuple`；按键查值 → `dict`；去重 / 成员测试 → `set`。`[R1]` `[R2]`
2. **简单映射与过滤用推导式，复杂逻辑用普通循环**；嵌套超过两层就换内置函数或展开写。`[R1]`
3. **转置类需求优先 `zip()`**，别手写嵌套推导式。`[R1]`
4. **要索引用 `enumerate()`**，不写 `range(len(a))`。`[R3]`
5. **去重并稳定输出用 `sorted(set(seq))`**。`[R1]`
6. **遍历中要删元素，先取副本或构造新集合**。`[R3]` `[R1]`
7. **队列场景用 `deque` 而非 list**（知道结论即可，实现放到第 21–22 章）。`[R1]`

## 5. 最佳编码建议

- **不要接收就地修改方法的返回值**，也不要把 `sort()` 结果继续链式调用。`[R1]`
- **需要副本时显式写 `[:]` 或 `.copy()`**，让「这是有意复制」在代码里可见。`[R1]` `[R2]`
- **判空用 `if not seq`，比较 `None` 用 `is None`**，不要混用。`[R4]`
- **命名表达意图**：`tool_names`、`tool_params`、`snapshot`，不用 `data` / `list2`；布尔量用 `is_` / `has_` 前缀（第 01 章约定）。
- **注释解释「为什么」**：例如「遍历副本，避免边遍历边删」这类非直觉取舍。`[R4]`
- **不硬编码业务值、不原地修改调用方传入的容器**（后者在第 05 章函数参数部分展开）。`[R3]`
- **显式优于隐式、失败要快且明确**：取不存在的键让错误暴露，不要用静默兜底掩盖数据问题。

## 6. 编码示例

### 6.1 可运行脚本

`examples/containers_demo.py` 覆盖四类容器、推导式、别名、浅拷贝与遍历副本：

```python
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
```

运行（**先切到本章目录**）：

```powershell
cd 'E:\ai-agent-study\py-base\00-入门与环境\04-容器类型'
python examples/containers_demo.py
```

本机实测输出：

```text
工具列表: ['search', 'summarize', 'translate', 'cache']
第一个: search 最后两个: ['translate', 'cache']
是否包含 search: True
sort 返回值: None
排序后: ['cache', 'search', 'summarize', 'translate']
原列表也被改动: ['cache', 'search', 'summarize', 'translate', 'audit']
快照长度: 6 原列表长度: 5
名称长度: [5, 6, 9, 9, 5]
长名称: ['summarize', 'translate']
主机: api.example.com 端口: 443
单元素元组: ('only',)
参数: {'query': 'AI news', 'limit': 5, 'lang': 'zh'}
所有键: ['query', 'limit', 'lang']
  query = AI news
  limit = 5
  lang = zh
是否有 query 键: True
名称长度映射: {'cache': 5, 'search': 6, 'summarize': 9, 'translate': 9, 'audit': 5}
成功工具（排序后）: ['search', 'summarize']
未完成工具（排序后）: ['audit', 'cache', 'translate']
筛选后: {'search': True}
```

三处值得对照：`sort 返回值: None` 印证就地修改方法不返回列表 `[R1]`；`原列表也被改动` 印证赋值只是新增名字引用 `[R2]`；`快照长度: 6` 而 `原列表长度: 5` 说明切片确实产生了独立的外层副本 `[R2]`。

### 6.2 REPL 一行验证

```powershell
python -c "a = [1, [2]]; b = a[:]; b[1].append(3); print(a)"
```

输出 `[1, [2, 3]]`——浅拷贝只复制最外层，嵌套 list 仍共享。`[R2]`

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org | https://docs.python.org/3.12/tutorial/datastructures.html | list 全部方法与「就地修改返回 None」、栈/队列与 `deque`、list/set/dict 推导式与嵌套推导式、`del`、tuple 打包解包与单元素逗号、不可变但可含可变对象、set 运算与空 set 写法、dict 键须不可变 / 插入顺序 / `items()` / `dict()`、循环技巧、序列字典序比较、跨类型比较失败 |
| `[R2]` | python.org | https://docs.python.org/3.12/tutorial/introduction.html | 「赋值永不复制数据」、切片返回浅拷贝、list 可变与字符串不可变、索引/切片/`+`/`*`/`len()`、嵌套 list |
| `[R3]` | python.org | https://docs.python.org/3.12/tutorial/controlflow.html | 遍历集合时修改的风险与遍历副本/构造新集合的做法、`enumerate()` 优于 `range(len())`、可变默认参数只求值一次的官方警告 |
| `[R4]` | PEP 官方 | https://peps.python.org/pep-0008/ | 空序列为假、`is None`、不用 `==` 比布尔、注释解释「为什么」、命名约定 |
| `[R5]` | GitHub 官方 | https://github.com/python/cpython/blob/main/Doc/tutorial/datastructures.rst | 官方教程源文件（`[R1]` 页脚 `Show Source` 指向，main 分支） |

## 8. 毕业自查清单

- [ ] 能按「顺序 / 可变 / 按键访问 / 去重」四个维度选出合适的容器
- [ ] 能解释为什么 `{}` 不是空 set、为什么单元素 tuple 要加逗号
- [ ] 能说出 `sort()` 为什么返回 `None`，以及这个设计适用于哪些方法
- [ ] 能解释「赋值不复制数据」与「切片是浅拷贝」，并说出嵌套可变对象的边界
- [ ] 能说出 dict 键的可哈希约束，以及 tuple 含 list 时为什么不能做键
- [ ] 能写出 list / dict / set 推导式，并说出何时该改用普通循环或 `zip()`
- [ ] 能说出遍历时修改集合的两种正确做法
- [ ] 能运行 `examples/containers_demo.py` 并解释 `sort` 返回值、别名、快照三段输出

## 9. 下一章衔接

第 05 章 `函数`：容器已经能承载工具参数与结果，下一步把重复逻辑封装成函数——参数传递、返回值、默认参数（本章提前预警的可变默认值坑会正式展开）、`*args` / `**kwargs`、docstring。第 06 章作用域与第 07 章 `lambda` 紧随其后。
