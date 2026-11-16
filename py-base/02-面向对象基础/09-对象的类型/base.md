# 09 对象的类型 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把截图里的「对象的类型、`type()` 动态定义类、MRO、类中私有成员、成员查找顺序」逐条展开，并补上身份/值、鸭子类型、`__getattr__` 兜底等必然遇到的内容，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测） |
| 前置 | 第 08 章（类、实例、继承、MRO 初识） |
| 覆盖范围 | 身份/类型/值、`type()`、`__class__`、`isinstance`、`issubclass`、鸭子类型、`__mro__`、成员查找顺序、`type()` 动态建类、类中私有成员 |
| 明确不覆盖 | `__new__` 创建过程（10）、`__call__`（11）、元类实现（12）、ABC（19）、Protocol 与静态类型（20） |
| 学完验收 | 能说清 `isinstance` 与 `type(...) is` 的差别、能画出成员查找链、能判断一段访问会命中哪一层（见第 13 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Tn]` `` 指向第 12 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果。

**推荐顺序**：

```text
1 身份 / 类型 / 值（第 1 节）→ 三件套与 is / ==
2 对象的类型（第 2 节）      → type(obj)、__class__、类也是对象
3 类型检查（第 3 节）        → isinstance / issubclass / type is
4 鸭子类型（第 4 节）        → 按能力而非按类
5 MRO 与查找（第 5 节）      → __mro__、逐层查找、__getattr__ 兜底
6 动态建类（第 6 节）        → type(name, bases, dict)
7 类中私有成员（第 7 节）    → 单/双下划线在类型体系里的表现
8 成员查找顺序（第 8 节）    → 完整链条与速查
9 综合示例（第 9 节）
10 注意事项（第 10 节）      → 30 条错误对照
```

**与 README 的分工**：README 讲结论，本文件负责穷举与判定。冲突时以本文件为准。

## 1. 对象三要素：身份、类型、值

每个 Python 对象都有三个东西：**身份**（`id()`）、**类型**（`type()`）、**值**（`==` 比较的内容）。`[T1]`

```python
a = [1, 2]
b = a
c = [1, 2]

print(id(a) == id(b), id(a) == id(c))   # True False（实测）
print(a is b, a is c, a == c)           # True False True（实测）
```

| 要素 | 获取方式 | 比较方式 | 依据 |
| --- | --- | --- | --- |
| 身份 | `id(obj)` | `is` | `[T1]` |
| 类型 | `type(obj)` | `isinstance` / `is` | `[T1]` |
| 值 | 对象内容 | `==` | `[T4]` |

### 1.1 `is` 与 `==`

| 运算符 | 比较 | 适用 | 依据 |
| --- | --- | --- | --- |
| `is` | 身份（是不是同一个对象） | `is None`、单例 | `[T4]` |
| `==` | 值（内容是否相等） | 绝大多数业务判断 | `[T4]` |

```python
print([] is [], [] == [])       # False True
print(None is None, None == None)   # True True
print(1 is 1, 1000 is 1000)     # True True（小整数与常量折叠，别依赖）
```

> 注意：`is` 只应用于 `None`、`True`/`False`、哨兵对象；用它比数字或字符串，结果依赖实现细节。`[T3]` `[T4]`

### 1.2 `id()` 会复用

```python
first = object()
second = object()
print(id(first) == id(second))   # False，同时存在就不同
del first
# first 被回收后，其 id 可能被新对象复用
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 同一对象生命周期内 id 不变 | 可作为临时标识 | `[T1]` |
| 对象销毁后 id 可能复用 | 不能长期当唯一键 | `[T1]` |
| `id` 不是内存地址（语义上） | CPython 恰好是地址 | `[T1]` |

> 注意：不要把 `id()` 存进数据库或缓存当业务主键；它只在对象存活期间有效。`[T1]`

## 2. 对象的类型

### 2.1 `type(obj)`

```python
class ToolCall:
    def __init__(self, name):
        self.name = name

call = ToolCall("search")
print(type(call).__name__)      # ToolCall
print(type(call) is ToolCall)   # True
```

| 用法 | 返回 | 依据 |
| --- | --- | --- |
| `type(obj)` | 对象的类型（类） | `[T2]` |
| `type(obj).__name__` | 类型名字符串 | `[T2]` |
| `type(name, bases, dict)` | 动态创建类 | `[T2]` |

