# 03 Python 基本语法 · 完整版（base.md）

> `README.md` 给的是「最小闭环」；本文件是**一遍学完即可毕业**的完整语法手册：把大纲里的每条逐条展开，并补上大纲没列、但写 Python 一定会遇到的基础语法。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测）；3.10+ 差异点单独标注 |
| 前置 | 第 02 章（解释器、REPL、`python -c` 可用） |
| 覆盖范围 | 词法、数据类型、变量、字符串格式化、运算符、输入输出、流程控制 |
| 明确不覆盖 | 函数（05）、作用域（06）、`lambda`（07）、类（08+）、容器进阶（04）、异常处理（16）、`import`（21） |
| 学完验收 | 能独立写出带条件、循环、格式化输出的完整脚本，并能解释每行输出（见第 13 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Bn]` `` 指向第 12 节的官方链接；标「实测」的是本机 Python 3.12.8 的运行结果，不是官方依据。

**推荐顺序**（每步都在 REPL 或 `python -c` 里验证一次再往下走）：

```text
1 语言特征（第 1 节）→ 知道 Python 和 Java/TS 差在哪
2 词法（第 2 节）      → 编码、缩进、行、注释、标识符、关键字
3 数据类型（第 3 节）  → 有什么值可用
4 变量（第 4 节）      → 怎么给值起名字、怎么转换
5 格式化（第 5 节）    → 怎么把值变成人看的文本
6 运算符（第 6 节）    → 怎么算、怎么比
7 输入输出（第 7 节）  → 怎么和用户交互
8 流程控制（第 8 节）  → 怎么让程序做选择、重复
9 综合示例（第 9 节）  → 把上面全部串起来
10 注意事项与错误对照表（第 10 节）→ 自查你踩的坑
```

**与 README 的分工**：README 解释「为什么这样设计」，本文件负责「语法点穷举 + 可查可用」。两者冲突时以本文件为准（本文件沿用了 README 的结论并做了补充）。

## 1. 语言基本特征

| 特征 | 准确含义 | 对你写代码的影响 | 依据 |
| --- | --- | --- | --- |
| 先编译成字节码再解释执行 | CPython 把源码编译为字节码，由虚拟机执行；不是逐字符「纯解释」 | 语法错误在运行前就报；逻辑错误才在运行时暴露 | `[B1]` `[B19]` |
| 动态类型 | 变量没有类型，**对象**才有类型；类型在运行时确定 | 同一个名字可以先绑 `int` 再绑 `str`，不需要声明 | `[B19]` |
| 强类型 | 不做隐式跨类型转换 | `"1" + 1` 直接 `TypeError`；JavaScript 那种自动拼接不存在 | `[B19]` |
| 一切皆对象 | 数字、字符串、函数、类、模块都是对象 | 都能赋值给名字、都能 `type()` 看类型 | `[B19]` |
| 缩进即语法 | 用缩进划分代码块，不用 `{}` | 缩进写错不是「不好看」，是 `IndentationError` | `[B4]` `[B9]` |
| 可读性优先 | `import this` 可看 The Zen of Python | 官方风格把「显式、简单、扁平」写在语言哲学里 | `[B21]` |
| 自动内存管理 | 引用计数为主，循环垃圾由 GC 回收 | 不用手动 `free`；但「还有引用」的对象不会释放（第 04 章别名） | `[B19]` |

**和常见语言的差异**（新手最容易带着旧习惯写错的地方）：

| 场景 | Java / TypeScript 习惯 | Python 正确写法 |
| --- | --- | --- |
| 代码块 | `{ }` | 缩进 + `:` |
| 变量声明 | `int x = 1;` | `x = 1`（无声明） |
| 布尔 | `true / false` | `True / False`（首字母大写） |
| 空值 | `null / undefined` | `None` |
| 字符串拼接数字 | 自动转换 | 必须 `str(n)` 或 f-string |
| 自增 | `i++` | **没有** `++`，写 `i += 1` |
| 三元 | `c ? a : b` | `a if c else b` |
| 循环 | `for (i=0;i<n;i++)` | `for i in range(n):` |

> 注意：Python 没有 `switch`（3.10 起有 `match`）、没有 `do...while`、没有 `++/--`、没有 `const`（只有命名约定）、没有块级作用域（`if` 里定义的变量函数外仍可见）`[B20]`。

## 2. 词法基础（写第一行代码前必须知道）

### 2.1 源文件编码

- Python 3 源码**默认 UTF-8**，不需要写编码声明；PEP 3120 把默认编码定为 UTF-8。`[B15]`
- 只有在用非 UTF-8 编码保存文件（少见）时才需要在**前两行**写 `# -*- coding: gbk -*-`；写了位置不对不生效。`[B4]`
- 源文件里的中文完全合法（字符串、注释都可以）。`[B4]`

### 2.2 缩进就是语法

```python
# 同一代码块缩进量必须一致
if True:
    print("缩进 4 空格")      # 属于 if 的块
print("回到顶层")             # 不属于 if

# 嵌套时逐层增加
if True:
    if True:
        print("两层缩进")
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 冒号 + 缩进 | `if` / `for` / `while` / `def` / `class` / `with` / `try` 后跟 `:`，下一行必须缩进 | `[B4]` |
| 同一块一致 | 同一块的缩进量必须完全相同，多一个空格都不行 | `[B4]` |
| 禁混 tab/空格 | 混用抛 `TabError`；PEP 8 规定每层 4 个空格 | `[B9]` |
| 缩进量自选 | 语法上任意正数都行，但项目必须统一 4 空格 | `[B9]` |
| 空块用 `pass` | 块里至少要有一条语句 | `[B20]` |

> 注意：IDE 里「自动转空格」一定要开；从网页复制的代码常带全角空格或 tab，报 `IndentationError` 时先看空白字符。

### 2.3 行、续行与分隔

```python
# 一行一条语句（推荐）
a = 1
b = 2

# 分号可以一行多条，但 PEP 8 反对
c = 3; d = 4

# 隐式续行：括号没闭合就可以换行（推荐）
total = (
    a
    + b
    + c
)

# 显式续行：行尾反斜杠（少用，容易出错）
total2 = a + \
         b
```

> 注意：反斜杠后**不能有任何字符**（包括空格和注释），否则 `SyntaxError`。优先用括号续行。`[B4]`

### 2.4 注释

```python
# 单行注释：从 # 到本行结束
x = 1  # 行内注释：与代码至少隔两个空格（PEP 8）

# 多行通常连续写多个 #
# 第二行

text = "# 这不是注释，是字符串内容"
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 只有 `#` 注释 | Python **没有** `/* */` 块注释 | `[B4]` |
| 三引号不是注释 | `"""..."""` 是字符串；放在模块/函数/类开头会被当成 docstring，放别处是「无用的字符串对象」 | `[B4]` `[B19]` |
| 注释写「为什么」 | `x = x + 1  # 加一` 是无信息量注释，PEP 8 明确反对 | `[B9]` |
| 别用注释留死代码 | 用版本控制，不用注释 | `[B9]` |

### 2.5 标识符（名字的语法规则）

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 首字符 | 字母、下划线 `_`、或非 ASCII 字母（Unicode） | `[B4]` `[B14]` |
| 后续字符 | 上述字符 + 数字 | `[B4]` |
| 区分大小写 | `Name` 与 `name` 是两个名字 | `[B4]` |
| 不能用关键字 | `if` / `class` / `for` 等是保留字 | `[B4]` |
| 不能用数字开头 | `2x = 1` 是 `SyntaxError` | `[B4]` |
| 不能含 `-` / `.` / 空格 | `user-name` 会被解析成减法 | `[B4]` |

```python
# 合法
user_name = "a"
_name = "b"
名字 = "c"        # 合法（PEP 3131 允许 Unicode），但不建议
π = 3.14159       # 合法

# 非法
# 2x = 1          SyntaxError
# user-name = 1   实际是 user - name（NameError）
# class = 1       SyntaxError（关键字）
```

> 注意：Unicode 标识符合法但可读性差、跨工具兼容性差；PEP 8 建议标识符只用 ASCII。`[B9]` `[B14]`

### 2.6 关键字与软关键字

**硬关键字**（任何地方都不能当名字）：`False` `None` `True` `and` `as` `assert` `async` `await` `break` `class` `continue` `def` `del` `elif` `else` `except` `finally` `for` `from` `global` `if` `import` `in` `is` `lambda` `nonlocal` `not` `or` `pass` `raise` `return` `try` `while` `with` `yield`。`[B4]`

**软关键字**（只在特定语法位置有特殊含义，可以当变量名）：`match` `case` `type`（3.12）。`[B4]` `[B12]`

