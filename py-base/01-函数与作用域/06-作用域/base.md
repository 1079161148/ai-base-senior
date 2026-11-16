# 06 作用域 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把 LEGB、`global`、`nonlocal`、闭包、常见错误逐条展开，并补上大纲没列但一定会遇到的边界，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测） |
| 前置 | 第 05 章（函数定义、参数、返回值） |
| 覆盖范围 | LEGB 规则、局部/全局/闭包/内置作用域、`global`、`nonlocal`、闭包机制、六类常见错误 |
| 明确不覆盖 | 类作用域细节（08）、装饰器（13）、`lambda`（07）、模块导入（21） |
| 学完验收 | 能解释 `UnboundLocalError`、能写出闭包计数器、能判断一段代码里每个名字属于哪层作用域（见第 13 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Sn]` `` 指向第 12 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果。

**推荐顺序**：

```text
1 作用域是什么（第 1 节）→ 名字的可见范围
2 LEGB 规则（第 2 节）    → 查找顺序与遮蔽
3 Local（第 3 节）        → 为什么函数内赋值就变局部
4 Global（第 4 节）       → 读、写、global
5 Enclosing（第 5 节）    → 闭包、nonlocal、延迟绑定
6 Builtins（第 6 节）     → 内置名与覆盖风险
7 常见错误（第 7 节）     → UnboundLocalError 与默认参数陷阱
8 速查（第 8 节）         → 判断任何一段代码的作用域
9 综合示例（第 9 节）
10 注意事项（第 10 节）   → 30 条错误对照
```

**与 README 的分工**：README 讲机制轮廓，本文件负责穷举与判定。冲突时以本文件为准。

## 1. 作用域是什么

**定义**：作用域是「一个名字在代码的哪些位置可见」的规则。Python 采用**静态作用域**（词法作用域）——名字属于哪层，在**定义时**就由代码的嵌套结构决定，与运行时调用栈无关。`[S1]` `[S4]`

```python
message = "module"        # 模块级（全局）

def show():
    message = "local"     # 函数级（局部）
    return message

print(show())             # local
print(message)            # module
```

| 概念 | 含义 | 依据 |
| --- | --- | --- |
| 名字绑定 | 赋值把名字绑定到对象 | `[S1]` |
| 作用域 | 名字可见的代码区域 | `[S1]` |
| 静态作用域 | 由代码嵌套结构决定，不由调用关系决定 | `[S4]` |
| 遮蔽 | 内层同名名字挡住外层 | `[S1]` |

**为什么需要作用域**：

| 收益 | 说明 | 依据 |
| --- | --- | --- |
| 隔离 | 函数内变量不会污染外部 | `[S1]` |
| 可推理 | 看代码嵌套就知道名字从哪来 | `[S4]` |
| 闭包 | 内层函数可以带着外层变量离开 | `[S1]` |
| 避免命名冲突 | 不同函数可复用同名变量 | `[S1]` |

**四层总览**：

```text
L  Local      当前函数内部
E  Enclosing  外层函数（嵌套定义时）
G  Global     当前模块（.py 文件顶层）
B  Builtins   Python 内置名字（len、print、True...）
```

> 注意：Python 没有「块级作用域」——`if` / `for` / `while` / `with` 内部赋值的变量，在块外**仍然可见**（函数级作用域）。`[S1]`

```python
if True:
    inside_if = 1

print(inside_if)     # 1，if 不构成作用域
```

## 2. LEGB 规则

### 2.1 查找顺序

名字解析按 **L → E → G → B** 依次查找，**找到第一个就停**，不会继续向外找。`[S1]`

```python
value = "global"

def outer():
    value = "enclosing"

    def inner():
        value = "local"
        print(value)      # local

    inner()

outer()
```

| 顺序 | 作用域 | 找不到时 |
| --- | --- | --- |
| 1 | Local | 继续向外 |
| 2 | Enclosing | 继续向外 |
| 3 | Global | 继续向外 |
| 4 | Builtins | 仍找不到 → `NameError` |

### 2.2 逐层演示

```python
value = "global"          # G

def outer():
    value = "enclosing"   # E

    def inner():
        print(value)      # 找到 E，打印 enclosing

    inner()

outer()
```

```python
value = "global"

def outer():
    def inner():
        print(value)      # 本地没有、外层没有 → 找到 G

    inner()

outer()
```

```python
def show():
    print(len("abc"))     # 本地/外层/全局都没有 len → 找到 B

show()
```

### 2.3 遮蔽（shadowing）

```python
name = "global"

def show():
    name = "local"        # 遮蔽全局
    return name

