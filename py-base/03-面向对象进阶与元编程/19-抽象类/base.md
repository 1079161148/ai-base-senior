# 19 抽象类（Abstract Base Class） · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把截图里的「定义抽象类、抽象属性、子类必须实现所有抽象方法、实际应用场景」逐条展开，并补上 `register`、`__subclasshook__`、与 Protocol 的分工，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测） |
| 前置 | 第 08、09、14 章（类、类型、协议） |
| 覆盖范围 | `abc.ABC`、`@abstractmethod`、抽象属性、`__abstractmethods__`、部分实现的报错、`register`、`__subclasshook__`、`collections.abc`、场景与取舍 |
| 明确不覆盖 | 元类实现细节（12）、静态类型 `Protocol` 全量（20）、迭代器实现（17） |
| 学完验收 | 能写强制实现的接口、能解释 `register` 为什么不补实现、能说清 ABC 与鸭子类型/Protocol 的分工（见第 13 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[An]` `` 指向第 12 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果。

**推荐顺序**：

```text
1 为什么需要（第 1 节）      → 鸭子类型的延迟报错
2 定义抽象类（第 2 节）      → ABC + abstractmethod
3 抽象属性（第 3 节）        → property 与 abstractmethod 的顺序
4 必须实现所有抽象方法（第 4 节）→ 报错与收集
5 虚拟子类（第 5 节）        → register / subclasshook
6 与鸭子类型、Protocol 分工（第 6 节）
7 标准库 ABC（第 7 节）      → collections.abc
8 实际场景（第 8 节）        → 插件、适配器、模板方法
9 综合示例（第 9 节）
10 注意事项（第 10 节）      → 30 条错误对照
```

**与 README 的分工**：README 给结论与边界，本文件负责用法、报错与场景。冲突时以本文件为准。

## 1. 为什么需要抽象基类

### 1.1 鸭子类型的问题

```python
class Search:
    def run(self, payload):
        return "search:" + payload

class Broken:
    pass          # 忘记实现 run

def execute(tool, payload):
    return tool.run(payload)

print(execute(Search(), "AI"))    # search:AI
execute(Broken(), "AI")           # AttributeError，调用时才炸
```

| 问题 | 表现 | 依据 |
| --- | --- | --- |
| 错误延迟 | 调用时才 `AttributeError` | `[A1]` |
| 缺什么不明确 | 只看类不知道要实现哪些 | `[A1]` |
| 大团队协作 | 接口靠口头约定 | `[A1]` |
| 重构风险 | 改名无提示 | `[A1]` |

### 1.2 ABC 的定位

| 能力 | 说明 | 依据 |
| --- | --- | --- |
| 声明接口 | 类上明确列出必须实现的方法 | `[A1]` |
| 创建时检查 | 缺失实现在**实例化**就报错 | `[A1]` |
| 可复用工具 | 抽象基类可提供公共实现 | `[A1]` |
| 运行时类型 | `isinstance` 认虚拟子类 | `[A1]` |

> 注意：ABC 是「运行时约束」，不是编译期检查；静态检查用 `typing.Protocol`（第 20 章）。`[A5]`

## 2. 定义抽象类

### 2.1 最小写法

```python
import abc

class Tool(abc.ABC):
    """工具接口。"""

    @abc.abstractmethod
    def run(self, argument):
        """执行工具并返回结果。"""

class Search(Tool):
    def run(self, argument):
        return "result:" + argument

print(Search().run("AI"))    # result:AI
```

| 要素 | 说明 | 依据 |
| --- | --- | --- |
| 继承 `abc.ABC` | 提供 `ABCMeta` 元类 | `[A1]` |
| `@abc.abstractmethod` | 标记必须实现 | `[A1]` |
| 方法体可写 `...` / `pass` / docstring | 仅是占位 | `[A1]` |
| 子类实现同名方法 | 解除抽象标记 | `[A1]` |

### 2.2 抽象类不能实例化

```python
try:
    Tool()
except TypeError as error:
    print(type(error).__name__, "abstract" in str(error).lower())
    # TypeError True（实测）