```python
# 合法：软关键字可以当名字
match = 3
case = 4
print(match + case)   # 7
```

> 注意：虽然合法，但把 `match` / `case` / `type` 当变量名会让读代码的人困惑，不要这么做。`[B9]`

## 3. 数据类型

### 3.1 内置类型总览

| 类型 | 字面量示例 | 可变 | 说明 | 依据 |
| --- | --- | --- | --- | --- |
| `int` | `42`、`-7`、`0xff`、`1_000` | 不可变 | 任意精度整数，不会溢出 | `[B6]` `[B16]` |
| `float` | `1.5`、`1e3`、`.5`、`-2.` | 不可变 | IEEE 754 双精度，有精度误差 | `[B6]` |
| `complex` | `2j`、`1+2j` | 不可变 | 复数，工程/信号处理用 | `[B6]` |
| `bool` | `True`、`False` | 不可变 | `int` 的子类，`True == 1` | `[B6]` |
| `str` | `'a'`、`"b"`、`f'{x}'` | 不可变 | Unicode 字符序列 | `[B1]` `[B6]` |
| `NoneType` | `None` | 不可变 | 唯一的「无值」对象 | `[B6]` |
| `list` / `tuple` / `dict` / `set` | `[1,2]` / `(1,2)` / `{"k":1}` / `{1,2}` | 前三者可变的只有 list/dict | 第 04 章详解 | `[B3]` |

### 3.2 整数 `int`

```python
print(10**30)          # 1000000000000000000000000000000，不溢出
print(1_000_000)       # 1000000，下划线只为可读，不影响值
print(0b1010, 0o17, 0xff)   # 10 15 255，二/八/十六进制
print(17 // 3, 17 % 3)      # 5 2，整除与取余
print(-7 // 2, -7 % 2)      # -4 1，// 向下取整，% 符号跟随除数
print(divmod(-7, 2))        # (-4, 1)，一次拿到商和余数
```

**必须记住的三条**（实测 3.12.8）：

| 表达式 | 结果 | 说明 |
| --- | --- | --- |
| `-7 // 2` | `-4` | 向下取整（floor），不是向零截断 |
| `int(-3.9)` | `-3` | 转 int 才是向零截断 |
| `-7 % 2` | `1` | 余数符号跟随**除数**，所以非负 |
| `7 % -2` | `-1` | 同上，跟随负数除数 |
| `0.1 + 0.2` | `0.30000000000000004` | float 精度问题，见 3.3 |

> 注意：`//` 叫「向下取整除法」而不是「截断除法」，负数上差别会让新手算错分页、取模。`[B6]`

### 3.3 浮点数 `float`

```python
print(1e3, 1.5e-3, .5)       # 1000.0 0.0015 0.5
print(0.1 + 0.2)             # 0.30000000000000004
print(0.1 + 0.2 == 0.3)      # False
print(round(0.1 + 0.2, 10))  # 0.3，四舍五入到 10 位
print(round(2.5), round(3.5))  # 2 4，银行家舍入（.5 取偶）
print(round(2.675, 2))       # 2.67，底层二进制表示导致
```

**浮点比较的正确做法**：

```python
import math   # import 机制在第 21 章；此处只需知道要先用它

print(math.isclose(0.1 + 0.2, 0.3))   # True
print(0.1 + 0.2 > 0.3)                # True，误差方向可能任意
```

| 场景 | 错误写法 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 相等判断 | `a == b` | `math.isclose(a, b)` | `[B17]` |
| 金额计算 | 用 `float` | 用 `decimal.Decimal`（第 22 章） | `[B6]` |
| 显示两位小数 | 直接 `print(x)` | `f"{x:.2f}"` | `[B8]` |

> 注意：`round()` 不是「四舍五入」而是「银行家舍入 + 浮点表示」，做金额务必用 `Decimal`。`[B6]`

### 3.4 复数 `complex`

```python
z = 1 + 2j
print(z.real, z.imag)   # 1.0 2.0
print(abs(3 + 4j))      # 5.0
print(z * z)            # (-3+4j)
```

> 注意：日常业务几乎不用；知道存在、别把 `j` 当成变量名就行。`[B6]`

### 3.5 布尔 `bool`

```python
print(True + True)          # 2（True 就是 1）
print(isinstance(True, int))  # True（bool 是 int 的子类）
print(True == 1, False == 0)  # True True
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 首字母大写 | `true` / `false` 是未定义名字，抛 `NameError` | `[B4]` |
| 是 int 子类 | 所以 `True + True == 2`；不要拿它做算术魔法 | `[B6]` |
| 不要与 `==` 比较 | `if flag == True:` 应写 `if flag:` | `[B9]` |
| `bool(x)` 看真值 | 规则见 3.10 | `[B6]` |

### 3.6 字符串 `str`

**四种写法**：

```python
single = '单引号'
double = "双引号"          # 与单引号完全等价
triple = """可以
跨行，
也能包含 ' 和 " """
raw = r"C:\new\table"      # 原始字符串：反斜杠不转义
```

| 写法 | 用途 | 陷阱 | 依据 |
| --- | --- | --- | --- |
| `'...'` / `"..."` | 普通字符串 | 内部含同种引号要转义 | `[B1]` |
| `'...' "..."` 相邻 | 字面量自动拼接 | **只对字面量生效**，变量不行 | `[B1]` |
| `"""..."""` / `'''...'''` | 多行文本、docstring | 不是注释 | `[B4]` |
| `r"..."` | 正则、Windows 路径 | **不能以奇数个反斜杠结尾** | `[B4]` |
| `f"..."` | 内嵌表达式 | 见第 5 节 | `[B10]` |
| `b"..."` | 字节串 | 元素是 0-255 的 int，不是字符 | `[B4]` |

**常用转义**：`\n` 换行、`\t` 制表、`\\` 反斜杠、`\'` `\"`、`\0`、`\xhh`（两位十六进制）、`\uXXXX`（四位 Unicode）、`\N{名称}`。`[B4]`

**索引与切片**（含起点、不含终点）：

```python
s = "Python"
print(s[0], s[-1])    # P n
print(s[1:4])         # yth
print(s[::-1])        # nohtyP，步长 -1 反转
print(s[:100])        # Python，切片越界被截断，不报错
# s[100]              IndexError，索引越界会报错
```

**常用方法速查**（全部返回新字符串，原串不变）：

```python
t = "  Hello World  "
print(t.strip())                  # "Hello World"
print(t.lower(), t.upper())       # "  hello world  " "  HELLO WORLD  "
print(t.replace("World", "Py"))   # "  Hello Py  "
print("a,b,c".split(","))         # ['a', 'b', 'c']
print("-".join(["a", "b"]))       # "a-b"
print("abc".startswith("ab"))     # True
print("abc".find("c"))            # 2（找不到返回 -1）
print("abc".count("a"))           # 1
print("42".isdigit())             # True（负号会返回 False）
print("abc".isalpha())            # True
print(f"{'x':*^5}")               # **x**，居中填充
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 不可变 | `s[0] = "J"` 抛 `TypeError`，只能构造新串 | `[B1]` |
| `len()` 按字符 | 中文一个字算 1；实测 `len("查一下今天的 AI 新闻")` 为 `12` | `[B6]` |
| 索引按字符 | 不是按字节，UTF-8 字节长度要用 `encode()` | `[B6]` |
| `in` 判子串 | `"th" in s` → `True` | `[B6]` |
| 方法不改变原串 | 忘了接收返回值是常见 bug | `[B6]` |

> 注意：`"abc" * 3` 得 `"abcabcabc"`；`"abc" + 1` 抛 `TypeError`，数字要先 `str()`。`[B1]` `[B6]`

### 3.7 `None`

```python
result = None
print(result is None)      # True，判空用 is
print(bool(None))          # False
print(type(None))          # <class 'NoneType'>
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 只有一个 | `None` 是单例，全程序共享 | `[B19]` |
| 用 `is` 比较 | `x is None` / `x is not None`，不用 `==` | `[B9]` |
| 不是 0、不是空串 | `None == 0` 为 `False`、`None == ""` 为 `False` | `[B6]` |
| 函数无返回值时 | 隐式返回 `None`（第 05 章） | `[B2]` |

### 3.8 可变与不可变

| 类别 | 类型 | 含义 |
| --- | --- | --- |
| 不可变 | `int` `float` `complex` `bool` `str` `tuple` `frozenset` `NoneType` | 内容不能改，「修改」都是产生新对象 |
| 可变 | `list` `dict` `set` `bytearray` | 可以原地增删改，所有引用看到同一份变化 |