print(show(), name)       # local global（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 遮蔽只在函数内生效 | 离开函数后外层名字不变 | `[S1]` |
| 遮蔽不看赋值先后 | 只要函数内有赋值，整个函数内都是局部 | `[S1]` |
| 遮蔽容易造成误读 | 同名不同义，改名更清楚 | `[S7]` |

> 注意：遮蔽不是错误，但同名会让人误以为在改外部变量；需要区分时改名（`local_name`）比加注释有效。`[S7]`

### 2.4 内置作用域 Builtins

```python
print(isinstance(1, int))     # print / isinstance / int 都来自 builtins
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 内置名在一个模块里 | `builtins` 模块，启动时自动可用 | `[S9]` |
| 可以被遮蔽 | 模块级或函数级赋值会挡住它 | `[S1]` |
| 优先级最低 | 最后才查 | `[S1]` |

> 注意：内置名不是关键字，可以覆盖；一旦覆盖，同一作用域内所有调用都会失败。`[S1]`

### 2.5 优先级实验（不用运行也能推）

```python
x = 1
def f():
    x = 2
    def g():
        x = 3
        return x      # 3，L
    return g()
print(f(), x)         # 3 1
```

| 问题 | 答案 | 依据 |
| --- | --- | --- |
| `g` 里 `x` 取哪层？ | Local（3） | `[S1]` |
| 去掉 `g` 里的 `x = 3`？ | Enclosing（2） | `[S1]` |
| 再去掉 `f` 里的 `x = 2`？ | Global（1） | `[S1]` |
| 全局也没有？ | `NameError` | `[S1]` |

## 3. 局部作用域 Local

### 3.1 函数内赋值即局部

```python
counter = 0

def increase():
    counter = 1          # 这是新局部变量，不是改全局
    return counter

print(increase(), counter)   # 1 0（实测 SHADOW 同款）
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 函数内赋值 → 局部 | 除非用 `global` / `nonlocal` 声明 | `[S1]` |
| 局部变量随函数调用创建 | 每次调用都是新的 | `[S1]` |
| 调用结束即销毁 | 返回值之后不可访问 | `[S1]` |

### 3.2 参数也是局部变量

```python
value = "global"

def show(value):          # 形参是局部名字，遮蔽全局
    return value

print(show("arg"), value) # arg global
```

> 注意：形参与函数内赋值同等对待；给形参重新赋值不会影响调用方（第 05 章「参数传递」）。`[S1]`

### 3.3 局部变量的判定发生在编译期

这是理解 `UnboundLocalError` 的关键：**只要函数体内某处对名字赋值，该名字在整个函数内就是局部**，不管赋值语句在不在执行路径上。`[S1]`

```python
def broken():
    print(counter_value)   # 编译期已判定 counter_value 是局部
    counter_value = 0      # 但执行到这里之前，局部还没绑定

try:
    broken()
except UnboundLocalError as error:
    print(type(error).__name__)   # UnboundLocalError（实测）
```

| 现象 | 原因 | 依据 |
| --- | --- | --- |
| 读一个「函数内后面才赋值」的名字 | 编译期已归为局部，运行时未绑定 | `[S1]` |
| 报错类型是 `UnboundLocalError` | `NameError` 的子类，专指「局部未绑定」 | `[S1]` |
| 加 `global` 能解决 | 声明后该名字指向模块级 | `[S2]` |

> 注意：这不是「执行顺序」问题，而是「变量分类」问题；把赋值删掉或加 `global` 都能修复，但语义完全不同。`[S1]`

### 3.4 局部作用域的生命周期

```python
def make():
    temp = [1, 2]
    return temp

result = make()
print(result)       # [1, 2]，对象被返回后仍然存活
# print(temp)       NameError：名字 temp 只在函数内存在
```

| 对象 | 名字 | 依据 |
| --- | --- | --- |
| 函数结束后名字消失 | 局部变量名不可再访问 | `[S1]` |
| 对象可能继续存活 | 被返回/被闭包引用就不会回收 | `[S1]` |

> 注意：「名字消失」和「对象销毁」是两件事；闭包正是靠「对象被引用」让局部变量活过函数调用。`[S1]`

## 4. 全局作用域 Global

### 4.1 模块级变量

```python
call_count = 0        # 模块级
def read():
    return call_count # 读：不需要声明

print(read())         # 0
```

| 操作 | 是否需要声明 | 依据 |
| --- | --- | --- |
| 读全局变量 | 不需要 | `[S1]` |
| 调用全局变量的方法（原地修改） | 不需要 | `[S1]` |
| 给全局变量**重新赋值** | 需要 `global` | `[S1]` `[S2]` |

### 4.2 函数内读全局

```python
counter_value = 1

def read_global():
    return counter_value

print(read_global())   # 1（实测）
```

