# 18 上下文管理器 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把截图里的「基本用法、自定义上下文管理器、异常处理、`@contextmanager`、多个上下文管理器」逐条展开，并补上 `ExitStack`、`suppress`、异步上下文管理器、异常抑制风险，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测） |
| 前置 | 第 14、16、17 章（特殊方法、异常、生成器） |
| 覆盖范围 | `with` 语义、`__enter__` / `__exit__`、类实现与生成器实现、异常抑制与转换、多上下文与 `ExitStack`、`contextlib` 工具箱 |
| 明确不覆盖 | 异步上下文管理器细节（27）、`asyncio` 生命周期（26）、`try/finally` 的异常链（16） |
| 学完验收 | 能写出两种自定义上下文管理器、能解释 `__exit__` 返回 `True` 的后果、能说清多上下文的退出顺序（见第 12 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Wn]` `` 指向第 11 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果。

**推荐顺序**：

```text
1 基本用法（第 1 节）        → with 只是 try/finally 的语法糖
2 自定义（第 2 节）          → 类实现的两个方法
3 异常处理（第 3 节）        → 三个参数 + 抑制开关
4 @contextmanager（第 4 节） → 生成器版，最常用
5 多个上下文（第 5 节）      → 顺序 + ExitStack
6 contextlib（第 6 节）      → 标准库现成工具
7 与 try/finally 对比（第 7 节）
8 综合示例（第 8 节）
9 注意事项（第 9 节）        → 32 条错误对照
```

**与 README 的分工**：README 给结论与边界，本文件负责协议细节与实现套路。冲突时以本文件为准。

## 1. 基本用法

### 1.1 语法

```python
with 表达式 as 变量名:
    代码块
```


带 `__enter__` 和 `__exit__` 方法的对象叫做上下文管理器（Context Manager）。

上下文管理器是支持 with 语句的对象
必须同时实现两个方法，否则 with 会报错


| 部分 | 说明 | 依据 |
| --- | --- | --- |
| `表达式` | 求值得到上下文管理器 | `[W2]` |
| `as 变量` | 绑定 `__enter__()` 的返回值 | `[W2]` |
| `代码块` | 在 `__enter__` 与 `__exit__` 之间执行 | `[W2]` |



### 1.2 等价展开

```python
with expr as value:
    body
```

等价于：

```python
manager = expr
value = manager.__enter__()
try:
    body
except BaseException as error:
    if not manager.__exit__(type(error), error, error.__traceback__):
        raise
else:
    manager.__exit__(None, None, None)
```

| 步骤 | 调用 | 依据 |
| --- | --- | --- |
| 1 | `expr.__enter__()` | `[W1]` |
| 2 | 执行代码块 | `[W2]` |
| 3 | 正常结束 → `__exit__(None, None, None)` | `[W1]` |
| 4 | 异常结束 → `__exit__(type, value, tb)` | `[W1]` |
| 5 | 返回假值 → 继续抛 | `[W1]` |

### 1.3 执行顺序

```python
class Session:
    def __init__(self, name):
        self.name = name

    def __enter__(self):
        print("ENTER", self.name)
        return {"name": self.name}

    def __exit__(self, exc_type, exc_value, traceback):
        print(
            "EXIT",
            self.name,
            exc_type.__name__ if exc_type else None,
            exc_value is not None,
            traceback is not None,
        )
        return False


with Session("search") as session:
    print("BODY", session)
```

本机实测输出：

```text
ENTER search
BODY {'name': 'search'}
EXIT search None False False
```

| 顺序 | 说明 | 依据 |
| --- | --- | --- |
| `__init__` → `__enter__` → 代码块 → `__exit__` | 固定 | `[W1]` |
| 正常退出时三个参数都是 `None` | 实测 | `[W1]` |
| `__exit__` 总能执行 | 含异常路径 | `[W1]` |

### 1.4 `as` 绑定的是 `__enter__` 返回值

| 写法 | `as` 得到 | 依据 |
| --- | --- | --- |
| `__enter__` 返回 `self` | 管理器本身 | `[W1]` |
| `__enter__` 返回别的对象 | 那个对象 | `[W1]` |
| 不写 `as` | 丢弃返回值 | `[W2]` |

```python
with open("data.txt", encoding="utf-8") as handle:
    content = handle.read()
