# 07 lambda 表达式 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把 lambda 的语法、与 `def` 的边界、五个内置高阶函数场景逐条展开，并补上大纲没列的坑，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测） |
| 前置 | 第 05 章（函数、参数、返回值）、第 06 章（闭包、延迟绑定） |
| 覆盖范围 | lambda 语法、与 `def` 对比、`map`/`filter`/`sorted`/`max`/`min`/`reduce`、闭包与 lambda |
| 明确不覆盖 | 装饰器（13）、`functools.partial`（22）、`operator` 模块（22）、类（08） |
| 学完验收 | 能判断什么时候该用 lambda、能写出五种高阶函数调用、能解释循环闭包陷阱（见第 10 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Ln]` `` 指向第 9 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果。

**推荐顺序**：

```text
1 lambda 是什么（第 1 节）→ 匿名函数、单表达式
2 基本语法（第 2 节）     → 参数、返回值、立即调用、限制
3 与 def 对比（第 3 节）  → 什么时候用哪个
4 高阶函数（第 4 节）     → map / filter / sorted / max / min / reduce
5 闭包（第 5 节）         → 捕获变量、延迟绑定
6 综合示例（第 6 节）
7 注意事项（第 7 节）     → 25 条错误对照
```

**与 README 的分工**：README 讲「lambda 是语法糖」，本文件负责穷举场景与边界。冲突时以本文件为准。

## 1. lambda 是什么

**定义**：`lambda` 是**匿名函数**的简写形式，函数体只能是**一个表达式**，表达式的结果就是返回值。`[L1]` `[L2]`

```python
add = lambda a, b: a + b
print(add(1, 2))           # 3
print(add.__name__)        # <lambda>（实测）
```

**与 `def` 的等价关系**：

```python
# 这两种写法功能等价
add_def = lambda a, b: a + b

def add_normal(a, b):
    return a + b

print(add_def(1, 2), add_normal(1, 2))   # 3 3
```

| 维度 | `lambda` | `def` |
| --- | --- | --- |
| 名字 | 匿名（`__name__` 为 `<lambda>`） | 有名字 |
| 函数体 | 一个表达式 | 任意语句块 |
| 返回值 | 表达式结果，不能写 `return` | 显式 `return` |
| 文档字符串 | 不能写 | 可以 |
| 注解 | 不能写参数/返回注解 | 可以 |
| 多行 | 不能（可用括号续行但仍是单表达式） | 可以 |
| 调试 | traceback 只显示 `<lambda>` | 显示函数名与行号 |
| 适用 | 一次性、简单转换 | 所有其他场景 |

> 注意：`lambda` 不是「更快的函数」，也不是「更高级的写法」；它只是「把三行 `def` 压成一行表达式」的语法糖，代价是名字、文档、可调试性。`[L1]`

**什么时候用、什么时候不用**：

| 场景 | 用 lambda | 用 def |
| --- | --- | --- |
| `sorted(key=...)` 里取字段 | ✅ | 也可以，但多写几行 |
| `filter` 一个简单条件 | ✅ | 条件复杂时用 def |
| 需要名字/文档/测试 | ❌ | ✅ |
| 逻辑超过一个表达式 | ❌ | ✅ |
| 需要复用多次 | ❌ | ✅ |
| 需要断点调试 | ❌ | ✅ |

## 2. 基本语法

### 2.1 语法形式

```text
lambda 参数列表: 表达式
```

```python
no_args = lambda: 42
one_arg = lambda x: x * 2
two_args = lambda a, b: a + b
with_default = lambda x, base=10: x + base
with_star = lambda *args: sum(args)
with_kwargs = lambda **kwargs: kwargs
```

| 部分 | 规则 | 依据 |
| --- | --- | --- |
| `lambda` | 关键字 | `[L2]` |
| 参数列表 | 与 `def` 相同的参数形式（默认、`*args`、`**kwargs`、仅关键字） | `[L2]` |
| 冒号 | 必须有 | `[L2]` |
| 表达式 | 只能一个，不能是语句 | `[L2]` |
| 返回值 | 表达式结果，隐式返回 | `[L2]` |

```python
print((lambda: 42)())                  # 42
print((lambda x: x * 2)(3))            # 6
print((lambda a, b: a + b)(1, 2))      # 3
print((lambda x, base=10: x + base)(5))# 15
print((lambda *args: sum(args))(1, 2, 3))       # 6
print((lambda **kwargs: kwargs)(a=1))           # {'a': 1}
```

### 2.2 不能写语句

```python
# 以下是语法错误，不要尝试
# lambda x: return x
# lambda x: x = 1
# lambda x: print(x); x
# lambda x: """docstring"""
```

| 想做的事 | lambda 里怎么写 | 依据 |
| --- | --- | --- |
| 返回结果 | 直接写表达式 | `[L2]` |
| 条件分支 | `a if cond else b` | `[L2]` |
| 赋值 | 不能（3.8+ 可用海象 `:=`） | `[L2]` |
| 多步操作 | 不能，改用 `def` | `[L2]` |

```python
# 条件表达式是唯一的分支手段
classify = lambda score: "A" if score >= 90 else ("B" if score >= 60 else "C")
print(classify(95), classify(70), classify(10))   # A B C

