# 08 类和对象 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把截图里的定义类、`__init__`、属性、方法、继承、MRO、访问控制、常见操作逐条展开，并补上截图没列但写类一定会遇到的语法，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测） |
| 前置 | 第 05–07 章（函数、作用域、lambda） |
| 覆盖范围 | `class`、`type()` 动态建类、`__init__`、实例/类属性、实例方法、`@classmethod`、`@staticmethod`、继承、多继承、MRO、`super()`、访问控制、内置属性与反射函数 |
| 明确不覆盖 | 对象的类型体系（09）、`__new__` 与创建过程（10）、`__call__`（11）、元类（12）、装饰器（13）、`property` 与描述符（15） |
| 学完验收 | 能写出带类属性、类方法、静态方法的三层继承结构，能解释 MRO 与名称改写（见第 14 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[On]` `` 指向第 13 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果。

**推荐顺序**：

```text
1 类与对象是什么（第 1 节）→ 数据 + 行为的绑定
2 定义类（第 2 节）        → class 语句、类体执行、type() 动态建类
3 __init__（第 3 节）      → self、返回值约束、校验
4 实例属性与类属性（第 4 节）→ 查找、遮蔽、共享陷阱、__slots__
5 实例方法（第 5 节）      → 绑定机制、通过类调用
6 类方法与静态方法（第 6 节）→ 三者对比、替代构造器
7 继承（第 7 节）          → super()、多继承、MRO、菱形
8 访问控制（第 8 节）      → 单/双下划线、名称改写
9 常见操作（第 9 节）      → 内置属性 + 反射函数速查
10 综合示例（第 10 节）
11 注意事项（第 11 节）    → 36 条错误对照
```

**与 README 的分工**：README 讲机制轮廓，本文件负责穷举与判定。冲突时以本文件为准。

## 1. 类与对象是什么

**定义**：类是「数据 + 行为」的模板；对象（实例）是按模板造出来的具体值。`[O1]`

```python
class ToolCall:
    """一次工具调用记录。"""

    kind = "tool"

    def __init__(self, name):
        self.name = name

    def describe(self):
        return f"{self.kind}:{self.name}"

call = ToolCall("search")
print(call.describe())    # tool:search
```

| 概念 | 说明 | 依据 |
| --- | --- | --- |
| 类 | 模板，描述「有哪些属性、能做什么」 | `[O1]` |
| 实例 | 按类创建的具体对象，各自持有数据 | `[O1]` |
| 属性 | 绑在对象或类上的数据 | `[O2]` |
| 方法 | 定义在类体里的函数，第一个参数是实例 | `[O1]` |

**为什么需要类**（对比第 04 章的 dict）：

| 方案 | 表达 | 问题 |
| --- | --- | --- |
| `{"name": "search", "cost": 1.2}` | 纯数据 | 没有行为，字段名靠约定 |
| `("search", 1.2)` | 元组 | 下标无语义，加字段就乱 |
| `ToolCall("search", 1.2)` | 类 | 字段有名字、行为跟着走、可校验 |

| 收益 | 说明 | 依据 |
| --- | --- | --- |
| 封装 | 数据与操作放在一起 | `[O1]` |
| 复用 | 一个类造多个实例 | `[O1]` |
| 校验 | `__init__` 里统一检查 | `[O1]` |
| 多态 | 同一接口不同实现（继承） | `[O1]` |

**类本身也是对象**：

```python
print(type(ToolCall))              # <class 'type'>（实测同款）
print(ToolCall.__name__)           # ToolCall
print(ToolCall.__bases__[0].__name__)   # object（实测）
```

> 注意：「类也是对象」意味着类可以赋值、可以当参数、可以被 `type()` 创建；它的类型是 `type`，完整讨论在第 09 章。`[O2]`

## 2. 定义类

### 2.1 基本语法

```python
class 类名(基类列表):
    """可选文档字符串。"""
    类属性 = 值

    def 方法名(self, 参数...):
        方法体
```

```python
class ToolCall:
    """一次工具调用记录。"""

    kind = "tool"          # 类属性

    def __init__(self, name, cost=0.0):   # 构造方法
        self.name = name                  # 实例属性
        self.cost = cost

    def describe(self):                   # 实例方法
        return f"{self.kind}:{self.name} ({self.cost:.1f}s)"
```

| 组成部分 | 规则 | 依据 |
| --- | --- | --- |
| `class` | 关键字 | `[O1]` |
| 类名 | `CapWords`（PEP 8） | `[O3]` |
| 基类列表 | 可省略，省略等价 `(object,)` | `[O1]` |
| 冒号与缩进 | 与函数一致 | `[O1]` |
| 类体 | 定义时执行一次 | `[O2]` |
| docstring | 类体第一条字符串 | `[O3]` |

### 2.2 类体在定义时执行

```python
print("before")

class Demo:
    print("类体执行")      # 定义时就打印

print("after")
# before
# 类体执行
# after
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 类体是一个代码块 | `class` 语句执行时运行一次 | `[O2]` |
| 只执行一次 | 之后实例化不再执行类体 | `[O2]` |
| 类体里的 `def` 创建函数对象 | 不是方法调用 | `[O2]` |

> 注意：类体里写 `print` 或耗时计算，会在**导入模块时**就执行；类体只应放定义与简单常量。`[O2]`

### 2.3 类体是独立命名空间