```python
a = "abc"
b = a
a = a + "d"      # 生成了新对象，b 仍是 "abc"
print(a, b)      # abcd abc

x = [1, 2]
y = x
y.append(3)      # 原地修改，x 和 y 看到同一份
print(x, y)      # [1, 2, 3] [1, 2, 3]
```

> 注意：可变对象的别名是第 04 章的核心问题；现在只需记住「`=` 不复制对象，只多一个名字」。`[B19]`

### 3.9 `type()` 与 `isinstance()`

```python
print(type(1))                 # <class 'int'>
print(type(1).__name__)        # int
print(type(True) is bool)      # True
print(isinstance(True, int))   # True，bool 是 int 子类
print(isinstance("a", (int, str)))   # True，第二参数可以是元组
```

| 用途 | 推荐 | 理由 | 依据 |
| --- | --- | --- | --- |
| 判断「是不是某类（含子类）」 | `isinstance(x, C)` | 支持继承关系 | `[B7]` |
| 判断「精确类型」 | `type(x) is C` | 不匹配子类 | `[B7]` |
| 取类型名字符串 | `type(x).__name__` | 日志/报错常用 | `[B19]` |

> 注意：`type(x) == C` 能写但不推荐，用 `isinstance`；`type` 本身是软关键字（3.12），可以当变量名但别这么做。`[B7]` `[B4]`

### 3.10 真值测试（哪些值算「假」）

**只有这些是假**：`False`、`None`、数值 `0`（`0` / `0.0` / `0j`）、空序列与空集合（`""` / `[]` / `()` / `{}` / `set()`）、以及定义了 `__bool__` 返回 `False` 或 `__len__` 返回 0 的对象（第 14 章）。

```python
values = [0, 0.0, "", [], {}, set(), None, False, "0", [0], -1]
print([bool(v) for v in values])
# 实测：[False, False, False, False, False, False, False, False, True, True, True]
```

| 写法 | 含义 | 依据 |
| --- | --- | --- |
| `if not seq:` | 序列为空 | `[B9]` |
| `if seq:` | 序列非空 | `[B9]` |
| `if x is None:` | 只判 `None` | `[B9]` |
| `if not x:` | **无法区分** `None`、`0`、`""`、`[]` | `[B6]` |

> 注意：`"0"` 和 `[0]` 都是**真**——非空容器/非空字符串不看内容。需要区分「没给值」和「给了 0」时必须显式 `is None`。`[B6]`

## 4. 变量

### 4.1 变量是「名字到对象的绑定」

```python
count = 3          # 把名字 count 绑定到 int 对象 3
count = "三个"      # 重新绑定到 str 对象，合法
print(count, type(count))   # 三个 <class 'str'>
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 无声明 | 第一次赋值即创建 | `[B1]` |
| 无类型 | 名字不绑定类型，对象才有类型 | `[B19]` |
| 先赋值后用 | 未定义就使用抛 `NameError` | `[B1]` |
| `=` 是绑定 | 不复制对象，只增加一个名字 | `[B19]` |
| 大小写敏感 | `Name` 与 `name` 无关 | `[B4]` |

### 4.2 命名规则（语法层，违反就报错）

```python
# 合法
user_name = 1
userName = 2
_user = 3
name2 = 4

# 非法
# 2name = 1        SyntaxError：数字开头
# user-name = 1    NameError：被解析成 user - name
# class = 1        SyntaxError：关键字
# user name = 1    SyntaxError：空格
```

### 4.3 命名规范（PEP 8，语法层不管但团队要求）

| 对象 | 规范 | 示例 | 依据 |
| --- | --- | --- | --- |
| 变量 | `lowercase_with_underscores` | `tool_call_count` | `[B9]` |
| 常量 | `UPPER_CASE` | `MAX_RETRY = 3` | `[B9]` |
| 类 | `CapWords` | `ToolCall` | `[B9]` |
| 函数/方法 | `lowercase_with_underscores` | `fetch_news()` | `[B9]` |
| 内部使用 | 单下划线前缀 | `_cache` | `[B9]` |
| 避免 | `l` `O` `I` 单字符 | 易与 `1` `0` 混淆 | `[B9]` |
| 避免 | 拼音、`data` `temp` `a1` | 无信息量 | `[B9]` |
| 布尔 | `is_` / `has_` / `can_` 前缀 | `is_valid` | `[B9]` |

### 4.4 多重赋值

```python
a = b = c = 0          # 三个名字指向同一个 0
x, y = 1, 2            # 元组解包
x, y = y, x            # 交换，不借助临时变量
print(a, b, c, x, y)   # 0 0 0 2 1
```

> 注意：`a = b = []` 会让两个名字指向**同一个列表**，改一个另一个也变；要各自独立必须写 `a, b = [], []`。`[B19]`

### 4.5 解包（含 `*` 收集）

```python
first, *rest = [1, 2, 3, 4]
*init, last = [1, 2, 3, 4]
print(first, rest)   # 1 [2, 3, 4]
print(init, last)    # [1, 2, 3] 4

# 嵌套解包
(a, b), c = (1, 2), 3
print(a, b, c)       # 1 2 3

# 右边数量必须匹配（除非用 *）
# p, q = 1, 2, 3     ValueError: too many values to unpack
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 左右数量相等 | 不等抛 `ValueError` | `[B20]` |
| `*` 最多一个 | 收集剩余为 `list` | `[B20]` |
| 可用于任意可迭代 | 字符串、元组、range 都行 | `[B20]` |
| 交换变量 | `a, b = b, a` 是标准写法 | `[B20]` |

### 4.6 类型转换

| 目标 | 写法 | 结果/陷阱 | 依据 |
| --- | --- | --- | --- |
| `int` | `int("42")` | `42`；`int("3.5")` 抛 `ValueError` | `[B7]` |
| `int` | `int(3.9)` / `int(-3.9)` | `3` / `-3`，**向零截断** | `[B7]` |
| `float` | `float("1.5")` / `float("1e3")` | `1.5` / `1000.0` | `[B7]` |
| `str` | `str(3.0)` | `"3.0"`，注意小数位 | `[B7]` |
| `bool` | `bool("False")` | `True`（非空字符串即真） | `[B6]` |
| `list` | `list("ab")` | `['a', 'b']` | `[B7]` |
| `tuple` | `tuple([1, 2])` | `(1, 2)` | `[B7]` |
| `set` | `set([1, 1, 2])` | `{1, 2}` 去重 | `[B7]` |

```python
# 正确：先 float 再 int
print(int(float("3.5")))    # 3

# 出错：直接转带小数点的字符串
try:
    int("3.5")
except ValueError as error:
    print(type(error).__name__)   # ValueError
```

> 注意：`bool("False")` 是 `True`——字符串转布尔只看空不空，不看内容；要解析用户输入的 true/false 必须自己判断。`[B6]`

### 4.7 常量约定、`del` 与类型注解预告

```python
MAX_RETRY = 3      # 常量只是「全大写约定」，Python 不会阻止你改
MAX_RETRY = 4      # 语法合法，靠团队纪律

temp = 1
del temp           # 删除名字绑定；之后再用 temp 抛 NameError

score: int = 0     # 3.6+ 类型注解（第 20 章详解），运行时不校验
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 没有真正常量 | 只有命名约定 | `[B9]` |
| `del` 删名字 | 不直接释放对象，引用计数归零才回收 | `[B20]` |
| 注解不校验 | `x: int = "abc"` 运行时合法，靠静态检查器 | `[B20]` |

> 注意：`del` 后变量再使用是 `NameError`；这也是「先赋值后用」的一个反例来源。`[B20]`

## 5. 字符串格式化

### 5.1 三种方式对比

| 方式 | 写法 | 推荐度 | 依据 |
| --- | --- | --- | --- |
| f-string（3.6+） | `f"{name} 有 {count} 条"` | **首选** | `[B10]` |
| `str.format()` | `"{} 有 {} 条".format(name, count)` | 需要延迟填值时 | `[B6]` |
| `%` 格式化 | `"%s 有 %d 条" % (name, count)` | 只维护旧代码 | `[B6]` |

### 5.2 f-string 完整用法

```python
name = "search"
count = 3
ratio = 0.256

