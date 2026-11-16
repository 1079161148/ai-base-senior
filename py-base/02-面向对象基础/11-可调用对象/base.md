# 11 可调用对象 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把截图里的「如何判断可调用、如何让对象可调用、两个应用场景」逐条展开，并补上可调用家族、`__call__` 与 `__init__` 的区别、与闭包/`partial` 的取舍，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测） |
| 前置 | 第 05–10 章（函数、作用域、lambda、类、创建过程） |
| 覆盖范围 | `obj(...)` 的等价形式、`callable()`、`__call__`、可调用家族、可配置函数对象、状态保持回调、与闭包/`partial` 的对比 |
| 明确不覆盖 | 装饰器（13）、`functools.partial` 细节（22）、元类（12）、描述符（15） |
| 学完验收 | 能判断任意对象是否可调用、能写出带配置与计数的可调用类、能说清何时用类而非闭包（见第 10 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Kn]` `` 指向第 9 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果。

**推荐顺序**：

```text
1 什么是可调用对象（第 1 节）→ obj(...) 的本质
2 如何判断（第 2 节）        → callable() 与它的局限
3 让对象可调用（第 3 节）    → __call__ 的写法
4 实际场景（第 4 节）        → 可配置函数对象、状态回调、与闭包对比
5 与类的关系（第 5 节）      → 类可调用、方法可调用、元类
6 综合示例（第 6 节）
7 注意事项（第 7 节）        → 28 条错误对照
```

**与 README 的分工**：README 讲概念，本文件负责穷举场景与边界。冲突时以本文件为准。

## 1. 什么是可调用对象

**定义**：能被 `()` 调用的对象就是可调用对象；`obj(args)` 等价于 `type(obj).__call__(obj, args)`。`[K1]`

```python
class Adder:
    def __init__(self, base):
        self.base = base

    def __call__(self, value):
        return self.base + value

add10 = Adder(10)
print(add10(5))                              # 15（实测）
print(type(add10).__call__(add10, 5))        # 15，等价写法（实测）
```

| 要素 | 说明 | 依据 |
| --- | --- | --- |
| 调用语法 | `obj(args)` | `[K5]` |
| 实际调用 | `type(obj).__call__(obj, args)` | `[K1]` |
| 必要条件 | 类型上有 `__call__` | `[K1]` |
| 注意 | `__call__` 定义在**类**上，不是实例上 | `[K1]` |

### 1.1 可调用家族

| 类别 | 例子 | `callable` | 依据 |
| --- | --- | --- | --- |
| 内置函数 | `len`、`print`、`sorted` | `True` | `[K2]` |
| 用户函数 | `def f(): ...` | `True` | `[K2]` |
| lambda | `lambda x: x` | `True` | `[K2]` |
| 方法 | `obj.method` | `True` | `[K2]` |
| 类 | `Adder` | `True`（调用即实例化） | `[K2]` |
| 带 `__call__` 的实例 | `add10` | `True` | `[K2]` |
| 普通实例 | `Adder.__new__(Adder)` | `False` | `[K2]` |
| 数字 / 字符串 | `1`、`"a"` | `False` | `[K2]` |

```python
print(callable(len), callable(lambda x: x), callable(Adder), callable(Adder(1)))
# True True True True（实测）
print(callable(1), callable("a"), callable(1.5), callable(None))
# False False False False
```

### 1.2 为什么能统一

| 机制 | 说明 | 依据 |
| --- | --- | --- |
| 函数是对象 | 有类型 `function` | `[K1]` |
| 方法也是对象 | 绑定方法持有 `__self__` | `[K1]` |
| 类也是对象 | 调用类 = 实例化（第 10 章） | `[K1]` |
| 实例也可调用 | 实现 `__call__` | `[K1]` |

> 注意：`callable(x)` 为真只说明「能调用」，不保证「参数对」；参数不匹配仍会 `TypeError`。`[K2]`

## 2. 如何判断对象是否可调用

### 2.1 `callable()`

```python
def plain(value):
    return value