```

`open()` 的 `__enter__` 返回文件对象本身。`[W3]`

### 1.5 常见内置上下文管理器

| 对象 | 退出时做什么 | 依据 |
| --- | --- | --- |
| `open(...)` | 关闭文件 | `[W3]` |
| `threading.Lock()` | 释放锁 | `[W3]` |
| `contextlib.suppress(E)` | 忽略指定异常 | `[W3]` |
| `contextlib.redirect_stdout(f)` | 恢复 `sys.stdout` | `[W3]` |
| `decimal.localcontext()` | 恢复精度设置 | `[W3]` |
| `tempfile.TemporaryDirectory()` | 删除临时目录 | `[W3]` |
| `unittest.mock.patch(...)` | 还原被替换对象 | `[W3]` |

> 注意：`with` 的价值是「退出一定执行」，而不是「更短」；只要需要成对操作（获取/释放、进入/退出、设置/恢复），就该考虑它。`[W4]`

## 2. 自定义上下文管理器

### 2.1 协议

```python
class Manager:
    def __enter__(self):
        """进入：返回给 as 的值"""
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        """退出：清理；返回真值可抑制异常"""
        return False
```

| 方法 | 必须 | 参数 | 依据 |
| --- | --- | --- | --- |
| `__enter__` | ✅ | 无（`self` 除外） | `[W1]` |
| `__exit__` | ✅ | 异常三元组 | `[W1]` |

### 2.2 类实现

```python
class Timer:
    def __enter__(self):
        import time
        self.start = time.perf_counter()
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        import time
        self.elapsed = time.perf_counter() - self.start
        print(f"耗时 {self.elapsed:.4f}s")
        return False        # 不吞异常


with Timer() as timer:
    sum(range(100_000))
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 状态存实例属性 | `__enter__` 写、`__exit__` 读 | `[W1]` |
| 返回 `False` | 异常正常传播 | `[W1]` |
| 可附加查询方法 | `timer.elapsed` | `[W1]` |

### 2.3 实例可复用

```python
class Reusable:
    def __init__(self):
        self.entered = 0

    def __enter__(self):
        self.entered += 1
        return self.entered

    def __exit__(self, *args):
        return False


reusable = Reusable()
with reusable as first:
    print("REUSE1", first)
with reusable as second:
    print("REUSE2", second)
```

实测输出：

```text
REUSE1 1
REUSE2 2
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 同一实例可多次 `with` | 只要状态允许 | `[W1]` |
| 计数/复用要自己维护 | 协议不管 | `[W1]` |
| 文件对象复用有限制 | 已关闭需重新 `open` | `[W3]` |

### 2.4 三种实现方式对比

| 方式 | 代码量 | 适合 | 依据 |
| --- | --- | --- | --- |
| 类实现 | 中 | 复杂状态、可复用、需要额外方法 | `[W1]` |
| `@contextmanager` | 少 | 简单「进入/退出」 | `[W3]` |
| `ExitStack` 组合 | 少 | 动态数量 | `[W3]` |

## 3. 异常处理

### 3.1 `__exit__` 的三个参数

```python
import types

tb_type = types.TracebackType


class Inspector:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        print("INSPECT", exc_type.__name__, repr(str(exc_value)), type(traceback).__name__)
        return False


try:
    with Inspector():
        raise KeyError("k")
except KeyError:
    pass
