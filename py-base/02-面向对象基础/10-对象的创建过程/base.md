# 10 对象的创建过程 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把截图里的「对象的创建过程 + 三个应用场景（单例、对象池/缓存、正整数带默认值回退）」逐条展开，并补上 `__new__`/`__init__` 的返回值、不可变类型子类化、元类位置等必然遇到的内容，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测） |
| 前置 | 第 08–09 章（类、实例、类型、MRO） |
| 覆盖范围 | `C(args)` 三步、`__new__`、`__init__`、返回值约束、不可变类型子类化、单例、对象池/缓存、默认值回退 |
| 明确不覆盖 | 元类实现（12）、`__call__`（11）、`pickle` 细节（22）、并发下的单例（28） |
| 学完验收 | 能说出创建顺序、能解释「返回非本类实例为什么跳过 `__init__`」、能写出三种缓存式创建（见第 12 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Nn]` `` 指向第 11 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果。

**推荐顺序**：

```text
1 创建过程总览（第 1 节）→ 三步链路
2 __new__（第 2 节）      → 创建、返回值、何时重写
3 __init__（第 3 节）     → 初始化、返回 None、参数一致
4 返回非本类实例（第 4 节）→ 为什么跳过 __init__
5 不可变类型子类化（第 5 节）→ int/str/tuple 必须在 __new__ 处理
6 三个应用场景（第 6 节）→ 单例、对象池、默认值回退
7 元类位置（第 7 节）     → type.__call__
8 综合示例（第 8 节）
9 注意事项（第 9 节）     → 28 条错误对照
```

**与 README 的分工**：README 讲顺序，本文件负责穷举场景与陷阱。冲突时以本文件为准。

## 1. 创建过程总览

### 1.1 三步链路

```text
C(args)
  ↓
type(C).__call__(C, args)     # 元类负责调度（第 12 章）
  ↓
C.__new__(C, args)            # 创建：返回实例
  ↓
C.__init__(instance, args)    # 初始化：返回 None
```

| 步骤 | 谁做 | 职责 | 依据 |
| --- | --- | --- | --- |
| 1 | 元类 `__call__` | 调度，串起后两步 | `[N1]` |
| 2 | `__new__` | 分配并返回实例 | `[N1]` |
| 3 | `__init__` | 给实例绑定属性 | `[N1]` |

### 1.2 顺序实测

```python
class Traced:
    def __new__(cls, name):
        print("NEW", name)
        return super().__new__(cls)

    def __init__(self, name):
        print("INIT", name)
        self.name = name

obj = Traced("search")
print("TRACED", isinstance(obj, Traced), obj.name)
```

实测输出：

```text
NEW search
INIT search
TRACED True search
```

| 结论 | 依据 |
| --- | --- |
| `__new__` 先，`__init__` 后 | `[N1]` |
| 两者收到同一批实参 | `[N1]`` |
| `__init__` 拿到的是 `__new__` 的返回值 | `[N1]` |

### 1.3 两个方法的分工

| 维度 | `__new__` | `__init__` |
| --- | --- | --- |
| 本质 | 静态方法（隐式收 `cls`） | 实例方法（收 `self`） |
| 职责 | 创建并返回实例 | 初始化已有实例 |
| 返回值 | 必须返回实例 | 必须返回 `None` |
| 能否省略 | 能（默认 `object.__new__`） | 能（默认 `object.__init__`） |
| 常见重写理由 | 单例、缓存、不可变类型 | 绑定属性、校验 |
| 依据 | `[N1]` | `[N1]` |

> 注意：`__new__` 的第一个参数是**类**，不是实例；所以它被称作「静态方法」，即使不用 `@staticmethod` 装饰。`[N1]`

## 2. `__new__`

### 2.1 定义与参数

