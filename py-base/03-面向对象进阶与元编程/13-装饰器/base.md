# 13 装饰器 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把截图里的「装饰器的本质、多个装饰器叠加」逐条展开，并补上 `functools.wraps`、带参装饰器、类装饰器、方法装饰、内置装饰器与实战模式，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测） |
| 前置 | 第 05–07、11 章（函数、作用域、闭包、可调用对象） |
| 覆盖范围 | `@` 语法糖、装饰器本质、`wraps`、堆叠顺序、带参装饰器、类装饰器、实例装饰器、方法装饰、内置装饰器、五种实战模式 |
| 明确不覆盖 | 描述符绑定细节（15）、`ParamSpec` 类型标注（20）、异步装饰器（27）、`import` 机制（21） |
| 学完验收 | 能手写带参装饰器、能说清堆叠顺序、能解释 `wraps` 保住了什么（见第 12 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Dn]` `` 指向第 11 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果。

**推荐顺序**：

```text
1 装饰器的本质（第 1 节）→ @ 只是语法糖
2 最小装饰器（第 2 节）  → 模板与三个必写点
3 functools.wraps（第 3 节）→ 元数据不能丢
4 多个装饰器叠加（第 4 节）→ 应用顺序 vs 执行顺序
5 带参数的装饰器（第 5 节）→ 三层结构
6 装饰器家族（第 6 节）  → 函数/类/实例/方法/内置
7 实战模式（第 7 节）    → 日志、计时、重试、缓存、权限、注册
8 综合示例（第 8 节）
9 注意事项（第 9 节）    → 32 条错误对照
```

**与 README 的分工**：README 给结论，本文件负责机制、顺序与避坑。冲突时以本文件为准。

## 1. 装饰器的本质

### 1.1 `@` 是语法糖

```python
@decorator
def func():
    ...

# 完全等价于
def func():
    ...
func = decorator(func)
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `@` 只是改写赋值 | 不改变函数体 | `[D1]` |
| 名字最终指向返回值 | 不是原函数 | `[D1]` |
| 可以做多层 | 等价嵌套调用 | `[D1]` |

```python
def upper(func):
    def wrapper():
        return func().upper()
    return wrapper

@upper
def greet():
    return "hello"

print(greet())        # HELLO
print(greet.__name__) # wrapper，元数据丢了（第 3 节解决）
```

### 1.2 求值时机：函数定义时

```python
def make_deco(label):
    print("求值装饰器表达式", label)
    def decorator(func):
        def wrapper(*args, **kwargs):
            return func(*args, **kwargs)
        return wrapper
    return decorator

@make_deco("A")
def target():
    pass

print("定义完成")
```

实测输出顺序：

```text
求值装饰器表达式 A
定义完成
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 装饰器表达式在**定义时**求值 | 不是调用时 | `[D1]` |
| 被装饰函数定义后立即替换 | 此时已完成包装 | `[D1]` |
| 导入模块即执行 | 不要在装饰器里做重 I/O | `[D4]` |

> 注意：这就是「装饰器在 import 时跑一遍」的原因；把 `@make_deco(load_config())` 写在模块顶层，会在导入时加载配置。`[D1]`

### 1.3 装饰器接收什么、返回什么

| 被装饰对象 | 装饰器收到 | 应返回 | 依据 |
| --- | --- | --- | --- |
| 函数 | 函数对象 | 可调用对象 | `[D2]` |
| 类 | 类对象 | 类（或可调用对象） | `[D5]` |
| 方法 | 函数对象 | 可调用对象 | `[D2]` |

| 返回值 | 后果 | 依据 |
| --- | --- | --- |
| 新的可调用对象 | 正常使用 | `[D2]` |
| 原函数 | 相当于「只做副作用」，如注册 | `[D2]` |
| `None` | 名字变成 `None`，调用时报 `TypeError` | `[D2]` |

### 1.4 为什么能「记住」原函数

```python
def log(func):
    def wrapper(*args, **kwargs):
        print("调用", func.__name__)
        return func(*args, **kwargs)
    return wrapper