class NotCallable:
    def run(self):
        return "run"

print(callable(plain))              # True（实测）
print(callable(NotCallable()))      # False（实测）
print(callable(NotCallable().run))  # True（实测）
print(callable(dict()))             # False（实测）
print(callable(dict))               # True（实测）
```

| 参数 | 返回 | 依据 |
| --- | --- | --- |
| 任意对象 | `bool` | `[K2]` |
| 类 | `True`（调用即实例化） | `[K2]` |
| 带 `__call__` 的实例 | `True` | `[K2]` |
| 内置类型实例 | 视类型而定（`dict()` 为 `False`） | `[K2]` |

### 2.2 不要用 `hasattr` 代替

```python
print(hasattr(len, "__call__"))      # True
print(hasattr(1, "__call__"))        # False
```

| 写法 | 是否推荐 | 依据 |
| --- | --- | --- |
| `callable(x)` | ✅ 语义准确 | `[K2]` |
| `hasattr(x, "__call__")` | ❌ 只是「有这个属性」，可能被代理或同名属性干扰 | `[K2]` |

> 注意：`callable` 是对「调用协议」的直接判断，`hasattr` 是属性查找；两者在代理对象上可能不一致。`[K2]`

### 2.3 判断的局限

```python
try:
    add10()
except TypeError as error:
    print(type(error).__name__)   # TypeError：缺参数
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 可调用 ≠ 参数正确 | 仍需签名匹配 | `[K1]` |
| 无法预先知道签名 | 需要 `inspect`（第 22 章） | `[K1]` |
| 测试要覆盖参数错误 | 否则线上才暴露 | `[K3]` |

## 3. 让对象变成可调用对象

### 3.1 定义 `__call__`

```python
class Adder:
    def __init__(self, base):
        self.base = base

    def __call__(self, value):
        return self.base + value

add10 = Adder(10)
print(add10(5))     # 15
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 写在类体里 | 实例才可调用 | `[K1]` |
| 第一个参数是 `self` | 与普通方法一致 | `[K1]` |
| 其余参数由调用方传 | 与函数一致 | `[K1]` |
| 返回值即调用结果 | 无限制 | `[K1]` |

### 3.2 支持任意参数

```python
class Flex:
    def __call__(self, *args, **kwargs):
        return args, kwargs

print(Flex()(1, 2, key="v"))    # ((1, 2), {'key': 'v'})
```

| 写法 | 适用 | 依据 |
| --- | --- | --- |
| `__call__(self, a, b)` | 固定签名 | `[K1]` |
| `__call__(self, *args, **kwargs)` | 转发型 | `[K1]` |
| `__call__(self, /, *, ...)` | 仅位置/仅关键字 | `[K1]` |

### 3.3 与普通方法共存

```python
class Tool:
    def __init__(self, name):
        self.name = name
        self.calls = 0

    def __call__(self, argument):
        self.calls += 1
        return f"{self.name}:{argument}"

    def reset(self):
        self.calls = 0

search = Tool("search")
print(search("AI"))        # search:AI
print(search.calls)        # 1
search.reset()
print(search.calls)        # 0
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 可调用实例仍可有普通方法 | 不冲突 | `[K1]` |
| `obj()` 与 `obj.method()` 并存 | 语义不同 | `[K1]` |
| 建议 `__call__` 只做「核心行为」 | 其他用命名方法 | `[K3]` |

### 3.4 `__call__` 与 `__init__` 的区别

| 维度 | `__init__` | `__call__` |
| --- | --- | --- |
| 触发时机 | 实例化时一次 | 每次调用时 |
| 第一个参数 | `self`（新实例） | `self`（已有实例） |
| 返回值 | 必须 `None` | 任意 |
| 目的 | 初始化状态 | 执行行为 |
| 依据 | `[K1]` | `[K1]` |

```python
class Demo:
    def __init__(self):
        print("init 一次")

    def __call__(self):
        print("call 每次")

d = Demo()    # init 一次
d()           # call 每次
d()           # call 每次
```