```

本机实测输出：

```text
INSPECT KeyError "'k'" traceback
```

| 参数 | 正常退出 | 异常退出 | 依据 |
| --- | --- | --- | --- |
| `exc_type` | `None` | 异常类 | `[W1]` |
| `exc_value` | `None` | 异常实例 | `[W1]` |
| `traceback` | `None` | 回溯对象 | `[W1]` |

> 注意：`str(KeyError("k"))` 是 `"'k'"`（带引号），因为 `KeyError.__str__` 对参数做了 `repr`；日志里容易看出差别。`[W1]`

### 3.2 返回真值 = 抑制异常

```python
class Suppressor:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        print("SUPPRESS_EXIT", exc_type.__name__)
        return True


with Suppressor():
    raise ValueError("swallowed")
print("AFTER_SUPPRESS", True)
```

实测输出：

```text
SUPPRESS_EXIT ValueError
AFTER_SUPPRESS True
```

| `__exit__` 返回 | 结果 | 依据 |
| --- | --- | --- |
| `True` / 真值 | 异常被吞，继续执行 | `[W1]` |
| `False` / `None` | 异常继续传播 | `[W1]` |
| 抛新异常 | 新异常替换原异常 | `[W1]` |

### 3.3 不抑制时正常传播

```python
try:
    with Session("fail") as session:
        raise ValueError("boom")
except ValueError as error:
    print("PROPAGATED", str(error))
```

实测输出：

```text
ENTER fail
EXIT fail ValueError True True
PROPAGATED boom
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `__exit__` 先执行 | 再决定是否传播 | `[W1]` |
| 返回 `False` 后原异常继续抛 | 回溯保留 | `[W1]` |

### 3.4 为什么抑制要克制

| 风险 | 说明 | 依据 |
| --- | --- | --- |
| 静默失败 | 调用方以为成功 | `[W4]` |
| 掩盖 bug | 真错误被吞 | `[W4]` |
| 资源状态不一致 | 已部分写入 | `[W4]` |
| 难以排查 | 日志缺失 | `[W4]` |

```python
# 反例：吞掉一切
class Bad:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return True        # 所有异常都消失


# 正例：只忽略明确的预期异常，并记录
class IgnoreMissing:
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is FileNotFoundError:
            print("忽略：文件不存在")
            return True
        return False
```

### 3.5 在 `__exit__` 里转换异常

```python
@contextlib.contextmanager
def transform():
    try:
        yield
    except ValueError as error:
        raise KeyError("converted") from error


try:
    with transform():
        raise ValueError("x")
except KeyError as error:
    print("CM_TRANSFORM", type(error.__cause__).__name__)   # ValueError（实测）
```

| 模式 | 说明 | 依据 |
| --- | --- | --- |
| 捕获后 `raise X from Y` | 转换并保留链 | 第 16 章 |
| 直接 `raise` | 保持原样 | 第 16 章 |
| 返回 `True` 且不抛 | 吞掉 | `[W1]` |

> 注意：类实现里也可以在 `__exit__` 里 `raise`，但要清楚这会「替换」原异常，原异常只能从 `__context__` 找回。`[W1]`

## 4. `@contextmanager`

### 4.1 生成器版

```python
import contextlib


@contextlib.contextmanager
def tool_session(name):
    print("CM_ENTER", name)
    try:
        yield {"tool": name}
    finally:
        print("CM_EXIT", name)


with tool_session("search") as session:
    print("CM_BODY", session)
```

本机实测输出：

```text
CM_ENTER search
CM_BODY {'tool': 'search'}
CM_EXIT search
```

| 位置 | 等价于 | 依据 |
| --- | --- | --- |
| `yield` 之前 | `__enter__` | `[W3]` |
| `yield` 的值 | `as` 绑定的对象 | `[W3]` |
| `yield` 之后（`finally`） | `__exit__` | `[W3]` |

### 4.2 为什么必须 `try/finally`

```python
@contextlib.contextmanager
def leaky():
    print("LEAKY_ENTER")
    yield "x"
    print("LEAKY_EXIT")


try:
    with leaky():
        raise RuntimeError("x")
except RuntimeError:
    print("LEAKY_NO_EXIT", True)
```