print(f"{name} 调用了 {count} 次")          # search 调用了 3 次
print(f"两倍是 {count * 2}")                # 两倍是 6
print(f"{count=}")                          # count=3，3.8+ 调试语法
print(f"{ratio:.1%}")                       # 25.6%
print(f"{1234567:,}")                       # 1,234,567
print(f"{42:05d}")                          # 00042
print(f"{'x':*^5}")                         # **x**
print(f"{3.14159:.2f}")                     # 3.14
print(f"{'已有值' if count else '空'}")      # 表达式里可以写条件表达式
```

**3.12 放宽的三件事**（PEP 701，本机实测可用）：`[B13]`

```python
data = {"k": "v"}
print(f"{data["k"]}")            # v：表达式里可复用同种引号（3.12 前是语法错误）
print(f"{'\n'.join(['a', 'b'])}")  # 表达式里可写反斜杠
```

> 注意：`f"{count=}"` 输出的是「源码文本=值」，适合调试，不要写进正式 UI 文案。`[B10]`
>
> 注意：`f"{x}"` 不能直接调用会改变外部状态的函数做副作用，表达式保持纯粹。

### 5.3 `str.format()`

```python
print("{} 有 {} 条".format("search", 3))
print("{0} 和 {1}".format("a", "b"))
print("{name} 有 {count} 条".format(name="cache", count=2))
print("{:>8}|".format("hi"))      # "      hi|"
```

> 注意：位置参数和关键字参数不要混着写错顺序；新代码优先 f-string。`[B6]`

### 5.4 `%` 格式化（旧式）

```python
print("%s 有 %d 条" % ("search", 3))
print("%.2f%%" % 25.6)        # 25.60%
print("%05d" % 42)            # 00042
```

> 注意：`%` 只接受一个值或一个元组；单个值时 `%` 后面不能多写元组。新代码不要用。`[B6]`

### 5.5 格式说明符速查（f-string 与 format 通用）

| 说明符 | 含义 | 示例输出 | 依据 |
| --- | --- | --- | --- |
| `.2f` | 保留 2 位小数 | `3.14` | `[B8]` |
| `.0f` | 无小数 | `3` | `[B8]` |
| `d` | 十进制整数 | `42` | `[B8]` |
| `05d` | 补零到 5 位 | `00042` | `[B8]` |
| `,` | 千分位 | `1,234,567` | `[B8]` |
| `%` | 百分比（乘 100 加 %） | `25.0%` | `[B8]` |
| `e` | 科学计数 | `1.23e+03` | `[B8]` |
| `>` `<` `^` | 右/左/居中对齐 | `   42` | `[B8]` |
| `*` `0` `-` | 填充字符 | `**x**` | `[B8]` |
| `b` `o` `x` | 二/八/十六进制 | `1010` | `[B8]` |

### 5.6 选择建议

- 新代码一律 f-string；需要「先写模板、后填值」时才用 `format()`。`[B10]`
- 需要给用户看的数字一律显式指定位数（`.2f` / `:.0%`），不要直接 `print(float)`。`[B8]`
- 日志里不要用 f-string 拼接敏感数据（令牌、密码），见第 01 章安全底线。

## 6. 运算符

### 6.1 算术运算符

| 运算符 | 含义 | 示例 | 结果 | 依据 |
| --- | --- | --- | --- | --- |
| `+` | 加 | `1 + 2` | `3` | `[B1]` |
| `-` | 减 / 取负 | `5 - 2`、`-3` | `3`、`-3` | `[B1]` |
| `*` | 乘 / 重复 | `3 * 4`、`"a" * 3` | `12`、`"aaa"` | `[B1]` |
| `/` | 真除法 | `17 / 3` | `5.666666666666667`（**总是 float**） | `[B1]` |
| `//` | 向下取整除法 | `17 // 3`、`-7 // 2` | `5`、`-4` | `[B6]` |
| `%` | 取余 | `17 % 3`、`-7 % 2` | `2`、`1` | `[B6]` |
| `**` | 幂 | `2 ** 10`、`2 ** -1` | `1024`、`0.5` | `[B1]` |
| `divmod()` | 商与余 | `divmod(17, 3)` | `(5, 2)` | `[B7]` |

> 注意：`**` 优先级高于一元 `-`，`-3 ** 2` 是 `-9`，要 `9` 必须写 `(-3) ** 2`。`[B1]`

### 6.2 比较运算符

| 运算符 | 含义 | 示例 | 结果 |
| --- | --- | --- | --- |
| `==` / `!=` | 值相等 | `1 == 1.0` | `True` |
| `<` `<=` `>` `>=` | 大小 | `"a" < "b"` | `True`（按 Unicode 码点） |
| `in` / `not in` | 成员 | `"th" in "Python"` | `True` |
| `is` / `is not` | 身份（同一对象） | `None is None` | `True` |

> 注意：`==` 比的是「值相等」，`is` 比的是「是不是同一个对象」。`[] == []` 为 `True`，`[] is []` 为 `False`。`[B5]`

### 6.3 链式比较（大纲重点）

```python
x = 5
print(0 < x < 10)          # True
print(1 < 2 > 1.5)         # True
print(1 < 2 == 2)          # True
print(10 < x < 20)         # False
```

**语义**：`a < b < c` 等价于 `a < b and b < c`，但 **`b` 只求值一次**。实测：

```python
calls = []

def echo(value):        # 函数在第 05 章，这里只为证明「只调用一次」
    calls.append(value)
    return value

print(0 < echo(1) < 5)  # True
print(calls)            # [1]，只求值一次
```

| 写法 | 是否推荐 | 理由 |
| --- | --- | --- |
| `0 < x < 10` | 推荐 | 直观、少写一次 `x` |
| `0 < x and x < 10` | 可以 | 老代码常见，语义相同 |
| `x > 0 & x < 10` | **错误** | `&` 是位运算且优先级高于比较，会先算 `0 & x` |
| `0 < x < 10 < 20` | 推荐 | 可以任意链接 |

> 注意：链式比较中间项只求值一次，所以中间项有副作用时行为和 `and` 版本不同——这也说明不要在比较表达式里写副作用。`[B5]`

### 6.4 赋值运算符

| 运算符 | 等价于 | 注意 |
| --- | --- | --- |
| `=` | 绑定 | 不是「相等」 |
| `+=` | `x = x + y` | 对 list 是原地扩展，对 str/int 是新建对象 |
| `-=` `*=` `/=` `//=` `%=` `**=` | 对应算术 | `/=` 结果是 float |
| `&=` `|=` `^=` `>>=` `<<=` | 位运算 | 集合也用 `|=` 做并集 |
| `:=` | 表达式内赋值 | 见 6.5 |

```python
n = 1
n += 1        # 2
n *= 3        # 6
s = "a"
s += "b"      # "ab"，生成新字符串
items = [1]
alias = items
items += [2]
print(alias)  # [1, 2]：+= 对 list 是原地修改，别名可见
```

> 注意：`items = items + [2]` 会新建列表（别名不受影响），`items += [2]` 是原地修改（别名受影响）——这是第 04 章别名问题的前置知识。`[B19]`

### 6.5 海象运算符 `:=`（PEP 572）

**用途**：在表达式内部给名字赋值，避免「先算一遍再判断一遍」。

```python
# 旧写法：算两次或写两行
data = "12345"
if len(data) > 3:
    print(len(data))

# 海象写法：只算一次，结果可复用
if (size := len(data)) > 3:
    print(size)      # 5

# 在 while 中读输入
# while (line := input("> ")) != "quit":
#     print("收到:", line)
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 需要括号 | 多数场景要写成 `(name := expr)`，否则可能被解析成别的意思 | `[B11]` |
| 优先级低 | 比大多数运算符低，别省括号 | `[B11]` |
| 不能当独立语句 | `x := 1` 单独一行是 `SyntaxError`，用 `x = 1` | `[B11]` |
| 不要滥用 | 可读性优先，只在能减少重复求值时用 | `[B11]` `[B9]` |

> 注意：海象不是「赋值语句的替代」，它的价值是「表达式里带一个名字」。为了省一行而把复杂表达式塞进 `if` 是反模式。`[B11]`

### 6.6 逻辑运算符

| 运算符 | 语义 | 返回值 | 依据 |
| --- | --- | --- | --- |
| `and` | 全真为真 | **返回某个操作数**，不强制 bool | `[B5]` |
| `or` | 一真即真 | **返回某个操作数**，不强制 bool | `[B5]` |
| `not` | 取反 | 一定返回 `bool` | `[B5]` |

```python
print(0 or "default")        # default，短路后返回右值
print("" or None or "x")     # x
print(1 and 2)               # 2
print(0 and 2)               # 0，左边为假直接返回左值
print(not 0)                 # True
```

**短路规则**：`and` 左边为假就停，`or` 左边为真就停；右边的表达式**不会执行**。`[B5]`

```python
def boom():            # 第 05 章的函数，这里只用来说明副作用
    raise RuntimeError("不该执行")

