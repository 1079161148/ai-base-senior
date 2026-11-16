# 17 迭代器与生成器 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把截图里的「迭代器、可迭代对象、倒数对象、消费者、`range`、推导式、生成器、`itertools`」逐条展开，并补上 `send`、`throw`、PEP 479、旧式迭代协议等必然遇到的内容，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测） |
| 前置 | 第 04、14、16 章（容器、特殊方法、异常） |
| 覆盖范围 | iterable / iterator 协议、自定义迭代器、七类消费者、`range`、四种推导式、生成器函数与表达式、`yield from`、`send`/`throw`/`close`、`itertools` 常用工具 |
| 明确不覆盖 | 异步迭代器（27）、协程与 `asyncio`（26）、`collections.abc` 全量（19） |
| 学完验收 | 能说清 iterable 与 iterator 的区别、能手写迭代器与生成器、能谓出「为什么生成器只能消费一次」（见第 13 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[In]` `` 指向第 12 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果。

**推荐顺序**：

```text
1 迭代协议（第 1 节）      → iterable vs iterator
2 自定义迭代器（第 2 节）  → 倒数对象 + 无限序列
3 可迭代对象（第 3 节）    → 谁算 iterable
4 消费者（第 4 节）        → 七种消费方式
5 range（第 5 节）         → 为什么不占内存
6 推导式（第 6 节）        → 四种 + 嵌套顺序
7 生成器（第 7 节）        → yield / send / yield from
8 itertools（第 8 节）     → 不造轮子
9 综合示例（第 9 节）
10 注意事项（第 10 节）    → 40 条错误对照
```

**与 README 的分工**：README 给结论，本文件负责协议细节与坑。冲突时以本文件为准。

## 1. 迭代协议：iterable 与 iterator

### 1.1 两个概念

| 概念 | 定义 | 例子 | 依据 |
| --- | --- | --- | --- |
| iterable（可迭代对象） | 能传给 `iter()` 得到 iterator | `list`、`str`、`dict`、`range`、生成器 | `[I1]` |
| iterator（迭代器） | 实现 `__next__()`，耗尽抛 `StopIteration` | `iter([1,2])` 的返回值 | `[I2]` |

```python
numbers = [1, 2, 3]
iterator = iter(numbers)

print(type(iterator).__name__)              # list_iterator（实测）
print(isinstance(numbers, Iterable))        # True（实测）
print(isinstance(numbers, Iterator))        # False（实测）
print(isinstance(iterator, Iterator))       # True（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| list 是 iterable 不是 iterator | 每次 `iter()` 给新迭代器 | `[I2]` |
| iterator 一定是 iterable | 实现 `__iter__` 返回自身 | `[I2]` |
| iterable 不一定是 iterator | 只承诺「能产出迭代器」 | `[I2]` |

### 1.2 `iter()` 与 `next()`

```python
iterator = iter([1, 2, 3])
print(next(iterator), next(iterator), next(iterator))   # 1 2 3（实测）
try:
    next(iterator)
except StopIteration:
    print("STOP", True)                                  # STOP True（实测）
```

| 调用 | 行为 | 依据 |
| --- | --- | --- |
| `iter(obj)` | 返回迭代器 | `[I1]` |
| `next(it)` | 取下一个，耗尽抛 `StopIteration` | `[I1]` |
| `next(it, default)` | 耗尽返回默认值 | `[I1]` |
| `iter(callable, sentinel)` | 反复调用直到等于哨兵 | `[I1]` |

```python
# 读到文件结束
with open("data.txt", encoding="utf-8") as handle:
    for line in iter(handle.readline, ""):
        print(line.rstrip())
```

### 1.3 `for` 循环就是 `next()` 循环

```python
for item in [1, 2, 3]:
    print(item)
```

等价于：

```python
iterator = iter([1, 2, 3])
while True:
    try:
        item = next(iterator)
    except StopIteration:
        break
    print(item)
```

| 步骤 | 说明 | 依据 |
| --- | --- | --- |
| 1 | 对可迭代对象调 `iter()` | `[I1]` |
| 2 | 反复 `next()` | `[I1]` |
| 3 | 捕 `StopIteration` 退出 | `[I1]` |
| 4 | `break` / `return` 都会停止，但**不会**自动 `close()` 生成器 | `[I1]` |

### 1.4 迭代器必须返回 `self`

```python
class Broken:
    def __init__(self, items):
        self.items = items

    def __iter__(self):
        return iter(self.items)      # 返回别的迭代器

    def __next__(self):
        return self.items.pop()      # 永远用不到
```

| 写法 | 结果 | 依据 |
| --- | --- | --- |
| `__iter__` 返回 `self` | ✅ 标准迭代器 | `[I2]` |
| `__iter__` 返回新迭代器 | 也能 `for`，但 `next(obj)` 失效 | `[I2]` |
| 只有 `__next__` 没有 `__iter__` | 不是 iterable | `[I2]` |

### 1.5 一次性：迭代器会被耗尽

```python
single = iter([1, 2, 3])
print("EXHAUST", list(single), list(single))   # [1, 2, 3] []（实测）
```

| 对象 | 能否重复遍历 | 依据 |
| --- | --- | --- |
| list / tuple / dict / set | ✅ 每次 `iter()` 新建 | `[I2]` |
| 迭代器 | ❌ 耗尽即空 | `[I2]` |
| 生成器 | ❌ 同迭代器 | `[I1]` |
| 文件对象 | ❌ 指针到末尾 | `[I1]` |

