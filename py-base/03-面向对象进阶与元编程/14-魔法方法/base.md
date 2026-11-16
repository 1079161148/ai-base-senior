# 14 魔法方法 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把截图里的「字符串表示、比较操作、算术运算、容器协议、类型转换、属性访问拦截、对象生命周期、常用魔法方法速查」逐条展开，并补上 `NotImplemented`、`__hash__` 联动、`__bool__` 优先级等必然遇到的内容，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测） |
| 前置 | 第 08–13 章（类、属性、可调用、装饰器） |
| 覆盖范围 | 特殊方法查找规则、`__str__`/`__repr__`、比较与哈希、算术与反射、容器协议、类型转换、属性拦截、生命周期、速查表 |
| 明确不覆盖 | 描述符协议细节（15）、迭代器与生成器实现（17）、上下文管理器深入（18）、`abc`（19） |
| 学完验收 | 能说出任一语法背后调哪个方法、能实现一个可比较可哈希可迭代的类、能解释 `__getattr__` 与 `__getattribute__` 的差别（见第 13 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Gn]` `` 指向第 12 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果。

**推荐顺序**：

```text
1 协议与隐式调用（第 1 节）→ 谁在调、在哪找
2 字符串表示（第 2 节）    → str / repr / format
3 比较操作（第 3 节）      → eq / lt / hash 联动
4 算术运算（第 4 节）      → add / radd / iadd / 类型转换
5 容器协议（第 5 节）      → len / getitem / contains / bool
6 属性访问拦截（第 6 节）  → getattr vs getattribute
7 对象生命周期（第 7 节）  → new / init / del / enter / exit
8 速查表（第 8 节）
9 综合示例（第 9 节）
10 注意事项（第 10 节）    → 40 条错误对照
```

**与 README 的分工**：README 给结论，本文件负责协议穷举与陷阱。冲突时以本文件为准。

## 1. 协议与隐式调用

### 1.1 魔法方法是「语法钩子」

| 语法 | 实际调用 | 依据 |
| --- | --- | --- |
| `str(x)` | `type(x).__str__(x)` | `[G1]` |
| `repr(x)` | `type(x).__repr__(x)` | `[G1]` |
| `len(x)` | `type(x).__len__(x)` | `[G1]` |
| `x[i]` | `type(x).__getitem__(x, i)` | `[G1]` |
| `x + y` | `type(x).__add__(x, y)` | `[G1]` |
| `x == y` | `type(x).__eq__(x, y)` | `[G1]` |
| `for i in x` | `type(x).__iter__(x)` | `[G1]` |
| `x()` | `type(x).__call__(x)` | `[G1]` |
| `with x` | `__enter__` / `__exit__` | `[G1]` |

### 1.2 关键：在**类型**上查找，不在实例字典

```python
class NoLen:
    pass

instance = NoLen()
instance.__len__ = lambda: 5    # 无效
try:
    len(instance)
except TypeError as error:
    print(type(error).__name__)   # TypeError（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 特殊方法查类型 | 绕过实例 `__dict__` | `[G1]` |
| 给实例塞 `__len__` 无效 | 解释器不认 | `[G1]` |
| 这就是「隐式调用」的实现方式 | 保证性能与一致性 | `[G1]` |

> 注意：这与普通属性查找不同（普通属性先看实例字典）；所以「给单个对象打补丁加 `__len__`」是行不通的。`[G1]`

### 1.3 不要手动调用

| 错误写法 | 问题 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `obj.__len__()` | 绕过协议、可读性差 | `len(obj)` | `[G1]` |
| `obj.__str__()` | 不会处理回退 | `str(obj)` | `[G1]` |
| `obj.__add__(y)` | 不会走反射 | `obj + y` | `[G1]` |
| `obj.__eq__(y)` | 不会让对方尝试 | `obj == y` | `[G1]` |

### 1.4 协议与鸭子类型

| 协议 | 需要的方法 | 语法 | 依据 |
| --- | --- | --- | --- |
| 可迭代 | `__iter__`（或旧式 `__getitem__`） | `for` | `[G1]` |
| 容器 | `__len__` + `__getitem__` | `len` / `[]` | `[G1]` |
| 可比较 | `__eq__` / `__lt__` | `==` / `<` | `[G1]` |
| 可哈希 | `__hash__` | `hash()` / dict 键 | `[G1]` |
| 可调用 | `__call__` | `()` | 第 11 章 |
| 上下文管理 | `__enter__` / `__exit__` | `with` | 第 18 章 |

## 2. 字符串表示

### 2.1 `__str__` 与 `__repr__`

```python
class Money:
    def __init__(self, amount):
        self.amount = amount

    def __repr__(self):
        return f"Money({self.amount})"

    def __str__(self):
        return f"CNY{self.amount}"

money = Money(10)
print(repr(money), str(money), f"{money}")
# Money(10) CNY10 CNY10（实测）
```