```

报错形如：

```text
TypeError: Can't instantiate abstract class Tool with abstract method run
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 抽象类不能直接实例化 | 缺实现 | `[A1]` |
| 错误消息列出缺失方法 | 可操作 | `[A1]` |
| 子类全实现后可实例化 | 正常 | `[A1]` |

### 2.3 `__abstractmethods__`

```python
print(Tool.__abstractmethods__)    # frozenset({'run'})（实测）
print(type(Tool).__name__)         # ABCMeta（实测）
```

| 项 | 值 | 依据 |
| --- | --- | --- |
| 类型 | `frozenset` | `[A1]` |
| 内容 | 仍未实现的方法名 | `[A1]` |
| 空集 | 可以实例化 | `[A1]` |
| 元类 | `ABCMeta` | `[A1]` |

### 2.4 抽象方法可以有实现体

```python
class Base(abc.ABC):
    @abc.abstractmethod
    def run(self):
        return "base-impl"

class Child(Base):
    def run(self):
        return super().run() + "+child"

print(Child().run())   # base-impl+child（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 抽象方法可以有函数体 | 供子类 `super()` 调用 | `[A1]` |
| 有实现也不影响「不可实例化」 | 标记才决定 | `[A1]` |
| 适合「模板方法」 | 公共逻辑在基类 | `[A1]` |

> 注意：这是 ABC 相对 Java 接口最大的不同——抽象方法可以带默认实现，子类可选择复用。`[A1]`

### 2.5 子类只实现一部分

```python
class Incomplete(Tool):
    pass

try:
    Incomplete()
except TypeError as error:
    print(type(error).__name__)   # TypeError（实测）
```

| 情况 | 结果 | 依据 |
| --- | --- | --- |
| 一个都没实现 | `TypeError` | `[A1]` |
| 实现一部分 | 仍 `TypeError`，消息列出剩余 | `[A1]` |
| 全部实现 | 可实例化 | `[A1]` |
| 实现后又用 `@abstractmethod` 覆盖 | 重新变抽象 | `[A1]` |

## 3. 抽象属性

### 3.1 正确顺序

```python
class WithProp(abc.ABC):
    @property
    @abc.abstractmethod
    def name(self):
        ...

    @abc.abstractmethod
    def run(self):
        ...

class Impl(WithProp):
    @property
    def name(self):
        return "impl"

    def run(self):
        return "run"

print(Impl().name, Impl().run())   # impl run（实测）
```

| 顺序 | 结果 | 依据 |
| --- | --- | --- |
| `@property` 在外、`@abstractmethod` 在内 | ✅ 正确 | `[A1]` |
| `@abstractmethod` 在外、`@property` 在内 | ❌ 属性不抽象，可绕过 | `[A1]` |

> 注意：装饰器自下而上应用，所以 `@property` 必须写在最上面（最后应用），否则 `abstractmethod` 标记的是 property 对象而非函数。`[A1]`

### 3.2 子类必须用 property 实现

```python
class Wrong(WithProp):
    def name(self):        # 普通方法，不是属性
        return "x"

    def run(self):
        return "run"
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| ABC 只检查「有没有这个名字」 | 不检查是不是 property | `[A1]` |
| 用普通方法也能通过实例化 | 但 `Wrong().name` 是方法对象 | `[A1]` |
| 语义一致要靠约定或测试 | ABC 管不了 | `[A1]` |

### 3.3 抽象类属性（类级常量）

```python
class Plugin(abc.ABC):
    key: str = ""          # 约定由子类覆盖，不需要 abstractmethod

    @abc.abstractmethod
    def run(self): ...
```

| 方式 | 能否强制 | 依据 |
| --- | --- | --- |
| 普通类属性 + 约定 | 不能 | `[A1]` |
| `@property @abstractmethod` | 能（实例级） | `[A1]` |
| 元类检查类属性 | 能（第 12 章） | `[A1]` |