> 注意：这是「流」模型的本质——迭代器只承诺「向前」，不承诺「回到开头」。需要重读时重新构造或先 `list()`。`[I2]`

### 1.6 `isinstance` 判定的坑

```python
class Legacy:
    def __init__(self, items):
        self.items = items

    def __getitem__(self, index):
        return self.items[index]

legacy = Legacy([10, 20])
print([item for item in legacy])              # [10, 20]（实测）
print(isinstance(legacy, Iterable))           # False（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 旧式 `__getitem__` 能迭代 | 解释器按索引一直取到 `IndexError` | `[I1]` |
| 但它不是 `Iterable` 实例 | 没有 `__iter__` | `[I2]` |
| 判定「能不能迭代」 | 用 `iter()` 试，别用 `isinstance` | `[I2]` |

> 注意：`isinstance(x, Iterable)` 只认 `__iter__`（或注册的虚拟子类），不认旧式 `__getitem__`；这也是 `collections.abc` 判定与实际行为不完全一致的地方。`[I2]`

## 2. 自定义迭代器

### 2.1 倒数对象（截图示例）

```python
class Countdown:
    def __init__(self, start):
        self.current = start

    def __iter__(self):
        return self

    def __next__(self):
        if self.current <= 0:
            raise StopIteration
        value = self.current
        self.current -= 1
        return value

print(list(Countdown(3)))     # [3, 2, 1]（实测）
```

| 要素 | 说明 | 依据 |
| --- | --- | --- |
| `__init__` 存状态 | 当前值 | `[I1]` |
| `__iter__` 返回 `self` | 自己是迭代器 | `[I2]` |
| `__next__` 推进状态 | 返回当前并递减 | `[I2]` |
| 耗尽抛 `StopIteration` | 不是 `return None` | `[I2]` |

### 2.2 应用：无限序列

```python
def naturals():
    number = 0
    while True:
        yield number
        number += 1

print(list(islice(naturals(), 5)))    # [0, 1, 2, 3, 4]（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 无限迭代器本身合法 | 由消费者决定取多少 | `[I1]` |
| 必须配合 `islice` / `takewhile` / `break` | 否则 `list()` 会耗尽内存 | `[I1]` |
| 惰性 = 只在需要时算 | 第 7 节 | `[I1]` |

### 2.3 状态与重置

```python
print(list(Countdown(2)), list(Countdown(2)))   # [2, 1] [2, 1]（实测）
```

| 写法 | 结果 | 依据 |
| --- | --- | --- |
| 每次新建实例 | ✅ 各自独立 | `[I1]` |
| 复用同一实例 | 第二次为空 | `[I2]` |
| 想复用 | 在 `__iter__` 里重置状态（非标准） | `[I2]` |

> 注意：`__iter__` 返回 `self` 的迭代器天然「一次性」；如果需要「可重复遍历的容器」，应该实现 `__iter__` 返回新的迭代器对象，而不是 `self`。`[I2]`

### 2.4 手写迭代器 vs 生成器

| 维度 | 迭代器类 | 生成器函数 |
| --- | --- | --- |
| 代码量 | 多（三个方法） | 少（一个 `yield`） |
| 状态管理 | 手动维护属性 | 自动保存局部变量 |
| 可读性 | 显式但啰嗦 | 接近普通函数 |
| 复用 | 可实现复杂协议 | 一次性 |
| 依据 | `[I2]` | `[I3]` |

```python
# 等价的两个版本
class CountdownClass:
    def __init__(self, start):
        self.current = start

    def __iter__(self):
        return self

    def __next__(self):
        if self.current <= 0:
            raise StopIteration
        self.current -= 1
        return self.current + 1


def countdown(start):
    while start > 0:
        yield start
        start -= 1
```

> 注意：除了需要实现 `__iter__` 之外的额外协议（如 `send`、`throw`、自定义属性），优先写生成器；手写迭代器的场景已经很少。`[I3]`

## 3. 可迭代对象（Iterable）

### 3.1 常见可迭代对象

| 类型 | 产出 | 依据 |
| --- | --- | --- |
| `list` / `tuple` | 元素 | `[I2]` |
| `str` | 字符 | `[I2]` |
| `dict` | 键 | `[I2]` |
| `set` / `frozenset` | 元素（无序） | `[I2]` |
| `range` | 整数序列 | `[I2]` |
| `file` | 行 | `[I1]` |
| 生成器 | `yield` 的值 | `[I1]` |
| `map` / `filter` / `zip` | 计算结果 | `[I2]` |
| `dict.keys()` / `.values()` / `.items()` | 视图 | `[I2]` |

```python
print(list({"a": 1, "b": 2}))                    # ['a', 'b']
print(list({"a": 1, "b": 2}.values()))           # [1, 2]
print(list({"a": 1, "b": 2}.items()))            # [('a', 1), ('b', 2)]
```

### 3.2 dict 视图是 iterable 但不是 iterator