### 4.3 函数内写全局（不加 `global`）

```python
counter_value = 1

def shadow_global():
    counter_value = 2      # 新局部变量
    return counter_value

print(shadow_global(), counter_value)   # 2 1（实测）
```

| 你以为 | 实际 |
| --- | --- |
| 改了全局 | 创建了同名局部 |
| 全局变成 2 | 全局仍是 1 |

> 注意：这是「静默失败」的典型——不报错、结果不对；排查时先看函数内有没有同名赋值。`[S1]`

### 4.4 `global` 声明

```python
counter_value = 1

def write_global():
    global counter_value    # 声明：这个名字指向模块级
    counter_value = 3

write_global()
print(counter_value)        # 3（实测）
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 声明位置 | 函数体内，通常放最前面 | `[S2]` |
| 作用范围 | 整个函数（编译期生效），不是「声明之后」 | `[S2]` |
| 可声明多个 | `global a, b` | `[S2]` |
| 不能先使用后声明 | 会 `SyntaxError: name 'x' is assigned to before global declaration` | `[S2]` |
| 声明后仍可读 | 读写都指向全局 | `[S2]` |

```python
def bad_order():
    counter_value = 1
    global counter_value    # SyntaxError（编译期）
```

> 注意：`global` 是「模块级」，不是「跨模块」；跨模块共享状态应通过模块导入（第 21 章），不要靠全局变量。`[S2]` `[S7]`

### 4.5 `global` 的风险与替代

| 风险 | 说明 | 替代 | 依据 |
| --- | --- | --- | --- |
| 隐式耦合 | 谁改了全局很难追 | 参数传入、返回值传出 | `[S7]` |
| 难测试 | 测试间互相污染 | 用类/闭包封装状态 | `[S7]` |
| 并发不安全 | 多线程共享写 | 加锁或避免共享（28） | `[S7]` |
| 阅读成本 | 看函数看不出依赖 | 显式参数 | `[S7]` |

```python
# 更好：用参数与返回值，而不是 global
def record_call(current):
    """返回加一后的计数，由调用方保存。"""
    return current + 1

call_count = record_call(call_count)
```

> 注意：`global` 不是禁止使用，而是「默认不用」；配置常量（全大写）读取没问题，可变状态尽量封装。`[S7]`

### 4.6 模块级 `__name__`

```python
print(__name__)      # 直接运行时是 "__main__"，被导入时是模块名
```

| 场景 | `__name__` 值 | 依据 |
| --- | --- | --- |
| `python script.py` | `"__main__"` | `[S3]` |
| `import script` | `"script"` | `[S3]` |
| 入口判断 | `if __name__ == "__main__":` | `[S3]` |

> 注意：`__name__` 是模块级全局变量，属于 Global 作用域；入口判断的完整用法在第 21 章。`[S3]`

## 5. 闭包作用域 Enclosing

### 5.1 嵌套函数

```python
def outer():
    prefix = "call-"

    def inner(number):
        return prefix + str(number)   # 引用外层变量

    return inner(2)

print(outer())      # call-2（README 同款）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 内层函数能读外层变量 | Enclosing 作用域 | `[S1]` `[S4]` |
| 内层函数不能直接改外层变量 | 赋值会变局部 | `[S1]` |
| 要改需 `nonlocal` | 3.x 引入 | `[S5]` |

### 5.2 `nonlocal`

```python
def outer_nonlocal():
    total = 0

    def inner():
        nonlocal total     # 声明：total 来自外层函数
        total += 1
        return total

    inner()
    inner()
    return total

print(outer_nonlocal())    # 2（实测）
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 只能用于嵌套函数 | 模块级写 `nonlocal` 是 `SyntaxError` | `[S5]` |
| 必须存在外层绑定 | 外层没有该名字 → 编译期 `SyntaxError` | `[S5]` |
| 跳过多层 | 就近绑定到最近的外层函数 | `[S5]` |
| 不创建新变量 | 只声明「这个名字在外层」 | `[S5]` |

> 注意：`nonlocal` 找不到外层绑定时是**编译期**错误，`try/except SyntaxError` 捕获不到——整个文件都无法导入。`[S5]`

### 5.3 闭包的本质

**闭包 = 内层函数 + 它引用的外层变量（cell）**。外层函数返回内层函数后，cell 仍然存活。`[S1]` `[S4]`

```python
def make_counter():
    count = 0

    def inc():
        nonlocal count
        count += 1
        return count

    return inc

