# 15 描述符 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把截图里的「问题、描述符协议（术语/访问顺序/读写删/钩子）、解决问题、`@property`、应用场景（惰性计算、类型检查）」逐条展开，并补上 `__set_name__`、状态存储、与 `__getattribute__` 的关系，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测） |
| 前置 | 第 08、14 章（类、属性的读写、特殊方法） |
| 覆盖范围 | 描述符协议、数据/非数据描述符、访问顺序、读写删、`__set_name__`、`property`、`cached_property`、类型检查描述符 |
| 明确不覆盖 | `__getattr__` / `__getattribute__` 全量行为（14）、元类上的描述符（12）、`__slots__` 实现细节（14） |
| 学完验收 | 能画出属性查找四步、能解释 `obj.method` 的 `self` 来源、能写出校验描述符与惰性属性（见第 13 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Pn]` `` 指向第 12 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果。

**推荐顺序**：

```text
1 问题（第 1 节）        → 重复的校验/转换逻辑
2 描述符协议（第 2 节）  → 三个方法 + 两类描述符
3 访问顺序（第 3 节）    → 四步链条，谁遮蔽谁
4 读写删（第 4 节）      → 状态存哪、__set_name__
5 钩子与边界（第 5 节）  → 必须放类上
6 解决问题（第 6 节）    → 一处定义，多处复用
7 @property（第 7 节）   → 最常用的现成描述符
8 应用场景（第 8 节）    → 惰性计算、类型检查、ORM、单位转换
9 综合示例（第 9 节）
10 注意事项（第 10 节）  → 32 条错误对照
```

**与 README 的分工**：README 给结论与优先级，本文件负责机制与实现套路。冲突时以本文件为准。

## 1. 问题：重复的属性逻辑

### 1.1 手写校验的重复

```python
class User:
    def __init__(self):
        self._age = 0

    @property
    def age(self):
        return self._age

    @age.setter
    def age(self, value):
        if not isinstance(value, int):
            raise TypeError("age 需要 int")
        if value < 0:
            raise ValueError("age 不能为负")
        self._age = value
```

一个类还好；三个字段、五个类时：

| 问题 | 表现 | 依据 |
| --- | --- | --- |
| 重复代码 | 每个字段一套 getter/setter | `[P2]` |
| 规则分散 | 校验逻辑散落在各处 | `[P2]` |
| 易漏 | 新加字段忘加校验 | `[P2]` |
| 难统一 | 修改规则要改多处 | `[P2]` |

### 1.2 要抽象出什么

| 需求 | 抽象 |
| --- | --- |
| 「读取时做什么」 | 一个可复用的访问器 |
| 「写入时校验」 | 同上，带规则参数 |
| 「字段名」 | 自动获得，不手写 |
| 「一处定义多处使用」 | 类属性级别的复用 |

**描述符**就是「把属性访问本身变成一个对象」的机制。`[P2]`

## 2. 描述符协议

### 2.1 认识术语

| 术语 | 含义 | 例子 | 依据 |
| --- | --- | --- | --- |
| 描述符（descriptor） | 实现了 `__get__` / `__set__` / `__delete__` 任一的对象 | `Typed(int)` | `[P1]` |
| 受管属性（managed attribute） | 由描述符接管的属性 | `User.age` | `[P2]` |
| 宿主类（owner） | 描述符所在的类 | `User` | `[P2]` |
| `instance` | 访问该属性的实例（类访问时为 `None`） | `user` | `[P2]` |
| 数据描述符 | 定义了 `__set__` 或 `__delete__` | `property` | `[P1]` |
| 非数据描述符 | 只有 `__get__` | 普通函数 | `[P1]` |

### 2.2 三个协议方法

```python
class Descriptor:
    def __get__(self, instance, owner=None):
        """读取：x.attr 或 Cls.attr"""
        ...

    def __set__(self, instance, value):
        """写入：x.attr = value"""

    def __delete__(self, instance):
        """删除：del x.attr"""
