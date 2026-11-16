# 20 类型标注 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把截图里的「为什么需要、基础标注、常用复合类型、类与自定义类型、泛型、`Callable`、应用场景、忽略检查」逐条展开，并补上 `TypedDict`、`Literal`、`Annotated`、`Self`、PEP 695、`ParamSpec` 等必然遇到的内容，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测） |
| 前置 | 第 05、04、09 章（函数、容器、类型） |
| 覆盖范围 | 注解本质、变量/函数标注、`Optional`/`Union`、容器泛型、`Any`、类型别名、`Literal`/`Final`/`Annotated`、`TypedDict`/`NamedTuple`、类与前向引用、`Self`、`TypeVar`、PEP 695、`Protocol`、`Callable`/`ParamSpec`、`overload`、`TYPE_CHECKING`/`cast`/`ignore` |
| 明确不覆盖 | mypy/pyright 内部规则（本机未安装，见 7.3）、运行时校验库（pydantic 等，23 章）、`dataclass` 全量特性（README 示例） |
| 学完验收 | 能解释注解为何不影响运行时、能写出带泛型与 `Protocol` 的公共接口、能说清 `Optional` 与默认值的区别（见第 13 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Yn]` `` 指向第 12 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果。

**推荐顺序**：

```text
1 为什么需要（第 1 节）      → 注解是元数据
2 基础标注（第 2 节）        → 变量 / 函数 / 求值时机
3 复合类型（第 3 节）        → Optional / 容器 / Any / 别名
4 类与自定义类型（第 4 节）  → 前向引用 / Self / dataclass
5 泛型（第 5 节）            → TypeVar / PEP 695 / Protocol
6 Callable（第 6 节）        → 回调 / ParamSpec / overload
7 应用场景（第 7 节）        → API / IDE / CI
8 忽略检查（第 8 节）        → ignore / cast / TYPE_CHECKING
9 综合示例（第 9 节）
10 注意事项（第 10 节）      → 40 条错误对照
```

**与 README 的分工**：README 给结论与边界，本文件负责语法穷举与运行时事实。冲突时以本文件为准。

## 1. 为什么需要类型标注

### 1.1 注解是元数据，不是校验

```python
def build(tool: str, results: list[str], limit: int = 3) -> dict[str, Any]:
    return {"tool": tool, "items": results[:limit]}

print(build.__annotations__)
```

本机实测输出：

```text
{'tool': <class 'str'>, 'results': list[str], 'limit': <class 'int'>, 'return': dict[str, typing.Any]}
```

传错类型照样能进函数：

```python
print("NOCHECK", build(123, "abc"))
# NOCHECK {'tool': 123, 'items': 'abc'}（实测）
```

错误要等业务代码用到才炸：

```python
try:
    build("search", ["a"], limit="x")
except TypeError as error:
    print(type(error).__name__, str(error)[:45])
# TypeError slice indices must be integers or None or hav（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 注解存在 `__annotations__` | 普通字典，可读可改 | `[Y1]` |
| 解释器不做类型检查 | 传错类型不会报错 | `[Y1]` |
| 注解可完全省略 | 语法可选 | `[Y1]` |
| 注解不影响性能 | 只在定义时求值 | `[Y1]` |

> 注意：这是最容易被误解的一点——**类型标注不是运行时校验**。外部输入（HTTP 请求、LLM 输出、文件内容）必须在服务端独立校验，不能靠注解兜底。

### 1.2 能带来的四件事

| 收益 | 具体表现 | 依据 |
| --- | --- | --- |
| 可读性 | 参数含义不用翻实现 | `[Y4]` |
| IDE 补全 | 属性、方法提示准确 | `[Y3]` |
| 静态检查 | mypy/pyright 在提交前发现错 | `[Y3]` |
| 文档即代码 | 签名就是接口说明 | `[Y4]` |

| 不能带来 | 说明 | 依据 |
| --- | --- | --- |
| 运行时不报错 | 见 1.1 | `[Y1]` |
| 自动转换类型 | 不做 coercion | `[Y1]` |
| 替代输入校验 | 仍需显式校验 | `[Y4]` |
| 保证逻辑正确 | 只保证类型自洽 | `[Y3]` |

### 1.3 类型检查器是外部工具

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| mypy / pyright 不是标准库 | 要单独安装 | `[Y4]` |
| PEP 8 明确：可忽略注解 | 不用检查器的人不受影响 | `[Y4]` |
| 注解是 PEP 484 体系 | 由类型检查器解释 | `[Y6]` |

> 注意：本机**未安装 mypy / pyright**（实测 `import importlib.util; find_spec('mypy')` → `None`），所以本文所有「静态检查」结论只作规则陈述，未在真实检查器上验证；运行时行为均已实测。

## 2. 基础类型标注

### 2.1 变量标注

```python
count: int = 1
name: str
tags: list[str] = []
```

实测模块级注解：

```text
{'count': <class 'int'>}
```

| 写法 | 含义 | 依据 |
| --- | --- | --- |
| `x: int = 1` | 标注 + 赋值 | `[Y2]` |
| `x: int` | 只标注，不赋值 | `[Y2]` |
| `x: int` 在函数内 | **不写入** `__annotations__` | `[Y2]` |
| `self.x: int` | 类体/实例属性标注 | `[Y2]` |