```python
print(type(iter({"a": 1})).__name__)                 # dict_keyiterator（实测）
print(list({"a": 1}.keys()))                         # ['a']（实测）
print(isinstance({"a": 1}.keys(), Iterable))         # True（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 视图可迭代多次 | 每次 `iter()` 新建 | `[I2]` |
| 视图不是快照 | 底层 dict 变化可见 | `[I2]` |
| 遍历时改 dict | `RuntimeError: dictionary changed size` | `[I2]` |

### 3.3 遍历时修改容器

| 场景 | 结果 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| 遍历 list 时 `append` | 可能无限循环 | 先复制 / 收集后再改 | `[I1]` |
| 遍历 list 时 `remove` | 跳过元素 | 用推导式重建 | `[I1]` |
| 遍历 dict 时增删 | `RuntimeError` | 遍历 `list(d)` 副本 | `[I2]` |

```python
# 反例
for name in names:
    if not name:
        names.remove(name)

# 正例
names = [name for name in names if name]
```

## 4. 消费者

### 4.1 七类消费者

```python
source = [1, 2, 3, 4]

print(sum(source), max(source), min(source))                              # 10 4 1（实测）
print(any(item > 3 for item in source), all(item > 0 for item in source)) # True True（实测）
print(list(zip("ab", source)))                                            # [('a', 1), ('b', 2)]（实测）
print(list(map(lambda item: item * 2, source)))                           # [2, 4, 6, 8]（实测）
print(list(filter(lambda item: item % 2 == 0, source)))                   # [2, 4]（实测）
print([*source], sorted({*source}))                                       # [1, 2, 3, 4] [1, 2, 3, 4]（实测）
print(3 in source)                                                        # True（实测）
```

| 消费者 | 行为 | 是否短路 | 依据 |
| --- | --- | --- | --- |
| `for` | 逐个处理 | 可 `break` | `[I1]` |
| `list()` / `tuple()` / `set()` | 全部收集 | 否 | `[I2]` |
| `*` 解包 | 全部展开 | 否 | `[I2]` |
| `in` | 找到即停 | ✅ | `[I1]` |
| `sum` / `max` / `min` | 全部遍历 | 否 | `[I2]` |
| `any` / `all` | 找到决定性结果即停 | ✅ | `[I2]` |
| `zip` / `map` / `filter` | 惰性，按需取 | 由下游决定 | `[I2]` |
| `sorted` | 全部读取 | 否 | `[I2]` |

> 注意：`len()` **不消费**可迭代对象，但它只对 `Sized` 有效；对生成器调 `len()` 直接 `TypeError`。`[I2]`

### 4.2 短路的价值

```python
def is_ok(value):
    print("检查", value)
    return value > 0

print(any(is_ok(item) for item in [1, 2, 3]))   # 只打印「检查 1」
print(all(is_ok(item) for item in [-1, 2]))     # 只打印「检查 -1」
```

| 函数 | 短路条件 | 依据 |
| --- | --- | --- |
| `any` | 遇到真值停止 | `[I2]` |
| `all` | 遇到假值停止 | `[I2]` |
| `in` | 找到即止 | `[I1]` |
| `next` | 取一个就停 | `[I1]` |
| `islice` | 取够就停 | `[I7]` |

### 4.3 `zip` / `map` / `filter` 是惰性的

```python
pairs = zip([1, 2, 3], "ab")
print(list(pairs))     # [(1, 'a'), (2, 'b')]，第三个被丢弃
```

| 函数 | 长度规则 | 依据 |
| --- | --- | --- |
| `zip` | 取最短 | `[I2]` |
| `zip(strict=True)` | 长度不等抛 `ValueError`（3.10+） | `[I2]` |
| `map` | 与最短输入一致 | `[I2]` |
| `filter` | 只保留为真的 | `[I2]` |

### 4.4 `enumerate` 与下标

```python
for index, name in enumerate(["a", "b"], start=1):
    print(index, name)     # 1 a / 2 b
```

| 写法 | 评价 | 依据 |
| --- | --- | --- |
| `enumerate(items, start=1)` | ✅ 推荐 | `[I4]` |
| `range(len(items))` + 下标 | ❌ 啰嗦 | `[I4]` |
| 手动计数器 | ❌ 容易漏 | `[I4]` |

### 4.5 消费者选择表

| 目标 | 用 | 依据 |
| --- | --- | --- |
| 全部收集成 list | `list(it)` | `[I2]` |
| 判断是否存在 | `any(...)` | `[I2]` |
| 判断全部满足 | `all(...)` | `[I2]` |
| 取第一个 | `next(it, default)` | `[I1]` |
| 取前 N 个 | `islice(it, n)` | `[I7]` |
| 边处理边输出 | `for` + 生成器 | `[I1]` |
| 求和/最值 | `sum` / `max` / `min` | `[I2]` |
| 排序 | `sorted(it)` | `[I2]` |

## 5. `range`

### 5.1 它不造列表

```python
span = range(1, 10, 2)
print(len(span), span[0], span[-1], 5 in span)      # 5 1 9 True（实测）
print(list(span[1:3]))                              # [3, 5]（实测）
print(isinstance(span, Iterator), isinstance(span, Iterable))   # False True（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `range` 是 iterable 不是 iterator | 可重复遍历 | `[I2]` |
| 内存 O(1) | 只存起止步长 | `[I4]` |
| 支持索引/切片/`in` | 惰性计算 | `[I2]` |
| `len(range)` 是 O(1) | 不遍历 | `[I2]` |

### 5.2 `range` vs `list` vs 生成器

