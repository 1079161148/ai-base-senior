# 16 异常处理 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把截图里的「异常的捕获、异常类型、主动抛出异常、自定义异常、异常链」逐条展开，并补上 `ExceptionGroup`、`add_note`、EAFP、`finally` 陷阱等必然遇到的内容，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测） |
| 前置 | 第 05、13–15 章（函数、装饰器、协议） |
| 覆盖范围 | 异常层级、`try/except/else/finally`、异常类型、`raise`、`assert`、自定义异常、异常链、`ExceptionGroup`、`add_note`、EAFP/LBYL |
| 明确不覆盖 | `with` 资源管理（18）、生成器内 `StopIteration`（17）、异步异常（27）、日志系统（22） |
| 学完验收 | 能说清四个子句的触发条件、能写自定义异常层级、能解释 `from` 与 `__context__` 的差别（见第 12 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[En]` `` 指向第 11 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果。

**推荐顺序**：

```text
1 异常是对象（第 1 节）    → 层级与携带的信息
2 异常的捕获（第 2 节）    → 四个子句 + 六个陷阱
3 异常类型（第 3 节）      → 选对类型才能捕获对
4 主动抛出（第 4 节）      → raise / assert / fail fast
5 自定义异常（第 5 节）    → 结构化字段 + 层级设计
6 异常链（第 6 节）        → cause / context / from None
7 现代机制（第 7 节）      → ExceptionGroup / add_note / EAFP
8 综合示例（第 8 节）
9 注意事项（第 9 节）      → 40 条错误对照
```

**与 README 的分工**：README 给结论与边界，本文件负责机制穷举与判据。冲突时以本文件为准。

## 1. 异常是对象

### 1.1 一句话定义

异常是**继承自 `BaseException` 的对象**；`raise` 抛出它，`except` 按类型捕获它。`[E1]`

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 异常是类 | 可继承、可实例化 | `[E2]` |
| 抛出的是实例 | 解释器自动实例化 | `[E1]` |
| 捕获按 `isinstance` | 子类会被父类的 `except` 捕获 | `[E1]` |

### 1.2 完整层级树

```text
BaseException
├── SystemExit                    # sys.exit()
├── KeyboardInterrupt             # Ctrl+C
├── GeneratorExit                 # 生成器 close()
└── Exception                     # 绝大多数业务异常
    ├── ArithmeticError
    │   ├── ZeroDivisionError
    │   └── OverflowError
    ├── LookupError
    │   ├── IndexError
    │   └── KeyError
    ├── ValueError
    ├── TypeError
    ├── AttributeError
    ├── NameError
    │   └── UnboundLocalError
    ├── AssertionError
    ├── RuntimeError
    │   ├── RecursionError
    │   └── NotImplementedError
    ├── OSError                     # IO 错误总类
    │   ├── FileNotFoundError
    │   ├── PermissionError
    │   ├── FileExistsError
    │   ├── TimeoutError
    │   └── ConnectionError
    │       ├── ConnectionResetError
    │       └── ConnectionRefusedError
    ├── ImportError
    │   └── ModuleNotFoundError
    ├── StopIteration
    ├── StopAsyncIteration
    └── ExceptionGroup              # 3.11+
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `SystemExit` 不是 `Exception` 子类 | 实测 `issubclass(SystemExit, Exception)` → `False` | `[E2]` |
| `KeyboardInterrupt` 不是 `Exception` 子类 | 同上 | `[E2]` |
| `ValueError` 是 `Exception` 子类 | 实测 `True` | `[E2]` |

### 1.3 `BaseException` 与 `Exception`

```python
print(issubclass(SystemExit, Exception))        # False（实测）
print(issubclass(KeyboardInterrupt, BaseException))   # True（实测）
print(issubclass(ValueError, Exception))        # True（实测）
```

| 捕获写法 | 能捕获 | 依据 |
| --- | --- | --- |
| `except Exception:` | 业务异常，**不含** `SystemExit` / `KeyboardInterrupt` | `[E2]` |
| `except BaseException:` | 全部，含退出与中断 | `[E2]` |
| `except:` | 等价 `except BaseException:` | `[E3]` |

> 注意：业务代码的兜底应该用 `except Exception`，而不是裸 `except:`；后者会把 Ctrl+C 和 `sys.exit()` 一起吞掉。`[E3]`

### 1.4 异常对象携带什么

| 属性 | 含义 | 依据 |
| --- | --- | --- |
| `args` | 构造时传入的参数元组 | `[E2]` |
| `str(e)` | 人类可读消息 | `[E2]` |
| `e.__traceback__` | 回溯对象 | `[E2]` |
| `e.__cause__` | 显式原因（`raise X from Y`） | `[E4]` |
| `e.__context__` | 隐式上下文（处理中又抛出） | `[E4]` |
| `e.__suppress_context__` | 是否隐藏 context | `[E4]` |
| `e.__notes__` | 附加说明（3.11+） | `[E6]` |

```python
try:
    int("x")
except ValueError as error:
    print(error.args)          # ('invalid literal for int() with base 10: 'x'',)
    print(type(error.__traceback__).__name__)   # traceback
```

## 2. 异常的捕获

### 2.1 最小结构

```python
try:
    risky()
except ValueError as error:
    handle(error)
```

### 2.2 四个子句的触发条件

