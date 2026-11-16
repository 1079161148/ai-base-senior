# 12 元类 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把截图里的「类的创建过程、自定义元类、深入：元类的查找顺序、总结」逐条展开，并补上 `__prepare__`、`__init_subclass__`、`__set_name__`、元类冲突等必然遇到的内容，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测） |
| 前置 | 第 08–11、13–15、19 章（类、创建、可调用、装饰器、描述符、ABC） |
| 覆盖范围 | 类创建五步、`type` 默认元类、`type()` 动态建类、自定义元类、`__prepare__`、`__init_subclass__`、`__set_name__`、元类冲突、元类查找顺序 |
| 明确不覆盖 | 装饰器实现（13）、描述符协议（15）、ABC 用法（19）、`__call__` 控制实例化（10） |
| 学完验收 | 能画出「类创建的五个步骤」、能说清元类查找顺序、能判断该不该用元类（见第 14 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Mn]` `` 指向第 13 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果。

**推荐顺序**：

```text
1 类是怎么被创建的（第 1 节）→ 五步链路
2 type 是默认元类（第 2 节）  → 三级对象模型
3 type() 动态建类（第 3 节）  → 三参数
4 自定义元类（第 4 节）      → __new__ / __init__
5 四个扩展钩子（第 5 节）    → __prepare__ / __new__ / __init_subclass__ / __set_name__
6 元类查找顺序（第 6 节）    → 类属性、元类属性、__call__
7 元类冲突（第 7 节）
8 与 ABC 的关系（第 8 节）
9 什么时候不该用（第 9 节）  → 总结
10 综合示例（第 10 节）
11 注意事项（第 11 节）      → 30 条错误对照
```

**与 README 的分工**：README 给结论与边界，本文件负责机制穷举与判定。冲突时以本文件为准。

```py
class Dog:
    pass


# 等效于
class Dog(metaclass=type):
    pass


# 等效于
Dog = type("Dog", (), {})

# 等效于
Dog = type.__call__(type, "Dog", (), {})
```
也就是说，class 关键字只是语法糖，底层仍然是通过 type() 创建类。

## 1. 类是怎么被创建的

### 1.1 五步链路

```text
class C(Base, metaclass=M):
    x = 1
    def m(self): ...

1 确定命名空间：调用 M.__prepare__(name, bases) 得到类体命名空间
2 执行类体：x = 1、def m 依次写入该命名空间
3 确定元类：显式 metaclass=M → 否则取基类的元类 → 都没有则 type
4 创建类对象：M.__new__(M, name, bases, namespace)
5 初始化类对象：M.__init__(cls, name, bases, namespace)
最终把类对象绑定到名字 C
```

| 步骤 | 谁执行 | 依据 |
| --- | --- | --- |
| 1 准备命名空间 | 元类 `__prepare__` | `[M2]` `[M3]` |
| 2 执行类体 | 解释器 | `[M1]` |
| 3 确定元类 | 解释器 | `[M1]` |
| 4 创建类 | 元类 `__new__` | `[M1]` |
| 5 初始化类 | 元类 `__init__` | `[M1]` |

### 1.2 类体先执行，类对象后生成

```python
class Demo:
    print("类体执行")
    value = 1

# 输出：类体执行
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 类体是代码块 | 执行一次，产出命名空间 | `[M1]` |
| 命名空间是 dict | 3.x 默认普通 dict | `[M3]` |
| 类对象在类体执行后才出现 | 类体里引用自身类名会 `NameError` | `[M1]` |

```python
try:
    class Bad:
        me = Bad     # 类还没创建完
except NameError as error:
    print(type(error).__name__)   # NameError
```

> 注意：类体里不能引用「正在定义的类名」，因为类对象还没绑定；需要延后引用时用方法体或字符串。

### 1.3 `metaclass=` 是给解释器的指令

```python
class Meta(type):
    pass

class C(metaclass=Meta):
    pass

print(type(C).__name__)   # Meta
print([c.__name__ for c in type(C).__mro__])   # ['Meta', 'type', 'object']（实测）
```