> 注意：函数体内的变量注解**不会**被记录到任何 `__annotations__` 里，只有模块级和类体级的会。`[Y2]`

### 2.2 函数标注

```python
def parse_limit(value: str, *, default: int = 3) -> int:
    return int(value) if value else default
```

| 位置 | 语法 | 依据 |
| --- | --- | --- |
| 位置参数 | `value: str` | `[Y1]` |
| 默认值 | `default: int = 3` | `[Y1]` |
| 仅关键字 | `*, default: int = 3` | `[Y1]` |
| 可变位置 | `*args: int` | `[Y1]` |
| 可变关键字 | `**kwargs: str` | `[Y1]` |
| 返回值 | `-> int` | `[Y1]` |
| 无返回值 | `-> None` | `[Y1]` |

```python
def collect(*values: int, **flags: str) -> list[int]:
    return list(values)
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| `*args: int` 表示每个元素是 `int` | 不是 `tuple[int]` | `[Y1]` |
| `**kwargs: str` 表示每个值是 `str` | 键总是 `str` | `[Y1]` |
| 没写返回注解 | 检查器推断为 `Any` | `[Y3]` |

### 2.3 注解的求值时机

| 时机 | 行为 | 依据 |
| --- | --- | --- |
| 函数定义时 | 注解表达式**立即求值**（默认） | `[Y1]` |
| 有 `from __future__ import annotations` | 存成字符串，延迟到 `get_type_hints` | `[Y7]` |
| 3.14 起 | 默认延迟求值（PEP 649） | `[Y7]` |

```python
def old(x: "int") -> "str":
    return str(x)

print(old.__annotations__)          # {'x': 'int', 'return': 'str'}（实测）
print(get_type_hints(old))          # {'x': <class 'int'>, 'return': <class 'str'>}（实测）
```

### 2.4 全模块字符串化

```python
from __future__ import annotations

def f(x: int, y: list[str]) -> dict[str, int]:
    return {}

print(f.__annotations__)
```

本机实测输出：

```text
{'x': 'int', 'y': 'list[str]', 'return': 'dict[str, int]'}
```

`get_type_hints(f)` 会解析回真实类型（实测 `{'x': <class 'int'>, 'y': list[str], 'return': dict[str, int]}`）。

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 注解变字符串 | 不立即求值 | `[Y7]` |
| 好处：前向引用、启动更快 | 不用引号 | `[Y7]` |
| 代价：运行时要 `get_type_hints` | 框架（如 dataclass）会自己解 | `[Y7]` |

### 2.5 `get_type_hints` 与 `__annotations__` 的区别

| 对比 | `__annotations__` | `get_type_hints()` |
| --- | --- | --- |
| 是否解析字符串 | 否 | 是 |
| 是否继承父类注解 | 否 | 是（含基类） |
| 是否处理 `Optional` | 原样 | 原样 |
| 开销 | 零 | 有（解析 + 导入） |
| 依据 | `[Y1]` | `[Y3]` |

## 3. 常用复合类型

### 3.1 `Optional` 与 `Union`

```python
print(Optional[int] == (int | None))     # True（实测）
print(Union[int, str] == (int | str))    # True（实测）
print(str(Optional[str]))                # typing.Optional[str]（实测）
print(str(int | None))                   # int | None（实测）
```

| 写法 | 含义 | 依据 |
| --- | --- | --- |
| `Optional[T]` | `T` 或 `None` | `[Y3]` |
| `Union[A, B]` | `A` 或 `B` | `[Y3]` |
| `A \| B` | 同上，3.10+ 语法 | `[Y6]` |
| `Optional[T]` ≠ 可选参数 | 可选参数靠默认值 | `[Y3]` |

```python
# 错：以为 Optional 就是可省略
def search(query: Optional[str]) -> None: ...

# 对：可省略用默认值
def search(query: str = "") -> None: ...

# 对：可能传 None
def search(query: str | None) -> None: ...
```

> 注意：`Optional[T]` 只表示「值可以是 `None`」，**不表示**「调用时可以不给这个参数」。参数可选性由默认值决定，这是最高频的误解。`[Y3]`

### 3.2 容器类型

```python
names: list[str] = []
mapping: dict[str, int] = {}
pair: tuple[int, str] = (1, "a")
variadic: tuple[int, ...] = (1, 2, 3)
unique: set[str] = set()
frozen: frozenset[int] = frozenset()
nested: list[dict[str, list[int]]] = [{}]
```

| 写法 | 含义 | 依据 |
| --- | --- | --- |
| `list[str]` | 元素都是 `str` | `[Y3]` |
| `dict[str, int]` | 键 `str`、值 `int` | `[Y3]` |
| `tuple[int, str]` | 定长、逐位类型 | `[Y3]` |
| `tuple[int, ...]` | 变长、同类型 | `[Y3]` |
| `set[str]` | 可哈希元素 | `[Y3]` |
| `Sequence[int]` | 只读序列（list/tuple 都行） | `[Y3]` |
| `Mapping[str, int]` | 只读映射 | `[Y3]` |
| `Iterable[int]` | 只要能迭代 | `[Y3]` |

| 旧写法（3.8 及以前） | 新写法（3.9+） | 依据 |
| --- | --- | --- |
| `List[str]` | `list[str]` | `[Y3]` |
| `Dict[str, int]` | `dict[str, int]` | `[Y3]` |
| `Tuple[int, ...]` | `tuple[int, ...]` | `[Y3]` |
| `Set[int]` | `set[int]` | `[Y3]` |

实测两者**并不相等**：

```python
import typing
print(dict[str, int] == typing.Dict[str, int])    # False（实测）
```

> 注意：混用新老写法不报错，但用 `==` 比较类型对象会得到 `False`；不要在运行时比较类型，用 `get_origin` / `get_args`。`[Y3]`

### 3.3 `Any` 与传染性

```python
def loose(x: Any) -> Any:
    return x