```

| 方法 | 触发 | 参数 | 依据 |
| --- | --- | --- | --- |
| `__get__` | 读取 | `instance`（可能 `None`）、`owner` | `[P1]` |
| `__set__` | 赋值 | `instance`、新值 | `[P1]` |
| `__delete__` | `del` | `instance` | `[P1]` |

```python
class Logged:
    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__.get("_value")

    def __set__(self, instance, value):
        print("写入:", value)
        instance.__dict__["_value"] = value

class Tool:
    name = Logged()

tool = Tool()
tool.name = "search"
print("读取:", tool.name)
print("实例字典:", tool.__dict__)
```

实测输出：

```text
写入: search
读取: search
实例字典: {'_value': 'search'}
```

### 2.3 数据描述符 vs 非数据描述符

| 类型 | 定义 | 优先级 | 例子 | 依据 |
| --- | --- | --- | --- | --- |
| 数据描述符 | 有 `__set__` 或 `__delete__` | 高于实例字典 | `property` | `[P1]` |
| 非数据描述符 | 只有 `__get__` | 低于实例字典 | 函数、`classmethod` | `[P1]` |

```python
class DataDesc:
    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__.get("_d", "default")

    def __set__(self, instance, value):
        instance.__dict__["_d"] = value

class NonData:
    def __get__(self, instance, owner):
        return "nondata"

class Host:
    data = DataDesc()
    nondata = NonData()
    plain = "class-attr"

host = Host()
print("DESC_DEFAULT", host.data)
host.data = "x"
host.nondata = "instance-wins"
print("DESC_DATA_WINS", host.data, host.nondata)
```

实测输出：

```text
DESC_DEFAULT default
DESC_DATA_WINS x instance-wins
```

| 属性 | 赋值后读到 | 原因 | 依据 |
| --- | --- | --- | --- |
| `data`（数据描述符） | `x` | 描述符压过实例字典 | `[P1]` |
| `nondata`（非数据描述符） | `instance-wins` | 实例字典压过非数据描述符 | `[P1]` |

### 2.4 `__set_name__`：自动获得字段名

```python
class Named:
    def __set_name__(self, owner, name):
        self.name = f"{owner.__name__}.{name}"

    def __get__(self, instance, owner):
        return self.name

class Model:
    title = Named()

print(Model.title)   # Model.title（实测）
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 类创建时自动调用 | 每个描述符一次 | `[P8]` |
| 参数是 owner 与属性名 | 不用手写 | `[P8]` |
| 比 `__init__` 传名字好 | 不会拼错 | `[P8]` |

## 3. 访问顺序

### 3.1 完整四步

```text
obj.attr
  1 在 type(obj).__mro__ 中找数据描述符  → 调 __get__
  2 在 obj.__dict__ 中找               → 直接返回
  3 在 type(obj).__mro__ 中找非数据描述符或普通属性 → 调 __get__ 或直接返回
  4 都没有 → __getattr__（若有）→ 否则 AttributeError
```

| 步骤 | 依据 |
| --- | --- |
| 数据描述符最优先 | `[P1]` |
| 实例字典其次 | `[P1]` |
| 非数据描述符/类属性第三 | `[P1]` |
| `__getattr__` 兜底 | `[P1]` |

### 3.2 实例字典遮蔽非数据描述符

```python
class Plain:
    value = "class"

plain = Plain()
print(plain.value)      # class
plain.value = "instance"
print(plain.value)      # instance
print(Plain.value)      # class
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 实例赋值只写实例字典 | 不动类属性 | `[P1]` |
| 非数据描述符随后被遮蔽 | 读不到类上的值 | `[P1]` |
| 数据描述符不会被遮蔽 | 写操作走 `__set__` | `[P1]` |

### 3.3 类访问时 `instance` 为 `None`

```python
print(type(Host.data).__name__)   # DataDesc（实测）
```

| 访问 | `instance` | 常见处理 | 依据 |
| --- | --- | --- | --- |
| `obj.attr` | 实例 | 返回真实值 | `[P1]` |
| `Cls.attr` | `None` | 返回描述符自身 | `[P1]` |

```python
class Descriptor:
    def __get__(self, instance, owner):
        if instance is None:
            return self          # 必须处理
        return instance.__dict__.get("_value")
