# 05 函数 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把大纲逐条展开，并补上大纲没列、但写函数一定会遇到的语法与陷阱，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测）；`/` 仅位置参数为 3.8+ |
| 前置 | 第 03–04 章（变量、控制流、容器） |
| 覆盖范围 | 定义函数、参数（位置/默认/关键字/可变/顺序）、返回值、文档字符串、递归、高阶函数预告 |
| 明确不覆盖 | 作用域细节（06）、`lambda`（07）、闭包（06）、装饰器（13）、类型标注（20） |
| 学完验收 | 能写出带默认参数、`*args`、`**kwargs` 的函数，能解释参数传递、能识别可变默认值陷阱（见第 11 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Fn]` `` 指向第 10 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果。

**推荐顺序**：

```text
1 函数是什么（第 1 节）→ 为什么要把代码装进函数
2 定义函数（第 2 节）  → def 的语法与执行顺序
3 参数（第 3 节）      → 五种参数形态与顺序规则（本章核心）
4 返回值（第 4 节）    → return、None、多返回值
5 文档字符串（第 5 节）→ 让别人（和 IDE）看懂你的函数
6 进阶（第 6 节）      → 递归、函数对象、高阶函数预告
7 综合示例（第 7 节）
8 注意事项（第 8 节）  → 35 条错误对照
```

**与 README 的分工**：README 讲取舍，本文件负责穷举与避坑。冲突时以本文件为准。

## 1. 函数是什么、为什么需要

**定义**：函数是「有名字、可重复调用、带参数与返回值的一段代码」。它把「做什么」和「怎么调用」拆开。`[F1]`

```python
def greet(name):
    return f"你好，{name}"

print(greet("search"))
print(greet("cache"))
```

**不用函数 vs 用函数**：

| 写法 | 问题 |
| --- | --- |
| 同一段统计逻辑复制三遍 | 改一处漏两处，无法测试 |
| 变量名随处复用 | 互相覆盖，难追踪 |
| 主流程几百行 | 读不出「这一步在做什么」 |

| 收益 | 说明 | 依据 |
| --- | --- | --- |
| 复用 | 写一次，处处调用 | `[F1]` |
| 抽象 | 调用方只需知道「输入 → 输出」 | `[F1]` |
| 可测试 | 给定输入断言输出 | `[F1]` |
| 命名即文档 | `build_report(...)` 比一段裸代码更易读 | `[F4]` |
| 隔离 | 局部变量不污染外部（第 06 章） | `[F1]` |

**函数是对象**：

```python
def documented(tool):
    """返回工具名。"""
    return tool

alias = documented          # 函数可以赋值给另一个名字
print(alias("search"))      # search
print(alias is documented)  # True，同一个对象（实测）
print(type(documented))     # <class 'function'>
```

> 注意：能赋值、能当参数、能当返回值，是「一切皆对象」的直接后果；第 07 章的 `lambda`、第 13 章的装饰器都建立在这条之上。`[F10]`

## 2. 定义函数

### 2.1 语法结构

```python
def 函数名(参数列表):
    """可选文档字符串。"""
    函数体
    return 返回值          # 可选
```

```python
def build_report(tool_name, results, limit=3):
    """返回工具结果摘要；limit 控制保留条数。"""
    selected = results[:limit]
    return {"tool": tool_name, "count": len(selected), "items": selected}
```

| 组成部分 | 规则 | 依据 |
| --- | --- | --- |
| `def` | 关键字，声明函数 | `[F1]` |
| 函数名 | 标识符规则；PEP 8 用 `snake_case` | `[F4]` |
| 括号 | 必须有，即使无参数：`def f():` | `[F2]` |
| 冒号 | 必须有 | `[F1]` |
| 函数体 | 必须缩进；空函数体写 `pass` | `[F1]` |
| 文档字符串 | 可选，放在函数体第一条语句 | `[F5]` |
| `return` | 可选，省略返回 `None` | `[F1]` |

### 2.2 调用与执行顺序

```python
def outer():
    print("A")
    inner()
    print("C")

def inner():
    print("B")

outer()
# A
# B
# C
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 定义时不执行函数体 | 只创建函数对象 | `[F1]` |
| 调用时才执行 | 每次调用都重新执行函数体 | `[F1]` |
| 必须先定义后调用 | 调用时名字还没绑定会 `NameError` | `[F1]` |
| 函数内可调用后面定义的函数 | 只要调用发生时那个名字已存在 | `[F1]` |

```python
try:
    not_defined()
except NameError as error:
    print(type(error).__name__)   # NameError
```

> 注意：`outer` 里调用 `inner` 能成功，是因为 `outer()` 执行时 `inner` 已经定义；如果把 `outer()` 提到 `def inner` 之前，就会 `NameError`。`[F1]`

### 2.3 函数名规则与命名

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 标识符规则 | 字母/下划线开头，不能用关键字 | `[F2]` |
| 区分大小写 | `report` 与 `Report` 无关 | `[F2]` |
| 动词开头 | `build_` / `get_` / `is_` / `has_` 表达意图 | `[F4]` |
| 不要与内置名冲突 | `len` / `list` / `str` / `sum` 会被覆盖 | `[F4]` |
| 私有约定 | 单下划线前缀 `_helper` 表示内部使用 | `[F4]` |