本机实测输出：

```text
LEAKY_ENTER
LEAKY_NO_EXIT True
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 没有 `try/finally` 时 | 异常直接抛进生成器，`yield` 后的代码不执行 | `[W3]` |
| 也没有报错 | 静默跳过清理 | `[W3]` |
| 后果 | 资源泄漏 | `[W4]` |

> 注意：这是 `@contextmanager` 最大的坑——清理逻辑必须放在 `try/finally` 的 `finally` 里，否则异常路径不执行，而且**不会给任何提示**。`[W3]`

### 4.3 只能 `yield` 一次

```python
@contextlib.contextmanager
def twice():
    yield 1
    yield 2


try:
    with twice() as value:
        print("TWICE", value)
except RuntimeError as error:
    print("TWICE_ERR", type(error).__name__, str(error)[:40])
```

实测输出：

```text
TWICE 1
TWICE_ERR RuntimeError generator didn't stop
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 第二次 `yield` | 抛 `RuntimeError: generator didn't stop` | `[W3]` |
| 原因 | `__exit__` 只推进到下一个 `yield`，发现还没结束 | `[W3]` |
| 想要多次进入 | 每次调用装饰器函数 | `[W3]` |

### 4.4 生成器版如何抑制异常

```python
@contextlib.contextmanager
def suppress_value_error():
    try:
        yield
    except ValueError:
        print("CM_SWALLOWED")


with suppress_value_error():
    raise ValueError("x")
print("CM_AFTER", True)
```

实测输出：

```text
CM_SWALLOWED
CM_AFTER True
```

| 写法 | 效果 | 依据 |
| --- | --- | --- |
| `except ValueError: pass` | 吞掉 `ValueError` | `[W3]` |
| `except ValueError: raise` | 继续传播 | `[W3]` |
| `except ValueError as e: raise KeyError(...) from e` | 转换 | `[W3]` |

> 注意：生成器版「不 `raise` 就是抑制」，比类实现「返回 `True`」更隐蔽；团队里应约定：抑制必须写注释说明原因。`[W4]`

### 4.5 与类实现的选择

| 场景 | 推荐 | 依据 |
| --- | --- | --- |
| 一次性的进入/退出 | `@contextmanager` | `[W3]` |
| 需要多个方法（`commit()` / `rollback()`） | 类 | `[W1]` |
| 需要复用并保存状态 | 类 | `[W1]` |
| 需要 `__enter__` 返回复杂对象 | 两者都行 | `[W3]` |
| 需要继承/多态 | 类 | `[W1]` |

## 5. 多个上下文管理器

### 5.1 一行多个

```python
with Session("a"), Session("b"):
    print("BOTH")
```

本机实测输出：

```text
ENTER a
ENTER b
BOTH
EXIT b None False False
EXIT a None False False
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 从左到右进入 | `a` → `b` | `[W2]` |
| 从右到左退出 | `b` → `a` | `[W2]` |
| 等价嵌套 | `with a: with b:` | `[W2]` |

### 5.2 嵌套写法

```python
with Session("outer"):
    with Session("inner"):
        print("NESTED")
```

| 对比 | 一行多个 | 嵌套 |
| --- | --- | --- |
| 可读性 | 短，适合 2–3 个 | 长，层次清晰 |
| 中间代码 | 无法插入 | 可以 |
| 依据 | `[W2]` | `[W2]` |

### 5.3 `ExitStack`：数量不确定时

```python
with contextlib.ExitStack() as stack:
    stack.enter_context(tool_session("a"))
    stack.enter_context(tool_session("b"))
    stack.callback(lambda: print("CLOSE_ALL"))
