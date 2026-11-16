# 04 Python 容器类型 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把大纲里每条逐条展开，并补上大纲没列、但写 Python 一定会用到的容器语法与陷阱，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测）；3.9+ 的 `dict \|` 单独标注 |
| 前置 | 第 03 章（变量、运算符、条件与循环） |
| 覆盖范围 | 容器概念、list、tuple、dict、set、通用操作与运算符、遍历方式 |
| 明确不覆盖 | 函数（05）、推导式的高阶用法（本章只讲基础形态）、`collections` 深入（22）、类（08） |
| 学完验收 | 能按场景选对容器，能解释「赋值不复制」「不可变 ≠ 内容永远不变」，能独立写出用 dict 计数 + set 去重 + 排序输出的脚本 |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Cn]` `` 指向第 12 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果，不是官方依据。

**推荐顺序**：

```text
1 容器概念（第 1 节）  → 知道「容器」解决什么问题、四类怎么分
2 list（第 2 节）      → 最常用的可变序列
3 tuple（第 3 节）     → 不可变序列 + 解包
4 dict（第 4 节）      → 键值映射，工程里用得最多
5 set（第 5 节）       → 去重与集合运算
6 通用操作（第 6 节）  → 所有容器共享的函数与运算符
7 遍历（第 7 节）      → for / enumerate / zip 的正规写法
8 决策表（第 8 节）    → 遇到需求先查表
9 综合示例（第 9 节）  → 串起来
10 注意事项（第 10 节）→ 自查踩过的坑
```

**与 README 的分工**：README 讲「为什么这样设计」，本文件负责「语法穷举 + 可查可用 + 陷阱清单」。冲突时以本文件为准。

## 1. 什么是容器类型

**定义**：容器是「能装多个对象的对象」。判断标准很实用——能 `len()`、能用 `for` 遍历、能用 `in` 判断成员，基本就是容器。`[C3]`

```python
tools = ["search", "cache"]      # list 容器
print(len(tools))                # 2
for name in tools:               # 可迭代
    print(name)
print("search" in tools)         # True，支持成员测试
```

**四类容器怎么分**：

| 类别 | 类型 | 存什么 | 访问方式 | 有序 | 可变 |
| --- | --- | --- | --- | --- | --- |
| 序列 | `list` | 任意对象 | 整数下标、切片 | 是 | 是 |
| 序列 | `tuple` | 任意对象 | 整数下标、切片 | 是 | 否 |
| 序列 | `str` | 字符 | 整数下标、切片 | 是 | 否 |
| 映射 | `dict` | 键 → 值 | 键 | 插入序（3.7+） | 是 |
| 集合 | `set` | 可哈希对象 | 只能遍历/判断成员 | **否** | 是 |
| 集合 | `frozenset` | 可哈希对象 | 只能遍历/判断成员 | **否** | 否 |

> 注意：`str` 也是序列，所以第 6 节的通用操作对字符串同样成立；但字符串「装的是字符」，业务上一般单独讨论。`[C3]`

**为什么需要容器**（对比散变量）：

| 写法 | 问题 | 容器写法 |
| --- | --- | --- |
| `tool1 = "search"; tool2 = "cache"; tool3 = "translate"` | 数量固定、无法循环、增删要改代码 | `tools = ["search", "cache", "translate"]` |
| `name1 = "a"; cost1 = 1.2; name2 = "b"; cost2 = 0.5` | 数据不成对，排序无从下手 | `records = [("a", 1.2), ("b", 0.5)]` |
| `if key == "a": v = 1` 一长串 | 分支爆炸 | `mapping = {"a": 1}; mapping[key]` |

**选择速查**：

| 需求 | 选 | 理由 |
| --- | --- | --- |
| 有序、要增删改 | `list` | 最通用 |
| 有序、内容固定、要当 dict 键 | `tuple` | 不可变、可哈希 |
| 按名字查值 | `dict` | O(1) 查找 |
| 去重、判断存在、集合运算 | `set` | 去重且 O(1) 成员测试 |
| 只读、要当键 | `frozenset` | 不可变集合 |

**可变与不可变**：

| 类别 | 类型 | 「不可变」的准确含义 |
| --- | --- | --- |
| 不可变 | `int` `float` `str` `tuple` `frozenset` | 不能换掉内部元素；但 tuple 里装的如果是 list，那个 list 本身仍可改 |
| 可变 | `list` `dict` `set` `bytearray` | 可以原地增删改，所有引用都能看到变化 |

```python
t = (1, [2])
t[1].append(3)      # 合法：改的是 tuple 里的 list
print(t)            # (1, [2, 3])
# t[1] = [9]        TypeError：不能换元素
```

> 注意：`tuple` 的「不可变」指**元素引用不变**，不保证元素内部状态不变；要真正只读，元素也必须是不可变的。`[C6]`

## 2. 列表 `list`

### 2.1 创建列表

```python
empty = []
numbers = [1, 2, 3]
mixed = [1, "a", 3.5, None, [1, 2]]     # 可以混装任意对象
from_range = list(range(3))             # [0, 1, 2]
from_str = list("abc")                  # ['a', 'b', 'c']
copy_of = list(numbers)                 # 浅拷贝
nested = [[1, 2], [3, 4]]               # 嵌套列表
```

| 写法 | 结果 / 说明 | 依据 |
| --- | --- | --- |
| `[]` | 空列表 | `[C1]` |
| `[1, 2, 3]` | 字面量 | `[C1]` |
| `list()` | 空列表 | `[C3]` |
| `list(iterable)` | 把任意可迭代对象转成列表 | `[C3]` |
| `list(range(3))` | `[0, 1, 2]` | `[C5]` |
| `[0] * 3` | `[0, 0, 0]`，元素是同一份 | `[C2]` |
| `[[0]] * 3` | **三行指向同一个内层列表** | `[C2]` |

**乘法陷阱（实测）**：

```python
rows = [[]] * 3
rows[0].append(1)
print(rows)      # [[1], [1], [1]]，三行被同时改
```

正确写法：

```python
rows = [[] for _ in range(3)]   # 每轮新建一个内层列表
rows[0].append(1)
print(rows)      # [[1], [], []]
```

> 注意：`[x] * n` 只复制「引用」。元素是不可变值时无害，元素是可变值时必须用推导式。`[C2]`

### 2.2 索引与切片

```python
tools = ["search", "cache", "translate", "audit", "summarize"]

print(tools[0])      # search
print(tools[-1])     # summarize，负索引从末尾数
print(tools[1:3])    # ['cache', 'translate']，含头不含尾
print(tools[:2])     # ['search', 'cache']
print(tools[2:])     # ['translate', 'audit', 'summarize']
print(tools[::2])    # ['search', 'translate', 'summarize']，步长 2
print(tools[::-1])   # 反序
print(tools[10:])    # []，切片越界不报错
```

| 操作 | 结果 | 越界行为 | 依据 |
| --- | --- | --- | --- |
| `lst[i]` | 单个元素 | `IndexError` | `[C1]` |
| `lst[-1]` | 最后一个 | `IndexError`（空列表） | `[C1]` |
| `lst[a:b]` | 新列表（浅拷贝） | 自动截断，不报错 | `[C2]` |
| `lst[a:b:c]` | 按步长取 | `c=0` 抛 `ValueError` | `[C2]` |
| `lst[:]` | 浅拷贝整表 | — | `[C2]` |

**切片赋值**（会改变长度）：

```python
lst = [1, 2, 3, 4]
lst[1:3] = [9]        # [1, 9, 4]，用 1 个元素替换 2 个
print(lst)

lst2 = [1, 2, 3]
lst2[1:1] = [7, 8]    # 在位置 1 插入，不删除任何元素
print(lst2)           # [1, 7, 8, 2, 3]

lst3 = [1, 2, 3]
lst3[::2] = [9, 7]    # 步长切片的赋值要求长度严格匹配
print(lst3)           # [9, 2, 7]
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 切片赋值可以改长度 | `lst[1:3] = [9]` 合法 | `[C2]` |
| 步长切片赋值长度必须匹配 | `lst[::2] = [1, 2]` 长度不符抛 `ValueError` | `[C2]` |
| 切片赋值右侧必须是可迭代 | 给 `1` 会 `TypeError` | `[C2]` |

> 注意：`lst[i] = x` 只替换一个元素，不能改长度；要插入用 `insert` 或切片赋值。`[C2]`

### 2.3 增加元素

```python
tools = ["search"]

tools.append("cache")        # 末尾追加一个元素
tools.extend(["translate"])  # 末尾追加多个（接收可迭代对象）
tools.insert(1, "audit")     # 在索引 1 处插入
tools += ["summarize"]       # 等价于 extend，但生成/复用方式不同
print(tools)                 # ['search', 'audit', 'cache', 'translate', 'summarize']
```