```python
class Config:
    timeout = 30

    def show(self):
        # return timeout      NameError：类体不是闭包作用域
        return self.timeout   # 正确：走 self

print(Config().show())    # 30
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 类体有自己的命名空间 | 名字在类体内可见 | `[O2]` |
| 类体不参与闭包 | 方法体不能直接读类体局部名 | `[O2]` |
| 访问要走 `self.` / 类名 | `self.timeout` 或 `Config.timeout` | `[O2]` |

> 注意：这是第 06 章「类作用域不参与 LEGB」的具体表现；方法里写 `return timeout` 会 `NameError`。`[O2]`

### 2.4 `type()` 动态创建类

`class` 语句的等价形式是调用 `type(name, bases, namespace)`。`[O2]`

```python
Dyn = type("Dyn", (ToolCall,), {"label": "dyn"})
dyn = Dyn("search", 0.5)
print(Dyn.__name__)              # Dyn
print(Dyn.__bases__[0].__name__) # ToolCall（实测）
print(dyn.label, dyn.describe()) # dyn tool:search (0.5s)
```

| 参数 | 含义 | 依据 |
| --- | --- | --- |
| `name` | 类名字符串，成为 `__name__` | `[O2]` |
| `bases` | 基类元组，空元组默认 `object` | `[O2]` |
| `namespace` | 类体字典（属性与方法） | `[O2]` |

```python
Plain = type("Plain", (), {})
print(Plain.__name__, Plain.__bases__[0].__name__)   # Plain object
```

| 用途 | 说明 | 依据 |
| --- | --- | --- |
| 运行时生成类 | 字段/接口由配置决定 | `[O2]` |
| 框架内部 | ORM、序列化库常用 | `[O2]` |
| 教学理解 | 看清 `class` 到底做了什么 | `[O2]` |

> 注意：`type()` 建类的 `namespace` 里写 `lambda` 会导致方法拿不到 `self` 的 `__name__`、也没有 docstring；业务代码优先用 `class` 语句。`[O3]`

### 2.5 空类与占位

```python
class Empty:
    pass

class Marker:
    """仅用于类型标记。"""
    ...
```

| 写法 | 用途 | 依据 |
| --- | --- | --- |
| `pass` | 合法空类体 | `[O1]` |
| `...` | 表达式占位 | `[O1]` |
| 只有 docstring | 也算类体 | `[O3]` |

> 注意：空类最常见的用途是「哨兵」或「标记接口」；真正要表达协议时用 `Protocol` 或 ABC（第 19、20 章）。`[O2]`

## 3. 构造方法 `__init__`

### 3.1 作用与调用时机

```python
class ToolCall:
    def __init__(self, name):
        print("初始化", name)
        self.name = name

call = ToolCall("search")   # 打印：初始化 search
print(call.name)            # search
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 实例化时自动调用 | 不需要手动调 `__init__` | `[O1]` |
| 负责初始化 | 给实例绑定属性 | `[O1]` |
| 真正的「创建」在 `__new__` | `__init__` 只是初始化（第 10 章） | `[O2]` |
| 不定义也能创建实例 | 得到空对象 | `[O1]` |

```python
class Bare:
    pass

bare = Bare()
print(bare.__dict__)    # {}
```

### 3.2 `self` 是什么

`self` 是**实例本身**，调用 `call.describe()` 时由解释器自动传入。`[O1]`

```python
class Counter:
    def __init__(self):
        self.value = 0

    def increase(self):
        self.value += 1
        return self.value

counter = Counter()
print(counter.increase(), counter.value)   # 1 1
print(Counter.increase(counter))           # 2，等价手动传
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 名字约定为 `self` | PEP 8 要求；改名能跑但别改 | `[O3]` |
| 调用时不要手动传 | `obj.m()` 自动传 | `[O1]` |
| 通过类调用要手动传 | `Class.m(obj)` | `[O1]` |
| `self` 不是关键字 | 只是普通参数名 | `[O1]` |

> 注意：`self` 不是「当前对象的特殊引用」，而是「第一个位置参数」；这解释了为什么 `Class.m(obj)` 与 `obj.m()` 等价。`[O1]`

### 3.3 必须返回 `None`

```python
class BadInit:
    def __init__(self):
        return 1

try:
    BadInit()
except TypeError as error:
    print(type(error).__name__)   # TypeError（实测）
```

| 规则 | 依据 |
| --- | --- |
| `__init__` 返回非 `None` → `TypeError` | `[O2]` |
| 不需要写 `return` | `[O2]` |
| 想「返回别的对象」用 `__new__`（第 10 章） | `[O2]` |

### 3.4 参数、默认值与校验

```python
class ToolCall:
    def __init__(self, name, cost=0.0):
        if not isinstance(name, str) or not name.strip():
            raise ValueError("name 必须是非空字符串")
        if cost < 0:
            raise ValueError("cost 不能为负")
        self.name = name
        self.cost = cost

print(ToolCall("search").cost)   # 0.0
```

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 构造即校验 | 非法参数立刻抛异常 | `[O1]` |
| 默认值用不可变对象 | 与第 05 章默认参数规则一致 | `[O1]` |
| 不在 `__init__` 做重 I/O | 构造要快、可预测 | `[O3]` |
| 参数多时考虑数据类 | `@dataclass`（第 13 章） | `[O1]` |

> 注意：`__init__` 里的可变默认参数与普通函数同罪——`def __init__(self, items=[])` 会让所有实例共享同一个列表。`[O1]`

### 3.5 不定义 `__init__` 的情况

```python
class Empty:
    pass

empty = Empty()
print(empty.__dict__)    # {}
```

| 场景 | 是否需要 `__init__` |
| --- | --- |
| 只是类型标记 | 不需要 |
| 属性由外部赋值 | 可选 |
| 有任何必填数据 | 需要，便于校验 |

## 4. 实例属性与类属性

### 4.1 实例属性

```python
class ToolCall:
    def __init__(self, name):
        self.name = name      # 绑定到当前实例

a = ToolCall("search")
b = ToolCall("cache")
print(a.name, b.name)         # search cache
print(vars(a))                # {'name': 'search'}（实测同款）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 存在实例的 `__dict__` | `vars(obj)` 可看 | `[O2]` |
| 每个实例独立 | 互不影响 | `[O2]` |
| 只能在实例上访问 | 类上读不到未赋值的实例属性 | `[O2]` |

### 4.2 类属性

```python
class ToolCall:
    kind = "tool"          # 所有实例共享

a = ToolCall()
b = ToolCall()
print(a.kind, b.kind, ToolCall.kind)   # tool tool tool
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 存在类的 `__dict__` | `vars(类)` 可看 | `[O2]` |
| 所有实例可见 | 通过实例也能读到 | `[O2]` |
| 修改类属性影响所有实例 | 除非实例已遮蔽 | `[O2]` |
| 适合放常量与默认值 | 不适合放实例级状态 | `[O3]` |

### 4.3 查找顺序与遮蔽

**顺序：实例 `__dict__` → 类 `__dict__` → 父类（MRO）**。`[O2]`

```python
class Point:
    kind = "point"