### 2.2 `obj.__class__`

```python
print(call.__class__ is ToolCall)   # True
print(call.__class__.__name__)      # ToolCall
```

| 途径 | 说明 | 依据 |
| --- | --- | --- |
| `type(obj)` | 最可靠，直接问解释器 | `[T2]` |
| `obj.__class__` | 走属性查找，可被覆盖 | `[T1]` |
| 选择 | 类型判断用 `isinstance`，展示用 `type(obj).__name__` | `[T3]` |

> 注意：`obj.__class__` 是普通属性，代理对象或刻意赋值的实例可能返回别的值；`type(obj)` 不会。`[T1]`

### 2.3 类也是对象

```python
print(type(ToolCall))            # <class 'type'>
print(type(ToolCall) is type)    # True
print(isinstance(type, type))    # True（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 类本身是对象 | 有 id、有类型 | `[T1]` |
| 类的类型是 `type` | `type(ToolCall) is type` | `[T2]` |
| `type` 自身也是 `type` 的实例 | 自指，元类的起点 | `[T2]` |
| 元类在第 12 章 | 这里只需知道「类也是对象」 | 课程边界 |

```python
print(type(type).__name__, type(type) is type)   # type True（实测）
```

> 注意：`type(type) is type` 为真，说明 `type` 是它自己的类型；自定义元类就是 `type` 的子类（第 12 章）。`[T2]`

## 3. 类型检查

### 3.1 `type(...) is`

```python
print(type(True) is int)     # False（实测）
print(type(True) is bool)    # True
```

| 特点 | 说明 | 依据 |
| --- | --- | --- |
| 精确匹配 | 不看继承 | `[T2]` |
| 写法 | `type(x) is SomeClass` | `[T2]` |
| 风险 | 子类实例被判为「不是」 | `[T3]` |

### 3.2 `isinstance()`

```python
class Base:
    pass

class Child(Base):
    pass

print(isinstance(Child(), Base))      # True，认继承
print(isinstance(Child(), (Base, str)))   # True，元组表示「任一」
print(isinstance(True, int))          # True（实测）
```

| 特点 | 说明 | 依据 |
| --- | --- | --- |
| 认继承链 | 沿 `__mro__` 判断 | `[T2]` |
| 支持元组 | 任一匹配即真 | `[T2]` |
| 支持协议/ABC 虚拟子类 | 第 19、20 章 | `[T2]` |
| PEP 8 推荐 | 类型判断用它 | `[T3]` |

### 3.3 `issubclass()`

```python
print(issubclass(Child, Base))    # True
print(issubclass(Child, str))     # False
print(issubclass(bool, int))      # True（实测）
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 第一个参数必须是类 | 传实例会 `TypeError` | `[T2]` |
| 支持元组 | 任一即可 | `[T2]` |
| 只看类关系 | 不看实例 | `[T2]` |

### 3.4 `bool` 是 `int` 的子类（重点）

```python
print(issubclass(bool, int))       # True（实测）
print(isinstance(True, int))       # True（实测）
print(type(True) is int)           # False（实测）
```

| 后果 | 说明 |
| --- | --- |
| `isinstance(True, int)` 为真 | 布尔会被当成整数 |
| 类型分发要先判 `bool` | 否则 `True` 被归为 `int` |
| `True + True == 2` | 第 03 章已见 |

```python
def describe_type(value):
    if isinstance(value, bool):     # 必须先判 bool
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, str):
        return "str"
    return type(value).__name__

print([describe_type(v) for v in [True, 3, "a", 1.5, None]])
# ['bool', 'int', 'str', 'float', 'NoneType']（实测）
```

> 注意：类型分发时把 `bool` 放在 `int` 之前，是最容易漏的一步；顺序反了不会报错，只会静默分错。`[T1]`

### 3.5 三种判断怎么选

| 目的 | 写法 | 依据 |
| --- | --- | --- |
| 是否某种能力 | `hasattr` / 直接调用 | `[T2]` |
| 是否某类或其子类 | `isinstance(x, C)` | `[T3]` |
| 是否严格等于某类 | `type(x) is C`（少用） | `[T2]` |
| 类之间关系 | `issubclass(A, B)` | `[T2]` |
| 调试展示 | `type(x).__name__` | `[T2]` |