```

> 注意：不处理 `instance is None` 时，`Cls.attr` 会在 `None.__dict__` 上抛 `AttributeError`，且错误信息指向内部实现，很难排查。`[P2]`

### 3.4 与 `__getattribute__` / `__getattr__` 的层级

| 层级 | 触发 | 依据 |
| --- | --- | --- |
| `__getattribute__` | 每次读取的最外层 | 第 14 章 |
| 描述符 | 在 `__getattribute__` 内部被调用 | `[P1]` |
| `__getattr__` | 前三步都失败后 | `[P1]` |

## 4. 读写删操作

### 4.1 读

```python
class Typed:
    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__.get("_value")
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 状态从实例取 | 不在描述符自身 | `[P1]` |
| 未赋值时给默认 | 或抛 `AttributeError` | `[P1]` |

### 4.2 写

```python
class Typed:
    def __set__(self, instance, value):
        if not isinstance(value, int):
            raise TypeError("需要 int")
        instance.__dict__["_value"] = value
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 校验在此处 | 统一入口 | `[P2]` |
| 写实例字典 | 不要 `setattr` 自己的名字 | `[P1]` |
| 键名避开属性名 | 否则再次触发描述符 | `[P1]` |

> 注意：在 `__set__` 里写 `setattr(instance, "age", value)` 而 `age` 就是描述符自己，会无限递归；必须写到 `instance.__dict__` 或用不同的键名。`[P1]`

### 4.3 删

```python
class Typed:
    def __delete__(self, instance):
        instance.__dict__.pop("_value", None)
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `del obj.attr` 走 `__delete__` | 有 `__delete__` 即数据描述符 | `[P1]` |
| 不实现则 `del` 报 `AttributeError` | 数据描述符拦截了删除 | `[P1]` |

### 4.4 状态存哪

| 方案 | 写法 | 优点 | 缺点 | 依据 |
| --- | --- | --- | --- | --- |
| 实例字典 | `instance.__dict__[name]` | 简单、快 | 键名要唯一 | `[P1]` |
| 私有键 | `instance.__dict__["_age"]` | 避免冲突 | 可能撞名 | `[P1]` |
| `WeakKeyDictionary` | 描述符持有 `{instance: value}` | 不动实例字典 | 复杂、要求可弱引用 | `[P2]` |
| 描述符自身属性 | `self.value = v` | ❌ 错误 | 所有实例共享 | `[P1]` |

```python
# 错误：所有实例共享
class Bad:
    def __set__(self, instance, value):
        self.value = value      # 存在描述符上

class A:
    x = Bad()

a1, a2 = A(), A()
a1.x = 1
a2.x = 2
print(a1.x)     # 2，被覆盖
```

> 注意：描述符对象是**类属性**，全类共用一份；把状态存它身上等于用实例变量模拟类变量。`[P1]`

### 4.5 `__set_name__` 与键名

```python
class Field:
    def __set_name__(self, owner, name):
        self.name = name
        self.private = "_" + name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__.get(self.private)

    def __set__(self, instance, value):
        instance.__dict__[self.private] = value
```

| 好处 | 说明 | 依据 |
| --- | --- | --- |
| 键名自动唯一 | 不同字段不同键 | `[P8]` |
| 不用手写 `"_age"` | 少写错 | `[P8]` |
| 继承时也对 | 子类同名会覆盖描述符 | `[P8]` |

## 5. 钩子与边界

### 5.1 必须放在类上