p = Point()
print(p.kind)        # point（来自类）
p.kind = "special"   # 创建实例属性，遮蔽类属性
print(p.kind, Point.kind)    # special point（实测）
print(vars(p))               # {'kind': 'special'}（实测）
del p.kind
print(p.kind)                # point（遮蔽解除）
```

| 操作 | 结果 | 依据 |
| --- | --- | --- |
| `p.kind` 只读 | 找到类属性 | `[O2]` |
| `p.kind = x` | 在实例上新建，遮蔽类属性 | `[O2]` |
| `del p.kind` | 删除实例属性，重新暴露类属性 | `[O2]` |
| `Point.kind = x` | 改类属性，未遮蔽的实例都看到新值 | `[O2]` |

```python
# 实测：实例字段 + 遮蔽后的完整字典
class Point:
    kind = "point"
    def __init__(self, x, y):
        self.x, self.y = x, y

p = Point(1, 2)
p.kind = "special"
print(vars(p))    # {'x': 1, 'y': 2, 'kind': 'special'}
```

> 注意：`p.kind = x` 永远写实例，不会改类；想改类必须写 `Point.kind = x` 或 `type(p).kind = x`。`[O2]`

### 4.4 可变类属性陷阱（重点）

```python
class Bag:
    items = []          # 危险：所有实例共享

b1, b2 = Bag(), Bag()
b1.items.append(1)
print(b2.items)             # [1]（实测）
print(b1.items is b2.items) # True（实测）
```

| 写法 | 后果 | 依据 |
| --- | --- | --- |
| `items = []` 类属性 | 全部实例共享 | `[O1]` |
| `self.items = []` | 每个实例独立 | `[O1]` |
| 在 `__init__` 里创建 | 正确做法 | `[O1]` |

```python
class Bag:
    def __init__(self):
        self.items = []      # 正确：实例级

b1, b2 = Bag(), Bag()
b1.items.append(1)
print(b2.items)              # []
```

> 注意：这与第 05 章 `def f(bucket=[])` 是同一个陷阱：**可变默认值只创建一次**。类属性在类定义时创建一次，被所有实例共享。`[O1]`

### 4.5 `__dict__` 与 `__slots__`

```python
class Slotted:
    __slots__ = ("x",)

    def __init__(self, x):
        self.x = x

s = Slotted(1)
print(hasattr(s, "__dict__"))   # False（实测）
print(s.x)                      # 1
try:
    s.y = 2
except AttributeError as error:
    print(type(error).__name__)  # AttributeError（实测）
```

| 项 | 默认类 | 带 `__slots__` |
| --- | --- | --- |
| 实例字典 | 有 `__dict__` | 没有 |
| 可否加新属性 | 可以 | 不可以 |
| 内存 | 较大 | 较小 |
| 继承 | 自由 | 子类要延续约束 |

> 注意：`__slots__` 是性能/内存优化手段，不是访问控制；大量小对象（如坐标、事件）才值得用。`[O2]`

### 4.6 何时用类属性、何时用实例属性

| 数据 | 放哪 | 理由 |
| --- | --- | --- |
| 所有实例相同的常量 | 类属性 | 一份即可 |
| 每个实例不同的状态 | 实例属性 | 隔离 |
| 可变容器 | 实例属性 | 避免共享 |
| 计数器（全类统计） | 类属性 + 类方法 | 需要显式管理 |
| 配置项 | 模块常量或类属性 | 只读 |

> 注意：类属性一旦是可变对象，就默认「共享」；除非你明确要共享，否则一律放实例属性。`[O1]`

## 5. 实例方法

### 5.1 定义与调用

```python
class ToolCall:
    def __init__(self, name):
        self.name = name

    def describe(self):
        return f"tool:{self.name}"

call = ToolCall("search")
print(call.describe())         # tool:search
print(ToolCall.describe(call)) # tool:search，等价（实测同款）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 第一个参数是实例 | 自动传入 | `[O1]` |
| 返回普通值 | 与函数一致 | `[O1]` |
| `obj.method` 是绑定方法 | 已绑定 `self` | `[O2]` |
| `Class.method` 是函数 | 需要显式传实例 | `[O2]` |

```python
bound = call.describe
print(bound())               # tool:search
print(bound.__self__ is call)  # True，绑定方法持有实例
```

### 5.2 绑定机制（描述符预告）

| 访问方式 | 得到 | 依据 |
| --- | --- | --- |
| `call.describe` | 绑定方法（`self` 已绑定） | `[O2]` |
| `ToolCall.describe` | 普通函数 | `[O2]` |
| `call.describe.__self__` | 实例 | `[O2]` |

> 注意：方法为什么能自动传 `self`，本质是描述符协议；第 15 章展开。现在只需记住「实例访问会绑定，类访问不绑定」。`[O2]`

### 5.3 方法也是属性

```python
call.describe = lambda: "patched"
print(call.describe())    # patched
print(ToolCall("x").describe())   # tool:x，其他实例不受影响
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 方法存在类上 | 实例通过查找得到 | `[O2]` |
| 实例可覆盖 | 赋值后走实例属性 | `[O2]` |
| 覆盖只影响该实例 | 类方法不变 | `[O2]` |

> 注意：给实例「打补丁」是调试手段，生产代码不要用；可读性差且难排查。`[O3]`

### 5.4 方法命名与职责

| 前缀 | 含义 | 例子 |
| --- | --- | --- |
| `get_` | 读 | `get_name()` |
| `set_` | 写 | `set_cost()` |
| `is_` / `has_` | 布尔判断 | `is_valid()` |
| `to_` | 转换 | `to_dict()` |
| `from_`（类方法） | 构造 | `from_dict()` |

> 注意：`to_dict()` / `from_dict()` 是最常见的「序列化对称」写法；`from_` 系列应做成 `@classmethod`。`[O3]`

## 6. 类方法与静态方法

### 6.1 `@classmethod`

第一个参数是**类**（约定 `cls`），既能通过类调用，也能通过实例调用。`[O1]`

```python
class Point:
    def __init__(self, x, y):
        self.x, self.y = x, y

    @classmethod
    def origin(cls):
        return cls(0, 0)

    @classmethod
    def from_tuple(cls, pair):
        return cls(*pair)