```python
def order_demo():
    try:
        print("TRY")
        return "from-try"
    except ValueError:
        print("EXCEPT")
    else:
        print("ELSE")
    finally:
        print("FINALLY")

print("ORDER", order_demo())
```

本机实测输出：

```text
TRY
FINALLY
ORDER from-try
```

| 子句 | 何时执行 | 依据 |
| --- | --- | --- |
| `try` | 总是 | `[E1]` |
| `except` | `try` 内有匹配异常 | `[E1]` |
| `else` | `try` 内**无**异常 | `[E1]` |
| `finally` | **总是**（含 `return` / `break` / 异常） | `[E1]` |

```python
def run(value):
    try:
        number = int(value)
    except ValueError:
        print("EXCEPT", value)
    else:
        print("ELSE", number)
    finally:
        print("FINALLY", value)

for raw in ["5", "x"]:
    run(raw)
```

实测输出：

```text
ELSE 5
FINALLY 5
EXCEPT x
FINALLY x
```

> 注意：`finally` 在 `return` 值计算之后、返回之前执行；所以「`TRY` → `FINALLY` → `ORDER from-try`」的顺序并不矛盾。`[E1]`

### 2.3 多 `except` 与顺序

```python
class MyError(Exception):
    pass

class SubError(MyError):
    pass

try:
    raise SubError("sub")
except SubError:
    print("SUB_FIRST")        # 命中
except MyError:
    print("PARENT_SECOND")

try:
    raise SubError("sub")
except MyError:
    print("PARENT_CATCHES_SUB")   # 父类也能捕获子类
```

实测输出：

```text
SUB_FIRST
PARENT_CATCHES_SUB
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 自上而下匹配 | 命中第一个就停 | `[E1]` |
| 子类必须写在父类前面 | 否则子类分支永远不可达 | `[E1]` |
| 父类能捕获子类 | `isinstance` 语义 | `[E1]` |
| 顺序写反不报错 | 只是逻辑死代码 | `[E3]` |

### 2.4 元组捕获

```python
try:
    int("x")
except (ValueError, TypeError) as error:
    print("TUPLE", type(error).__name__)    # TUPLE ValueError（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 元组表示「任一匹配」 | 不区分具体类型 | `[E1]` |
| `as` 绑定实际异常 | 类型是命中的那个 | `[E1]` |
| 元组里不能有实例 | 必须是类 | `[E1]` |

### 2.5 `as` 变量的作用域

```python
try:
    int("x")
except ValueError as error:
    pass

try:
    print(error)
except NameError:
    print("EXC_VAR_DELETED", True)    # True（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `except ... as e:` 结束后 `e` 被删除 | 防止循环引用 | `[E4]` |
| 想在 `except` 外用 | 先赋给别的变量 | `[E3]` |
| 名字冲突会静默删除 | 覆盖同名变量要小心 | `[E4]` |

> 注意：这个删除是语言规定的（PEP 3110），不是实现细节；`except ... as error` 之后 `error` 就是 `NameError`。`[E4]`

### 2.6 裸 `except` 的危险

```python
try:
    raise SystemExit(0)
except:
    print("BARE_CATCHES_SYSTEMEXIT")    # 命中了（实测）

try:
    raise SystemExit(0)
except Exception:
    print("UNREACHABLE")
except SystemExit:
    print("SPECIFIC_SYSTEMEXIT")        # 命中的是这个（实测）
```

| 写法 | 能捕获 `SystemExit` | 能捕获 `KeyboardInterrupt` | 依据 |
| --- | --- | --- | --- |
| `except:` | ✅ | ✅ | `[E2]` |
| `except BaseException:` | ✅ | ✅ | `[E2]` |
| `except Exception:` | ❌ | ❌ | `[E2]` |

> 注意：裸 `except` 会让进程无法正常退出、Ctrl+C 失效；除非你在写进程最外层的守护逻辑，否则永远不要用。`[E3]`

### 2.7 `except Exception` 也不该滥用

| 场景 | 是否可接受 | 依据 |
| --- | --- | --- |
| 进程/线程最外层兜底 | ✅ 记录后终止或重试 | `[E3]` |
| 单个工具调用边界 | ✅ 转成结构化错误 | `[E3]` |
| 业务函数内部 | ❌ 掩盖 bug | `[E3]` |
| 循环体里 | ❌ 会跳过后续数据 | `[E3]` |

### 2.8 嵌套与 re-raise

```python
try:
    raise
except RuntimeError as error:
    print(type(error).__name__, str(error))
# RuntimeError No active exception to reraise（实测）
```

| 写法 | 含义 | 依据 |
| --- | --- | --- |
| `raise` | 重新抛出当前异常（只能在 `except` 内） | `[E1]` |
| `raise error` | 抛出指定实例（会改 traceback） | `[E1]` |
| `raise X from error` | 抛出并设置原因 | `[E4]` |

> 注意：`raise error` 会重置回溯起点，`raise` 保留原始回溯；排查时优先用裸 `raise`。`[E1]`

### 2.9 `finally` 的四个陷阱

**陷阱一：`return` 吞掉异常**

```python
def bad_finally():
    try:
        raise ValueError("x")
    finally:
        return "swallowed"