| 写法 | 结果 | 依据 |
| --- | --- | --- |
| 不写 `metaclass` | 元类是 `type` | `[M1]` |
| 基类已有元类 | 继承基类的元类 | `[M1]` |
| 显式 `metaclass=M` | 必须是所有基类元类的子类 | `[M1]` |

## 2. `type` 是默认元类

### 2.1 三级对象模型

```text
实例        type(obj)        → 类
类          type(Cls)        → 元类（默认 type）
元类        type(type)       → type（自指）
```

```python
class Tool:
    pass

tool = Tool()
print(type(tool).__name__)     # Tool
print(type(Tool).__name__)     # type
print(type(type).__name__)     # type（实测）
print(type(type) is type)      # True（实测）
```

| 层级 | 提问 | 答案 | 依据 |
| --- | --- | --- | --- |
| 实例 | 我是谁造的 | 类 | `[M1]` |
| 类 | 我是谁造的 | 元类 | `[M1]` |
| 元类 | `type` 是谁造的 | `type` 自己 | `[M1]` |

### 2.2 `type` 同时是函数与类

| 用法 | 形态 | 返回 | 依据 |
| --- | --- | --- | --- |
| `type(obj)` | 单参数 | 对象的类型 | `[M6]` |
| `type(name, bases, dict)` | 三参数 | 新建的类 | `[M6]` |
| `isinstance(x, type)` | 类对象 | `True` | `[M6]` |

> 注意：`type` 既是内置函数名，又是所有类的默认元类；这两种身份在「三参数调用」处合流——用元类创建类。`[M1]`

## 3. 用 `type()` 动态创建类

```python
def run(self, argument):
    return self.name + ":" + argument

DynamicTool = type("DynamicTool", (), {"name": "search", "run": run})
print(DynamicTool.__name__)                 # DynamicTool
print(DynamicTool.__bases__[0].__name__)    # object（实测）
print(DynamicTool().run("AI"))              # search:AI（实测）
print(type(DynamicTool).__name__)           # type（实测）
```

| 参数 | 含义 | 依据 |
| --- | --- | --- |
| `name` | 类名，成为 `__name__` | `[M6]` |
| `bases` | 基类元组，空元组等价 `(object,)` | `[M6]` |
| `namespace` | 属性与方法字典 | `[M6]` |

### 3.1 与 `class` 语句的等价关系

| `class` 写法 | `type()` 写法 | 依据 |
| --- | --- | --- |
| `class A: x = 1` | `type("A", (), {"x": 1})` | `[M1]` |
| `class A(B): pass` | `type("A", (B,), {})` | `[M1]` |
| `class A(metaclass=M)` | `M("A", (), {})` | `[M1]` |

```python
class Manual:
    label = "manual"

Generated = type("Generated", (), {"label": "generated"})
print(Manual().label, Generated().label)   # manual generated
```

### 3.2 动态建类的真实用途

| 用途 | 说明 | 依据 |
| --- | --- | --- |
| 字段由配置决定 | 运行时才知道属性名 | `[M1]` |
| ORM / 序列化框架 | 模型类由元数据生成 | `[M1]` |
| 测试替身 | 临时造一个类 | `[M6]` |
| 枚举式常量类 | 批量生成 | `[M6]` |

> 注意：`type()` 建的类默认 `__module__` 是调用方模块、方法用 `lambda` 会缺 `self` 与 docstring；业务代码优先 `class` 或 `types.new_class`（第 22 章）。`[M6]`

## 4. 自定义元类

### 4.1 最小写法