```python
class B:
    def m(self):
        return "m"

b = B()
b.desc = DataDesc()
print(b.desc.__class__.__name__)   # DataDesc（实测：没有触发 __get__）
```

| 放置位置 | 是否生效 | 依据 |
| --- | --- | --- |
| 类属性 | ✅ | `[P1]` |
| 实例属性 | ❌ 只是普通对象 | `[P1]` |
| 元类属性 | ✅ 对类访问生效 | `[P1]` |

> 注意：判断「描述符有没有生效」最快的方法就是看它有没有打印日志；放在实例上时，它就是一个普通对象。`[P2]`

### 5.2 方法绑定就是非数据描述符

```python
class B:
    def m(self):
        return "m"

print(hasattr(B.m, "__get__"))     # True（实测）
print(B.m.__get__(B())())          # m（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 函数有 `__get__` | 所以是非数据描述符 | `[P1]` |
| `__get__` 返回绑定方法 | `self` 被绑上 | `[P1]` |
| 这就是 `obj.m()` 自动传 `self` 的原因 | 第 08 章的悬念解开 | `[P1]` |

### 5.3 继承与覆盖

| 情况 | 结果 | 依据 |
| --- | --- | --- |
| 子类重新声明同名描述符 | 用子类的 | `[P1]` |
| 子类没声明 | 用父类的（MRO） | `[P1]` |
| 父类描述符的 `__set_name__` | 只在父类创建时调用一次 | `[P8]` |

### 5.4 与 `__slots__` 的关系

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `__slots__` 生成的是描述符 | 类属性级 | `[P1]` |
| 同名字段冲突 | `__slots__` 与类属性不能同名 | `[P1]` |
| 用 `__slots__` 后没有 `__dict__` | 描述符状态要用弱引用或 slots 名 | `[P1]` |

## 6. 解决最初的问题

### 6.1 一处定义，多处复用

```python
class Typed:
    def __init__(self, expected):
        self.expected = expected

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__.get(self.name)

    def __set__(self, instance, value):
        if not isinstance(value, self.expected):
            raise TypeError(f"{self.name} 需要 {self.expected.__name__}")
        instance.__dict__[self.name] = value

class User:
    name = Typed(str)
    age = Typed(int)

user = User()
user.name = "a"
user.age = 1
print(user.name, user.age)      # a 1（实测）
try:
    user.age = "x"
except TypeError as error:
    print(error)                # age 需要 int（实测）
```

| 对比 | 手写 property | 描述符 |
| --- | --- | --- |
| 新增字段 | 复制一套 getter/setter | 一行声明 |
| 规则修改 | 改 N 处 | 改 1 处 |
| 代码量 | 多 | 少 |
| 可读性 | 直白 | 需要理解协议 |
| 依据 | `[P3]` | `[P2]` |

### 6.2 什么时候用哪个

| 场景 | 选择 | 理由 | 依据 |
| --- | --- | --- | --- |
| 一个字段的校验 | `@property` | 简单直白 | `[P3]` |
| 多个字段同种校验 | 描述符 | 消除重复 | `[P2]` |
| 需要复用给别的类 | 描述符 | 跨类复用 | `[P2]` |
| 只读派生值 | `@property` | 够用 | `[P3]` |
| 框架/ORM | 描述符 | 字段元数据 | `[P2]` |

## 7. `@property` 装饰器

### 7.1 三段式

```python
class Celsius:
    def __init__(self):
        self._c = 0

    @property
    def value(self):
        return self._c

    @value.setter
    def value(self, new_value):
        if not isinstance(new_value, (int, float)):
            raise TypeError("必须数字")
        self._c = new_value

    @value.deleter
    def value(self):
        self._c = None

celsius = Celsius()
celsius.value = 25
print(celsius.value)      # 25（实测）
try:
    celsius.value = "x"
except TypeError as error:
    print(type(error).__name__)   # TypeError（实测）