print(bad_finally())    # swallowed（实测，异常消失）
```

**陷阱二：`finally` 里抛新异常会覆盖原异常**

```python
def override():
    try:
        raise ValueError("first")
    finally:
        raise TypeError("second")

try:
    override()
except Exception as error:
    print(type(error).__name__, type(error.__context__).__name__)
    # TypeError ValueError（实测）
```

**陷阱三：`finally` 的 `return` 会吞掉 `with` 的异常**

```python
def with_finally():
    try:
        with open("nope.txt"):
            pass
    finally:
        return "swallowed"

print(with_finally())   # swallowed（实测，FileNotFoundError 消失）
```

**陷阱四：`break` / `continue` 同理**

| 陷阱 | 后果 | 依据 |
| --- | --- | --- |
| `finally` 里 `return` | 吞异常、覆盖返回值 | `[E3]` |
| `finally` 里 `raise` | 覆盖原异常（留 `__context__`） | `[E4]` |
| `finally` 里 `break/continue` | 吞异常 | `[E1]` |

> 注意：PEP 8 明确要求不要在 `finally` 里 `return`；清理逻辑只做清理。`[E3]`

### 2.10 `else` 里的异常不被同层捕获

```python
def else_raise():
    try:
        value = 1
    except ValueError:
        print("NEVER")
    else:
        raise KeyError("from-else")

try:
    else_raise()
except KeyError:
    print("ELSE_NOT_CAUGHT")    # 实测命中
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `else` 里抛的异常 | 不被同层 `except` 捕获 | `[E1]` |
| 这正是 `else` 存在的意义 | 缩小 `try` 的捕获范围 | `[E1]` |
| 但 `finally` 仍会执行 | 无条件 | `[E1]` |

### 2.11 捕获后的最小模板

```python
try:
    result = risky()
except SpecificError as error:
    logger.exception("risky 失败")        # 保留 traceback
    raise AppError("可操作的原因") from error   # 不丢上下文
```

| 步骤 | 要求 | 依据 |
| --- | --- | --- |
| 记日志 | 用 `logger.exception` 保留堆栈 | `[E7]` |
| 转换 | 用 `from error` 保留链 | `[E4]` |
| 消息 | 原因 + 下一步 | `[E3]` |
| 不吞 | 不要 `pass` | `[E3]` |

## 3. 异常类型

### 3.1 内置异常速查

| 异常 | 典型诱因 | 依据 |
| --- | --- | --- |
| `ValueError` | 类型对但值不合法（`int("x")`） | `[E2]` |
| `TypeError` | 类型不对（`1 + "a"`） | `[E2]` |
| `KeyError` | 字典缺键 | `[E2]` |
| `IndexError` | 序列越界 | `[E2]` |
| `AttributeError` | 对象无此属性 | `[E2]` |
| `NameError` | 名字未定义 | `[E2]` |
| `ZeroDivisionError` | 除以零 | `[E2]` |
| `FileNotFoundError` | 文件不存在 | `[E2]` |
| `PermissionError` | 无权限 | `[E2]` |
| `TimeoutError` | 超时（`OSError` 子类） | `[E2]` |
| `ImportError` | 导入失败 | `[E2]` |
| `ModuleNotFoundError` | 模块不存在 | `[E2]` |
| `StopIteration` | 迭代器耗尽 | `[E2]` |
| `NotImplementedError` | 抽象方法未实现 | `[E2]` |
| `AssertionError` | `assert` 失败 | `[E2]` |
| `RecursionError` | 递归过深 | `[E2]` |
| `RuntimeError` | 其它运行时错误 | `[E2]` |

```python
print("BUILTIN")
for probe in [
    lambda: int("x"),          # ValueError
    lambda: 1 + "a",           # TypeError
    lambda: {}["k"],           # KeyError
    lambda: [][0],             # IndexError
    lambda: None.attr,         # AttributeError
    lambda: open("nope.txt"),  # FileNotFoundError
    lambda: 1 / 0,             # ZeroDivisionError
    lambda: next(iter([])),    # StopIteration
]:
    try:
        probe()
    except BaseException as error:
        print("  ", type(error).__name__)
```

实测输出：

```text
BUILTIN
   ValueError
   TypeError
   KeyError
   IndexError
   AttributeError
   FileNotFoundError
   ZeroDivisionError
   StopIteration
```

### 3.2 容易混淆的三组

| 对比 | 区别 | 例子 | 依据 |
| --- | --- | --- | --- |
| `KeyError` vs `IndexError` | 映射缺键 vs 序列越界 | `{}["k"]` / `[][0]` | `[E2]` |
| `ValueError` vs `TypeError` | 类型对值错 vs 类型错 | `int("x")` / `int(None)` | `[E2]` |
| `AttributeError` vs `KeyError` | 属性 vs 下标 | `obj.x` / `obj["x"]` | `[E2]` |

### 3.3 `OSError` 家族

| 异常 | 说明 | 依据 |
| --- | --- | --- |
| `OSError` | 所有 IO 错误的基类 | `[E2]` |
| `FileNotFoundError` | `ENOENT` | `[E2]` |
| `PermissionError` | `EACCES` | `[E2]` |
| `FileExistsError` | `EEXIST` | `[E2]` |
| `IsADirectoryError` | 对目录做文件操作 | `[E2]` |
| `TimeoutError` | 超时（3.3+ 并入 `OSError`） | `[E2]` |
| `ConnectionError` | 连接类错误基类 | `[E2]` |