> 注意：把重逻辑放 `__init__` 会让「创建」变重；放 `__call__` 才能多次执行。`[K3]`

## 4. 实际应用场景

### 4.1 实现可配置的函数对象

```python
class Retry:
    def __init__(self, func, attempts=3, delay=0.0):
        self.func = func
        self.attempts = attempts
        self.delay = delay

    def __call__(self, *args, **kwargs):
        last_error = None
        for _ in range(self.attempts):
            try:
                return self.func(*args, **kwargs)
            except Exception as error:      # 教学示例：实际应捕获具体异常（第 16 章）
                last_error = error
        raise last_error

runner = Retry(int, attempts=2)
print(runner("42"))     # 42
```

| 配置 | 存在哪 | 依据 |
| --- | --- | --- |
| `func` | 实例属性 | `[K1]` |
| `attempts` | 实例属性 | `[K1]` |
| 多次调用复用配置 | 实例长期存活 | `[K1]` |

**对比闭包**：

```python
def make_retry(func, attempts=3):
    def runner(*args, **kwargs):
        last_error = None
        for _ in range(attempts):
            try:
                return func(*args, **kwargs)
            except Exception as error:
                last_error = error
        raise last_error
    return runner
```

| 维度 | 可调用类 | 闭包 |
| --- | --- | --- |
| 配置可见性 | 实例属性，可查看/修改 | 藏在 cell 里 |
| 可测试性 | 可单独测 `__call__` | 只能测整体 |
| 可扩展 | 加方法容易 | 只能加函数 |
| 代码量 | 多几行 | 少 |
| 依据 | `[K1]` | `[K1]` |

> 注意：配置多、需要多方法、需要被继承时用类；一次性小逻辑用闭包或 `lambda`（第 07 章）。`[K3]`

### 4.2 实现状态保持的回调函数

```python
class Counter:
    def __init__(self):
        self.count = 0

    def __call__(self):
        self.count += 1
        return self.count

counter = Counter()
print(counter(), counter(), counter.count)   # 1 2 2（实测）
```

| 场景 | 说明 | 依据 |
| --- | --- | --- |
| 事件回调计数 | 每次触发累加 | `[K1]` |
| 限流器 | 记录上次调用时间 | `[K1]` |
| 缓存装饰 | 保存最近结果 | `[K1]` |
| 状态机 | 保存当前状态 | `[K1]` |

**带状态的限流示例**：

```python
class RateLimiter:
    def __init__(self, limit=2):
        self.limit = limit
        self.calls = 0

    def __call__(self):
        if self.calls >= self.limit:
            return False
        self.calls += 1
        return True

limiter = RateLimiter(2)
print([limiter() for _ in range(3)])   # [True, True, False]
```

| 优势 | 说明 | 依据 |
| --- | --- | --- |
| 状态显式 | `limiter.calls` 可查看 | `[K1]` |
| 多实例独立 | 每个 limiter 自己计数 | `[K1]` |
| 可序列化配置 | 属性可读 | `[K1]` |

> 注意：状态放在实例属性里，多线程下要加锁（第 28 章）；回调里做重 I/O 也要考虑超时。`[K3]`

### 4.3 与 `functools.partial` 的取舍

```python
import functools

def add(a, b):
    return a + b

add10 = functools.partial(add, 10)
print(add10(5), callable(add10))    # 15 True（实测）
```

| 方案 | 适用 | 依据 |
| --- | --- | --- |
| `partial` | 只固定部分参数 | `[K4]` |
| `lambda x: add(10, x)` | 一次性地固定 | `[K4]` |
| 可调用类 | 需要状态、方法、文档 | `[K1]` |

> 注意：`partial` 不支持「调用时改配置」，也不方便加计数；需要这些就用类。`[K4]`

## 5. 可调用对象与类

### 5.1 类本身可调用