```python
class Traced:
    def __new__(cls, name):
        instance = super().__new__(cls)   # 真正分配对象
        return instance

    def __init__(self, name):
        self.name = name

print(Traced("x").name)    # x
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 第一个参数是 `cls` | 当前类（可能是子类） | `[N1]` |
| 其余参数与 `__init__` 一致 | 调用方传几个就收几个 | `[N1]` |
| 必须调 `super().__new__(cls)` | 否则没有真正的实例 | `[N1]` |
| 不需要 `@staticmethod` | 解释器自动按静态方法处理 | `[N1]` |

### 2.2 必须返回实例

```python
class Weird:
    def __new__(cls):
        return 42          # 不是 cls 的实例

    def __init__(self):
        print("INIT_CALLED")

print("WEIRD", Weird())    # WEIRD 42（实测，INIT_CALLED 没有打印）
```

| 返回什么 | `__init__` 是否执行 | 依据 |
| --- | --- | --- |
| `cls` 的实例 | ✅ 执行 | `[N1]` |
| 其他类的实例 | ❌ 跳过 | `[N1]` |
| 非实例（`42` / `None` / 字符串） | ❌ 跳过 | `[N1]` |

> 注意：`__new__` 返回非本类实例时，Python 只返回该对象、不调用 `__init__`；这是「工厂式创建」的底层机制，也是很多「构造没生效」问题的根源。`[N1]`

### 2.3 `super().__new__(cls)` 的正确写法

```python
class Base:
    def __new__(cls, *args, **kwargs):
        return super().__new__(cls)

class Child(Base):
    def __new__(cls, *args, **kwargs):
        return super().__new__(cls, *args, **kwargs)   # 透传参数

print(type(Child()).__name__)    # Child
```

| 正确 | 错误 | 后果 | 依据 |
| --- | --- | --- | --- |
| `super().__new__(cls)` | `super().__new__()` | `TypeError` | `[N1]` |
| `super().__new__(cls, *args)` | `super().__new__(cls)` 丢参 | 父类收不到 | `[N1]` |
| 返回结果 | 忘记 `return` | 得到 `None` | `[N1]` |

> 注意：在 `__new__` 里忘记 `return`，`C()` 会得到 `None`，且不报错——这是最难查的一类。`[N1]`

### 2.4 什么时候才需要重写 `__new__`

| 场景 | 需要重写 | 依据 |
| --- | --- | --- |
| 单例 | ✅ | `[N1]` |
| 对象池 / 缓存 | ✅ | `[N1]` |
| 子类化不可变类型 | ✅ | `[N1]` |
| 普通业务类 | ❌ 只用 `__init__` | `[N1]` |
| 想「返回别的对象」 | ✅（但要清楚跳过 `__init__`） | `[N1]` |

> 注意：`__new__` 属于进阶手段；能用类方法工厂（`from_dict`）解决就别重写它，可读性更好。`[N2]`

### 2.5 只重写 `__new__` 时的多余参数

```python
class CachedInt:
    _cache = {}

    def __new__(cls, value, default=0):
        key = int(value) if str(value).lstrip("-").isdigit() else default
        if key in cls._cache:
            return cls._cache[key]
        instance = super().__new__(cls)
        instance.value = key
        cls._cache[key] = instance
        return instance

print(CachedInt(1).value)    # 1（实测同款）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 没写 `__init__` 时，多余实参被容忍 | CPython 对「只覆盖 `__new__`」的类有特例 | `[N1]` |
| 一旦写了 `__init__` | 参数必须对得上 | `[N1]` |

> 注意：这个特例容易让人误以为「参数随便传」；一旦你后来补了 `__init__`，原来的调用就会 `TypeError`。`[N1]`

## 3. `__init__`

### 3.1 初始化职责

```python
class ToolCall:
    def __init__(self, name, cost=0.0):
        self.name = name
        self.cost = cost

call = ToolCall("search", 1.2)
print(vars(call))    # {'name': 'search', 'cost': 1.2}
```