```

`wrapper` 是闭包，通过 cell 持有 `func`——这是第 06 章「闭包」的直接应用。`[D2]`

| 机制 | 说明 | 依据 |
| --- | --- | --- |
| 闭包 | `wrapper` 捕获 `func` | 第 06 章 |
| 函数是对象 | 可作参数、可返回 | `[D1]` |
| 可调用对象也可被装饰 | 见第 11 章 | 第 11 章 |

## 2. 最小装饰器

### 2.1 三个必写点

```python
import functools

def log_call(func):
    """记录调用并保留元数据。"""
    @functools.wraps(func)              # ③ 保留元数据
    def wrapper(*args, **kwargs):       # ② 透传参数
        print("调用:", func.__name__)
        return func(*args, **kwargs)    # ① 返回原函数结果
    return wrapper

@log_call
def search(query):
    """搜索。"""
    return ["r:" + query]

print(search("AI"))          # 调用: search / ['r:AI']
```

| 必写点 | 漏掉的后果 | 依据 |
| --- | --- | --- |
| `return func(...)` | 调用方拿到 `None` | `[D2]` |
| `*args, **kwargs` | 参数不匹配 `TypeError` | `[D2]` |
| `@functools.wraps` | `__name__` 变成 `wrapper` | `[D3]` |

### 2.2 忘 `return` 是最高频 bug

```python
import functools