print(Point.origin())            # <Point object>（实测：Point(0, 0)）
print(Point.from_tuple((3, 4)))  # Point(3, 4)
print(Point(1, 2).origin())      # 通过实例也可以
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `cls` 是类本身 | 不是实例 | `[O1]` |
| 继承时 `cls` 是子类 | 实测：`Point3D.origin()` 返回 `Point3D` | `[O2]` |
| 常用于替代构造器 | `from_dict` / `from_json` | `[O1]` |
| 类属性访问走 `cls` | 不要硬编码类名 | `[O1]` |

```python
class Point3D(Point):
    def __init__(self, x, y, z=0):
        super().__init__(x, y)
        self.z = z

print(type(Point3D.origin()).__name__)   # Point3D（实测）
```

> 注意：类方法里写 `Point(...)` 会把子类写死；写 `cls(...)` 才能让子类正确实例化。`[O2]`

### 6.2 `@staticmethod`

没有自动参数，本质是「放在类命名空间里的普通函数」。`[O1]`

```python
class Point:
    def __init__(self, x, y):
        self.x, self.y = x, y

    @staticmethod
    def distance(a, b):
        return ((a.x - b.x) ** 2 + (a.y - b.y) ** 2) ** 0.5

print(Point.distance(Point(0, 0), Point(3, 4)))   # 5.0（实测）
print(Point(0, 0).distance(Point(3, 4), Point(0, 0)))  # 5.0，实例调用也可
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 无 `self` / `cls` | 不自动传任何东西 | `[O1]` |
| 通过类和实例都能调用 | 行为一致 | `[O1]` |
| 适合放「与类相关但不依赖状态」的工具 | 如距离、格式转换 | `[O3]` |

> 注意：如果函数完全不需要类，放模块级更好；`@staticmethod` 的价值只是「归属清晰」。`[O3]`

### 6.3 三者对比

| 特性 | 实例方法 | `@classmethod` | `@staticmethod` |
| --- | --- | --- | --- |
| 第一个参数 | `self`（实例） | `cls`（类） | 无 |
| 通过实例调用 | ✅ | ✅ | ✅ |
| 通过类调用 | 需手动传实例 | ✅ | ✅ |
| 能访问实例属性 | ✅ | ❌ | ❌ |
| 能访问类属性 | ✅（`self.x` / `cls.x`） | ✅（`cls.x`） | 需显式传类 |
| 典型用途 | 业务行为 | 替代构造器、工厂 | 工具函数 |
| 依据 | `[O1]` | `[O1]` | `[O1]` |

```python
class Demo:
    value = 1

    def instance_method(self):
        return "instance", self.value

    @classmethod
    def class_method(cls):
        return "class", cls.value

    @staticmethod
    def static_method():
        return "static", Demo.value   # 静态方法里访问类属性要写类名

print(Demo().instance_method(), Demo.class_method(), Demo.static_method())
```

> 注意：静态方法里访问类属性必须显式写类名（或把类作为参数传入），这也说明它和类的关系只是「命名空间归属」。`[O1]`

### 6.4 用类方法实现「多构造器」

```python
class ToolCall:
    def __init__(self, name, cost):
        self.name = name
        self.cost = cost

    @classmethod
    def from_dict(cls, data):
        return cls(data["name"], data.get("cost", 0.0))

    @classmethod
    def from_line(cls, line):
        name, cost = line.split(",")
        return cls(name.strip(), float(cost))

print(ToolCall.from_dict({"name": "search", "cost": 1.2}).cost)   # 1.2
print(ToolCall.from_line("cache, 0.1").name)                       # cache
```

| 场景 | 推荐 |
| --- | --- |
| 从 dict / JSON 构造 | `@classmethod from_dict` |
| 从字符串 / 文件行构造 | `@classmethod from_xxx` |
| 需要默认实例 | `@classmethod default()` |
| 需要多个重载签名 | 多个 `from_` 类方法，Python 不支持重载 |

> 注意：Python 不支持方法重载；「多种构造方式」的标准写法就是多个 `@classmethod`。`[O1]`

## 7. 继承

### 7.1 单继承与重写

```python
class Base:
    def hello(self):
        return "base"

class Child(Base):
    def hello(self):
        return "child"

print(Base().hello(), Child().hello())   # base child
print(isinstance(Child(), Base))         # True
print(issubclass(Child, Base))           # True
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 子类继承父类全部属性与方法 | 通过 MRO 查找 | `[O1]` |
| 同名方法覆盖父类 | 直接定义即可 | `[O1]` |
| `isinstance` 认继承 | 子类实例是父类类型 | `[O2]` |

### 7.2 `super()` 调用父类

```python
class Base:
    def __init__(self, name):
        self.name = name

    def describe(self):
        return f"base:{self.name}"

class Child(Base):
    def __init__(self, name, extra):
        super().__init__(name)     # 调用父类初始化
        self.extra = extra

    def describe(self):
        return super().describe() + f"+{self.extra}"

print(Child("search", "fast").describe())   # base:search+fast
```

| 写法 | 说明 | 依据 |
| --- | --- | --- |
| `super().__init__(...)` | 标准做法 | `[O1]` |
| `Base.__init__(self, ...)` | 可行但硬编码父类 | `[O1]` |
| `super()` 零参形式 | 3.x 自动推断，见 PEP 3135 | `[O6]` |
| `super()` 在 MRO 中找「下一个」 | 不是「父类」，是「链上的下一个」 | `[O2]` |

> 注意：`super()` 的准确含义是「沿 MRO 的下一个类」，不是「直接父类」；这在多继承下差别巨大（见 7.5）。`[O2]`

### 7.3 多继承