| 职责 | 说明 | 依据 |
| --- | --- | --- |
| 绑定属性 | `self.x = ...` | `[N1]` |
| 校验参数 | 非法就抛异常 | `[N2]` |
| 轻量计算 | 派生字段 | `[N1]` |
| 重 I/O | ❌ 不要 | `[N2]` |

### 3.2 必须返回 `None`

```python
class BadInit:
    def __init__(self):
        return 1

try:
    BadInit()
except TypeError as error:
    print(type(error).__name__)   # TypeError（实测）
```

| 写法 | 结果 | 依据 |
| --- | --- | --- |
| 不写 `return` | `None`，正常 | `[N1]` |
| `return` | `None`，正常 | `[N1]` |
| `return 1` | `TypeError` | `[N1]` |

### 3.3 与 `__new__` 的参数一致性

```python
class Traced:
    def __new__(cls, name):          # 收 name
        return super().__new__(cls)

    def __init__(self, name):        # 也收 name
        self.name = name
```

| 规则 | 依据 |
| --- | --- |
| 两个方法收到同一批实参 | `[N1]` |
| 签名不一致会在调用时报 `TypeError` | `[N1]` |
| 用 `*args, **kwargs` 透传可避免不一致 | `[N1]` |

> 注意：多继承下 `__new__` 的 `*args` 透传尤其重要，漏传会导致父类初始化缺参。`[N1]`

## 4. 返回非本类实例

### 4.1 行为与风险

```python
class Weird:
    def __new__(cls):
        return 42

print(Weird())        # 42（实测，没有 __init__ 调用）
```

| 行为 | 说明 | 依据 |
| --- | --- | --- |
| `__init__` 跳过 | 返回值不是 `cls` 实例 | `[N1]` |
| 类型不是 `Weird` | `isinstance(Weird(), Weird)` 为 `False` | `[N1]` |
| 调用方可能无感知 | 只在后续属性访问时炸 | `[N1]` |

> 注意：需要「返回别的对象」时，优先写类方法工厂（`from_dict` / `create`），语义清楚且不会让调用方误判类型。`[N2]`

### 4.2 合法用途

| 用途 | 说明 | 依据 |
| --- | --- | --- |
| 缓存命中返回已有实例 | 单例、对象池 | `[N1]` |
| 返回子类实例 | 工厂分发 | `[N1]` |
| 返回代理对象 | 框架层 | `[N1]` |

## 5. 不可变类型子类化

### 5.1 为什么必须在 `__new__` 处理

`int` / `str` / `tuple` 的**值在创建时就固定**，`__init__` 阶段改不了。`[N1]`

```python
class UpperStr(str):
    def __new__(cls, value):
        return super().__new__(cls, value.upper())

print(UpperStr("ab"))                 # AB（实测）
print(isinstance(UpperStr("ab"), str)) # True（实测）
```

| 类型 | 值在哪定 | 重写位置 | 依据 |
| --- | --- | --- | --- |
| `str` | `__new__` | `__new__` | `[N1]` |
| `int` | `__new__` | `__new__` | `[N1]` |
| `tuple` | `__new__` | `__new__` | `[N1]` |
| 普通类 | `__init__` | `__init__` | `[N1]` |

### 5.2 错误写法

```python
class BadStr(str):
    def __init__(self, value):
        self.value = value.upper()    # 改不了字符串本身

print(BadStr("ab"))       # ab，不是 AB
```

| 现象 | 原因 | 依据 |
| --- | --- | --- |
| 字符串值没变 | `str` 的值在 `__new__` 已定 | `[N1]` |
| 可能报参数错误 | `str.__init__` 不接受额外参数 | `[N1]` |

> 注意：`__init__` 里给不可变对象「赋值」只会新增属性，不会改变它的值；这是子类化内置类型最常见的误解。`[N1]`

### 5.3 子类化内置类型的其他注意点