> 注意：业务代码优先「按能力判断」；只有确实需要类型约束（如参数校验）时才用 `isinstance`。`[T3]`

## 4. 鸭子类型

**鸭子类型**：不关心对象是什么类，只关心它「能不能做某件事」——「走起来像鸭子、叫起来像鸭子，就是鸭子」。`[T1]`

```python
class Duck:
    def __len__(self):
        return 3

print(len(Duck()))       # 3（实测）
print(bool(Duck()))      # True，用 __len__ 判真值（实测）
print(hasattr(Duck(), "__len__"))   # True（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 只需实现协议方法 | 不需要继承特定基类 | `[T1]` |
| 标准库大量使用 | `len` / `iter` / `+` 都按协议分发 | `[T1]` |
| 运行时才暴露缺失 | 缺方法到调用时才报错 | `[T1]` |
| 静态检查靠 Protocol | 第 20 章 | `[T7]` |

### 4.1 常见协议

| 协议 | 需要实现 | 支持语法 | 依据 |
| --- | --- | --- | --- |
| 长度 | `__len__` | `len(x)` | `[T1]` |
| 可迭代 | `__iter__` | `for`、`list(x)` | `[T1]` |
| 上下文管理 | `__enter__` / `__exit__` | `with` | `[T1]` |
| 可调用 | `__call__` | `x()`（第 11 章） | `[T1]` |
| 加法 | `__add__` | `x + y` | `[T1]` |

### 4.2 与继承的分工

| 方式 | 关系 | 何时用 | 依据 |
| --- | --- | --- | --- |
| 继承 | is-a | 明确共享实现 | `[T1]` |
| 鸭子类型 | can-do | 只要求行为 | `[T1]` |
| ABC | 显式声明接口 | 需要强制约束（第 19 章） | `[T2]` |
| Protocol | 静态结构匹配 | 类型检查（第 20 章） | `[T7]` |

> 注意：鸭子类型让代码灵活，但错误会推迟到运行时；关键路径要补测试，或改用 ABC/Protocol 把约束显式化。`[T1]`

## 5. MRO 与方法查找

### 5.1 `__mro__`

```python
class Base:
    attr = "base"

class Child(Base):
    attr = "child"

print([item.__name__ for item in Child.__mro__])   # ['Child', 'Base', 'object']（实测）
print(Child.__mro__[1].__name__)                   # Base（实测）
```

| 属性 | 类型 | 依据 |
| --- | --- | --- |
| `__mro__` | tuple | `[T1]` |
| `mro()` | list（方法） | `[T1]` |
| `__bases__` | 直接基类元组 | `[T1]` |

### 5.2 成员查找的完整顺序

```text
1 实例 __dict__            （obj.__dict__）
2 类 __dict__              （type(obj).__dict__）
3 父类链（__mro__ 依次）
4 __getattr__ 兜底          （常规查找全部失败后才调用）
5 仍失败 → AttributeError
```

```python
class Base:
    attr = "base"

class Child(Base):
    attr = "child"

ch = Child()
print(ch.attr)          # child（类 dict 命中）（实测）
ch.attr = "instance"
print(ch.attr)          # instance（实例 dict 命中）（实测）
del ch.attr
print(ch.attr)          # child（回到类 dict）（实测）
```

| 步骤 | 命中对象 | 依据 |
| --- | --- | --- |
| 1 | 实例属性 | `[T1]` |
| 2 | 类属性 | `[T1]` |
| 3 | 父类属性 | `[T1]` |
| 4 | `__getattr__` 返回值 | `[T1]` |
| 5 | 抛 `AttributeError` | `[T1]` |

### 5.3 `__getattr__` 兜底

```python
class Fallback:
    def __getattr__(self, name):
        return f"fallback:{name}"