print(get_type_hints(loose))    # {'x': typing.Any, 'return': typing.Any}（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `Any` 与所有类型兼容 | 检查器不做约束 | `[Y3]` |
| `Any` 会传染 | 从 `Any` 取属性仍是 `Any` | `[Y3]` |
| `object` 比 `Any` 安全 | 取属性会被检查 | `[Y3]` |

| 场景 | 该用什么 | 依据 |
| --- | --- | --- |
| 真的什么都能接受 | `object` | `[Y3]` |
| 暂时不知道怎么标 | `Any` + TODO | `[Y4]` |
| 外部未标注库的返回值 | `Any` + 边界封装 | `[Y3]` |
| 想绕过检查 | 先问为什么 | `[Y4]` |

### 3.4 类型别名

```python
type Vector = list[float]
print(type(Vector).__name__, Vector.__value__)
# TypeAliasType list[float]（实测）
```

| 写法 | 版本 | 依据 |
| --- | --- | --- |
| `Vector = list[float]` | 全版本（隐式别名） | `[Y3]` |
| `Vector: TypeAlias = list[float]` | 3.10+（显式） | `[Y3]` |
| `type Vector = list[float]` | 3.12+（PEP 695） | `[Y6]` |

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| PEP 695 别名是独立对象 | 类型是 `TypeAliasType` | `[Y6]` |
| 取值用 `__value__` | 不是 `get_args` | `[Y6]` |
| 可延迟求值 | 支持递归别名 | `[Y6]` |

> 注意：实测 `get_args(Vector)` 返回 `()`（空元组），PEP 695 别名要用 `Vector.__value__` 才能拿到真实类型；这是把「泛型」和「别名」搞混时的常见困惑。`[Y6]`

### 3.5 `Literal` / `Final` / `Annotated`

```python
mode: Literal["fast", "safe"] = "fast"
MAX: Final[int] = 3
Port = Annotated[int, "1-65535"]
print(get_args(Literal["fast", "safe"]))    # ('fast', 'safe')（实测）
print(get_args(Port))                        # (<class 'int'>, '1-65535')（实测）
```

| 类型 | 作用 | 运行时效果 | 依据 |
| --- | --- | --- | --- |
| `Literal["a","b"]` | 限定字面量取值 | 无 | `[Y3]` |
| `Final[int]` | 禁止再赋值 | 无 | `[Y3]` |
| `Annotated[T, meta]` | 附加元数据 | 无（元数据可读） | `[Y3]` |

```python
# Literal 只对检查器有效，运行时仍可传别的值
mode: Literal["fast", "safe"] = "slow"    # 检查器报错，运行时不报
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `Final` 运行时不阻止赋值 | 只是约定 | `[Y3]` |
| `Annotated` 元数据可取 | 框架可读（如 FastAPI） | `[Y3]` |
| `Literal` 不能用于复杂对象 | 只支持字面量 | `[Y3]` |

### 3.6 `TypedDict`

```python
class ToolConfig(TypedDict):
    name: str
    timeout: int

cfg: ToolConfig = {"name": "search", "timeout": 5}
print(type(cfg).__name__, ToolConfig.__annotations__)
# dict {'name': <class 'str'>, 'timeout': <class 'int'>}（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 运行时就是普通 `dict` | 不创建类实例 | `[Y3]` |
| 只检查「键和值类型」 | 不检查多余键 | `[Y3]` |
| 支持 `total=False` | 全部可选键 | `[Y3]` |
| 支持 `NotRequired` / `Required` | 单个键可选/必填 | `[Y3]` |

```python
class PartialConfig(TypedDict, total=False):
    timeout: int
    retries: int
```

| 场景 | 建议 | 依据 |
| --- | --- | --- |
| 函数返回配置字典 | `TypedDict` | `[Y3]` |
| 需要默认值或方法 | `dataclass` | `[Y3]` |
| 需要运行时校验 | pydantic 等（23 章） | `[Y3]` |

### 3.7 `NamedTuple`

```python
class Point(NamedTuple):
    x: int
    y: int

print(Point(1, 2), Point(1, 2).x)    # Point(x=1, y=2) 1（实测）
```