| 方法 | 作用 | 返回 | 依据 |
| --- | --- | --- | --- |
| `append(x)` | 追加一个元素（`x` 整体作为一个元素） | `None` | `[C2]` |
| `extend(iterable)` | 把可迭代对象的元素逐个追加 | `None` | `[C2]` |
| `insert(i, x)` | 在 `i` 前插入；`i` 越界则追加到末尾 | `None` | `[C2]` |
| `lst += other` | 原地扩展（`__iadd__`） | `None`（语句） | `[C2]` |

**`append` 与 `extend` 的区别（高频错误）**：

```python
a = [1]
a.append([2, 3])
print(a)      # [1, [2, 3]]，一个嵌套列表

b = [1]
b.extend([2, 3])
print(b)      # [1, 2, 3]，三个元素
```

> 注意：`append` 装的是「一个对象」，`extend` 摊平的是「一组元素」；想把多个列表合并，用 `extend` 或 `+`。`[C2]`

### 2.4 删除元素

```python
tools = ["search", "cache", "translate", "audit"]

tools.remove("cache")     # 按值删除，找不到抛 ValueError
last = tools.pop()        # 弹出末尾，返回该值
first = tools.pop(0)      # 弹出指定下标，越界抛 IndexError
del tools[0]              # 按位置删除，也可 del tools[1:3]
tools.clear()             # 清空
print(last, first, tools) # audit translate []
```

| 操作 | 依据 / 边界 | 依据 |
| --- | --- | --- |
| `remove(x)` | 删第一个等于 `x` 的元素；不存在抛 `ValueError` | `[C2]` |
| `pop()` / `pop(i)` | 删除并返回；空列表/越界抛 `IndexError` | `[C2]` |
| `del lst[i]` | 按下标删，**不返回值** | `[C2]` |
| `del lst[a:b]` | 删除切片 | `[C2]` |
| `clear()` | 清空为 `[]`，列表对象本身还在 | `[C2]` |

> 注意：`remove` 只删第一个匹配项；要删全部同名元素得用循环 + 倒序或列表推导式重建。`[C2]`

### 2.5 查找与统计

```python
tools = ["search", "cache", "search"]

print(tools.index("cache"))    # 1，返回首个下标，找不到抛 ValueError
print(tools.count("search"))   # 2
print("audit" in tools)        # False
print(tools.index("search", 1))  # 1，从下标 1 开始找
```

| 方法 | 返回 | 找不到 | 依据 |
| --- | --- | --- | --- |
| `index(x[, start[, end]])` | 首个下标 | `ValueError` | `[C2]` |
| `count(x)` | 出现次数 | 返回 `0` | `[C2]` |
| `x in lst` | `bool` | `False` | `[C3]` |

> 注意：`in` 对 list 是**线性扫描** O(n)；需要频繁判断存在时改用 `set` 或 `dict`。`[C3]`

### 2.6 排序与反转

```python
numbers = [3, 1, 2]
print(numbers.sort())          # None，就地排序，返回 None（实测）
print(numbers)                 # [1, 2, 3]

original = [3, 1, 2]
print(sorted(original))        # [1, 2, 3]，返回新列表
print(original)                # [3, 1, 2]，原列表不变

print(sorted(["bbb", "a", "cc"], key=len))   # ['a', 'cc', 'bbb']，按长度排
print(sorted([3, 1, 2], reverse=True))       # [3, 2, 1]

words = ["b", "a"]
words.reverse()                # 就地反转，返回 None
print(words)                   # ['a', 'b']
```

| 方法/函数 | 作用 | 返回 | 依据 |
| --- | --- | --- | --- |
| `lst.sort(key=None, reverse=False)` | 就地排序 | `None` | `[C2]` |
| `sorted(iterable, key=None, reverse=False)` | 新列表 | 新 `list` | `[C5]` |
| `lst.reverse()` | 就地反转 | `None` | `[C2]` |
| `reversed(seq)` | 反向迭代器 | 迭代器 | `[C5]` |

**排序的关键事实**：

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 稳定排序 | 相等元素的相对顺序保持 | `[C5]` |
| `key` 只算一次 | 每个元素调用一次 `key`，比 `cmp` 高效 | `[C5]` |
| 混合类型报错 | `[1, "a"]` 排序抛 `TypeError`（实测） | `[C5]` |
| `sort` 返回 `None` | 写 `new = lst.sort()` 会拿到 `None` | `[C2]` |
| 不能边遍历边排 | 排序会改变顺序，遍历中排序行为不可预期 | `[C2]` |

> 注意：`lst.sort()` 返回 `None` 是官方设计原则（就地修改的方法都不返回新对象），不是 bug。`[C2]`

### 2.7 复制列表

```python
original = [1, 2]
copy1 = original.copy()     # 浅拷贝
copy2 = original[:]         # 浅拷贝
copy3 = list(original)      # 浅拷贝
alias = original            # 不是拷贝，是第二个名字

alias.append(3)
print(original)             # [1, 2, 3]，别名共享
print(copy1)                # [1, 2]，拷贝独立
```

| 写法 | 是否新对象 | 内层对象是否共享 | 依据 |
| --- | --- | --- | --- |
| `b = a` | 否（同一对象） | 是 | `[C6]` |
| `b = a.copy()` | 是 | **是（浅）** | `[C2]` |
| `b = a[:]` | 是 | **是（浅）** | `[C2]` |
| `b = list(a)` | 是 | **是（浅）** | `[C3]` |
| `b = copy.deepcopy(a)` | 是 | 否（深） | `[C14]` |

```python
nested = [1, [2, 3]]
shallow = nested[:]
shallow[1].append(4)
print(nested)       # [1, [2, 3, 4]]，内层还是同一个列表（实测）
```

> 注意：需要完全独立时用 `copy.deepcopy`；`copy` 模块属于第 22 章标准库，本章只需知道「浅拷贝只复制第一层」。`[C14]`

### 2.8 列表推导式

```python
numbers = [1, 2, 3, 4]

squares = [n * n for n in numbers]
evens = [n for n in numbers if n % 2 == 0]
labels = [f"tool-{n}" for n in numbers]
nested = [[r * c for c in range(3)] for r in range(2)]
print(squares, evens, labels, nested, sep="\n")
# [1, 4, 9, 16]
# [2, 4]
# ['tool-1', 'tool-2', 'tool-3', 'tool-4']
# [[0, 0, 0], [1, 2, 3]]
```

| 形式 | 含义 | 依据 |
| --- | --- | --- |
| `[expr for x in it]` | 映射 | `[C10]` `[C2]` |
| `[expr for x in it if cond]` | 过滤 | `[C10]` |
| `[expr for x in it for y in it2]` | 嵌套展开（等价双层 for） | `[C10]` |
| `[[...] for r in ...]` | 嵌套列表 / 矩阵 | `[C2]` |

> 注意：推导式是表达式，适合「一行能说清」的转换；带副作用的循环、需要多层 `if/else` 或需要 `print` 调试时，写普通 `for` 更清楚。`[C7]`

### 2.9 嵌套列表

```python
matrix = [
    [1, 2, 3],
    [4, 5, 6],
]

print(matrix[1][2])      # 6，先取行再取列
for row in matrix:
    for value in row:
        print(value, end=" ")
print()

column0 = [row[0] for row in matrix]   # 取第一列
print(column0)                          # [1, 4]
```

> 注意：嵌套列表「行」是独立对象才安全；`[[0] * 3] * 2` 两行共享，改一行两行都变。`[C2]`

### 2.10 复杂度与选型

| 操作 | list | dict / set |
| --- | --- | --- |
| 按下标取值 | O(1) | — |
| 按值查找 `in` | O(n) | O(1) 平均 |
| 末尾追加 | O(1) 摊还 | — |
| 中间插入/删除 | O(n) | — |
| 按位置删除开头 | O(n) | — |

> 注意：官方文档说明 dict/set 的成员测试是「平均 O(1)」，依赖哈希质量；list 的 `in` 是线性扫描。数据量大且要频繁查存在性时，先把 list 转成 set。`[C3]`

### 2.11 列表注意事项

| 陷阱 | 现象 | 正确做法 |
| --- | --- | --- |
| `[[0]] * 3` | 三行共享 | `[[0] for _ in range(3)]` |
| `new = lst.sort()` | `new` 是 `None` | 先 `lst.sort()` 再用 `lst`，或 `new = sorted(lst)` |
| `lst[10]` | `IndexError` | 先判 `len` 或用切片 |
| `lst[1:2] = 1` | `TypeError` | 右侧给可迭代：`[1]` |
| 遍历中 `remove` | 漏删/错删 | 遍历副本或重建 |
| `append` 想摊平 | 得到嵌套列表 | 用 `extend` |
| 用 list 去重 | 不去重 | 用 `dict.fromkeys` 或 `set` |
| `+` 混合 tuple | `TypeError`（实测） | 同类型相加，或先 `list()` |