```python
class RegisterMeta(type):
    created = []

    def __new__(mcls, name, bases, namespace):
        cls = super().__new__(mcls, name, bases, namespace)
        mcls.created.append(name)
        return cls

class Index(metaclass=RegisterMeta):
    pass

class Query(metaclass=RegisterMeta):
    pass

print(RegisterMeta.created)          # ['Index', 'Query']（实测）
print(type(Query).__name__)          # RegisterMeta（实测）
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 继承 `type` | 元类必须是 `type` 的子类 | `[M1]` |
| `__new__` 第一个参数是 `mcls` | 元类本身（约定名） | `[M1]` |
| 必须 `super().__new__(mcls, name, bases, namespace)` | 真正创建类 | `[M1]` |
| 返回值就是类对象 | 忘记返回会得到 `None` | `[M1]` |

### 4.2 `namespace` 里有什么

```python
class NamespaceMeta(type):
    def __new__(mcls, name, bases, namespace):
        print("NS_KEYS", name, sorted(k for k in namespace if not k.startswith("__")))
        return super().__new__(mcls, name, bases, namespace)

class WithAttrs(metaclass=NamespaceMeta):
    first = 1
    second = 2

    def method(self):
        pass
```

实测输出：

```text
NS_KEYS WithAttrs ['first', 'method', 'second']
```

| 键 | 来源 | 依据 |
| --- | --- | --- |
| `first` / `second` | 类体赋值 | `[M1]` |
| `method` | 类体 `def` | `[M1]` |
| `__module__` / `__qualname__` | 解释器自动写入 | `[M1]` |
| `__doc__` | docstring（没有则缺省） | `[M1]` |

> 注意：`namespace` 是**可变 dict**，元类可以增删属性；但改完必须把同一个 dict（或副本）传给 `super().__new__`，否则类体定义丢失。`[M1]`

### 4.3 `__init__` 版

```python
class InitMeta(type):
    def __init__(cls, name, bases, namespace):
        super().__init__(name, bases, namespace)
        cls.label = f"meta:{name}"

class Tagged(metaclass=InitMeta):
    pass

print(Tagged.label)   # meta:Tagged
```

| 位置 | 适合做什么 | 依据 |
| --- | --- | --- |
| `__new__` | 改 namespace、决定返回哪个类 | `[M1]` |
| `__init__` | 给已创建的类补属性 | `[M1]` |

> 注意：`__new__` 与 `__init__` 都会被调用；只想改类属性时用 `__init__` 更直观，要在创建阶段干预则用 `__new__`。`[M1]`

### 4.4 `__prepare__`：控制类体命名空间

```python
class OrderedMeta(type):
    @classmethod
    def __prepare__(mcls, name, bases):
        return {}

    def __new__(mcls, name, bases, namespace):
        cls = super().__new__(mcls, name, bases, dict(namespace))
        cls.order = [key for key in namespace if not key.startswith("__")]
        return cls

class Ordered(metaclass=OrderedMeta):
    z = 1
    a = 2
    m = 3

print(Ordered.order)   # ['z', 'a', 'm']（实测）
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 必须 `@classmethod` | 元类方法，收 `mcls` | `[M3]` |
| 返回值被当作类体命名空间 | 默认是 dict | `[M3]` |
| 可以返回自定义映射 | 记录写入顺序等 | `[M3]` |
| 3.x 的 dict 已保序 | 返回 `{}` 就能拿到顺序 | `[M3]` |

> 注意：`__prepare__` 是 PEP 3115 引入的，正是为了让「记录字段声明顺序」这类需求不必依赖 `__new__` 里的事后分析。`[M3]`

## 5. 四个扩展钩子对比

| 钩子 | 定义在 | 触发时机 | 复杂度 | 依据 |
| --- | --- | --- | --- | --- |
| `__prepare__` | 元类 | 类体执行前 | 高 | `[M3]` |
| `__new__` / `__init__` | 元类 | 类创建时 | 高 | `[M1]` |
| `__init_subclass__` | 普通父类 | 子类创建后 | 低 | `[M1]` |
| `__set_name__` | 描述符 | 类创建时（每个描述符） | 低 | `[M1]` |

### 5.1 `__init_subclass__`：不需要元类的注册表