```python
class A:
    def hello(self):
        return ["A"]

class B(A):
    def hello(self):
        return ["B"] + super().hello()

class C(A):
    def hello(self):
        return ["C"] + super().hello()

class D(B, C):
    def hello(self):
        return ["D"] + super().hello()

print(D().hello())                              # ['D', 'B', 'C', 'A']（实测）
print([c.__name__ for c in D.__mro__])          # ['D', 'B', 'C', 'A', 'object']（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 顺序由 `class D(B, C)` 决定 | 从左到右 | `[O2]` |
| `super()` 沿 MRO 前进 | B 的 `super()` 是 C | `[O2]` |
| 每个类只出现一次 | C3 线性化保证 | `[O2]` |
| `object` 在最后 | 所有类的根 | `[O2]` |

### 7.4 MRO（方法解析顺序）

**MRO = 类的方法与属性的查找顺序**，用 C3 线性化算法计算，保证：

1. 子类在父类之前；
2. 声明顺序在前的基类优先；
3. 每个类只出现一次；
4. 单调性：父类的相对顺序不被破坏。

| 查看方式 | 结果 | 依据 |
| --- | --- | --- |
| `D.__mro__` | 元组 | `[O2]` |
| `D.mro()` | 列表（可调用） | `[O2]` |
| `[c.__name__ for c in D.__mro__]` | 名字列表 | `[O2]` |

```python
print([c.__name__ for c in D.mro()])   # ['D', 'B', 'C', 'A', 'object']
```

**MRO 冲突会直接报错**：

```python
class X:
    pass

class Y(X):
    pass

try:
    class Z(X, Y):    # X 是 Y 的父类，顺序矛盾
        pass
except TypeError as error:
    print(type(error).__name__)   # TypeError: Cannot create a consistent MRO
```

> 注意：多继承顺序不是「谁写前面谁优先」这么简单；当基类之间有继承关系时，顺序必须满足「子类在前」。`[O2]`

### 7.5 菱形继承与 `super()` 链

```text
      A
     / \
    B   C
     \ /
      D
```

`D` 的 MRO 是 `D → B → C → A → object`；`B.hello()` 里的 `super()` 指向 **C**（不是 A），所以 `A.hello()` 只执行一次。`[O2]`

| 常见误解 | 实际 |
| --- | --- |
| `super()` = 父类 | `super()` = MRO 下一个 |
| 菱形会重复调用 A | 协作式 `super()` 只调用一次 |
| 不写 `super()` 也能协作 | 不写就断了链 |

> 注意：协作式多继承要求**每一层都调用 `super()`**；只要有一层漏掉，链就断了，后面的类不会执行。`[O2]`

### 7.6 重写与扩展的边界

| 做法 | 何时用 | 依据 |
| --- | --- | --- |
| 完全重写（不调 `super`） | 行为彻底不同 | `[O1]` |
| 扩展（`super()` + 新逻辑） | 保留父类行为 | `[O1]` |
| 抽公共逻辑到父类 | 多个子类重复 | `[O3]` |
| 用组合替代继承 | 只是「有一个」关系 | `[O3]` |

```python
# 组合优于继承
class Logger:
    def log(self, message):
        return f"[log] {message}"

class Service:
    def __init__(self, logger):
        self.logger = logger      # 有一个 logger，而不是是 logger

    def run(self):
        return self.logger.log("run")
```

> 注意：「is-a」用继承，「has-a」用组合；深层继承（超过 2 层）通常说明该拆成组合。`[O3]`

### 7.7 `object` 与常见基类

| 基类 | 用途 | 依据 |
| --- | --- | --- |
| `object` | 所有类的根 | `[O2]` |
| `Exception` | 自定义异常（第 16 章） | `[O2]` |
| `ABC` | 抽象基类（第 19 章） | `[O2]` |
| 内置类型 | 子类化 `str` / `list` 需谨慎（第 10 章） | `[O2]` |

## 8. 访问控制

**Python 没有真正的 private**，只有约定与名称改写。`[O3]`

### 8.1 单下划线：内部约定

```python
class Connection:
    def __init__(self):
        self._socket = "raw"     # 约定：内部使用，别从外部依赖

conn = Connection()
print(conn._socket)              # raw，能访问，只是「别这么做」
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| `_x` 只是约定 | 解释器不阻止访问 | `[O3]` |
| 用于「内部实现」 | API 不承诺稳定 | `[O3]` |
| `from module import *` 会跳过 | 部分工具遵守 | `[O3]` |

> 注意：单下划线不是安全机制；它表达「这是实现细节，改版可能变」。`[O3]`

### 8.2 双下划线：名称改写

```python
class Secret:
    def __init__(self):
        self.__token = "x"

    def reveal(self):
        return self.__token

s = Secret()
print(s.reveal())               # x
print(sorted(vars(s)))          # ['_Secret__token']（实测）
try:
    print(s.__token)
except AttributeError as error:
    print(type(error).__name__) # AttributeError（实测）
print(s._Secret__token)         # x，改写后仍可访问
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `__x` 被改写为 `_类名__x` | 编译期完成 | `[O3]` |
| 目的是避免子类属性冲突 | 不是访问控制 | `[O3]` |
| `_类名__x` 仍可访问 | 所以不是私有 | `[O3]` |
| 双前后下划线（`__x__`）不改写 | 保留给语言机制 | `[O3]` |

```python
class BaseToken:
    def __init__(self):
        self.__token = "base"

class ChildToken(BaseToken):
    def __init__(self):
        super().__init__()
        self.__token = "child"

ct = ChildToken()
print(sorted(vars(ct)))                    # ['_BaseToken__token', '_ChildToken__token']（实测）
print(ct._BaseToken__token, ct._ChildToken__token)   # base child（实测）
```

> 注意：名称改写让父子类的同名「私有」属性互不覆盖，这是它的真实用途；不要把它当安全边界。`[O3]`

### 8.3 双前后下划线：语言保留

```python
class Demo:
    def __init__(self):
        pass