```python
def shadows_len():
    return "shadowed"

print(shadows_len())   # shadowed
# 但如果写 def len(...)，后面所有 len() 调用都会被打断
```

> 注意：覆盖内置函数不会报错，只会在别处静默出错；命名前先想一下是不是内置名。`[F4]`

### 2.4 空函数体与占位

```python
def todo():
    pass            # 合法：函数体不能为空

def todo2():
    ...             # 省略号也是合法表达式，常用来占位

def todo3():
    """只有文档字符串也算函数体。"""
```

| 占位符 | 说明 | 依据 |
| --- | --- | --- |
| `pass` | 空语句，什么都不做 | `[F1]` |
| `...` | `Ellipsis` 对象，合法表达式 | `[F3]` |

> 注意：`pass` 与 `...` 只是让语法通过；真正的空实现应写清楚「为什么还没实现」，否则是技术债。`[F4]`

### 2.5 嵌套定义（作用域预告）

```python
def outer():
    def inner():
        return "inner"
    return inner()

print(outer())      # inner
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 函数内可定义函数 | 内层函数默认只在外层可见 | `[F2]` |
| 内层可引用外层变量 | 闭包的基础，第 06 章详讲 | `[F2]` |
| 嵌套不是必须 | 能用模块级函数就别嵌套 | `[F4]` |

> 注意：嵌套定义的主要用途是「只给外层用的辅助函数」和「闭包」；业务代码里层层嵌套会降低可读性。`[F4]`

## 3. 参数

### 3.1 五种参数形态总览

| 形态 | 写法 | 调用方式 | 接收类型 | 依据 |
| --- | --- | --- | --- | --- |
| 位置参数 | `def f(a, b)` | `f(1, 2)` | 按顺序 | `[F1]` |
| 默认参数 | `def f(a, b=2)` | `f(1)` / `f(1, 3)` | 缺省用默认值 | `[F1]` |
| 关键字参数 | 调用时 `f(b=2, a=1)` | 按名字传 | 与位置无关 | `[F1]` |
| 可变位置参数 | `def f(*args)` | `f(1, 2, 3)` | `tuple` | `[F1]` |
| 可变关键字参数 | `def f(**kwargs)` | `f(a=1, b=2)` | `dict` | `[F1]` |
| 仅位置参数 | `def f(a, /, b)` | `f(1, 2)`，`a` 不能用名字 | — | `[F7]` |
| 仅关键字参数 | `def f(a, *, b)` | `f(1, b=2)` | `b` 必须用名字 | `[F6]` |

### 3.2 位置参数

```python
def build_report(tool_name, results, limit):
    return {"tool": tool_name, "count": len(results[:limit])}

print(build_report("search", ["a", "b", "c"], 2))
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 按顺序绑定 | 第一个实参给第一个形参 | `[F1]` |
| 数量必须匹配 | 少给/多给都 `TypeError` | `[F3]` |
| 名字不必相同 | 调用方不需要知道形参名 | `[F1]` |

```python
try:
    build_report("search", ["a"])
except TypeError as error:
    print(type(error).__name__)   # TypeError: missing 1 required positional argument
```

### 3.3 关键字参数

```python
def build_report(tool_name, results, limit=3):
    return {"tool": tool_name, "count": len(results[:limit])}

# 顺序无关，按名字绑定
print(build_report(results=["x"], tool_name="cache", limit=1))
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 按名字绑定 | 顺序无所谓 | `[F1]` |
| 可读性 | `limit=1` 比裸 `1` 清楚 | `[F4]` |
| 不能重复传参 | 位置传了 `a` 又写 `a=...` 会 `TypeError` | `[F3]` |
| 名字必须匹配 | 拼错形参名会 `TypeError` | `[F3]` |

```python
try:
    build_report("x", 1, 2, 3, name="y")
except TypeError as error:
    print(type(error).__name__)   # TypeError（实测）
```

> 注意：参数超过 3 个、或布尔/数字实参容易混淆时，**调用方**应写关键字参数，这是可读性收益最大的一处。`[F4]`

### 3.4 默认参数

```python
def build_report(tool_name, results, limit=3):
    return {"tool": tool_name, "count": len(results[:limit])}

print(build_report("search", ["a", "b", "c", "d"]))   # 用默认 3
print(build_report("search", ["a", "b"], 1))          # 覆盖默认
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 默认值在**定义时**求值一次 | 不是每次调用重新求值 | `[F1]` |
| 默认参数必须在非默认参数之后 | `def f(a=1, b)` 是 `SyntaxError` | `[F2]` |
| 默认值可以是任意表达式 | 包括函数调用、可变对象（危险） | `[F1]` |
| 调用方不传才用默认 | 传 `None` 也算传了 | `[F1]` |

**默认值只在定义时算一次（实测）**：

```python
def mutable_default(value, bucket=[]):
    bucket.append(value)
    return bucket

print(mutable_default(1))   # [1]
print(mutable_default(2))   # [1, 2]，同一个列表被复用
```

正确写法（官方教程同款）：