| 注意点 | 说明 | 依据 |
| --- | --- | --- |
| `__slots__` 不生效 | 内置类型已有布局 | `[N1]` |
| 切片返回基类 | `UpperStr("ab")[0:1]` 是 `str`，需重写 `__getitem__` | `[N1]` |
| 运算返回基类 | `+` / `*` 返回 `str` | `[N1]` |
| 建议 | 能用组合就别继承内置类型 | `[N2]` |

## 6. 三个应用场景

### 6.1 单例模式

```python
class Singleton:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

print(Singleton() is Singleton())   # True（实测）
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 缓存放类属性 | 所有调用共享 | `[N1]` |
| `cls` 而不是 `Singleton` | 子类各自单例 | `[N1]` |
| `__init__` 会重复执行 | 返回的是 `cls` 实例 | `[N1]` |

**`__init__` 重复执行的坑**：

```python
class Singleton:
    _instance = None

    def __new__(cls, value):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._ready = False
        return cls._instance

    def __init__(self, value):
        if self._ready:
            return                  # 防重复初始化
        self.value = value
        self._ready = True

first = Singleton("a")
second = Singleton("b")
print(first is second, first.value)   # True a
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 单例的 `__init__` 每次调用都执行 | 因为返回的是 `cls` 实例 | `[N1]` |
| 后一次可能覆盖前一次状态 | 需要显式防重入 | `[N1]` |

> 注意：很多单例教程只写 `__new__`，漏掉 `__init__` 重复初始化；带参数的单例一定要加标志位。`[N1]`

**单例的替代方案**：

| 方案 | 优点 | 缺点 | 依据 |
| --- | --- | --- | --- |
| `__new__` 单例 | 类本身保证唯一 | 隐藏依赖、难测试 | `[N2]` |
| 模块级实例 | 最简单、Python 惯例 | 只在本模块唯一 | `[N2]` |
| 依赖注入 | 可测试、显式 | 需要传参 | `[N2]` |

> 注意：模块级对象（`settings = Settings()`）通常比 `__new__` 单例更 Pythonic；单例的主要问题是「隐藏全局状态」。`[N2]`

### 6.2 对象池 / 缓存

```python
class Pooled:
    _pool = {}

    def __new__(cls, key):
        if key not in cls._pool:
            cls._pool[key] = super().__new__(cls)
        return cls._pool[key]

    def __init__(self, key):
        self.key = key

print(Pooled("a") is Pooled("a"))   # True（实测）
print(Pooled("a") is Pooled("b"))   # False（实测）
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 键决定是否复用 | 同键返回同一实例 | `[N1]` |
| `__init__` 每次执行 | 会重复赋值（通常无害） | `[N1]` |
| 池会持续增长 | 需要淘汰策略 | `[N2]` |

**带上限的池**（避免无界增长）：

```python
class LimitedPool:
    _pool = {}
    _limit = 2

    def __new__(cls, key):
        if key in cls._pool:
            return cls._pool[key]
        if len(cls._pool) >= cls._limit:
            # 简单策略：直接新建，不入池
            return super().__new__(cls)
        instance = super().__new__(cls)
        cls._pool[key] = instance
        return instance

print(len(LimitedPool._pool))    # 0，类属性在定义时已建好
first = LimitedPool("a")
second = LimitedPool("b")
third = LimitedPool("c")
print(len(LimitedPool._pool), third is LimitedPool("c"))   # 2 False
```

| 策略 | 说明 | 依据 |
| --- | --- | --- |
| 不设上限 | 内存持续增长 | `[N2]` |
| 超限不缓存 | 简单可用 | `[N2]` |
| LRU 淘汰 | 更复杂，见第 22 章 | `[N2]` |

> 注意：对象池的实例会被长期持有，池里的对象不能依赖「用完即释放」的清理逻辑。`[N2]`

### 6.3 正整数带默认值回退

需求：像 `int()` 一样「解析失败就给默认值」，同时对常用范围做缓存（呼应 CPython 的整数缓存）。`[N1]`

```python
class CachedInt:
    _cache = {}

    def __new__(cls, value, default=0):
        try:
            key = int(value)
        except (TypeError, ValueError):
            key = default
        if -5 <= key <= 256 and key in cls._cache:
            return cls._cache[key]
        instance = super().__new__(cls)
        instance.value = key
        if -5 <= key <= 256:
            cls._cache[key] = instance
        return instance

    def __repr__(self):
        return f"CachedInt({self.value})"