# 海象可以让 lambda 里出现赋值（不推荐，可读性差）
print((lambda x: (y := x * 2) + y)(3))            # 12
```

> 注意：嵌套三元超过一层就该用 `def`；海象在 lambda 里只是「语法上可行」，工程上几乎总是更差的选择。`[L2]` `[L3]`

### 2.3 立即调用（IIFE 风格）

```python
print((lambda x: x * 2)(3))    # 6，定义后立刻调用（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 括号不能省 | `(lambda ...)(args)` 才是调用 | `[L2]` |
| 用途 | 一次性计算、避免临时变量 | `[L1]` |
| 常见于 | 默认值初始化、测试、演示 | `[L1]` |

> 注意：业务代码里「立即调用的 lambda」很少见，通常直接写表达式或用 `def` 更清楚。`[L3]`

### 2.4 参数形式与 `def` 一致

```python
print((lambda a, /, b, *, c: a + b + c)(1, 2, c=3))    # 6，仅位置 + 仅关键字
print((lambda x, y=2: x + y)(1))                        # 3，默认参数
print((lambda *args, sep="-": sep.join(map(str, args)))(1, 2, sep="+"))   # 1+2
```

| 参数形式 | lambda 是否支持 | 依据 |
| --- | --- | --- |
| 位置参数 | ✅ | `[L2]` |
| 默认参数 | ✅ | `[L2]` |
| 关键字传参 | ✅（调用时） | `[L2]` |
| `*args` / `**kwargs` | ✅ | `[L2]` |
| 仅位置 `/` | ✅（3.8+） | `[L2]` |
| 仅关键字 `*` | ✅ | `[L2]` |
| 参数注解 | ❌ | `[L2]` |

> 注意：lambda 不能写注解，所以「需要类型提示的公开接口」一律用 `def`。`[L2]`

### 2.5 返回值只有表达式

```python
lengths = lambda items: [len(item) for item in items]
print(lengths(["a", "bb"]))    # [1, 2]

# 等价于
def lengths_def(items):
    return [len(item) for item in items]
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 表达式结果即返回值 | 不需要 `return` | `[L2]` |
| 可以有副作用 | 但不推荐（如 `append`） | `[L3]` |
| 返回 `None` | 写 `lambda x: print(x)` 会返回 `None` | `[L2]` |

> 注意：`lambda x: print(x)` 能跑，但返回值是 `None`；用它做 `map` 会得到一串 `None`，这是常见误用。`[L2]`

### 2.6 嵌套与柯里化

```python
make_adder = lambda n: (lambda x: x + n)
add_five = make_adder(5)
print(add_five(3))     # 8