```

实测输出顺序：

```text
CM_ENTER a
CM_ENTER b
CLOSE_ALL
CM_EXIT b
CM_EXIT a
```

| 能力 | 说明 | 依据 |
| --- | --- | --- |
| 动态进入任意数量 | 循环里 `enter_context` | `[W3]` |
| 统一退出 | 离开 `with` 时 LIFO | `[W3]` |
| 注册任意清理 | `stack.callback(fn)` | `[W3]` |
| 异常仍传播 | 默认不抑制 | `[W3]` |

```python
# 动态打开多个文件
with contextlib.ExitStack() as stack:
    handles = [stack.enter_context(open(path)) for path in paths]
    contents = [handle.read() for handle in handles]
```

### 5.4 退出顺序为什么是 LIFO

| 原因 | 说明 | 依据 |
| --- | --- | --- |
| 后进先出符合依赖关系 | 后获取的资源可能依赖先获取的 | `[W3]` |
| 与函数栈一致 | 容易推理 | `[W3]` |
| 顺序写反会泄漏 | 先关被依赖的资源 | `[W3]` |

> 注意：`ExitStack` 的回调也是 LIFO（实测 `CALLBACK_2` 先于 `CALLBACK_1`），注册顺序与执行顺序相反。`[W3]`

## 6. `contextlib` 工具箱

### 6.1 `suppress`

```python
with contextlib.suppress(FileNotFoundError):
    open("nope.txt")
print("SUPPRESS_OK", True)    # SUPPRESS_OK True（实测）
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 只忽略指定类型 | 其它异常照常抛 | `[W3]` |
| 比 `try/except: pass` 更明确 | 意图清晰 | `[W3]` |
| 不要忽略过宽的类型 | 如 `Exception` | `[W4]` |

### 6.2 `redirect_stdout`

```python
import io

buffer = io.StringIO()
with contextlib.redirect_stdout(buffer):
    print("captured")
print("REDIRECT", buffer.getvalue().strip())   # REDIRECT captured（实测）
```

| 用途 | 说明 | 依据 |
| --- | --- | --- |
| 捕获第三方库的 `print` | 测试、日志收集 | `[W3]` |
| 线程不安全 | 全局替换 `sys.stdout` | `[W3]` |
| 异步场景慎用 | 事件循环共享 | `[W3]` |

### 6.3 `closing`

```python
with contextlib.closing(legacy_connection()) as conn:
    conn.query("...")
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 退出时调 `close()` | 适合没有上下文协议的对象 | `[W3]` |
| `__enter__` 返回对象本身 | 不调用别的 | `[W3]` |

### 6.4 `nullcontext`

```python
print(contextlib.nullcontext("x").__enter__())   # x（实测）
```

| 用途 | 说明 | 依据 |
| --- | --- | --- |
| 条件性使用上下文 | 有资源用真管理器，否则占位 | `[W3]` |
| 不做事 | `__exit__` 返回 `False` | `[W3]` |

```python
manager = open(path) if path else contextlib.nullcontext()
with manager as handle:
    ...
```

### 6.5 `ExitStack` / `AsyncExitStack`

| 类 | 用于 | 依据 |
| --- | --- | --- |
| `ExitStack` | 同步上下文 | `[W3]` |
| `AsyncExitStack` | 异步上下文 | `[W3]` |

### 6.6 `@asynccontextmanager`

```python
import asyncio


async def async_main():
    @contextlib.asynccontextmanager
    async def async_session():
        print("ASYNC_ENTER")
        try:
            yield "session"
        finally:
            print("ASYNC_EXIT")

    async with async_session() as value:
        print("ASYNC_BODY", value)


asyncio.run(async_main())
```

实测输出：

```text
ASYNC_ENTER
ASYNC_BODY session
ASYNC_EXIT
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 用 `async with` | 不是 `with` | `[W8]` |
| 生成器要 `async def` + `await` | 内部可 `await` | `[W8]` |
| 类实现要 `__aenter__` / `__aexit__` | 异步版本 | `[W8]` |

## 7. 与 `try/finally` 的对比