print(False and boom())   # False，boom 不会执行
print(True or boom())     # True，boom 不会执行
```

> 注意：`x = a or b` 是「默认值」惯用法，但当 `a` 是 `0` / `""` / `[]` 时也会被替换——这常是 bug 来源，需要区分时用 `a if a is not None else b`。`[B5]`

### 6.7 三元表达式（条件表达式）

```python
status = "通过" if score >= 60 else "不通过"
label = f"{count} 条" if count else "无数据"
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 形式 | `值1 if 条件 else 值2`，**必须有 else** | `[B5]` |
| 惰性 | 只求值被选中的分支 | `[B5]` |
| 不要嵌套多层 | 超过一层改用 `if`/`elif` | `[B9]` |

> 注意：写成 `a if c else b`，不是 `c ? a : b`；漏写 `else` 是 `SyntaxError`。`[B5]`

### 6.8 位运算符

| 运算符 | 含义 | 示例 | 结果 | 依据 |
| --- | --- | --- | --- | --- |
| `&` | 按位与 | `6 & 3` | `2` | `[B5]` |
| `\|` | 按位或 | `6 \| 3` | `7` | `[B5]` |
| `^` | 按位异或 | `6 ^ 3` | `5` | `[B5]` |
| `~` | 按位取反 | `~6` | `-7` | `[B5]` |
| `<<` | 左移 | `1 << 4` | `16` | `[B5]` |
| `>>` | 右移 | `256 >> 4` | `16` | `[B5]` |

> 注意：位运算优先级高于比较，`x & 1 == 0` 实际是 `x & (1 == 0)`；要写 `(x & 1) == 0`。`[B5]`

### 6.9 成员与身份运算符

```python
print("th" in "Python")      # True
print(3 in [1, 2, 3])        # True
print("k" in {"k": 1})       # True，判断键
print(4 not in [1, 2])       # True
print(None is None)          # True
print([] is [])              # False，两个不同的对象
```

| 判断什么 | 用什么 | 示例 | 依据 |
| --- | --- | --- | --- |
| 值是否相等 | `==` | `[1] == [1]` → `True` | `[B5]` |
| 是否同一对象 | `is` | `[1] is [1]` → `False` | `[B5]` |
| 是否为 `None` | `is None` | PEP 8 明确要求 | `[B9]` |
| 是否在容器里 | `in` | dict 判的是键 | `[B3]` |

> 注意：`1 is 1` 在 CPython 里常为 `True`（小整数缓存），但会触发 `SyntaxWarning`，且是实现细节——**数值和字符串一律用 `==`**。`[B5]`

### 6.10 优先级与结合性（从高到低）

| 级别 | 运算符 | 说明 |
| --- | --- | --- |
| 1 | `()` `[]` `{}` `x.attr` `x[i]` `f()` | 括号、索引、属性、调用 |
| 2 | `**` | 幂，**右结合**：`2**3**2` = `2**9` |
| 3 | `+x` `-x` `~x` | 一元运算 |
| 4 | `*` `/` `//` `%` | 乘除类 |
| 5 | `+` `-` | 加减 |
| 6 | `<<` `>>` | 移位 |
| 7 | `&` | 按位与 |
| 8 | `^` | 按位异或 |
| 9 | `\|` | 按位或 |
| 10 | `==` `!=` `<` `<=` `>` `>=` `in` `not in` `is` `is not` | 比较（支持链式） |
| 11 | `not x` | 逻辑非 |
| 12 | `and` | 逻辑与 |
| 13 | `or` | 逻辑或 |
| 14 | `if...else` | 条件表达式 |
| 15 | `:=` | 海象（最低） |

实测校验：`2 + 3 * 4` → `14`；`(2 + 3) * 4` → `20`；`not 1 == 2` → `True`（即 `not (1 == 2)`）；`1 | 2 & 3` → `3`（即 `1 | (2 & 3)`）。`[B5]`

> 注意：记不住优先级就加括号——括号不收费，读错代码代价很高。`[B9]`

### 6.11 运算符常见误区

| 误区 | 现象 | 正确做法 |
| --- | --- | --- |
| `-3 ** 2` 以为是 9 | 得 `-9` | 写 `(-3) ** 2` |
| `x & 1 == 0` | 先算 `1 == 0` | 写 `(x & 1) == 0` |
| `x / 2` 当整除 | 得 float | 用 `x // 2` |
| `x % 2 == 1` 判断奇数 | 负数时失败（`-3 % 2 == 1` 成立，但 `-3 % -2` 不同） | 用 `x % 2 != 0` |
| `a == b == c` 以为比三值 | 实际是链式比较 `a==b and b==c` | 明确意图再加括号 |
| 用 `is` 比数字/字符串 | 结果依赖实现 | 用 `==` |
| `not a == b` 想表达 `a != b` | 语义相同但难读 | 写 `a != b` |

## 7. 输入输出

### 7.1 `print` 完整参数

函数签名（第 05 章会讲参数，这里只记用法）：`print(*objects, sep=' ', end='\n', file=sys.stdout, flush=False)`。`[B7]`

```python
print("a", "b", "c")                    # a b c，默认空格分隔
print("a", "b", "c", sep="-")           # a-b-c
print("a", "b", "c", sep="-", end="!\n")  # a-b-c!
print()                                  # 输出一个空行
print("值:", 3.14159)                    # 值: 3.14159
```

| 参数 | 默认 | 作用 | 依据 |
| --- | --- | --- | --- |
| `*objects` | 无 | 任意多个值，逐个转成 `str` 后输出 | `[B7]` |
| `sep` | `' '` | 值之间的分隔符 | `[B7]` |
| `end` | `'\n'` | 结尾追加的字符串 | `[B7]` |
| `file` | `sys.stdout` | 输出目标（可换成文件/标准错误） | `[B7]` |
| `flush` | `False` | 是否立即刷新缓冲 | `[B7]` |

**多参数 vs 字符串拼接**：

```python
count = 3
print("共", count, "条")      # 推荐：print 自动加空格
print("共 " + str(count) + " 条")   # 能用但要手动转换
print(f"共 {count} 条")       # 最推荐：格式化优先 f-string
```

> 注意：`print` 的每个参数必须是可 `str()` 的对象；`print("共" + count)` 会 `TypeError`。`[B7]`

### 7.2 `input` 输入

```python
name = input("请输入名字: ")      # 提示语写到标准输出，不带换行
print(f"你好，{name}")
print(type(name))                 # <class 'str'>，永远是字符串
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 返回 `str` | 输入 `3` 得到 `"3"`，算术前必须转换 | `[B7]` |
| 提示语是参数 | `input("...")` 的提示写到 stdout，不适合写日志 | `[B7]` |
| EOF 抛 `EOFError` | 管道/重定向读完会抛，交互场景才适合用 | `[B7]` |
| 非交互会挂起 | 在无输入的脚本/CI 里调用会一直等，不要放进自动化脚本 | — |
| 不要用 `eval(input())` | 等价于执行用户输入的任意代码，严重安全问题 | `[B7]` |

### 7.3 输入校验套路

```python
raw = input("请输入次数: ")

if raw.isdigit():          # 只接受非负整数
    count = int(raw)
else:
    count = 0
print(f"次数: {count}")
```

| 输入 | `isdigit()` | 说明 |
| --- | --- | --- |
| `"42"` | `True` | 正常 |
| `"-3"` | `False` | 负号不被接受，需要额外判断 |
| `"3.5"` | `False` | 小数要先 `float()` |
| `""` | `False` | 空输入 |
| `"４２"` | `True` | 全角数字也算 digit，转 `int` 前要留意 |

> 注意：`input()` 拿到的一律是字符串；任何「用户输入直接参与计算」的地方都要校验类型与范围。完整异常处理在第 16 章，本章用 `isdigit()` 做最小防线。`[B7]`

### 7.4 `repr` 与 `str`

```python
text = "a\nb"
print(str(text))    # a 换行 b（给人看）
print(repr(text))   # 'a\nb'（给开发者看，带引号和转义）
print([str(1), repr(1)])
```

| 函数 | 面向 | 特点 | 依据 |
| --- | --- | --- | --- |
| `str(x)` | 用户 | 可读文本，`print` 默认用它 | `[B7]` |
| `repr(x)` | 开发者/调试 | 尽量给出可重建对象的表示 | `[B7]` |

> 注意：调试时用 `repr()` 才能看见换行、空格、引号；`print(x)` 常把问题藏起来。`[B7]`

### 7.5 输出到标准错误与文件（极简）

```python
import sys   # import 机制在第 21 章，此处只记用法