counter = make_counter()
print(counter(), counter())        # 1 2（实测）
print(counter.__closure__[0].cell_contents)   # 2（实测）
```

| 属性 | 含义 | 依据 |
| --- | --- | --- |
| `__closure__` | cell 元组；没有闭包时为 `None` | `[S1]` |
| `cell_contents` | 当前捕获的值 | `[S1]` |
| 同名多变量 | 每个被捕获变量一个 cell | `[S1]` |

> 注意：`counter.__closure__[0].cell_contents` 只是调试手段，业务代码不要依赖；它能证明「变量活在函数之外」。`[S1]`

### 5.4 闭包 vs 全局 vs 类

| 方案 | 状态存在哪 | 优点 | 缺点 |
| --- | --- | --- | --- |
| `global` | 模块级 | 简单 | 全局污染、难测试 |
| 闭包 | 外层函数的 cell | 封装、可造多个独立实例 | 调试时看不见状态 |
| 类（08） | 实例属性 | 显式、可扩展 | 代码量稍多 |

```python
counter_a = make_counter()
counter_b = make_counter()
print(counter_a(), counter_b())    # 1 1，两个独立状态
```

> 注意：每次调用 `make_counter()` 都创建新的 cell，所以多个计数器互不影响——这是闭包比全局变量强的地方。`[S1]`

### 5.5 延迟绑定陷阱

```python
handlers = []
for index in range(3):
    handlers.append(lambda: index)

print([handler() for handler in handlers])   # [2, 2, 2]（实测）
```

**原因**：闭包捕获的是**变量**，不是当时的值；循环结束后 `index` 是 2。

**两种修复**：

```python
# 1 默认参数在定义时求值
handlers = []
for index in range(3):
    handlers.append(lambda index=index: index)
print([handler() for handler in handlers])   # [0, 1, 2]（实测）

# 2 工厂函数固化
def make_handler(value):
    return lambda: value

handlers = [make_handler(index) for index in range(3)]
print([handler() for handler in handlers])   # [0, 1, 2]
```

| 方案 | 原理 | 依据 |
| --- | --- | --- |
| `lambda index=index` | 默认参数在定义时求值 | `[S1]` |
| 工厂函数 | 每次调用生成新 cell | `[S1]` |

> 注意：这是「词法作用域 + 延迟求值」的必然结果，不是 bug；凡是「循环里创建函数」都要检查这一点。`[S1]`

## 6. 内置作用域 Builtins

### 6.1 内置名来自 `builtins` 模块

```python
import builtins

print(builtins.len("abc"))     # 3
print(len("abc"))              # 3，等价
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `builtins` 是普通模块 | 可用 `dir(builtins)` 查看全部内置名 | `[S9]` |
| 内置名可被遮蔽 | 模块级/函数级赋值生效 | `[S1]` |
| 屏蔽后如何恢复 | 删除遮蔽名或显式 `builtins.xxx` | `[S9]` |

### 6.2 覆盖内置名的风险

```python
len = 3          # 模块级覆盖
# len([1, 2])    TypeError: 'int' object is not callable

del len          # 删除后重新查找到 builtins
print(len([1, 2]))   # 2
```

| 常见误覆盖 | 后果 |
| --- | --- |
| `list = [...]` | 后续 `list(...)` 全部失败 |
| `str = "x"` | 类型转换失效 |
| `sum = 0` | 聚合函数失效 |
| `id` / `type` / `input` | 调试与交互全部异常 |

> 注意：局部变量遮蔽内置名只影响该函数；模块级遮蔽影响整个文件。命名时避开内置名是最省事的做法。`[S7]`

### 6.3 排查方法

| 手段 | 用途 | 依据 |
| --- | --- | --- |
| `print(len)` | 看它被什么覆盖了 | `[S9]` |
| `dir(builtins)` | 确认原本有哪些内置名 | `[S9]` |
| `globals()` / `locals()` | 看当前绑定 | `[S6]` |

> 注意：`TypeError: 'int' object is not callable` 出现在调用内置函数时，先查有没有同名变量。`[S9]`

## 7. 常见错误

### 7.1 错误 1：在函数内同时读写全局变量

```python
counter_value = 1

def broken():
    print(counter_value)     # 编译期判定为局部
    counter_value = 0        # 执行到这里之前，局部未绑定

try:
    broken()
except UnboundLocalError as error:
    print(type(error).__name__)   # UnboundLocalError（实测）
```

| 你会以为 | 实际发生 | 依据 |
| --- | --- | --- |
| 先读到全局 1 | 编译期已把名字归为局部 | `[S1]` |
| 然后赋值为 0 | 读取时局部还没绑定 → 报错 | `[S1]` |

**三种修复，语义不同**：

```python
# 1 只想读：去掉函数内的赋值
def read_only():
    return counter_value

# 2 想改全局：声明 global
def write_global():
    global counter_value
    counter_value = 0

# 3 想用局部：换个名字
def local_only():
    local_counter = 0
    return local_counter
```