## 3. 元组 `tuple`

### 3.1 创建元组

```python
empty = ()
single = ("only",)          # 逗号决定类型，不能省
also_single = "only",       # 括号也可以省，靠逗号
pair = ("api.example.com", 443)
from_list = tuple([1, 2, 3])
from_str = tuple("abc")     # ('a', 'b', 'c')
```

**逗号陷阱（实测）**：

```python
print(type((1)))     # <class 'int'>，不是元组
print(type((1,)))    # <class 'tuple'>
print(type(()))      # <class 'tuple'>
```

| 写法 | 类型 | 依据 |
| --- | --- | --- |
| `()` | `tuple` | `[C2]` |
| `(1)` | `int`（括号只是分组） | `[C2]` |
| `(1,)` | `tuple` | `[C2]` |
| `1,` | `tuple` | `[C2]` |
| `tuple(iterable)` | `tuple` | `[C3]` |

> 注意：函数返回多个值、`for` 同时取两个变量，本质上都是元组打包/解包，不是语法特例。`[C2]`

### 3.2 为什么用元组

| 理由 | 说明 | 依据 |
| --- | --- | --- |
| 不可变 | 不能误改，可安全共享 | `[C6]` |
| 可哈希 | 元素都可哈希时可作 dict 键、放进 set | `[C6]` |
| 语义清晰 | 「一条记录」用元组，表达「固定结构」 | `[C2]` |
| 更省内存 | 同样元素通常比 list 小 | `[C6]` |

```python
endpoint = ("api.example.com", 443)
config = {( "api.example.com", 443): "primary"}   # 元组可作键（实测）
print(config[endpoint])                            # primary
```

> 注意：含可变元素的元组不可哈希，`([1], 2)` 不能当键；`hash((1, 2))` 可以。`[C6]`

### 3.3 基本操作

```python
point = (3, 5, 7)

print(point[0], point[-1])    # 3 7
print(point[1:])              # (5, 7)
print(point.count(5))         # 1
print(point.index(7))         # 2
print(len(point))             # 3
print(point + (9,))           # (3, 5, 7, 9)，拼接产生新元组
print(point * 2)              # 重复
print(5 in point)             # True
```

| 操作 | 支持 | 说明 | 依据 |
| --- | --- | --- | --- |
| 索引/切片 | 是 | 返回元组（切片） | `[C3]` |
| `count` / `index` | 是 | 与 list 同名同义 | `[C3]` |
| `+` / `*` | 是 | 产生**新**元组 | `[C3]` |
| `in` | 是 | 线性扫描 | `[C3]` |
| `append` / `remove` / `sort` | **否** | 不可变，没有这些方法 | `[C6]` |

> 注意：`t[0] = 1` 抛 `TypeError`；要「修改」只能构造新元组，如 `t = t[:1] + (9,) + t[2:]`。`[C6]`

### 3.4 元组解包（大纲重点）

```python
endpoint = ("api.example.com", 443)
host, port = endpoint
print(host, port)              # api.example.com 443

# 交换变量
a, b = 1, 2
a, b = b, a
print(a, b)                    # 2 1

# 星号收集
first, *rest = [1, 2, 3, 4]
*init, last = [1, 2, 3, 4]
print(first, rest)             # 1 [2, 3, 4]
print(init, last)              # [1, 2, 3] 4

# 嵌套解包
(a, b), c = (1, 2), 3
print(a, b, c)                 # 1 2 3

# for 循环里解包
records = [("search", 1.2), ("cache", 0.1)]
for name, cost in records:
    print(name, cost)
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 左右数量必须相等 | 否则 `ValueError`（实测） | `[C2]` |
| `*` 最多一个 | 收集剩余为 `list` | `[C2]` |
| 可用于任意可迭代 | 字符串、range、生成器都行 | `[C2]` |
| 交换变量 | `a, b = b, a` 是标准写法 | `[C2]` |
| 嵌套解包 | 结构要对齐 | `[C2]` |

```python
try:
    a, b = [1, 2, 3]
except ValueError as error:
    print(type(error).__name__)   # ValueError
```

> 注意：`*` 收集的是 **list**，不是 tuple；`_` 只是「我不关心这个值」的命名约定，不特殊处理。`[C2]`

### 3.5 命名元组（预告）

```python
# 第 22 章标准库内容，这里只建立印象
import collections
Point = collections.namedtuple("Point", ["x", "y"])
p = Point(3, 5)
print(p.x, p.y, p[0])    # 3 5 3，既有名字也有下标
```

| 特性 | 说明 | 依据 |
| --- | --- | --- |
| 仍是 tuple | 支持索引、解包、不可变 | `[C12]` |
| 多了字段名 | `p.x` 比 `p[0]` 可读 | `[C12]` |
| 比 dict 省内存 | 适合大量结构化记录 | `[C12]` |

> 注意：`namedtuple` 定义后字段名固定；需要可变或默认值更多时看 `dataclasses`（第 22 章后）。`[C12]`

### 3.6 与 list 的取舍

| 场景 | 选 tuple | 选 list |
| --- | --- | --- |
| 记录结构固定（坐标、主机端口） | 是 | 否 |
| 需要增删改 | 否 | 是 |
| 要当 dict 键 / 放 set | 是 | 否（不可哈希） |
| 需要排序 | 可 `sorted()` 得新 list | 可 `sort()` 就地 |
| 函数返回多个值 | 是（惯例） | 也可以但不推荐 |

> 注意：`sorted(tuple)` 返回的是 **list**，不是 tuple；要 tuple 得再 `tuple(...)`。`[C5]`

### 3.7 元组注意事项

| 陷阱 | 现象 | 正确做法 |
| --- | --- | --- |
| `(1)` 当元组 | 实际是 `int` | 写 `(1,)` |
| 改元组元素 | `TypeError` | 构造新元组 |
| 含 list 的元组当键 | `TypeError: unhashable` | 元素全部可哈希 |
| 解包数量不等 | `ValueError` | 用 `*rest` 或对齐 |
| 以为 tuple 一定只读 | 内含 list 仍可改 | 元素也用不可变类型 |

## 4. 字典 `dict`

### 4.1 创建字典

```python
empty = {}
config = {"host": "api.example.com", "port": 443}
from_pairs = dict([("a", 1), ("b", 2)])
from_kwargs = dict(a=1, b=2)
comprehension = {name: len(name) for name in ["search", "cache"]}
print(config, from_pairs, from_kwargs, comprehension)
```

| 写法 | 说明 | 依据 |
| --- | --- | --- |
| `{}` | 空字典（**不是**空集合） | `[C2]` |
| `{"k": v}` | 字面量 | `[C2]` |
| `dict(pairs)` | 从键值对序列建 | `[C3]` |
| `dict(**kwargs)` | 关键字建（键必须是合法标识符） | `[C3]` |
| `{k: v for ...}` | 字典推导式 | `[C11]` |
| `dict.fromkeys(iterable, value)` | 批量建键 | `[C3]` |

> 注意：`fromkeys` 的 `value` 如果是可变对象，**所有键共享同一个对象**（实测）；需要独立值时必须推导式。`[C3]`

### 4.2 访问与修改

```python
config = {"host": "api.example.com", "port": 443}

print(config["host"])              # 读，键不存在抛 KeyError
print(config.get("timeout"))       # None，不抛错
print(config.get("timeout", 30))   # 30，给默认值

config["timeout"] = 30             # 新增或覆盖
config["port"] = 8443              # 覆盖
config.update({"retries": 3})      # 批量更新
config.setdefault("lang", "zh")    # 键不存在则写入并返回默认值

del config["retries"]              # 按删除键，不存在抛 KeyError
removed = config.pop("lang")       # 删除并返回值
pair = config.popitem()            # 弹出最后一对（LIFO，实测）
config.clear()                     # 清空
print(removed, pair)               # zh ('timeout', 30)
```

| 操作 | 键不存在时 | 返回 | 依据 |
| --- | --- | --- | --- |
| `d[key]` | `KeyError` | 值 | `[C3]` |
| `d.get(key)` | `None` | 值或 `None` | `[C3]` |
| `d.get(key, default)` | 返回 `default` | 值或默认值 | `[C3]` |
| `d.setdefault(key, default)` | 写入 `default` 并返回 | 值 | `[C3]` |
| `d.pop(key)` | `KeyError`（可给默认值） | 值 | `[C3]` |
| `d.popitem()` | `KeyError`（空字典） | `(键, 值)` | `[C3]` |
| `d.update(other)` | 合并/覆盖 | `None` | `[C3]` |
| `del d[key]` | `KeyError` | 无 | `[C2]` |

**`get` 与 `setdefault` 的区别**：

```python
d = {"a": 1}
print(d.get("b", 0))          # 0，不写入
print(d)                      # {'a': 1}