| 维度 | `with` | `try/finally` |
| --- | --- | --- |
| 代码量 | 少 | 多 |
| 可复用 | ✅ 封装成管理器 | ❌ 每次重写 |
| 遗漏风险 | 低 | 高（忘写 `finally`） |
| 异常抑制 | 显式由 `__exit__` 决定 | 需手写 |
| 语义清晰度 | 高（名字即语义） | 中 |
| 依据 | `[W4]` | `[W4]` |

```python
# 等价写法
handle = open("data.txt")
try:
    content = handle.read()
finally:
    handle.close()

# 推荐
with open("data.txt") as handle:
    content = handle.read()
```

> 注意：PEP 8 明确建议用 `with` 管理局部资源；`try/finally` 只在你需要「非上下文协议」的细粒度控制时才用。`[W4]`

## 8. 综合示例：事务与批量清理

```python
"""第 18 章综合示例：类上下文管理器 + ExitStack。"""

import contextlib


class Transaction:
    def __init__(self, name):
        self.name = name
        self.committed = False

    def __enter__(self):
        print("BEGIN", self.name)
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        if exc_type is None:
            self.committed = True
            print("COMMIT", self.name)
        else:
            print("ROLLBACK", self.name, exc_type.__name__)
        return False


with Transaction("t1") as tx:
    print("WORK", tx.name, tx.committed)
print("AFTER", tx.committed)

try:
    with Transaction("t2") as tx2:
        raise ValueError("boom")
except ValueError:
    print("AFTER_ROLLBACK", tx2.committed)

with contextlib.ExitStack() as stack:
    stack.enter_context(Transaction("a"))
    stack.enter_context(Transaction("b"))
    stack.callback(lambda: print("CLOSE_ALL"))
```

本机实测输出：

```text
BEGIN t1
WORK t1 False
COMMIT t1
AFTER True
BEGIN t2
ROLLBACK t2 ValueError
AFTER_ROLLBACK False
BEGIN a
BEGIN b
CLOSE_ALL
COMMIT b
COMMIT a
```

**逐段说明**：

| 代码 | 用到的机制 | 依据 |
| --- | --- | --- |
| `__exit__` 按 `exc_type` 分支 | 正常提交、异常回滚 | `[W1]` |
| 返回 `False` | 异常继续传播 | `[W1]` |
| `ExitStack.enter_context` | 动态管理多个事务 | `[W3]` |
| `stack.callback` | 注册无管理器协议的清理 | `[W3]` |
| 输出逆序 | LIFO 保证依赖正确 | `[W3]` |

> 注意：`ROLLBACK` 之后 `tx2.committed` 仍为 `False`，这是有意的——回滚不等于提交；如果业务需要「已处理」标记，应另设状态字段。`[W4]`

## 9. 注意事项与新手错误对照表