print(hasattr(Demo, "__init__"), hasattr(Demo, "__dict__"))   # True True
```

| 名字 | 用途 | 依据 |
| --- | --- | --- |
| `__init__` / `__repr__` / `__eq__` | 特殊方法（第 14 章） | `[O2]` |
| `__dict__` / `__class__` / `__mro__` | 内置属性 | `[O2]` |
| `__x__` 自定义 | 不要发明 | `[O3]` |

> 注意：自定义 `__xxx__` 可能与未来语言特性冲突，且会让工具误判；PEP 8 明确不要发明。`[O3]`

### 8.4 真正的封装怎么做

| 手段 | 效果 | 依据 |
| --- | --- | --- |
| 单下划线 | 约定 | `[O3]` |
| 双下划线 | 防子类冲突 | `[O3]` |
| `__slots__` | 限制可加属性 | `[O2]` |
| `property` | 读写拦截（第 15 章） | `[O2]` |
| 只读属性 / 返回副本 | 防止外部改内部状态 | `[O3]` |

> 注意：想要「改值必须走校验」，用 `property`；想要「不能加字段」，用 `__slots__`；两者都不是安全隔离。`[O2]`

## 9. 常见操作

### 9.1 内置属性速查

| 属性 | 含义 | 实测值示例 | 依据 |
| --- | --- | --- | --- |
| `__name__` | 类名 | `Point` | `[O2]` |
| `__qualname__` | 限定名（含外层） | `Point` | `[O7]` |
| `__module__` | 定义所在模块 | `__main__` | `[O2]` |
| `__doc__` | 类 docstring 或 `None` | 字符串 | `[O2]` |
| `__dict__` | 类命名空间（mappingproxy） | 只读映射 | `[O2]` |
| `__bases__` | 直接基类元组 | `(object,)` | `[O2]` |
| `__mro__` | 方法解析顺序 | `(...)` | `[O2]` |
| `__class__` | 实例所属类 | `Point` | `[O2]` |

```python
print(Point.__name__, Point.__bases__[0].__name__, Point.__module__, Point.__qualname__)
# Point object __main__ Point（实测）
print(sorted(vars(Point).keys())[:6])
# ['__dict__', '__doc__', '__init__', '__module__', '__repr__', '__weakref__']（实测前 6 项）
```

**`__dict__` 是只读映射**：

```python
try:
    Point.__dict__["kind"] = "x"
except TypeError as error:
    print(type(error).__name__)   # TypeError（实测）
```

> 注意：类 `__dict__` 是 `mappingproxy`，不能直接改；要改类属性用 `setattr(类, 名, 值)`。`[O2]`

### 9.2 `type()`

```python
p = Point(1, 2)
print(type(p).__name__)        # Point
print(type(p) is Point)        # True
print(type(Point).__name__)    # type
```

| 用法 | 返回 | 依据 |
| --- | --- | --- |
| `type(obj)` | 对象的类型 | `[O4]` |
| `type(name, bases, dict)` | 新类（动态创建） | `[O4]` |
| `type(obj) is X` | 精确类型，不含子类 | `[O4]` |

> 注意：业务判断用 `isinstance` 而非 `type(...) is`，详见第 09 章。`[O3]`

### 9.3 `isinstance()`

```python
class Point3D(Point):
    pass

print(isinstance(Point3D(1, 2), Point))     # True，认继承
print(isinstance(Dyn(1, 2), Point))         # True（实测）
print(isinstance(1, (int, float)))          # True，元组表示「任意一个」
```

| 参数 | 说明 | 依据 |
| --- | --- | --- |
| `obj` | 任意对象 | `[O4]` |
| `classinfo` | 类、元组、联合类型 | `[O4]` |
| 返回 | `bool` | `[O4]` |

### 9.4 `issubclass()`

```python
print(issubclass(Dyn, Point))   # True（实测）
print(issubclass(Dyn, str))     # False（实测）
print(issubclass(bool, int))    # True，bool 是 int 子类
```

| 事实 | 依据 |
| --- | --- |
| 参数必须是类，否则 `TypeError` | `[O4]` |
| 支持元组 | `[O4]` |
| 认继承链 | `[O4]` |

### 9.5 `dir()`

```python
p = Point(1, 2)
print("kind" in dir(p), "move" in dir(p), "x" in dir(p))   # True True True（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 返回名字列表 | 含实例、类、父类、object | `[O4]` |
| 已排序 | 便于阅读 | `[O4]` |
| 不等于 `__dict__` | 后者只有当前层 | `[O4]` |

### 9.6 `vars()`

```python
print(vars(p))          # {'x': 1, 'y': 2}
print(vars(Point)["kind"])   # point（实测）
```

| 调用 | 返回 | 依据 |
| --- | --- | --- |
| `vars(obj)` | 实例 `__dict__` | `[O4]` |
| `vars(cls)` | 类 `__dict__`（mappingproxy） | `[O4]` |
| 无 `__dict__` 的对象 | `TypeError` | `[O4]` |

### 9.7 `getattr` / `setattr` / `hasattr` / `delattr`

```python
p = Point(1, 2)
print(getattr(p, "x"))               # 1
print(getattr(p, "nope", "default")) # default（实测）

setattr(p, "z", 9)
print(p.z, hasattr(p, "z"))          # 9 True（实测）

delattr(p, "z")
print(hasattr(p, "z"))               # False（实测）

try:
    getattr(p, "nope")
except AttributeError as error:
    print(type(error).__name__)      # AttributeError
```

| 函数 | 等价写法 | 依据 |
| --- | --- | --- |
| `getattr(o, "x")` | `o.x` | `[O4]` |
| `getattr(o, "x", d)` | `o.x`，失败返回 `d` | `[O4]` |
| `setattr(o, "x", v)` | `o.x = v` | `[O4]` |
| `hasattr(o, "x")` | `try: o.x; except AttributeError` | `[O4]` |
| `delattr(o, "x")` | `del o.x` | `[O4]` |

> 注意：名字来自外部输入时，必须用白名单校验后再 `getattr`/`setattr`；否则等于允许任意属性访问（含 `__class__` 等）。`[O4]`

### 9.8 反射使用边界

| 场景 | 是否推荐 | 依据 |
| --- | --- | --- |
| 框架/序列化 | ✅ | `[O4]` |
| 调试打印 `vars(obj)` | ✅ | `[O4]` |
| 业务逻辑里字符串拼属性名 | ❌ | `[O3]` |
| `getattr` 读用户输入 | ❌ 需白名单 | `[O4]` |

## 10. 综合示例：ToolCall 类