> 注意：报错信息是 `cannot access local variable 'x' where it is not associated with a value`，关键词是 **local variable**——说明编译器已经把它当局部了。`[S1]`

### 7.2 错误 2：默认参数陷阱

```python
def collect(value, bucket=[]):
    bucket.append(value)
    return bucket

print(collect("a"))    # ['a']
print(collect("b"))    # ['a', 'b']（实测，累积了）
```

| 原因 | 说明 | 依据 |
| --- | --- | --- |
| 默认值在 `def` 时求值一次 | 之后复用同一个 list | `[S1]` |
| 默认值存在 `__defaults__` | 可通过 `f.__defaults__` 看到 | `[S1]` |
| 与作用域的关系 | 默认值是模块级对象，被函数长期引用 | `[S1]` |

**修复**：

```python
def collect(value, bucket=None):
    if bucket is None:
        bucket = []
    bucket.append(value)
    return bucket
```

> 注意：这个陷阱常被误认为「作用域问题」，本质是「默认值求值时机」；但它的表现（状态跨调用保留）与闭包很像，所以放在本章一起记。`[S1]` `[S7]`

### 7.3 错误 3：循环变量泄漏

```python
for loop_index in range(3):
    pass

print(loop_index)     # 2（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `for` 不构成作用域 | 循环变量留在当前函数/模块作用域 | `[S1]` |
| 循环结束后仍可访问 | 值是最后一次的值 | `[S1]` |
| 容易与「推导式」混淆 | 两者行为不同，见 7.4 | `[S1]` |

> 注意：循环变量在循环外可见是 Python 的设计（函数级作用域），不是 bug；不想污染就用推导式或局部函数。`[S1]`

### 7.4 错误 4：以为推导式会泄漏变量

```python
x_global = "global"
result = [x_global for x_global in range(3)]

print(x_global)   # global，没被改（实测）
print(result)     # [0, 1, 2]
```

| 结构 | 变量是否泄漏 | 依据 |
| --- | --- | --- |
| `for` 循环 | **泄漏** | `[S1]` |
| 列表/字典/集合推导式 | **不泄漏**（3.x 起有独立作用域） | `[S1]` |
| 生成器表达式 | 不泄漏 | `[S1]` |

> 注意：推导式内部的循环变量是推导式自己的作用域；这也解释了为什么 `[x for x in ...]` 里能放心用 `x` 而不担心覆盖外部。`[S1]`

### 7.5 错误 5：类体不参与 LEGB 的 Enclosing

```python
class Holder:
    value = 1

    def read(self):
        return value      # 找不到，不会自动去类体找

try:
    Holder().read()
except NameError as error:
    print(type(error).__name__)   # NameError（实测）
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 类体是独立命名空间 | 不构成函数闭包的外层 | `[S8]` |
| 方法内访问类变量 | 要写 `self.value` 或 `Holder.value` | `[S8]` |
| 类体里可以写推导式 | 但推导式看不到类变量 | `[S8]` |

> 注意：这是第 08 章「类和对象」要展开的第一个坑；现在只需记住「类不是作用域链的一环」。`[S8]`

### 7.6 错误 6：`except` 变量在块结束后被删除

```python
try:
    try:
        1 / 0
    except ZeroDivisionError as exc:
        pass
    print(exc)          # 块外访问
except NameError as error:
    print(type(error).__name__)   # NameError（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `as exc` 的名字在 `except` 块结束时被删除 | 防止循环引用与作用域污染 | `[S3]` |
| 想在块外使用 | 提前赋给另一个变量 | `[S3]` |

> 注意：这条常让新手困惑「为什么 except 里能打印、出了块就不行」；把异常对象先存到普通变量即可。`[S3]`

### 7.7 错误 7：闭包延迟绑定（已在 5.5 讲）

| 现象 | 原因 | 修复 |
| --- | --- | --- |
| 循环里创建的函数都返回最后一个值 | 捕获变量而非值 | `lambda i=i` / 工厂函数 |

> 注意：凡是在循环里创建 `lambda` 或内层函数，都要检查是否存在延迟绑定问题。`[S1]`

## 8. 作用域速查

### 8.1 场景对照表（直接查结论）

| 你的代码 | 名字属于 | 结果 / 依据 |
| --- | --- | --- |
| 模块顶层 `x = 1` | Global | 全模块可读 `[S1]` |
| 函数内 `x = 1` | Local | 只在该函数内 `[S1]` |
| 函数内读模块级 `x` | Global | 可以，无需声明 `[S1]` |
| 函数内写模块级 `x` | Local（新变量） | 全局不变 `[S1]` |
| 函数内 `global x; x = 1` | Global | 改到模块级 `[S2]` |
| 内层函数读外层 `x` | Enclosing | 可以 `[S1]` |
| 内层函数写外层 `x` | Local（新变量） | 外层不变 `[S1]` |
| 内层函数 `nonlocal x; x = 1` | Enclosing | 改到外层 `[S5]` |
| 只有 `print(...)` 等内置调用 | Builtins | 最后才查 `[S1]` |
| 函数内 `if` / `for` 里赋值 | Local | 块外仍可见 `[S1]` |
| 推导式循环变量 | 推导式内部 | 不泄漏 `[S1]` |
| 类体中定义的方法访问类变量 | 不自动查找 | 要 `self.` `[S8]` |
| `except ... as exc` 块外使用 `exc` | 已删除 | `NameError` `[S3]` |

### 8.2 判断一个名字属于哪层（四步）

```text
1 这个名字在当前函数内有没有被赋值（含参数、for 目标、with as、import as）？
   有 → Local（除非声明了 global/nonlocal）