```python
class Base:
    registry = []

    def __init_subclass__(cls, **kwargs):
        super().__init_subclass__(**kwargs)
        Base.registry.append(cls.__name__)

class ChildA(Base):
    pass

class ChildB(Base):
    pass

print(Base.registry)   # ['ChildA', 'ChildB']（实测）
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 定义在父类的普通类方法 | 隐式 `classmethod` | `[M1]` |
| 每个子类创建时调用一次 | 自动收到 `cls` | `[M1]` |
| 能收类关键字参数 | `class C(Base, key="x")` | `[M1]` |

```python
class Registry:
    plugins = {}

    def __init_subclass__(cls, key=None, **kwargs):
        super().__init_subclass__(**kwargs)
        if key:
            Registry.plugins[key] = cls

class Search(Registry, key="search"):
    pass

class Cache(Registry, key="cache"):
    pass

print(sorted(Registry.plugins))   # ['cache', 'search']
```

> 注意：只要「子类创建时自动登记」，`__init_subclass__` 就够，不必上元类；它可读性更好、开销更小。`[M1]`

### 5.2 `__set_name__`：描述符自动得知自己的名字

```python
class Field:
    def __set_name__(self, owner, name):
        self.name = f"{owner.__name__}.{name}"

class Model:
    title = Field()
    body = Field()

print(Model.title.name, Model.body.name)   # Model.title Model.body（实测）
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 类创建时对所有描述符调用 | 自动传 owner 与属性名 | `[M1]` |
| 比在 `__init__` 里手写名字参数好 | 避免重复与拼错 | `[M1]` |
| 详细协议见第 15 章 | 这里是钩子视角 | 课程边界 |

## 6. 深入：元类的查找顺序

### 6.1 实例属性查找（不查元类）

```text
instance.attr
  1 数据描述符（type(instance) 的 MRO 上）
  2 instance.__dict__
  3 非数据描述符 / 类属性（type(instance) 的 MRO）
  4 __getattr__
```

| 步骤 | 依据 |
| --- | --- |
| 数据描述符优先 | `[M1]` |
| 再到实例字典 | `[M1]` |
| 再到类与 MRO | `[M1]` |
| 最后 `__getattr__` | `[M1]` |

### 6.2 类属性查找（会查元类）

```text
Cls.attr
  1 type(Cls)（元类）的 MRO 上的数据描述符
  2 Cls.__dict__
  3 Cls.__mro__（父类链）
  4 type(Cls).__mro__（元类链，含 type / object）
  5 type(Cls).__getattr__
```

```python
class MetaWithAttr(type):
    meta_only = "from-meta"

class Demo(metaclass=MetaWithAttr):
    pass

print(Demo.meta_only)   # from-meta（实测）
```

| 顺序 | 说明 | 依据 |
| --- | --- | --- |
| 先类自身 | `Demo.__dict__` | `[M1]` |
| 再父类 | `Demo.__mro__` | `[M1]` |
| 最后元类 | `type(Demo).__mro__` | `[M1]` |

```python
class MetaWithAttr(type):
    meta_only = "from-meta"

class Demo(metaclass=MetaWithAttr):
    meta_only = "from-class"

print(Demo.meta_only)   # from-class，类自己优先
```

> 注意：「类找不到再去元类找」是类属性独有的；实例属性永远不看元类。这是两条不同的查找链，别混。`[M1]`

### 6.3 元类方法查找与 `__call__`

```text
Cls(args)
  → type(Cls).__mro__ 里找 __call__
  → 默认 type.__call__ → Cls.__new__ → Cls.__init__
```

| 查找对象 | 起点 | 依据 |
| --- | --- | --- |
| `Cls.run()`（实例方法） | `Cls.__mro__` | `[M2]` |
| `Cls(...)`（调用类） | `type(Cls).__mro__` | `[M1]` |
| `Cls.run`（不绑定） | `Cls.__mro__` | `[M2]` |

> 注意：元类 `__call__` 控制「类被调用」（即实例化），普通类 `__call__` 控制「实例被调用」；两者同名不同层（第 10、11 章）。`[M1]`