print(Fallback().missing)    # fallback:missing（实测）
```

| 钩子 | 调用时机 | 依据 |
| --- | --- | --- |
| `__getattr__` | **常规查找失败后**才调用 | `[T1]` |
| `__getattribute__` | 每次属性访问都先调用 | `[T1]` |
| `__setattr__` | 每次赋值 | `[T1]` |

> 注意：`__getattr__` 不要写成「什么都返回」，否则 `hasattr` 永远为真、拼错的属性名永远不报错。`[T3]`

### 5.4 私有成员与 MRO

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

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 名称改写发生在定义类时 | 与查找顺序无关 | `[T3]` |
| 父子同名私有属性互不覆盖 | 名字不同 | `[T3]` |
| 改写名仍可访问 | 不是安全机制 | `[T3]` |

> 注意：这正是「双下划线用于避免子类冲突」的场景；但不要据此认为数据被保护了。`[T3]`

### 5.5 元类在链条之外

| 层级 | 谁负责 | 依据 |
| --- | --- | --- |
| 实例属性查找 | 实例 → 类 → MRO | `[T1]` |
| 类属性查找（类作为对象） | 类 → 元类 → 元类 MRO | `[T1]` |
| 类被调用 | 元类 `__call__`（第 10、12 章） | `[T1]` |

> 注意：`Child.attr` 找不到时，会去 `type(Child)`（即元类）找；日常几乎遇不到，但这是「类也是对象」的必然结果。`[T1]`

## 6. `type()` 动态定义类

```python
class Base:
    def hello(self):
        return "base"

Dyn = type("Dyn", (Base,), {"label": "dyn", "hello": lambda self: "dyn"})
obj = Dyn()
print(Dyn.__name__, Dyn.__bases__[0].__name__)   # Dyn Base
print(obj.label, obj.hello())                    # dyn dyn
print(isinstance(obj, Base))                     # True
```

| 参数 | 说明 | 依据 |
| --- | --- | --- |
| `name` | 类名 | `[T2]` |
| `bases` | 基类元组 | `[T2]` |
| `dict` | 类体内容 | `[T2]` |

| `class` 写法 | `type()` 写法 | 依据 |
| --- | --- | --- |
| `class Dyn(Base): label = "dyn"` | `type("Dyn", (Base,), {"label": "dyn"})` | `[T2]` |
| 方法直接 `def` | 函数写进 dict | `[T2]` |

```python
Plain = type("Plain", (), {})
print(Plain.__name__, Plain.__bases__[0].__name__)   # Plain object
print(type(Plain).__name__)                          # type
```

> 注意：`type()` 建的类没有 `__module__` 推断、方法也没有 docstring 归属；框架用它做「运行时生成」，业务代码优先 `class`。`[T3]`

## 7. 类中的私有成员

### 7.1 单下划线

```python
class Connection:
    def __init__(self):
        self._socket = "raw"

print(Connection()._socket)   # raw，能访问
```

| 规则 | 依据 |
| --- | --- |
| 只是「内部使用」约定 | `[T3]` |
| 解释器不阻止 | `[T3]` |
| `import *` 时被跳过 | `[T3]` |

### 7.2 双下划线名称改写

```python
class Secret:
    def __init__(self):
        self.__token = "x"

    def reveal(self):
        return self.__token

s = Secret()
print(s.reveal())              # x
print(sorted(vars(s)))         # ['_Secret__token']（实测）
print(s._Secret__token)        # x，改写名可访问

try:
    print(s.__token)
except AttributeError as error:
    print(type(error).__name__)   # AttributeError（实测）
```

| 规则 | 依据 |
| --- | --- |
| `__x` → `_类名__x`，编译期完成 | `[T3]` |
| 不作用于 `__x__` 形式 | `[T3]` |
| 目的是避免子类冲突 | `[T3]` |
| 可在 `vars()` 里看到真实名字 | `[T1]` |

### 7.3 在子类中的表现

```python
class BaseToken:
    def __init__(self):
        self.__token = "base"

class ChildToken(BaseToken):
    def __init__(self):
        super().__init__()
        self.__token = "child"