| 对比 | `NamedTuple` | `dataclass` |
| --- | --- | --- |
| 可迭代/可解包 | ✅ | ❌ |
| 不可变 | ✅ | ❌（默认可变） |
| 内存 | 小（tuple） | 大（有 `__dict__`） |
| 适用 | 返回值、坐标 | 有默认值/方法的模型 |
| 依据 | `[Y3]` | `[Y3]` |

### 3.8 `get_origin` 与 `get_args`

```python
print(get_origin(list[str]), get_args(dict[str, int]), get_args(tuple[int, ...]))
# <class 'list'> (<class 'str'>, <class 'int'>) (<class 'int'>, Ellipsis)（实测）
```

| 函数 | 作用 | 依据 |
| --- | --- | --- |
| `get_origin(list[str])` | 取外层类型 `list` | `[Y3]` |
| `get_args(dict[str, int])` | 取参数元组 | `[Y3]` |
| `get_args(tuple[int, ...])` | 变长用 `Ellipsis` | `[Y3]` |
| `get_args(Literal["a"])` | 取字面量值 | `[Y3]` |

### 3.9 运行时不能 `isinstance` 泛型

```python
try:
    isinstance([], list[int])
except TypeError as error:
    print(type(error).__name__, str(error)[:50])
# TypeError isinstance() argument 2 cannot be a parameterized（实测）
```

| 写法 | 结果 | 依据 |
| --- | --- | --- |
| `isinstance(x, list)` | ✅ | `[Y3]` |
| `isinstance(x, list[int])` | ❌ `TypeError` | `[Y3]` |
| `isinstance(x, int \| None)` | ✅ 3.10+ 支持 | `[Y6]` |
| 要判断元素 | 遍历 + `isinstance` | `[Y3]` |

## 4. 类与自定义类型

### 4.1 类名即类型

```python
class Base: ...

class Child(Base): ...

def take(value: Base) -> None: ...

take(Child())     # 运行时不检查，传谁都行
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 类可作注解 | 表示「该类的实例」 | `[Y3]` |
| 子类兼容父类 | 名义子类型 | `[Y3]` |
| 传错不报错 | 运行时无检查 | `[Y1]` |

### 4.2 前向引用

```python
class Node:
    def __init__(self, next_node: "Node | None" = None) -> None:
        self.next = next_node

print(Node(Node()).next is not None)    # True（实测）
```

| 写法 | 说明 | 依据 |
| --- | --- | --- |
| `"Node"` | 字符串，延迟解析 | `[Y3]` |
| `from __future__ import annotations` | 全模块字符串化 | `[Y7]` |
| `if TYPE_CHECKING: import x` | 只给检查器看 | `[Y3]` |

### 4.3 `Self`（3.11+）

```python
class Builder:
    def set(self) -> Self:
        return self

print(type(Builder().set()).__name__)    # Builder（实测）
```

| 对比 | 返回 `"Builder"` | 返回 `Self` |
| --- | --- | --- |
| 子类调用 | 类型退化为 `Builder` | 保持子类类型 |
| 适用 | 不打算被继承 | 链式 API |
| 依据 | `[Y3]` | `[Y3]` |

### 4.4 `dataclass` 与属性标注

```python
@dataclass
class Msg:
    role: str
    content: str = ""

print([field.name for field in fields(Msg)], Msg("user"))
# ['role', 'content'] Msg(role='user', content='')（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `dataclass` 读 `__annotations__` 生成 `__init__` | 注解是数据源 | `[Y3]` |
| 无默认值的字段必须在前 | 语法顺序 | `[Y3]` |
| 可变默认值要用 `field(default_factory=...)` | 否则报错 | `[Y3]` |

## 5. 泛型

### 5.1 `TypeVar`

```python
T = TypeVar("T")

def first(items: list[T]) -> T:
    return items[0]

print(first([1, 2]), first(["a"]))    # 1 a（实测）
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| `TypeVar` 表达「同一类型」 | 输入输出关联 | `[Y3]` |
| 名字要与变量一致 | `TypeVar("T")` | `[Y3]` |
| 运行时无约束 | 传混类型也不报 | `[Y3]` |

### 5.2 `bound` 与约束

```python
Num = TypeVar("Num", bound=int)          # 必须是 int 或其子类
StrOrInt = TypeVar("StrOrInt", str, int) # 只能是这两个
print(Num.__bound__)                      # <class 'int'>（实测）
```

| 形式 | 含义 | 依据 |
| --- | --- | --- |
| `TypeVar("T")` | 任意类型 | `[Y3]` |
| `TypeVar("T", bound=X)` | `X` 或子类 | `[Y3]` |
| `TypeVar("T", A, B)` | `A` 或 `B`（约束） | `[Y3]` |

### 5.3 泛型类（PEP 695）

```python
class Box[T]:
    def __init__(self, item: T) -> None:
        self.item = item

    def get(self) -> T:
        return self.item

print(Box[int](1).get(), Box.__type_params__)
# 1 (T,)（实测）
```

| 写法 | 版本 | 依据 |
| --- | --- | --- |
| `class Box(Generic[T])` | 3.8+ | `[Y3]` |
| `class Box[T]` | 3.12+ | `[Y6]` |
| `def pair[T](a: T, b: T) -> tuple[T, T]` | 3.12+ | `[Y6]` |

### 5.4 `Protocol`：结构化子类型

```python
class SupportsClose(Protocol):
    def close(self) -> None: ...