double = (lambda factor: lambda value: value * factor)(2)
print(double(5))       # 10（实测）
```

| 写法 | 含义 | 依据 |
| --- | --- | --- |
| `lambda a: lambda b: ...` | 返回函数的函数（柯里化） | `[L2]` |
| 外层参数被内层捕获 | 闭包 | `[L2]` |
| 可读性 | 嵌套超过一层就改用 `def` | `[L3]` |

> 注意：`(lambda factor: lambda value: ...)(2)` 这种「立即调用 + 返回函数」的写法只在演示里可爱，生产代码写成两个 `def` 更易读。`[L3]`

### 2.7 调试与可观测性

```python
add = lambda a, b: a + b
print(add.__name__, add.__qualname__)   # <lambda> <lambda>（实测）
```

| 问题 | 现象 | 依据 |
| --- | --- | --- |
| traceback 不显示名字 | 只显示 `<lambda>` 和行号 | `[L2]` |
| 不能写 docstring | `__doc__` 为 `None` | `[L2]` |
| IDE 无法跳转 | 没有名字可跳 | `[L3]` |
| 日志里难看 | `<lambda>` 无法区分是哪个 | `[L3]` |

> 注意：当你在 traceback 里看到一堆 `<lambda>` 却不知道是哪一个时，就该把它改成 `def` 了。`[L3]`

## 3. Lambda vs 普通函数

### 3.1 能力对比

| 能力 | lambda | def |
| --- | --- | --- |
| 任意多条语句 | ❌ | ✅ |
| 显式 `return` | ❌ | ✅ |
| docstring | ❌ | ✅ |
| 参数/返回注解 | ❌ | ✅ |
| 递归（需要名字） | ⚠️ 困难 | ✅ |
| 被装饰器装饰 | ⚠️ 可以但无意义 | ✅ |
| 作为参数传入 | ✅ | ✅ |
| 就地定义、不占名字 | ✅ | ❌ |
| 可读的名字 | ❌ | ✅ |

### 3.2 PEP 8 的明确立场

> *"Always use a def statement instead of an assignment statement that binds a lambda expression directly to an identifier."* `[L3]`

```python
# 不推荐（PEP 8 明确反对）
f = lambda x: x * 2

# 推荐
def f(x):
    return x * 2

# 推荐（真正适合 lambda 的用法：作为参数）
result = sorted(items, key=lambda item: item.cost)
```

| 写法 | PEP 8 态度 | 原因 |
| --- | --- | --- |
| `f = lambda x: ...` | ❌ 反对 | 等价于 def 但丢了名字/文档 |
| `sorted(key=lambda ...)` | ✅ 合理 | 就地使用、不需要名字 |
| `map(lambda ...)` | ✅ 合理 | 同上 |

> 注意：PEP 8 反对的是「把 lambda 赋给标识符」，不是反对 lambda 本身；`key=`、`map` 里的用法完全合规。`[L3]`

### 3.3 可读性对比

```python
# 版本 A：lambda 赋值（差）
cut = lambda text, n: text[:n] + "..." if len(text) > n else text

# 版本 B：def（好）
def cut(text, n):
    """超过 n 个字符时截断并加省略号。"""
    return text[:n] + "..." if len(text) > n else text