> 注意：`@abstractmethod` 只对「方法/描述符」生效；想强制子类声明类属性，需要自己写元类或 `__init_subclass__` 检查。`[A1]`

## 4. 子类必须实现所有抽象方法

### 4.1 收集规则

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 沿 MRO 收集 | 所有基类的抽象方法 | `[A1]` |
| 同名实现即解除 | 子类覆盖即移除 | `[A1]` |
| 重新标记会加回 | 子类再写 `@abstractmethod` | `[A1]` |
| 实例化时统一检查 | 缺失即 `TypeError` | `[A1]` |

```python
class A(abc.ABC):
    @abc.abstractmethod
    def one(self): ...

class B(A):
    @abc.abstractmethod
    def two(self): ...

class C(B):
    def one(self): return 1
    def two(self): return 2

print(C().__class__.__abstractmethods__)   # frozenset()
```

### 4.2 多继承与 mixin

```python
class Mixin:
    def helper(self):
        return "helper"

class Service(Mixin, abc.ABC):
    @abc.abstractmethod
    def run(self): ...

class ServiceImpl(Service):
    def run(self):
        return "run"

print(ServiceImpl().run(), ServiceImpl().helper())   # run helper（实测）
```

| 组合 | 说明 | 依据 |
| --- | --- | --- |
| `Mixin` 在前 | 方法与 ABC 一起继承 | `[A1]` |
| ABC 在后 | 不影响 MRO 收集 | `[A1]` |
| mixin 提供公共方法 | 不算抽象 | `[A1]` |

### 4.3 不用 `abc.ABC` 的写法

```python
class NotABC(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def m(self): ...

try:
    NotABC()
except TypeError as error:
    print(type(error).__name__)   # TypeError（实测）
```

| 写法 | 说明 | 依据 |
| --- | --- | --- |
| `class X(abc.ABC)` | 推荐，语义清晰 | `[A1]` |
| `metaclass=abc.ABCMeta` | 等价，少一个基类 | `[A1]` |
| 只加 `@abstractmethod` 不设元类 | ❌ 不生效 | `[A1]` |

> 注意：`@abstractmethod` 本身只是打标记，真正让它生效的是 `ABCMeta`；只写装饰器不设元类，类照常可实例化。`[A1]`

## 5. 虚拟子类

### 5.1 `register()`

```python
class FileLike:
    pass

Tool.register(FileLike)
print(isinstance(FileLike(), Tool))    # True（实测）
print(hasattr(FileLike(), "run"))      # False（实测，不会补实现）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 只影响 `isinstance` / `issubclass` | 不继承方法 | `[A1]` |
| 适用于「无法修改的第三方类」 | 典型用途 | `[A1]` |
| 误用会掩盖缺失实现 | 风险 | `[A1]` |

### 5.2 `__subclasshook__`

```python
class Sized(abc.ABC):
    @classmethod
    def __subclasshook__(cls, candidate):
        return hasattr(candidate, "__len__")

class HasLen:
    def __len__(self):
        return 1

print(issubclass(HasLen, Sized))   # True（实测）
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 按「有没有某方法」判定 | 鸭子类型的结构化检查 | `[A1]` |
| 返回 `True` / `False` / `NotImplemented` | 后者交给常规判定 | `[A1]` |
| `collections.abc` 大量使用 | 如 `Iterable` 看 `__iter__` | `[A3]` |

### 5.3 风险

| 风险 | 说明 | 依据 |
| --- | --- | --- |
| 虚拟子类没有实现 | `isinstance` 为真但调用炸 | `[A1]` |
| 绕过类型检查 | 生产事故来源 | `[A1]` |
| 调试困难 | 类关系不可见 | `[A1]` |

> 注意：`register` 是「我保证它符合协议」的声明；这个保证只能靠你，ABC 无法验证。`[A1]`

## 6. 与鸭子类型、Protocol 的分工