print(CachedInt(1) is CachedInt(1))         # True（实测）
print(CachedInt("x") is CachedInt(0))       # True，回退到默认值 0（实测）
print(CachedInt(999) is CachedInt(999))     # False，超出缓存范围（实测）
```

| 设计点 | 说明 | 依据 |
| --- | --- | --- |
| `try/except` 回退 | 解析失败用默认值 | `[N1]` |
| 范围限制 | 只缓存常用区间 | `[N1]` |
| 缓存键 | 用解析后的值 | `[N1]` |
| 不可变语义 | 值在 `__new__` 定 | `[N1]` |

| 容易错的地方 | 后果 |
| --- | --- |
| `default` 不校验类型 | 缓存键可能是 `None` |
| 回退值也缓存 | 不同非法输入共享同一对象（可能非预期） |
| 缓存无上限 | 内存增长 |

> 注意：`int("x")` 本身抛 `ValueError`；「带默认值」是**你的 API** 的约定，不是 `int` 的行为（`int` 的 `default` 参数只用于 `int(str, base)` 之外的场景，实际上 `int()` 没有 `default` 参数）。`[N1]`

## 7. 与元类的关系

```text
调用 C(args)
  → type(C).__call__(C, args)     ← 元类的 __call__
      → C.__new__(C, args)
      → C.__init__(instance, args)
```

| 层级 | 负责 | 依据 |
| --- | --- | --- |
| 元类 `__call__` | 调度 `__new__` / `__init__` | `[N1]` |
| `__new__` | 创建 | `[N1]` |
| `__init__` | 初始化 | `[N1]` |

> 注意：想「控制实例化过程」有三个层次：`__new__`（对象级）、元类 `__call__`（类级）、装饰器（函数级）；按需选择，别都用元类。`[N1]`

## 8. 综合示例：服务注册表

```python
"""第 10 章综合示例：对象池式注册表。"""


class ServiceRegistry:
    _instances = {}

    def __new__(cls, name):
        if name not in cls._instances:
            instance = super().__new__(cls)
            instance.name = name
            instance.calls = 0
            cls._instances[name] = instance
        return cls._instances[name]

    def record(self):
        self.calls += 1
        return self.calls