```python
def safe_default(value, bucket=None):
    if bucket is None:
        bucket = []
    bucket.append(value)
    return bucket

print(safe_default(1))   # [1]
print(safe_default(2))   # [2]，每次新建
```

> 注意：这是 Python 最著名的陷阱之一。默认值只在 `def` 执行时求值一次并保存在 `函数.__defaults__`；想要「每次调用一个新的」，默认写 `None` 再在函数内创建。`[F1]` `[F4]`

### 3.5 可变位置参数 `*args`

```python
def collect(*args):
    print(args, type(args).__name__)

collect()            # () tuple
collect(1)           # (1,) tuple
collect(1, "a", [2]) # (1, 'a', [2]) tuple
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 收集成 `tuple` | 不是 list（实测 `ARGS_TYPE tuple`） | `[F1]` |
| 可以为空 | 不传就是 `()` | `[F1]` |
| 一个函数只能有一个 | 名字习惯写 `args`，可自定义 | `[F1]` |
| 它之后可跟仅关键字参数 | `def f(*args, sep=",")` | `[F6]` |

> 注意：`*args` 只是**约定名**，写 `*values` 一样合法；`args` 本身是 tuple，不能 `append`。`[F1]`

### 3.6 可变关键字参数 `**kwargs`

```python
def build(name, **kwargs):
    print(kwargs, type(kwargs).__name__)

build("x")                      # {} dict
build("x", limit=5, extra=True) # {'limit': 5, 'extra': True} dict
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 收集成 `dict` | 键是参数名（字符串） | `[F1]` |
| 可以为空 | 不传就是 `{}` | `[F1]` |
| 键必须是合法标识符 | `f(**{"a-b": 1})` 能传但函数内只能 `kwargs["a-b"]` | `[F3]` |
| 一个函数只能有一个 | 习惯名 `kwargs` | `[F1]` |

> 注意：`**kwargs` 会吞掉所有「拼错的参数名」，让 `TypeError` 变成静默忽略；对外 API 不要无脑加 `**kwargs`。`[F4]`

### 3.7 仅位置参数 `/`（3.8+）

```python
def pos_only(a, /, b, *, c):
    return a + b + c

print(pos_only(1, 2, c=3))      # 6
# pos_only(a=1, b=2, c=3)       TypeError：a 不能用关键字传
```

| 用途 | 说明 | 依据 |
| --- | --- | --- |
| 防止调用方依赖参数名 | 参数改名不算破坏兼容 | `[F7]` |
| 与 C 实现的内置函数一致 | `len(obj=...)` 本来就不行 | `[F7]` |
| `/` 左侧只能按位置 | 右侧规则不变 | `[F7]` |

> 注意：日常业务函数很少需要 `/`；它是给库作者控制 API 兼容性用的。`[F7]`

### 3.8 仅关键字参数 `*`

```python
def keyword_only(a, *, b, c=3):
    return a + b + c

print(keyword_only(1, b=2))     # 6
print(keyword_only(1, b=2, c=9))# 12
# keyword_only(1, 2)            TypeError：b 必须用关键字
```

| 用途 | 说明 | 依据 |
| --- | --- | --- |
| 强制调用方写明参数名 | 避免位置参数含义不明 | `[F6]` |
| `*` 后面可以有默认值 | `*, c=3` 合法 | `[F6]` |
| `*args` 之后自动进入仅关键字区 | `def f(*args, sep=",")` | `[F6]` |

> 注意：当函数有多个布尔开关时，用 `*` 强制关键字传参能显著减少「参数写错位置」的 bug。`[F6]` `[F4]`

### 3.9 参数顺序规则（必背）

```python
def full(positional, /, normal, default=1, *args, keyword_only, kw_default=2, **kwargs):
    ...
```

**从左到右的固定顺序**：

| 顺序 | 部分 | 说明 |
| --- | --- | --- |
| 1 | 位置参数 | 只能按位置传 |
| 2 | `/` | 分隔符，前面是仅位置 |
| 3 | 普通参数 | 可位置可关键字 |
| 4 | 默认参数 | 必须在普通参数之后 |
| 5 | `*args` | 收集多余位置参数 |
| 6 | 仅关键字参数 | `*` 之后必须用名字传 |
| 7 | `**kwargs` | 收集多余关键字参数 |

**合法与非法对照**：

| 写法 | 是否合法 | 原因 | 依据 |
| --- | --- | --- | --- |
| `def f(a, b=1)` | ✅ | 默认在后 | `[F2]` |
| `def f(a=1, b)` | ❌ | 非默认参数跟在默认参数后 | `[F2]` |
| `def f(a, *args, b=1)` | ✅ | `b` 是仅关键字 | `[F6]` |
| `def f(a, *, b)` | ✅ | 仅关键字可无默认 | `[F6]` |
| `def f(*, a, b=1)` | ✅ | 全部仅关键字 | `[F6]` |
| `def f(a, /, b)` | ✅ | 3.8+ | `[F7]` |
| `def f(a, /, *args, b, **kwargs)` | ✅ | 完整形态 | `[F2]` |
| `def f(**kwargs, a)` | ❌ | `**kwargs` 必须最后 | `[F2]` |
| `def f(*args, *more)` | ❌ | 只能一个 `*` 收集 | `[F2]` |