ct = ChildToken()
print(sorted(vars(ct)))    # ['_BaseToken__token', '_ChildToken__token']（实测）
```

| 现象 | 原因 |
| --- | --- |
| 父子各有一份 | 改写后的名字不同 |
| 子类无法「覆盖」父类私有 | 名字不在同一空间 |
| 需要真正独立状态时有用 | 避免意外共享 |

### 7.4 它不是访问控制

| 误以为 | 实际 | 依据 |
| --- | --- | --- |
| `__x` 外部不能访问 | `_类名__x` 可访问 | `[T3]` |
| 双下划线 = private | 只是名称改写 | `[T3]` |
| 能保护敏感数据 | 不能，需加密/权限 | `[T3]` |

> 注意：真正的封装靠「不暴露 + 返回副本 + `property` 校验」，不靠命名。`[T3]`

## 8. 成员查找顺序（速查）

### 8.1 一张表记住

| 你的代码 | 命中位置 | 结果 | 依据 |
| --- | --- | --- | --- |
| `obj.attr`（实例有） | 实例 `__dict__` | 实例值 | `[T1]` |
| `obj.attr`（实例无、类有） | 类 `__dict__` | 类值 | `[T1]` |
| `obj.attr`（类无、父类有） | MRO 上层 | 父类值 | `[T1]` |
| 都没有，有 `__getattr__` | 钩子 | 钩子返回值 | `[T1]` |
| 都没有，无钩子 | — | `AttributeError` | `[T1]` |
| `obj.method()` | 类 `__dict__` 找到函数 → 绑定 | 自动传 `self` | `[T1]` |
| `Cls.attr`（类作为对象） | 类 → 元类 → 元类 MRO | — | `[T1]` |
| `s.__x`（类内定义） | 名字已改写 | 查不到 → `AttributeError` | `[T3]` |

### 8.2 判断四步

```text
1 写成实例属性了吗？（self.x = / obj.x =）
   有 → 命中实例
2 类里定义了吗？（类体里赋值 / def）
   有 → 命中类
3 父类里有吗？沿 __mro__ 依次找
   有 → 命中父类
4 定义了 __getattr__ 吗？
   有 → 调它；没有 → AttributeError
```

> 注意：第 1 步的「写成实例属性」只看有没有赋值，与赋值语句在方法里的位置无关（与第 06 章的 `UnboundLocalError` 是同一类「编译期分类」思想）。`[T1]`

### 8.3 与 `dir()` / `vars()` 的关系

```python
class Demo:
    class_attr = 1
    def __init__(self):
        self.instance_attr = 2
    def method(self):
        pass

d = Demo()
print(vars(d))                      # {'instance_attr': 2}
print("class_attr" in dir(d))       # True
print("method" in dir(d))           # True
print("instance_attr" in vars(Demo))# False
```

| 函数 | 范围 | 依据 |
| --- | --- | --- |
| `vars(obj)` | 只有实例这一层 | `[T2]` |
| `vars(cls)` | 只有类这一层 | `[T2]` |
| `dir(obj)` | 实例 + 类 + 父类 + object | `[T2]` |

## 9. 综合示例：类型分发与查找

```python
"""第 09 章综合示例：类型判断、MRO 与鸭子类型。"""


def describe_type(value):
    if isinstance(value, bool):      # bool 必须先判
        return "bool"
    if isinstance(value, int):
        return "int"
    if isinstance(value, str):
        return "str"
    return type(value).__name__


class ToolCall:
    def __init__(self, name):
        self.name = name