def broken(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        func(*args, **kwargs)      # 忘了 return
    return wrapper

@broken
def add(a, b):
    return a + b

print(add(1, 2))    # None
```

| 现象 | 原因 | 依据 |
| --- | --- | --- |
| 返回值变 `None` | wrapper 没返回 | `[D2]` |
| 不报错 | 语法完全合法 | `[D2]` |
| 排查 | 检查 wrapper 最后一行 | `[D4]` |

### 2.3 参数透传的几种形态

| 原函数签名 | wrapper 写法 | 依据 |
| --- | --- | --- |
| 无参 | `def wrapper():` | `[D2]` |
| 固定参数 | `def wrapper(a, b):` 不推荐 | `[D2]` |
| 任意参数 | `def wrapper(*args, **kwargs):` | `[D2]` |
| 仅关键字 | 仍用 `*args, **kwargs` | `[D2]` |

> 注意：不要为了「看起来精确」把参数写死；一旦原函数签名变化，wrapper 就会 `TypeError`。`[D4]`

## 3. `functools.wraps`

### 3.1 不用 `wraps` 会丢什么

```python
import functools

def no_wraps(func):
    def wrapper(*args, **kwargs):
        return func(*args, **kwargs)
    return wrapper

@no_wraps
def plain(query):
    """plain doc"""
    return query

print(plain.__name__, plain.__doc__)
# wrapper None（实测）
```

| 丢失项 | 后果 | 依据 |
| --- | --- | --- |
| `__name__` | 日志、调试器显示 `wrapper` | `[D3]` |
| `__doc__` | 帮助文档变 `None` | `[D3]` |
| `__module__` / `__qualname__` | 错误堆栈定位错 | `[D3]` |
| `__annotations__` | 类型提示丢失 | `[D3]` |
| `__wrapped__` | 无法追溯原函数 | `[D3]` |

### 3.2 `wraps` 之后

```python
@log_call
def search(query):
    """搜索。"""
    return ["r:" + query]

print(search.__name__)          # search（实测）
print(search.__doc__)           # 搜索。（实测）
print(hasattr(search, "__wrapped__"))   # True（实测）
print(search.__wrapped__("x"))  # 直接调原函数
```

| 项 | 结果 | 依据 |
| --- | --- | --- |
| `__name__` | 原函数名 | `[D3]` |
| `__doc__` | 原 docstring | `[D3]` |
| `__wrapped__` | 指向原函数 | `[D3]` |

### 3.3 `wraps` 不是万能的

| 它能做 | 它做不到 | 依据 |
| --- | --- | --- |
| 复制元数据 | 改变真实调用签名 | `[D3]` |
| 设置 `__wrapped__` | 让 IDE 精确推断参数类型 | `[D3]` |
| 保留 `__dict__` 更新 | 处理异步函数 | 第 27 章 |

> 注意：`inspect.signature` 会沿 `__wrapped__` 找原签名，所以 `wraps` 后大多正常；但静态检查器需要 `ParamSpec` 才能精确标注（第 20 章）。`[D3]`

### 3.4 `update_wrapper`：给非函数对象用

```python
import functools

class CountCalls:
    def __init__(self, func):
        self.func = func
        self.calls = 0
        functools.update_wrapper(self, func)   # 手动复制元数据

    def __call__(self, *args, **kwargs):
        self.calls += 1
        return self.func(*args, **kwargs)

@CountCalls
def add(a, b):
    return a + b

print(add(1, 2), add.calls, add.__name__)   # 3 1 add（实测）
```

| 场景 | 用什么 | 依据 |
| --- | --- | --- |
| 装饰器返回函数 | `@functools.wraps` | `[D3]` |
| 装饰器返回类实例 | `functools.update_wrapper` | `[D3]` |

## 4. 多个装饰器叠加

### 4.1 应用顺序：自下而上

```python
@deco_a
@deco_b
def target():
    print("target")
```

等价于：

```python
target = deco_a(deco_b(target))
```

| 步骤 | 发生什么 | 依据 |
| --- | --- | --- |
| 1 | 先 `deco_b(target)` | `[D1]` |
| 2 | 再 `deco_a(...)` 包住结果 | `[D1]` |
| 3 | 名字指向最外层 wrapper | `[D1]` |

### 4.2 执行顺序：自上而下

```python
def deco_a(func):
    def wrapper(*args, **kwargs):
        print("A-before")
        result = func(*args, **kwargs)
        print("A-after")
        return result
    return wrapper

def deco_b(func):
    def wrapper(*args, **kwargs):
        print("B-before")
        result = func(*args, **kwargs)
        print("B-after")
        return result
    return wrapper

@deco_a
@deco_b
def target():
    print("target")

target()
```

本机实测输出：

```text
A-before
B-before
target
B-after
A-after
```

| 视角 | 顺序 | 记忆法 | 依据 |
| --- | --- | --- | --- |
| 应用（包装） | 从下往上 | 离 `def` 近的先包 | `[D1]` |
| 执行（进入） | 从上往下 | 最外层先动手 | `[D1]` |
| 退出 | 从下往上 | 像洋葱一层层退 | `[D1]` |

### 4.3 顺序影响行为的典型例子

| 组合 | 差异 | 依据 |
| --- | --- | --- |
| 日志 + 缓存 | 日志在外层 → 每次调用都记；内层 → 只记未命中 | `[D2]` |
| 重试 + 计时 | 计时在外层 → 含全部重试耗时 | `[D2]` |
| 权限 + 日志 | 权限在外层 → 越权请求不写调用日志 | `[D2]` |

```python
@log_calls
@timer
def search(query):
    return ["r:" + query]

# 执行顺序：LOG → TIME → search 本体
```

> 注意：堆叠顺序不是「随意」的，它决定了日志、缓存、重试、计时的语义；上线前用一次日志验证。`[D4]`

### 4.4 三次以上叠加

| 装饰器数量 | 建议 | 依据 |
| --- | --- | --- |
| 1–2 个 | 直接叠 | `[D4]` |
| 3 个以上 | 抽成一个组合装饰器 | `[D4]` |
| 顺序敏感 | 注释写清为什么这样排 | `[D4]` |

```python
import functools

def observed(func):
    """把日志 + 计时合成一个装饰器，固定顺序。"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        import time
        start = time.perf_counter()
        print("调用:", func.__name__)
        try:
            return func(*args, **kwargs)
        finally:
            print(f"耗时: {time.perf_counter() - start:.4f}s")
    return wrapper
```

## 5. 带参数的装饰器

### 5.1 三层结构

```python
def repeat(times):
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            return [func(*args, **kwargs) for _ in range(times)]
        return wrapper
    return decorator

@repeat(3)
def ping():
    return "pong"

print(ping())   # ['pong', 'pong', 'pong']（实测）
```

等价于：

```python
ping = repeat(3)(ping)
```

| 层 | 作用 | 依据 |
| --- | --- | --- |
| 第 1 层 `repeat(times)` | 接收装饰器参数 | `[D2]` |
| 第 2 层 `decorator(func)` | 接收被装饰函数 | `[D2]` |
| 第 3 层 `wrapper(*args)` | 实际调用逻辑 | `[D2]` |

### 5.2 参数校验与默认值

```python
def repeat(times=2):
    if not isinstance(times, int) or times < 1:
        raise ValueError("times 必须是正整数")
    ...
```

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 参数在装饰器创建时校验 | 早失败 | `[D4]` |
| 给默认值 | 允许 `@repeat` 与 `@repeat(3)` 两种写法？见 5.3 | `[D2]` |
| 不把配置写死 | 走参数或环境变量 | `[D4]` |

### 5.3 「可选参数」写法

```python
import functools

def retry(func=None, *, attempts=3):
    def decorate(target):
        @functools.wraps(target)
        def wrapper(*args, **kwargs):
            for index in range(1, attempts + 1):
                try:
                    return target(*args, **kwargs)
                except ValueError:
                    if index == attempts:
                        raise
        return wrapper

    if func is None:
        return decorate          # 带参用法：@retry(attempts=5)
    return decorate(func)        # 无参用法：@retry

@retry
def plain():
    return "ok"

@retry(attempts=5)
def configured():
    return "ok"

print(plain(), configured())   # ok ok
```

| 写法 | 支持 | 依据 |
| --- | --- | --- |
| `def retry(func)` | `@retry` | `[D2]` |
| `def retry(attempts=3)` | `@retry(5)`，不支持裸 `@retry` | `[D2]` |
| `def retry(func=None, *, attempts=3)` | 两种都支持 | `[D2]` |

> 注意：最后一种写法灵活但可读性下降，非公共 API 不建议；`*` 用来强制关键字参数，避免位置参数混淆。`[D4]`

## 6. 装饰器家族

### 6.1 函数装饰器

最常见的形态，前面各节已覆盖。`[D2]`

### 6.2 类装饰器

接收类、返回类（或替换类）。`[D5]`

```python
def add_repr(cls):
    cls.__repr__ = lambda self: f"<{cls.__name__} instance>"
    return cls

@add_repr
class Box:
    pass

print(repr(Box()))   # <Box instance>（实测）
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 收到的是类 | 可增删属性 | `[D5]` |
| 返回类或新类 | 调用方无感 | `[D5]` |
| 与元类对比 | 更显式 | `[D5]` |

```python
def frozen(cls):
    def no_setattr(self, name, value):
        raise AttributeError("不允许修改")
    cls.__setattr__ = no_setattr
    return cls
```

> 注意：在类装饰器里改 `__setattr__` 会连 `__init__` 里的赋值一起禁掉；需要「构造后冻结」得加开关，复杂度会上升。`[D5]`

### 6.3 类实例作装饰器

```python
class CountCalls:
    def __init__(self, func):
        self.func = func
        self.calls = 0
        functools.update_wrapper(self, func)

    def __call__(self, *args, **kwargs):
        self.calls += 1
        return self.func(*args, **kwargs)

@CountCalls
def add(a, b):
    return a + b

print(add(1, 2), add.calls, add.__name__)   # 3 1 add（实测）
```

| 优势 | 说明 | 依据 |
| --- | --- | --- |
| 状态显式 | `add.calls` 可查看 | `[D3]` |
| 支持多方法 | 可加 `reset()` | `[D3]` |
| 可继承 | 类可扩展 | `[D3]` |

### 6.4 装饰方法：`self` 去哪了

```python
import functools

def trace(func):
    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        return f"traced:{func(self, *args, **kwargs)}"
    return wrapper

class Service:
    @trace
    def run(self, x):
        return x

print(Service().run("a"))   # traced:a（实测）
```

| 错误写法 | 现象 | 依据 |
| --- | --- | --- |
| `def wrapper(*args)` 但不传 `self` | `TypeError: missing 1 required positional argument` | `[D1]` |
| 用 `@staticmethod` 包方法 | 失去绑定 | `[D1]` |
| 装饰在类外定义后不绑定 | 调用时多传一个 | `[D1]` |

> 注意：装饰器作用在**函数**上，之后函数作为类属性被绑定成方法；`self` 是调用时自动传的第一个参数，所以 wrapper 必须留出 `self` 位置。`[D1]`

### 6.5 内置与标准库装饰器

| 装饰器 | 作用 | 等价于 | 依据 |
| --- | --- | --- | --- |
| `@property` | getter | `property(fget)` | `[D3]` |
| `@staticmethod` | 去绑定 | `staticmethod(f)` | `[D3]` |
| `@classmethod` | 绑定类 | `classmethod(f)` | `[D3]` |
| `@functools.lru_cache` | 缓存 | `lru_cache(maxsize)(f)` | `[D3]` |
| `@functools.cache` | 无上限缓存（3.9+） | `lru_cache(None)` | `[D3]` |
| `@dataclasses.dataclass` | 生成 `__init__` / `__repr__` | 类装饰器 | `[D8]` |
| `@contextlib.contextmanager` | 生成器转上下文管理器 | 装饰器 | 第 18 章 |

```python
class P:
    @property
    def value(self):
        return 1

    @staticmethod
    def s():
        return "s"

    @classmethod
    def c(cls):
        return cls.__name__

print(P().value, P.s(), P.c())   # 1 s P（实测）
```

```python
@functools.lru_cache(maxsize=None)
def slow(n):
    return n * 2

print(slow(2), slow(2), slow.cache_info().hits)   # 4 4 1（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `lru_cache` 缓存按参数 | 参数必须可哈希 | `[D3]` |
| 命中次数可查 | `cache_info()` | `[D3]` |
| 参数含 list → `TypeError` | 不可哈希 | `[D3]` |

## 7. 实战模式

### 7.1 日志

```python
def log_call(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print("调用:", func.__name__)
        return func(*args, **kwargs)
    return wrapper
```

| 注意 | 说明 | 依据 |
| --- | --- | --- |
| 不要打印参数中的敏感信息 | 密码/令牌 | `[D4]` |
| 用 `logging` 而非 `print` | 可分级、可关闭 | 第 22 章 |
| 记录异常 | `try/finally` 或 `except` | 第 16 章 |

### 7.2 计时

```python
import functools
import time

def timer(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            print("TIME", func.__name__, f"{time.perf_counter() - start:.4f}s")
    return wrapper
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 用 `perf_counter` | 单调时钟，不受系统时间调整影响 | `[D3]` |
| `finally` 保证记录 | 异常也计时 | `[D3]` |
| 不要用 `time.time()` 测耗时 | 可能被回拨 | `[D3]` |

### 7.3 重试（必须有上限）

```python
def retry(attempts=3, *, exceptions=(ValueError,)):
    if attempts < 1:
        raise ValueError("attempts 至少为 1")

    def decorate(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            for index in range(1, attempts + 1):
                try:
                    return func(*args, **kwargs)
                except exceptions:
                    if index == attempts:
                        raise
        return wrapper
    return decorate
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 只捕具体异常 | 别 `except Exception` | `[D4]` |
| 次数有上限 | 防死循环 | `[D4]` |
| 最终要抛出 | 不能静默吞错 | `[D4]` |
| 加退避 | 避免打爆下游 | 第 28 章 |

### 7.4 缓存

```python
@functools.lru_cache(maxsize=128)
def load_profile(user_id):
    ...
```

| 场景 | 方案 | 依据 |
| --- | --- | --- |
| 纯函数 | `lru_cache` | `[D3]` |
| 需要过期 | 自建缓存或第三方库 | `[D3]` |
| 参数不可哈希 | 先转 tuple/str | `[D3]` |

### 7.5 权限校验

```python
def require_role(role):
    def decorate(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            user = kwargs.get("user")
            if user is None or user.get("role") != role:
                raise PermissionError(f"需要角色: {role}")
            return func(*args, **kwargs)
        return wrapper
    return decorate
```

| 注意 | 说明 | 依据 |
| --- | --- | --- |
| 权限校验必须在服务端 | 前端只影响体验 | `[D4]` |
| 装饰器里拿不到请求上下文时别硬猜 | 显式传参 | `[D4]` |
| 失败信息不泄露内部细节 | 只说明缺什么权限 | `[D4]` |

### 7.6 注册表（返回原函数）

```python
handlers = {}

def register(name):
    def decorate(func):
        handlers[name] = func
        return func          # 返回原函数，不改行为
    return decorate

@register("search")
def search(payload):
    return "search:" + payload

print(sorted(handlers), search("AI"))   # ['search'] search:AI
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 可以返回原函数 | 装饰器不一定要包装 | `[D2]` |
| 副作用发生在定义时 | 注册发生在 import | `[D1]` |
| 便于测试 | 可直接调用原函数 | `[D4]` |

## 8. 综合示例：日志 + 计时

```python
"""第 13 章综合示例：两个装饰器叠加。"""

import functools
import time


def log_calls(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print("LOG", func.__name__)
        return func(*args, **kwargs)
    return wrapper


def timer(func):
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            print("TIME", func.__name__, f"{time.perf_counter() - start:.4f}s")
    return wrapper


@log_calls
@timer
def search(query):
    return ["r:" + query]


print("结果:", search("AI"))
```

本机实测输出（时间值随机器变化）：

```text
LOG search
TIME search 0.0000s
结果: ['r:AI']
```

**逐段说明**：

| 代码 | 用到的机制 | 依据 |
| --- | --- | --- |
| `@log_calls` 在外层 | 先应用 `timer`，再包 `log_calls` | `[D1]` |
| `LOG` 先打印 | 外层 wrapper 先进入 | `[D1]` |
| `TIME` 后打印 | 内层 `finally` 在返回时执行 | `[D3]` |
| `wraps` 两处都写 | 元数据不丢 | `[D3]` |

**顺序换成 `@timer` 在外会怎样**：

```text
TIME search 0.0000s   ← 计时包含日志开销
结果: ['r:AI']
LOG search            ← finally 之后才打印
```

> 注意：这个例子说明「叠加顺序改变语义」；如果你要测「纯函数耗时」，计时应尽量贴近函数本体（放在最内层）。`[D4]`

## 9. 注意事项与新手错误对照表

| 错误写法 / 操作 | 报错或现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| wrapper 忘 `return` | 返回值变 `None` | `return func(...)` | `[D2]` |
| 不写 `*args, **kwargs` | `TypeError` | 透传参数 | `[D2]` |
| 不写 `@functools.wraps` | `__name__` 变 `wrapper` | 加 `wraps` | `[D3]` |
| 装饰器返回值写成 `None` | 名字变 `None` | 返回可调用对象 | `[D2]` |
| 装饰器在调用时才求值 | 以为能动态生效 | 定义时就执行 | `[D1]` |
| 在装饰器里做网络请求 | 导入变慢/失败 | 移到函数体 | `[D4]` |
| 堆叠顺序记反 | 日志/缓存语义错 | 自下而上应用 | `[D1]` |
| 以为执行顺序也是自下而上 | 观察结果不符 | 执行自上而下 | `[D1]` |
| 带参装饰器少一层 | `TypeError` | 三层结构 | `[D2]` |
| `@retry(3)` 写成 `@retry` | 参数被当函数 | 分清两种签名 | `[D2]` |
| 用 `lambda` 当 wrapper | 缺 `wraps`、无 docstring | 命名函数 | `[D4]` |
| 装饰方法时 wrapper 少 `self` | `TypeError` | 第一个参数 `self` | `[D1]` |
| 用 `@staticmethod` 包实例方法 | 绑定丢失 | 普通 wrapper | `[D1]` |
| 类装饰器返回 `None` | 类名变 `None` | 返回类 | `[D5]` |
| 类装饰器里改 `__setattr__` | `__init__` 也失效 | 加开关 | `[D5]` |
| `lru_cache` 参数含 list | `TypeError: unhashable` | 转 tuple | `[D3]` |
| `lru_cache` 缓存可变对象 | 结果被污染 | 只缓存不可变返回 | `[D3]` |
| 重试无上限 | 死循环 | `attempts` | `[D4]` |
| 重试 `except Exception` | 吞掉不该重试的错 | 具体异常 | `[D4]` |
| 重试最终不抛 | 失败被掩盖 | 最后一次 `raise` | `[D4]` |
| 权限装饰器只查前端标记 | 越权 | 服务端校验 | `[D4]` |
| 日志打印密码/令牌 | 泄露 | 脱敏 | `[D4]` |
| `time.time()` 计时 | 可能为负 | `perf_counter` | `[D3]` |
| 计时不放 `finally` | 异常时无记录 | `finally` | `[D3]` |
| 装饰器有状态用全局变量 | 难测试、线程不安全 | 类实例或显式注入 | `[D4]` |
| `@register` 后以为函数被替换 | 实际返回原函数 | 看返回值 | `[D2]` |
| 动态添加装饰器 | 语法不允许运行时加 `@` | `f = deco(f)` | `[D1]` |
| 装饰器改变签名后靠 IDE 提示 | 提示不准 | 用 `wraps` / `ParamSpec` | `[D3]` |
| 异步函数用同步 wrapper | 返回 coroutine 未被 await | 写异步装饰器 | 第 27 章 |
| 装饰器捕获实例导致内存不释放 | 内存增长 | 弱引用或避免持有 | `[D4]` |
| 多个装饰器顺序敏感却不注释 | 后来者改坏 | 注释说明 | `[D4]` |
| 在 `__init__` 里给实例加装饰器 | 无效（方法已在类上） | 装饰类方法 | `[D1]` |

## 10. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 三个必写点固定 | `wraps` / 透传 / `return` | `[D2]` `[D3]` |
| 装饰器只做横切关注点 | 日志、计时、重试、缓存、权限 | `[D4]` |
| 优先用标准库 | `lru_cache`、`contextlib`、`dataclass` | `[D3]` `[D8]` |
| 顺序敏感就注释 | 说明为什么这样叠 | `[D4]` |
| 参数校验放在装饰器创建时 | 早失败 | `[D4]` |
| 重试有上限、有退避、有具体异常 | 不吞错 | `[D4]` |
| 命名表达意图 | `retry` / `log_call` / `require_role` | `[D4]` |
| 公共装饰器写 docstring | 说明改变了什么 | `[D4]` |
| 能不用装饰器就不用 | 直接调用更易读 | `[D4]` |
| 类装饰器优先于元类 | 更显式 | `[D5]` |

**风格示范**：

```python
import functools
import time


def timer(func):
    """记录函数耗时（含异常路径）。

    为什么用 perf_counter：单调时钟，不受系统时间回拨影响。
    """

    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        try:
            return func(*args, **kwargs)
        finally:
            elapsed = time.perf_counter() - start
            print(f"{func.__name__} 耗时 {elapsed:.4f}s")

    return wrapper
```

**边界**：

- 装饰器里的日志不能打印参数原文（密码、令牌、个人数据）。
- 装饰器在 import 期执行，不能依赖「main 之后才有的资源」。
- 异步函数的装饰器要 `async def wrapper` 并 `await`，否则协程不会被驱动（第 27 章）。

## 11. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[D1]` | python.org | https://docs.python.org/3.12/reference/compound_stmts.html | 函数/类定义中的装饰器语法、等价赋值、堆叠应用顺序、求值时机 |
| `[D2]` | PEP 官方 | https://peps.python.org/pep-0318/ | 装饰器动机、语法、带参装饰器、类装饰器 |
| `[D3]` | python.org | https://docs.python.org/3.12/library/functools.html | `wraps` / `update_wrapper` / `__wrapped__` / `lru_cache` / `cache` / `partial` |
| `[D4]` | PEP 官方 | https://peps.python.org/pep-0008/ | 命名、注释写「为什么」、docstring、简单优先 |
| `[D5]` | PEP 官方 | https://peps.python.org/pep-3129/ | 类装饰器语法与动机 |
| `[D6]` | GitHub 官方 | https://github.com/python/cpython/blob/main/Doc/reference/compound_stmts.rst | 官方语言参考源文件（`[D1]` 页脚 Show Source 指向） |
| `[D7]` | PEP 官方 | https://peps.python.org/pep-0020/ | The Zen of Python（显式、简单） |
| `[D8]` | python.org | https://docs.python.org/3.12/library/dataclasses.html | `@dataclass` 作为标准库中最常见的类装饰器 |

> **核对状态**：`[D1]` `[D4]` 与本章 `README.md` 已核对来源一致；其余链接按 `docs.python.org/3.12` 与 `peps.python.org` 官方结构整理，**本次未逐页直连复核**。文中「实测」结论均为本机 Python 3.12.8 运行结果。

## 12. 毕业自查清单

**能说清（概念层）**：

- [ ] `@decorator` 的等价赋值形式
- [ ] 装饰器表达式在什么时候求值
- [ ] 装饰器必须做什么（接收、返回、透传、返回结果）
- [ ] `wraps` 保住了哪些元数据，`__wrapped__` 有什么用
- [ ] 多个装饰器的应用顺序与执行顺序为什么不一致
- [ ] 带参装饰器为什么需要三层
- [ ] 装饰方法时 `self` 从哪来
- [ ] 类装饰器与元类的分工

**能写出（代码层）**：

- [ ] 最小日志装饰器（含 `wraps`）
- [ ] 计时装饰器（`perf_counter` + `finally`）
- [ ] 带参的 `repeat(n)` 装饰器
- [ ] 支持 `@retry` 与 `@retry(attempts=5)` 两种用法
- [ ] 类装饰器加 `__repr__`
- [ ] 实例装饰器统计调用次数
- [ ] 装饰实例方法并验证 `self` 正确
- [ ] 注册表装饰器（返回原函数）

**能判断（避坑层）**：

- [ ] 看到 wrapper 忘 `return` 能定位「返回 `None`」
- [ ] 看到没 `wraps` 能指出 `__name__` 变 `wrapper`
- [ ] 看到堆叠顺序能预判日志/缓存语义
- [ ] 看到重试 `except Exception` 能指出吞错
- [ ] 看到 `lru_cache` 参数含 list 能指出不可哈希
- [ ] 看到同步 wrapper 包 `async def` 能指出协程未驱动

**能跑通（验收层）**：

- [ ] 运行 `examples/decorator_demo.py` 并解释「保留的函数名」
- [ ] 把第 8 节示例存成文件运行，输出顺序与文档一致
- [ ] 在 REPL 验证「去掉 `wraps` 后 `__name__` 变 `wrapper`」
- [ ] 手写「日志 + 计时」并交换顺序观察差异

## 13. 下一章衔接

第 14 章 `魔法方法`：装饰器包装的是「函数对象」，下一章往下一层——`obj(...)`、`obj[i]`、`obj + other` 这些语法该由类的哪些 `__xxx__` 承担。

本章留下的伏笔：

1. `@property` / `@staticmethod` / `@classmethod` 本身就是装饰器，它们的真身是描述符（第 15 章）。
2. `@dataclass` 是类装饰器，它生成的 `__repr__` / `__eq__` 正是第 14 章的协议方法。
3. 装饰器改的是「对象」，魔法方法改的是「语法到协议的映射」；两者共同构成 Python 的元编程基础。