### 6.4 元类上的描述符

```python
class MetaDesc(type):
    @property
    def summary(cls):
        return f"class:{cls.__name__}"

class WithMetaDesc(metaclass=MetaDesc):
    pass

print(WithMetaDesc.summary)   # class:WithMetaDesc
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 元类上的 `property` 作用于类访问 | `Cls.summary` 走元类描述符 | `[M1]` |
| 实例访问不受影响 | 实例不查元类 | `[M1]` |
| 这让「类级只读属性」成为可能 | 框架常用 | `[M1]` |

### 6.5 一张速查表

| 表达式 | 查找链 | 命中示例 | 依据 |
| --- | --- | --- | --- |
| `obj.x` | 实例 → 类 MRO → `__getattr__` | 实例属性 | `[M1]` |
| `Cls.x` | 类 → 类 MRO → 元类 MRO | 类属性 / 元类属性 | `[M1]` |
| `Cls()` | 元类 MRO 找 `__call__` | `type.__call__` | `[M1]` |
| `Cls.__mro__` | 类自带 | 元组 | `[M1]` |
| `type(Cls).__mro__` | 元类链 | `(Meta, type, object)` | `[M1]` |

## 7. 元类冲突

```python
class Meta1(type):
    pass

class Meta2(type):
    pass

class A1(metaclass=Meta1):
    pass

class B1(metaclass=Meta2):
    pass

try:
    class C1(A1, B1):
        pass
except TypeError as error:
    print(type(error).__name__, "metaclass conflict" in str(error))
    # TypeError True（实测）
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 子类元类必须是所有基类元类的子类 | 否则冲突 | `[M1]` |
| 冲突在类定义时爆 | 不是实例化时 | `[M1]` |
| 解决方式一 | 派生共同元类 `class Meta3(Meta1, Meta2)` | `[M1]` |
| 解决方式二 | 减少元类使用，改用 `__init_subclass__` | `[M1]` |

```python
class Meta3(Meta1, Meta2):
    pass

class C2(A1, B1, metaclass=Meta3):
    pass

print(type(C2).__name__)   # Meta3
```

> 注意：每引入一个元类，就多一条「继承时必须兼容」的约束；这是「元类不宜多用」的直接原因。`[M2]`

## 8. 元类与 ABC

```python
import abc

class Tool(abc.ABC):
    @abc.abstractmethod
    def run(self, argument):
        """执行。"""

print(type(abc.ABC).__name__)   # ABCMeta（实测）
print(type(Tool).__name__)      # ABCMeta（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `ABCMeta` 是元类 | 继承 `type` | `[M4]` |
| ABC 能阻止实例化靠它 | 创建类时收集 `__abstractmethods__` | `[M4]` |
| 你不需要自己写 | 用 `abc.ABC` 即可 | `[M4]` |
| 与元类冲突 | ABC 与自定义元类混用要兼容 `ABCMeta` | `[M1]` |

> 注意：`class X(abc.ABC, metaclass=MyMeta)` 会与 `ABCMeta` 冲突，除非 `MyMeta` 继承 `ABCMeta`。详见第 19 章。`[M4]`

## 9. 总结：什么时候不该用元类

| 需求 | 首选方案 | 理由 | 依据 |
| --- | --- | --- | --- |
| 子类创建时登记 | `__init_subclass__` | 更轻、更显式 | `[M1]` |
| 描述符知道自己的名字 | `__set_name__` | 专为此设计 | `[M1]` |
| 给类加方法/属性 | 类装饰器 | 显式、可组合 | `[M2]` |
| 控制实例化 | `__new__` / `__init__` | 对象级已够 | `[M1]` |
| 修改类体字段顺序 | `__prepare__` | 少数场景才需要 | `[M3]` |
| 强制接口 | `abc.ABC` / `Protocol` | 现成方案 | `[M4]` |
| 以上都不行 | 元类 | 最后手段 | `[M1]` |

**判断口诀**：

```text
能用模块级注册表 → 不用类
能用 __init_subclass__ → 不用元类
能用类装饰器 → 不用元类
必须改「类创建过程本身」→ 才用元类
```

> 注意：元类的问题不是「难写」，而是「隐式」——读代码的人必须知道元类存在，才能理解类为什么多出属性。这是显式优于隐式的典型场景。`[M5]` `[M8]`

## 10. 综合示例：插件注册表

```python
"""第 12 章综合示例：元类在类创建时登记插件。"""