| 方法 | 受众 | 目标 | 依据 |
| --- | --- | --- | --- |
| `__repr__` | 开发者 | 无歧义、最好能重建对象 | `[G1]` |
| `__str__` | 最终用户 | 可读 | `[G1]` |
| `__format__` | 格式化 | 控制 `format()` / f-string | `[G1]` |

### 2.2 回退规则

```python
class NoStr:
    def __repr__(self):
        return "NoStr()"

print(str(NoStr()))    # NoStr()（实测：没有 __str__ 时回退 __repr__）
```

| 情况 | `str(x)` | `repr(x)` | 依据 |
| --- | --- | --- | --- |
| 两个都有 | `__str__` | `__repr__` | `[G1]` |
| 只有 `__repr__` | 用 `__repr__` | `__repr__` | `[G1]` |
| 只有 `__str__` | `__str__` | 默认 `<... object at ...>` | `[G1]` |
| 都没有 | 默认 repr | 默认 repr | `[G1]` |

```python
class Plain:
    pass

print(repr(Plain()))   # <__main__.Plain object at 0x...>（实测）
```

> 注意：默认 `repr` 包含**模块名与地址**，形如 `<__main__.Plain object at 0x...>`；不要用它做断言或日志解析。`[G1]`

### 2.3 容器里用 `repr`

```python
money = Money(10)
print([money])     # [Money(10)]（实测：列表内部用 repr）
```

| 场景 | 用哪个 | 依据 |
| --- | --- | --- |
| `print(x)` | `str` | `[G1]` |
| `print([x])` | `repr` | `[G1]` |
| 日志 / 调试 | `repr` | `[G1]` |
| 面向用户输出 | `str` | `[G1]` |

### 2.4 `__format__` 与 f-string

```python
class Amount:
    def __init__(self, value):
        self.value = value

    def __format__(self, spec):
        return format(self.value, spec)

print(f"{Amount(3.14159):.2f}")   # 3.14
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| f-string 调 `__format__` | 不是 `str` | `[G1]` |
| 默认 `__format__` 忽略 spec | 返回 `str(self)` | `[G1]` |
| 自定义可转发给数值格式 | 常用 | `[G1]` |

### 2.5 `repr` 的写法规范

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 形如 `ClassName(字段=值)` | 一眼看出类型与内容 | `[G2]` |
| 字符串用 `!r` | `Money('x')` 而非 `Money(x)` | `[G1]` |
| 不调用可能抛异常的逻辑 | `repr` 要安全 | `[G1]` |
| 递归要截断 | 防无限递归 | `[G1]` |

```python
class Node:
    def __init__(self, name, children=None):
        self.name = name
        self.children = children or []

    def __repr__(self):
        return f"Node({self.name!r}, {len(self.children)} children)"
```

## 3. 比较操作

### 3.1 `__eq__` 与 `NotImplemented`

```python
class Eq:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        if not isinstance(other, Eq):
            return NotImplemented     # 让对方尝试，而不是直接 False
        return self.value == other.value

print(Eq(1) == Eq(1))   # True（实测）
```

| 返回值 | 含义 | 依据 |
| --- | --- | --- |
| `True` / `False` | 明确结论 | `[G1]` |
| `NotImplemented` | 「我不认识这个类型，你试试」 | `[G1]` |
| 抛异常 | 不推荐，破坏比较语义 | `[G1]` |

> 注意：`NotImplemented` 是单例对象，不是 `NotImplementedError`；前者用于协议回退，后者是「未实现」异常。`[G1]`

### 3.2 `__eq__` 会关掉 `__hash__`

```python
class Eq:
    def __eq__(self, other):
        return NotImplemented

print(Eq.__hash__ is None)    # True（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 定义 `__eq__` 且未定义 `__hash__` | `__hash__` 被设为 `None` | `[G1]` |
| 实例变不可哈希 | 不能做 dict 键 / set 元素 | `[G1]` |
| 原因 | 维持「相等则哈希相等」契约 | `[G1]` |

```python
class Frozen:
    def __init__(self, value):
        self.value = value

    def __eq__(self, other):
        return isinstance(other, Frozen) and self.value == other.value

    def __hash__(self):
        return hash(self.value)

print(hash(Frozen(1)) == hash(Frozen(1)))   # True（实测）
print(len({Frozen(1), Frozen(1)}))          # 1（实测）
```

| 对象类型 | 是否该实现 `__hash__` | 依据 |
| --- | --- | --- |
| 不可变值对象 | 应该（按字段组合） | `[G1]` |
| 可变对象 | 不应该 | `[G1]` |
| 实体（有 id） | 用默认（按身份） | `[G1]` |

### 3.3 六个比较与 `total_ordering`