2 没有赋值：当前函数是不是嵌套在内层？
   是 → 逐层向外找，找到第一个赋值处 → Enclosing
3 还没找到：模块顶层有没有？
   有 → Global
4 还没有：builtins 里有没有？
   有 → Builtins；没有 → NameError
```

> 注意：第 1 步的「有没有被赋值」看的是**整个函数体**，不是执行顺序——这就是 `UnboundLocalError` 的来源。`[S1]`

### 8.3 `locals()` / `globals()` / `dir()`

```python
def local_scope():
    inside = "local"
    return inside, sorted(locals().keys())

print(local_scope())          # ('local', ['inside'])（实测）
print(locals() is globals())  # True，模块级两者相同（实测）
```

| 函数 | 返回 | 依据 |
| --- | --- | --- |
| `locals()` | 当前局部命名空间快照 | `[S6]` |
| `globals()` | 模块级命名空间字典 | `[S6]` |
| `dir()` | 当前可见名字列表 | `[S6]` |

> 注意：调试时用它们确认「这个名字到底绑在哪」，比猜快得多；但不要用它们修改作用域。`[S6]`

### 8.4 各层可见性矩阵

| 从 \ 看 | Local | Enclosing | Global | Builtins |
| --- | --- | --- | --- | --- |
| 函数内部 | ✅ | ✅ | ✅ | ✅ |
| 外层函数 | ❌ | ✅ | ✅ | ✅ |
| 模块顶层 | ❌ | ❌ | ✅ | ✅ |
| 其他模块 | ❌ | ❌ | 需 `import` | 需 `import builtins` |

> 注意：内层能看到外层，外层看不到内层——这是「单向可见」；闭包之所以能工作，是因为内层函数对象被返回后仍然持有外层 cell。`[S1]`

## 9. 综合示例：闭包计数器

```python
"""第 06 章综合示例：用闭包封装状态，避免 global。"""


def make_tool_counter():
    """返回一个带状态的闭包计数器。"""
    counts = {}

    def record(name):
        counts[name] = counts.get(name, 0) + 1
        return counts[name]

    return record