```

| 装饰器 | 作用 | 依据 |
| --- | --- | --- |
| `@property` | 定义 getter | `[P3]` |
| `@x.setter` | 定义 setter | `[P3]` |
| `@x.deleter` | 定义 deleter | `[P3]` |

### 7.2 只读属性

```python
class Config:
    def __init__(self):
        self._timeout = 30

    @property
    def timeout(self):
        return self._timeout
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 只有 getter 时赋值报 `AttributeError` | 只读 | `[P3]` |
| 内部仍可通过 `_timeout` 改 | 不是安全边界 | `[P3]` |

### 7.3 `property` 就是数据描述符

```python
class Demo:
    @property
    def x(self):
        return 1

print(type(Demo.x).__name__)      # property
print(hasattr(Demo.x, "__set__")) # True
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `property` 有 `__set__` | 数据描述符 | `[P3]` |
| 优先级高于实例字典 | `obj.x = 1` 走 setter/报错 | `[P1]` |
| 只读 property 也能阻止遮蔽 | 所以 `obj.x = 1` 抛 `AttributeError` | `[P3]` |

> 注意：只读 `property` 会让「给实例赋同名属性」直接失败，这是它与「只有 getter 的普通方法」最大的区别。`[P3]`

### 7.4 缓存式属性

```python
import functools

class Expensive:
    def __init__(self):
        self.calls = 0

    @functools.cached_property
    def heavy(self):
        self.calls += 1
        return "computed"

expensive = Expensive()
print(expensive.heavy, expensive.heavy, expensive.calls)
# computed computed 1（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 第一次计算后写入实例字典 | 后续不再调用 | `[P5]` |
| 是非数据描述符 | 所以能被实例字典覆盖 | `[P5]` |
| 要求实例有 `__dict__` | `__slots__` 不适用 | `[P5]` |
| 3.8+ 才有 | 旧版用 `lru_cache` 或手写 | `[P5]` |

## 8. 应用场景

### 8.1 惰性计算

```python
import functools

class Report:
    def __init__(self, rows):
        self.rows = rows

    @functools.cached_property
    def total(self):
        print("计算 total")
        return sum(self.rows)

report = Report([1, 2, 3])
print(report.total)    # 计算 total / 6
print(report.total)    # 6，不再计算
```

| 适用 | 不适用 | 依据 |
| --- | --- | --- |
| 昂贵且稳定的派生值 | 随时间变化的数据 | `[P5]` |
| 纯计算 | 需要外部 I/O 且要刷新 | `[P5]` |
| 有 `__dict__` 的实例 | `__slots__` | `[P5]` |

> 注意：`cached_property` 缓存的是第一次的值，底层数据变了它不会自动失效；需要失效就 `del obj.total` 或改用显式方法。`[P5]`

### 8.2 类型检查

```python
class Typed:
    def __init__(self, expected, minimum=None):
        self.expected = expected
        self.minimum = minimum

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__.get(self.name)

    def __set__(self, instance, value):
        if not isinstance(value, self.expected):
            raise TypeError(f"{self.name} 需要 {self.expected.__name__}")
        if self.minimum is not None and value < self.minimum:
            raise ValueError(f"{self.name} 不能小于 {self.minimum}")
        instance.__dict__[self.name] = value
```

| 优势 | 说明 | 依据 |
| --- | --- | --- |
| 规则集中 | 一处定义 | `[P2]` |
| 声明式 | 类体一行一个字段 | `[P2]` |
| 误用早失败 | 赋值即报错 | `[P2]` |

### 8.3 ORM 字段（框架场景）

| 能力 | 描述符如何支持 | 依据 |
| --- | --- | --- |
| 字段名 | `__set_name__` | `[P8]` |
| 类型/长度约束 | `__set__` 校验 | `[P1]` |
| 延迟加载 | `__get__` 里查库 | `[P2]` |
| 变更追踪 | `__set__` 里记脏 | `[P2]` |