| 方式 | 检查时机 | 是否需继承 | 能否提供实现 | 依据 |
| --- | --- | --- | --- | --- |
| 鸭子类型 | 运行时（调用时） | 不需要 | 不涉及 | `[A1]` |
| ABC | 运行时（实例化） | 需要（或 `register`） | 可以 | `[A1]` |
| `Protocol` | 静态（类型检查器） | 不需要（结构化） | 可以（默认实现） | `[A5]` |
| `__subclasshook__` | 运行时（结构化） | 不需要 | 不涉及 | `[A1]` |

| 场景 | 推荐 | 理由 | 依据 |
| --- | --- | --- | --- |
| 内部插件接口 | ABC | 早失败、可提供公共逻辑 | `[A1]` |
| 公共库的宽松接口 | Protocol 或鸭子类型 | 不强迫用户继承 | `[A5]` |
| 结构性判断（有 `__iter__`） | `__subclasshook__` / `collections.abc` | 标准做法 | `[A3]` |
| 想复用默认实现 | ABC | 支持具体方法 | `[A1]` |
| 完全动态的第三方对象 | 鸭子类型 + `hasattr` | 不侵入 | `[A1]` |

> 注意：ABC 的代价是「必须显式继承」；如果你希望第三方类不加修改就能通过检查，用 `Protocol`（静态）或 `register`（运行时）。`[A5]`

## 7. 标准库 ABC

### 7.1 `collections.abc`

```python
from collections.abc import Iterable, Sequence

print(isinstance([], Iterable))    # True（实测）
print(isinstance([], Sequence))    # True（实测）
print(isinstance({}, Sequence))    # False（实测）
```

| 类 | 语义 | 必须实现 | 依据 |
| --- | --- | --- | --- |
| `Iterable` | 可迭代 | `__iter__` | `[A3]` |
| `Iterator` | 迭代器 | `__next__` | `[A3]` |
| `Sequence` | 有序序列 | `__getitem__` / `__len__` | `[A3]` |
| `Mapping` | 映射 | `__getitem__` / `__len__` / `__iter__` | `[A3]` |
| `Set` | 集合 | `__contains__` / `__iter__` / `__len__` | `[A3]` |
| `Sized` | 有长度 | `__len__` | `[A3]` |

### 7.2 继承 `Sequence` 得到什么

```python
from collections.abc import Sequence

class Deck(Sequence):
    def __init__(self, cards):
        self._cards = list(cards)

    def __getitem__(self, index):
        return self._cards[index]

    def __len__(self):
        return len(self._cards)

deck = Deck(["a", "b", "c"])
print(deck[0], len(deck), "b" in deck, list(reversed(deck)))
```

| 免费得到 | 来源 | 依据 |
| --- | --- | --- |
| `in` | `Sequence.__contains__` | `[A3]` |
| `reversed` | `Sequence.__reversed__` | `[A3]` |
| `index` / `count` | `Sequence` | `[A3]` |
| 迭代 | `__getitem__` 回退 | `[A3]` |

> 注意：继承标准库 ABC 只写两个方法就获得一整套行为，但**切片**仍需 `__getitem__` 自己处理 `slice`。`[A3]`

## 8. 实际应用场景

### 8.1 插件接口

```python
class Plugin(abc.ABC):
    key: str = ""

    @property
    @abc.abstractmethod
    def display_name(self): ...

    @abc.abstractmethod
    def run(self, payload): ...
```

| 收益 | 说明 | 依据 |
| --- | --- | --- |
| 新增插件漏实现 → 启动即报错 | 早失败 | `[A1]` |
| 接口文档化 | 类上即契约 | `[A1]` |
| 统一注册 | 配合 `__init_subclass__` | 第 12 章 |

### 8.2 存储/支付适配器

```python
class Storage(abc.ABC):
    @abc.abstractmethod
    def read(self, key: str) -> bytes: ...

    @abc.abstractmethod
    def write(self, key: str, value: bytes) -> None: ...

class MemoryStorage(Storage):
    def __init__(self):
        self._data = {}

    def read(self, key):
        return self._data[key]

    def write(self, key, value):
        self._data[key] = value
```