record = make_tool_counter()
print(record("search"), record("search"), record("cache"))
```

本机实测输出：

```text
1 2 1
```

**逐段说明**：

| 代码 | 作用域要点 | 依据 |
| --- | --- | --- |
| `counts = {}` | 外层函数局部变量，被内层捕获 | `[S1]` |
| `def record(name):` | 内层函数，`name` 是它自己的局部 | `[S1]` |
| `counts[name] = ...` | 原地修改 dict，**不需要 `nonlocal`** | `[S1]` |
| `return record` | 返回函数对象，cell 随之存活 | `[S1]` |
| `record("search")` 两次 | 同一个 cell，状态累积 | `[S1]` |

**为什么不需要 `nonlocal`**：

| 操作 | 是否重新绑定 `counts` 这个名字 | 需要 `nonlocal` 吗 |
| --- | --- | --- |
| `counts[name] = ...` | 否（改的是 dict 内容） | 不需要 |
| `counts = {}` | 是（换了个对象） | 需要 |

> 注意：`nonlocal` 管的是「名字重新绑定」，不是「对象内容修改」；可变对象天然可以跨作用域共享。`[S1]` `[S5]`

**两个独立计数器**：

```python
a = make_tool_counter()
b = make_tool_counter()
print(a("search"), b("search"), a("cache"))   # 1 1 1
```

> 注意：每次调用 `make_tool_counter()` 都生成新的 cell，所以 `a` 与 `b` 状态互不影响——这是闭包优于 `global` 的核心原因。`[S1]`

## 10. 注意事项与新手错误对照表

| 错误写法 / 操作 | 报错或现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 函数内改全局不写 `global` | 静默创建局部，全局不变 | 加 `global` 或换设计 | `[S1]` |
| 函数内先读后写同名全局 | `UnboundLocalError` | 先声明 `global` 或改名 | `[S1]` |
| `global` 写在赋值之后 | `SyntaxError` | 声明放函数体开头 | `[S2]` |
| 模块级用 `nonlocal` | `SyntaxError` | 只能用于嵌套函数 | `[S5]` |
| `nonlocal` 无外层绑定 | 编译期 `SyntaxError` | 先在外层赋值 | `[S5]` |
| 默认参数写 `[]` | 跨调用累积 | `None` 哨兵 | `[S1]` `[S7]` |
| 默认参数写函数调用 | 只在定义时算一次 | 函数内计算 | `[S1]` |
| 循环里创建闭包 | 全部返回最终值 | `lambda i=i` 或工厂 | `[S1]` |
| 以为 `if` 有作用域 | 变量泄漏到函数级 | 正常现象，命名注意 | `[S1]` |
| 以为推导式泄漏 | 实际不泄漏 | 不用特殊处理 | `[S1]` |
| 方法内直接访问类变量 | `NameError` | `self.value` | `[S8]` |
| `except` 变量块外使用 | `NameError` | 先赋给普通变量 | `[S3]` |
| 覆盖 `len` / `list` | `TypeError: not callable` | 改名 | `[S9]` |
| 用 `global` 传状态 | 难测试、难追踪 | 参数/返回值/闭包 | `[S7]` |
| 闭包内改外层不声明 | `UnboundLocalError` | `nonlocal` | `[S5]` |
| `del` 后继续使用名字 | `NameError` | 删除后重新赋值 | `[S1]` |
| 以为参数是引用传递 | 重新赋值无效 | 用返回值接收 | `[S1]` |
| 同名遮蔽外层 | 结果与预期不符 | 改名 | `[S7]` |
| 模块级变量当常量却修改 | 其他函数读到新值 | 用全大写 + 不改 | `[S7]` |
| `if __name__ == "__main__"` 拼错 | 入口逻辑不执行 | 对照拼写 | `[S3]` |
| 函数内 `import` 后当全局用 | 其他函数 `NameError` | 提到模块顶部 | `[S3]` |
| 多线程共享全局写 | 数据竞争 | 加锁/避免共享（28） | `[S7]` |
| 递归中误用 `global` 累加 | 多次调用互相污染 | 用参数传递 | `[S7]` |
| 嵌套函数同名遮蔽 | 调用到外层版本 | 改名 | `[S1]` |
| `global` 后又写局部同名 | 实际都指向全局 | 明确只用一种 | `[S2]` |
| 变量名拼写错误 | 创建了新变量，不报错 | 用静态检查/仔细核对 | `[S7]` |
| 函数内 `del` 全局 | 需要 `global` 声明 | `global x; del x` | `[S2]` |
| 闭包持有大对象 | 内存不释放 | 只捕获需要的值 | `[S1]` |
| 推导式内同名变量 | 遮蔽外层同名 | 换名或确认意图 | `[S1]` |
| 循环闭包默认值忘写 | 延迟绑定 | `i=i` | `[S1]` |

## 11. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 默认不用 `global` | 用参数/返回值传状态 | `[S7]` |
| 需要状态优先闭包或类 | 可造多个实例、可测试 | `[S1]` |
| 默认参数用 `None` 哨兵 | 避免可变默认值共享 | `[S1]` |
| 避开内置名 | `len` / `list` / `sum` / `id` 不要当变量 | `[S9]` |
| 循环创建函数时固化变量 | `lambda i=i` 或工厂函数 | `[S1]` |
| 变量名见名知意 | 减少遮蔽与拼错 | `[S7]` |
| 模块级只放常量与入口 | 状态放函数/类里 | `[S7]` |
| 用 `if __name__ == "__main__"` | 区分「运行」与「被导入」 | `[S3]` |

**命名与风格** `[S7]`：

- 常量：`UPPER_CASE`；普通变量：`lowercase_with_underscores`。
- 表示「全局配置」的名字加前缀，如 `DEFAULT_TIMEOUT`，避免与局部混淆。
- 函数内不要出现与模块级同名的局部变量（遮蔽的第一大来源）。

**边界与安全**：

- 闭包捕获大对象（大列表、连接）会导致内存无法释放；只捕获必要的值。
- 多线程共享可变全局必须同步（第 28 章），否则结果不可预测。
- `global` 修改的配置在测试之间会互相污染；测试要显式重置。

## 12. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[S1]` | python.org | https://docs.python.org/3.12/reference/executionmodel.html | 名字绑定、作用域层级、LEGB、`UnboundLocalError`、闭包 cell、局部/全局判定 |
| `[S2]` | python.org | https://docs.python.org/3.12/reference/simple_stmts.html | `global` / `nonlocal` 语句规则与 `SyntaxError` 条件 |
| `[S3]` | python.org | https://docs.python.org/3.12/reference/compound_stmts.html | 函数定义、`except ... as` 变量删除、`import as` 绑定 |
| `[S4]` | PEP 官方 | https://peps.python.org/pep-0227/ | 嵌套作用域（静态/词法作用域）设计 |
| `[S5]` | PEP 官方 | https://peps.python.org/pep-3104/ | `nonlocal` 的语义与限制 |
| `[S6]` | python.org | https://docs.python.org/3.12/library/functions.html | `locals()` / `globals()` / `dir()` / `vars()` |
| `[S7]` | PEP 官方 | https://peps.python.org/pep-0008/ | 命名、避免全局状态、可读性 |
| `[S8]` | python.org | https://docs.python.org/3.12/tutorial/classes.html | 类作用域不参与 Enclosing、`self` 访问 |
| `[S9]` | python.org | https://docs.python.org/3.12/library/builtins.html | 内置命名空间与内置函数清单 |
| `[S10]` | GitHub 官方 | https://github.com/python/cpython/blob/main/Doc/reference/executionmodel.rst | 官方语言参考源文件（`[S1]` 页脚 Show Source 指向） |