call = ToolCall("search")
print([describe_type(v) for v in [True, 3, "a", 1.5, None]])
print("精确类型:", type(call) is ToolCall, type(call).__name__)
print("MRO:", [item.__name__ for item in ToolCall.__mro__])
print("鸭子类型:", hasattr(call, "name"))
```

本机实测输出：

```text
['bool', 'int', 'str', 'float', 'NoneType']
精确类型: True ToolCall
MRO: ['ToolCall', 'object']
鸭子类型: True
```

**逐段说明**：

| 代码 | 用到的语法 | 依据 |
| --- | --- | --- |
| `isinstance(value, bool)` 先判 | `bool` 是 `int` 子类 | `[T1]` |
| `type(value).__name__` | 兜底显示类型名 | `[T2]` |
| `type(call) is ToolCall` | 精确类型 | `[T2]` |
| `ToolCall.__mro__` | 查找顺序 | `[T1]` |
| `hasattr(call, "name")` | 能力判断 | `[T2]` |

> 注意：`type(call) is ToolCall` 在这里为真，但换成 `ToolCall` 的子类实例就为假；生产判断统一用 `isinstance`。`[T3]`

## 10. 注意事项与新手错误对照表

| 错误写法 / 操作 | 报错或现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `type(x) is C` 判子类 | 漏判 | `isinstance(x, C)` | `[T3]` |
| `x is 1` / `x is "a"` | 结果依赖实现 | `x == 1` | `[T4]` |
| `x == None` | 能跑但不规范 | `x is None` | `[T3]` |
| 用 `id()` 当业务主键 | 对象销毁后复用 | 用业务 ID | `[T1]` |
| 先判 `int` 再判 `bool` | `True` 被归为 `int` | `bool` 放最前 | `[T1]` |
| 以为类不是对象 | 无法解释 `type(C)` | 类是对象 | `[T1]` |
| `type(C)` 以为返回 `object` | 实际是 `type` | 记住元类 | `[T2]` |
| `obj.__class__` 当绝对可靠 | 可被覆盖 | 用 `type(obj)` | `[T1]` |
| `isinstance(x, "str")` | `TypeError` | 传类不是字符串 | `[T2]` |
| `issubclass(obj, C)` | `TypeError` | 传类 | `[T2]` |
| `hasattr` 判断后直接调用 | 参数不匹配仍错 | 校验签名或 `try` | `[T2]` |
| `__getattr__` 返回一切 | `hasattr` 永远真 | 只处理特定名字 | `[T3]` |
| 依赖 `dir()` 顺序做逻辑 | 只是排序展示 | 用 `in` 判断 | `[T2]` |
| `vars(obj)` 以为有全部属性 | 只有实例层 | `dir()` 看全部 | `[T2]` |
| `vars(instance)` 改值绕过 | 能改但不推荐 | 走方法 | `[T3]` |
| `s.__x` 访问私有 | `AttributeError` | 改写名（不推荐） | `[T3]` |
| 把双下划线当私有 | 仍可访问 | 它不是访问控制 | `[T3]` |
| `type()` 建类后用 `lambda` 当方法 | 缺 `self`、无元数据 | 用 `class` / 命名函数 | `[T3]` |
| 动态建类后忘记设 `__module__` | 调试信息错 | 显式设置 | `[T2]` |
| 用字符串拼属性名读用户输入 | 任意访问 | 白名单 | `[T3]` |
| 多继承顺序导致 MRO 冲突 | `TypeError` | 调整顺序 | `[T1]` |
| 以为 `isinstance` 只看直接父类 | 实际看整条 MRO | 认全部祖先 | `[T2]` |
| 用 `is` 比较类型 | 应 `is` 比较类对象本身 | 可，但优先 `isinstance` | `[T4]` |
| `bool` 当纯 `int` 处理 | 序列化/分支出错 | 显式判断 | `[T1]` |
| `None` 当空字符串 | 语义不同 | 分开判断 | `[T3]` |
| 鸭子类型不做校验 | 运行时才炸 | 测试或 Protocol | `[T7]` |
| 以为 `__mro__` 可改 | 它是只读 tuple | 改继承定义 | `[T1]` |
| `C.mro()` 与 `C.__mro__` 混用 | 一个函数一个元组 | 按需选 | `[T1]` |
| 元类查找当实例查找 | 层级不同 | 区分「类作对象」 | `[T1]` |
| `hasattr(x, "__call__")` 当 `callable` | 语义近似但不等价 | 用 `callable` | `[T2]` |

## 11. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 类型判断用 `isinstance` | 认继承 | `[T3]` |
| `is` 只用于单例 | `None` / 哨兵 | `[T3]` |
| 按能力设计接口 | 鸭子类型优先 | `[T1]` |
| 需要约束时用 ABC/Protocol | 显式化 | `[T7]` |
| 类型分发先判 `bool` | 避免 `int` 吞掉 | `[T1]` |
| 调试打印 `type(x).__name__` | 比 `print(x)` 信息多 | `[T2]` |
| 不在业务逻辑里做长串 `isinstance` | 用多态 | `[T3]` |
| `__getattr__` 只兜底明确的前缀 | 避免吞错 | `[T3]` |
| 动态属性名走白名单 | 安全 | `[T3]` |
| 用 `dir()` 探索、`vars()` 排查 | 分工明确 | `[T2]` |

**风格与安全**：

- `isinstance(x, (int, float))` 比 `type(x) is int or type(x) is float` 更短更准。
- 反射读属性时先 `startswith` 白名单，再 `getattr`。
- 不要用 `__class__` 赋值来「改变类型」；需要转换就新建对象。

## 12. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[T1]` | python.org | https://docs.python.org/3.12/reference/datamodel.html | 对象身份/类型/值、`__class__`、`__mro__`、属性查找顺序、`__getattr__`、鸭子类型与协议、类的类型 |
| `[T2]` | python.org | https://docs.python.org/3.12/library/functions.html | `type()` 两种形态、`isinstance()`、`issubclass()`、`id()`、`dir()`、`vars()`、`hasattr`、`callable` |
| `[T3]` | PEP 官方 | https://peps.python.org/pep-0008/ | 用 `isinstance` 而非直接比类型、`is None`、单/双下划线约定、不发明 dunder |
| `[T4]` | python.org | https://docs.python.org/3.12/reference/expressions.html | `is` / `is not` / `==` 的语义与比较规则 |
| `[T5]` | python.org | https://docs.python.org/3.12/library/stdtypes.html | 内置类型、`bool` 与 `int` 的关系、真值测试 |
| `[T6]` | PEP 官方 | https://peps.python.org/pep-0285/ | `bool` 类型的引入与「`bool` 是 `int` 子类」的设计 |
| `[T7]` | PEP 官方 | https://peps.python.org/pep-0544/ | Protocol 与结构化子类型（静态检查，第 20 章） |
| `[T8]` | GitHub 官方 | https://github.com/python/cpython/blob/main/Doc/reference/datamodel.rst | 官方语言参考源文件（`[T1]` 页脚 Show Source 指向） |