```python
import functools

@functools.total_ordering
class Ver:
    def __init__(self, number):
        self.number = number

    def __eq__(self, other):
        return self.number == other.number

    def __lt__(self, other):
        return self.number < other.number

print(Ver(1) < Ver(2), Ver(2) >= Ver(1), Ver(1) <= Ver(1))
# True True True（实测）
```

| 方法 | 运算符 | 依据 |
| --- | --- | --- |
| `__eq__` | `==` | `[G1]` |
| `__ne__` | `!=`（默认由 `__eq__` 推导） | `[G1]` |
| `__lt__` | `<` | `[G1]` |
| `__le__` | `<=` | `[G1]` |
| `__gt__` | `>` | `[G1]` |
| `__ge__` | `>=` | `[G1]` |

| 方案 | 代码量 | 依据 |
| --- | --- | --- |
| 手写六个 | 多 | `[G2]` |
| `@total_ordering` + 两个 | 少，推荐 | `[G3]` |
| `@dataclass(order=True)` | 自动生成 | `[G2]` |

> 注意：`total_ordering` 要求 `__eq__` + 至少一个排序方法（通常 `__lt__`）；它会补出其余四个。`[G3]`

### 3.4 比较与排序

```python
items = [Ver(3), Ver(1), Ver(2)]
print([item.number for item in sorted(items)])   # [1, 2, 3]
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `sorted` 用 `__lt__` | 只需一个排序方法 | `[G1]` |
| 排序稳定 | 相等元素保持原序 | `[G1]` |
| `key=` 优先于 `__lt__` | 字段排序更常用 | `[G1]` |

## 4. 算术运算

### 4.1 `__add__` 与 `__radd__`

```python
class Vec:
    def __init__(self, x):
        self.x = x

    def __add__(self, other):
        if isinstance(other, Vec):
            return Vec(self.x + other.x)
        return NotImplemented

    def __radd__(self, other):
        if other == 0:
            return self           # 支持 sum()
        return NotImplemented

    def __repr__(self):
        return f"Vec({self.x})"

print(Vec(1) + Vec(2))                 # Vec(3)（实测）
print(sum([Vec(1), Vec(2)]))           # Vec(3)（实测，靠 __radd__）
```

| 步骤 | 情况 | 依据 |
| --- | --- | --- |
| 1 | 先 `type(x).__add__(x, y)` | `[G1]` |
| 2 | 返回 `NotImplemented` → `type(y).__radd__(y, x)` | `[G1]` |
| 3 | 都失败 → `TypeError` | `[G1]` |

| 场景 | 需要哪个 | 依据 |
| --- | --- | --- |
| `vec + vec` | `__add__` | `[G1]` |
| `0 + vec` / `sum` | `__radd__` | `[G1]` |
| `vec += vec` | `__iadd__`（没有则用 `__add__`） | `[G1]` |

### 4.2 `__iadd__` 就地修改

```python
class Vec:
    def __init__(self, x):
        self.x = x

    def __iadd__(self, other):
        self.x += other.x
        return self

vec = Vec(1)
vec += Vec(2)
print(vec)     # Vec(3)（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `+=` 先找 `__iadd__` | 没有则 `__add__` 后重新绑定 | `[G1]` |
| 必须返回对象 | 返回 `None` 会让名字变 `None` | `[G1]` |
| 可变对象适合就地改 | 不可变对象应返回新值 | `[G1]` |

> 注意：`__iadd__` 返回 `None` 是常见 bug——`a += b` 之后 `a` 变成 `None`，且不报错。`[G1]`

### 4.3 一元运算

| 方法 | 语法 | 依据 |
| --- | --- | --- |
| `__neg__` | `-x` | `[G1]` |
| `__pos__` | `+x` | `[G1]` |
| `__abs__` | `abs(x)` | `[G1]` |
| `__invert__` | `~x` | `[G1]` |
| `__round__` | `round(x)` | `[G1]` |

### 4.4 类型转换

```python
class AsInt:
    def __int__(self):
        return 42

    def __float__(self):
        return 1.5

    def __index__(self):
        return 3

print(int(AsInt()), float(AsInt()), [0, 1, 2, 3][AsInt()])
# 42 1.5 3（实测）
```

| 方法 | 语法 | 依据 |
| --- | --- | --- |
| `__int__` | `int(x)` | `[G1]` |
| `__float__` | `float(x)` | `[G1]` |
| `__complex__` | `complex(x)` | `[G1]` |
| `__bool__` | `bool(x)` | `[G1]` |
| `__index__` | 用于索引、`hex`、切片 | `[G1]` |
| `__bytes__` | `bytes(x)` | `[G1]` |

> 注意：`__index__` 才让对象能当索引/切片，`__int__` 不行；这是容易混淆的一对。`[G1]`

### 4.5 `NotImplemented` 与 `NotImplementedError`