class PluginMeta(type):
    registry = {}

    def __new__(mcls, name, bases, namespace):
        cls = super().__new__(mcls, name, bases, namespace)
        key = namespace.get("key")
        if key:
            mcls.registry[key] = cls
        return cls


class Plugin(metaclass=PluginMeta):
    key = None

    def run(self, payload):
        raise NotImplementedError


class SearchPlugin(Plugin):
    key = "search"

    def run(self, payload):
        return f"search:{payload}"


class CachePlugin(Plugin):
    key = "cache"

    def run(self, payload):
        return f"cache:{payload}"


print("注册表:", sorted(PluginMeta.registry))
print("执行:", PluginMeta.registry["search"]().run("AI"))
```

本机实测输出：

```text
注册表: ['cache', 'search']
执行: search:AI
```

**逐段说明**：

| 代码 | 用到的机制 | 依据 |
| --- | --- | --- |
| `PluginMeta(type)` | 自定义元类 | `[M1]` |
| `namespace.get("key")` | 读取类体里声明的键 | `[M1]` |
| `mcls.registry[key] = cls` | 类创建时登记 | `[M1]` |
| `base = Plugin` 不登记 | `key` 为 `None` | `[M1]` |
| 从注册表取类并实例化 | 运行时按名分发 | `[M1]` |

> 注意：`Plugin` 自身 `key = None` 所以不登记；如果写成 `key = ""`，建议用 `if key:` 而不是 `if key is not None:`，避免空字符串被登记。`[M5]`

**同样的功能用 `__init_subclass__` 更短**：

```python
class Plugin:
    registry = {}

    def __init_subclass__(cls, key=None, **kwargs):
        super().__init_subclass__(**kwargs)
        if key:
            Plugin.registry[key] = cls

class SearchPlugin(Plugin, key="search"):
    pass