```

| 维度 | A | B |
| --- | --- | --- |
| 能看懂 | 要读完整行 | 有名字和文档 |
| 能测试 | 可以，但名字是 `<lambda>` | 可以 |
| 能调试 | 难 | 易 |
| 能复用 | 可以 | 可以 |

### 3.4 什么时候真的该用 lambda

| 场景 | 例子 |
| --- | --- |
| 排序键 | `sorted(rows, key=lambda r: r[1])` |
| 过滤条件 | `filter(lambda x: x > 0, values)` |
| 极值键 | `max(rows, key=lambda r: r[2])` |
| 映射转换 | `map(lambda x: x.strip(), lines)` |
| 回调参数 | `button.on_click(lambda: save())` |

> 注意：只要这个 lambda **需要被命名**（赋值给变量、出现在日志、需要测试），就应该改成 `def`。`[L3]`

## 4. 应用场景：内置高阶函数

**高阶函数** = 接受函数作为参数（或返回函数）的函数。`lambda` 的主要用途就是给它们提供「一次性小函数」。`[L1]`

### 4.1 `map()` —— 映射

```python
numbers = [1, 2, 3]
print(list(map(lambda x: x * 2, numbers)))    # [2, 4, 6]（实测）
print(type(map(lambda x: x, numbers)).__name__)  # map（实测）
```

| 参数 | 说明 | 依据 |
| --- | --- | --- |
| `func` | 接收 1 个参数（多序列时接收 N 个） | `[L4]` |
| `iterable` | 可迭代对象，可传多个 | `[L4]` |
| 返回 | **迭代器**（3.x），惰性 | `[L4]` |
| 多序列 | 按最短截断 | `[L4]` |

```python
print(list(map(lambda a, b: a + b, [1, 2], [10, 20])))   # [11, 22]（实测）
```

**`map` vs 列表推导式**：

```python
# 等价
print(list(map(lambda x: x * 2, numbers)))    # [2, 4, 6]
print([x * 2 for x in numbers])               # [2, 4, 6]
```

| 场景 | 推荐 | 理由 | 依据 |
| --- | --- | --- | --- |
| 已有现成函数 | `list(map(str.strip, lines))` | 更短，C 层调用 | `[L4]` |
| 需要表达式 | `[x * 2 for x in xs]` | 不用 lambda，更易读 | `[L9]` |
| 需要惰性 | `map(...)` | 不立即生成列表 | `[L4]` |
| 需要过滤 | `[x for x in xs if cond]` | 一步完成 | `[L9]` |

> 注意：`map` 返回迭代器，**只能消费一次**；打印结果是 `<map object at 0x...>`，不是 `[2, 4, 6]`。`[L4]`

### 4.2 `filter()` —— 过滤

```python
print(list(filter(lambda x: x % 2 == 0, [1, 2, 3, 4])))   # [2, 4]（实测）
print(type(filter(None, [1])).__name__)                    # filter（实测）
```

| 参数 | 说明 | 依据 |
| --- | --- | --- |
| `func` | 返回真/假；传 `None` 时用元素真值判断 | `[L5]` |
| `iterable` | 可迭代对象 | `[L5]` |
| 返回 | 迭代器 | `[L5]` |

```python
print(list(filter(None, [0, 1, "", "a", None])))   # [1, 'a']（实测）
```

| 写法 | 结果 | 依据 |
| --- | --- | --- |
| `filter(None, xs)` | 去掉假值（`0`/`""`/`None`/空容器） | `[L5]` |
| `filter(lambda x: x > 0, xs)` | 自定义条件 | `[L5]` |
| `[x for x in xs if cond]` | 等价、通常更可读 | `[L9]` |

> 注意：`filter(None, xs)` 会把 `0` 也过滤掉；如果 `0` 是有效数据，必须写显式条件 `lambda x: x is not None`。`[L5]`

### 4.3 `sorted()` —— 排序（指定 key）

```python
pairs = [("b", 2), ("a", 3), ("c", 1)]

print(sorted(pairs, key=lambda item: item[1]))
# [('c', 1), ('b', 2), ('a', 3)]（实测）

print(sorted(pairs, key=lambda item: item[1], reverse=True))
# [('a', 3), ('b', 2), ('c', 1)]（实测）
```

| 参数 | 说明 | 依据 |
| --- | --- | --- |
| `key` | 每个元素算一个排序键 | `[L6]` |
| `reverse` | 是否降序 | `[L6]` |
| 返回 | 新 `list`，原对象不变 | `[L6]` |
| 稳定性 | 相等元素的相对顺序保持 | `[L6]` |

```python
stable = [("a", 1), ("b", 1), ("c", 0)]
print(sorted(stable, key=lambda item: item[1]))
# [('c', 0), ('a', 1), ('b', 1)]（实测，a 在 b 前保持原序）
```

**常见排序写法**：

| 目标 | 写法 |
| --- | --- |
| 按第二列升序 | `sorted(rows, key=lambda r: r[1])` |
| 按第二列降序 | `sorted(rows, key=lambda r: r[1], reverse=True)` |
| 多关键字（主、次） | `sorted(rows, key=lambda r: (r[1], r[0]))` |
| 忽略大小写 | `sorted(words, key=str.lower)` |
| 按长度 | `sorted(words, key=len)` |
| 字典按值排序 | `sorted(d.items(), key=lambda kv: kv[1])` |

> 注意：`sorted(xs, key=lambda x: x)` 等价于 `sorted(xs)`，是多余写法；`key` 里不要做副作用（如 `append`）。`[L6]` `[L3]`

**`list.sort()` 与 `sorted()` 的分工**：

| 写法 | 是否改原列表 | 返回 | 依据 |
| --- | --- | --- | --- |
| `lst.sort(key=...)` | 是 | `None` | `[L8]` |
| `sorted(lst, key=...)` | 否 | 新 list | `[L6]` |

### 4.4 `max()` / `min()` —— 极值（指定 key）

```python
pairs = [("b", 2), ("a", 3), ("c", 1)]