| 名字 | 类型 | 用途 | 依据 |
| --- | --- | --- | --- |
| `NotImplemented` | 单例对象 | 运算符/比较回退 | `[G1]` |
| `NotImplementedError` | 异常类 | 抽象方法「未实现」 | `[G1]` |

```python
class Base:
    def run(self):
        raise NotImplementedError("子类必须实现 run")
```

## 5. 容器协议

### 5.1 `__len__` + `__getitem__` 就够了

```python
class Batch:
    def __init__(self, names):
        self.names = list(names)

    def __len__(self):
        return len(self.names)

    def __getitem__(self, index):
        return self.names[index]

    def __contains__(self, name):
        return name in self.names

batch = Batch(["a", "b"])
print(len(batch), batch[0], "a" in batch, [item for item in batch])
# 2 a True ['a', 'b']（实测）
```

| 语法 | 依赖 | 依据 |
| --- | --- | --- |
| `len(x)` | `__len__` | `[G1]` |
| `x[0]` | `__getitem__` | `[G1]` |
| `for i in x` | `__iter__` 或旧式 `__getitem__` | `[G1]` |
| `in` | `__contains__` 或迭代回退 | `[G1]` |
| `reversed(x)` | `__reversed__` 或 `__len__` + `__getitem__` | `[G1]` |

> 注意：只实现 `__getitem__` 也能迭代（旧式协议），但**没有结束条件时会无限循环**；显式 `__iter__` 更安全清晰（第 17 章）。`[G1]`

### 5.2 `__contains__` 覆盖默认行为

```python
class CaseInsensitive:
    def __init__(self, words):
        self.words = {w.lower() for w in words}

    def __contains__(self, item):
        return item.lower() in self.words

    def __iter__(self):
        return iter(self.words)

print("ABC" in CaseInsensitive(["abc"]))   # True
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 有 `__contains__` 就直接用 | 不再迭代 | `[G1]` |
| 没有则退化为迭代 + `==` | 慢 | `[G1]` |

### 5.3 写操作

| 方法 | 语法 | 依据 |
| --- | --- | --- |
| `__setitem__` | `x[i] = v` | `[G1]` |
| `__delitem__` | `del x[i]` | `[G1]` |
| `__getitem__` 收 `slice` | `x[1:3]` | `[G1]` |

```python
class Box:
    def __init__(self):
        self._data = {}

    def __getitem__(self, key):
        return self._data[key]

    def __setitem__(self, key, value):
        self._data[key] = value

    def __len__(self):
        return len(self._data)
```

> 注意：切片会传 `slice` 对象；如果你的 `__getitem__` 只处理整数，`x[1:3]` 会静默返回错误结果或抛 `TypeError`。`[G1]`

### 5.4 布尔值：`__bool__` 优先于 `__len__`

```python
class Truthy:
    def __init__(self, number):
        self.number = number

    def __len__(self):
        return self.number

    def __bool__(self):
        return False

print(bool(Truthy(5)), len(Truthy(5)))   # False 5（实测）
```

| 优先级 | 方法 | 依据 |
| --- | --- | --- |
| 1 | `__bool__` | `[G1]` |
| 2 | `__len__ != 0` | `[G1]` |
| 3 | 默认 `True` | `[G1]` |

> 注意：容器类通常不需要写 `__bool__`，`__len__` 就够了；两者都写时以 `__bool__` 为准，可能造成「长度 5 却是假」的困惑。`[G1]`

## 6. 属性访问拦截

### 6.1 `__getattr__`：只在找不到时调用

```python
class Hooked:
    def __getattr__(self, name):
        return f"getattr:{name}"

hooked = Hooked()
print(hooked.missing)              # getattr:missing（实测）
print(hasattr(hooked, "missing"))  # True（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 常规查找失败才调用 | 兜底 | `[G1]` |
| 返回任意值 | 不抛异常就等于「存在」 | `[G1]` |
| 适合动态属性、代理对象 | 如 ORM 的惰性字段 | `[G1]` |

**无限递归陷阱**：

```python
class Bad:
    def __getattr__(self, name):
        return self.anything      # 又一次触发 __getattr__ → 递归

# RecursionError
```

正确写法：

```python
class Good:
    def __getattr__(self, name):
        return f"fallback:{name}"     # 不访问未定义属性
```

> 注意：`__getattr__` 里访问 `self.xxx` 若 `xxx` 不存在，会再次触发 `__getattr__`，导致 `RecursionError`；需要走 `object.__getattribute__` 或直接返回常量。`[G1]`

### 6.2 `__getattribute__`：每次访问都调用

```python
class Always:
    def __getattribute__(self, name):
        if name == "special":
            return "intercepted"
        return object.__getattribute__(self, name)

print(Always().special)   # intercepted（实测）
```

| 方法 | 触发时机 | 性能影响 | 依据 |
| --- | --- | --- | --- |
| `__getattr__` | 只有查找失败 | 小 | `[G1]` |
| `__getattribute__` | **每次**属性访问 | 大，容易出错 | `[G1]` |