@runtime_checkable
class SupportsCloseRC(Protocol):
    def close(self) -> None: ...

class Conn:
    def close(self) -> None: ...

print(isinstance(Conn(), SupportsCloseRC), isinstance(object(), SupportsCloseRC))
# True False（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 不需要继承 | 只要方法签名匹配 | `[Y5]` |
| 静态检查器认 | 结构性判断 | `[Y5]` |
| `runtime_checkable` 才能 `isinstance` | 只查方法存在，不查签名 | `[Y5]` |
| 与 ABC 分工 | Protocol 静态、ABC 运行时 | `[Y5]` |

| 场景 | 用 | 依据 |
| --- | --- | --- |
| 只想约束「有这个方法」 | `Protocol` | `[Y5]` |
| 需要在运行时 `isinstance` 强制 | ABC（19 章） | `[Y5]` |
| 第三方类无法继承 | `Protocol` | `[Y5]` |

### 5.5 协变与逆变

| 概念 | 含义 | 例子 | 依据 |
| --- | --- | --- | --- |
| 协变 `covariant=True` | 子类型关系同向 | `Sequence[Child]` 可当 `Sequence[Base]` | `[Y3]` |
| 逆变 `contravariant=True` | 反向 | `Callable` 的参数 | `[Y3]` |
| 不变（默认） | 无子类型关系 | `list` | `[Y3]` |

> 注意：`list[Child]` **不能**当 `list[Base]` 用（因为可以往里塞 `Base`）；想要只读语义用 `Sequence`。`[Y3]`

## 6. `Callable` 与回调函数

### 6.1 基本写法

```python
def apply(fn: Callable[[int], str], value: int) -> str:
    return fn(value)

print(apply(str, 42), get_args(Callable[[int], str]))
# 42 ([<class 'int'>], <class 'str'>)（实测）
```

| 写法 | 含义 | 依据 |
| --- | --- | --- |
| `Callable[[int], str]` | 收一个 `int`，返回 `str` | `[Y3]` |
| `Callable[..., str]` | 任意参数，返回 `str` | `[Y3]` |
| `Callable[[], None]` | 无参无返回 | `[Y3]` |
| `collections.abc.Callable` | 同上，可用于 `isinstance` | `[Y3]` |

```python
Handler = Callable[[dict[str, Any]], Awaitable[str]]
```

### 6.2 `ParamSpec`：保留装饰器签名

```python
from typing import ParamSpec

P = ParamSpec("P")

def logged(fn: Callable[P, str]) -> Callable[P, str]:
    def wrapper(*args: P.args, **kwargs: P.kwargs) -> str:
        return fn(*args, **kwargs)
    return wrapper
```

| 工具 | 解决什么 | 依据 |
| --- | --- | --- |
| `functools.wraps` | 运行时签名/文档 | 13 章 |
| `ParamSpec` | 静态签名保持 | `[Y3]` |
| `Concatenate` | 前置额外参数 | `[Y3]` |

### 6.3 `@overload`

```python
@overload
def double(x: int) -> int: ...

@overload
def double(x: str) -> str: ...

def double(x):
    return x + x

print(double(2), double("a"), double.__annotations__)
# 4 aa {}（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `@overload` 版本只是给检查器看 | 运行时被最后的实现覆盖 | `[Y3]` |
| 最终实现**必须**存在且无 `@overload` | 否则运行时返回 `None` | `[Y3]` |
| 实现上的注解常被忽略 | 实测 `__annotations__` 为空 | `[Y3]` |

> 注意：`@overload` 只写声明不写实现，运行时调用会得到 `None`（因为函数体是 `...`）；这是新手最常见的运行时事故。`[Y3]`

## 7. 应用场景

### 7.1 API 接口定义

```python
class ToolResult(TypedDict):
    name: str
    ok: bool
    detail: str


def call_tool(name: str, payload: dict[str, Any]) -> ToolResult:
    ...
```

| 收益 | 说明 | 依据 |
| --- | --- | --- |
| 调用双方契约明确 | 不用读实现 | `[Y4]` |
| 重构安全 | 检查器报错 | `[Y3]` |
| 文档自动生成 | 签名即文档 | `[Y4]` |

### 7.2 配合 IDE 获得补全

| 场景 | 标注前 | 标注后 | 依据 |
| --- | --- | --- | --- |
| `dict` 取值 | 只提示 `dict` 方法 | `TypedDict` 提示键 | `[Y3]` |
| 函数返回值 | `Any`，无提示 | 精确到型号方法 | `[Y3]` |
| `Protocol` 参数 | 无提示 | 提示协议方法 | `[Y5]` |

### 7.3 静态检查器（未实测）

| 工具 | 语言 | 速度 | 依据 |
| --- | --- | --- | --- |
| mypy | Python 生态最主流 | 中 | `[Y3]` |
| pyright | TypeScript 实现 | 快 | `[Y3]` |
| pytype | Google 出品 | 中 | `[Y3]` |

```powershell
# 需要先安装，本机未装，故本节未实测
python -m pip install mypy
python -m mypy src/
```

> 注意：本机 **mypy / pyright 均未安装**（实测），上表只作选型参考；文档中的「检查器会报错」均为规则陈述，不是你机器上的实际结果。

### 7.4 接进 CI

| 步骤 | 建议 | 依据 |
| --- | --- | --- |
| 增量推进 | 先只检查新增文件 | `[Y4]` |
| 从 `--strict` 起步 | 新项目直接严格 | `[Y4]` |
| 老项目 | 逐步收紧，先 `disallow_untyped_defs` | `[Y4]` |
| 与格式化/测试并列 | 失败即阻断合并 | `[Y4]` |

## 8. 忽略类型检查

### 8.1 `# type: ignore`