> 注意：`TimeoutError` 在 3.3 之前是独立的，现在继承 `OSError`；捕获 `OSError` 会连超时一起捕获。`[E2]`

### 3.4 不该捕获的异常

| 异常 | 为什么不捕 | 依据 |
| --- | --- | --- |
| `SystemExit` | 会阻止程序退出 | `[E2]` |
| `KeyboardInterrupt` | 会屏蔽 Ctrl+C | `[E2]` |
| `MemoryError` | 捕获后通常也无法继续 | `[E2]` |
| `RecursionError` | 栈已接近极限 | `[E2]` |
| `GeneratorExit` | 生成器关闭信号 | `[E2]` |

## 4. 主动抛出异常

### 4.1 `raise` 的三种形式

| 写法 | 说明 | 依据 |
| --- | --- | --- |
| `raise ValueError("原因")` | 抛新实例（推荐） | `[E1]` |
| `raise ValueError` | 自动实例化（无消息，不推荐） | `[E1]` |
| `raise` | 重抛当前异常（仅 `except` 内） | `[E1]` |
| `raise X from Y` | 抛新异常并设原因 | `[E4]` |
| `raise X from None` | 抛新异常并隐藏上下文 | `[E4]` |

```python
def parse_limit(value):
    number = int(value)
    if number <= 0:
        raise ValueError(f"limit 必须为正数，收到 {number}")
    return number
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 消息含实际值 | 可定位 | `[E3]` |
| 消息含期望 | 可操作 | `[E3]` |
| 不抛裸 `Exception` | 无法精确捕获 | `[E3]` |

### 4.2 `assert` 与 `raise` 的分工

```python
try:
    assert 1 == 2, "assert failed"
except AssertionError as error:
    print("ASSERT", str(error))    # ASSERT assert failed（实测）
```

| 维度 | `assert` | `raise` |
| --- | --- | --- |
| 用途 | 内部不变量、调试 | 对外契约、可预期失败 |
| `-O` 时 | **被移除** | 保留 |
| 消息 | 断言表达式 + 说明 | 自由构造 |
| 能否捕获 | 能，但语义不该依赖 | 应当 |

> 注意：`python -O` 会删掉所有 `assert`，所以「用 assert 校验用户输入」在优化模式下等于没校验。`[E1]`

```python
# 反例：生产校验用 assert
assert isinstance(payload, str), "payload 必须是 str"

# 正例
if not isinstance(payload, str):
    raise TypeError(f"payload 必须是 str，收到 {type(payload).__name__}")
```

### 4.3 fail fast 判据

| 情况 | 做法 | 依据 |
| --- | --- | --- |
| 参数非法，继续会出错 | 立即 `raise` | `[E3]` |
| 参数非法但可容错 | 返回明确结果或默认值 | `[E3]` |
| 内部状态被破坏 | 立即 `raise` | `[E3]` |
| 外部依赖不可用 | 抛出可重试/不可重试的明确类型 | `[E3]` |

### 4.4 抛什么异常：选择表

| 场景 | 选择 | 依据 |
| --- | --- | --- |
| 参数类型错 | `TypeError` | `[E2]` |
| 参数值错 | `ValueError` | `[E2]` |
| 缺键 | `KeyError` | `[E2]` |
| 越界 | `IndexError` | `[E2]` |
| 未实现 | `NotImplementedError` | `[E2]` |
| 状态非法 | `RuntimeError` 或自定义 | `[E2]` |
| 业务规则 | 自定义 `XxxError` | `[E3]` |

## 5. 自定义异常

### 5.1 最小写法

```python
class ToolError(Exception):
    """工具执行失败。"""
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 继承 `Exception` | 不是 `BaseException` | `[E3]` |
| 类名 `XxxError` | PEP 8 | `[E3]` |
| docstring 说明何时抛 | 契约 | `[E3]` |

### 5.2 带结构化字段

```python
class ToolError(Exception):
    def __init__(self, tool_name, reason, *, retryable=False):
        super().__init__(f"tool {tool_name} failed: {reason}")
        self.tool_name = tool_name
        self.reason = reason
        self.retryable = retryable

try:
    raise ToolError("search", "timeout", retryable=True)
except ToolError as error:
    print(str(error), error.tool_name, error.retryable)
    # tool search failed: timeout search True（实测）
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 调 `super().__init__(消息)` | 否则 `str(e)` 为空 | `[E2]` |
| 字段存实例属性 | 调用方可按需读取 | `[E3]` |
| `retryable` 用关键字参数 | 意图清晰 | `[E3]` |

> 注意：自定义 `__init__` 后一定要调 `super().__init__`，否则 `e.args` 为空、日志里只有类名没有原因。`[E2]`

### 5.3 层级设计

```python
class AppError(Exception):
    """应用异常基类。"""

class ValidationError(AppError):
    """输入不合法。"""

class InfraError(AppError):
    """基础设施故障，通常可重试。"""

class InfraTimeout(InfraError):
    """超时。"""
```

| 设计原则 | 说明 | 依据 |
| --- | --- | --- |
| 按「捕获方关心什么」分层 | 不是按抛出位置 | `[E3]` |
| 根异常一个 | 方便边界层统一兜底 | `[E3]` |
| 层级不超过三层 | 过深难记 | `[E3]` |
| 可重试/不可重试分开 | 便于重试策略 | `[E3]` |

### 5.4 多继承

```python
class Both(ValueError, TypeError):
    pass