| 维度 | `__getattr__` | `__getattribute__` |
| --- | --- | --- |
| 调用条件 | 常规查找失败 | 总是先调用 |
| 能否拦截已有属性 | 不能 | 能 |
| 递归风险 | 有（访问未定义属性） | 高（访问任何属性） |
| 优先级 | 最后 | 最先 |
| 推荐度 | ✅ 常用 | ⚠️ 框架级才用 |

> 注意：`__getattribute__` 会拦截**所有**属性，包括 `self.__dict__`；实现时必须用 `object.__getattribute__(self, name)`，否则极易递归。`[G1]`

### 6.3 `__setattr__` 与 `__delattr__`

```python
class Setter:
    def __setattr__(self, name, value):
        print("SET", name)
        object.__setattr__(self, name, value)

setter = Setter()
setter.x = 1
print(setter.x)     # SET x / 1（实测）
```

| 方法 | 语法 | 依据 |
| --- | --- | --- |
| `__setattr__` | `x.attr = v` | `[G1]` |
| `__delattr__` | `del x.attr` | `[G1]` |

```python
class ReadOnly:
    def __setattr__(self, name, value):
        if name in ("frozen",) and getattr(self, "frozen", False):
            raise AttributeError("对象已冻结")
        object.__setattr__(self, name, value)
```

> 注意：`__setattr__` 会拦截 `__init__` 里的赋值；用「冻结开关」必须先允许初始化，再打开。`[G1]`

### 6.4 与描述符的关系

| 层级 | 谁先 | 依据 |
| --- | --- | --- |
| `__getattribute__` | 最先，包住一切 | `[G1]` |
| 描述符 `__get__` | 在其内部调用 | 第 15 章 |
| `__getattr__` | 最后兜底 | `[G1]` |

> 注意：同时实现 `__getattribute__` 与描述符会让行为极难推理；业务代码只选一个。`[G1]`

## 7. 对象生命周期

### 7.1 创建与销毁

| 方法 | 时机 | 依据 |
| --- | --- | --- |
| `__new__` | 创建（第 10 章） | `[G1]` |
| `__init__` | 初始化 | `[G1]` |
| `__del__` | 回收前，**不保证**执行 | `[G1]` |

```python
class Res:
    def __init__(self):
        self.opened = True

    def __del__(self):
        self.opened = False    # 不能依赖它释放资源
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `__del__` 调用时机不确定 | 解释器退出时可能不调 | `[G1]` |
| 异常会被忽略 | 别在里面做重要清理 | `[G1]` |
| 资源释放用 `with` | 第 18 章 | `[G1]` |

### 7.2 上下文管理

| 方法 | 作用 | 依据 |
| --- | --- | --- |
| `__enter__` | 进入 `with`，返回值给 `as` | `[G1]` |
| `__exit__` | 退出，返回 `True` 可吞异常 | `[G1]` |

```python
class Timer:
    def __enter__(self):
        import time
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc, tb):
        import time
        self.elapsed = time.perf_counter() - self.start
        return False    # 不吞异常
```

> 注意：`__exit__` 返回 `True` 会**吞掉**异常，这是静默失败的常见来源；除非你有意压制，否则返回 `False`/`None`。`[G1]`

### 7.3 `__slots__` 与实例字典

```python
class Slotted:
    __slots__ = ("x",)

    def __init__(self):
        self.x = 1

print(hasattr(Slotted(), "__dict__"))   # False（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 有 `__slots__` 就没有 `__dict__` | 省内存 | `[G1]` |
| 不能加未声明属性 | `AttributeError` | `[G1]` |
| 子类不声明会重新有 `__dict__` | 需延续 | `[G1]` |

### 7.4 `__call__`

第 11 章已详述：`__call__` 让实例可调用，与 `__init__` 的触发时机不同。`[G1]`

## 8. 常用魔法方法速查

### 8.1 表示与格式化

| 方法 | 触发 | 依据 |
| --- | --- | --- |
| `__repr__` | `repr()`、容器内、调试 | `[G1]` |
| `__str__` | `str()`、`print()` | `[G1]` |
| `__format__` | `format()`、f-string | `[G1]` |
| `__bytes__` | `bytes()` | `[G1]` |

### 8.2 比较与哈希

| 方法 | 触发 | 依据 |
| --- | --- | --- |
| `__eq__` / `__ne__` | `==` / `!=` | `[G1]` |
| `__lt__` / `__le__` / `__gt__` / `__ge__` | `<` `<=` `>` `>=` | `[G1]` |
| `__hash__` | `hash()`、set、dict 键 | `[G1]` |
| `__bool__` | `bool()`、`if` | `[G1]` |

### 8.3 算术与转换