```

| 对比 | 元类 | `__init_subclass__` |
| --- | --- | --- |
| 代码量 | 多 | 少 |
| 能否改类体 | 能 | 不能 |
| 可读性 | 隐式 | 显式（类定义上就有 `key=`） |
| 依据 | `[M1]` | `[M1]` |

## 11. 注意事项与新手错误对照表

| 错误写法 / 操作 | 报错或现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 元类不继承 `type` | `TypeError: metaclass must be a subclass of type` | `class M(type)` | `[M1]` |
| `__new__` 忘 `return` | 类变成 `None` | 返回 `super().__new__(...)` | `[M1]` |
| `super().__new__(...)` 漏 `mcls` | `TypeError` | `super().__new__(mcls, name, bases, ns)` | `[M1]` |
| 漏传 `namespace` | 类体定义丢失 | 原样透传 | `[M1]` |
| 在 `__new__` 里改 `namespace` 后又新建 dict | 修改未生效 | 传同一 dict 或先改再传 | `[M1]` |
| 用 `lambda` 当类方法 | 缺 `self` | 命名函数 | `[M6]` |
| 元类里做 I/O | 导入期变慢/失败 | 移到显式函数 | `[M5]` |
| 元类里抛裸 `Exception` | 信息不可操作 | 具体异常 + 说明 | `[M5]` |
| 多继承混用元类 | `metaclass conflict` | 派生共同元类 | `[M1]` |
| 与 `abc.ABC` 混用 | 元类冲突 | 元类继承 `ABCMeta` | `[M4]` |
| 以为 `type(C)` 是 `type` | 自定义元类时为 `Meta` | 打印确认 | `[M1]` |
| 以为实例属性会查元类 | 找不到 | 只有类属性查元类 | `[M1]` |
| 在 `__init_subclass__` 里忘 `super()` | 别的钩子不生效 | 先调 `super().__init_subclass__(**kwargs)` | `[M1]` |
| `__init_subclass__` 写成 `staticmethod` | 拿不到 `cls` | 普通方法（隐式 classmethod） | `[M1]` |
| `__prepare__` 忘 `@classmethod` | `TypeError` | 加装饰器 | `[M3]` |
| 用元类做「自动注册一切」 | 调试困难 | 显式注册 / 装饰器 | `[M5]` |
| 用元类替代类装饰器 | 过度设计 | 类装饰器 | `[M2]` |
| 元类里改 `__bases__` | 不可预期 | 在 `__new__` 前决定 bases | `[M1]` |
| 元类属性与类属性同名 | 类属性优先 | 换名字 | `[M1]` |
| 把元类实例当普通对象用 | 混淆层级 | 记住三级模型 | `[M1]` |
| `type("X", (), {})` 后忘记设 `__module__` | 调试信息错 | 显式设置 | `[M6]` |
| 动态类的 `__qualname__` 不对 | 序列化/日志异常 | 显式设置 | `[M6]` |
| 元类 `__call__` 与实例 `__call__` 混 | 控制层级错 | 区分对象 | `[M1]` |
| 在元类 `__new__` 里访问 `cls.__name__` | 未创建完 | 用 `name` 参数 | `[M1]` |
| 元类依赖导入顺序 | 随机失败 | 避免导入期副作用 | `[M5]` |
| 静态检查器不认元类 | 类型报错 | 补 `# type: ignore` 或注解 | `[M5]` |
| 元类改 `__dict__` 后实例行为异常 | 描述符未重新处理 | 改 namespace 再创建 | `[M1]` |
| `__set_name__` 在元类里手动调 | 重复调用 | 交给解释器 | `[M1]` |
| 子类继承自定义元类后忘记 `key` | 注册表缺项 | 在子类声明 `key` | `[M1]` |
| 注册表用可变类属性跨测试污染 | 测试互相影响 | 提供 `clear()` | `[M5]` |

## 12. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 默认不用元类 | 先问「装饰器够不够」 | `[M5]` |
| 注册用 `__init_subclass__` | 显式且轻 | `[M1]` |
| 字段命名用 `__set_name__` | 免手写名字参数 | `[M1]` |
| 元类只做「类创建阶段」的事 | 不塞业务逻辑 | `[M5]` |
| 元类保持极薄 | 只注册/校验 | `[M5]` |
| 命名 `XxxMeta` | 一眼看出是元类 | `[M5]` |
| 元类里错误信息写清「哪个类、缺什么」 | 导入期排错 | `[M5]` |
| 不依赖导入顺序 | 避免随机失败 | `[M5]` |
| 与 ABC 混用时继承 `ABCMeta` | 避免冲突 | `[M4]` |
| 元类行为写进 docstring | 因为它不可见 | `[M5]` |

**风格示范**：

```python
class RegistryMeta(type):
    """把声明了 key 的子类登记到 registry。

    为什么用元类：需要在类创建时读取类体里的 key，并阻止重复注册。
    """

    registry: dict[str, type] = {}

    def __new__(mcls, name, bases, namespace):
        key = namespace.get("key")
        if key and key in mcls.registry:
            raise ValueError(f"重复注册: {key} 已被 {mcls.registry[key].__name__} 使用")
        cls = super().__new__(mcls, name, bases, namespace)
        if key:
            mcls.registry[key] = cls
        return cls
```

**边界**：

- 元类在导入期执行，**不能**做网络、读大文件、写数据库。
- 元类里的异常会变成 `ImportError` 的根因，错误信息必须能定位到类。
- 元类对类型检查器不透明，公共库要补注解或提供 `Protocol`（第 20 章）。