> 注意：记不住就记一句——**「必需 → 默认 → `*args` → 仅关键字 → `**kwargs`」**。`[F2]`

### 3.10 参数传递语义（非常关键）

Python 传的是**对象引用**（call by object reference），不是值拷贝，也不是引用变量。`[F1]` `[F10]`

| 传入类型 | 函数内操作 | 外部是否受影响 |
| --- | --- | --- |
| 不可变（`int` / `str` / `tuple`） | 重新赋值 | 否 |
| 可变（`list` / `dict` / `set`） | 原地修改（`append` / `[]=`） | **是** |
| 可变 | 重新赋值（`x = [...]`） | 否（只改了局部名字） |

```python
items = [1]
def mutate(target):
    target.append(2)

mutate(items)
print(items)        # [1, 2]，外部被改（实测）

number = 1
def rebind(value):
    value = 99

rebind(number)
print(number)       # 1，不受影响（实测）
```

> 注意：说「Python 是值传递」或「引用传递」都不准确；准确说法是「传对象引用，函数内重新赋值不影响调用方，原地修改会影响」。`[F1]`

### 3.11 解包传参 `*` 与 `**`

```python
def build(name, *args, limit=2, **kwargs):
    return name, args, limit, kwargs

params = ["x", 1, 2]
print(build(*params, **{"limit": 7}))
# ('x', (1, 2), 7, {})（实测）
```

| 写法 | 含义 | 依据 |
| --- | --- | --- |
| `f(*seq)` | 把序列展开成位置参数 | `[F1]` |
| `f(**mapping)` | 把映射展开成关键字参数 | `[F1]` |
| 两者可混用 | `f(*a, **b)` | `[F1]` |

> 注意：`*` 解包要求 `seq` 是可迭代对象；`**` 解包要求键都是字符串且是合法参数名，否则 `TypeError`。`[F3]`

### 3.12 参数相关 `TypeError` 速查

| 报错信息关键词 | 原因 | 依据 |
| --- | --- | --- |
| `missing N required positional argument` | 少传必需参数 | `[F3]` |
| `takes 2 positional arguments but 3 were given` | 多传位置参数 | `[F3]` |
| `got an unexpected keyword argument` | 关键字名拼错/不存在 | `[F3]` |
| `multiple values for argument` | 同一参数位置和关键字各传一次 | `[F3]` |
| `positional argument follows keyword argument` | 关键字参数后又写位置参数（调用语法错误） | `[F2]` |

> 注意：读报错先看最后一行关键词，再回去数实参个数；这类错误 90% 是「多传/少传/拼错名」。`[F3]`

## 4. 返回值

### 4.1 `return` 的基本用法

```python
def add(a, b):
    return a + b

result = add(1, 2)
print(result)      # 3
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| `return` 结束函数 | 后面的语句不再执行 | `[F1]` |
| 可返回任意对象 | 数字、字符串、容器、函数、`None` | `[F1]` |
| 一个函数可有多个 `return` | 走哪条取决于分支 | `[F1]` |

```python
def classify(score):
    if score >= 90:
        return "A"
    if score >= 60:
        return "B"
    return "C"          # 兜底，不再写 else

print(classify(95), classify(70), classify(10))
```

> 注意：「早返回」比层层 `else` 更易读：先处理异常/边界，再写主逻辑。`[F4]`

### 4.2 没有 `return` / 只有 `return`

```python
def no_return():
    pass

def only_return():
    return

print(no_return())            # None
print(only_return())          # None
print(type(no_return()).__name__)   # NoneType（实测）
```

| 情况 | 返回值 | 依据 |
| --- | --- | --- |
| 没有 `return` | `None` | `[F1]` |
| `return`（无表达式） | `None` | `[F1]` |
| `return None` | `None` | `[F1]` |

> 注意：「没有返回值」在 Python 里就是返回 `None`；调用方不要假设「没写 return 就没有结果」，一律按 `None` 处理。`[F1]`

### 4.3 多返回值

```python
def min_max(numbers):
    return min(numbers), max(numbers)

low, high = min_max([3, 1, 5])
print(low, high)              # 1 5

pair = min_max([3, 1, 5])
print(pair, type(pair).__name__)   # (1, 5) tuple（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 本质是返回 tuple | 不是「多返回值」语法 | `[F1]` |
| 可用解包接收 | `a, b = f()` | `[F1]` |
| 也可整体接收 | `pair = f()`，再 `pair[0]` | `[F1]` |
| 数量必须匹配 | 解包数量不对会 `ValueError` | `[F1]` |

> 注意：返回超过 3 个值时，用 `dict` 或 `namedtuple`（第 22 章）比长 tuple 更可读；`return a, b, c, d` 的调用方很容易记错顺序。`[F4]`

### 4.4 返回可变对象的风险

```python
SHARED = []

def get_shared():
    return SHARED

result = get_shared()
result.append(1)
print(get_shared())   # [1]，调用方改到了「内部状态」
```

| 风险 | 说明 | 依据 |
| --- | --- | --- |
| 返回内部可变对象 | 调用方可绕过封装修改 | `[F10]` |
| 返回默认值对象 | 同上 | `[F1]` |
| 应返回副本 | `return list(SHARED)` | `[F10]` |