| 方法 | 触发 | 依据 |
| --- | --- | --- |
| `__add__` / `__radd__` / `__iadd__` | `+` / `+=` | `[G1]` |
| `__sub__` / `__mul__` / `__truediv__` / `__floordiv__` / `__mod__` / `__pow__` | 对应运算符 | `[G1]` |
| `__neg__` / `__pos__` / `__abs__` / `__round__` | 一元运算 | `[G1]` |
| `__int__` / `__float__` / `__complex__` / `__index__` | 类型转换 | `[G1]` |

### 8.4 容器与迭代

| 方法 | 触发 | 依据 |
| --- | --- | --- |
| `__len__` | `len()`、真值回退 | `[G1]` |
| `__getitem__` | `x[i]`、切片、旧式迭代 | `[G1]` |
| `__setitem__` / `__delitem__` | `x[i] = v` / `del x[i]` | `[G1]` |
| `__contains__` | `in` | `[G1]` |
| `__iter__` / `__next__` | `for`、`next()` | `[G1]` |
| `__reversed__` | `reversed()` | `[G1]` |

### 8.5 属性与生命周期

| 方法 | 触发 | 依据 |
| --- | --- | --- |
| `__getattr__` | 查找失败后 | `[G1]` |
| `__getattribute__` | 每次读取 | `[G1]` |
| `__setattr__` / `__delattr__` | 赋值 / 删除 | `[G1]` |
| `__init__` / `__new__` / `__del__` | 生命周期 | `[G1]` |
| `__enter__` / `__exit__` | `with` | `[G1]` |
| `__call__` | `obj()` | `[G1]` |

### 8.6 不要自己实现的

| 方法 | 原因 | 依据 |
| --- | --- | --- |
| `__getattribute__`（除框架） | 性能与递归风险 | `[G1]` |
| `__del__` 做资源释放 | 时机不确定 | `[G1]` |
| 自定义 `__xxx__` | 保留给语言 | `[G2]` |

## 9. 综合示例：值对象

```python
"""第 14 章综合示例：可表示、可比较、可哈希、可相加的值对象。"""

import functools


@functools.total_ordering
class Money:
    def __init__(self, amount, currency="CNY"):
        self.amount = amount
        self.currency = currency

    def __repr__(self):
        return f"Money({self.amount}, {self.currency!r})"

    def __str__(self):
        return f"{self.amount} {self.currency}"

    def __eq__(self, other):
        if not isinstance(other, Money):
            return NotImplemented
        return (self.amount, self.currency) == (other.amount, other.currency)

    def __lt__(self, other):
        return self.amount < other.amount

    def __hash__(self):
        return hash((self.amount, self.currency))

    def __add__(self, other):
        if not isinstance(other, Money):
            return NotImplemented
        return Money(self.amount + other.amount, self.currency)

    def __len__(self):
        return len(str(self.amount))


first = Money(10)
second = Money(5)
print(repr(first), str(first), first + second, first > second, len(first), {first, Money(10)})
```

本机实测输出：

```text
Money(10, 'CNY') 10 CNY 15 CNY True 2 {Money(10, 'CNY')}
```

**逐段说明**：

| 方法 | 作用 | 依据 |
| --- | --- | --- |
| `__repr__` | 无歧义，字符串用 `!r` | `[G1]` |
| `__str__` | 面向用户 | `[G1]` |
| `__eq__` | 类型不符返回 `NotImplemented` | `[G1]` |
| `__lt__` + `total_ordering` | 补出 `>` `<=` `>=` | `[G3]` |
| `__hash__` | 与 `__eq__` 保持一致 | `[G1]` |
| `__add__` | 返回新对象 | `[G1]` |
| `__len__` | 让 `len()` 有意义 | `[G1]` |
| `{first, Money(10)}` | 去重成功 | `[G1]` |

> 注意：`__len__` 返回「金额位数」是刻意设计，但如果 `amount` 是负数，`len(str(-5))` 会算上负号；值对象的 `__len__` 语义要写进 docstring，否则容易误解。`[G1]`

## 10. 注意事项与新手错误对照表