```python
class Tool:
    def __init__(self, name):
        self.name = name

print(callable(Tool))       # True（实测）
print(callable(Tool("x")))  # False，普通实例不可调用（实测）
```

| 对象 | 可调用 | 调用结果 | 依据 |
| --- | --- | --- | --- |
| 类 | ✅ | 实例化 | `[K1]` |
| 普通实例 | ❌ | `TypeError` | `[K1]` |
| 带 `__call__` 的实例 | ✅ | 执行 `__call__` | `[K1]` |

### 5.2 方法可调用

```python
print(callable(Tool.__init__), callable(Tool("x").__init__))   # True True
```

| 形式 | 绑定 | 依据 |
| --- | --- | --- |
| `obj.method` | 已绑定 `self` | `[K1]` |
| `Class.method` | 未绑定，需传实例 | `[K1]` |
| `Class.method(obj)` | 等价于 `obj.method()` | `[K1]` |

### 5.3 两个 `__call__` 别混

| 层 | 谁定义 | 作用 | 依据 |
| --- | --- | --- | --- |
| 元类 `__call__` | 元类（如 `type`） | 控制「类被调用」（实例化） | `[K1]` |
| 实例 `__call__` | 普通类 | 控制「实例被调用」 | `[K1]` |

```text
Tool("x")     → type(Tool).__call__(Tool, "x")   → 实例化
tool("arg")   → type(tool).__call__(tool, "arg") → 实例的 __call__
```

> 注意：看到 `__call__` 先问「是谁的 `__call__`」：定义在普通类上是调用实例，定义在元类上是调用类。`[K1]`

## 6. 综合示例：带重试的可调用包装器

```python
"""第 11 章综合示例：可配置 + 带状态的可调用对象。"""


class RetryRunner:
    def __init__(self, func, attempts=3):
        self.func = func
        self.attempts = attempts
        self.calls = 0

    def __call__(self, *args, **kwargs):
        for index in range(1, self.attempts + 1):
            self.calls += 1
            try:
                return self.func(*args, **kwargs)
            except ValueError:
                if index == self.attempts:
                    raise


runner = RetryRunner(lambda value: int(value), attempts=2)
print("可调用:", callable(runner))
print("结果:", runner("42"), "调用次数:", runner.calls)
try:
    runner("x")
except ValueError:
    print("失败调用次数:", runner.calls)
```

本机实测输出：

```text
可调用: True
结果: 42 调用次数: 1
失败调用次数: 3
```

**逐段说明**：

| 代码 | 用到的机制 | 依据 |
| --- | --- | --- |
| `__init__` 存配置 | 实例属性 | `[K1]` |
| `__call__` 执行 | 每次调用 | `[K1]` |
| `self.calls += 1` | 状态保持 | `[K1]` |
| 最后一次失败 `raise` | 保留原始异常 | `[K1]` |
| `callable(runner)` | 判断可调用 | `[K2]` |

**调用次数为什么是 3**：

| 调用 | 尝试 | 累加后 `calls` |
| --- | --- | --- |
| `runner("42")` | 第 1 次成功 | 1 |
| `runner("x")` | 第 1 次失败 | 2 |
| `runner("x")` | 第 2 次失败并抛出 | 3 |

> 注意：示例里捕获 `ValueError` 是为了演示「按异常类型重试」；生产代码不要 `except Exception` 无差别重试（第 16 章）。`[K3]`

## 7. 注意事项与新手错误对照表