> **核对状态**：`[S1]` `[S7]` 与本章 `README.md` 已核对来源一致；其余链接按 `docs.python.org/3.12` 与 `peps.python.org` 官方结构整理，**本次未逐页直连复核**。文中「实测」结论均为本机 Python 3.12.8 运行结果。

## 13. 毕业自查清单

**能说清（概念层）**：

- [ ] LEGB 四个字母分别代表什么，查找顺序与「找到即停」
- [ ] 为什么说 Python 是静态（词法）作用域，而不是动态作用域
- [ ] 函数内赋值为什么默认是局部变量
- [ ] `UnboundLocalError` 与 `NameError` 的关系与区别
- [ ] `global` 与 `nonlocal` 分别解决什么问题，各自限制是什么
- [ ] 闭包是什么，变量为什么能活过外层函数
- [ ] 为什么循环里创建的闭包都返回最后一个值
- [ ] 为什么类体不参与 LEGB
- [ ] 为什么 `except as exc` 的变量出了块就没了
- [ ] 推导式与 `for` 循环在变量泄漏上为什么不同

**能写出（代码层）**：

- [ ] 用闭包写一个计数器，并创建两个互不影响的实例
- [ ] 用 `nonlocal` 修改外层变量
- [ ] 用 `global` 修改模块级计数，并说明风险
- [ ] 用 `None` 哨兵规避默认参数陷阱
- [ ] 用 `lambda i=i` 修复循环闭包
- [ ] 用 `locals()` / `globals()` 排查名字绑定

**能判断（避坑层）**：

- [ ] 看到「函数内先读后写同名全局」能立刻指出 `UnboundLocalError`
- [ ] 看到「函数内改全局没写 `global`」能指出全局没变
- [ ] 看到 `def f(bucket=[])` 能指出跨调用累积
- [ ] 看到循环里 `lambda: i` 能指出最后都是同一个值
- [ ] 看到方法里直接写类变量名能指出 `NameError`
- [ ] 看到覆盖 `len` / `list` 能指出 `TypeError`

**能跑通（验收层）**：

- [ ] 运行 `examples/scope_demo.py` 并解释 `call_count` 为什么是 2
- [ ] 把第 9 节示例存成文件运行，输出 `1 2 1`
- [ ] 在 REPL 复现 `UnboundLocalError` 并解释原因
- [ ] 手写「读模块级计数 → 用闭包封装 → 两个独立实例」的完整脚本

## 14. 下一章衔接

第 07 章 `lambda 表达式`：本章的闭包与延迟绑定会直接出现在 `lambda` 里——`lambda` 没有自己的语句块，它的函数体就是一个表达式，所以「捕获变量而非值」的表现更明显。第 07 章会讲清：

1. `lambda` 与 `def` 的等价关系与能力边界（为什么不能写语句、不能有 docstring）。
2. 为什么 PEP 8 反对 `f = lambda: ...` 这种赋值写法。
3. `sorted(key=...)`、`map`、`filter`、`max/min(key=...)`、`reduce` 这五个高频场景的正确用法。

本章的 `nonlocal`、默认参数陷阱、循环闭包三块，是第 07 章所有反例的基础。