| 错误写法 / 操作 | 报错或现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 手动调 `obj.__len__()` | 可读性差、绕过回退 | `len(obj)` | `[G1]` |
| 给实例赋 `__len__` | `TypeError: object has no len()` | 定义在类上 | `[G1]` |
| 只写 `__str__` 不写 `__repr__` | 容器里显示默认地址 | 两个都写 | `[G1]` |
| `__repr__` 里用 `str` | 字符串无引号，歧义 | 用 `!r` | `[G1]` |
| `__repr__` 抛异常 | 调试更难 | 只做简单拼装 | `[G1]` |
| `__eq__` 直接返回 `False` | 破坏反射比较 | `NotImplemented` | `[G1]` |
| 定义 `__eq__` 后忘记 `__hash__` | 不可哈希 | 显式实现或接受 | `[G1]` |
| 可变对象实现 `__hash__` | dict 键行为错乱 | 不可变或按身份 | `[G1]` |
| 只写 `__lt__` | `>` 报错 | `total_ordering` | `[G3]` |
| `__iadd__` 返回 `None` | 名字变 `None` | `return self` | `[G1]` |
| `__add__` 返回 `None` | 结果为 `None` | 返回新对象 | `[G1]` |
| 只写 `__add__` 就期望 `sum` | `TypeError` | 补 `__radd__` | `[G1]` |
| `__getitem__` 不处理 `slice` | 切片报错 | 检查 `isinstance(key, slice)` | `[G1]` |
| 只实现 `__getitem__` 当迭代 | 可能无限循环 | 显式 `__iter__` | `[G1]` |
| `__len__` 返回负数 | `ValueError` | 非负整数 | `[G1]` |
| `__len__` 返回浮点 | `TypeError` | 返回 `int` | `[G1]` |
| 同时写 `__bool__` 与 `__len__` | 布尔与长度不一致 | 只保留一个语义 | `[G1]` |
| `__getattr__` 里访问 `self.x` | `RecursionError` | 用 `object.__getattribute__` | `[G1]` |
| `__getattr__` 无条件返回 | `hasattr` 永远真、拼写错误不报 | 限定前缀 | `[G1]` |
| `__getattribute__` 里直接 `self.x` | `RecursionError` | `object.__getattribute__` | `[G1]` |
| 用 `__getattribute__` 拦普通属性 | 性能下降、难推理 | 优先 `__getattr__` | `[G1]` |
| `__setattr__` 拦截初始化 | 对象建不出来 | 加开关 | `[G1]` |
| `__del__` 释放文件/连接 | 可能不执行 | `with` / `close()` | `[G1]` |
| `__exit__` 返回 `True` | 静默吞异常 | 返回 `False`/`None` | `[G1]` |
| `__int__` 当索引 | `TypeError` | 实现 `__index__` | `[G1]` |
| 用 `NotImplementedError` 做运算符回退 | 报错而非回退 | `NotImplemented` | `[G1]` |
| 比较不同货币金额 | 语义错误 | 先校验币种 | `[G1]` |
| `__hash__` 与 `__eq__` 不一致 | set 去重失效 | 同一组字段 | `[G1]` |
| `__slots__` 子类不声明 | 子类又有 `__dict__` | 子类也声明 | `[G1]` |
| 自定义 `__xxx__` | 与语言冲突 | 不用 | `[G2]` |
| `__repr__` 递归引用自身 | `RecursionError` | 截断或 `...` | `[G1]` |
| `__format__` 忽略 spec | f-string 格式化无效 | 转发给 `format()` | `[G1]` |
| `__contains__` 里做重 I/O | `in` 变慢 | 预处理 | `[G1]` |
| `__iter__` 返回 `self` 但无 `__next__` | `TypeError` | 两者配套 | `[G1]` |
| `__next__` 不抛 `StopIteration` | 无限循环 | 正确终止 | `[G1]` |
| 可变对象做 dict 键 | 找不到 | 用不可变键 | `[G1]` |
| `__eq__` 里改状态 | 副作用 | 只读比较 | `[G1]` |
| 在 `__repr__` 里查数据库 | 调试变慢 | 只读内存字段 | `[G1]` |
| `__len__` 中做懒加载 | `len` 有副作用 | 显式方法 | `[G1]` |

## 11. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| `__repr__` 必写，`__str__` 按需 | 调试友好 | `[G1]` |
| `repr` 用 `ClassName(字段=值!r)` | 无歧义 | `[G2]` |
| `__eq__` 返回 `NotImplemented` | 支持反射 | `[G1]` |
| 值对象同时实现 `__eq__` 与 `__hash__` | 保持契约 | `[G1]` |
| 排序用 `total_ordering` 或 `dataclass(order=True)` | 少写四个方法 | `[G3]` |
| 算术运算返回新对象 | 不可变风格 | `[G1]` |
| 实现 `__radd__` 支持 `sum` | 组合友好 | `[G1]` |
| 容器至少 `__len__` + `__getitem__` | 即可迭代 | `[G1]` |
| 迭代显式写 `__iter__` | 避免无限循环 | `[G1]` |
| 属性拦截优先 `__getattr__` | 影响面小 | `[G1]` |
| 资源释放用上下文管理器 | 不用 `__del__` | `[G1]` |
| 特殊方法写 docstring | 调用点不可见 | `[G2]` |

**风格示范**：

```python
class Point:
    """二维点：不可变值对象。"""

    __slots__ = ("x", "y")

    def __init__(self, x: float, y: float) -> None:
        object.__setattr__(self, "x", x)
        object.__setattr__(self, "y", y)

    def __repr__(self) -> str:
        return f"Point({self.x!r}, {self.y!r})"

    def __eq__(self, other) -> bool:
        if not isinstance(other, Point):
            return NotImplemented
        return (self.x, self.y) == (other.x, other.y)

    def __hash__(self) -> int:
        return hash((self.x, self.y))
```