print(max(pairs, key=lambda item: item[1]))   # ('a', 3)（实测）
print(min(pairs, key=lambda item: item[1]))   # ('c', 1)（实测）
```

| 参数 | 说明 | 依据 |
| --- | --- | --- |
| `key` | 按什么比较 | `[L6]` |
| `default` | 空序列时的默认值（3.4+） | `[L6]` |
| 返回 | 原始元素，不是 key | `[L6]` |

```python
print(max([], key=lambda x: x, default="空"))   # 空
# max([]) 不加 default 会 ValueError
```

| 容易踩的点 | 说明 |
| --- | --- |
| 返回的是元素 | `max(pairs, key=...)` 返回 tuple，不是 key |
| 空序列 | 必须给 `default`，否则 `ValueError` |
| 多个同 key | 返回第一个遇到的（稳定） |

> 注意：`max(dict, key=...)` 迭代的是键；要按值取最大，用 `max(d.items(), key=lambda kv: kv[1])`。`[L6]`

### 4.5 `reduce()` —— 累积计算

**注意**：`reduce` 在 Python 3 被移到 `functools`，必须 `import`。`[L7]`

```python
import functools

print(functools.reduce(lambda a, b: a * b, [1, 2, 3, 4]))      # 24（实测）
print(functools.reduce(lambda a, b: a + b, [1, 2], 10))        # 13（实测，初始值 10）
```

| 参数 | 说明 | 依据 |
| --- | --- | --- |
| `function` | 接收两个参数，返回累积值 | `[L7]` |
| `iterable` | 要折叠的序列 | `[L7]` |
| `initializer` | 可选初始值；不传时用第一个元素 | `[L7]` |
| 空序列 | 不传初始值会 `TypeError` | `[L7]` |

**执行过程（左折叠）**：

```text
reduce(f, [1, 2, 3, 4])
= f(f(f(1, 2), 3), 4)
= ((1*2)*3)*4
= 24
```

| 场景 | 替代写法 | 说明 |
| --- | --- | --- |
| 求和 | `sum(xs)` | 更清楚 |
| 求积 | `math.prod(xs)`（3.8+） | 更清楚 |
| 最大值 | `max(xs)` | 更清楚 |
| 字符串拼接 | `"".join(xs)` | 更高效 |
| 复杂累积 | `reduce` 或显式循环 | 循环通常更易读 |

> 注意：`reduce` 的可读性通常差于显式循环；只有在「累积规则本身就是参数」时才值得用。`[L7]` `[L3]`

### 4.6 五个函数速查

| 函数 | 输入 | 返回 | 是否需要 `list()` | 依据 |
| --- | --- | --- | --- | --- |
| `map(f, xs)` | 函数 + 可迭代 | 迭代器 | 是（要列表时） | `[L4]` |
| `filter(f, xs)` | 函数或 `None` + 可迭代 | 迭代器 | 是 | `[L5]` |
| `sorted(xs, key=)` | 可迭代 | 新 list | 否 | `[L6]` |
| `max/min(xs, key=)` | 可迭代 | 元素 | 否 | `[L6]` |
| `reduce(f, xs, init)` | 函数 + 可迭代 | 标量/对象 | 否 | `[L7]` |

## 5. 闭包与 lambda

### 5.1 lambda 会捕获外层变量

```python
def make_multiplier(factor):
    return lambda value: value * factor

double = make_multiplier(2)
print(double(5))      # 10（README 同款）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| lambda 是函数 | 同样遵循 LEGB（第 06 章） | `[L2]` |
| 捕获的是变量 | 不是当时的值 | `[L2]` |
| 外层返回后仍可用 | 闭包 cell 存活 | `[L2]` |

### 5.2 延迟绑定（最经典的坑）

```python
handlers = []
for index in range(3):
    handlers.append(lambda: index)

print([handler() for handler in handlers])   # [2, 2, 2]（实测）
```

| 原因 | 说明 | 依据 |
| --- | --- | --- |
| 捕获变量 `index` | 循环结束后 `index` 是 2 | `[L2]` |
| 不是捕获值 | 所有 lambda 共用一个变量 | `[L2]` |

**修复**：