print("警告信息", file=sys.stderr)   # 错误流，不与正常输出混在一起
```

写文件属于第 22 章标准库内容；本章只需知道 `print(..., file=...)` 可以换输出目标。`[B7]`

## 8. 流程控制

### 8.1 `if` / `elif` / `else`

```python
score = 82

if score >= 90:
    level = "A"
elif score >= 60:
    level = "B"
else:
    level = "C"
print(level)      # B
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 冒号不能省 | `if x > 0:` 少了 `:` 是 `SyntaxError` | `[B2]` |
| 条件不必是 bool | 任何对象都按真值判断（见 3.10） | `[B6]` |
| 从上到下短路 | 命中一个分支后其余不再判断 | `[B2]` |
| 没有 `switch` 也能写 | 3.10+ 可用 `match`（见 8.3） | `[B12]` |
| 不要写 `if x == True:` | 写 `if x:` | `[B9]` |

### 8.2 条件写法清单

| 意图 | 推荐写法 | 不要写 | 依据 |
| --- | --- | --- | --- |
| 判空值 | `if x is None:` | `if x == None:` | `[B9]` |
| 判非空序列 | `if seq:` | `if len(seq) > 0:` | `[B9]` |
| 判空序列 | `if not seq:` | `if len(seq) == 0:` | `[B9]` |
| 范围 | `if 0 <= x < 10:` | `if x >= 0 and x < 10:` | `[B5]` |
| 多值之一 | `if x in (1, 2, 3):` | `if x == 1 or x == 2 or x == 3:` | `[B3]` |
| 取反 | `if not flag:` | `if flag == False:` | `[B9]` |

### 8.3 `match` / `case`（3.10+）

```python
command = "search"

match command:
    case "search" | "cache":          # 或模式
        print("读类工具")
    case "translate":
        print("转换类工具")
    case _:                            # 通配，必须最后
        print("未知工具")
```

常见模式：

| 模式 | 写法 | 匹配什么 | 依据 |
| --- | --- | --- | --- |
| 字面量 | `case 0:` | 等于 0 | `[B12]` |
| 或模式 | `case 1 \| 2:` | 等于 1 或 2 | `[B12]` |
| 序列 | `case [x]:` | 单元素序列，绑定 `x` | `[B12]` |
| 映射 | `case {"t": token}:` | 含键 `t` 的字典 | `[B12]` |
| 类 | `case str() as text:` | 是 `str` 实例并绑定名字 | `[B12]` |
| 守卫 | `case str() as t if t.startswith("a"):` | 模式 + 额外条件 | `[B12]` |
| 通配 | `case _:` | 任意，必须最后 | `[B12]` |

实测（3.12.8）：

```python
def describe(value):          # 函数在第 05 章，这里只为集中演示
    match value:
        case 0:
            return "zero"
        case [item]:
            return f"one:{item}"
        case {"t": token}:
            return f"dict:{token}"
        case str() as text if text.startswith("a"):
            return "str-a"
        case _:
            return "other"

print([describe(v) for v in [0, [7], {"t": 9}, "abc", 3.5]])
# ['zero', 'one:7', 'dict:9', 'str-a', 'other']
```

> 注意：`match` 是**软关键字**，不影响你继续用 `match` 当变量名；但 `case _` 必须在最后，否则后面的分支永远不执行。`[B12]`
>
> 注意：`match` 不是「C 的 switch」，它做的是结构匹配 + 绑定名字，能力更强也更容易写复杂。日常多分支仍优先 `if/elif`。

### 8.4 `pass` 占位符

```python
if True:
    pass          # 语法占位：什么都不做

for i in range(3):
    pass          # 先占住循环体，避免 IndentationError
```

| 用途 | 说明 | 依据 |
| --- | --- | --- |
| 空块占位 | 块里至少要有一条语句，`pass` 就是那条 | `[B20]` |
| 临时骨架 | 先写结构、后填逻辑 | `[B2]` |
| 不是 `continue` | `pass` 继续执行本块后续语句，`continue` 跳到下一轮 | `[B2]` |

> 注意：`if x: pass` 后立刻写业务逻辑，等于什么都没判断就往下走——这是逻辑 bug 的常见伪装。`[B2]`

### 8.5 `while` 循环

```python
remaining = 3
while remaining > 0:
    print("剩余:", remaining)
    remaining -= 1
print("结束")
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 条件为真才进 | 先判断后执行，可能一次都不进 | `[B2]` |
| 必须有退出路径 | 循环变量不更新就是死循环 | `[B2]` |
| 标准写法 | `while True:` + 内部 `break`，适合「先做再判」 | `[B2]` |
| 没有 `do...while` | 用 `while True` + 末尾 `break` 模拟 | `[B2]` |

### 8.6 `for` 与 `range`

```python
for char in "abc":          # 遍历可迭代对象
    print(char)

for i in range(5):          # 0 1 2 3 4，不含 5
    print(i)

for i in range(1, 10, 3):   # 1 4 7，起点、终点（不含）、步长
    print(i)

for i in range(5, 0, -2):   # 5 3 1，负步长
    print(i)
```

| 形式 | 结果 | 依据 |
| --- | --- | --- |
| `range(5)` | `0..4` | `[B2]` |
| `range(2, 5)` | `2..4` | `[B2]` |
| `range(0, 10, 2)` | `0 2 4 6 8`，长度 5 | `[B2]` |
| `range(0)` | 空，循环一次都不执行 | `[B2]` |
| `range(1, 5, 0)` | `ValueError: range() arg 3 must not be zero` | `[B7]` |

> 注意：`for` 遍历的是**可迭代对象**，不是「下标」；`range` 返回的是惰性序列，不会真的构造列表，所以 `range(10**9)` 不占内存。`[B2]`

### 8.7 `enumerate` / `zip` / `sorted` / `reversed`

```python
tools = ["search", "cache", "translate"]

for index, name in enumerate(tools):        # 默认从 0 开始
    print(index, name)

for index, name in enumerate(tools, start=1):   # 从 1 开始
    print(index, name)

for name, cost in zip(tools, [1.2, 0.5]):   # 按位置配对，长度以短的为准
    print(name, cost)

print(sorted([3, 1, 2]))                    # [1, 2, 3]，返回新列表
print(sorted(tools, reverse=True))          # ['translate', 'search', 'cache']
print(list(reversed([1, 2, 3])))            # [3, 2, 1]
```

| 函数 | 返回 | 用途 | 依据 |
| --- | --- | --- | --- |
| `enumerate(it, start=0)` | `(下标, 元素)` | 既要索引又要值 | `[B7]` |
| `zip(*its)` | `(a, b, ...)` | 并行遍历多个序列 | `[B7]` |
| `zip(..., strict=True)` | 长度不等抛 `ValueError` | 3.10+ 防止静默截断 | `[B18]` |
| `sorted(it)` | 新 `list` | 排序，不改原对象 | `[B3]` |
| `reversed(seq)` | 迭代器 | 反序，不复制 | `[B3]` |

实测 `zip([1, 2, 3], "ab")` → `[(1, 'a'), (2, 'b')]`；加 `strict=True` 抛 `ValueError`。`[B18]`

> 注意：`zip` 默认按最短截断且**不报错**，长度不等时容易静默丢数据；关键路径加 `strict=True`。`[B18]`

### 8.8 `break` 与 `continue`

```python
for attempt in range(1, 5):
    if attempt == 2:
        continue          # 跳过本轮剩余，进入下一轮
    if attempt == 4:
        break             # 直接结束整个循环
    print("处理:", attempt)
```

| 语句 | 作用 | 边界 | 依据 |
| --- | --- | --- | --- |
| `break` | 立即退出**最内层**循环 | 只跳一层 | `[B2]` |
| `continue` | 跳过本轮剩余语句 | 仍会执行下一轮 | `[B2]` |
| `return` | 退出函数（第 05 章） | 不是循环语句 | `[B2]` |

> 注意：`break` 只跳出最内层循环；两层都要跳出时用标志变量或把内层抽成函数（第 05 章）。`[B2]`

### 8.9 循环 `else` 子句

**语义**：循环**正常跑完**才执行 `else`；被 `break` 打断则不执行。`[B2]`

```python
for i in range(3):
    if i == 5:
        break
else:
    print("没有触发 break")      # 会执行

i = 0
while i < 3:
    i += 1
else:
    print("while 正常结束:", i)  # 会执行，输出 3