print(d.setdefault("b", 0))   # 0，会写入
print(d)                      # {'a': 1, 'b': 0}
```

> 注意：`d.get(k, [])` 每次返回的是**同一个列表吗**？不是——每次调用都会新建 `[]`，所以「拿默认值再 append」不会保存。要累积必须 `setdefault` 或 `defaultdict`（第 22 章）。`[C3]`

### 4.3 键的规则

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 键必须可哈希 | `int` `str` `tuple`（元素可哈希）、`frozenset` 可以 | `[C6]` |
| 键必须唯一 | 重复键**后者覆盖**前者 | `[C2]` |
| 键不可变 | `list` / `dict` / `set` 不能当键 | `[C6]` |
| 值任意 | 值可以是任何对象 | `[C2]` |
| 键区分类型 | `1` 与 `"1"` 是不同键；但 `1` 与 `1.0` 视为同一个 | `[C3]` |

```python
try:
    {[]: 1}
except TypeError as error:
    print(type(error).__name__)   # TypeError（实测）

print({"a": 1, "a": 2})           # {'a': 2}，后者覆盖
print({1: "int", 1.0: "float"})   # {1: 'float'}，1 与 1.0 相等且哈希相同
```

> 注意：`1` 与 `True` 也被视为同一个键（`hash(True) == hash(1)`）；用数字当键时别混用布尔。`[C3]`

### 4.4 遍历字典

```python
config = {"host": "api", "port": 443}

for key in config:                      # 遍历键（默认）
    print(key)

for key in config.keys():               # 等价，显式写法
    print(key)

for value in config.values():           # 遍历值
    print(value)

for key, value in config.items():       # 同时取键值（推荐）
    print(key, value)
```

| 方式 | 得到 | 推荐度 | 依据 |
| --- | --- | --- | --- |
| `for k in d` | 键 | 简洁 | `[C2]` |
| `d.keys()` | 键视图 | 显式 | `[C3]` |
| `d.values()` | 值视图 | 只需要值时 | `[C3]` |
| `d.items()` | `(键, 值)` | **最常用** | `[C3]` |

> 注意：`keys()` / `values()` / `items()` 返回的是**视图**，不是列表；视图会随字典变化，需要快照时用 `list(d.items())`。`[C3]`

### 4.5 合并字典

```python
a = {"x": 1}
b = {"y": 2, "x": 9}

print({**a, **b})      # {'x': 9, 'y': 2}，后者覆盖
print(a | b)           # {'x': 9, 'y': 2}，3.9+，后者覆盖

merged = {"x": 1}
merged |= {"y": 2}     # 原地合并，3.9+
print(merged)          # {'x': 1, 'y': 2}
```

| 写法 | 版本 | 是否原地 | 依据 |
| --- | --- | --- | --- |
| `{**a, **b}` | 3.5+ | 新建 | `[C8]` |
| `a \| b` | 3.9+ | 新建 | `[C9]` |
| `a.update(b)` | 一直可用 | **原地** | `[C3]` |
| `a \|= b` | 3.9+ | **原地** | `[C9]` |

> 注意：`|` 与 `|=` 是 3.9 才有的语法，旧环境会 `TypeError`；覆盖规则都是「右侧优先」。`[C9]`

### 4.6 字典推导式

```python
names = ["search", "cache"]
lengths = {name: len(name) for name in names}
filtered = {k: v for k, v in {"a": 1, "b": 2}.items() if v > 1}
inverted = {v: k for k, v in {"a": 1, "b": 2}.items()}
print(lengths, filtered, inverted)
# {'search': 6, 'cache': 5} {'b': 2} {1: 'a', 2: 'b'}
```

> 注意：反转字典时如果值重复，后者覆盖前者；需要保留全部值应改成「值 → 列表」。`[C11]`

### 4.7 插入顺序（3.7+）

```python
d = {"z": 1, "a": 2, "m": 3}
print(list(d))     # ['z', 'a', 'm']，按插入顺序（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 3.7+ 保证插入序 | 语言规范层面保证 | `[C13]` |
| 覆盖不改变位置 | 已存在的键赋值后位置不变 | `[C13]` |
| `sorted(d)` 才按字母序 | 直接遍历是插入序 | `[C5]` |

> 注意：不要依赖「字典默认有序」来做排序输出；要可预期顺序就显式 `sorted()`。`[C5]`

### 4.8 字典重要注意事项

| 陷阱 | 现象 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| `d["missing"]` | `KeyError` | `d.get(...)` 或 `in` 先判断 | `[C3]` |
| 遍历中增删键 | `RuntimeError: dictionary changed size`（实测） | 遍历 `list(d)` 副本 | `[C2]` |
| `dict.fromkeys(keys, [])` | 所有键共享同一个 list | 推导式 `{k: [] for k in keys}` | `[C3]` |
| `d.get(k, []).append(x)` | 默认值丢弃，无法累积 | `d.setdefault(k, []).append(x)` | `[C3]` |
| 用 list 当键 | `TypeError: unhashable` | 转成 tuple | `[C6]` |
| 键混用 `1` / `True` | 相互覆盖 | 键类型保持统一 | `[C3]` |
| 以为 `d.keys()` 是列表 | `d.keys()[0]` 报错 | `list(d.keys())[0]` | `[C3]` |
| 用 `d.items()` 结果反复遍历 | 视图可重复遍历，但顺序随字典变 | 需要固定快照先 `list()` | `[C3]` |

> 注意：`RuntimeError: dictionary changed size during iteration` 只禁止「改变大小」；只改已有键的值是允许的。但为了可读性，遍历中改字典一律先取副本。`[C2]`

### 4.9 复杂度

| 操作 | 平均复杂度 | 依据 |
| --- | --- | --- |
| `d[k]` 读/写 | O(1) | `[C3]` |
| `k in d` | O(1) | `[C3]` |
| `del d[k]` | O(1) | `[C3]` |
| 遍历 | O(n) | `[C3]` |

> 注意：O(1) 是平均情况；哈希冲突严重时会退化，但正常业务不需要担心。`[C3]`

## 5. 集合 `set`

### 5.1 创建集合

```python
empty = set()                 # 空集合只能这样写
numbers = {1, 2, 3}
from_list = set([1, 2, 2, 3]) # {1, 2, 3}，自动去重
from_str = set("hello")       # 去重后的字符集合
from_comp = {n * 2 for n in range(3)}

print(empty, numbers, from_list, len(from_str))
```

**空集合陷阱（实测）**：

```python
print(type({}))      # <class 'dict'>，不是 set
print(type(set()))   # <class 'set'>
```

| 写法 | 结果 | 依据 |
| --- | --- | --- |
| `set()` | 空集合 | `[C2]` |
| `{}` | 空**字典** | `[C2]` |
| `{1, 2}` | 集合字面量 | `[C2]` |
| `set(iterable)` | 从可迭代对象去重建 | `[C3]` |
| `{x for x in ...}` | 集合推导式 | `[C2]` |

> 注意：`set("hello")` 只有 4 个元素（`l` 重复），且**输出顺序不保证**；要可预期输出用 `sorted(set(...))`。`[C2]` `[C3]`

### 5.2 集合运算

```python
a = {1, 2, 3}
b = {2, 3, 4}

print(a | b)     # {1, 2, 3, 4}，并集
print(a & b)     # {2, 3}，交集
print(a - b)     # {1}，差集（a 有 b 没有）
print(a ^ b)     # {1, 4}，对称差

print(a.union(b))                  # 同上并集
print(a.intersection(b))           # 同上交集
print(a.difference(b))             # 同上差集
print(a.symmetric_difference(b))   # 同上对称差
print(a.issubset({1, 2, 3, 4}))    # True，子集
print(a.issuperset({1, 2}))        # True，超集
print(a.isdisjoint({9}))           # True，无交集
```

| 运算符 | 方法 | 含义 | 依据 |
| --- | --- | --- | --- |
| `\|` | `union` | 并集 | `[C3]` |
| `&` | `intersection` | 交集 | `[C3]` |
| `-` | `difference` | 差集 | `[C3]` |
| `^` | `symmetric_difference` | 对称差 | `[C3]` |
| `<=` | `issubset` | 子集 | `[C3]` |
| `>=` | `issuperset` | 超集 | `[C3]` |
| `<` / `>` | 真子集/真超集 | 不相等才为真 | `[C3]` |