print(issubclass(Both, ValueError), issubclass(Both, TypeError))   # True True（实测）
```

| 场景 | 说明 | 依据 |
| --- | --- | --- |
| 兼容两种捕获 | 过渡期常用 | `[E2]` |
| MRO 仍要能构造 | 内置异常多继承通常安全 | `[E2]` |
| 不要滥用 | 语义会模糊 | `[E3]` |

### 5.5 `__str__` 与 `__repr__`

```python
class ConfigError(Exception):
    def __init__(self, key, expected, actual):
        super().__init__(f"{key} 需要 {expected}，收到 {actual!r}")
        self.key = key

    def __repr__(self):
        return f"ConfigError(key={self.key!r})"
```

| 方法 | 用途 | 依据 |
| --- | --- | --- |
| `__str__` | 用户/日志消息 | `[E2]` |
| `__repr__` | 调试、测试断言 | `[E2]` |

### 5.6 该不该自定义

| 情况 | 建议 | 依据 |
| --- | --- | --- |
| 调用方需要按业务类型区分 | 自定义 | `[E3]` |
| 需要携带结构化字段 | 自定义 | `[E3]` |
| 只是想加一句消息 | 用内置 + 消息 | `[E3]` |
| 仅一个地方抛 | 内置足够 | `[E3]` |

## 6. 异常链

### 6.1 隐式上下文 `__context__`

```python
def implicit():
    try:
        {}["k"]
    except KeyError:
        raise RuntimeError("rethrow")

try:
    implicit()
except RuntimeError as error:
    print(type(error.__context__).__name__, error.__cause__ is None, error.__suppress_context__)
    # KeyError True False（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 处理异常时又抛 | 自动设 `__context__` | `[E4]` |
| `__cause__` 仍为 `None` | 不是显式声明的 | `[E4]` |
| `__suppress_context__` 为 `False` | 上下文会显示 | `[E4]` |

### 6.2 显式原因 `__cause__`

```python
def parse():
    try:
        int("x")
    except ValueError as error:
        raise InfraError("param parse failed") from error

try:
    parse()
except AppError as error:
    print(type(error).__name__, type(error.__cause__).__name__, error.__suppress_context__)
    # InfraError ValueError True（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `from error` 设置 `__cause__` | 明确因果 | `[E4]` |
| 同时 `__suppress_context__` 为 `True` | 不再显示隐式上下文 | `[E4]` |
| 回溯里显示「直接原因」 | 排查更清晰 | `[E4]` |

### 6.3 `from None`

```python
def suppressed():
    try:
        int("x")
    except ValueError:
        raise InfraError("param parse failed") from None

try:
    suppressed()
except InfraError as error:
    print(error.__cause__ is None, error.__suppress_context__)
    # True True（实测）
```

| 写法 | `__cause__` | `__suppress_context__` | 回溯显示 | 依据 |
| --- | --- | --- | --- | --- |
| `raise X` | `None` | `False` | 原异常 + 新异常 | `[E4]` |
| `raise X from Y` | `Y` | `True` | 只显示 Y → X | `[E4]` |
| `raise X from None` | `None` | `True` | 只显示 X | `[E4]` |

> 注意：`from None` 适用于「底层异常对调用方无意义，且消息已包含全部信息」；滥用会让排查失去线索，关键信息必须手动写进新消息。`[E4]`

### 6.4 三层结构对照

```text
__cause__    ← 显式声明：raise X from Y
__context__  ← 隐式：处理 Y 时抛了 X
__suppress_context__ ← 是否在回溯里隐藏 context
```

### 6.5 边界层翻译模式

```python
def call_tool(name, payload):
    try:
        return upstream(name, payload)
    except TimeoutError as error:
        raise ToolTimeout(name, "upstream timeout", retryable=True) from error
    except (ConnectionError, OSError) as error:
        raise ToolUnavailable(name, "upstream unavailable", retryable=True) from error
    except ValueError as error:
        raise ToolError(name, f"invalid payload: {error}") from error
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 每个底层异常都有对应业务异常 | 调用方只需认识业务类型 | `[E3]` |
| 保留 `from` | 排查时能追到根因 | `[E4]` |
| 区分可重试 | 重试策略据此决策 | `[E3]` |

## 7. 现代异常机制

### 7.1 `ExceptionGroup` 与 `except*`（3.11+）

```python
def group():
    raise ExceptionGroup("batch failed", [ValueError("v"), TypeError("t")])

try:
    group()
except* ValueError as error:
    print("EG_VALUE", len(error.exceptions))    # 1（实测）
except* TypeError as error:
    print("EG_TYPE", len(error.exceptions))     # 1（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 一个组里可含多类型 | 并行任务常见 | `[E5]` |
| `except*` 匹配后仍继续匹配其他分支 | 不是「命中即停」 | `[E5]` |
| 剩余的会重新聚合成组 | 未被匹配的部分继续抛 | `[E5]` |

```python
try:
    raise ExceptionGroup("mixed", [ValueError("v"), TypeError("t")])
except* (ValueError, TypeError) as error:
    print("EG_TUPLE", len(error.exceptions))    # 2（实测）