| 错误写法 / 操作 | 报错或现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `__exit__` 返回 `True` 兜底 | 静默吞异常 | 只在明确预期时抑制 | `[W1]` |
| `__exit__` 忘写 `return False` | 默认 `None`，正常传播（不算错） | 显式写更清晰 | `[W1]` |
| `__enter__` 返回 `None` | `as x` 拿到 `None` | 返回 `self` 或目标对象 | `[W1]` |
| 只实现 `__exit__` 不实现 `__enter__` | `TypeError` | 两个都要 | `[W2]` |
| `@contextmanager` 里不写 `try/finally` | 异常时清理逻辑不执行 | 必须包 `try/finally` | `[W3]` |
| `@contextmanager` 里 `yield` 两次 | `RuntimeError: generator didn't stop` | 只 `yield` 一次 | `[W3]` |
| `@contextmanager` 的生成器捕获 `BaseException` | 吞掉退出信号 | 捕具体异常 | `[W4]` |
| `with` 里 `return` | `__exit__` 仍执行（正常路径） | 无问题 | `[W1]` |
| `__exit__` 里 `return` 值当函数返回值理解 | 语义混淆 | 它只表示是否抑制 | `[W1]` |
| 在 `__exit__` 里做耗时 I/O | 退出变慢 | 移到显式方法 | `[W4]` |
| 在 `__enter__` 里做重副作用 | 难以控制时机 | 显式初始化 | `[W4]` |
| 多上下文顺序写反 | 依赖资源先关 | 按依赖顺序声明 | `[W2]` |
| 动态数量用嵌套 `with` | 无法循环 | `ExitStack` | `[W3]` |
| `suppress(Exception)` | 吞掉所有错误 | 具体类型 | `[W4]` |
| `redirect_stdout` 在多线程用 | 输出串台 | 避免或加锁 | `[W3]` |
| 用 `with` 打开后把对象传出块外使用 | 已关闭 | 块内消费完 | `[W3]` |
| 以为 `with` 会捕获异常 | 实际只清理 | 需要捕获就 `try/except` | `[W1]` |
| `__exit__` 抛新异常 | 原异常被替换 | 用 `from` 保留链 | `[W1]` |
| 类实现里 `__exit__` 签名少参数 | `TypeError` | 三参数齐全 | `[W1]` |
| 用 `with` 管理不需要清理的对象 | 增加噪音 | 直接写 | `[W4]` |
| 资源在 `__init__` 获取 | 获取失败没机会清理 | 在 `__enter__` 获取 | `[W1]` |
| `__enter__` 里获取资源失败 | 不会调用 `__exit__` | 自行回滚 | `[W1]` |
| `nullcontext` 当万能占位 | 类型不一致导致下游出错 | 保持接口一致 | `[W3]` |
| `closing` 用于上下文协议对象 | 多余 | 直接 `with` | `[W3]` |
| 异步资源用同步 `with` | `TypeError` | `async with` | `[W8]` |
| `async with` 里阻塞调用 | 阻塞事件循环 | `await` / 线程池 | 第 27 章 |
| `ExitStack` 回调抛异常 | 后续回调仍执行（会记录） | 回调要自己兜底 | `[W3]` |
| 事务在 `__exit__` 里提交失败 | 异常掩盖原错误 | 单独处理 | `[W1]` |
| 依赖 `__exit__` 顺序却用 `suppress` | 状态不一致 | 明确顺序 | `[W3]` |
| 上下文里改全局状态 | 并发污染 | 用局部/参数 | `[W4]` |
| `with` 块里 `break`/`continue` | `__exit__` 正常执行 | 无问题 | `[W1]` |
| 用 `__del__` 替代 `__exit__` | 时机不确定 | 用 `with` | 第 16 章 |

## 10. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 局部资源一律 `with` | 不手写 `try/finally` | `[W4]` |
| 简单场景用 `@contextmanager` | 少写样板 | `[W3]` |
| 复杂状态用类 | 可复用、可扩展 | `[W1]` |
| `@contextmanager` 必写 `try/finally` | 否则泄漏 | `[W3]` |
| 抑制异常要克制并注释 | 不静默失败 | `[W4]` |
| 资源在 `__enter__` 获取 | 失败可感知 | `[W1]` |
| 动态数量用 `ExitStack` | 顺序 LIFO | `[W3]` |
| 命名表达语义 | `tool_session` / `transaction` | `[W4]` |
| 异步用 `async with` | 不阻塞事件循环 | `[W8]` |
| 注释说明清理了什么 | 后来者需要 | `[W4]` |

**风格示范**：

```python
import contextlib


@contextlib.contextmanager
def tool_session(name: str):
    """打开工具会话并在退出时关闭。

    为什么用上下文管理器：会话必须在异常路径也关闭。
    """
    session = open_session(name)
    try:
        yield session
    finally:
        session.close()      # 无论如何都执行
```

**边界**：

- `__exit__` 里不要做网络调用；退出路径应该快且可靠。
- 不要在 `__exit__` 里 `return True` 掩盖错误（除非明确是「忽略不存在」这类预期）。
- 异步上下文管理器不能执行阻塞代码（第 27 章）。