> 注意：`-` 有方向，`a - b` 与 `b - a` 不同；`&`、`\|`、`^` 可交换。`[C3]`

### 5.3 增加与删除

```python
s = {1, 2}

s.add(3)              # 添加单个元素
s.update([4, 5])      # 批量添加
s.discard(99)         # 不存在也不报错
s.remove(3)           # 不存在抛 KeyError
popped = s.pop()      # 随机弹出一个（不保证顺序）
s.clear()             # 清空

print(popped, s)      # 1，set()
```

| 方法 | 不存在时 | 返回 | 依据 |
| --- | --- | --- | --- |
| `add(x)` | 已存在则无变化 | `None` | `[C3]` |
| `update(iterable)` | — | `None` | `[C3]` |
| `remove(x)` | `KeyError` | `None` | `[C3]` |
| `discard(x)` | 静默忽略 | `None` | `[C3]` |
| `pop()` | 空集合 `KeyError` | 某个元素 | `[C3]` |
| `clear()` | — | `None` | `[C3]` |

> 注意：`set.pop()` 弹出的是「任意一个」，不是第一个也不是最后一个；不要用它做有序出栈。`[C3]`

### 5.4 `frozenset`

```python
fs = frozenset([1, 2, 3])
print(fs | frozenset([4]))     # frozenset({1, 2, 3, 4})

config = {frozenset(["read", "write"]): "role"}   # 可作 dict 键（实测）
print(config[frozenset(["read", "write"])])
```

| 特性 | `set` | `frozenset` |
| --- | --- | --- |
| 可变 | 是 | 否 |
| 可哈希 | 否 | 是 |
| 可作 dict 键 | 否 | 是 |
| 可放进 set | 否 | 是 |

> 注意：`frozenset` 没有 `add/remove`；要改只能新建。`[C3]`

### 5.5 元素必须可哈希

```python
{1, 2, 3}          # 可以
{"a", "b"}         # 可以
{(1, 2), (3, 4)}   # 可以，元组可哈希

try:
    {[1, 2]}
except TypeError as error:
    print(type(error).__name__)   # TypeError（实测）
```

> 注意：集合元素必须可哈希，所以 `list` / `dict` / `set` 不能直接放进去；需要放「一组值」时用 `tuple` 或 `frozenset`。`[C6]`

### 5.6 无序性与不可索引

```python
s = {3, 1, 2}
print(s)              # 顺序不保证，不要依赖
print(sorted(s))      # [1, 2, 3]，要有序就显式排序

try:
    s[0]
except TypeError as error:
    print(type(error).__name__)   # TypeError，不支持下标
```

> 注意：集合没有下标、不支持切片；要按位置访问先转 `list` 或 `sorted`。`[C3]`

### 5.7 典型场景

| 场景 | 写法 | 依据 |
| --- | --- | --- |
| 去重保序 | `list(dict.fromkeys(items))` | `[C3]` |
| 去重不保序 | `list(set(items))` | `[C3]` |
| 判断是否存在 | `x in s`（O(1)） | `[C3]` |
| 找共同项 | `set(a) & set(b)` | `[C3]` |
| 找差异项 | `set(a) - set(b)` | `[C3]` |
| 权限/标签比较 | `required <= granted` | `[C3]` |

```python
items = ["b", "a", "b", "c"]
print(list(set(items)))               # 顺序不保证
print(list(dict.fromkeys(items)))     # ['b', 'a', 'c']，保序（实测）
```

> 注意：需要「去重后保持原顺序」时不要用 `set`，用 `dict.fromkeys`（3.7+ 保插入序）。`[C3]` `[C13]`

### 5.8 集合注意事项

| 陷阱 | 现象 | 正确做法 |
| --- | --- | --- |
| `{}` 当空集合 | 实际是 dict | `set()` |
| 依赖遍历顺序 | 每次可能不同 | `sorted()` 后再用 |
| `s[0]` | `TypeError` | 转 list/排序 |
| 放 list 进去 | `TypeError: unhashable` | 用 tuple |
| 用 `remove` 删不存在 | `KeyError` | 用 `discard` |
| 用 set 去重又想保序 | 顺序丢失 | `dict.fromkeys` |

## 6. 容器通用操作

### 6.1 通用函数

```python
tools = ["search", "cache", "translate"]
prices = {"a": 2, "b": 1}

print(len(tools), len(prices))          # 3 2
print(min(tools), max(tools))           # cache translate（按字符串比较）
print(sum([1, 2, 3]), sum([]))          # 6 0
print(max(prices))                      # b，对 dict 迭代的是键（实测）
print(sorted(prices))                   # ['a', 'b']，键排序
print(list(reversed(tools)))            # ['translate', 'cache', 'search']
```

| 函数 | 对 dict 的含义 | 空容器 | 依据 |
| --- | --- | --- | --- |
| `len(c)` | 键的个数 | `0` | `[C5]` |
| `min(c)` / `max(c)` | 比较**键** | `ValueError` | `[C5]` |
| `sum(c)` | 对键求和（通常不是想要的） | `0` | `[C5]` |
| `sorted(c)` | 键排序成 list | `[]` | `[C5]` |
| `reversed(c)` | 3.8+ 支持反向迭代 dict | — | `[C5]` |
| `all(c)` / `any(c)` | 对元素求真值 | `True` / `False` | `[C5]` |

```python
print(all([True, 1]), all([True, 0]))   # True False
print(any([0, ""]), any([0, "x"]))      # False True
print(all([]), any([]))                 # True False，空容器的边界（实测）
```

> 注意：`min([])` / `max([])` 抛 `ValueError`；`sum([])` 是 `0`、`all([])` 是 `True`、`any([])` 是 `False`——这四个空容器边界要记牢。`[C5]`

### 6.2 成员运算符 `in` / `not in`

```python
print("search" in ["search"])      # True，list 按值线性扫描
print("host" in {"host": 1})       # True，dict 判**键**
print(2 in {1, 2})                 # True，set 哈希查找
print("th" in "python")            # True，str 判子串
print("value" in {"host": 1})      # False，不判值
```

| 容器 | `in` 判断什么 | 复杂度 | 依据 |
| --- | --- | --- | --- |
| `list` / `tuple` | 元素值 | O(n) | `[C3]` |
| `dict` | **键** | O(1) | `[C3]` |
| `set` | 元素 | O(1) | `[C3]` |
| `str` | 子串 | O(n) | `[C3]` |

> 注意：`"value" in d` 判断的不是值；要判值用 `"value" in d.values()`（O(n)）。`[C3]`

### 6.3 连接与重复运算

```python
print([1, 2] + [3])      # [1, 2, 3]
print((1, 2) + (3,))     # (1, 2, 3)
print("ab" + "cd")       # abcd
print([1, 2] * 2)        # [1, 2, 1, 2]
print((0,) * 3)          # (0, 0, 0)
print("ab" * 2)          # abab
```

| 运算 | 支持类型 | 结果 | 依据 |
| --- | --- | --- | --- |
| `+` | `list`+`list`、`tuple`+`tuple`、`str`+`str` | 新对象 | `[C3]` |
| `*` | 序列 × `int` | 新对象（元素引用复制） | `[C3]` |
| `+=` | 同上 | list 原地扩展，tuple/str 新建 | `[C2]` |

```python
try:
    [1] + (2,)
except TypeError as error:
    print(type(error).__name__)   # TypeError，类型必须相同（实测）
```

> 注意：`+` 要求两侧同类型；`[1] + (2,)` 报错，需要先转换。`[C3]`

### 6.4 相等运算符 `==`

```python
print([1, 2] == [1, 2])            # True，逐元素比较
print([1, [2]] == [1, [2]])        # True，递归比较
print({"a": 1} == {"a": 1})        # True
print({1, 2} == {2, 1})            # True，集合无序也相等
print([1, 2] == (1, 2))            # False，不同类型不相等
print(1 == 1.0)                    # True，数值按值比较
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 序列 | 逐元素、递归比较 | `[C3]` |
| 映射 | 键值集合都相同才相等（不看顺序） | `[C3]` |
| 集合 | 元素相同即相等 | `[C3]` |
| 跨类型 | `list` 与 `tuple` 不相等 | `[C3]` |

> 注意：`==` 比较的是「内容」；嵌套结构也是递归比较，但遇到自引用结构会按身份短路处理。`[C3]`

### 6.5 身份运算符 `is` / `is not`

```python
a = [1, 2]
b = [1, 2]
c = a