> 注意：函数返回「缓存/配置/全局列表」时，要么返回副本，要么明确文档写「不要修改」。`[F4]`

### 4.5 返回值可以与表达式组合

```python
def double(x):
    return x * 2

print(double(double(3)))        # 12，链式调用
print(sum([double(1), double(2)]))   # 6
```

> 注意：链式调用提高表达力，但嵌套过深会难读；超过两层就拆成中间变量。`[F4]`

## 5. 文档字符串（Docstring）

### 5.1 三种常见写法

```python
def build_report(tool_name, results, limit=3):
    """返回工具结果摘要；limit 控制保留条数。"""
    selected = results[:limit]
    return {"tool": tool_name, "count": len(selected), "items": selected}


def fetch_news(query, limit=5):
    """抓取新闻标题。

    Args:
        query: 搜索关键词。
        limit: 最多返回条数。

    Returns:
        标题字符串列表。

    Raises:
        ValueError: limit 非正数时。
    """
    if limit <= 0:
        raise ValueError("limit 必须为正数")
    return [f"{query}-{index}" for index in range(limit)]
```

| 风格 | 特点 | 依据 |
| --- | --- | --- |
| 单行摘要 | 一句话说清「做什么」 | `[F5]` |
| 摘要 + 空行 + 详细 | PEP 257 推荐的多行结构 | `[F5]` |
| Google / NumPy / reST 风格 | `Args` / `Returns` / `Raises` 分节，工具可解析 | `[F5]` |

### 5.2 `__doc__` 与 `help()`

```python
def documented(tool):
    """返回工具名。"""
    return tool

print(documented.__doc__)      # 返回工具名。（实测）
print(documented.__name__)     # documented
help(documented)               # 在 REPL 里打印完整帮助
```

| 访问方式 | 得到 | 依据 |
| --- | --- | --- |
| `f.__doc__` | 字符串或 `None` | `[F10]` |
| `help(f)` | 格式化后的帮助 | `[F9]` |
| IDE 悬浮提示 | 读的就是 `__doc__` | `[F5]` |

> 注意：没有 docstring 时 `f.__doc__` 是 `None`，不是空字符串；写 `if f.__doc__:` 可以判断「有没有文档」。`[F10]`

### 5.3 内容规范

| 该写 | 不该写 | 依据 |
| --- | --- | --- |
| 做什么、返回什么 | 「这是个函数」 | `[F5]` |
| 参数含义与约束 | 实现细节逐步解说 | `[F5]` |
| 可能抛出的异常 | 版本变更史（放 CHANGELOG） | `[F5]` |
| 副作用（写文件、改全局） | 与代码重复的字面翻译 | `[F4]` |

> 注意：docstring 是「给调用方的契约」，注释是「给维护者的解释」；两者不要互相替代。`[F5]` `[F4]`

### 5.4 与注释的区别

| 项 | docstring | 注释 `#` |
| --- | --- | --- |
| 位置 | 函数/类/模块第一条语句 | 任意位置 |
| 类型 | 字符串对象，运行时可读 | 被解释器忽略 |
| 用途 | 对外契约 | 对内解释「为什么」 |
| 工具支持 | `help()`、IDE、文档生成 | 无 | 

> 注意：把 `#` 注释写成 docstring 不会报错，但 `help()` 读不到；把 docstring 当注释随意写也不会报错，但会污染对外文档。`[F5]`

## 6. 函数进阶（本章范围内）

### 6.1 函数注解（第 20 章预告）

```python
def build_report(tool_name: str, results: list, limit: int = 3) -> dict:
    """带注解的版本；注解在运行时不做校验。"""
    return {"tool": tool_name, "count": len(results[:limit])}

print(build_report.__annotations__)
# {'tool_name': <class 'str'>, 'results': <class 'list'>, 'limit': <class 'int'>, 'return': <class 'dict'>}
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 注解是表达式 | 求值后存进 `__annotations__` | `[F8]` |
| 运行时不校验 | `build_report(123, "abc")` 照样跑 | `[F8]` |
| 由静态检查器/框架使用 | mypy、FastAPI 等读取 | `[F8]` |
| 完整规则在第 20 章 | 本章只需知道「可以写」 | 课程边界 |

> 注意：注解不是类型强制；`limit: int` 传 `"3"` 不会报错，只会在后面 `slice` 时报 `TypeError`。`[F8]`

### 6.2 递归

```python
def factorial(n):
    """阶乘：n! = n * (n-1)!，n<=1 时为 1。"""
    return 1 if n <= 1 else n * factorial(n - 1)

print(factorial(5))    # 120（实测）
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 必须有终止条件 | 否则无限递归，最终 `RecursionError` | `[F1]` |
| 每次向终止条件靠近 | `n - 1` | `[F1]` |
| 递归深度有上限 | 超过抛 `RecursionError`；CPython 可用 `sys.getrecursionlimit()` 查看（第 22 章） | `[F1]` |
| 递归不总是更优 | 能用循环就用循环，递归适合树/分治结构 | `[F4]` |

```python
def fib(n):
    """朴素递归，时间复杂度指数级，只为演示。"""
    return n if n < 2 else fib(n - 1) + fib(n - 2)

print(fib(10))    # 55
```