**边界**：

- 特殊方法里不要做重 I/O 或阻塞调用，它们在语法路径上被高频触发。
- `__eq__` / `__hash__` 的字段必须一致，否则 set/dict 行为错乱。
- `__repr__` 里不要输出敏感数据（它常被写进日志）。

## 12. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[G1]` | python.org | https://docs.python.org/3.12/reference/datamodel.html | 特殊方法查找规则、表示/比较/哈希/算术/容器/属性访问/生命周期协议、`NotImplemented`、旧式迭代回退、`__slots__` |
| `[G2]` | PEP 官方 | https://peps.python.org/pep-0008/ | 补齐比较方法、不发明 dunder、docstring、`!r` 风格的调试表示 |
| `[G3]` | python.org | https://docs.python.org/3.12/library/functools.html | `functools.total_ordering` |
| `[G4]` | python.org | https://docs.python.org/3.12/library/stdtypes.html | 真值测试、容器抽象、`bool` 与 `len` 的关系 |
| `[G5]` | PEP 官方 | https://peps.python.org/pep-0020/ | The Zen of Python（显式、简单） |
| `[G6]` | GitHub 官方 | https://github.com/python/cpython/blob/main/Doc/reference/datamodel.rst | 官方语言参考源文件（`[G1]` 页脚 Show Source 指向） |
| `[G7]` | python.org | https://docs.python.org/3.12/library/dataclasses.html | `@dataclass(order=True)` 自动生成比较方法 |

> **核对状态**：`[G1]` `[G2]` 与本章 `README.md` 已核对来源一致；其余链接按 `docs.python.org/3.12` 与 `peps.python.org` 官方结构整理，**本次未逐页直连复核**。文中「实测」结论均为本机 Python 3.12.8 运行结果。

## 13. 毕业自查清单

**能说清（概念层）**：

- [ ] 特殊方法为什么在类型上查找，给实例塞 `__len__` 为什么无效
- [ ] `__str__` 与 `__repr__` 的受众与回退关系
- [ ] 容器里为什么显示 `repr`
- [ ] 定义 `__eq__` 后 `__hash__` 发生什么，为什么
- [ ] `NotImplemented` 与 `NotImplementedError` 的区别
- [ ] `x + y` 的完整查找顺序（含反射）
- [ ] `__iadd__` 返回 `None` 会怎样
- [ ] `__bool__` 与 `__len__` 的优先级
- [ ] `__getattr__` 与 `__getattribute__` 的触发时机
- [ ] `__exit__` 返回 `True` 的后果
- [ ] `__index__` 与 `__int__` 的差别

**能写出（代码层）**：

- [ ] 带 `__repr__` / `__str__` 的值类
- [ ] 带 `__eq__` / `__hash__` 且能进 set 的值类
- [ ] 用 `total_ordering` 实现完整比较
- [ ] 实现 `__add__` / `__radd__` 并支持 `sum`
- [ ] 实现 `__len__` / `__getitem__` / `__contains__` 的容器
- [ ] 实现 `__iter__` / `__next__` 的迭代器（第 17 章预习）
- [ ] 用 `__getattr__` 做代理并避免递归
- [ ] 用 `__enter__` / `__exit__` 写计时器

**能判断（避坑层）**：

- [ ] 看到只写 `__str__` 能指出容器里显示地址
- [ ] 看到 `__eq__` 后未写 `__hash__` 能指出不可哈希
- [ ] 看到 `__iadd__` 返回 `None` 能指出名字变 `None`
- [ ] 看到 `__getattr__` 里访问 `self.x` 能指出递归
- [ ] 看到 `__exit__` 返回 `True` 能指出吞异常
- [ ] 看到 `__del__` 释放资源能指出时机不确定

**能跑通（验收层）**：

- [ ] 运行 `examples/magic_demo.py` 并解释迭代为什么能工作
- [ ] 把第 9 节示例存成文件运行，输出与文档一致
- [ ] 在 REPL 验证「实例上赋 `__len__` 无效」
- [ ] 手写值对象并验证 `set` 去重与排序

## 14. 下一章衔接

第 15 章 `描述符`：本章说「属性访问可以拦截」，但没有解释 `obj.method` 为什么自动带 `self`、`@property` 到底怎么实现——答案都是描述符协议。

本章留下的伏笔：

1. 函数本身就是非数据描述符，`__get__` 负责绑定 `self`。
2. `@property` 是标准的数据描述符，优先级高于实例字典。
3. `__getattr__` 与 `__getattribute__` 是查找链的两端，描述符插在中间；第 15 章会给出完整顺序。