print(a == b)      # True，内容相同
print(a is b)      # False，两个不同对象
print(a is c)      # True，同一个对象
print(a is None)   # False
```

| 判断 | 用 | 依据 |
| --- | --- | --- |
| 内容是否相同 | `==` | `[C4]` |
| 是否同一对象 | `is` | `[C4]` |
| 是否为 `None` | `is None` | `[C7]` |

> 注意：`is` 比的是 `id()`；空容器、相同字面量都不保证是同一对象，永远不要用 `is` 判断内容相等。`[C4]`

### 6.6 位运算符（对集合是集合运算）

```python
a = {1, 2, 3}
b = {2, 3, 4}

print(a & b)    # {2, 3}，交集
print(a | b)    # {1, 2, 3, 4}，并集
print(a ^ b)    # {1, 4}，对称差
print(a - b)    # {1}，差集

print(6 & 3, 6 | 3, 6 ^ 3, ~6, 1 << 4)   # 对 int 才是按位运算
```

| 运算符 | 对 `int` | 对 `set` | 依据 |
| --- | --- | --- | --- |
| `&` | 按位与 | 交集 | `[C3]` `[C4]` |
| `\|` | 按位或 | 并集 | `[C3]` `[C4]` |
| `^` | 按位异或 | 对称差 | `[C3]` `[C4]` |
| `-` | 减法 | 差集 | `[C3]` |
| `~` | 按位取反 | 不支持 | `[C4]` |

> 注意：`& | ^` 对 `dict` **不是**集合运算；dict 合并用 `|`（3.9+），但 `&`、`^` 对 dict 会 `TypeError`。`[C9]`

### 6.7 各容器支持的运算符

| 运算 | `list` | `tuple` | `dict` | `set` |
| --- | --- | --- | --- | --- |
| `+` | ✅ | ✅ | ❌ | ❌ |
| `*` | ✅ | ✅ | ❌ | ❌ |
| `==` | ✅ | ✅ | ✅ | ✅ |
| `in` | ✅ 值 | ✅ 值 | ✅ 键 | ✅ 值 |
| `&` | ❌ | ❌ | ❌ | ✅ 交集 |
| `\|` | ❌ | ❌ | ✅ 合并（3.9+） | ✅ 并集 |
| `-` | ❌ | ❌ | ❌ | ✅ 差集 |
| `^` | ❌ | ❌ | ❌ | ✅ 对称差 |

> 注意：这张表能省掉大量 `TypeError` 试错；不确定时先用 REPL 验证一次。`[C3]`

### 6.8 可哈希与可变性

| 类型 | 可变 | 可哈希 | 能当 dict 键 / 放进 set |
| --- | --- | --- | --- |
| `int` / `float` / `bool` / `str` | 否 | 是 | ✅ |
| `tuple` | 否 | 元素可哈希才可哈希 | ✅（元素可哈希时） |
| `frozenset` | 否 | 是 | ✅ |
| `list` | 是 | 否 | ❌ |
| `dict` | 是 | 否 | ❌ |
| `set` | 是 | 否 | ❌ |

> 注意：**可哈希 ≈ 不可变**，但有例外（自定义类默认按 `id` 哈希，即使内部可变）；本章只需记住内置类型的这张表。`[C6]`

### 6.9 浅拷贝与深拷贝

```python
import copy

original = [[1], [2]]
shallow = copy.copy(original)      # 等价于 original[:]
deep = copy.deepcopy(original)

shallow[0].append(9)
print(original)      # [[1, 9], [2]]，内层共享

deep[0].append(9)
print(original)      # [[1, 9], [2]]，内层独立（不受影响）
```

| 方式 | 复制层数 | 适用 | 依据 |
| --- | --- | --- | --- |
| `b = a` | 0（别名） | 故意共享 | `[C6]` |
| `a.copy()` / `a[:]` / `list(a)` | 1（浅） | 一维容器 | `[C2]` |
| `copy.deepcopy(a)` | 全部（深） | 嵌套容器 | `[C14]` |

> 注意：`deepcopy` 会递归复制，遇到自引用结构会做记忆化；性能开销明显，只在确实需要隔离嵌套结构时用。`[C14]`

## 7. 遍历容器

### 7.1 基本 `for` 循环

```python
tools = ["search", "cache"]

for name in tools:              # 直接遍历元素，不需要下标
    print(name)

for i in range(len(tools)):     # 需要下标时（不推荐，见 7.4）
    print(i, tools[i])
```

| 写法 | 得到 | 推荐度 | 依据 |
| --- | --- | --- | --- |
| `for x in c` | 元素 | **首选** | `[C2]` |
| `for i in range(len(c))` | 下标 | 需要修改元素时 | `[C2]` |
| `for i, x in enumerate(c)` | 下标 + 元素 | 需要下标时首选 | `[C5]` |

> 注意：`for x in c` 拿到的是元素本身；如果元素是可变对象，改 `x` 的内容会影响容器（因为指向同一对象），但给 `x` 重新赋值不会。`[C2]`

### 7.2 遍历字典

```python
config = {"host": "api", "port": 443}

for key in config:                    # 键
    print(key)

for key, value in config.items():     # 键 + 值（推荐）
    print(key, "=", value)

for value in config.values():         # 只要值
    print(value)

for index, (key, value) in enumerate(config.items(), start=1):   # 带序号
    print(index, key, value)
```

| 需求 | 写法 | 依据 |
| --- | --- | --- |
| 只要键 | `for k in d` | `[C2]` |
| 只要值 | `for v in d.values()` | `[C3]` |
| 键和值 | `for k, v in d.items()` | `[C3]` |
| 带序号 | `enumerate(d.items(), start=1)` | `[C5]` |

> 注意：`enumerate(d.items())` 得到的是 `(序号, (键, 值))`，所以要写 `for index, (key, value) in ...`，括号不能少。`[C5]`

### 7.3 遍历集合

```python
tags = {"search", "cache", "translate"}

for tag in tags:
    print(tag)          # 顺序不保证

for tag in sorted(tags):   # 需要稳定输出时
    print(tag)
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 顺序不保证 | 每次运行可能不同 | `[C3]` |
| 不能索引 | `tags[0]` 抛 `TypeError` | `[C3]` |
| 遍历中不能改大小 | 会 `RuntimeError` | `[C2]` |
| 要稳定顺序 | `sorted(tags)` | `[C5]` |

> 注意：集合的输出顺序取决于哈希，跨进程还可能受 `PYTHONHASHSEED` 影响；测试断言里不要写死顺序。`[C3]`

### 7.4 `enumerate()` 函数

```python
tools = ["search", "cache"]

for index, name in enumerate(tools):          # 默认从 0 开始
    print(index, name)

for index, name in enumerate(tools, start=1): # 从 1 开始
    print(index, name)

pairs = list(enumerate(tools))
print(pairs)      # [(0, 'search'), (1, 'cache')]
```

| 参数 | 默认 | 说明 | 依据 |
| --- | --- | --- | --- |
| `iterable` | 必填 | 任意可迭代对象 | `[C5]` |
| `start` | `0` | 计数起点 | `[C5]` |

> 注意：`enumerate` 返回的是迭代器，打印它本身只会看到 `<enumerate object>`；要查看内容先 `list()`。`[C5]`

### 7.5 `zip()` 函数

```python
names = ["search", "cache", "translate"]
costs = [1.2, 0.5, 3.5]

for name, cost in zip(names, costs):
    print(name, cost)

print(list(zip(names, costs)))     # [(...), (...), (...)]
print(list(zip(names, "ab")))      # 按最短截断，只出 2 对（实测）
```

| 场景 | 写法 | 依据 |
| --- | --- | --- |
| 并行遍历 | `zip(a, b)` | `[C5]` |
| 长度必须一致 | `zip(a, b, strict=True)`，3.10+ | `[C8]` `[C5]` |
| 转成 dict | `dict(zip(keys, values))` | `[C3]` |
| 解压 | `list(zip(*pairs))` | `[C8]` |

```python
try:
    list(zip(names, "ab", strict=True))
except ValueError as error:
    print(type(error).__name__)   # ValueError，长度不一致（实测）
```

> 注意：`zip` 默认按最短**静默截断**，是数据丢失的常见来源；关键路径加 `strict=True`。`[C5]`

### 7.6 反向与排序遍历

```python
numbers = [3, 1, 2]

for n in reversed(numbers):    # 反向，不改原列表
    print(n)

for n in sorted(numbers):      # 升序，返回新列表
    print(n)

for n in sorted(numbers, reverse=True):
    print(n)
```