```python
"""第 08 章综合示例：类属性、类方法、静态方法协作。"""


class ToolCall:
    kind = "tool"

    def __init__(self, name, cost=0.0):
        self.name = name
        self.cost = cost

    def describe(self):
        return f"{self.kind}:{self.name} ({self.cost:.1f}s)"

    @classmethod
    def from_dict(cls, data):
        return cls(data["name"], data.get("cost", 0.0))

    @staticmethod
    def is_valid_name(name):
        return isinstance(name, str) and bool(name.strip())


calls = [ToolCall("search", 1.2), ToolCall.from_dict({"name": "cache", "cost": 0.1})]
for call in calls:
    print(call.describe())
print("总数:", len(calls))
print("名称合法:", ToolCall.is_valid_name("search"), ToolCall.is_valid_name(""))
```

本机实测输出：

```text
tool:search (1.2s)
tool:cache (0.1s)
总数: 2
名称合法: True False
```

**逐段说明**：

| 代码 | 用到的语法 | 依据 |
| --- | --- | --- |
| `kind = "tool"` | 类属性 | `[O1]` |
| `self.name = name` | 实例属性 | `[O1]` |
| `ToolCall.from_dict(...)` | 类方法替代构造器 | `[O1]` |
| `ToolCall.is_valid_name(...)` | 静态方法 | `[O1]` |
| `isinstance(name, str)` | 类型检查 | `[O4]` |

> 注意：`is_valid_name` 不依赖实例也不依赖类状态，写成静态方法的价值只是「归属清晰」；如果它将来需要读配置，就要改成类方法。`[O3]`

## 11. 注意事项与新手错误对照表

| 错误写法 / 操作 | 报错或现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `class = 1` | `SyntaxError` | 换名字 | `[O3]` |
| 类名小写 | 不符合 PEP 8 | `CapWords` | `[O3]` |
| 实例方法忘写 `self` | `TypeError: takes 0 positional arguments but 1 was given` | 第一个参数写 `self` | `[O1]` |
| 调用时手动传 `self` | 参数多一个 | `obj.m()` | `[O1]` |
| `__init__` 写 `return 1` | `TypeError` | 不返回值 | `[O2]` |
| 可变类属性存实例状态 | 所有实例共享 | 放 `self.xxx` | `[O1]` |
| `def __init__(self, items=[])` | 跨实例共享 | `items=None` 哨兵 | `[O1]` |
| 在方法里直接写类属性名 | `NameError` | `self.x` / `cls.x` | `[O2]` |
| 类体里用 `self` | `NameError` | 类体没有 `self` | `[O2]` |
| `p.kind = x` 想改类属性 | 只改了实例 | `Point.kind = x` | `[O2]` |
| 类方法里硬编码 `Point(...)` | 子类实例化错误 | `cls(...)` | `[O2]` |
| 静态方法里写 `cls` | `NameError` | 显式传类或写类名 | `[O1]` |
| `@classmethod` 忘写 `cls` | 调用时报参数错误 | 第一个参数 `cls` | `[O1]` |
| 多继承顺序写反 | `TypeError: Cannot create a consistent MRO` | 按「子类在前」排序 | `[O2]` |
| 以为 `super()` 是父类 | 多继承下行为不符预期 | 理解为「MRO 下一个」 | `[O2]` |
| 子类 `__init__` 不调 `super()` | 父类属性缺失 | 先 `super().__init__(...)` | `[O1]` |
| 菱形继承漏掉某层 `super()` | 链断，后面的类不执行 | 每层都调 | `[O2]` |
| `s.__token` 访问私有 | `AttributeError` | `s._Secret__token`（不推荐） | `[O3]` |
| 把双下划线当私有 | 仍可访问 | 它不是安全机制 | `[O3]` |
| 自定义 `__xxx__` | 可能与语言冲突 | 不要发明 | `[O3]` |
| `vars(obj)` 以为有全部属性 | 只有实例自己那层 | `dir(obj)` 看全部 | `[O4]` |
| `Point.__dict__["x"] = 1` | `TypeError` | `setattr(Point, "x", 1)` | `[O2]` |
| 用 `type(x) is C` 判断 | 漏掉子类 | `isinstance(x, C)` | `[O3]` |
| `getattr` 直接吃用户输入 | 任意属性访问 | 白名单 | `[O4]` |
| `hasattr` 判断方法存在就调用 | 参数不匹配仍 `TypeError` | 校验签名或 `try` | `[O4]` |
| 给实例打补丁改方法 | 只影响该实例，难排查 | 改类或重写 | `[O3]` |
| 深层继承 | 难维护 | 组合 | `[O3]` |
| 用继承表达「有一个」 | 语义错误 | 组合 | `[O3]` |
| `__slots__` 当访问控制 | 仍可访问已声明属性 | 它是内存优化 | `[O2]` |
| `__slots__` 子类忘了声明 | 子类又有 `__dict__` | 子类也声明 | `[O2]` |
| 类属性改后以为实例都变 | 被遮蔽的实例不变 | 理解遮蔽 | `[O2]` |
| `dir()` 里出现一堆 dunder | 正常 | 只看关心的名字 | `[O4]` |
| `isinstance(True, int)` 意外为真 | `bool` 是 `int` 子类 | 先判 `bool` | `[O2]` |
| 在 `__init__` 里联网/读大文件 | 构造变慢、难测 | 移到显式方法 | `[O3]` |
| 一个类上千行 | 职责过多 | 拆分 | `[O3]` |
| `self` 写成 `cls` 或 `s` | 可运行但违反约定 | 固定 `self` / `cls` | `[O3]` |

## 12. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 类名 `CapWords`，方法/属性 `snake_case` | PEP 8 | `[O3]` |
| `self` / `cls` 不改名 | 团队一致 | `[O3]` |
| `__init__` 只做赋值与校验 | 构造轻量可预测 | `[O1]` |
| 可变状态放实例属性 | 避免共享 | `[O1]` |
| 常量放类属性或模块常量 | 一份即可 | `[O3]` |
| 替代构造器用 `@classmethod` | `from_dict` / `from_json` | `[O1]` |
| 纯工具函数用 `@staticmethod` | 归属清晰 | `[O1]` |
| 优先组合而非深层继承 | 依赖显式 | `[O3]` |
| 用 `super()` 而非硬编码父类名 | 多继承正确 | `[O6]` |
| 公开 API 用简单属性，需要时再加 `property` | 别一上来写 getter/setter | `[O3]` |
| 每个公共类写 docstring | 说明职责与不变量 | `[O3]` |
| 为公共类写 `__repr__` | 调试友好（第 14 章） | `[O2]` |