```python
ignored: int = "not int"  # type: ignore[assignment]
print(ignored)            # not int（实测，运行时无任何效果）
```

| 写法 | 作用 | 依据 |
| --- | --- | --- |
| `# type: ignore` | 整行忽略 | `[Y3]` |
| `# type: ignore[assignment]` | 只忽略指定错误码 | `[Y3]` |
| 放在语句上一行 | 不生效（必须同行） | `[Y3]` |

### 8.2 `TYPE_CHECKING`

```python
from typing import TYPE_CHECKING

print(TYPE_CHECKING)      # False（实测，运行时恒为 False）

if TYPE_CHECKING:
    from expensive_module import HeavyType
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 运行时恒为 `False` | 只给检查器看 | `[Y3]` |
| 用于避免循环导入 | 只在注解里引用 | `[Y3]` |
| 配合字符串注解 | 运行时不求值 | `[Y7]` |

### 8.3 `cast`

```python
from typing import cast

raw: Any = {"name": "search"}
config = cast(dict[str, str], raw)
```

| 工具 | 语义 | 运行时 | 依据 |
| --- | --- | --- | --- |
| `cast(T, v)` | 告诉检查器「当作 T」 | 原样返回，不检查 | `[Y3]` |
| `# type: ignore` | 压制这一行 | 无 | `[Y3]` |
| `assert isinstance(...)` | 真检查 + 收窄 | 会执行 | `[Y3]` |

| 选择 | 何时用 | 依据 |
| --- | --- | --- |
| `cast` | 确定类型但检查器推不出 | `[Y3]` |
| `isinstance` 收窄 | 需要运行时保证 | `[Y3]` |
| `ignore` | 第三方 stub 有误 | `[Y4]` |

### 8.4 `Any` 与 ignore 的取舍

| 做法 | 影响范围 | 建议 | 依据 |
| --- | --- | --- | --- |
| 参数标 `Any` | 该参数及其下游全失效 | 少用 | `[Y3]` |
| `# type: ignore` | 只影响一行 | 优先，但需注释原因 | `[Y4]` |
| `cast` | 只影响该表达式 | 次选 | `[Y3]` |
| 改设计 | 从根上消除 | 最优 | `[Y4]` |

## 9. 综合示例：带类型的工具调用层

```python
"""第 20 章综合示例：TypedDict + Protocol + 泛型 + 返回类型。"""

from dataclasses import dataclass
from typing import Any, Protocol, TypedDict


class ToolResult(TypedDict):
    name: str
    ok: bool
    detail: str


class SupportsRun(Protocol):
    def run(self, payload: dict[str, Any]) -> ToolResult: ...


@dataclass
class Tool:
    name: str
    hits: int = 0

    def run(self, payload: dict[str, Any]) -> ToolResult:
        self.hits += 1
        return {"name": self.name, "ok": True, "detail": str(payload.get("q", ""))}


def execute(tool: SupportsRun, payload: dict[str, Any]) -> ToolResult:
    return tool.run(payload)


tool = Tool("search")
print("RESULT", execute(tool, {"q": "AI"}))
print("HITS", tool.hits)
print("SIG", Tool.run.__annotations__)
```

本机实测输出：

```text
RESULT {'name': 'search', 'ok': True, 'detail': 'AI'}
HITS 1
SIG {'payload': dict[str, typing.Any], 'return': ToolResult}
```

**逐段说明**：

| 代码 | 用到的机制 | 依据 |
| --- | --- | --- |
| `TypedDict` | 结构化返回值 | `[Y3]` |
| `Protocol` | 不继承也能表达「能 run」 | `[Y5]` |
| `dataclass` + 注解 | 自动 `__init__` | `[Y3]` |
| `dict[str, Any]` | 容器泛型 | `[Y3]` |
| 返回 `ToolResult` | 接口契约 | `[Y4]` |

> 注意：`execute` 运行时**不会**检查 `tool` 是否真有 `run`；传个 `object()` 进去会得到 `AttributeError`，而不是类型错误。`[Y1]`