| 函数 | 返回 | 是否改原容器 | 依据 |
| --- | --- | --- | --- |
| `reversed(c)` | 反向迭代器 | 否 | `[C5]` |
| `sorted(c)` | 新 `list` | 否 | `[C5]` |
| `c.sort()` | `None` | **是** | `[C2]` |
| `c.reverse()` | `None` | **是** | `[C2]` |

> 注意：`reversed(dict)` 需要 3.8+；对 dict 反向遍历的是键。`[C5]`

### 7.7 遍历中修改容器

**错误示范（会漏项或报错）**：

```python
items = ["a", "b", "c"]
for item in items:
    if item == "b":
        items.remove(item)      # 遍历过程中改变长度
print(items)                    # ['a', 'c'] 这次碰巧对，但不保证
```

```python
config = {"a": 1, "b": 2}
try:
    for key in config:
        config["c"] = 3          # 改变大小
except RuntimeError as error:
    print(type(error).__name__)  # RuntimeError（实测）
```

**三种正确解法**：

```python
# 1 遍历副本
for item in items[:]:
    if item == "b":
        items.remove(item)

# 2 先收集再统一删除
to_remove = [item for item in items if item == "b"]
for item in to_remove:
    items.remove(item)

# 3 重建（最推荐，语义最清楚）
items = [item for item in items if item != "b"]
```

| 容器 | 遍历中改大小 | 遍历中只改值 |
| --- | --- | --- |
| `list` | 危险（漏项/错乱），不报错 | 允许 |
| `dict` | `RuntimeError` | 允许 |
| `set` | `RuntimeError` | 不适用 |

> 注意：list 遍历中删除**不会**报错，只会静默出 bug，比报错更难查；一律用重建写法。`[C2]`

### 7.8 嵌套遍历与并行遍历

```python
# 嵌套：笛卡尔积
for row in ["a", "b"]:
    for col in [1, 2]:
        print(row, col)

# 并行：按位置配对
for name, cost in zip(["search", "cache"], [1.2, 0.5]):
    print(name, cost)

# 嵌套展开（等价两层 for）
pairs = [(r, c) for r in ["a", "b"] for c in [1, 2]]
print(pairs)   # [('a', 1), ('a', 2), ('b', 1), ('b', 2)]
```

> 注意：`zip` 是「并行」，`for` 嵌套是「组合」；两者语义不同，别混用。`[C5]`

## 8. 容器选择决策表

| 你的需求 | 用 | 一句话理由 |
| --- | --- | --- |
| 一串有序数据，要增删 | `list` | 最通用 |
| 一条固定记录（坐标、主机端口） | `tuple` | 不可变、可解包 |
| 用名字查值 | `dict` | O(1) 查找 |
| 去重 | `set` | 自动去重 |
| 判断「在不在」 | `set` / `dict` | O(1) |
| 保留插入顺序去重 | `dict.fromkeys` | 3.7+ 保序 |
| 需要当 dict 键的一组值 | `tuple` / `frozenset` | 可哈希 |
| 频次统计 | `dict` 计数（或第 22 章 `Counter`） | 简单直接 |
| 固定大小矩阵 | 嵌套 `list` | 下标访问 |
| 只读集合 | `frozenset` | 不可变 |

**反模式提醒**：

| 反模式 | 问题 | 改用 |
| --- | --- | --- |
| 用 `list` 频繁 `in` 判断 | O(n) | `set` |
| 用 `list` 去重 | 不去重 | `dict.fromkeys` / `set` |
| 用 `list` 当队列 `pop(0)` | O(n) | `collections.deque`（22） |
| 用 `dict` 当有序列表 | 语义错 | `list` |
| 用 `tuple` 存要变的数据 | 改不了 | `list` |
| 用 `set` 存要排序输出的数据 | 顺序不稳 | `sorted(set(...))` |

## 9. 综合示例：Tool 调用统计

只用本章 + 第 03 章语法（无函数、无类、无自定义 import）。

```python
"""第 04 章综合示例：用 dict 计数、set 去重、list 过滤。"""

records = [
    ("search", "ok"),
    ("cache", "ok"),
    ("search", "fail"),
    ("translate", "ok"),
    ("search", "ok"),
]

counts = {}
for name, status in records:              # 元组解包 + for
    counts[name] = counts.get(name, 0) + 1  # get 给默认值，避免 KeyError

print(f"工具数: {len(counts)}")
for name in sorted(counts):               # 显式排序，输出可预期
    print(f"{name}: {counts[name]} 次")

status_set = {status for _, status in records}   # 集合推导式去重
print("出现过的状态:", sorted(status_set))

failed = [name for name, status in records if status == "fail"]   # 列表推导式过滤
print("失败记录:", failed)

unique_tools = set(counts)
print("去重后的工具:", sorted(unique_tools))
```

本机实测输出：

```text
工具数: 3
cache: 1 次
search: 3 次
translate: 1 次
出现过的状态: ['fail', 'ok']
失败记录: ['search']
去重后的工具: ['cache', 'search', 'translate']
```

**逐段说明**：

| 代码 | 用到的语法 | 依据 |
| --- | --- | --- |
| `for name, status in records` | 元组解包 | `[C2]` |
| `counts.get(name, 0) + 1` | `dict.get` 默认值 | `[C3]` |
| `sorted(counts)` | 排序字典的键 | `[C5]` |
| `{status for _, status in records}` | 集合推导式 | `[C2]` |
| `[name for name, status in ... if ...]` | 列表推导式 + 过滤 | `[C10]` |
| `set(counts)` | dict 转 set 得到键集合 | `[C3]` |

> 注意：`counts.get(name, 0) + 1` 是最小计数写法；更复杂的聚合（按状态分组、Top-N）会在第 22 章 `collections` 与第 07 章 `sorted(key=...)` 里展开。`[C12]`

## 10. 注意事项与新手错误对照表

| 错误写法 / 操作 | 报错或现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `empty = {}` 当空集合 | 是 dict，`add` 报错 | `set()` | `[C2]` |
| `t = (1)` 当元组 | 是 `int` | `(1,)` | `[C2]` |
| `[[0]] * 3` | 三行共享 | `[[0] for _ in range(3)]` | `[C2]` |
| `new = lst.sort()` | `new` 是 `None` | `new = sorted(lst)` | `[C2]` |
| `a.append([1, 2])` 想摊平 | 得到嵌套列表 | `a.extend([1, 2])` | `[C2]` |
| `lst[10]` | `IndexError` | 先判 `len` | `[C1]` |
| `lst[10:]` 以为报错 | 返回 `[]` | 切片自动截断 | `[C2]` |
| `lst[1:2] = 1` | `TypeError` | `lst[1:2] = [1]` | `[C2]` |
| `lst[::2] = [1]` | `ValueError`（长度不匹配） | 长度严格对齐 | `[C2]` |
| `lst.remove(9)` | `ValueError` | 先 `in` 判断 | `[C2]` |
| `[].pop()` | `IndexError` | 判空 | `[C2]` |
| `d["missing"]` | `KeyError` | `d.get(...)` | `[C3]` |
| 遍历 `d` 时新增键 | `RuntimeError` | 遍历 `list(d)` | `[C2]` |
| `dict.fromkeys(keys, [])` | 所有键共享同一个 list | 推导式 | `[C3]` |
| `d.get(k, []).append(x)` | 默认值被丢弃 | `d.setdefault(k, []).append(x)` | `[C3]` |
| `d[[]]` | `TypeError: unhashable` | 键用 `tuple` | `[C6]` |
| `{1: "a", True: "b"}` | 相互覆盖 | 键类型统一 | `[C3]` |
| `d.keys()[0]` | `TypeError` | `list(d)[0]` | `[C3]` |
| `s[0]`（集合） | `TypeError` | `sorted(s)[0]` | `[C3]` |
| `s.remove(9)` 不存在 | `KeyError` | `s.discard(9)` | `[C3]` |
| 依赖 `set` 遍历顺序 | 每次可能不同 | `sorted(s)` | `[C3]` |
| `min([])` / `max([])` | `ValueError` | 先判空 | `[C5]` |
| `sorted([1, "a"])` | `TypeError` | 统一类型 | `[C5]` |
| `[1] + (2,)` | `TypeError` | 同类型相加 | `[C3]` |
| `a, b = [1, 2, 3]` | `ValueError` | `a, b, *rest = ...` | `[C2]` |
| `a is b` 判内容 | 结果依赖对象身份 | `a == b` | `[C4]` |
| 用 `set` 去重又想保序 | 顺序丢失 | `dict.fromkeys` | `[C3]` |
| `x =+ 1` 想自增 | 实际是 `x = +1` | `x += 1` | `[C2]` |
| 遍历 list 时 `remove` | 静默漏项 | 重建列表 | `[C2]` |
| 3.9 以下用 `d1 \| d2` | `TypeError` | `d1.update(d2)` | `[C9]` |
| `copy` 当深拷贝 | 内层仍共享 | `copy.deepcopy` | `[C14]` |
| `t[0] = 1` | `TypeError` | 构造新元组 | `[C6]` |
| `"a" + ["b"]` | `TypeError` | `"a" + "b"` 或 `["a"] + ["b"]` | `[C3]` |
| `del` 后继续用变量 | `NameError` | 删除后不要再用 | `[C2]` |
| `insert(100, x)` 以为报错 | 实际追加到末尾（实测） | 这是设计行为 | `[C2]` |
| `sum(d)` 想求和值 | 实际求和键 | `sum(d.values())` | `[C5]` |
| `max(d)` 想取最大值 | 得到键 | `max(d.values())` | `[C5]` |