> 注意：在 `__get__` 里查库属于隐式 I/O，会让属性访问变慢且难以调试；框架用它是因为对外接口简洁，业务代码慎用。`[P2]`

### 8.4 单位转换

```python
class Meters:
    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__.get(self.name, 0)

    def __set__(self, instance, value):
        instance.__dict__[self.name] = value

class Distance:
    meters = Meters()

    @property
    def feet(self):
        return self.meters * 3.28084
```

| 模式 | 说明 | 依据 |
| --- | --- | --- |
| 存储用描述符 | 统一校验/转换 | `[P1]` |
| 派生用 property | 只读计算 | `[P3]` |

## 9. 综合示例：校验描述符

```python
"""第 15 章综合示例：一个带上下限的校验描述符。"""


class Validated:
    def __init__(self, expected, minimum=None):
        self.expected = expected
        self.minimum = minimum

    def __set_name__(self, owner, name):
        self.name = name

    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__.get(self.name)

    def __set__(self, instance, value):
        if not isinstance(value, self.expected):
            raise TypeError(f"{self.name} 需要 {self.expected.__name__}")
        if self.minimum is not None and value < self.minimum:
            raise ValueError(f"{self.name} 不能小于 {self.minimum}")
        instance.__dict__[self.name] = value


class Config:
    timeout = Validated(int, minimum=1)
    name = Validated(str)


config = Config()
config.timeout = 30
config.name = "search"
print(vars(config))
try:
    config.timeout = 0
except ValueError as error:
    print("ERR", error)
```

本机实测输出：

```text
{'timeout': 30, 'name': 'search'}
ERR timeout 不能小于 1
```

**逐段说明**：

| 代码 | 用到的机制 | 依据 |
| --- | --- | --- |
| `__set_name__` 记录字段名 | 自动、不手写 | `[P8]` |
| `__set__` 校验类型与下限 | 统一入口 | `[P1]` |
| `__get__` 处理 `instance is None` | 支持 `Config.timeout` | `[P2]` |
| 状态存 `instance.__dict__` | 每实例独立 | `[P1]` |
| `vars(config)` 可见真实键 | 键名即字段名 | `[P1]` |

> 注意：键名直接用 `self.name`（如 `timeout`），没有下划线前缀，会和「实例属性名」看起来一样；在 `__set__` 里必须写 `instance.__dict__[...]` 而不是 `setattr`，否则递归。`[P1]`

## 10. 注意事项与新手错误对照表