| 收益 | 说明 | 依据 |
| --- | --- | --- |
| 换实现不改调用方 | 依赖接口 | `[A1]` |
| 测试用内存实现 | 快 | `[A1]` |
| 缺方法早暴露 | 实例化时报错 | `[A1]` |

### 8.3 模板方法模式

```python
class Exporter(abc.ABC):
    def export(self, rows):
        """模板方法：固定流程，子类只填步骤。"""
        clean = self.clean(rows)
        return self.serialize(clean)

    def clean(self, rows):
        return [row for row in rows if row]

    @abc.abstractmethod
    def serialize(self, rows):
        ...

class CsvExporter(Exporter):
    def serialize(self, rows):
        return "\n".join(",".join(map(str, row)) for row in rows)

print(CsvExporter().export([[1, 2], [], [3, 4]]))   # 1,2 / 3,4
```

| 角色 | 说明 | 依据 |
| --- | --- | --- |
| 基类定流程 | `export` 不被覆盖 | `[A1]` |
| 子类填步骤 | `serialize` 抽象 | `[A1]` |
| 可选步骤有默认实现 | `clean` | `[A1]` |

### 8.4 不适合用的场景

| 场景 | 为什么不合适 | 替代 | 依据 |
| --- | --- | --- | --- |
| 只有一个实现 | 过度设计 | 普通类 | `[A4]` |
| 第三方类无法继承 | 需 `register` 但无实现校验 | Protocol | `[A5]` |
| 纯数据载体 | 没有行为约束 | `@dataclass` | `[A4]` |
| 需要动态组装 | 继承僵化 | 组合 | `[A4]` |

## 9. 综合示例：插件接口与工厂

```python
"""第 19 章综合示例：ABC 约束插件必须实现属性与方法。"""

import abc


class PluginBase(abc.ABC):
    key = ""

    @property
    @abc.abstractmethod
    def display_name(self):
        ...

    @abc.abstractmethod
    def run(self, payload):
        ...


class SearchTool(PluginBase):
    key = "search"

    @property
    def display_name(self):
        return "搜索"

    def run(self, payload):
        return f"search:{payload}"


def build(cls):
    if not issubclass(cls, PluginBase):
        raise TypeError(f"{cls.__name__} 必须是 PluginBase 子类")
    return cls()


print(build(SearchTool).run("AI"), build(SearchTool).display_name)
try:
    build(str)
except TypeError as error:
    print("ERR", error)
```

本机实测输出：

```text
search:AI 搜索
ERR str 必须是 PluginBase 子类
```

**逐段说明**：

| 代码 | 用到的机制 | 依据 |
| --- | --- | --- |
| `PluginBase(abc.ABC)` | 抽象基类 | `[A1]` |
| `@property @abstractmethod` | 抽象属性（顺序正确） | `[A1]` |
| `key = ""` | 类属性约定 | `[A1]` |
| `issubclass` 校验 | 工厂入口检查 | `[A1]` |
| 子类同时实现属性与方法 | 才能实例化 | `[A1]` |

> 注意：`build()` 里的 `issubclass` 检查其实是多余的——`cls()` 本身就会因抽象方法未实现而 `TypeError`；但显式检查能给出更清楚的错误信息（「不是子类」而不是「有抽象方法」）。`[A4]`

## 10. 注意事项与新手错误对照表