| 维度 | `range(10**8)` | `list(range(10**8))` | `(x for x in ...)` |
| --- | --- | --- | --- |
| 内存 | 极小 | 数 GB | 极小 |
| 可重复遍历 | ✅ | ✅ | ❌ |
| 可索引 | ✅ | ✅ | ❌ |
| 可 `len` | ✅ | ✅ | ❌ |
| 依据 | `[I2]` | `[I4]` | `[I1]` |

```python
total = sum(range(1_000_001))    # 不占内存
```

### 5.3 常见误用

| 误用 | 问题 | 依据 |
| --- | --- | --- |
| `for i in range(len(items))` | 用 `enumerate` 更清晰 | `[I4]` |
| `list(range(...))` 只为遍历 | 白占内存 | `[I4]` |
| `range(0, 10, 0)` | `ValueError: step must not be zero` | `[I2]` |
| `range(10, 0)` | 空序列（方向错） | `[I2]` |

## 6. 推导式

### 6.1 四种形态

```python
source = [1, 2, 3, 4]

print([item * 2 for item in source if item % 2 == 0])   # [4, 8]（实测）
print({str(item): item * 2 for item in source})         # {'1': 2, '2': 4, ...}（实测）
print({item % 3 for item in source})                    # {0, 1, 2}（实测）
print((item * 2 for item in source))                    # generator（实测）
```

| 形态 | 语法 | 结果类型 | 依据 |
| --- | --- | --- | --- |
| 列表推导式 | `[expr for x in it if cond]` | `list` | `[I4]` |
| 字典推导式 | `{k: v for x in it}` | `dict` | `[I4]` |
| 集合推导式 | `{expr for x in it}` | `set` | `[I4]` |
| 生成器表达式 | `(expr for x in it)` | `generator` | `[I1]` |
| 元组推导式 | 不存在 | —— | `[I4]` |

### 6.2 元组推导式是个误解

```python
gen = (item * 2 for item in [1, 2])
print(type(gen).__name__)     # generator（实测）
print(tuple(gen))             # (2, 4)
```

| 写法 | 实际是 | 依据 |
| --- | --- | --- |
| `(x for x in it)` | 生成器表达式 | `[I1]` |
| `tuple(x for x in it)` | 先求值再转元组 | `[I4]` |
| `(x,)` | 单元素元组，不是推导式 | `[I4]` |

### 6.3 嵌套推导式的顺序

```python
print([(a, b) for a in "ab" for b in [1, 2]])
# [('a', 1), ('a', 2), ('b', 1), ('b', 2)]（实测）

print([[row * 2 for row in [1, 2]] for _ in range(2)])
# [[2, 4], [2, 4]]（实测）
```

| 写法 | 等价循环 | 依据 |
| --- | --- | --- |
| `[f(a, b) for a in A for b in B]` | 外层 a、内层 b | `[I4]` |
| `[[f(r) for r in row] for row in grid]` | 外层行、内层列 | `[I4]` |

> 注意：多个 `for` 从左到右就是嵌套层级，越靠左越外层；写反了结果形状会变（行列转置）。`[I4]`

### 6.4 推导式 vs 循环

| 维度 | 推导式 | 显式循环 |
| --- | --- | --- |
| 用途 | 纯映射/过滤 | 有副作用、多步逻辑 |
| 可读性 | 简单场景更好 | 复杂逻辑更好 |
| 性能 | 略快（C 层优化） | 相当 |
| 调试 | 难打断点 | 容易 |
| 依据 | `[I4]` | `[I6]` |

```python
# 反例：推导式里做副作用
[print(item) for item in items]

# 正例
for item in items:
    print(item)
```

| 红线 | 说明 | 依据 |
| --- | --- | --- |
| 不为了副作用用推导式 | 违反语义 | `[I6]` |
| 嵌套不超过两层 | 再深就难读 | `[I6]` |
| 条件超过两个 | 抽成函数 | `[I6]` |

### 6.5 作用域

```python
value = "outer"
squares = [value for value in range(3)]
print(value)     # outer，推导式变量不外泄（Python 3）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 推导式有自己的作用域 | 变量不外泄 | `[I4]` |
| 生成器表达式同理 | 惰性求值 | `[I1]` |
| 闭包捕获的是**变量** | 循环里创建函数要小心 | 第 06 章 |

### 6.6 海象运算符

```python
results = [cleaned for item in ["a", "", "b"] if (cleaned := item.strip())]
print(results)     # ['a', 'b']
```

| 用法 | 说明 | 依据 |
| --- | --- | --- |
| `if (x := f())` | 求值一次、复用 | `[I4]` |
| 过度使用 | 可读性下降 | `[I6]` |

## 7. 生成器（Generator）

### 7.1 生成器函数

```python
def tool_names(names, prefix=None):
    for name in names:
        if prefix is None or name.startswith(prefix):
            yield name
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 含 `yield` 的函数是生成器函数 | 调用返回生成器对象 | `[I3]` |
| 调用时**不执行**函数体 | 只创建对象 | `[I3]` |
| 每次 `next()` 执行到下一个 `yield` | 然后暂停 | `[I3]` |

### 7.2 执行流程