## 11. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 先查决策表再写代码 | 容器选错，后面全是补丁 | `[C3]` |
| 结构固定用 `tuple`，会变用 `list` | 语义清晰、可哈希 | `[C2]` |
| 频繁判存在用 `set` / `dict` | 避免 O(n) | `[C3]` |
| 就地修改方法不要接返回值 | `sort` / `append` / `update` 都返回 `None` | `[C2]` |
| 遍历中不改容器 | 用副本或重建 | `[C2]` |
| 去重保序用 `dict.fromkeys` | 3.7+ 稳定 | `[C3]` `[C13]` |
| 输出前显式 `sorted()` | 集合顺序不可预期 | `[C5]` |
| 键类型保持统一 | `1` / `True` / `"1"` 混用会出错 | `[C3]` |
| 深拷贝只在必要时用 | 性能与语义成本都高 | `[C14]` |
| 参数默认值不用可变容器 | `def f(x=[])` 是经典 bug（第 05 章） | `[C7]` |

**PEP 8 相关速记** `[C7]`：

- 逗号后一个空格：`[1, 2, 3]`，不是 `[1,2,3]`。
- 切片冒号两侧不加空格：`lst[1:3]`，不是 `lst[1 : 3]`。
- 等号在关键字参数里不加空格：`dict(a=1)`。
- 容器字面量建议保持可读，超过行宽用括号换行。

**安全与边界**：

- 不要把用户输入直接当键拼进 `dict` 后无限制增长（内存风险）。
- 处理外部数据时先校验结构与长度，再索引/解包；`IndexError` / `KeyError` / `ValueError` 都会让程序中断。
- 不要把敏感值（令牌、密码）放在会被打印或序列化的容器里。

## 12. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[C1]` | python.org | https://docs.python.org/3.12/tutorial/introduction.html | 列表字面量、索引、切片、`append`、嵌套列表、`len()` |
| `[C2]` | python.org | https://docs.python.org/3.12/tutorial/datastructures.html | list 方法、`del`、tuple 与打包解包、set、dict、推导式、`enumerate`/`zip`/`reversed`/`sorted`、遍历时修改集合的风险 |
| `[C3]` | python.org | https://docs.python.org/3.12/library/stdtypes.html | 序列通用操作、`dict`/`set`/`frozenset` 方法与运算、成员测试、真值测试、复杂度说明 |
| `[C4]` | python.org | https://docs.python.org/3.12/reference/expressions.html | 成员/身份/比较运算符、切片语义、位运算、运算符优先级 |
| `[C5]` | python.org | https://docs.python.org/3.12/library/functions.html | `len`/`min`/`max`/`sum`/`sorted`/`reversed`/`enumerate`/`zip`/`all`/`any`/`list`/`tuple`/`set`/`dict` |
| `[C6]` | python.org | https://docs.python.org/3.12/reference/datamodel.html | 可变与不可变、可哈希、对象身份、容器对象 |
| `[C7]` | PEP 官方 | https://peps.python.org/pep-0008/ | 逗号/切片空格、容器写法、避免可变默认参数 |
| `[C8]` | PEP 官方 | https://peps.python.org/pep-0448/ | 额外解包 `{**a, **b}`、`*` 解包 |
| `[C9]` | PEP 官方 | https://peps.python.org/pep-0584/ | dict 合并运算符 `\|` 与 `\|=`（3.9+） |
| `[C10]` | PEP 官方 | https://peps.python.org/pep-0202/ | 列表推导式 |
| `[C11]` | PEP 官方 | https://peps.python.org/pep-0274/ | 字典推导式 |
| `[C12]` | python.org | https://docs.python.org/3.12/library/collections.html | `Counter`、`namedtuple`、`deque`（后续章节引用） |
| `[C13]` | python.org | https://docs.python.org/3.12/whatsnew/3.7.html | dict 插入顺序保证 |
| `[C14]` | python.org | https://docs.python.org/3.12/library/copy.html | 浅拷贝与深拷贝 |
| `[C15]` | GitHub 官方 | https://github.com/python/cpython/blob/main/Doc/tutorial/datastructures.rst | 官方教程源文件（`[C2]` 页脚 Show Source 指向） |
| `[C16]` | python.org | https://docs.python.org/3.12/library/exceptions.html | `IndexError`/`KeyError`/`ValueError`/`TypeError`/`RuntimeError` 的定义 |

> **核对状态**：`[C1]` `[C2]` `[C7]` `[C15]` 与本章 `README.md` 已核对来源一致；其余链接按 `docs.python.org/3.12` 与 `peps.python.org` 的官方结构整理，**本次未逐页直连复核**。文中所有「实测」结论均为本机 Python 3.12.8 运行结果。链接失效时请从 `https://docs.python.org/3.12/` 站点导航进入同名页面。

## 13. 毕业自查清单

**能说清（概念层）**：

- [ ] 容器类型的判断标准是什么（`len` / `for` / `in`）
- [ ] 序列、映射、集合三类容器的本质差别
- [ ] 可变与不可变的区别，以及 tuple 内含 list 时「不可变」的真实含义
- [ ] 可哈希与可变性的关系，哪些类型能当 dict 键
- [ ] `==` 与 `is` 的区别，为什么判 `None` 用 `is`
- [ ] 浅拷贝与深拷贝的区别，`b = a` 为什么不是拷贝
- [ ] `list` 的 `in`、`dict` 的 `in`、`set` 的 `in` 分别判断什么
- [ ] 为什么 `set` 不能索引、顺序不保证

**能写出（代码层）**：

- [ ] 用 list 完成增删改查、切片、切片赋值、排序、反转
- [ ] 用列表推导式完成映射、过滤、嵌套展开
- [ ] 用 tuple 完成打包、解包、星号收集、交换变量
- [ ] 用 dict 完成计数、累加、合并、反转、按插入序遍历
- [ ] 用 set 完成去重、交并差、子集判断、保序去重
- [ ] 用 `enumerate` 带序号遍历、用 `zip` 并行遍历
- [ ] 用 `sorted(key=...)` 做稳定排序

**能判断（避坑层）**：

- [ ] 看到 `{}` 能判断是 dict 而不是 set
- [ ] 看到 `(1)` 能判断是 int 而不是 tuple
- [ ] 看到 `[[0]] * 3` 能指出共享问题并改写
- [ ] 看到 `new = lst.sort()` 能指出 `None`
- [ ] 看到遍历中 `remove` / 新增键能指出风险并给出三种改法
- [ ] 看到 `dict.fromkeys(keys, [])` 能指出共享默认值
- [ ] 看到 `[1] + (2,)`、`sorted([1, "a"])` 能预判 `TypeError`
- [ ] 看到依赖集合顺序的断言能指出不可靠

**能跑通（验收层）**：

- [ ] 运行 `examples/containers_demo.py` 并解释每行输出
- [ ] 把第 9 节综合示例存成文件运行，输出与文档一致
- [ ] 在 REPL 逐条验证本文「实测」结论
- [ ] 不看文档，手写「读入若干条 `(工具名, 状态)` → 统计次数 → 去重 → 排序输出」的脚本

## 14. 下一章衔接

第 05 章 `函数`：本章的代码已经出现「同样的计数逻辑要写两遍」的问题（第 9 节里 `counts[name] = counts.get(name, 0) + 1` 若要按状态再统计一次就得复制一遍）。下一章用 `def` 把重复逻辑装起来，同时讲清参数传递——这会直接解释本章埋下的两个伏笔：为什么「把列表传给函数再 append，外部也变了」，以及为什么「默认参数写成 `collected=[]` 会在多次调用间累积」。

本章刻意没展开的：`collections` 的 `Counter` / `defaultdict` / `deque`（22）、`sorted(key=lambda ...)` 的 lambda 写法（07）、容器的类型标注（20）、生成器表达式（17）。