| 错误写法 / 操作 | 报错或现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 描述符放进实例属性 | 不生效 | 放类属性 | `[P1]` |
| 状态存描述符自身 | 所有实例共享 | 存 `instance.__dict__` | `[P1]` |
| `__set__` 里 `setattr(instance, self.name, v)` | 无限递归 | 写 `instance.__dict__` | `[P1]` |
| 不处理 `instance is None` | 类访问报错 | 返回 `self` | `[P2]` |
| 只写 `__get__` 想拦截赋值 | 赋值走实例字典 | 需要 `__set__` | `[P1]` |
| 只写 `__set__` 不写 `__get__` | 读不到值 | 成对实现 | `[P1]` |
| `__get__` 返回描述符本身总 | 拿不到值 | 区分类/实例访问 | `[P2]` |
| 手写 `_value` 键 | 多字段撞名 | `__set_name__` | `[P8]` |
| 在 `__init__` 里创建描述符 | 每实例一个，且无效 | 类属性 | `[P1]` |
| 描述符用 `lambda` 生成 | 无 `__set_name__` | 类定义 | `[P2]` |
| `property` getter 里改状态 | 副作用 | 只读 | `[P3]` |
| 只读 property 想赋值 | `AttributeError` | 加 setter | `[P3]` |
| `cached_property` 用于 `__slots__` | `AttributeError` | 用显式缓存 | `[P5]` |
| `cached_property` 期望自动失效 | 值不更新 | 手动 `del` | `[P5]` |
| `__get__` 里做重 I/O | 访问变慢 | 显式方法 | `[P2]` |
| `__set__` 里抛裸 `Exception` | 难定位 | 具体异常 | `[P4]` |
| `__set__` 不返回（有返回值） | 被忽略，无害但误导 | 不返回 | `[P1]` |
| `__delete__` 不存在时 `del` | `AttributeError` | 实现或别删 | `[P1]` |
| 描述符与 `__slots__` 同名 | 冲突 | 换名 | `[P1]` |
| 描述符与 `__getattribute__` 同时改 | 行为难推理 | 二选一 | `[P1]` |
| 继承后 `__set_name__` 未再调用 | 名字是父类的 | 子类重新声明 | `[P8]` |
| 描述符持有实例强引用 | 内存泄漏 | `WeakKeyDictionary` | `[P2]` |
| `__get__` 返回可变对象 | 外部可改内部状态 | 返回副本 | `[P4]` |
| 用描述符做权限控制 | 可绕过（直接 `__dict__`） | 服务端校验 | `[P4]` |
| `property` 里调 `super()` | 可能递归 | 显式父类 | `[P3]` |
| 一个描述符实例给多个字段用 | 字段名互相覆盖 | 每字段一个实例 | `[P8]` |
| `__set__` 里不校验类型 | 脏数据 | 统一校验 | `[P4]` |
| 描述符名与实例属性同名 | 读被描述符接管 | 键名加前缀 | `[P1]` |
| `__get__` 抛 `AttributeError` 又定义 `__getattr__` | 触发兜底逻辑 | 分清语义 | `[P1]` |
| 用描述符做懒加载但忽略线程安全 | 并发重复计算 | 加锁 | `[P5]` |
| 描述符里打印日志 | 高频日志 | 采样 | `[P4]` |
| 以为描述符能替代测试 | 仍会漏规则 | 补单测 | `[P4]` |

## 11. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 单字段优先 `@property` | 简单直白 | `[P3]` |
| 多字段同规则用描述符 | 消除重复 | `[P2]` |
| 一律用 `__set_name__` 取名字 | 免手写键 | `[P8]` |
| 状态存 `instance.__dict__` | 每实例独立 | `[P1]` |
| 处理 `instance is None` | 支持类访问 | `[P2]` |
| 描述符只做「访问控制」 | 不塞业务逻辑 | `[P2]` |
| 命名表达意图 | `Validated` / `Meters` | `[P4]` |
| 校验失败用具体异常 + 可操作信息 | 早失败 | `[P4]` |
| `cached_property` 用于稳定派生值 | 省重复计算 | `[P5]` |
| 框架级才自研描述符 | 业务代码克制 | `[P2]` |

**风格示范**：

```python
class Validated:
    """类型 + 下限校验的描述符。

    状态按实例存储在 instance.__dict__[name]，描述符自身不保存数据。
    """

    def __init__(self, expected: type, *, minimum: float | None = None) -> None:
        self.expected = expected
        self.minimum = minimum

    def __set_name__(self, owner: type, name: str) -> None:
        self.name = name

    def __get__(self, instance, owner=None):
        if instance is None:
            return self
        return instance.__dict__.get(self.name)

    def __set__(self, instance, value) -> None:
        if not isinstance(value, self.expected):
            raise TypeError(f"{self.name} 需要 {self.expected.__name__}，收到 {type(value).__name__}")
        if self.minimum is not None and value < self.minimum:
            raise ValueError(f"{self.name} 不能小于 {self.minimum}，收到 {value}")
        instance.__dict__[self.name] = value
```

**边界**：

- 描述符里的校验不能替代服务端业务校验；它只管「本对象内部状态合法」。
- `__get__` 里不要做网络/数据库调用（除非是明确的 ORM 懒加载，并接受其代价）。
- 描述符状态不要存自身，也不要用全局字典（泄漏）。