```python
def counting():
    for item in [1, 2]:
        print("YIELD", item)
        yield item
    print("YIELD_END")

gen = counting()
print("FIRST_NEXT", next(gen))
print("SECOND_NEXT", next(gen))
try:
    next(gen)
except StopIteration:
    print("EXHAUSTED", True)
```

本机实测输出：

```text
YIELD 1
FIRST_NEXT 1
YIELD 2
SECOND_NEXT 2
YIELD_END
EXHAUSTED True
```

| 阶段 | 状态 | 依据 |
| --- | --- | --- |
| 调用 `counting()` | 创建生成器，未执行 | `[I3]` |
| `next()` 第 1 次 | 执行到 `yield 1` 暂停 | `[I3]` |
| `next()` 第 2 次 | 从暂停处继续 | `[I3]` |
| `next()` 第 3 次 | 函数结束 → `StopIteration` | `[I3]` |

```python
print(gen.gi_frame, gen.gi_running)     # None False（实测，耗尽后帧已释放）
```

### 7.3 生成器表达式

```python
import sys

list_comp = [item for item in range(1000)]
gen_expr = (item for item in range(1000))
print(sys.getsizeof(list_comp), sys.getsizeof(gen_expr))   # 8856 192（实测）
```

| 维度 | `[...]` | `(...)` |
| --- | --- | --- |
| 求值 | 立即 | 惰性 |
| 内存 | 与元素数成正比 | 固定（约 200 字节） |
| 可重复遍历 | ✅ | ❌ |
| 可索引 | ✅ | ❌ |
| 依据 | `[I4]` | `[I1]` |

> 注意：内存对比只在「不用一次算完」时才有意义；如果下游立刻 `sum()` 或 `list()`，生成器省的是中间列表，仍然省。`[I1]`

### 7.4 链式调用（管道）

```python
def filter_even(items):
    for item in items:
        if item % 2 == 0:
            yield item


def square(items):
    for item in items:
        yield item * item


print(list(take(square(filter_even(naturals())), 4)))   # [0, 4, 16, 36]（实测）
```

| 特点 | 说明 | 依据 |
| --- | --- | --- |
| 每个阶段都是惰性 | 只在最下游拉取时推进 | `[I3]` |
| 内存恒定 | 一次只流过一个元素 | `[I3]` |
| 可无限管道 | 前提是下游有限制（`take` / `islice`） | `[I7]` |

### 7.5 `send`：向生成器传值

```python
def accumulator():
    total = 0
    while True:
        value = yield total
        if value is None:
            break
        total += value
    return total


acc = accumulator()
print(next(acc), acc.send(10), acc.send(5))    # 0 10 15（实测）
try:
    acc.send(None)
except StopIteration as error:
    print("SEND_RETURN", error.value)          # 15（实测）
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 首次必须 `next()` 或 `send(None)` | 推进到第一个 `yield` | `[I3]` |
| `send(v)` 的值成为 `yield` 表达式的值 | 双向通道 | `[I3]` |
| `return x` 变成 `StopIteration.value` | 可取值 | `[I3]` |

> 注意：`send` 是协程的雏形；`yield from` 与 `asyncio` 都建立在这条通道上（第 26 章）。`[I5]`

### 7.6 `yield from`：委托子迭代器

```python
def inner():
    yield 1
    yield 2
    return "done"


def outer():
    result = yield from inner()
    print("YIELD_FROM_RESULT", result)
    yield 3


print("YIELD_FROM", list(outer()))
```

实测输出：

```text
YIELD_FROM_RESULT done
YIELD_FROM [1, 2, 3]
```

| 能力 | 说明 | 依据 |
| --- | --- | --- |
| 产出子迭代器的所有值 | 不用手写 `for` | `[I5]` |
| 拿到子生成器的 `return` 值 | `yield from` 的求值结果 | `[I5]` |
| 转发 `send` / `throw` | 双向委托 | `[I5]` |
| 扁平化嵌套 | 替代递归 `for` | `[I5]` |

### 7.7 生成器的 `return` 值

```python
def with_return():
    yield 1
    return 99


generator = with_return()
print(next(generator))          # 1
try:
    next(generator)
except StopIteration as error:
    print(error.value)          # 99（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `return` 结束生成器 | 抛 `StopIteration(value)` | `[I3]` |
| `for` 拿不到返回值 | 被循环吞掉 | `[I3]` |
| 想让 `for` 拿到 | 用 `yield from` 或显式 `next` | `[I5]` |

### 7.8 `throw` 与 `close`

```python
def handler():
    try:
        yield 1
    except ValueError:
        yield "handled"


gen_handler = handler()
print(next(gen_handler))                 # 1
print(gen_handler.throw(ValueError("x")))  # handled（实测）
gen_handler.close()
print(gen_handler.gi_frame is None)      # True（实测）
```

| 方法 | 作用 | 依据 |
| --- | --- | --- |
| `throw(exc)` | 在暂停处抛异常 | `[I3]` |
| `close()` | 抛 `GeneratorExit`，触发 `finally` | `[I3]` |
| `gi_frame` | 耗尽/关闭后为 `None` | `[I3]` |

### 7.9 PEP 479：生成器内不许抛 `StopIteration`