| 错误写法 / 操作 | 报错或现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 只写 `@abstractmethod` 不继承 `ABC` | 类能实例化，标记无效 | 继承 `abc.ABC` | `[A1]` |
| `@abstractmethod` 写在 `@property` 上面 | 属性不抽象 | `@property` 在外 | `[A1]` |
| 子类少实现一个方法 | `TypeError` | 补齐 | `[A1]` |
| 抽象类直接实例化 | `TypeError` | 用子类 | `[A1]` |
| 以为 ABC 能检查签名 | 不检查参数 | 测试/Docstring | `[A1]` |
| 以为 ABC 能检查返回类型 | 不检查 | 类型标注 + 测试 | `[A5]` |
| 用 `register` 代替继承 | 缺实现，调用炸 | 真正实现 | `[A1]` |
| `register` 后以为方法被补上 | `AttributeError` | 只影响 isinstance | `[A1]` |
| `__subclasshook__` 返回 `True` 就放心 | 结构匹配但语义未必 | 加测试 | `[A1]` |
| 抽象属性用普通方法实现 | 实例化通过但语义错 | 用 `@property` | `[A1]` |
| 想强制子类声明类属性 | `abstractmethod` 管不了 | 元类/`__init_subclass__` | 第 12 章 |
| 滥用深继承链 | 维护困难 | 组合 | `[A4]` |
| 一个实现也上 ABC | 过度设计 | 普通类 | `[A4]` |
| ABC 里塞业务逻辑 | 难测试 | 只放契约与模板 | `[A4]` |
| 用 ABC 当 Java 接口硬套 | 代码僵化 | 鸭子类型 + Protocol | `[A4]` |
| 抽象方法体写完整实现但子类不调 | 死代码 | 或删或强制 `super()` | `[A4]` |
| `Tool()` 在测试里想 mock | 不能实例化 | mock 子类 | `[A1]` |
| 多继承时 ABC 顺序错 | MRO 复杂 | mixin 在前 | `[A1]` |
| 与自定义元类混用 | `metaclass conflict` | 元类继承 `ABCMeta` | `[A1]` |
| 标准库 ABC 重复造 | 维护成本 | 用 `collections.abc` | `[A3]` |
| 继承 `Sequence` 不处理切片 | 类型错 | 处理 `slice` | `[A3]` |
| 抽象方法名与属性名冲突 | 覆盖混乱 | 换名 | `[A1]` |
| `__abstractmethods__` 当可变集合 | 实际是 `frozenset` | 只读查看 | `[A1]` |
| 子类 `@abstractmethod` 又实现 | 仍抽象 | 去掉装饰器 | `[A1]` |
| 用 `hasattr` 替代 `isinstance` | 漏掉虚拟子类 | 按需选择 | `[A1]` |
| 异常类继承 `BaseException` | 捕获不到 | 继承 `Exception` | `[A4]` |
| 接口方法太多 | 实现负担 | 拆分 | `[A4]` |
| ABC 用于数据校验 | 职责错位 | 描述符/校验器 | 第 15 章 |
| 把 `abstractmethod` 当文档标记 | 无强制力 | 真加装饰器 | `[A1]` |
| 忘记 `import abc` | `NameError` | 导入 | `[A1]` |

## 11. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 只对「必须实现」的方法用 `@abstractmethod` | 不要全标 | `[A1]` |
| 优先复用 `collections.abc` | 别重造 | `[A3]` |
| 抽象属性用 `@property` 在外 | 顺序不能反 | `[A1]` |
| 接口少而内聚 | 1–5 个方法 | `[A4]` |
| 提供默认实现时说明 | 子类可选择复用 | `[A1]` |
| 类名表达抽象性 | `Storage` / `Exporter` | `[A4]` |
| docstring 写清契约与不变量 | 接口即文档 | `[A4]` |
| 工厂入口显式校验 | 错误信息更清楚 | `[A4]` |
| 不要用 `register` 兜底未实现 | 会掩盖问题 | `[A1]` |
| 需要静态检查时上 Protocol | 运行时 + 静态互补 | `[A5]` |

**风格示范**：

```python
import abc


class Storage(abc.ABC):
    """键值存储接口。

    契约：
      - read 未命中时抛 KeyError；
      - write 覆盖同键旧值。
    """

    @abc.abstractmethod
    def read(self, key: str) -> bytes:
        """返回 key 对应的字节；未命中抛 KeyError。"""

    @abc.abstractmethod
    def write(self, key: str, value: bytes) -> None:
        """写入 key；已存在则覆盖。"""
```

**边界**：

- ABC 只保证「有这个名字」，不保证行为正确；关键路径仍要测试。
- 抽象基类不应持有可变全局状态，否则所有子类共享。
- 与框架的元类混用时，先确认元类继承关系。