```

嵌套组会被展开：

```python
try:
    raise ExceptionGroup("outer", [ExceptionGroup("inner", [ValueError("v")])])
except* ValueError as error:
    print("NESTED_EG", len(error.exceptions))   # 1（实测）
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| `except*` 不能与 `except` 混用 | 语法限制 | `[E5]` |
| `except*` 捕获的是子组 | 已匹配的从组里移除 | `[E5]` |
| 全部匹配后不再抛 | 正常继续 | `[E5]` |
| 部分未匹配 | 抛剩余组 | `[E5]` |

> 注意：`asyncio.TaskGroup`、并发批处理会天然产生 `ExceptionGroup`；如果你不支持 3.11+，需要自己收集并逐个抛出。`[E5]`

### 7.2 `add_note`（3.11+）

```python
try:
    try:
        int("x")
    except ValueError as error:
        error.add_note("input came from user form")
        raise
except ValueError as error:
    print(error.__notes__)    # ['input came from user form']（实测）
```

| 用途 | 说明 | 依据 |
| --- | --- | --- |
| 补充上下文 | 不改消息、不新建异常 | `[E6]` |
| 多处追加 | 形成注释列表 | `[E6]` |
| 回溯里显示 | 排查时可见 | `[E6]` |

### 7.3 EAFP 与 LBYL

```python
data = {"k": 1}
try:
    value = data["k"]
except KeyError:
    value = 0
print("EAFP", value)     # 1（实测）
```

| 风格 | 写法 | 适用 | 依据 |
| --- | --- | --- | --- |
| EAFP | 先做，出错再处理 | 竞争少、失败罕见 | `[E1]` |
| LBYL | 先检查，再做 | 检查成本低、失败常见 | `[E1]` |
| `dict.get` | 内置兜底 | 缺键是常态 | `[E2]` |

| 场景 | 推荐 | 依据 |
| --- | --- | --- |
| 取字典值可缺省 | `get` / `setdefault` | `[E2]` |
| 打开文件 | `with open(...)` 直接开 | `[E1]` |
| 类型判断后操作 | 能 EAFP 就 EAFP | `[E1]` |
| 并发写同一资源 | 需要锁，不适合 EAFP | `[E1]` |

### 7.4 异常的性能

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `try` 本身几乎零成本 | 无异常时 | `[E1]` |
| 抛出+捕获开销大 | 构造回溯、栈展开 | `[E1]` |
| 不要用异常做正常分支 | 循环里尤甚 | `[E3]` |
| 异常不应出现在热路径 | 用返回值/哨兵 | `[E3]` |

### 7.5 `traceback` 模块

```python
import traceback

try:
    int("x")
except ValueError:
    traceback.print_exc()          # 打印完整回溯
    text = traceback.format_exc()  # 取字符串，便于日志
```

| 函数 | 用途 | 依据 |
| --- | --- | --- |
| `traceback.print_exc()` | 当前异常打印到 stderr | `[E7]` |
| `traceback.format_exc()` | 取字符串 | `[E7]` |
| `traceback.format_exception(*sys.exc_info())` | 自定义格式 | `[E7]` |
| `logger.exception(...)` | 日志里带堆栈（推荐） | `[E7]` |

### 7.6 生成器里的 `StopIteration`（PEP 479）

```python
def bad():
    raise StopIteration("oops")
    yield 1

try:
    list(bad())
except RuntimeError as error:
    print(type(error).__name__, type(error.__cause__).__name__)
    # RuntimeError StopIteration（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 生成器内 `StopIteration` 变 `RuntimeError` | 防止静默提前结束 | `[E1]` |
| 原异常存进 `__cause__` | 可追溯 | `[E1]` |
| 想主动结束用 `return` | 07 章 / 17 章 | `[E1]` |

## 8. 综合示例：边界层统一翻译

```python
"""第 16 章综合示例：把底层异常翻译成带重试标记的业务异常。"""


class ToolError(Exception):
    def __init__(self, tool, reason, *, retryable=False):
        super().__init__(f"tool {tool} failed: {reason}")
        self.tool = tool
        self.reason = reason
        self.retryable = retryable


class ToolTimeout(ToolError):
    pass


def call_tool(name, payload):
    if not isinstance(payload, str):
        raise ToolError(name, f"payload must be str, got {type(payload).__name__}")
    if payload == "slow":
        try:
            raise TimeoutError("upstream timeout")
        except TimeoutError as error:
            raise ToolTimeout(name, "upstream timeout", retryable=True) from error
    return f"{name}:{payload}"


for payload in ["AI", "slow", 123]:
    try:
        print("OK:", call_tool("search", payload))
    except ToolTimeout as error:
        print("RETRYABLE:", error.tool, error.retryable, type(error.__cause__).__name__)
    except ToolError as error:
        print("FATAL:", error.reason)
    finally:
        print("DONE:", payload)