```python
def bad():
    raise StopIteration("oops")
    yield 1


try:
    list(bad())
except RuntimeError as error:
    print(type(error).__name__, type(error.__cause__).__name__)
    # RuntimeError StopIteration（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 生成器内 `StopIteration` 被转成 `RuntimeError` | 防止静默截断 | `[I8]` |
| 原异常存进 `__cause__` | 可追溯 | `[I8]` |
| 想结束生成器 | 用 `return` | `[I3]` |

> 注意：PEP 479 的原因很实际——如果生成器内部调用某个函数抛了 `StopIteration`，旧行为会让整个生成器**静默提前结束**，非常难查。`[I8]`

### 7.10 三种实现对比

| 方案 | 代码量 | 内存 | 一次性 | 适用 |
| --- | --- | --- | --- | --- |
| 列表 | 少 | 大 | 可重复 | 小集合 |
| 迭代器类 | 多 | 小 | 一次性 | 需要复杂状态/额外方法 |
| 生成器 | 少 | 小 | 一次性 | 绝大多数场景 |

## 8. `itertools` 简介

### 8.1 无限迭代器

| 工具 | 作用 | 依据 |
| --- | --- | --- |
| `count(start, step)` | 无限递增 | `[I7]` |
| `cycle(iterable)` | 无限循环 | `[I7]` |
| `repeat(value, times)` | 重复（可限次） | `[I7]` |

```python
print(list(islice(count(10, 2), 4)))       # [10, 12, 14, 16]（实测）
print(list(islice(cycle("ab"), 5)))        # ['a', 'b', 'a', 'b', 'a']（实测）
```

### 8.2 有限但高效

| 工具 | 作用 | 依据 |
| --- | --- | --- |
| `chain(*its)` | 串联 | `[I7]` |
| `islice(it, n)` | 取前 n 个 | `[I7]` |
| `tee(it, n)` | 复制成 n 个独立迭代器 | `[I7]` |
| `pairwise(it)` | 相邻对（3.10+） | `[I7]` |
| `zip_longest(*its)` | 取最长，补 `fillvalue` | `[I7]` |
| `takewhile` / `dropwhile` | 按条件截断/跳过 | `[I7]` |

```python
print(list(chain([1, 2], [3])))                  # [1, 2, 3]（实测）
print(list(pairwise([1, 2, 3, 4])))              # [(1, 2), (2, 3), (3, 4)]（实测）
left, right = tee(iter([1, 2, 3]))
print(list(left), list(right))                   # [1, 2, 3] [1, 2, 3]（实测）
```

### 8.3 组合

| 工具 | 作用 | 依据 |
| --- | --- | --- |
| `product(A, B)` | 笛卡尔积（可 `repeat=n`） | `[I7]` |
| `permutations(A, r)` | 排列 | `[I7]` |
| `combinations(A, r)` | 组合（不重复） | `[I7]` |
| `combinations_with_replacement` | 可重复组合 | `[I7]` |

```python
print(list(product("ab", [1, 2])))    # [('a', 1), ('a', 2), ('b', 1), ('b', 2)]（实测）
```

### 8.4 分组与累积

| 工具 | 作用 | 依据 |
| --- | --- | --- |
| `groupby(it, key)` | 相邻同键分组 | `[I7]` |
| `accumulate(it, func)` | 累积（默认求和） | `[I7]` |

```python
print([(key, list(group)) for key, group in groupby("aabbbc")])
# [('a', ['a', 'a']), ('b', ['b', 'b', 'b']), ('c', ['c'])]（实测）

print(list(accumulate([1, 2, 3, 4])))    # [1, 3, 6, 10]（实测）
```

> 注意：`groupby` 只合并**相邻**同键元素；输入未排序会得到多个同名分组，需要先 `sorted(key=...)`。`[I7]`

### 8.5 常见组合写法

| 需求 | 写法 | 依据 |
| --- | --- | --- |
| 批次切分 | `islice(it, size)` 循环 | `[I7]` |
| 滑动窗口 | `pairwise` 或 `zip(*[it]*n)` | `[I7]` |
| 展平一层 | `chain.from_iterable(nested)` | `[I7]` |
| 累计和 | `accumulate` | `[I7]` |
| 按组统计 | `sorted` → `groupby` | `[I7]` |
| 补长配对 | `zip_longest` | `[I7]` |

```python
# 展平一层
nested = [[1, 2], [3], []]
print(list(chain.from_iterable(nested)))   # [1, 2, 3]
```

## 9. 综合示例：流式事件管道

```python
"""第 17 章综合示例：生成器管道 + islice 限流。"""

from itertools import islice


def tool_events(names):
    for name in names:
        yield {"type": "tool", "name": name}
        if name.startswith("fail"):
            yield {"type": "error", "name": name}


def only_errors(events):
    for event in events:
        if event["type"] == "error":
            yield event