```python
handlers = []
for index in range(3):
    handlers.append(lambda index=index: index)
print([handler() for handler in handlers])   # [0, 1, 2]（实测）
```

| 方案 | 原理 |
| --- | --- |
| `lambda index=index:` | 默认参数在定义时求值，把当前值固化 |
| 工厂函数 | 每次调用生成新 cell |

> 注意：只要在循环里创建 lambda 或内层函数，就必须检查这一点；这是「闭包捕获变量」的直接后果，不是 lambda 独有。`[L2]`

### 5.3 lambda 工厂与 `functools.partial`

```python
import functools

add_ten = functools.partial(lambda a, b: a + b, 10)
print(add_ten(5))     # 15
```

| 方案 | 适用 | 依据 |
| --- | --- | --- |
| `lambda x: f(x, 10)` | 简单、一次性 | `[L2]` |
| `functools.partial(f, 10)` | 需要复用、可 pickle | `[L7]` |
| `def` 包装 | 需要文档与类型 | `[L3]` |

> 注意：`partial` 属于第 22 章标准库；这里只需知道「固定部分参数」不一定要写 lambda。`[L7]`

## 6. 综合示例：用 lambda 做筛选、映射与排序

```python
"""第 07 章综合示例：map / filter / sorted 组合。"""

tools = [
    ("search", 3, True),
    ("cache", 1, False),
    ("translate", 2, True),
]

active = list(filter(lambda item: item[2], tools))
names = list(map(lambda item: item[0], active))
costs = sum(map(lambda item: item[1], active))
by_cost = sorted(tools, key=lambda item: item[1], reverse=True)

print("启用工具:", names)
print("总成本:", costs)
print("按成本降序:", by_cost)
```

本机实测输出：

```text
启用工具: ['search', 'translate']
总成本: 5
按成本降序: [('search', 3, True), ('translate', 2, True), ('cache', 1, False)]
```

**逐段说明**：

| 代码 | 作用 | 依据 |
| --- | --- | --- |
| `filter(lambda item: item[2], tools)` | 保留第 3 列为真的元素 | `[L5]` |
| `list(filter(...))` | 迭代器转列表 | `[L5]` |
| `map(lambda item: item[0], active)` | 取第 1 列 | `[L4]` |
| `sum(map(lambda item: item[1], active))` | 第 2 列求和 | `[L4]` |
| `sorted(..., key=lambda item: item[1], reverse=True)` | 按成本降序 | `[L6]` |

**用推导式改写（可读性对比）**：

```python
active = [item for item in tools if item[2]]
names = [item[0] for item in active]
costs = sum(item[1] for item in active)
by_cost = sorted(tools, key=lambda item: item[1], reverse=True)
```

| 版本 | 优点 | 缺点 |
| --- | --- | --- |
| `filter` + `map` | 显式表达「函数式」 | 需要 `list()`，链条长 |
| 推导式 | 不用 lambda、一眼看懂 | 略长 |

> 注意：两者等价；团队统一一种即可。`sorted(key=...)` 用 lambda 是共识写法，`filter`/`map` 在有推导式时优先级更低。`[L9]` `[L3]`

## 7. 注意事项与新手错误对照表