first = ServiceRegistry("search")
second = ServiceRegistry("search")
print("同实例:", first is second, "调用:", first.record(), second.record(), first.calls)
```

本机实测输出：

```text
同实例: True 调用: 1 2 2
```

**逐段说明**：

| 代码 | 用到的机制 | 依据 |
| --- | --- | --- |
| `_instances = {}` | 类属性作为池 | `[N1]` |
| `__new__` 查池 | 命中直接返回 | `[N1]` |
| 未命中时初始化字段 | 在 `__new__` 里完成 | `[N1]` |
| `first is second` | 同一对象 | `[N1]` |
| `first.calls` 累加 | 状态共享 | `[N1]` |

> 注意：这里把 `name` / `calls` 放在 `__new__` 里初始化，是为了避免 `__init__` 每次调用重置状态；如果写在 `__init__` 里，`calls` 会被反复归零。`[N1]`

## 9. 注意事项与新手错误对照表

| 错误写法 / 操作 | 报错或现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `__new__` 忘记 `return` | 得到 `None` | 返回实例 | `[N1]` |
| `super().__new__()` 漏 `cls` | `TypeError` | `super().__new__(cls)` | `[N1]` |
| `__new__` 返回非实例 | `__init__` 被跳过 | 明确设计意图 | `[N1]` |
| `__init__` 返回值 | `TypeError` | 不返回 | `[N1]` |
| `__new__` / `__init__` 签名不一致 | 调用报错 | 参数对齐 | `[N1]` |
| 多继承 `__new__` 不透传参数 | 父类收不到 | `*args, **kwargs` | `[N1]` |
| 普通类重写 `__new__` | 无必要、易错 | 用 `__init__` | `[N2]` |
| 单例 `__init__` 未防重入 | 状态被重置 | 标志位 | `[N1]` |
| 单例用硬编码类名 | 子类不独立 | 用 `cls` | `[N1]` |
| 对象池无上限 | 内存增长 | 淘汰策略 | `[N2]` |
| 缓存键用原始输入 | 同值不同键 | 用解析后的值 | `[N1]` |
| 回退值也缓存 | 非法输入共享对象 | 只缓存合法值 | `[N1]` |
| 子类化 `str` 在 `__init__` 改值 | 值不变 | 在 `__new__` 处理 | `[N1]` |
| 子类化 `int` 忘记 `super().__new__(cls, value)` | 值丢失 | 传值给父类 | `[N1]` |
| 以为切片返回子类 | 返回基类 | 重写 `__getitem__` | `[N1]` |
| `__slots__` 加在内置类型子类 | 不生效 | 别加 | `[N1]` |
| 在 `__init__` 里做网络请求 | 构造慢、难测 | 移到显式方法 | `[N2]` |
| 构造里吞异常 | 隐藏错误 | 失败要快 | `[N2]` |
| 用 `__new__` 做参数校验 | 顺序反了 | 校验放 `__init__` | `[N1]` |
| 单例当全局配置 | 难测试 | 依赖注入 | `[N2]` |
| 多线程下单例竞争 | 可能创建两个 | 加锁（第 28 章） | `[N1]` |
| `pickle` 还原绕过 `__new__` | 状态缺失 | 实现 `__reduce__`（第 22 章） | `[N3]` |
| `copy.copy` 绕过构造 | 同上 | 同上 | `[N3]` |
| 以为 `__new__` 会调 `__init__` | 实际是元类调 | 理解为调度 | `[N1]` |
| `object()` 当哨兵 | 每次都是新对象 | 用模块级常量 | `[N2]` |
| 重写 `__new__` 后忘记 `__init__` 参数 | `TypeError` | 检查签名 | `[N1]` |
| 缓存对象可被外部修改 | 状态污染 | 返回副本或只读 | `[N2]` |
| 单例池跨测试污染 | 测试互相影响 | 提供重置方法 | `[N2]` |

## 10. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 普通类只写 `__init__` | 简单直接 | `[N1]` |
| `__init__` 只做赋值与校验 | 构造轻量可预测 | `[N2]` |
| 需要多构造方式用 `@classmethod` | 比 `__new__` 清晰 | `[N2]` |
| 需要缓存/唯一实例才用 `__new__` | 明确理由 | `[N1]` |
| 用 `cls` 而不是硬编码类名 | 支持子类 | `[N1]` |
| 单例加防重入标志 | 避免重复初始化 | `[N1]` |
| 对象池要有上限 | 防内存增长 | `[N2]` |
| 构造失败要快 | 非法参数立即抛 | `[N2]` |
| 单例优先用模块级对象 | Python 惯例 | `[N2]` |
| 缓存对象考虑不可变 | 防外部修改 | `[N2]` |

**风格示范**：

```python
class ToolCall:
    """普通类：只写 __init__。"""

    def __init__(self, name: str, cost: float = 0.0) -> None:
        if not name:
            raise ValueError("name 不能为空")
        self.name = name
        self.cost = cost

    @classmethod
    def from_dict(cls, data: dict) -> "ToolCall":
        return cls(data["name"], data.get("cost", 0.0))