| 错误写法 / 操作 | 报错或现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `obj()` 但类没 `__call__` | `TypeError: not callable` | 定义 `__call__` | `[K1]` |
| `__call__` 忘写 `self` | `TypeError` | 第一个参数 `self` | `[K1]` |
| 在实例上赋值 `__call__` | 无效（特殊方法查类型） | 定义在类上 | `[K1]` |
| `callable(x)` 为真就直接调用 | 参数不匹配 `TypeError` | 校验签名/捕获 | `[K2]` |
| `hasattr(x, "__call__")` 代替 | 代理对象上误判 | `callable(x)` | `[K2]` |
| `callable(实例)` 当「有方法」 | 普通实例为 `False` | 看具体方法 | `[K2]` |
| 以为类不可调用 | 实际调用即实例化 | 记住类可调用 | `[K1]` |
| `__call__` 里做重 I/O | 调用点变慢 | 拆分或异步（第 30 章） | `[K3]` |
| `__call__` 有隐藏副作用 | 调用点看不出状态变了 | 文档写明 | `[K3]` |
| 用 `__call__` 代替所有方法 | 意图不清 | 命名方法 | `[K3]` |
| `__call__` 与 `__init__` 混淆 | 重逻辑在构造里 | 行为放 `__call__` | `[K1]` |
| 可调用实例当函数传参 | 默认参数求值时机 | 传实例本身 | `[K1]` |
| 多线程共享实例计数 | 数据竞争 | 加锁（第 28 章） | `[K1]` |
| `__call__` 返回 `self` 做链式 | 可能意外 | 明确文档 | `[K3]` |
| 重试里 `except Exception` | 吞掉不该重试的错误 | 具体异常 | `[K3]` |
| 重试无退避 | 打爆下游 | 加 delay/backoff | `[K3]` |
| 用可调用类替代简单函数 | 过度设计 | 普通函数 | `[K3]` |
| `partial` 当可配置对象 | 不能改配置 | 用类 | `[K4]` |
| `callable` 判断后不处理失败 | 线上异常 | `try/except` | `[K2]` |
| 把 `__call__` 写成 `__call` | 不可调用 | 双下划线 | `[K1]` |
| `__call__` 无 docstring | 调用方不知语义 | 写 docstring | `[K3]` |
| 回调里捕获所有异常 | 掩盖 bug | 只处理已知 | `[K3]` |
| 状态放类属性 | 所有实例共享 | 放实例属性 | `[K1]` |
| 回调持有大对象 | 内存不释放 | 只捕获必要 | `[K3]` |
| 可调用对象被当函数序列化 | 失败 | 用 `__reduce__`（第 22 章） | `[K4]` |
| `callable(None)` 以为真 | 实际 `False` | 记住返回值 | `[K2]` |
| 元类 `__call__` 与实例 `__call__` 混 | 控制层级错 | 区分对象 | `[K1]` |
| 用 `__call__` 做单例 | 语义不对 | 用 `__new__`（第 10 章） | `[K1]` |

## 8. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 单一行为、无状态用函数 | 不过度设计 | `[K3]` |
| 有配置、有状态用可调用类 | 显式、可测 | `[K1]` |
| 只固定参数用 `partial` | 最轻量 | `[K4]` |
| `__call__` 只做核心行为 | 其他用命名方法 | `[K3]` |
| 状态放实例属性 | 不要放类属性 | `[K1]` |
| 为 `__call__` 写 docstring | 说明副作用与返回 | `[K3]` |
| 重试只捕具体异常 | 避免吞错 | `[K3]` |
| 判断可调用用 `callable` | 语义准确 | `[K2]` |
| 回调要可取消/可观测 | 加计数或日志 | `[K3]` |
| 并发场景加锁 | 状态共享 | `[K1]` |

**风格示范**：

```python
class RetryRunner:
    """把函数包装成「可重试的可调用对象」。

    属性：
        calls: 累计调用次数，便于观测。
    """

    def __init__(self, func, attempts: int = 3) -> None:
        if attempts < 1:
            raise ValueError("attempts 至少为 1")
        self.func = func
        self.attempts = attempts
        self.calls = 0

    def __call__(self, *args, **kwargs):
        """执行包装函数；失败按 attempts 重试。"""
        for index in range(1, self.attempts + 1):
            self.calls += 1
            try:
                return self.func(*args, **kwargs)
            except ValueError:
                if index == self.attempts:
                    raise
```

**安全与边界**：

- 不要把用户输入直接当回调名去 `getattr` 调用（白名单）。
- 重试要有上限与退避，避免放大故障。
- 回调里不要打印敏感参数（第 01 章安全底线）。