> **核对状态**：`[T1]` `[T3]` 与本章 `README.md` 已核对来源一致；其余链接按 `docs.python.org/3.12` 与 `peps.python.org` 官方结构整理，**本次未逐页直连复核**。文中「实测」结论均为本机 Python 3.12.8 运行结果。

## 13. 毕业自查清单

**能说清（概念层）**：

- [ ] 身份、类型、值三者的区别，以及 `is` / `==` 各自适用场景
- [ ] 为什么 `id()` 不能当长期唯一标识
- [ ] `type(obj)` 与 `obj.__class__` 的差别
- [ ] 为什么 `type(ToolCall)` 是 `type`
- [ ] `isinstance` 与 `type(...) is` 在子类上的差别
- [ ] 为什么 `isinstance(True, int)` 为真，类型分发时要注意什么
- [ ] 鸭子类型的含义，以及它与继承、ABC、Protocol 的分工
- [ ] 成员查找的五步顺序
- [ ] `__getattr__` 与 `__getattribute__` 的调用时机差异
- [ ] 双下划线名称改写在父子类中的表现

**能写出（代码层）**：

- [ ] 用 `isinstance` 写一个正确的类型分发函数（`bool` 在前）
- [ ] 用 `issubclass` 判断类关系
- [ ] 打印任意类的 `__mro__` 并解释
- [ ] 用 `type("X", (Base,), {...})` 动态建类并实例化
- [ ] 用 `hasattr` / `getattr` 做白名单式动态访问
- [ ] 用 `__getattr__` 实现「缺失属性兜底」并避免吞错
- [ ] 用 `vars()` / `dir()` 排查一个属性到底在哪层

**能判断（避坑层）**：

- [ ] 看到 `type(x) is C` 能指出漏掉子类
- [ ] 看到 `x is 1` 能指出不可靠
- [ ] 看到先判 `int` 再判 `bool` 能指出顺序错误
- [ ] 看到 `s.__token` 能解释 `AttributeError` 与改写名
- [ ] 看到 `__getattr__` 无条件返回值能指出会吞错
- [ ] 看到 `vars(obj)` 找类属性找不到能解释原因
- [ ] 看到 `getattr(obj, user_input)` 能指出安全风险

**能跑通（验收层）**：

- [ ] 运行 `examples/type_demo.py` 并解释 `类的类型: type`
- [ ] 把第 9 节示例存成文件运行，输出与文档一致
- [ ] 在 REPL 验证「实例遮蔽 → `del` 后回到类属性」
- [ ] 手写「三层继承 → 打印 MRO → 按 `isinstance` 分发」的脚本

## 14. 下一章衔接

第 10 章 `对象的创建过程`：本章确认了「类也是对象」，接着要回答——`ToolCall("search")` 这一行到底发生了什么？

1. 谁先执行：`__new__` 还是 `__init__`？
2. `__new__` 返回别的对象时，为什么 `__init__` 会被跳过？
3. 单例、对象池为什么必须重写 `__new__` 而不是 `__init__`？

第 10 章会把 `type.__call__ → __new__ → __init__` 这条链路拆开；本章的「类也是对象」「元类在链条之外」正是那条链路的前提。