> 注意：`fib` 这种写法 `n=40` 就会明显卡；教学示例可以，生产代码要用循环或缓存（`functools.lru_cache`，第 22 章）。`[F4]`

### 6.3 函数作为参数与返回值（高阶函数预告）

```python
def apply_twice(func, value):
    """把函数应用两次。"""
    return func(func(value))

print(apply_twice(lambda x: x + 1, 0))   # 2
```

```python
def make_multiplier(factor):
    """返回一个把参数乘以 factor 的函数。"""
    def multiply(value):
        return value * factor
    return multiply

double = make_multiplier(2)
print(double(5))     # 10
```

| 能力 | 说明 | 依据 |
| --- | --- | --- |
| 函数作参数 | 把「行为」传进去 | `[F1]` |
| 函数作返回值 | 生成专用函数 | `[F1]` |
| 引用外层变量 | 形成闭包，第 06 章详讲 | `[F2]` |
| 简写形式 | `lambda`，第 07 章 | `[F1]` |

> 注意：`make_multiplier` 里的 `factor` 在函数返回后仍然存活——这是闭包；第 06 章会解释它存在哪个作用域里。`[F2]`

### 6.4 局部函数

```python
def process(records):
    """把重复的小步骤收进局部函数。"""
    def normalize(name):
        return name.strip().lower()

    return [normalize(name) for name in records]

print(process(["  Search ", "CACHE"]))   # ['search', 'cache']
```

| 场景 | 是否推荐 | 依据 |
| --- | --- | --- |
| 只给当前函数用的小工具 | ✅ 推荐，避免污染模块命名空间 | `[F4]` |
| 需要被别处复用 | ❌ 提到模块级 | `[F4]` |
| 需要测试 | ❌ 局部函数难直接测试 | `[F4]` |

> 注意：局部函数每次外层调用都会重新创建，适合「依赖外层参数的小逻辑」；没有依赖时提到模块级更清晰。`[F4]`

### 6.5 函数常用属性

| 属性 | 含义 | 依据 |
| --- | --- | --- |
| `__name__` | 函数名 | `[F10]` |
| `__qualname__` | 限定名（嵌套时含外层） | `[F10]` |
| `__doc__` | docstring 或 `None` | `[F10]` |
| `__defaults__` | 默认参数元组或 `None` | `[F10]` |
| `__annotations__` | 注解字典 | `[F10]` |
| `__module__` | 定义所在模块名 | `[F10]` |

```python
def documented(tool):
    """返回工具名。"""
    return tool

print(documented.__name__, documented.__doc__, documented.__defaults__)
# documented 返回工具名。 None（实测）
```

> 注意：装饰器如果不处理这些属性，包装后的函数会「改名」——这正是第 13 章要 `functools.wraps` 的原因。`[F10]`

## 7. 综合示例：用函数重构统计逻辑

对比第 04 章：同样的 `counts[name] = counts.get(name, 0) + 1` 如果要按状态再统计一次，就得复制一遍。用函数装起来：

```python
"""第 05 章综合示例：用函数封装统计与格式化。"""


def summarize(records):
    """统计每个工具出现的次数。"""
    counts = {}
    for name, status in records:
        counts[name] = counts.get(name, 0) + 1
    return counts


def format_line(name, count):
    """格式化单行统计。"""
    return f"{name}: {count} 次"


records = [
    ("search", "ok"),
    ("cache", "ok"),
    ("search", "fail"),
    ("translate", "ok"),
    ("search", "ok"),
]

counts = summarize(records)
print(f"工具数: {len(counts)}")
for name in sorted(counts):
    print(format_line(name, counts[name]))
```

本机实测输出：

```text
工具数: 3
cache: 1 次
search: 3 次
translate: 1 次
```

**逐段说明**：

| 代码 | 用到的语法 | 依据 |
| --- | --- | --- |
| `def summarize(records):` | 定义函数、单参数 | `[F1]` |
| `for name, status in records` | 元组解包（第 04 章） | `[F1]` |
| `return counts` | 返回可变对象 | `[F1]` |
| `def format_line(name, count):` | 两个位置参数 | `[F1]` |
| `f"{name}: {count} 次"` | f-string（第 03 章） | `[F1]` |
| `sorted(counts)` | 排序字典键（第 04 章） | `[F1]` |

> 注意：`summarize` 返回的是内部新建的 `counts`，调用方拿到后可以随意修改，不会影响下一次调用——因为它每次调用都新建，这一点和可变默认值完全不同。`[F1]` `[F4]`

**为什么这样重构**：

| 重构前 | 重构后 |
| --- | --- |
| 统计逻辑写死在主流程 | `summarize` 可单独测试 |
| 输出格式散落 | `format_line` 一处修改全局生效 |
| 想按状态统计要复制代码 | 传不同的 `records` 即可 |

## 8. 注意事项与新手错误对照表