| 错误写法 / 操作 | 报错或现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `f = lambda x: x` | 不符合 PEP 8 | `def f(x):` | `[L3]` |
| `lambda x: return x` | `SyntaxError` | 直接写表达式 | `[L2]` |
| `lambda x: x = 1` | `SyntaxError` | 用 `def` | `[L2]` |
| `lambda x: print(x); x` | `SyntaxError` | 用 `def` | `[L2]` |
| `lambda x: """doc"""` | 不是 docstring | 用 `def` | `[L2]` |
| `lambda (x): x` | `SyntaxError`（3.x 不支持元组参数） | `lambda x: x` | `[L2]` |
| `lambda: 1` 忘了调用 | 打印出函数对象 | 加 `()` | `[L2]` |
| `map(...)` 直接 `print` | `<map object at ...>` | `list(map(...))` | `[L4]` |
| `map` 对象用两次 | 第二次为空 | 先转 `list` | `[L4]` |
| `filter(...)` 当列表用 | `TypeError`（迭代器） | `list(filter(...))` | `[L5]` |
| `filter(None, [0, 1])` | `0` 被过滤 | 显式条件 | `[L5]` |
| `sorted(xs, key=lambda x: x)` | 多余 | `sorted(xs)` | `[L6]` |
| 排序对象没给 `key` | `TypeError` | 按字段取 key | `[L6]` |
| `key` 返回 `None` | `TypeError`（与数字比较） | 过滤 `None` 或用哨兵 | `[L6]` |
| `key` 返回混合类型 | `TypeError` | 统一类型 | `[L6]` |
| `max([])` | `ValueError` | `default=` | `[L6]` |
| `reduce` 空序列无初值 | `TypeError` | 传 `initializer` | `[L7]` |
| 循环里 `lambda: i` | 全部最终值 | `lambda i=i: i` | `[L2]` |
| lambda 里做副作用 | 结果不可预期 | 用普通循环 | `[L3]` |
| 复杂逻辑塞 lambda | 难读 | `def` | `[L3]` |
| 用 lambda 需要断点调试 | traceback 只有 `<lambda>` | `def` | `[L2]` |
| lambda 需要 docstring | 写不了 | `def` | `[L2]` |
| lambda 需要类型注解 | 写不了 | `def` | `[L2]` |
| lambda 里 `yield` | `SyntaxError` | 用 `def` 生成器 | `[L2]` |
| 用 lambda 写递归 | 需要先赋值再引用，难读 | `def` | `[L3]` |
| 用 `map` 替代 `sum` | 多绕一层 | `sum(xs)` | `[L4]` |
| 嵌套多层 lambda | 可读性差 | 拆 `def` | `[L3]` |
| 用 lambda 排序含 `None` 的字段 | `TypeError` | 先过滤或 `key` 里兜底 | `[L6]` |

## 8. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 只用于一次性小函数 | 需要名字就写 `def` | `[L3]` |
| 优先 `sorted(key=lambda ...)` | 这是 lambda 最正当的用法 | `[L6]` |
| 有现成函数就别包 lambda | `key=str.lower` 优于 `lambda x: x.lower()` | `[L6]` |
| 不把 lambda 赋给变量 | PEP 8 明确反对 | `[L3]` |
| 不在 lambda 里做副作用 | 难以推理与测试 | `[L3]` |
| 表达式保持一行能读懂 | 嵌套三元/海象一律改用 `def` | `[L3]` |
| 循环里创建 lambda 要固化变量 | `i=i` 或工厂函数 | `[L2]` |
| 需要文档/类型/测试就换 `def` | lambda 三者都给不了 | `[L2]` |
| `map`/`filter` 记得 `list()` | 否则拿到迭代器 | `[L4]` `[L5]` |
| 求和使用 `sum`、拼接使用 `join` | 不要为炫技用 `reduce` | `[L7]` |

**风格示范**：

```python
# 好：作为排序键
rows = sorted(rows, key=lambda row: (row["cost"], row["name"]))

# 好：有现成函数就直接传
rows = sorted(words, key=str.lower)

# 好：需要名字与文档就用 def
def is_active(tool):
    """工具是否启用。"""
    return tool.enabled

# 差：把 lambda 赋给变量
is_active = lambda tool: tool.enabled
```

**边界与安全**：

- 不要把用户输入拼进 `eval` 再交给 `map`（代码注入）。
- `lambda` 里不要访问敏感全局变量做日志输出。
- 排序键里不要做 I/O（每次比较都会触发副作用，性能与正确性双输）。