## 12. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[P1]` | python.org | https://docs.python.org/3.12/reference/datamodel.html | 描述符协议、数据/非数据描述符、属性查找优先级、函数绑定、`__slots__` |
| `[P2]` | python.org | https://docs.python.org/3.12/howto/descriptor.html | 描述符指南、状态存储、`WeakKeyDictionary`、延迟加载、与 `property` 的关系 |
| `[P3]` | python.org | https://docs.python.org/3.12/library/functions.html | `property` / `classmethod` / `staticmethod` 的内置说明 |
| `[P4]` | PEP 官方 | https://peps.python.org/pep-0008/ | 命名、注释写「为什么」、失败要快、简单优先 |
| `[P5]` | python.org | https://docs.python.org/3.12/library/functools.html | `functools.cached_property` |
| `[P6]` | GitHub 官方 | https://github.com/python/cpython/blob/main/Doc/howto/descriptor.rst | 官方指南源文件（`[P2]` 页脚 Show Source 指向） |
| `[P7]` | PEP 官方 | https://peps.python.org/pep-0020/ | The Zen of Python（显式、简单） |
| `[P8]` | PEP 官方 | https://peps.python.org/pep-0487/ | `__set_name__` 与 `__init_subclass__` 的引入 |

> **核对状态**：`[P1]` `[P4]` 与本章 `README.md` 已核对来源一致；其余链接按 `docs.python.org/3.12` 与 `peps.python.org` 官方结构整理，**本次未逐页直连复核**。文中「实测」结论均为本机 Python 3.12.8 运行结果。

## 13. 毕业自查清单

**能说清（概念层）**：

- [ ] 描述符是什么，为什么必须作为类属性
- [ ] 数据描述符与非数据描述符的区别和优先级
- [ ] 属性查找的四步链条
- [ ] 为什么 `obj.method` 自动带 `self`
- [ ] `instance is None` 代表什么访问
- [ ] 描述符状态为什么不能存在自身
- [ ] `property` 为什么能阻止实例遮蔽
- [ ] `cached_property` 为什么要求有 `__dict__`

**能写出（代码层）**：

- [ ] 一个最小数据描述符（读写）
- [ ] 带 `__set_name__` 的校验描述符
- [ ] 带下限校验的描述符并对越界值报错
- [ ] `@property` 的 getter / setter / deleter 三段式
- [ ] 只读 property 并验证赋值报错
- [ ] 用 `cached_property` 做惰性计算
- [ ] 用 `WeakKeyDictionary` 存实例状态（了解）

**能判断（避坑层）**：

- [ ] 看到描述符放进实例能指出不生效
- [ ] 看到状态存描述符自身能指出跨实例共享
- [ ] 看到 `__set__` 里 `setattr` 自己能指出递归
- [ ] 看到没处理 `instance is None` 能指出类访问报错
- [ ] 看到只写 `__get__` 却想拦截赋值能指出需要 `__set__`
- [ ] 看到 `cached_property` 用于 `__slots__` 能指出失败

**能跑通（验收层）**：

- [ ] 运行 `examples/descriptor_demo.py` 并解释「写入/读取/实例字典」三行
- [ ] 把第 9 节示例存成文件运行，输出与文档一致
- [ ] 在 REPL 验证「非数据描述符被实例遮蔽、数据描述符不被遮蔽」
- [ ] 手写校验描述符并测试类型错误与越界错误

## 14. 下一章衔接

第 19 章 `ABC`：描述符解决「属性怎么被访问」，ABC 解决「实现契约怎么被强制」。

本章留下的伏笔：

1. ABC 的 `@abstractmethod` 依赖元类 `ABCMeta` 在类创建时收集信息（第 19 章）。
2. 描述符的 `__set_name__` 与 `__init_subclass__` 都来自同一个 PEP 487，它们是「轻量元编程」的基础。
3. 方法绑定来自函数的 `__get__`，这解释了为什么 `@staticmethod` 要「去掉 `__get__` 效果」。