| 错误写法 / 操作 | 报错或现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 调用未定义的函数 | `NameError` | 先 `def` 再调用 | `[F1]` |
| 少传必需参数 | `TypeError` | 补齐或给默认值 | `[F3]` |
| 多传位置参数 | `TypeError` | 对齐参数个数 | `[F3]` |
| 关键字名拼错 | `TypeError: unexpected keyword` | 对照形参名 | `[F3]` |
| 位置和关键字各传一次 | `TypeError: multiple values` | 只传一次 | `[F3]` |
| `def f(a=1, b)` | `SyntaxError` | 默认参数放后面 | `[F2]` |
| `def f(**kw, a)` | `SyntaxError` | `**kwargs` 必须最后 | `[F2]` |
| `def f(*a, *b)` | `SyntaxError` | 只能一个 `*args` | `[F2]` |
| 默认参数写 `[]` / `{}` | 跨调用累积共享 | 用 `None` 哨兵 | `[F1]` `[F4]` |
| 默认参数写函数调用 | 只在定义时算一次 | 函数内计算 | `[F1]` |
| 以为 `*args` 是 list | 实际是 `tuple` | 要改先 `list(args)` | `[F1]` |
| `args.append(...)` | `AttributeError` | `list(args).append(...)` | `[F1]` |
| 以为 `**kwargs` 是 list | 实际是 `dict` | 按字典用 | `[F1]` |
| 参数名与内置名冲突 | 静默覆盖 `len` / `list` | 换名字 | `[F4]` |
| 函数内改全局未声明 | 只改局部，全局不变 | 用 `global`（第 06 章） | `[F1]` |
| 函数内先读后写同名全局 | `UnboundLocalError` | 先声明 `global` | `[F1]` |
| 修改可变参数影响外部 | 无意副作用 | 传副本或文档说明 | `[F10]` |
| 以为不可变参数被改 | 实际没变 | 用返回值接收 | `[F1]` |
| 多返回值解包数量不对 | `ValueError` | 数量对齐或用 `*` | `[F1]` |
| 把多返回值当 list | 实际是 `tuple` | 需要 list 就 `list(...)` | `[F1]` |
| 无 `return` 却使用返回值 | 得到 `None` | 显式 `return` | `[F1]` |
| `return` 后继续写代码 | 不会执行 | 删掉死代码 | `[F1]` |
| 函数名与变量重名 | 后者覆盖前者 | 分开命名 | `[F1]` |
| 重复定义同名函数 | 后者生效 | 改名或合并 | `[F1]` |
| 递归没有终止条件 | `RecursionError` | 加基准情形 | `[F1]` |
| 递归太深 | `RecursionError` | 改循环 | `[F1]` |
| docstring 写成 `#` 注释 | `__doc__` 为 `None` | 函数体第一行写字符串 | `[F5]` |
| `pass` 占位忘记实现 | 调用方拿到 `None` | 加 TODO 或直接抛 `NotImplementedError` | `[F4]` |
| 用 `print` 代替 `return` | 调用方拿不到值 | 返回数据，由调用方打印 | `[F4]` |
| 函数过长（>50 行） | 难读难测 | 拆成小函数 | `[F4]` |
| 参数过多（>5） | 调用易错 | 用配置对象或 `**kwargs` | `[F4]` |
| 隐藏副作用 | 名字看不出来 | 命名体现（`save_` / `update_`） | `[F4]` |
| 返回内部可变对象 | 调用方可破坏内部状态 | 返回副本 | `[F10]` |
| 用 `is` 比较返回值 | 结果不可靠 | 用 `==` | `[F3]` |
| `print(function)` | 只看到内存地址 | 打印 `function()` 的结果 | `[F1]` |

## 9. 最佳实践与编码建议

**设计层面**：

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 单一职责 | 一个函数只做一件事，名字能说清 | `[F4]` |
| 参数控制在 5 个以内 | 超过就考虑配置对象 | `[F4]` |
| 默认参数用 `None` 哨兵 | 避免可变默认值共享 | `[F1]` |
| 布尔开关用 `*` 强制关键字 | `def run(task, *, dry_run=False)` | `[F6]` |
| 早返回减少嵌套 | 先处理边界与错误 | `[F4]` |
| 返回类型保持一致 | 要么总有返回值，要么总没有 | `[F4]` |
| 纯函数优先 | 同样输入同样输出、无副作用 | `[F4]` |
| 副作用写进名字 | `save_report` / `fetch_news` | `[F4]` |

**风格层面** `[F4]`：

- 函数名用 `snake_case`，动词开头：`build_` / `get_` / `is_` / `has_`。
- 参数名表达含义，不要 `a` / `b` / `data`（除非确实是通用工具）。
- 冒号后一个空格，逗号后一个空格：`def f(a, b=1):`。
- 空行：模块级函数之间 2 个空行，类内方法之间 1 个。
- 函数体不要超过一屏（约 30–50 行）。

**文档与测试**：

- 每个公开函数写 docstring：做什么、参数、返回、异常。`[F5]`
- 复杂分支写注释解释「为什么」，不写「是什么」。`[F4]`
- 给函数写最小测试：正常值、边界值、非法值。`[F4]`

**安全边界**：

- 不要把用户输入直接 `eval` 或拼进表达式。
- 对外接口用 `**kwargs` 时要显式校验白名单，否则拼错的参数会被静默吞掉。
- 返回敏感数据前先脱敏（延续第 01 章安全底线）。