```

**安全与边界**：

- 单例 / 对象池里的对象被长期持有，不要把敏感临时数据（令牌、密码）缓存进去。
- 多线程环境下的单例需要加锁，否则可能创建两个实例（第 28 章）。
- 缓存键不要直接用不可信的用户输入，先规范化。

## 11. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[N1]` | python.org | https://docs.python.org/3.12/reference/datamodel.html | `object.__new__` / `__init__` 语义、返回值约束、实例化协议、不可变类型子类化、元类 `__call__` |
| `[N2]` | PEP 官方 | https://peps.python.org/pep-0008/ | `super()` 与继承设计、注释写「为什么」、简单可读优先 |
| `[N3]` | python.org | https://docs.python.org/3.12/library/pickle.html | 反序列化可绕过常规创建路径、`__reduce__` |
| `[N4]` | GitHub 官方 | https://github.com/python/cpython/blob/main/Doc/reference/datamodel.rst | 官方语言参考源文件（`[N1]` 页脚 Show Source 指向） |
| `[N5]` | python.org | https://docs.python.org/3.12/reference/expressions.html | 调用语义、参数绑定 |
| `[N6]` | PEP 官方 | https://peps.python.org/pep-0020/ | The Zen of Python（显式、简单） |

> **核对状态**：`[N1]` `[N2]` 与本章 `README.md` 已核对来源一致；其余链接按 `docs.python.org/3.12` 与 `peps.python.org` 官方结构整理，**本次未逐页直连复核**。文中「实测」结论均为本机 Python 3.12.8 运行结果。

## 12. 毕业自查清单

**能说清（概念层）**：

- [ ] `C(args)` 的三步链路，以及谁负责调度
- [ ] `__new__` 与 `__init__` 的职责与返回值约束
- [ ] 为什么 `__new__` 返回非本类实例时 `__init__` 被跳过
- [ ] 为什么子类化 `int` / `str` / `tuple` 必须重写 `__new__`
- [ ] 单例为什么会导致 `__init__` 重复执行，怎么防
- [ ] 对象池与单例的区别
- [ ] 「带默认值回退」的解析与缓存顺序
- [ ] 元类 `__call__` 在链路中的位置

**能写出（代码层）**：

- [ ] 一个打印 `NEW` / `INIT` 顺序的类
- [ ] 一个 `__new__` 返回非实例的类，并解释现象
- [ ] `UpperStr(str)` 用 `__new__` 改值
- [ ] 单例（含防重复初始化的标志位）
- [ ] 对象池（同键同实例，不同键不同实例）
- [ ] `CachedInt`（解析失败回退默认值 + 范围缓存）
- [ ] 用 `@classmethod` 工厂替代 `__new__` 的写法

**能判断（避坑层）**：

- [ ] 看到 `__new__` 忘 `return` 能指出会得到 `None`
- [ ] 看到 `super().__new__()` 漏 `cls` 能指出 `TypeError`
- [ ] 看到单例只写 `__new__` 能指出 `__init__` 会重复
- [ ] 看到「在 `__init__` 里改 `str` 值」能指出无效
- [ ] 看到对象池无上限能指出内存风险
- [ ] 看到 `pickle.loads` 造对象能指出绕过了 `__new__`

**能跑通（验收层）**：

- [ ] 运行 `examples/creation_demo.py` 并解释三行输出顺序
- [ ] 把第 8 节示例存成文件运行，输出与文档一致
- [ ] 在 REPL 验证「`__new__` 返回 42 时 `__init__` 不执行」
- [ ] 手写「解析配置 → 失败回退默认值 → 常用值缓存」的完整类

## 13. 下一章衔接

第 11 章 `可调用对象`：对象已经能创建，接下来让实例「像函数一样被调用」——`obj(x)` 等价于 `type(obj).__call__(obj, x)`。

本章留下的伏笔：

1. 元类 `__call__` 负责实例化，而普通类的 `__call__` 负责「调用实例」，两者同名不同层，第 11 章会分开讲。
2. 单例、对象池也可以写成「可调用对象 + 内部缓存」，第 11 章会对比两种实现。
3. 第 13 章装饰器建立在「可调用对象 + 闭包」之上，本章的创建链路是它的前置。