```

本机实测输出：

```text
OK: search:AI
DONE: AI
RETRYABLE: search True TimeoutError
DONE: slow
FATAL: payload must be str, got int
DONE: 123
```

**逐段说明**：

| 代码 | 用到的机制 | 依据 |
| --- | --- | --- |
| 自定义 `ToolError` | 业务异常基类 | `[E3]` |
| `super().__init__(消息)` | 保证 `str(e)` 有内容 | `[E2]` |
| `retryable` 字段 | 重试策略的判据 | `[E3]` |
| `raise ... from error` | 保留底层超时原因 | `[E4]` |
| 先捕 `ToolTimeout` 再捕 `ToolError` | 子类优先 | `[E1]` |
| `finally` 记录 | 成功失败都留痕 | `[E1]` |

> 注意：`except ToolTimeout` 必须先于 `except ToolError`，否则子类分支永远不执行；这与第 2.3 节的规则一致。`[E1]`

## 9. 注意事项与新手错误对照表

| 错误写法 / 操作 | 报错或现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 裸 `except:` | 吞掉 `SystemExit` / `KeyboardInterrupt` | `except Exception:` 或具体类型 | `[E3]` |
| `except: pass` | 静默失败 | 记录 + 转换或重抛 | `[E3]` |
| 父类写在子类前 | 子类分支不可达 | 具体在前 | `[E1]` |
| `except` 捕获 `BaseException` | 进程无法退出 | `Exception` | `[E2]` |
| `try` 包住整段逻辑 | 误捕无关异常 | 缩小 `try` | `[E3]` |
| `else` 里抛异常以为被捕获 | 实际向外传播 | 理解 `else` 语义 | `[E1]` |
| `finally` 里 `return` | 吞异常、改返回值 | 只做清理 | `[E3]` |
| `finally` 里抛新异常 | 覆盖原异常 | 先处理再抛 | `[E4]` |
| `except ... as e` 后在外部用 `e` | `NameError` | 提前赋值 | `[E4]` |
| 裸 `raise` 用在 `except` 外 | `RuntimeError: No active exception` | 只能在 `except` 内 | `[E1]` |
| `raise e` 而非 `raise` | 回溯起点被重置 | 用裸 `raise` | `[E1]` |
| 自定义异常忘 `super().__init__` | `str(e)` 为空 | 必须调用 | `[E2]` |
| 自定义异常继承 `BaseException` | 无法被常规捕获 | 继承 `Exception` | `[E3]` |
| 异常名不以 `Error` 结尾 | 与类混淆 | `XxxError` | `[E3]` |
| 抛 `Exception("出错了")` | 无法精确捕获 | 具体类型 | `[E3]` |
| 消息只有「失败」 | 无法排查 | 原因 + 实际值 + 期望 | `[E3]` |
| `except Exception as e: raise Exception(str(e))` | 丢链、丢类型 | `raise AppError(...) from e` | `[E4]` |
| 到处 `from None` | 排查无据 | 关键信息写进消息 | `[E4]` |
| 用 `assert` 校验输入 | `-O` 下失效 | `if ... raise` | `[E1]` |
| 用异常做正常分支 | 热路径变慢 | 返回值/哨兵 | `[E3]` |
| 循环里靠异常跳出 | 难读且慢 | 条件判断 | `[E3]` |
| 捕获后只 `print` | 线上无日志 | `logger.exception` | `[E7]` |
| 把堆栈返回给用户 | 信息泄露 | 只给可操作提示 | `[E3]` |
| 记录密码/令牌到异常消息 | 泄露 | 脱敏 | `[E3]` |
| 生成器里 `raise StopIteration` | 变 `RuntimeError`（PEP 479） | `return` | `[E1]` |
| 以为 `except*` 和 `except` 可混用 | `SyntaxError` | 分开写 | `[E5]` |
| `except*` 当作「命中即停」 | 后续分支也执行 | 理解子组语义 | `[E5]` |
| 只用 `ExceptionGroup` 不拆 | 看不出具体失败 | `except*` 分类型 | `[E5]` |
| 用 `TimeoutError` 捕所有超时 | 可能捕到文件 IO 超时 | 自定义更精确的类型 | `[E2]` |
| 捕获 `OSError` 却只处理缺文件 | 其它错误被误判 | 细分异常 | `[E2]` |
| `finally` 里 `break` | 吞异常 | 不在 finally 用控制流 | `[E1]` |
| 异常消息用 f-string 拼用户输入 | 注入/泄露 | 校验 + 转义 | `[E3]` |
| 重试时捕获所有异常 | 死循环 + 掩盖 bug | 只捕可重试类型 | `[E3]` |
| 重试无上限 | 拖垮下游 | 次数 + 退避 | `[E3]` |
| 最终不抛出 | 失败被掩盖 | 最后一次 `raise` | `[E3]` |
| 在 `__del__` 里抛异常 | 被忽略 | 不用异常做清理 | `[E2]` |
| 捕获后不 `raise` 也不返回 | 返回 `None` 导致下游 `AttributeError` | 明确返回值 | `[E3]` |
| 依赖 `e.args[0]` 取消息 | 多参数时错位 | `str(e)` | `[E2]` |
| 用 `sys.exc_info()` 跨函数传递 | 上下文丢失 | 显式传 `e` | `[E7]` |
| `except (ValueError)` 少了逗号 | 不是元组，仍是单类型 | `(A, B)` | `[E1]` |

## 10. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| `try` 只包可能抛的那几行 | 提高捕获精度 | `[E3]` |
| 捕获具体异常 | 不吞无关错误 | `[E3]` |
| 用 `else` 放「成功后逻辑」 | 避免误捕 | `[E1]` |
| 用 `with` 替代 `try/finally` | 更可靠（18 章） | `[E3]` |
| 边界层统一翻译异常 | 调用方只认业务类型 | `[E4]` |
| 转换必须带 `from` | 保留根因 | `[E4]` |
| 自定义异常带结构化字段 | 便于策略决策 | `[E3]` |
| 记录日志用 `logger.exception` | 保留堆栈 | `[E7]` |
| 面向用户只给可操作提示 | 不泄露内部 | `[E3]` |
| 失败要快 | 非法状态立即抛 | `[E3]` |

**风格示范**：

```python
class PayloadError(ValueError):
    """payload 不合法。

    retryable=False：同样的输入重试也不会成功。
    """

    def __init__(self, field: str, reason: str) -> None:
        super().__init__(f"payload.{field} 不合法：{reason}")
        self.field = field
        self.reason = reason