```

| 场景 | `else` 是否执行 | 依据 |
| --- | --- | --- |
| 循环跑完所有轮次 | 执行 | `[B2]` |
| 中途 `break` | 不执行 | `[B2]` |
| 循环体一次都没进 | 执行（没有 break） | `[B2]` |
| 循环里抛异常 | 不执行 | `[B2]` |

> 注意：`else` 属于 `for` / `while`，不是 `if` 的 `else`；它常被误读成「否则」。更清楚的替代写法是设一个 `found` 标志，团队可读性优先。`[B2]` `[B9]`

### 8.10 嵌套循环

```python
for row in range(2):
    for col in range(3):
        print(f"({row},{col})", end=" ")
    print()
# (0,0) (0,1) (0,2)
# (1,0) (1,1) (1,2)
```

**内层需要提前结束整个双层循环时**（不引入函数的标准做法）：

```python
found = False
for row in range(3):
    for col in range(3):
        if row * col == 4:
            found = True
            break
    if found:
        break
print(found)     # True
```

> 注意：嵌套层数超过 2 层基本说明该拆函数了；本章不写函数，但要知道这是「结构信号」。`[B9]`

### 8.11 循环与条件的高频陷阱

| 陷阱 | 现象 | 正确做法 | 依据 |
| --- | --- | --- | --- |
| 遍历时增删列表 | 漏项或死循环 | 遍历副本 `for x in lst[:]`，或构建新列表 | `[B2]` |
| `while` 忘更新变量 | 死循环 | 每轮必须让条件趋近假 | `[B2]` |
| `range(5)` 以为含 5 | 少一轮 | 要 1..5 写 `range(1, 6)` | `[B2]` |
| 浮点做循环条件 | 可能多跑或少跑一轮 | 用整数计数，浮点用 `isclose` 判断 | `[B17]` |
| `break` 以为跳两层 | 只跳内层 | 用标志变量 | `[B2]` |
| 循环 `else` 以为「否则」 | 逻辑反了 | 记「没 break 才执行」 | `[B2]` |
| 在循环里拼字符串 | 大量临时对象，慢 | 收集到列表再 `join` | `[B6]` |
| 循环里 `print` 调试后忘删 | 生产环境刷屏 | 调试输出用完即删 | `[B9]` |

## 9. 综合示例：Agent 用量统计

只用本章语法（无函数、无类、无 `import`），可直接运行。

```python
"""第 03 章综合示例：Tool 调用用量统计。"""

records = [
    ("search", 1.2),
    ("cache", 0.1),
    ("translate", 3.5),
    ("search", 0.8),
]

total = 0.0
slowest_name = ""
slowest_cost = 0.0
count_search = 0

for name, cost in records:          # 元组解包
    total += cost                   # 增强赋值
    if cost > slowest_cost:         # 条件判断
        slowest_name, slowest_cost = name, cost   # 多重赋值
    if name == "search":
        count_search += 1

print(f"调用次数: {len(records)}")
print(f"总耗时: {total:.2f} 秒")
print(f"平均耗时: {total / len(records):.2f} 秒")
print(f"最慢工具: {slowest_name} ({slowest_cost:.1f} 秒)")
print(f"search 占比: {count_search / len(records):.0%}")
```

运行（先切到本章目录）：

```powershell
cd 'E:\ai-agent-study\py-base\00-入门与环境\03-python基本语法'
python examples\basics_demo.py     # 章节原示例
```

把上面代码存成 `.py` 后运行，本机实测输出：

```text
调用次数: 4
总耗时: 5.60 秒
平均耗时: 1.40 秒
最慢工具: translate (3.5 秒)
search 占比: 50%
```

**逐段说明**：

| 代码 | 用到的语法点 | 依据 |
| --- | --- | --- |
| `for name, cost in records:` | 元组解包 + `for` 遍历 | `[B20]` |
| `total += cost` | 增强赋值 | `[B20]` |
| `if cost > slowest_cost:` | 比较运算符 + 缩进块 | `[B1]` |
| `slowest_name, slowest_cost = name, cost` | 多重赋值 | `[B20]` |
| `f"{total:.2f}"` | f-string + 格式说明符 | `[B10]` `[B8]` |
| `:.0%` | 百分比格式 | `[B8]` |

> 注意：`total` 是 float 累加，展示用 `.2f` 已经掩盖了精度误差；如果这是计费场景，必须换 `Decimal`，不能靠格式化补救。`[B6]`

## 10. 注意事项与新手错误对照表

| 错误写法 / 操作 | 报错或现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 块内不缩进 | `IndentationError` | 冒号下一行缩进 4 空格 | `[B4]` |
| tab 与空格混用 | `TabError` | 全项目统一 4 空格 | `[B9]` |
| 用了全角 `（ ）` `：` | `SyntaxError` 或行为异常 | 切成半角符号 | `[B4]` |
| `if x = 1:` | `SyntaxError` | `if x == 1:` | `[B5]` |
| `print "x"` | `SyntaxError` | `print("x")` | `[B7]` |
| 使用未定义名字 | `NameError` | 先赋值再用 | `[B1]` |
| `class = 1` | `SyntaxError` | 换名字，避开关键字 | `[B4]` |
| `2x = 1` | `SyntaxError` | `x2 = 1` | `[B4]` |
| `"1" + 1` | `TypeError` | `int("1") + 1` 或 f-string | `[B6]` |
| `int("3.5")` | `ValueError` | `int(float("3.5"))` | `[B7]` |
| `1 / 0` | `ZeroDivisionError` | 先判 0 再除 | `[B6]` |
| `s[0] = "J"` | `TypeError` | 构造新串：`"J" + s[1:]` | `[B1]` |
| `lst[10]` | `IndexError` | 先判长度 | `[B1]` |
| `d["missing"]` | `KeyError` | `d.get("missing")` | `[B3]` |
| `p, q = 1, 2, 3` | `ValueError` | 数量对齐或用 `*rest` | `[B20]` |
| `0.1 + 0.2 == 0.3` | `False` | `math.isclose(...)` | `[B17]` |
| `range(5)` 取到 5 | 少一轮/多一轮 | `range(1, 6)` | `[B2]` |
| `while` 条件不更新 | 死循环 | 每轮更新循环变量 | `[B2]` |
| `input()` 结果直接相加 | `TypeError` | `int(input(...))` 并校验 | `[B7]` |
| `bool("False")` 以为假 | 得 `True` | 自己判断字符串内容 | `[B6]` |
| `x is 1` | `SyntaxWarning`，结果不可靠 | `x == 1` | `[B5]` |
| 遍历列表时 `append` | 死循环或漏项 | 遍历副本或新建列表 | `[B2]` |
| `x =+ 1` 想自增 | 实际是 `x = +1` | `x += 1` | `[B20]` |
| `r"c:\"` | `SyntaxError` | `r"c:\\"` 或 `"c:\\"` | `[B4]` |
| 用三引号当注释 | 不是注释，产生字符串对象 | 用 `#` | `[B4]` |
| `a = b = []` | 两个名字共享同一列表 | `a, b = [], []` | `[B19]` |
| `round(2.5)` 以为 3 | 得 `2` | 需要四舍五入用 `Decimal` | `[B6]` |
| `-7 // 2` 以为 `-3` | 得 `-4` | 记住向下取整 | `[B6]` |
| `"abc"[1:2]` 以为取 2 个字符 | 得 `"b"` | 切片不含终点，写 `[1:3]` | `[B1]` |
| `not x is None` | 能跑但难读 | `x is not None` | `[B9]` |
| 只写 `if` 不写 `else` 的三元 | `SyntaxError` | `a if c else b` | `[B5]` |
| 用 `%` 拼日志里的敏感值 | 泄露风险 | 脱敏后再输出 | 第 01 章安全底线 |

## 11. 最佳实践与编码建议

**PEP 8 必记（新手版）** `[B9]`：

| 项 | 要求 |
| --- | --- |
| 缩进 | 每层 4 个空格，禁用 tab |
| 行宽 | 79 字符（团队可放宽，但要统一） |
| 空行 | 顶层定义之间 2 行，类内方法之间 1 行 |
| 空格 | 运算符两侧各一个；逗号后一个；`=` 在关键字参数里不带空格 |
| 复合语句 | 不写 `if x: y = 1` 这种一行流 |
| 导入 | 每个 `import` 单独一行，放文件顶部（第 21 章） |
| 命名 | 变量/函数 `snake_case`，常量 `UPPER_CASE`，类 `CapWords` |
| 比较 | `is None` / `is not None`，布尔不写 `== True` |
| 注释 | 解释「为什么」，行内注释与代码隔两个空格 |

**写法建议**：