**风格示范**：

```python
class ToolCall:
    """一次工具调用记录。

    不变量：name 非空，cost >= 0。
    """

    kind = "tool"

    def __init__(self, name: str, cost: float = 0.0) -> None:
        if not name:
            raise ValueError("name 不能为空")
        self.name = name
        self.cost = cost

    def __repr__(self) -> str:
        return f"ToolCall(name={self.name!r}, cost={self.cost!r})"

    @classmethod
    def from_dict(cls, data: dict) -> "ToolCall":
        """从字典构造。"""
        return cls(data["name"], data.get("cost", 0.0))
```

**安全边界**：

- 不要用 `getattr` / `setattr` 直接消费外部传入的属性名。
- 双下划线不是访问控制，敏感数据不要指望「命名私有」来保护。
- 类属性里不要放凭据；配置从环境变量读取（第 01 章）。

## 13. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[O1]` | python.org | https://docs.python.org/3.12/tutorial/classes.html | `class` 语法、实例化、`__init__`、`self`、实例/类属性、方法、继承、`super()`、多继承 |
| `[O2]` | python.org | https://docs.python.org/3.12/reference/datamodel.html | 类命名空间、属性查找、`__dict__`、`__mro__`、C3 线性化、`__slots__`、名称改写、内置属性 |
| `[O3]` | PEP 官方 | https://peps.python.org/pep-0008/ | 类名 `CapWords`、`self` / `cls` 约定、单下划线、不发明 dunder、组合优先 |
| `[O4]` | python.org | https://docs.python.org/3.12/library/functions.html | `type` / `isinstance` / `issubclass` / `dir` / `vars` / `getattr` / `setattr` / `hasattr` / `delattr` |
| `[O5]` | python.org | https://docs.python.org/3.12/reference/expressions.html | 属性引用、调用、绑定方法与 `__self__` |
| `[O6]` | PEP 官方 | https://peps.python.org/pep-3135/ | 零参 `super()` 的语义 |
| `[O7]` | PEP 官方 | https://peps.python.org/pep-3155/ | `__qualname__` 与限定名 |
| `[O8]` | GitHub 官方 | https://github.com/python/cpython/blob/main/Doc/tutorial/classes.rst | 官方教程源文件（`[O1]` 页脚 Show Source 指向） |
| `[O9]` | PEP 官方 | https://peps.python.org/pep-0020/ | The Zen of Python（显式、简单、可读） |

> **核对状态**：`[O1]` `[O3]` 与本章 `README.md` 已核对来源一致；其余链接按 `docs.python.org/3.12` 与 `peps.python.org` 官方结构整理，**本次未逐页直连复核**。文中「实测」结论均为本机 Python 3.12.8 运行结果。

## 14. 毕业自查清单

**能说清（概念层）**：

- [ ] 类与实例的关系，类体在什么时候执行
- [ ] `self` 到底是什么，为什么 `Class.m(obj)` 与 `obj.m()` 等价
- [ ] 实例属性与类属性的查找顺序与遮蔽规则
- [ ] 为什么可变类属性会被所有实例共享
- [ ] 实例方法 / 类方法 / 静态方法的第一个参数与用途差异
- [ ] `super()` 的准确含义（MRO 下一个，而非父类）
- [ ] MRO 的 C3 规则四条
- [ ] 菱形继承中 `super()` 为什么只调用一次 `A`
- [ ] 单下划线与双下划线的真实区别
- [ ] 名称改写后的实际属性名
- [ ] 类 `__dict__` 为什么不能直接赋值

**能写出（代码层）**：

- [ ] 一个带 `__init__`、实例属性、实例方法的类
- [ ] 用 `@classmethod` 写 `from_dict` 替代构造器
- [ ] 用 `@staticmethod` 写与实例无关的工具方法
- [ ] 用 `type("X", (Base,), {...})` 动态建类
- [ ] 一个两层继承 + `super().__init__()` 的结构
- [ ] 一个多继承 + 协作式 `super()` 的链
- [ ] 打印任意类的 `__mro__` 并解释顺序
- [ ] 用 `getattr/setattr/hasattr/delattr` 做安全的动态访问
- [ ] 用 `__slots__` 限制实例属性

**能判断（避坑层）**：

- [ ] 看到类里 `items = []` 能指出共享问题
- [ ] 看到 `p.kind = x` 能指出只改实例
- [ ] 看到 `@classmethod` 里硬编码类名能指出应改 `cls`
- [ ] 看到多继承顺序矛盾能预判 `TypeError`
- [ ] 看到 `s.__token` 访问能解释 `AttributeError` 与正确名字
- [ ] 看到 `Point.__dict__["x"] = 1` 能指出 `TypeError`
- [ ] 看到 `type(x) is C` 能指出漏掉子类
- [ ] 看到深层继承能提出用组合

**能跑通（验收层）**：

- [ ] 运行 `examples/class_demo.py` 并解释三行输出
- [ ] 把第 10 节示例存成文件运行，输出与文档一致
- [ ] 在 REPL 验证「可变类属性共享」与「实例遮蔽」
- [ ] 手写「基类 + 两个子类 + `from_dict` 类方法 + `__repr__`」的完整脚本

## 15. 下一章衔接

第 09 章 `对象的类型`：本章已经出现 `type(obj)`、`isinstance`、`__mro__` 三个悬念——

1. 为什么 `type(Point)` 是 `type`？类本身是什么的对象？
2. `isinstance` 与 `type(...) is` 在子类上为什么结论不同？
3. 成员查找到底按什么顺序走？`__getattr__` 在链条的哪个位置？

第 09 章会把「身份、类型、值」三件套和鸭子类型讲透；第 10 章再拆 `__new__` / `__init__` 的创建顺序，第 11 章讲 `__call__`。本章的 `__init__`、MRO、名称改写是这三章的地基。