## 13. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[M1]` | python.org | https://docs.python.org/3.12/reference/datamodel.html | 类创建步骤、元类、`__init_subclass__`、`__set_name__`、元类冲突、`type.__call__`、实例/类属性查找 |
| `[M2]` | python.org | https://docs.python.org/3.12/reference/compound_stmts.html | `class` 语句语法、`metaclass=`、装饰器语法 |
| `[M3]` | PEP 官方 | https://peps.python.org/pep-3115/ | `__prepare__` 与类体命名空间、现代元类写法 |
| `[M4]` | python.org | https://docs.python.org/3.12/library/abc.html | `ABCMeta` 是元类、抽象方法收集 |
| `[M5]` | PEP 官方 | https://peps.python.org/pep-0008/ | 命名、注释写「为什么」、简单优先 |
| `[M6]` | python.org | https://docs.python.org/3.12/library/functions.html | `type()` 三参数形式、`isinstance` |
| `[M7]` | GitHub 官方 | https://github.com/python/cpython/blob/main/Doc/reference/datamodel.rst | 官方语言参考源文件（`[M1]` 页脚 Show Source 指向） |
| `[M8]` | PEP 官方 | https://peps.python.org/pep-0020/ | The Zen of Python（显式、简单） |

> **核对状态**：`[M1]` `[M5]` 与本章 `README.md` 已核对来源一致；其余链接按 `docs.python.org/3.12` 与 `peps.python.org` 官方结构整理，**本次未逐页直连复核**。文中「实测」结论均为本机 Python 3.12.8 运行结果。

## 14. 毕业自查清单

**能说清（概念层）**：

- [ ] 类创建的五步，以及每步由谁执行
- [ ] 为什么 `type(type) is type`
- [ ] `type(obj)` 与 `type(Cls)` 分别返回什么
- [ ] 实例属性查找与类属性查找的链条差异
- [ ] 元类属性在什么情况下会被访问到
- [ ] 元类冲突的成因与两种解法
- [ ] `ABCMeta` 为什么是元类
- [ ] `__init_subclass__` / `__set_name__` / 类装饰器分别替代元类的哪种用法

**能写出（代码层）**：

- [ ] `type("X", (Base,), {...})` 动态建类并实例化
- [ ] 一个最小注册元类（`__new__` 收集）
- [ ] 用 `__init_subclass__` 实现同样的注册
- [ ] 用 `__prepare__` 记录类体字段顺序
- [ ] 用 `__set_name__` 让属性知道自己的名字
- [ ] 打印 `type(Cls).__mro__` 并解释
- [ ] 制造并修复一次 `metaclass conflict`

**能判断（避坑层）**：

- [ ] 看到元类只做注册能建议改 `__init_subclass__`
- [ ] 看到 `__new__` 忘 `return` 能指出类变 `None`
- [ ] 看到 `super().__new__` 漏 `namespace` 能指出类体丢失
- [ ] 看到元类里做 I/O 能指出导入期风险
- [ ] 看到 `class X(abc.ABC, metaclass=M)` 能预判冲突
- [ ] 看到用元类替代类装饰器能指出过度设计

**能跑通（验收层）**：

- [ ] 运行 `examples/metaclass_demo.py` 并解释「类的类型」一行
- [ ] 把第 10 节示例存成文件运行，输出与文档一致
- [ ] 在 REPL 验证 `type(type) is type`
- [ ] 手写「元类版注册表 + `__init_subclass__` 版」并对比代码量

## 15. 下一章衔接

第 13 章 `装饰器`：本章反复提到「类装饰器能替代元类」，下一章就把它讲透——`@` 的本质、堆叠顺序、`functools.wraps`、带参装饰器。

本章留下的伏笔：

1. 类装饰器与元类都能改类，但前者显式、后者隐式；第 13 章会给出判据。
2. `@abc.abstractmethod` 本身就是装饰器，它只是把函数标记进 `__abstractmethods__`（第 19 章）。
3. `@property` 是描述符（第 15 章），而描述符在类创建时正是被 `__set_name__` 与元类处理的对象。