## 9. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[L1]` | python.org | https://docs.python.org/3.12/tutorial/controlflow.html | `lambda` 表达式入门、`sorted(key=...)` 示例、`map`/`filter` 的定位 |
| `[L2]` | python.org | https://docs.python.org/3.12/reference/expressions.html | lambda 语法与语义、只能一个表达式、参数形式、`__name__` |
| `[L3]` | PEP 官方 | https://peps.python.org/pep-0008/ | 「不要用赋值语句绑定 lambda」的明确规定、可读性要求 |
| `[L4]` | python.org | https://docs.python.org/3.12/library/functions.html#map | `map` 的参数、返回迭代器、多序列按最短截断 |
| `[L5]` | python.org | https://docs.python.org/3.12/library/functions.html#filter | `filter` 的参数、`None` 表示真值判断、返回迭代器 |
| `[L6]` | python.org | https://docs.python.org/3.12/library/functions.html#sorted | `sorted` 的 `key`/`reverse`、稳定性、`max`/`min` 的 `key` 与 `default` |
| `[L7]` | python.org | https://docs.python.org/3.12/library/functools.html#functools.reduce | `reduce` 在 `functools`、`initializer`、左折叠语义、`partial` |
| `[L8]` | python.org | https://docs.python.org/3.12/library/stdtypes.html#list.sort | `list.sort` 就地排序、返回 `None`、与 `sorted` 的分工 |
| `[L9]` | PEP 官方 | https://peps.python.org/pep-0202/ | 列表推导式（与 `map`/`filter` 的取舍） |
| `[L10]` | GitHub 官方 | https://github.com/python/cpython/blob/main/Doc/tutorial/controlflow.rst | 官方教程源文件（`[L1]` 页脚 Show Source 指向） |

> **核对状态**：`[L1]` `[L3]` `[L10]` 与本章 `README.md` 已核对来源一致；其余链接按 `docs.python.org/3.12` 与 `peps.python.org` 官方结构整理，**本次未逐页直连复核**。文中「实测」结论均为本机 Python 3.12.8 运行结果。

## 10. 毕业自查清单

**能说清（概念层）**：

- [ ] lambda 与 `def` 的等价关系，以及三条能力差异（语句、docstring、注解）
- [ ] 为什么 lambda 只能写一个表达式
- [ ] PEP 8 反对的具体是什么写法，为什么
- [ ] `map` / `filter` 返回什么类型，为什么需要 `list()`
- [ ] `sorted` 的 `key` 与 `reverse` 分别控制什么，稳定性意味着什么
- [ ] `max` / `min` 返回的是元素还是 key
- [ ] `reduce` 为什么在 `functools`，左折叠怎么算
- [ ] 循环里创建 lambda 为什么都返回最后一个值

**能写出（代码层）**：

- [ ] 用 lambda 写两参数、默认参数、`*args` 版本
- [ ] 立即调用 lambda 完成一次性计算
- [ ] 用 `sorted(key=lambda ...)` 按字段、按多字段排序
- [ ] 用 `max(key=lambda ...)` 取成本最高的记录
- [ ] 用 `filter` + `map` 完成「筛 → 转 → 汇总」
- [ ] 用 `functools.reduce` 求累积乘积并传入初始值
- [ ] 用 `lambda i=i` 修复循环延迟绑定
- [ ] 用列表推导式写出与 `map`/`filter` 等价的版本

**能判断（避坑层）**：

- [ ] 看到 `f = lambda ...` 能指出 PEP 8 问题并改写
- [ ] 看到 `print(map(...))` 能指出输出的是对象
- [ ] 看到 `filter(None, xs)` 能指出 `0` 会被过滤
- [ ] 看到 `sorted(xs, key=lambda x: x)` 能指出多余
- [ ] 看到 `max([])` 能指出 `ValueError`
- [ ] 看到复杂嵌套 lambda 能建议改 `def`
- [ ] 看到 traceback 里 `<lambda>` 能定位到「应改用 def」

**能跑通（验收层）**：

- [ ] 运行 `examples/lambda_demo.py` 并解释两次排序的差别
- [ ] 把第 6 节示例存成文件运行，输出与文档一致
- [ ] 在 REPL 验证「`map` 对象只能消费一次」
- [ ] 手写「一组记录 → 过滤 → 取字段 → 求和 → 按字段排序输出」的完整脚本

## 11. 下一章衔接

第 08 章 `类和对象`：本章的 `lambda` 只是「没有名字的函数」，下一章会讲「带状态的对象」——把一组函数和它们共享的数据装进同一个结构。

本章留下的三个伏笔会在第 08 章展开：

1. `sorted(key=lambda item: item.cost)` 里的 `item.cost` 是**属性访问**，下一章才知道它是怎么来的。
2. `filter(lambda t: t.enabled, tools)` 里的 `t.enabled` 同理；到第 08 章你会写出自己的 `Tool` 类，而不是用 tuple 的下标。
3. 本章用 lambda 做「一次性行为」，第 13 章的装饰器会用函数做「包装行为」——两者都建立在第 05–07 章的函数对象模型上。