## 12. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[A1]` | python.org | https://docs.python.org/3.12/library/abc.html | `ABC`、`abstractmethod`、抽象属性、`__abstractmethods__`、`register`、`__subclasshook__`、实例化检查 |
| `[A2]` | PEP 官方 | https://peps.python.org/pep-3119/ | ABC 的动机、虚拟子类、与鸭子类型的关系 |
| `[A3]` | python.org | https://docs.python.org/3.12/library/collections.abc.html | 标准库抽象基类与免费获得的混入方法 |
| `[A4]` | PEP 官方 | https://peps.python.org/pep-0008/ | 类名/异常命名、注释写「为什么」、简单优先 |
| `[A5]` | python.org | https://docs.python.org/3.12/library/typing.html | `Protocol`、结构化子类型（静态检查，第 20 章） |
| `[A6]` | GitHub 官方 | https://github.com/python/cpython/blob/main/Doc/library/abc.rst | 官方文档源文件（`[A1]` 页脚 Show Source 指向） |
| `[A7]` | PEP 官方 | https://peps.python.org/pep-0544/ | `Protocol` 与 ABC 的分工 |

> **核对状态**：`[A1]` `[A4]` 与本章 `README.md` 已核对来源一致；其余链接按 `docs.python.org/3.12` 与 `peps.python.org` 官方结构整理，**本次未逐页直连复核**。文中「实测」结论均为本机 Python 3.12.8 运行结果。

## 13. 毕业自查清单

**能说清（概念层）**：

- [ ] ABC 与鸭子类型各自解决什么问题
- [ ] 抽象方法为什么能带实现体
- [ ] `@property` 与 `@abstractmethod` 为什么顺序不能反
- [ ] `__abstractmethods__` 是什么、何时为空
- [ ] `register` 影响什么、不影响什么
- [ ] `__subclasshook__` 与鸭子类型的关系
- [ ] ABC 与 Protocol 的分工（运行时 vs 静态）
- [ ] 为什么继承 `Sequence` 只写两个方法就够

**能写出（代码层）**：

- [ ] 一个含 `@abstractmethod` 的接口并验证不可实例化
- [ ] 抽象属性并用 `@property` 在子类实现
- [ ] 模板方法：基类定流程、子类填步骤
- [ ] 用 `register` 把第三方类登记为虚拟子类
- [ ] 用 `__subclasshook__` 做结构化判定
- [ ] 继承 `collections.abc.Iterable` / `Sequence`
- [ ] 工厂函数校验 `issubclass`

**能判断（避坑层）**：

- [ ] 看到只写 `@abstractmethod` 没继承 `ABC` 能指出无效
- [ ] 看到装饰器顺序反了能指出属性不抽象
- [ ] 看到 `register` 后直接调用方法能指出未实现
- [ ] 看到子类少实现能预判 `TypeError`
- [ ] 看到「一个实现也上 ABC」能指出过度设计
- [ ] 看到想强制类属性能指出要用元类或 `__init_subclass__`

**能跑通（验收层）**：

- [ ] 运行 `examples/abc_demo.py` 并解释「未实现的抽象方法」一行
- [ ] 把第 9 节示例存成文件运行，输出与文档一致
- [ ] 在 REPL 验证 `Tool()` 抛 `TypeError` 且消息含方法名
- [ ] 手写「存储接口 + 内存实现 + 文件实现」并互换使用

## 14. 下一章衔接

第 12 章 `元类`：ABC 能阻止实例化，靠的是元类 `ABCMeta` 在类创建时收集 `__abstractmethods__`——这正是「类是怎么被创建的」的入口。

本章留下的伏笔：

1. `ABCMeta` 是元类，`class X(abc.ABC)` 等价于 `class X(metaclass=ABCMeta)`。
2. `@abstractmethod` 只是打标记，收集与检查都发生在类创建阶段（第 12 章第 1 节的五步链路）。
3. 一旦理解了 `__init_subclass__` 与元类的分工，就能判断「接口约束该用 ABC 还是更轻的钩子」。