## 10. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 以为注解会校验 | 传错类型不报错 | 显式 `if not isinstance` / pydantic | `[Y1]` |
| `Optional[T]` 当可选参数 | 调用不传仍报 `TypeError` | 用默认值 `= None` | `[Y3]` |
| `x: list = []` | 丢失元素类型 | `x: list[str] = []` | `[Y3]` |
| `dict` / `list` 裸写 | 检查器无从判断 | 写元素类型 | `[Y3]` |
| 用 `Any` 消除报错 | 传染下游 | 具体类型或 `object` | `[Y3]` |
| `isinstance(x, list[int])` | `TypeError` | 判 `list` 再遍历 | `[Y3]` |
| `dict[str,int] == typing.Dict` | `False` | 用 `get_origin` | `[Y3]` |
| `get_args` 取 PEP 695 别名 | 空元组 | `Alias.__value__` | `[Y6]` |
| `@overload` 不写实现 | 运行时返回 `None` | 补最终实现 | `[Y3]` |
| `@overload` 实现也加装饰器 | `None` | 实现不加 | `[Y3]` |
| 装饰器不加 `wraps` | 签名/文档丢失 | `functools.wraps` | 13 章 |
| 装饰器后 `__annotations__` 消失 | 包装函数无注解 | `wraps` 会拷贝 | `[Y3]` |
| 前向引用不加引号 | `NameError` | `"Node"` 或 future import | `[Y3]` |
| `Final` 以为运行时报错 | 照样能改 | 只是约定 | `[Y3]` |
| `Literal` 传别的值 | 运行时不报 | 自己校验 | `[Y3]` |
| `TypedDict` 以为会校验键 | 多余键照样在 | 手动校验 | `[Y3]` |
| `TypedDict` 里用默认值 | 语法不支持 | 用 `dataclass` | `[Y3]` |
| `NamedTuple` 想加方法 | 可以，但别改字段 | 用 `dataclass` | `[Y3]` |
| `Protocol` 直接 `isinstance` | `TypeError` | 加 `@runtime_checkable` | `[Y5]` |
| `runtime_checkable` 以为查签名 | 只查方法名 | 别依赖它校验 | `[Y5]` |
| `list[Child]` 当 `list[Base]` | 检查器报错 | 用 `Sequence[Base]` | `[Y3]` |
| `Callable` 不写参数 | 只能写 `...` | `Callable[..., R]` | `[Y3]` |
| `TypeVar` 名字与变量不一致 | 检查器报错 | 保持一致 | `[Y3]` |
| `TypeVar` 用于单个参数 | 无意义 | 至少两处 | `[Y3]` |
| 函数内变量注解 | 不进 `__annotations__` | 别指望反射 | `[Y2]` |
| `from __future__ import annotations` 后又用 `get_type_hints` 取不到 | 未导入类型 | 确保类型可导入 | `[Y7]` |
| 注解里调用函数 | 定义时执行一次 | 用字符串/别名 | `[Y1]` |
| 注解里写复杂表达式 | 求值开销/副作用 | 提前定义别名 | `[Y1]` |
| `cast` 当校验用 | 运行时不变 | `isinstance` | `[Y3]` |
| `# type: ignore` 不给原因 | 掩盖真问题 | 加 `[code]` 与注释 | `[Y4]` |
| `Any` 出现在公共 API | 契约失效 | `object` / `Protocol` | `[Y3]` |
| `-> None` 写成 `-> NoneType` | 检查器不认 | `None` | `[Y3]` |
| 返回注解写成 `-> "None"` | 字符串误用 | `-> None` | `[Y3]` |
| 用注解做参数校验 | 外部输入未校验 | 服务端独立校验 | `[Y4]` |
| `dict[str, Any]` 传用户输入 | 注入/类型混乱 | 逐字段校验 | `[Y4]` |
| 注解里放敏感信息 | 泄露到文档 | 只写类型 | `[Y4]` |
| 老代码全量 `# type: ignore` | 检查形同虚设 | 增量推进 | `[Y4]` |
| 用 `typing.List` 混 `list` | 比较结果不一致 | 统一一种 | `[Y3]` |
| 忘了 `from __future__` 就写 `X \| Y` | 3.10 以下 `TypeError` | 用 `Optional`/`Union` | `[Y6]` |
| 异步函数标 `-> str` | 实际返回协程 | `-> Awaitable[str]` / `async def` 标 `-> str` | `[Y3]` |

## 11. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 公共 API 必标 | 内部一次性脚本可省 | `[Y4]` |
| 容器一定写元素类型 | 否则等于 `Any` | `[Y3]` |
| 用 `Sequence`/`Mapping` 作参数 | 调用方更自由 | `[Y3]` |
| 用 `Protocol` 表达能力 | 少用具体类 | `[Y5]` |
| 返回类型必写 | 尤其 `-> None` | `[Y4]` |
| `# type: ignore` 必带原因 | 便于复查 | `[Y4]` |
| 注解写不出来先简化设计 | 别塞 `Any` | `[Y4]` |
| 新项目直接 PEP 695 | 3.12+ 更简洁 | `[Y6]` |
| 静态检查进 CI | 但不阻塞紧急修复 | `[Y4]` |
| 注解与文档同步 | 改签名就改文档 | `[Y4]` |

**风格示范**：