## 10. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[F1]` | python.org | https://docs.python.org/3.12/tutorial/controlflow.html | `def` 定义、默认参数、关键字参数、`*args`/`**kwargs`、解包传参、docstring、递归示例、`lambda` 入口 |
| `[F2]` | python.org | https://docs.python.org/3.12/reference/compound_stmts.html | 函数定义语法、参数顺序、`/` 与 `*` 的语法位置、`def` 的完整规则 |
| `[F3]` | python.org | https://docs.python.org/3.12/reference/expressions.html | 调用语义、参数绑定、`TypeError` 触发条件、`*`/`**` 解包调用 |
| `[F4]` | PEP 官方 | https://peps.python.org/pep-0008/ | 函数命名、参数命名、默认参数建议、空行与空格、避免可变默认参数 |
| `[F5]` | PEP 官方 | https://peps.python.org/pep-0257/ | docstring 约定、单行/多行结构、摘要行规则 |
| `[F6]` | PEP 官方 | https://peps.python.org/pep-3102/ | 仅关键字参数 `*` |
| `[F7]` | PEP 官方 | https://peps.python.org/pep-0570/ | 仅位置参数 `/`（3.8+） |
| `[F8]` | PEP 官方 | https://peps.python.org/pep-3107/ | 函数注解、`__annotations__`、运行时不校验 |
| `[F9]` | python.org | https://docs.python.org/3.12/library/functions.html#help | `help()` 读取 docstring |
| `[F10]` | python.org | https://docs.python.org/3.12/reference/datamodel.html | 函数对象、`__name__`/`__doc__`/`__defaults__`/`__annotations__`、调用与绑定 |
| `[F11]` | GitHub 官方 | https://github.com/python/cpython/blob/main/Doc/tutorial/controlflow.rst | 官方教程源文件（`[F1]` 页脚 Show Source 指向） |
| `[F12]` | PEP 官方 | https://peps.python.org/pep-0020/ | The Zen of Python（显式、简单、可读） |

> **核对状态**：`[F1]` `[F4]` `[F11]` 与本章 `README.md` 已核对来源一致；其余链接按 `docs.python.org/3.12` 与 `peps.python.org` 官方结构整理，**本次未逐页直连复核**。文中「实测」结论均为本机 Python 3.12.8 运行结果。

## 11. 毕业自查清单

**能说清（概念层）**：

- [ ] 定义函数时函数体为什么不执行，什么时候才执行
- [ ] 五种参数形态各自解决什么问题
- [ ] 参数顺序规则（必需 → 默认 → `*args` → 仅关键字 → `**kwargs`）
- [ ] 默认参数为什么只在定义时求值一次，可变默认值为什么会累积
- [ ] Python 的参数传递语义（对象引用；重新赋值 vs 原地修改）
- [ ] 没有 `return` 与 `return` 无值的区别（都是 `None`）
- [ ] 多返回值本质是 tuple
- [ ] docstring 与注释的区别，`__doc__` 什么时候是 `None`
- [ ] `/` 与 `*` 分别限制什么

**能写出（代码层）**：

- [ ] 带位置参数、默认参数、关键字调用的函数
- [ ] 用 `*args` 收集任意位置参数并遍历
- [ ] 用 `**kwargs` 收集任意关键字参数并按字典处理
- [ ] 用 `*` 强制关键字的函数，并说明为什么
- [ ] 用 `*` / `**` 解包调用函数
- [ ] 用 `None` 哨兵规避可变默认值
- [ ] 返回多个值并正确解包
- [ ] 写符合 PEP 257 的 docstring
- [ ] 写一个带终止条件的递归函数

**能判断（避坑层）**：

- [ ] 看到 `def f(a=1, b)` 能立刻指出 `SyntaxError`
- [ ] 看到 `def f(bucket=[])` 能指出跨调用共享
- [ ] 看到 `args.append(...)` 能指出 `AttributeError`
- [ ] 看到 `def f(**kwargs)` 的公共 API 能指出「拼错参数名会被吞」
- [ ] 看到函数内 `print` 当结果能指出调用方拿不到值
- [ ] 看到 `return` 后还有代码能指出死代码
- [ ] 看到 5 个以上参数能提出用配置对象

**能跑通（验收层）**：

- [ ] 运行 `examples/function_demo.py` 并解释两次 `append_result` 输出
- [ ] 把第 7 节示例存成文件运行，输出与文档一致
- [ ] 在 REPL 验证「可变默认值累积」与「`None` 哨兵不累积」
- [ ] 手写一个 `def summarize(records, status=None, *, limit=None)`，同时支持按状态过滤与限条数

## 12. 下一章衔接

第 06 章 `作用域`：本章留下了三个必须回答的问题——

1. 为什么函数里改 `global` 变量必须写 `global`，不写就变成局部变量？
2. 为什么 `make_multiplier` 返回后，`factor` 还能被内层函数读到？它存在哪？
3. 为什么「函数内先 `print(x)` 再 `x = 1`」会抛 `UnboundLocalError`，而不是正常打印？

这三个问题分别对应 LEGB、闭包 `nonlocal`、编译期变量分类。第 06 章会把它们一次讲透，本章的 `global` 反例和默认参数陷阱也会在那里得到完整解释。