## 11. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[W1]` | python.org | https://docs.python.org/3.12/reference/datamodel.html | `__enter__` / `__exit__` 协议、异常抑制、异常替换 |
| `[W2]` | python.org | https://docs.python.org/3.12/reference/compound_stmts.html | `with` 语句语义、多上下文进入/退出顺序 |
| `[W3]` | python.org | https://docs.python.org/3.12/library/contextlib.html | `@contextmanager`、`suppress`、`closing`、`nullcontext`、`ExitStack`、`redirect_stdout` |
| `[W4]` | PEP 官方 | https://peps.python.org/pep-0008/ | 局部资源用 `with`、不静默失败、命名与注释 |
| `[W5]` | PEP 官方 | https://peps.python.org/pep-0343/ | `with` 语句与 `contextmanager` 的设计动机 |
| `[W6]` | GitHub 官方 | https://github.com/python/cpython/blob/main/Doc/reference/compound_stmts.rst | 官方语言参考源文件（`[W2]` 页脚 Show Source 指向） |
| `[W7]` | PEP 官方 | https://peps.python.org/pep-0020/ | The Zen of Python（显式、简单） |
| `[W8]` | PEP 官方 | https://peps.python.org/pep-0492/ | `async with`、`__aenter__` / `__aexit__` |

> **核对状态**：`[W4]` 与本章 `README.md` 已核对来源一致；其余链接按 `docs.python.org/3.12` 与 `peps.python.org` 官方结构整理，**本次未逐页直连复核**。文中「实测」结论均为本机 Python 3.12.8 运行结果。

## 12. 毕业自查清单

**能说清（概念层）**：

- [ ] `with` 的完整等价展开
- [ ] `__enter__` 与 `__exit__` 各做什么
- [ ] `as` 绑定的是谁
- [ ] `__exit__` 三个参数在正常/异常时的值
- [ ] 返回 `True` 会发生什么、为什么危险
- [ ] `@contextmanager` 里 `yield` 前后分别对应什么
- [ ] 为什么生成器版必须 `try/finally`
- [ ] 多上下文为什么「左进右出」
- [ ] `ExitStack` 解决什么问题
- [ ] `with` 与 `try/finally` 的取舍

**能写出（代码层）**：

- [ ] 类实现的计时器上下文管理器
- [ ] 类实现的事务管理器（提交/回滚）
- [ ] `@contextmanager` 版会话管理器（含 `try/finally`）
- [ ] 用 `suppress` 忽略特定异常
- [ ] 用 `ExitStack` 动态管理多个资源
- [ ] 用 `redirect_stdout` 捕获输出
- [ ] `async with` 版会话（了解）

**能判断（避坑层）**：

- [ ] 看到 `@contextmanager` 缺 `try/finally` 能指出泄漏
- [ ] 看到 `yield` 两次能指出 `RuntimeError`
- [ ] 看到 `__exit__` 无条件 `return True` 能指出吞异常
- [ ] 看到资源在 `__init__` 获取能指出失败无法清理
- [ ] 看到同步 `with` 包异步资源能指出要 `async with`
- [ ] 看到多资源顺序写反能指出依赖问题

**能跑通（验收层）**：

- [ ] 运行 `examples/context_demo.py` 并解释三行顺序
- [ ] 把第 8 节示例存成文件运行，输出与文档一致
- [ ] 在 REPL 验证「`__exit__` 返回 `True` 后异常消失」
- [ ] 手写 `ExitStack` 版本并观察逆序退出

## 13. 下一章衔接

第 20 章 `类型标注`：核心协议到此收束——你已经掌握异常、迭代、上下文三套运行时协议，接下来进入工程化：给函数与数据结构加类型标注，让静态检查器在运行前发现问题。

本章留下的伏笔：

1. `@contextmanager` 依赖生成器的 `finally`，与第 17 章的 `close()` 机制同源。
2. 异步上下文管理器是第 27 章流式输出的基础设施。
3. 异常抑制的克制原则，与第 16 章「不静默失败」是同一套工程纪律。