print("ALL:", list(tool_events(["search", "fail_cache", "summarize"])))
print("ERRORS:", list(only_errors(tool_events(["search", "fail_cache"]))))
print("FIRST_TWO:", list(islice(tool_events(["a", "b", "c"]), 2)))
```

本机实测输出：

```text
ALL: [{'type': 'tool', 'name': 'search'}, {'type': 'tool', 'name': 'fail_cache'}, {'type': 'error', 'name': 'fail_cache'}, {'type': 'tool', 'name': 'summarize'}]
ERRORS: [{'type': 'error', 'name': 'fail_cache'}]
FIRST_TWO: [{'type': 'tool', 'name': 'a'}, {'type': 'tool', 'name': 'b'}]
```

**逐段说明**：

| 代码 | 用到的机制 | 依据 |
| --- | --- | --- |
| `tool_events` 里两次 `yield` | 一个事件可产出多条 | `[I3]` |
| `only_errors` 过滤 | 生成器管道 | `[I3]` |
| `islice(..., 2)` | 限流，防止无限管道 | `[I7]` |
| 每个 `list()` 都重新构造 | 生成器一次性 | `[I1]` |

> 注意：如果写成 `events = tool_events(...)` 再分别 `list(events)` 两次，第二次是空的——这是本节最容易踩的坑。`[I1]`

## 10. 注意事项与新手错误对照表

| 错误写法 / 操作 | 报错或现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 对 list 调 `next()` | `TypeError` | 先 `iter()` | `[I2]` |
| 对生成器调 `len()` / 索引 | `TypeError` | 先 `list()` | `[I2]` |
| 生成器用两次 | 第二次为空 | 重新构造或存 list | `[I1]` |
| `__iter__` 返回新迭代器却调 `next(obj)` | `TypeError` | 返回 `self` | `[I2]` |
| `__next__` 用 `return None` 结束 | 死循环 | `raise StopIteration` | `[I2]` |
| 生成器里 `raise StopIteration` | `RuntimeError`（PEP 479） | `return` | `[I8]` |
| `for` 里改 list | 跳过元素 | 重建/复制 | `[I1]` |
| `for` 里增删 dict | `RuntimeError` | 遍历副本 | `[I2]` |
| 无限生成器直接 `list()` | 内存耗尽 | `islice` / `takewhile` | `[I7]` |
| 用 `range(len(x))` | 啰嗦易错 | `enumerate` | `[I4]` |
| `zip` 长度不等以为报错 | 静默截断 | `strict=True` | `[I2]` |
| 推导式里做 `print` | 可读性差 | 用 `for` | `[I6]` |
| 推导式嵌套三层 | 难读 | 拆函数 | `[I6]` |
| 以为 `(x for x in ...)` 是元组 | 实际是生成器 | `tuple(...)` | `[I4]` |
| 嵌套推导式顺序写反 | 结果转置 | 左外右内 | `[I4]` |
| 推导式变量以为会泄漏 | 实际不泄漏 | 正常用 | `[I4]` |
| `send` 首次不用 `next` | `TypeError: can't send non-None value` | 先 `next()` | `[I3]` |
| 生成器 `return` 值用 `for` 取 | 取不到 | `yield from` / `next` | `[I3]` |
| `groupby` 前不排序 | 同名分组多个 | 先 `sorted` | `[I7]` |
| `tee` 之后原迭代器再用 | 数据被缓冲/错乱 | 只用 `tee` 的副本 | `[I7]` |
| 生成器持有大对象 | 内存不释放 | 及时 `close()` / 不用时丢弃 | `[I3]` |
| 生成器里做隐藏副作用 | 调用时机难预测 | 显式函数 | `[I6]` |
| 在生成器里 `yield` 后忘记 `return` | 逻辑不结束 | 明确终止条件 | `[I3]` |
| 迭代器耗尽后以为会重置 | 空 | 新建 | `[I1]` |
| `iter(callable, sentinel)` 顺序写反 | 行为异常 | `iter(f, sentinel)` | `[I1]` |
| 用 `isinstance(x, Iterator)` 判断能否 `for` | 旧式协议漏判 | 用 `iter()` 试 | `[I2]` |
| 文件对象遍历后 `read()` | 空字符串 | `seek(0)` | `[I1]` |
| `map`/`filter` 结果当 list 用 | `TypeError` | `list()` 包一层 | `[I2]` |
| 用生成器做「可重复的默认参数」 | 第二次为空 | 传函数或 `None` | `[I1]` |
| 生成器里 `yield from` 无限序列 | 卡死 | 加限流 | `[I5]` |
| `close()` 里 `yield` | `RuntimeError` | `close` 不产出 | `[I3]` |
| 生成器异常没被消费 | 静默丢失 | 消费方处理异常 | `[I3]` |
| 用 list 做大数据管道 | 内存爆炸 | 生成器管道 | `[I1]` |
| 递归生成器不 `yield from` | 需要手写循环 | `yield from` | `[I5]` |
| 生成器当协程用 | 需 `send` 且易错 | 用 `async`（26） | `[I3]` |
| `sum` 生成器后还想再用 | 空 | 先 `list` | `[I1]` |
| `any`/`all` 里写有副作用的函数 | 短路导致部分不执行 | 用显式循环 | `[I2]` |
| `zip` 结果不 `list` 就打印 | 显示对象地址 | 转 list | `[I2]` |
| `range` 步长为 0 | `ValueError` | 步长非 0 | `[I2]` |
| 推导式里用 `await` | `SyntaxError` | 异步推导式（27） | `[I4]` |

## 11. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 大数据用生成器，小集合用 list | 别过度优化 | `[I1]` |
| 简单转换用推导式 | 可读性最好 | `[I4]` |
| 复杂逻辑写生成器函数 | 比推导式清晰 | `[I3]` |
| 用 `enumerate` 取下标 | 不手写计数器 | `[I4]` |
| 用 `zip(..., strict=True)` | 早暴露长度不一致 | `[I2]` |
| 用 `islice` 限流 | 防止无限管道 | `[I7]` |
| `groupby` 前先排序 | 否则分组重复 | `[I7]` |
| 生成器命名表达意图 | `iter_tool_names()` | `[I6]` |
| 注释说明「为什么惰性」 | 后来者需要 | `[I6]` |
| 需要重复遍历就转 list | 显式优于隐式 | `[I6]` |