```

**边界**：

- 异常消息里不要拼未脱敏的用户输入（日志注入、隐私泄露）。
- 不要在 `__del__`、`finally` 里抛新异常。
- 异步任务的异常不会自动冒泡到主线程（第 25、28 章）。

## 11. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[E1]` | python.org | https://docs.python.org/3.12/tutorial/errors.html | `try/except/else/finally`、`raise`、用户异常、异常链、EAFP |
| `[E2]` | python.org | https://docs.python.org/3.12/library/exceptions.html | 异常层级、`BaseException` / `Exception`、内置异常家族、`OSError` 子树 |
| `[E3]` | PEP 官方 | https://peps.python.org/pep-0008/ | 具体 `except`、缩小 `try`、`finally` 不放 `return`、异常命名、`with` 优先 |
| `[E4]` | PEP 官方 | https://peps.python.org/pep-3134/ | 异常链 `__cause__` / `__context__` / `__suppress_context__`、`except ... as e` 删除 |
| `[E5]` | PEP 官方 | https://peps.python.org/pep-0654/ | `ExceptionGroup` 与 `except*` 语义 |
| `[E6]` | PEP 官方 | https://peps.python.org/pep-0678/ | `BaseException.add_note` 与 `__notes__` |
| `[E7]` | python.org | https://docs.python.org/3.12/library/traceback.html | `print_exc` / `format_exc` / `format_exception` |
| `[E8]` | GitHub 官方 | https://github.com/python/cpython/blob/main/Doc/tutorial/errors.rst | 官方教程源文件（`[E1]` 页脚 Show Source 指向） |

> **核对状态**：`[E3]` 与本章 `README.md` 已核对来源一致；其余链接按 `docs.python.org/3.12` 与 `peps.python.org` 官方结构整理，**本次未逐页直连复核**。文中「实测」结论均为本机 Python 3.12.8 运行结果。

## 12. 毕业自查清单

**能说清（概念层）**：

- [ ] `BaseException` 与 `Exception` 的分界，哪些异常不该捕获
- [ ] `try/except/else/finally` 四个子句各自的触发条件
- [ ] 为什么 `except` 要从具体到一般
- [ ] `except ... as e` 之后 `e` 为什么消失
- [ ] 裸 `except:` 的两个具体危害
- [ ] `finally` 里 `return` 会发生什么
- [ ] `__cause__` 与 `__context__` 的区别
- [ ] `from None` 什么时候用
- [ ] `except*` 与 `except` 的语义差异
- [ ] EAFP 与 LBYL 各自适用场景

**能写出（代码层）**：

- [ ] 带 `else` / `finally` 的完整捕获结构
- [ ] 三层自定义异常层级（根 / 校验 / 基础设施）
- [ ] 带 `retryable` 字段的业务异常
- [ ] 边界层翻译函数（`raise X from Y`）
- [ ] 用 `add_note` 补充上下文
- [ ] 用 `except*` 处理 `ExceptionGroup`
- [ ] 用 `traceback.format_exc()` 记录日志

**能判断（避坑层）**：

- [ ] 看到裸 `except` 能指出吞掉 `KeyboardInterrupt`
- [ ] 看到 `finally: return` 能指出吞异常
- [ ] 看到 `except Exception: pass` 能指出静默失败
- [ ] 看到用 `assert` 校验输入能指出 `-O` 失效
- [ ] 看到 `raise Exception(str(e))` 能指出丢链
- [ ] 看到重试捕获所有异常能指出掩盖 bug

**能跑通（验收层）**：

- [ ] 运行 `examples/exception_demo.py` 并解释三组输出
- [ ] 把第 8 节示例存成文件运行，输出与文档一致
- [ ] 在 REPL 验证「`except ... as e` 后 `e` 不存在」
- [ ] 手写一个异常链并用 `traceback.print_exc()` 观察「直接原因」

## 13. 下一章衔接

第 17 章 `迭代器与生成器`：本章说 `StopIteration` 是迭代的终止信号，下一章把它拆开——`for` 到底怎么调用 `next()`、`yield` 如何暂停、PEP 479 为什么要求生成器内不许抛 `StopIteration`。

本章留下的伏笔：

1. `finally` 保证清理，但资源释放更该用 `with`（第 18 章）。
2. 生成器内抛 `StopIteration` 会变成 `RuntimeError`，原因在第 17 章的迭代协议里。
3. 边界层翻译异常的模式，会直接复用到工具调用与流式输出。