- **数字一律显式格式化**：`f"{x:.2f}"`，别让 `0.30000000000000004` 出现在界面上。`[B8]`
- **判断优先用真值与 `in`**：`if seq:`、`if x in (1, 2, 3):`，比 `len()` 和长串 `or` 清楚。`[B9]`
- **魔法数字要命名**：`MAX_RETRY = 3`，不要散落 `3`。`[B9]`
- **输入校验前置**：`input()` 之后立刻校验，不要带着字符串往下算。`[B7]`
- **一条语句只做一件事**：`x = a if c else b` 可以，嵌套三元不行。`[B5]`
- **循环里少做字符串拼接**：收集到列表再 `"-".join(...)`。`[B6]`
- **调试用 `repr()`**：能看见空白字符与换行。`[B7]`
- **生产代码不用 `print` 当日志**：日志与可观测性在第 32 章。`[B7]`
- **绝不用 `eval(input())`**：等于把执行权交给用户。`[B7]`
- **行为要可预测**：不确定的表达式先在 REPL 验证，再写进代码。`[B1]`

## 12. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[B1]` | python.org | https://docs.python.org/3.12/tutorial/introduction.html | 数字与 `/` `//` `%` `**`、字符串引号/转义/raw/索引/切片/不可变/相邻字面量拼接、变量赋值与 `NameError`、`print()` |
| `[B2]` | python.org | https://docs.python.org/3.12/tutorial/controlflow.html | `if`/`elif`/`else`、`for`、`range()`、`break`/`continue`、循环 `else`、`pass`、`match`、遍历时修改集合的风险 |
| `[B3]` | python.org | https://docs.python.org/3.12/tutorial/datastructures.html | `list` 方法、`del`、`tuple`、`set`、`dict`、`enumerate()`/`zip()`/`reversed()`/`sorted()`、`in` 判键、比较 |
| `[B4]` | python.org | https://docs.python.org/3.12/reference/lexical_analysis.html | 编码声明、行与续行、缩进、注释、标识符、关键字与软关键字、数字/字符串/字节字面量、f-string |
| `[B5]` | python.org | https://docs.python.org/3.12/reference/expressions.html | 运算符优先级与结合性、算术转换、比较与链式比较、布尔短路、条件表达式、海象、解包 |
| `[B6]` | python.org | https://docs.python.org/3.12/library/stdtypes.html | 真值测试、`int`/`float`/`bool` 语义、`str` 方法与不可变、`str.format`、`//` 与 `%` 规则 |
| `[B7]` | python.org | https://docs.python.org/3.12/library/functions.html | `print`/`input`/`len`/`range`/`enumerate`/`zip`/`int`/`float`/`str`/`bool`/`round`/`abs`/`sum`/`max`/`min`/`pow`/`divmod`/`sorted`/`reversed`/`type`/`isinstance`/`repr` |
| `[B8]` | python.org | https://docs.python.org/3.12/library/string.html | 格式说明符语法（`.2f`、`%`、`,`、`>`/`<`/`^`、填充、进制） |
| `[B9]` | PEP 官方 | https://peps.python.org/pep-0008/ | 4 空格、禁混 tab、79 字符、命名约定、`is None`、布尔不与 `==` 比较、注释规范 |
| `[B10]` | PEP 官方 | https://peps.python.org/pep-0498/ | f-string 语法、内嵌表达式、`=` 调试语法（3.8+） |
| `[B11]` | PEP 官方 | https://peps.python.org/pep-0572/ | 海象运算符的语法限制、括号要求、可读性建议 |
| `[B12]` | PEP 官方 | https://peps.python.org/pep-0634/ | `match`/`case` 语句、字面量/序列/映射/类模式、守卫、通配 |
| `[B13]` | PEP 官方 | https://peps.python.org/pep-0701/ | 3.12 f-string 放宽：复用引号、反斜杠、多行表达式、注释 |
| `[B14]` | PEP 官方 | https://peps.python.org/pep-3131/ | 标识符支持 Unicode |
| `[B15]` | PEP 官方 | https://peps.python.org/pep-3120/ | 源码默认编码 UTF-8 |
| `[B16]` | PEP 官方 | https://peps.python.org/pep-0515/ | 数字字面量下划线分隔 |
| `[B17]` | python.org | https://docs.python.org/3.12/library/math.html#math.isclose | 浮点近似比较 |
| `[B18]` | PEP 官方 | https://peps.python.org/pep-0618/ | `zip(strict=True)` 长度校验（3.10+） |
| `[B19]` | python.org | https://docs.python.org/3.12/reference/datamodel.html | 对象 / 类型 / 身份、可变与不可变、`None` 单例、名字绑定语义 |
| `[B20]` | python.org | https://docs.python.org/3.12/reference/simple_stmts.html | 赋值与增强赋值、解包、注解赋值、`del`、`pass`、`break`/`continue` |
| `[B21]` | PEP 官方 | https://peps.python.org/pep-0020/ | The Zen of Python（可读性、显式优于隐式） |
| `[B22]` | GitHub 官方 | https://github.com/python/cpython/blob/main/Doc/tutorial/introduction.rst | 官方教程源文件（`[B1]` 页脚 Show Source 指向） |

> **核对状态**：`[B1]` `[B2]` `[B9]` `[B22]` 与本章 `README.md` 已核对来源一致；其余链接按 `docs.python.org/3.12` 与 `peps.python.org` 的官方结构整理，**本次未逐页直连复核**。文中所有「实测」输出均为本机 Python 3.12.8 实际运行结果。若链接失效，请从 `https://docs.python.org/3.12/` 站点导航进入同名页面。

## 13. 毕业自查清单

**能说清（概念层）**：

- [ ] Python 的「动态类型」和「强类型」分别指什么，为什么 `"1" + 1` 会报错
- [ ] 为什么说缩进是语法而不是风格，混用 tab/空格会怎样
- [ ] 硬关键字与软关键字的区别，`match` 为什么能当变量名
- [ ] 可变与不可变的区别，`=` 为什么不复制对象
- [ ] `==` 与 `is` 的区别，什么时候必须用 `is`
- [ ] `and` / `or` 返回的为什么不是 `bool`
- [ ] 哪些值在条件判断里是假
- [ ] `//` 与 `/`、`//` 与 `int()` 在负数上的差别
- [ ] 为什么 `0.1 + 0.2 != 0.3`，正确比较方式是什么
- [ ] 链式比较与 `and` 写法语义相同，但差在哪

**能写出（代码层）**：

- [ ] 一个带 `if` / `elif` / `else` 的分支判断
- [ ] 一个 `for` + `range` 的计数循环和一个 `while` 循环
- [ ] 用 `enumerate` 同时取下标与值，用 `zip` 并行遍历
- [ ] 用 `break` / `continue` 控制循环，并说清循环 `else` 何时执行
- [ ] 一个 `match` / `case` 的简单分支（含 `case _`）
- [ ] 用 f-string 输出保留两位小数、千分位、百分比
- [ ] 用 `input()` 读入并转成数字，带最小校验
- [ ] 用 `int()` / `float()` / `str()` / `bool()` 正确转换并知道各自的坑
- [ ] 用多重赋值交换两个变量、用 `*rest` 解包
- [ ] 用海象运算符消除重复求值

**能判断（避坑层）**：

- [ ] 看到 `IndentationError` 知道先查空白字符
- [ ] 看到 `NameError` / `TypeError` / `ValueError` / `IndexError` / `KeyError` 知道分别对应什么错误
- [ ] 看到 `while` 循环能判断会不会死循环
- [ ] 看到遍历中增删元素的代码能指出风险并给出改法
- [ ] 看到 `x =+ 1`、`r"c:\"`、三引号当注释能立刻指出问题
- [ ] 能解释 `a = b = []` 的别名问题
- [ ] 能判断一段代码是否符合 PEP 8 的基本要求

**能跑通（验收层）**：

- [ ] 运行 `examples/basics_demo.py` 并解释每一行输出
- [ ] 把第 9 节综合示例存成文件运行，输出与文档一致
- [ ] 在 REPL 里逐条验证本文的「实测」结论
- [ ] 不看文档，手写一个「读入 5 个数 → 统计最大/最小/平均 → 格式化输出」的脚本

## 14. 下一章衔接

第 04 章 `容器类型`：本章的 `for` 已经能遍历序列，但「被遍历的东西」还没讲透。下一章补齐 `list` / `tuple` / `dict` / `set` 的取舍、可变性与可哈希、别名与浅拷贝、推导式——第 3.8 节和第 4.4 节埋下的「`=` 不复制对象」会在那里变成完整规则，第 8.11 节的「遍历时修改集合」也会在那里给出标准解法。

本章刻意没展开的：函数（05）、作用域（06）、`lambda`（07）、类（08）、异常处理（16）、迭代器与生成器（17）。它们都建立在「变量是名字绑定」「对象有类型」这两条之上，而这两条本章已经讲完。