**风格示范**：

```python
def iter_tool_names(records, prefix=None):
    """按前缀过滤工具名。

    为什么用生成器：records 可能来自流式响应，无法预知总量。
    """
    for record in records:
        name = record.get("name")
        if not name:
            continue
        if prefix is None or name.startswith(prefix):
            yield name
```

**边界**：

- 生成器持有文件/连接时，必须用 `with` 或 `close()` 保证释放（第 18 章）。
- 生成器内异常只有被消费时才暴露，不要在生成器里做「必须成功」的关键事务。
- 同步生成器不能 `await`；异步场景要用异步生成器（第 27 章）。

## 12. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[I1]` | python.org | https://docs.python.org/3.12/tutorial/classes.html | 迭代器协议、`__next__`、`StopIteration`、生成器、遍历时修改容器 |
| `[I2]` | python.org | https://docs.python.org/3.12/library/stdtypes.html | 迭代器类型、`iter()` / `next()`、`range`、dict 视图、`zip` / `map` / `filter` |
| `[I3]` | PEP 官方 | https://peps.python.org/pep-0255/ | 生成器与 `yield` 的引入、执行模型 |
| `[I4]` | python.org | https://docs.python.org/3.12/tutorial/controlflow.html | `range` 是 iterable、`enumerate`、推导式、`zip` |
| `[I5]` | PEP 官方 | https://peps.python.org/pep-0380/ | `yield from` 委托语义 |
| `[I6]` | PEP 官方 | https://peps.python.org/pep-0008/ | 命名、注释写「为什么」、可读性优先 |
| `[I7]` | python.org | https://docs.python.org/3.12/library/itertools.html | `count` / `cycle` / `repeat` / `chain` / `islice` / `tee` / `groupby` / `accumulate` / `pairwise` / `product` |
| `[I8]` | PEP 官方 | https://peps.python.org/pep-0479/ | 生成器内 `StopIteration` 转 `RuntimeError` |

> **核对状态**：`[I4]` `[I6]` 与本章 `README.md` 已核对来源一致；其余链接按 `docs.python.org/3.12` 与 `peps.python.org` 官方结构整理，**本次未逐页直连复核**。文中「实测」结论均为本机 Python 3.12.8 运行结果。

## 13. 毕业自查清单

**能说清（概念层）**：

- [ ] iterable 与 iterator 的区别，各自需要什么方法
- [ ] `for` 循环的完整展开
- [ ] 为什么迭代器只能消费一次
- [ ] 迭代器 `__iter__` 为什么返回 `self`
- [ ] 旧式 `__getitem__` 协议为什么能迭代但不是 `Iterable`
- [ ] `range` 为什么不占内存、为什么不是 iterator
- [ ] 元组推导式为什么不存在
- [ ] 嵌套推导式哪个 `for` 是外层
- [ ] 生成器函数调用时为什么不执行
- [ ] `send`、`yield from`、`throw`、`close` 各自作用
- [ ] PEP 479 解决什么问题

**能写出（代码层）**：

- [ ] 倒数迭代器类（`__iter__` + `__next__`）
- [ ] 无限自然数生成器 + `islice` 限流
- [ ] 三层生成器管道（过滤 → 变换 → 限量）
- [ ] 用 `send` 传值的累加器
- [ ] 用 `yield from` 委托并拿到 `return` 值
- [ ] 四种推导式（列表/字典/集合/生成器）
- [ ] 用 `groupby` 分组（先排序）
- [ ] 用 `pairwise` / `accumulate` / `chain`

**能判断（避坑层）**：

- [ ] 看到生成器用两次能指出第二次为空
- [ ] 看到对生成器 `len()` 能指出 `TypeError`
- [ ] 看到 `__next__` 返回 `None` 能指出死循环
- [ ] 看到生成器内 `raise StopIteration` 能指出 PEP 479
- [ ] 看到 `list(无限生成器)` 能指出内存耗尽
- [ ] 看到 `groupby` 未排序能指出重复分组
- [ ] 看到推导式里 `print` 能指出不该为副作用用推导式

**能跑通（验收层）**：

- [ ] 运行 `examples/generator_demo.py` 并解释「剩余」为什么少一个
- [ ] 把第 9 节示例存成文件运行，输出与文档一致
- [ ] 在 REPL 验证「`iter([1,2])` 用两次第二次为空」
- [ ] 手写生成器并用 `sys.getsizeof` 对比列表与生成器内存

## 14. 下一章衔接

第 18 章 `上下文管理器`：生成器持有资源时必须保证释放，`with` 就是标准答案；`@contextmanager` 本身就是「只 `yield` 一次的生成器」。

本章留下的伏笔：

1. `close()` 会向生成器抛 `GeneratorExit`，`finally` 里的清理因此得以执行——这正是 `with` 的底层机制。
2. `yield from` 的双向通道是协程的基础，第 26 章会用它写 `async` 逻辑。
3. 生成器管道 + `islice` 的组合，是流式响应处理的常用形态（第 27 章）。