## 9. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[K1]` | python.org | https://docs.python.org/3.12/reference/datamodel.html | `__call__` 语义、`obj(args)` 等价形式、方法绑定、元类 `__call__`、描述符绑定 |
| `[K2]` | python.org | https://docs.python.org/3.12/library/functions.html#callable | `callable()` 定义与返回语义 |
| `[K3]` | PEP 官方 | https://peps.python.org/pep-0008/ | 命名、注释写「为什么」、简单可读优先 |
| `[K4]` | python.org | https://docs.python.org/3.12/library/functools.html | `functools.partial` 等可调用工具、`wraps` 保留元数据 |
| `[K5]` | python.org | https://docs.python.org/3.12/reference/expressions.html | 调用表达式的求值语义 |
| `[K6]` | GitHub 官方 | https://github.com/python/cpython/blob/main/Doc/reference/datamodel.rst | 官方语言参考源文件（`[K1]` 页脚 Show Source 指向） |
| `[K7]` | PEP 官方 | https://peps.python.org/pep-0020/ | The Zen of Python（显式、简单） |

> **核对状态**：`[K1]` `[K3]` 与本章 `README.md` 已核对来源一致；其余链接按 `docs.python.org/3.12` 与 `peps.python.org` 官方结构整理，**本次未逐页直连复核**。文中「实测」结论均为本机 Python 3.12.8 运行结果。

## 10. 毕业自查清单

**能说清（概念层）**：

- [ ] `obj(args)` 实际调用了什么
- [ ] `callable()` 判断的是什么，为什么它不等于「参数合适」
- [ ] 为什么 `callable(SomeClass)` 为真
- [ ] `__call__` 与 `__init__` 的触发时机与返回值差异
- [ ] 元类 `__call__` 与实例 `__call__` 的区别
- [ ] 可调用类相对闭包、`partial` 的优势与代价
- [ ] 状态放在实例属性与类属性的差别

**能写出（代码层）**：

- [ ] 一个带配置的可调用类（如 `Adder`）
- [ ] 一个带计数的回调类（如 `Counter`）
- [ ] 一个带限流的可调用对象
- [ ] 一个带重试的可调用包装器（含 `calls` 计数）
- [ ] 用 `partial` 固定参数并与类版本对比
- [ ] 用 `callable` 判断并安全调用

**能判断（避坑层）**：

- [ ] 看到 `obj()` 报 `not callable` 能定位到没写 `__call__`
- [ ] 看到在实例上赋值 `__call__` 能指出无效
- [ ] 看到 `hasattr(x, "__call__")` 能建议改 `callable`
- [ ] 看到 `except Exception` 重试能指出吞错风险
- [ ] 看到计数放类属性能指出所有实例共享
- [ ] 看到用 `__call__` 做单例能指出应该用 `__new__`

**能跑通（验收层）**：

- [ ] 运行 `examples/callable_demo.py` 并解释五行输出
- [ ] 把第 6 节示例存成文件运行，输出与文档一致
- [ ] 在 REPL 验证「`callable(类)` 为真、`callable(普通实例)` 为假」
- [ ] 手写「可配置 + 计数 + 重试」的可调用对象并测试失败路径

## 11. 下一章衔接

第 13 章 `装饰器`：可调用对象 + 闭包 +「函数也是对象」三者合起来，就是装饰器的全部基础。

本章留下的三个伏笔：

1. 装饰器本质是「接收函数、返回可调用对象」的高阶函数；返回的既可以是闭包，也可以是本章的可调用实例。
2. `functools.wraps` 保留的是被包装函数的 `__name__` / `__doc__`（第 08 章的函数属性）。
3. 带参数的装饰器是「三层可调用」结构，本章的 `__call__` 与配置存储是它的原型。

按课程顺序：第 12 章先讲元类（理解 `type` 如何控制类创建），第 13 章再讲装饰器；本章的 `__call__` 是两章之间的桥。