```python
from collections.abc import Iterable
from typing import Protocol


class SupportsRun(Protocol):
    def run(self, payload: dict[str, str]) -> str:
        """执行工具并返回文本结果。"""


def run_all(tools: Iterable[SupportsRun], payload: dict[str, str]) -> list[str]:
    """依次执行，任一失败即抛出。

    为什么参数用 Iterable 而不是 list：调用方可能传生成器。
    """
    return [tool.run(payload) for tool in tools]
```

**空格格式**（PEP 8）：

| 位置 | 正确 | 错误 | 依据 |
| --- | --- | --- | --- |
| 参数注解 | `def f(x: int)` | `def f(x:int)` | `[Y4]` |
| 返回注解 | `-> int` | `->int` | `[Y4]` |
| 有默认值时 | `x: int = 1` | `x: int=1` | `[Y4]` |
| 变量注解 | `x: int = 1` | `x : int = 1` | `[Y4]` |

## 12. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[Y1]` | python.org | https://docs.python.org/3.12/tutorial/controlflow.html | 函数注解是可选元数据、存 `__annotations__`、不影响运行时 |
| `[Y2]` | PEP 官方 | https://peps.python.org/pep-0526/ | 变量注解语法与作用域 |
| `[Y3]` | python.org | https://docs.python.org/3.12/library/typing.html | `Optional`/`Union`/`Protocol`/`TypeVar`/`ParamSpec`/`TypedDict`/`Literal`/`Final`/`Annotated`/`cast`/`overload` |
| `[Y4]` | PEP 官方 | https://peps.python.org/pep-0008/ | 注解空格规则、检查器是可选工具、不使用者可忽略 |
| `[Y5]` | PEP 官方 | https://peps.python.org/pep-0544/ | Protocol 与结构化子类型 |
| `[Y6]` | PEP 官方 | https://peps.python.org/pep-0695/ | `type X = ...`、`class C[T]`、`def f[T]()` |
| `[Y7]` | PEP 官方 | https://peps.python.org/pep-0563/ | `from __future__ import annotations` 与延迟求值；PEP 649 演进 |
| `[Y8]` | python.org | https://docs.python.org/3.12/library/typing.html#typing.get_type_hints | `get_type_hints` 解析字符串与继承注解 |

> **核对状态**：`[Y1]` `[Y4]` 与本章 `README.md` 已核对来源一致；其余按 `docs.python.org/3.12` 与 `peps.python.org` 官方结构整理，**本次未逐页直连复核**。mypy/pyright **未安装未实测**，文中「检查器会报错」为规则陈述；其余「实测」结论为本机 Python 3.12.8 运行结果。

## 13. 毕业自查清单

**能说清（概念层）**：

- [ ] 注解为什么不影响运行时，存在哪里
- [ ] `Optional[T]` 与「有默认值」的区别
- [ ] `list[str]` 与 `Sequence[str]` 的取舍
- [ ] `Any` 为什么危险、`object` 为什么更安全
- [ ] 类型别名三种写法与版本
- [ ] `TypedDict` 运行时是什么
- [ ] `Protocol` 与 ABC 的分工
- [ ] `TypeVar` 表达什么关系
- [ ] `Callable[[int], str]` 的含义
- [ ] `@overload` 为什么必须跟实现
- [ ] `cast` 与 `isinstance` 的区别
- [ ] `from __future__ import annotations` 改变了什么

**能写出（代码层）**：

- [ ] 带默认值、`*args`、`->` 的完整函数签名
- [ ] `TypedDict` 版接口返回值
- [ ] `Protocol` + `runtime_checkable` 的能力约束
- [ ] 泛型函数 `first(items: list[T]) -> T`
- [ ] PEP 695 的 `type` 别名与 `class Box[T]`
- [ ] `Literal` 限定模式字符串
- [ ] `dataclass` + 注解 + `field(default_factory=...)`
- [ ] `ParamSpec` 装饰器

**能判断（避坑层）**：

- [ ] 看到 `Optional` 当可选参数能指出错误
- [ ] 看到裸 `list` / `dict` 能指出丢信息
- [ ] 看到 `isinstance(x, list[int])` 能指出 `TypeError`
- [ ] 看到 `@overload` 无实现能指出运行时 `None`
- [ ] 看到 `Any` 满屏能指出契约失效
- [ ] 看到 `# type: ignore` 无原因能要求说明
- [ ] 看到 `cast` 当校验用能指出运行时不变

**能跑通（验收层）**：

- [ ] 运行 `examples/typing_demo.py` 并解释 `__annotations__`
- [ ] 把第 9 节示例存成文件运行，输出与文档一致
- [ ] 在 REPL 验证「传错类型不报错」
- [ ] 在 REPL 验证 `get_type_hints` 能解析字符串注解

## 14. 下一章衔接

第 21 章 `模块化`：注解让「单个文件内的接口」清晰，模块化让「跨文件边界」清晰——`import` 到底做了什么、包怎么组织、循环导入怎么解。

本章留下的伏笔：

1. 前向引用需要 `TYPE_CHECKING` + 字符串注解，第 21 章讲循环导入时会再遇到。
2. `Protocol` 的结构化判断依赖「能导入到类型」，模块布局会影响可导入性。
3. `Annotated` 的元数据常被框架用于声明配置，第 23 章的第三方库会大量使用。