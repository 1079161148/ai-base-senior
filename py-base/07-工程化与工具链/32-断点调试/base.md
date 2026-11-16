# 32 断点调试 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把课件里的「调试组件、调试原理（`sys.settrace`）、单文件调试（`launch.json`）、工程调试（`debugpy` + `attach`）」逐条展开，并补上课件没写但实战必须知道的：`breakpoint()` 的钩子机制、`PYTHONBREAKPOINT` 的三种取值、pdb 命令全表、条件断点、post-mortem、多线程/异步调试、`faulthandler` 与 `trace`，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 / Windows 实测） |
| 前置 | 第 16、22、27–28 章（异常、标准库、并发） |
| 覆盖范围 | 调试链路四层组件、`sys.settrace` 事件模型、`breakpoint()`/`PYTHONBREAKPOINT`、pdb 命令、条件断点、post-mortem、`launch.json` 逐字段、`debugpy` attach、日志与 `faulthandler` |
| 明确不覆盖 | DAP 协议完整实现、远程调试的鉴权体系、性能剖析（profiler） |
| 学完验收 | 能解释断点为什么不改字节码、能脚本化跑 pdb、能配出可用的 `launch.json` 与 attach（见第 10 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Dn]` `` 指向第 9 节官方链接；标「实测」的是本机 Python 3.12.8 / Windows 运行结果。本章所有 pdb 交互都是**子进程喂命令**完成的，不需要人工敲键盘。

**推荐顺序**：

```text
1 调试组件（第 1 节）      → 四层链路
2 调试原理（第 2 节）      → settrace 事件模型（重点）
3 单文件调试（第 3 节）    → breakpoint + pdb 命令
4 工程调试（第 4 节）      → launch.json + debugpy attach
5 其他手段（第 5 节）      → 日志/trace/faulthandler
6 综合示例（第 6 节）
7 注意事项（第 7 节）      → 41 条错误对照
```

**与 README 的分工**：README 给结论与边界，本文件负责机制、命令与实测证据。冲突时以本文件为准。

## 1. 调试组件

### 1.1 四层链路

```text
┌──────────────┐   DAP (JSON)   ┌──────────────┐   sys.settrace   ┌──────────────┐
│ 编辑器/IDE    │ ⇄   socket   ⇄ │ 调试适配器    │ ⇄              ⇄ │ 被调试进程     │
│ VSCode       │               │ debugpy      │                  │ CPython      │
└──────────────┘               └──────────────┘                  └──────────────┘
```

| 组件 | 职责 | 依据 |
| --- | --- | --- |
| **UI（编辑器）** | 展示源码、断点红点、变量面板、调用栈 | `[D7]` |
| **协议（DAP）** | 编辑器与适配器之间的标准消息格式 | `[D11]` |
| **适配器（debugpy）** | 把 DAP 请求翻译成 `settrace`/断点操作 | `[D6]` |
| **运行时（CPython）** | 提供 `sys.settrace`、帧对象、`breakpoint()` 钩子 | `[D3]` `[D2]` |

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 断点不是「改字节码」 | 而是适配器在 `settrace` 回调里判断行号 | `[D3]` |
| 变量面板来自帧对象 | `frame.f_locals` | `[D5]` |
| 调用栈来自 `f_back` 链 | 逐层回溯 | `[D5]` |
| 所以「调试器能看到什么」= 帧里有什么 | 优化/内联会影响可见性 | `[D3]` |

> 注意：断点**不改代码**。你在 VSCode 里点的红点只存在于调试器状态里（`bdb.Breakpoint` 对象），进程重启即消失。这也是为什么「调试时能停，直接跑就跳过」——没有调试器就没有 `settrace`。`[D3]` `[D4]`

### 1.2 两种工作模式

| 模式 | 请求类型 | 谁启动进程 | 依据 |
| --- | --- | --- | --- |
| **launch** | `"request": "launch"` | 调试器负责启动 | `[D7]` |
| **attach** | `"request": "attach"` | 进程已在跑，调试器连上去 | `[D7]` |

| 场景 | 用哪种 | 依据 |
| --- | --- | --- |
| 当前文件调试 | launch + `${file}` | `[D7]` |
| 复杂启动命令（`uv run --package`） | attach（先起 debugpy 监听） | 课件 4.1 |
| 容器/远程 | attach + 端口映射 | `[D6]` |
| 已崩溃想查现场 | post-mortem（`pdb.pm()`） | `[D1]` |

## 2. 调试原理

### 2.1 课件原始演示

待调试的文件：

```python
# demo.py
def main():
    a = 1
    b = 2
    c = a + b
    return c


r = main()
print(r)
```

课件给的「调试适配器核心逻辑」：

```python
# debugpy
import os
import sys

current_dir = os.path.dirname(os.path.abspath(__file__))
file_path = os.path.join(current_dir, "demo.py")
code = open(file_path, "r").read()


def my_tracer(frame, event, arg):
    print(f"事件: {event}, 行号: {frame.f_lineno}")
    return my_tracer


sys.settrace(my_tracer)
exec(code)
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| `sys.settrace(fn)` | 注册全局跟踪函数 | `[D3]` |
| 返回自身 | 否则后续行事件不再上报 | `[D3]` |
| `event` | `call` / `line` / `return` / `exception` / `opcode` | `[D3]` |
| `frame.f_lineno` | 当前行号 | `[D5]` |

### 2.2 实测：事件序列

```python
events = []


def tracer(frame, event, arg):
    if frame.f_code.co_name == "main" and event in ("call", "line", "return"):
        events.append((event, frame.f_lineno))
    return tracer


sys.settrace(tracer)
try:
    exec(compile(TARGET, "demo.py", "exec"), {"__name__": "__main__"})
finally:
    sys.settrace(None)
```

```text
TRACE_EVENTS [('call', 1), ('line', 2), ('line', 3), ('line', 4), ('line', 5), ('return', 5)]
```

| 事件 | 行号 | 含义 | 依据 |
| --- | --- | --- | --- |
| `call` | 1 | 进入 `main` 帧（函数定义行） | `[D3]` |
| `line` | 2 | 即将执行 `a = 1` | `[D3]` |
| `line` | 3 | 即将执行 `b = 2` | `[D3]` |
| `line` | 4 | 即将执行 `c = a + b` | `[D3]` |
| `line` | 5 | 即将执行 `return c` | `[D3]` |
| `return` | 5 | 函数返回 | `[D3]` |

| 观察 | 说明 | 依据 |
| --- | --- | --- |
| 没有空行/注释的行事件 | 只有可执行字节码才触发 | `[D3]` |
| `line` 事件在**执行前** | 所以此时变量还没赋值 | `[D3]` |
| `return` 的 `arg` 是返回值 | 课件里只打印了 event | `[D3]` |

> 注意：「`line` 事件在语句执行前」这一点决定了断点语义——停在某行时，该行**还没执行**。所以「停在 `c = a + b` 时 `p c` 会 `NameError`」，必须 `n` 一步之后 `c` 才有值。这是新手最常困惑的地方。`[D3]`

### 2.3 帧对象：调试器能看到的全部信息

```python
def inner():
    frame = inspect.currentframe()
    return frame.f_code.co_name, frame.f_lineno, frame.f_back.f_code.co_name


print("FRAME", inner())
```

```text
FRAME ('inner', 101, '<module>')
```

| 属性 | 含义 | 依据 |
| --- | --- | --- |
| `f_code.co_name` | 函数名 | `[D5]` |
| `f_code.co_filename` | 文件路径 | `[D5]` |
| `f_lineno` | 当前行号 | `[D5]` |
| `f_locals` | 局部变量字典 | `[D5]` |
| `f_globals` | 全局变量字典 | `[D5]` |
| `f_back` | 上一层帧（调用者） | `[D5]` |
| `f_lasti` | 当前字节码偏移 | `[D5]` |

**多层调用栈实测**（`level_one → level_two → level_three`）：

```text
TB_CHAIN ['<module>:11', 'level_one:8', 'level_two:5', 'level_three:2']
```

| 层 | 函数:行号 | 依据 |
| --- | --- | --- |
| 4 | `<module>:11` | `[D5]` |
| 3 | `level_one:8` | `[D5]` |
| 2 | `level_two:5` | `[D5]` |
| 1 | `level_three:2` | `[D5]` |

这就是 VSCode「调用栈」面板里的四行，也是 pdb `w` 命令的输出。

### 2.4 断点是怎么实现的

```text
用户点红点 → 适配器记录 (文件, 行号)
          → settrace 回调里比较 frame.f_lineno == 目标行号
          → 命中则暂停，等待命令
```

| 步骤 | 实现 | 依据 |
| --- | --- | --- |
| 记录断点 | `bdb.Bdb.set_break(filename, lineno)` | `[D4]` |
| 每行检查 | `Bdb.trace_dispatch` 比较行号 | `[D4]` |
| 命中暂停 | 进入交互循环（`cmdloop`） | `[D4]` |
| 继续 | `c` 清空「命中一次」状态 | `[D4]` |

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 标准库 `bdb` 就是这套逻辑 | `pdb` 是 `bdb` 的子类 | `[D4]` |
| 条件断点是「命中后再判表达式」 | 不满足则自动继续 | `[D4]` |
| 断点数过多会明显变慢 | 每行都要比较 | `[D3]` |

### 2.5 开销实测

```python
def cpu_work(rounds=200000):
    total = 0
    for index in range(rounds):
        total += index
    return total


# 不开 trace
start = time.perf_counter(); cpu_work(); plain = ...
# 开 trace（只返回 tracer，不做任何事）
sys.settrace(line_tracer); cpu_work(); sys.settrace(None); traced = ...
```

```text
TRACE_OVERHEAD_MS 4 25
```

| 指标 | 值 | 倍数 |
| --- | --- | --- |
| 无 trace | 4ms | 1× |
| 有 trace（空回调） | 25ms | ≈ 6× |

| 结论 | 说明 | 依据 |
| --- | --- | --- |
| `settrace` 开销显著 | 每行一次 Python 函数调用 | `[D3]` |
| 回调里越少做事越好 | `print` 会让它更慢 | `[D3]` |
| 生产环境禁止长期开 | 用采样/APM 替代 | `[D3]` |

> 注意：这是「空回调」的 6 倍。如果在 tracer 里 `print`，实测会掉到几十倍——所以课件那种「每行打印事件」只适合 10 行以内的小 demo。`[D3]`

### 2.6 从 trace 到 DAP

| 层 | 做什么 | 依据 |
| --- | --- | --- |
| `sys.settrace` | 提供事件流 | `[D3]` |
| `bdb` | 断点管理、单步、栈操作 | `[D4]` |
| `pdb` | 文本交互界面 | `[D1]` |
| `debugpy` | 把以上能力包装成 DAP 服务端 | `[D6]` |
| VSCode | DAP 客户端（UI） | `[D7]` |

## 3. 单文件调试

### 3.1 `breakpoint()` 与 `PYTHONBREAKPOINT`

`breakpoint()` 的实现本质是：

```python
import sys

sys.breakpointhook()      # breakpoint() 就是调它
```

默认 `sys.breakpointhook` 会 `import pdb; pdb.set_trace()`。

| `PYTHONBREAKPOINT` 取值 | 行为 | 依据 |
| --- | --- | --- |
| 未设置 | 进入 pdb | `[D2]` |
| `0` | **完全禁用**，直接返回 | `[D2]` |
| `""`（空串） | 同样禁用 | `[D2]` |
| `模块.函数`（如 `mytool.hook`） | 调用该函数 | `[D2]` |
| `pdb.set_trace` | 显式指定 pdb | `[D2]` |

**实测（禁用）**：

```powershell
$env:PYTHONBREAKPOINT = "0"
python bp.py     # bp.py: x = 1 / breakpoint() / print("AFTER_BP", x)
```

```text
BP_DISABLED 0 True False
```

| 字段 | 含义 |
| --- | --- |
| 退出码 0 | 正常结束 |
| `AFTER_BP 1` 存在 | 后续代码执行了 |
| 无 `(Pdb)` | 没有进入调试器 |

**实测（默认进入）**：

```text
BP_ENABLED True True
```

有 `(Pdb)` 提示符，喂 `c` 后继续执行并输出 `AFTER_BP 1`。

> 注意：`PYTHONBREAKPOINT=0` 是**生产环境的保险**——即使代码里漏了 `breakpoint()`，进程也不会挂起等 stdin。反过来，如果生产容器里没设这个变量而代码里有断点，进程会直接卡死（无 TTY 时 pdb 读 stdin 得到 EOF 后退出，但行为依场景而定）。`[D2]`

### 3.2 `python -m pdb`

```shell
python -m pdb examples/debug_demo.py
```

| 方式 | 行为 | 依据 |
| --- | --- | --- |
| `python -m pdb x.py` | 从第一行开始，停住 | `[D1]` |
| `python -m pdb -c continue x.py` | 不停，只装调试器（配合 `b` 文件里的断点） | `[D1]` |
| 代码里 `breakpoint()` | 跑到该行才停 | `[D2]` |

**实测启动输出**：

```text
> c:\...\demo.py(1)<module>()
-> def main():
(Pdb)   1  ->	def main():
2  	    a = 1
3  	    b = 2
4  	    c = a + b
5  	    return c
6
7  	r = main()
8  	print("RESULT", r)
[EOF]
```

| 片段 | 含义 | 依据 |
| --- | --- | --- |
| `> file(1)<module>()` | 当前停在 `demo.py` 第 1 行，模块级 | `[D1]` |
| `-> def main():` | 即将执行这一行 | `[D1]` |
| 行号列表 | `l` 命令输出，`->` 标记当前行 | `[D1]` |
| `[EOF]` | 已到文件末尾（`l` 无更多内容） | `[D1]` |

### 3.3 pdb 命令全表

| 命令 | 缩写 | 作用 | 依据 |
| --- | --- | --- | --- |
| `help` | `h` | 帮助 | `[D1]` |
| `list` | `l` | 列出源码（默认当前行上下 11 行） | `[D1]` |
| `longlist` | `ll` | 列出整个函数 | `[D1]` |
| `next` | `n` | 执行下一行（不进入函数） | `[D1]` |
| `step` | `s` | 执行下一步（进入函数） | `[D1]` |
| `return` | `r` | 执行到当前函数返回 | `[D1]` |
| `continue` | `c` | 继续到下一个断点 | `[D1]` |
| `until` | `unt` | 执行到指定行 | `[D1]` |
| `jump` | `j` | 跳到指定行（不执行中间代码） | `[D1]` |
| `where` | `w` | 打印调用栈 | `[D1]` |
| `up` | `u` | 上移一层帧 | `[D1]` |
| `down` | `d` | 下移一层帧 | `[D1]` |
| `break` | `b` | 设断点：`b 12` / `b f.py:12` / `b f.py:12, x==3` | `[D1]` |
| `tbreak` | —— | 临时断点（命中一次即删） | `[D1]` |
| `clear` | `cl` | 删除断点 | `[D1]` |
| `disable` / `enable` | —— | 停用/启用断点 | `[D1]` |
| `condition` | —— | 给断点加条件 | `[D1]` |
| `ignore` | —— | 忽略前 N 次命中 | `[D1]` |
| `print` | `p` | 打印表达式 | `[D1]` |
| `p(r)ettyprint` | `pp` | 美化打印 | `[D1]` |
| `args` | `a` | 打印当前函数参数 | `[D1]` |
| `retval` | `rv` | 打印返回值（在 return 事件时） | `[D1]` |
| `source` | —— | 打印对象源码 | `[D1]` |
| `alias` / `unalias` | —— | 命令别名 | `[D1]` |
| `interact` | —— | 进入交互式解释器（共享变量） | `[D1]` |
| `!语句` | —— | 执行任意 Python 语句 | `[D1]` |
| `restart` | —— | 重启调试 | `[D1]` |
| `quit` | `q` | 退出 | `[D1]` |

**实测：设断点并查看变量**

```python
run_pdb(script, "l\nb 4\nc\np a\np b\nn\np c\nq\n")
```

```text
(Pdb)   1  ->	def main():
...
(Pdb) Breakpoint 1 at c:\...\demo.py:4
(Pdb) > c:\...\demo.py(4)main()
-> c = a + b
```

| 步骤 | 输出 | 依据 |
| --- | --- | --- |
| `l` | 列出 8 行源码 | `[D1]` |
| `b 4` | `Breakpoint 1 at ...:4` | `[D1]` |
| `c` | 停在 `(4)main()`，即将执行 `c = a + b` | `[D1]` |
| `p a` / `p b` | `1` / `2` | `[D1]` |
| `n` | 执行该行 | `[D1]` |
| `p c` | `3` | `[D1]` |

### 3.4 实测：`w` / `pp` / `u` / `d`

在 `level_three` 的 `return x / 0` 处停下后：

```text
(Pdb) w
  ...\bdb.py(607)run()
-> exec(cmd, globals, locals)
  <string>(1)<module>()
  ...\layers.py(11)<module>()
-> level_one(5)
  ...\layers.py(8)level_one()
-> return level_two(x)
  ...\layers.py(5)level_two()
-> return level_three(x)
> ...\layers.py(2)level_three()
-> return x / 0
```

```text
(Pdb) pp locals()
{'x': 5}
(Pdb) u
> ...\layers.py(5)level_two()
-> return level_three(x)
(Pdb) p x
5
(Pdb) d
> ...\layers.py(2)level_three()
-> return x / 0
```

| 命令 | 观察 | 依据 |
| --- | --- | --- |
| `w` | 6 层栈：pdb 自身 2 层 + 用户代码 4 层 | `[D1]` |
| `>` 标记 | 当前帧 | `[D1]` |
| `pp locals()` | `{'x': 5}` | `[D1]` |
| `u` | 跳到 `level_two` 帧，`p x` 仍得 5（参数传下来的） | `[D1]` |
| `d` | 回到 `level_three` | `[D1]` |

> 注意：`w` 里前两层是 `pdb`/`bdb` 自身的帧，属正常现象，看栈时从第一个用户文件开始。`u`/`d` 只改「当前查看的帧」，不改变执行位置。`[D1]`

### 3.5 条件断点

```text
(Pdb) b 4, a == 1
Breakpoint 1 at ...:4
(Pdb) c
> ...(4)main()
-> c = a + b
```

| 写法 | 含义 | 依据 |
| --- | --- | --- |
| `b 4, a == 1` | 第 4 行且 `a == 1` 才停 | `[D1]` |
| `condition 1 a > 10` | 给 1 号断点设条件 | `[D1]` |
| `ignore 1 100` | 前 100 次不停 | `[D1]` |
| `tbreak 4` | 只停一次 | `[D1]` |

| 场景 | 用法 | 依据 |
| --- | --- | --- |
| 循环第 500 次才出问题 | `ignore 1 499` 或条件断点 | `[D1]` |
| 只在特定输入停 | `b 4, name == "bad"` | `[D1]` |
| 不想手动 `c` 几百次 | 条件断点 | `[D1]` |

> 注意：条件断点的条件在**每次命中都会求值**，成本不低。循环千万次时，用 `ignore` 跳过前 N 次比复杂条件更快。`[D1]`

### 3.6 post-mortem：崩溃后查现场

```python
import pdb

try:
    risky()
except Exception:
    pdb.post_mortem()      # 进入异常发生处的帧
```

| 方式 | 用法 | 依据 |
| --- | --- | --- |
| `pdb.pm()` | 在 `except` 里进入最近异常的帧 | `[D1]` |
| `pdb.post_mortem(tb)` | 指定 traceback | `[D1]` |
| `python -m pdb -c continue` + `b` | 预埋断点 | `[D1]` |

| 优势 | 说明 | 依据 |
| --- | --- | --- |
| 不用猜哪里崩 | 直接停在异常点 | `[D1]` |
| 保留完整栈 | 可 `u`/`d` 逐层看 | `[D1]` |
| 适合线上复现脚本 | 崩溃后自动进调试 | `[D1]` |

### 3.7 脚本化跑 pdb（CI 友好）

本章所有 pdb 输出都是这样拿到的：

```python
import subprocess
import sys

proc = subprocess.run(
    [sys.executable, "-m", "pdb", str(script)],
    input="l\nb 4\nc\np a\nn\np c\nq\n",
    capture_output=True,
    text=True,
    encoding="utf-8",
    errors="replace",
    timeout=40,
)
print(proc.stdout)
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| `input=` 喂命令序列 | 每行一个命令 | `[D1]` |
| 末尾 `q` 必须加 | 否则等到 EOF | `[D1]` |
| `encoding="utf-8"` + `PYTHONIOENCODING` | 避免 Windows GBK 乱码 | 第 22 章 |
| 退出码 0 | 正常退出 | `[D1]` |

> 注意：pdb 读 stdin，非 TTY 也能工作，所以可以脚本化。这适合「把一次调试过程固化成可重复的验证脚本」，也适合教学材料。`[D1]`

## 4. 工程调试

### 4.1 一、配置

**安装依赖**（课件原文）：

```shell
uv add --dev debugpy
```

**配置调试器**（课件原文 Makefile）：

```makefile
# Makefile
run-web-debug:
	uv run --package web-service python -m debugpy --listen 5678 --wait-for-client app/web-service/main.py
```

**配置调试客户端**（课件原文 `launch.json`）：

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Attach to make run",
      "type": "debugpy",
      "request": "attach",
      "connect": {
        "host": "localhost",
        "port": 5678
      }
    }
  ]
}
```

| 字段 | 含义 | 依据 |
| --- | --- | --- |
| `version` | `launch.json` 格式版本，固定 `0.2.0` | `[D7]` |
| `name` | 下拉菜单显示名 | `[D7]` |
| `type` | 调试器类型，Python 用 `debugpy`（旧版 `python`） | `[D7]` |
| `request` | `launch` 或 `attach` | `[D7]` |
| `program` | 入口文件，`${file}` 是当前打开文件 | `[D7]` |
| `args` | 命令行参数数组 | `[D7]` |
| `cwd` | 工作目录 | `[D7]` |
| `env` | 环境变量 | `[D7]` |
| `console` | `integratedTerminal` / `internalConsole` / `externalTerminal` | `[D7]` |
| `justMyCode` | 是否跳过标准库/三方库 | `[D7]` |
| `python` | 指定解释器（**关键**：要用 venv 里的） | `[D7]` |
| `envFile` | 从 `.env` 读环境变量 | `[D7]` |
| `subProcess` | 是否调试子进程 | `[D7]` |
| `connect.host` / `connect.port` | attach 目标 | `[D7]` |

**`debugpy` 命令行参数**：

| 参数 | 作用 | 依据 |
| --- | --- | --- |
| `--listen 5678` | 监听端口 | `[D6]` |
| `--listen 0.0.0.0:5678` | 指定地址 | `[D6]` |
| `--wait-for-client` | **等客户端连上才继续执行** | `[D6]` |
| `-m module` | 以模块方式运行 | `[D6]` |
| `--log-to file` | 适配器日志 | `[D6]` |
| `--connect host:port` | 反向连接 | `[D6]` |

**单文件 `launch.json`**（课件原文）：

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "Python 调试程序: 当前文件",
      "type": "debugpy",
      "request": "launch",
      "program": "${file}",
      "console": "integratedTerminal"
    }
  ]
}
```

| 问题 | 后果 | 修法 | 依据 |
| --- | --- | --- | --- |
| 没写 `python` | 用系统解释器，venv 依赖不可见 | 加 `"python": "${workspaceFolder}/.venv/Scripts/python.exe"` | `[D7]` |
| 没写 `cwd` | 相对路径找不到文件 | 加 `"cwd": "${workspaceFolder}"` | `[D7]` |
| 没写 `justMyCode: false` | 想看库内部代码断点不生效 | 显式关掉 | `[D7]` |
| 用了 `"type": "python"` | 新版本仍兼容，但推荐 `debugpy` | 改成 `debugpy` | `[D7]` |

**推荐的单文件配置**：

```json
{
  "version": "0.2.0",
  "configurations": [
    {
      "name": "当前文件（项目环境）",
      "type": "debugpy",
      "request": "launch",
      "program": "${file}",
      "cwd": "${workspaceFolder}",
      "python": "${workspaceFolder}/.venv/Scripts/python.exe",
      "console": "integratedTerminal",
      "justMyCode": true,
      "env": { "PYTHONBREAKPOINT": "pdb.set_trace" }
    }
  ]
}
```

| 配置项 | 为什么加 |
| --- | --- |
| `python` | 保证用 uv 装的依赖 |
| `cwd` | 让 `Path("data/x.json")` 相对项目根 |
| `PYTHONBREAKPOINT` | 防止外部环境把它设成 `0` |

### 4.2 二、启动调试

```text
1 启动调试器：make run-web-debug
2 启动调试客户端：VSCode → 运行和调试 → Attach to make run
```

| 步骤 | 预期输出 | 依据 |
| --- | --- | --- |
| 1 | 终端停在 `Waiting for debugger attach...` 或 `debugpy listening on 5678` | `[D6]` |
| 2 | VSCode 状态栏变橙、断点生效 | `[D7]` |
| 3 | 命中断点后可在变量面板看值 | `[D7]` |

| 现象 | 原因 | 处理 | 依据 |
| --- | --- | --- | --- |
| 卡在 `--wait-for-client` 不动 | 没有客户端连上 | 检查端口/防火墙 | `[D6]` |
| 连上但断点灰 | 路径映射不一致 | 配 `pathMappings`（容器） | `[D7]` |
| 断点命中在错的行 | 代码与运行版本不一致 | 重新构建/确认 `cwd` | `[D7]` |
| `Address already in use` | 端口被占用 | 换端口 | `[D6]` |

**workspace 场景的 Makefile**：

```makefile
.PHONY: run-web-debug

run-web-debug:
	uv run --package web-service python -m debugpy --listen 5678 --wait-for-client app/web-service/main.py
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| `--package` | 用成员的依赖环境 | 第 31 章 |
| `--wait-for-client` | 避免启动太快、来不及 attach | `[D6]` |
| 端口固定 5678 | 与 `launch.json` 对齐 | `[D7]` |

> 注意：attach 模式下**代码里不需要 `breakpoint()`**，断点完全由调试器管理。这与单文件 `launch` 的体验一致，但启动权在 Makefile 手里，适合「启动命令很复杂」的项目。`[D6]`

### 4.3 多线程与异步的调试现实

| 场景 | pdb 行为 | 建议 | 依据 |
| --- | --- | --- | --- |
| 多线程 | 只有当前线程停住，其他线程继续跑 | 用日志 + 线程名；VSCode 可切换线程 | `[D1]` |
| asyncio | 停在某个协程，事件循环停摆 | 用 `--wait-for-client` + 单任务复现 | `[D1]` |
| 多进程 | 默认只调父进程 | 配 `subProcess: true` 或分别 attach | `[D7]` |
| 容器内 | 端口映射 + `pathMappings` | 见 4.4 | `[D7]` |

### 4.4 远程/容器调试

```json
{
  "name": "Attach 容器",
  "type": "debugpy",
  "request": "attach",
  "connect": { "host": "127.0.0.1", "port": 5678 },
  "pathMappings": [
    { "localRoot": "${workspaceFolder}", "remoteRoot": "/app" }
  ]
}
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 端口映射 | `docker run -p 5678:5678` | `[D6]` |
| `pathMappings` | 断点行号靠路径匹配 | `[D7]` |
| 只监听内网 | `--listen 127.0.0.1:5678` | 安全底线 |
| 用完关闭端口 | 调试端口属于攻击面 | 安全底线 |

> 注意：`--listen 0.0.0.0` 会把调试端口暴露到网络——任何能连上的人都能**执行任意代码**（调试器支持 `!语句`）。生产/公网环境禁止；临时用完立刻关闭。`[D6]`

## 5. 其他调试手段

### 5.1 `logging`：生产可用

```python
import logging

logger = logging.getLogger(__name__)


def call_tool(name: str) -> None:
    logger.info("tool start", extra={"tool": name, "request_id": rid()})
```

| 相对于 `print` | 优势 | 依据 |
| --- | --- | --- |
| 级别可调 | `DEBUG`/`INFO`/`WARNING` 分环境 | 第 22 章 |
| 带时间/模块/行号 | 定位快 | 第 22 章 |
| 可结构化（JSON） | 便于检索与告警 | 第 22 章 |
| 可关闭 | 生产不留噪音 | 第 22 章 |

| 反模式 | 问题 | 依据 |
| --- | --- | --- |
| `print(f"x={x}")` 上线 | 无级别、无上下文、污染 stdout | 第 22 章 |
| 日志里打完整请求体 | 泄露敏感数据 | 第 01 章 |
| 只打 `except Exception: pass` | 错误消失 | 第 16 章 |

### 5.2 `trace`：行覆盖率

```python
import trace

counter = trace.Trace(count=1, trace=0)
counter.runfunc(exec, compile(TARGET, "demo.py", "exec"), {"__name__": "__main__", "__file__": "demo.py"})
hits = sorted(line for (filename, line) in counter.results().counts if filename.endswith("demo.py"))
print(hits)
```

```text
TRACE_LINES [1, 2, 3, 4, 5, 7, 8]
```

| 观察 | 说明 | 依据 |
| --- | --- | --- |
| 行 6 缺失 | 是空行，无可执行代码 | `[D8]` |
| 行 1 有命中 | 函数定义行会产生事件 | `[D8]` |
| 必须传 `__file__` | 否则 `trace` 无法识别模块名（实测踩过） | `[D8]` |

| 用途 | 命令 | 依据 |
| --- | --- | --- |
| 行覆盖率 | `python -m trace --count -m module` | `[D8]` |
| 调用关系 | `python -m trace --trackcalls` | `[D8]` |
| 生成带计数的源码 | `--coverdir=DIR` | `[D8]` |

> 注意：`trace` 是「为什么这一行没执行」的利器。传 `exec` 时如果 globals 里没有 `__file__`，`trace` 会认为模块名为 `None` 而不统计——这是本课实测踩到的坑。`[D8]`

### 5.3 `faulthandler`：段错误与卡死

```python
import faulthandler

faulthandler.enable()                      # 崩溃时打印 Python 栈
faulthandler.dump_traceback_later(10, exit=True)   # 10 秒后仍卡住则打印并退出
```

| API | 作用 | 依据 |
| --- | --- | --- |
| `enable()` | 段错误/`abort()` 时打印栈 | `[D9]` |
| `dump_traceback_later(timeout, exit=True)` | 卡死超时打印 | `[D9]` |
| `dump_traceback(file=...)` | 手动打印当前栈 | `[D9]` |
| 环境变量 `PYTHONFAULTHANDLER=1` | 全局开启 | `[D9]` |

| 场景 | 为什么用它 | 依据 |
| --- | --- | --- |
| C 扩展崩溃 | Python 层看不到 traceback | `[D9]` |
| 死锁/卡死 | 无异常可抓 | `[D9]` |
| 容器被 OOM kill 前 | 有栈可留 | `[D9]` |

### 5.4 `assert` 与开发模式

| 手段 | 用法 | 依据 |
| --- | --- | --- |
| `assert cond, "msg"` | 断言内部不变量 | 第 16 章 |
| `python -X dev` | 开启开发模式（更严的警告） | `[D3]` |
| `python -W error` | 警告转异常 | 第 22 章 |
| `python -X tracemalloc` | 内存分配追踪 | 第 22 章 |

| 注意 | 说明 | 依据 |
| --- | --- | --- |
| `assert` 在 `-O` 下被移除 | 不能做参数校验 | 第 16 章 |
| 开发模式更慢 | 仅本地 | `[D3]` |

### 5.5 手段选型

| 问题类型 | 首选 | 次选 | 依据 |
| --- | --- | --- | --- |
| 「这行为什么没执行」 | `trace` 覆盖率 | 断点 | `[D8]` |
| 「变量为什么是这个值」 | 断点 + `p` | 日志 | `[D1]` |
| 「第 500 次循环才错」 | 条件断点 | `ignore` | `[D1]` |
| 「崩溃后想知道现场」 | `pdb.post_mortem` | `faulthandler` | `[D1]` `[D9]` |
| 「线上偶发」 | 结构化日志 + trace id | APM | 第 22 章 |
| 「C 扩展崩了」 | `faulthandler` | gdb | `[D9]` |
| 「卡住不动」 | `dump_traceback_later` | `py-spy`（第三方） | `[D9]` |

## 6. 综合示例：可复现的调试脚本

```python
"""第 32 章综合示例：用 settrace 复现一次「断点」并检查栈。"""

from __future__ import annotations

import sys
import traceback
from types import FrameType

TARGET = """\
def level_three(x):
    return x / 0

def level_two(x):
    return level_three(x)

def level_one(x):
    return level_two(x)

try:
    level_one(5)
except ZeroDivisionError:
    pass
"""


def describe(frame: FrameType) -> str:
    return f"{frame.f_code.co_name}:{frame.f_lineno}"


def main() -> None:
    seen: list[str] = []

    def tracer(frame: FrameType, event: str, arg: object):
        if frame.f_code.co_name.startswith("level"):
            if event == "call":
                seen.append("call " + describe(frame))
            elif event == "exception":
                seen.append("raise " + describe(frame))
        return tracer

    sys.settrace(tracer)
    try:
        exec(compile(TARGET, "layers.py", "exec"), {"__name__": "__main__"})
    except ZeroDivisionError:
        chain = []
        tb = sys.exc_info()[2]
        while tb is not None:
            chain.append(describe(tb.tb_frame))
            tb = tb.tb_next
        print("TB_CHAIN", chain)
        traceback.print_exc(limit=2)
    finally:
        sys.settrace(None)

    print("EVENTS", seen)


main()
```

本机实测输出（关键两行）：

```text
TB_CHAIN ['<module>:11', 'level_one:8', 'level_two:5', 'level_three:2']
EVENTS ['call level_one:7', 'call level_two:4', 'call level_three:1', 'raise level_three:2']
```

**逐段说明**：

| 代码 | 机制 | 依据 |
| --- | --- | --- |
| `sys.settrace(tracer)` | 注册全局跟踪 | `[D3]` |
| `event == "call"` | 函数进入 | `[D3]` |
| `event == "exception"` | 异常抛出（在 `f_lineno` 处） | `[D3]` |
| `tb.tb_frame` | traceback 里的帧链 | `[D5]` |
| `traceback.print_exc(limit=2)` | 只看最近两层 | `[D5]` |
| `finally: sys.settrace(None)` | 必须清理，否则全局拖慢 | `[D3]` |

> 注意：`raise` 事件发生在 `level_three:2`，也就是 `return x / 0` 那一行——这正是「断点停在出错行」的实现原理。`[D3]`

## 7. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 生产镜像里留 `breakpoint()` | 进程挂起等 stdin | `PYTHONBREAKPOINT=0` + 代码审查 | `[D2]` |
| 以为 `breakpoint()` 是语法 | 它只是函数调用 | 可用钩子改成别的 | `[D2]` |
| `PYTHONBREAKPOINT=0` 后以为断点还生效 | 完全不进调试器（实测） | 要调试时别设 | `[D2]` |
| `PYTHONBREAKPOINT` 写成 `1` | 会尝试 import 模块 `1` 失败 | 用 `0` 或模块路径 | `[D2]` |
| tracer 不返回自身 | 只有第一次事件 | `return tracer` | `[D3]` |
| 忘记 `sys.settrace(None)` | 后续代码全部拖慢 | `try/finally` | `[D3]` |
| 在 tracer 里 `print` | 输出爆炸、慢几十倍 | 只记录关键事件 | `[D3]` |
| 生产开 `settrace` | 性能塌陷 | 只本地用 | `[D3]` |
| 断点停在 `c = a + b` 就 `p c` | `NameError`（行未执行） | 先 `n` | `[D1]` |
| `b` 的行号写错 | 断点不命中 | 用 `l` 先确认行号 | `[D1]` |
| 循环里手动 `c` 几百次 | 低效 | 条件断点 / `ignore` | `[D1]` |
| 条件断点写复杂表达式 | 每次命中都求值，慢 | 用 `ignore` | `[D1]` |
| `q` 忘了敲 | 进程挂住 | 脚本化时末尾加 `q` | `[D1]` |
| 用 `p` 打印大对象 | 刷屏 | `pp` 或 `!` 后 `reprlib` | `[D1]` |
| 用 `print` 代替日志 | 无级别无上下文 | `logging` | 第 22 章 |
| 日志里打完整响应体 | 泄露密钥/隐私 | 脱敏 + 截断 | 第 01 章 |
| `except: pass` 掩盖错误 | 定位成本翻倍 | 记 traceback | 第 16 章 |
| 只凭 traceback 猜变量值 | 猜错方向 | 断点或加日志 | `[D1]` |
| `launch.json` 不指定 `python` | 用了系统解释器 | 指向 `.venv` | `[D7]` |
| `launch.json` 不指定 `cwd` | 相对路径失效 | `${workspaceFolder}` | `[D7]` |
| `${file}` 在无文件时启动 | 报「没有可调试文件」 | 指定具体 `program` | `[D7]` |
| `type` 写 `python` 又报错 | 版本兼容问题 | 用 `debugpy` | `[D7]` |
| attach 时端口不对 | 一直等待 | 对齐 Makefile 与 `launch.json` | `[D6]` |
| 忘加 `--wait-for-client` | 进程已跑完来不及 attach | 加上 | `[D6]` |
| `--listen 0.0.0.0` 暴露公网 | 任意代码执行 | 只监听内网 | 安全底线 |
| 调试端口用完不关 | 留下攻击面 | 用完立即停 | 安全底线 |
| 容器调试不配 `pathMappings` | 断点灰 | 映射 local/remote | `[D7]` |
| 多线程只停一个线程就以为全停 | 其他线程照跑 | 日志 + 线程名 | `[D1]` |
| 异步代码里 `time.sleep` 调试 | 循环全停，误判死锁 | 用 `await asyncio.sleep` | 第 24 章 |
| 多进程调试只看父进程 | 子进程断点不生效 | `subProcess: true` 或分开 attach | `[D7]` |
| 断点数过多 | 明显变慢 | 只留关键断点 | `[D3]` |
| 以为断点改代码 | 重启即消失 | 想持久用日志 | `[D4]` |
| `pdb.pm()` 用在不相关的 except 里 | 停在别处 | 用 `post_mortem(tb)` | `[D1]` |
| `trace` 传 `exec` 不传 `__file__` | 统计为空（实测） | globals 里加 `__file__` | `[D8]` |
| 用 `assert` 做用户输入校验 | `-O` 下被移除 | 显式 `if not: raise` | 第 16 章 |
| 崩溃只看到 `Segmentation fault` | 无栈 | `faulthandler.enable()` | `[D9]` |
| 卡死无限等 | 不知道卡哪 | `dump_traceback_later` | `[D9]` |
| 把临时 `breakpoint()` 提交 | 团队被卡 | pre-commit 检查 | 第 01 章 |
| 调试完不删临时 print | 日志噪音 | 提交前搜索 | 第 01 章 |
| 在 `__del__` 里打断点 | 时机诡异 | 改显式清理 | `[D1]` |
| 用 `jump` 跳过初始化 | 状态不一致、难排查 | 只在明确安全时用 | `[D1]` |

## 8. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 先复现、再最小化、后断点 | 稳定复现是前提 | `[D1]` |
| 用条件断点处理第 N 次 | 不要手敲 `c` | `[D1]` |
| 崩溃用 `post_mortem` | 直接停在现场 | `[D1]` |
| 线上用结构化日志 + trace id | 不可交互 | 第 22 章 |
| 生产设 `PYTHONBREAKPOINT=0` | 保险 | `[D2]` |
| 配 `faulthandler` | 卡死/段错误有栈 | `[D9]` |
| 调试器用 venv 解释器 | 依赖一致 | `[D7]` |
| attach 用 `--wait-for-client` | 不漏机会 | `[D6]` |
| 调试端口只监听内网 | 安全 | 安全底线 |
| 修复后补回归测试 | 把 bug 变防线 | 第 01 章 |
| 提交前清 `breakpoint()`/print | 代码卫生 | 第 01 章 |
| `settrace` 用 `try/finally` 清理 | 避免全局拖慢 | `[D3]` |

**风格示范**：

```python
"""diagnostics 模块：可开关的调试辅助，避免把 breakpoint 留在代码里。

为什么用环境变量控制：生产设 DIAG=0 即完全不产生开销，不必改代码。
"""

from __future__ import annotations

import logging
import os
import sys
from types import FrameType

logger = logging.getLogger(__name__)

ENABLED = os.environ.get("DIAG", "0") == "1"


def watch(function_name: str) -> None:
    """在指定函数入口打印帧信息（仅 DIAG=1 时生效）。"""
    if not ENABLED:
        return
    frame: FrameType | None = sys._getframe(1)
    if frame is not None:
        logger.debug("enter %s at %s:%s", function_name, frame.f_code.co_filename, frame.f_lineno)
```

**命令速查**：

```powershell
# 单文件
python -m pdb script.py
python -m pdb -c continue script.py

# 禁用所有 breakpoint()
$env:PYTHONBREAKPOINT = "0"

# 段错误/卡死诊断
$env:PYTHONFAULTHANDLER = "1"

# 行覆盖率
python -m trace --count -m your_module

# 工程调试（先起服务，再 attach）
uv run --package web-service python -m debugpy --listen 5678 --wait-for-client app/web-service/main.py
```

**边界**：

- 调试器只能看到「帧里有的东西」，被内联/优化的代码可能行号不准。
- 异步与多线程下「暂停」是局部的，别把「停住」当「全局冻结」。
- 交互式调试不适用于无 stdin 的容器/CI，那里只能用日志与 `faulthandler`。

## 9. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[D1]` | python.org | https://docs.python.org/3.12/library/pdb.html | `python -m pdb`、命令全表、条件断点、`post_mortem` |
| `[D2]` | PEP 官方 | https://peps.python.org/pep-0553/ | `breakpoint()` 与 `PYTHONBREAKPOINT` 语义 |
| `[D3]` | python.org | https://docs.python.org/3.12/library/sys.html#sys.settrace | 事件类型、tracer 返回值要求、开销 |
| `[D4]` | python.org | https://docs.python.org/3.12/library/bdb.html | 断点管理、单步、栈操作实现 |
| `[D5]` | python.org | https://docs.python.org/3.12/library/inspect.html | 帧对象属性、`currentframe`、traceback 链 |
| `[D6]` | GitHub 官方 | https://github.com/microsoft/debugpy | `--listen`/`--wait-for-client`、DAP 服务端 |
| `[D7]` | VSCode 官方文档 | https://code.visualstudio.com/docs/python/debugging | `launch.json` 字段、launch/attach、`pathMappings`、`subProcess` |
| `[D8]` | python.org | https://docs.python.org/3.12/library/trace.html | 行覆盖率、`__file__` 与模块识别 |
| `[D9]` | python.org | https://docs.python.org/3.12/library/faulthandler.html | 段错误/卡死时的栈输出 |
| `[D10]` | PEP 官方 | https://peps.python.org/pep-0008/ | 注释写「为什么」、不提交调试代码 |
| `[D11]` | 官方站点 | https://microsoft.github.io/debug-adapter-protocol/ | DAP 协议职责划分 |

> **核对状态**：`[D10]` 与本章 `README.md` 已核对来源一致；`[D1]`–`[D9]`、`[D11]` 按官方文档结构整理，**本次未逐页直连复核**。文中「实测」为本机 Python 3.12.8 / Windows 的真实输出；pdb 均为子进程喂命令获得，`debugpy` 本机**未安装**，第 4 节配置按官方文档陈述，**未实际 attach 验证**。

## 10. 毕业自查清单

**能说清（概念层）**：

- [ ] 调试四层组件各自职责（UI/DAP/适配器/运行时）
- [ ] 断点为什么不改字节码
- [ ] `settrace` 的 `call`/`line`/`return`/`exception` 各在何时触发
- [ ] 为什么 `line` 事件停在语句「执行前」
- [ ] `breakpoint()` 与 `sys.breakpointhook` 的关系
- [ ] `PYTHONBREAKPOINT=0` 与 `""` 的差异
- [ ] launch 与 attach 的适用场景
- [ ] `settrace` 的性能代价量级（实测约 6 倍）
- [ ] 多线程/异步「暂停」的局部性
- [ ] 生产为什么不能用交互式调试

**能写出（代码层）**：

- [ ] 一个 `settrace` tracer 并正确清理
- [ ] 用 `inspect.currentframe` 取函数名与行号
- [ ] 遍历 traceback 链输出 `函数:行号`
- [ ] 脚本化跑 pdb（`subprocess` + `input`）
- [ ] 条件断点 `b 4, a == 1`
- [ ] post-mortem 捕获
- [ ] 单文件 `launch.json`（含 `python`/`cwd`）
- [ ] `debugpy --listen --wait-for-client` + attach 配置
- [ ] `trace.Trace` 统计行命中
- [ ] `faulthandler.dump_traceback_later`

**能判断（避坑层）**：

- [ ] 看到生产 `breakpoint()` 能指出挂起风险
- [ ] 看到 tracer 不返回自身能指出只触发一次
- [ ] 看到 `p c` 报 `NameError` 能指出行未执行
- [ ] 看到 `launch.json` 无 `python` 能指出用了系统解释器
- [ ] 看到 `--listen 0.0.0.0` 能指出远程代码执行风险
- [ ] 看到 `trace` 统计为空能指出缺 `__file__`
- [ ] 看到 `except: pass` 能指出错误丢失

**能跑通（验收层）**：

- [ ] 运行 `examples/debug_demo.py` 并解释 `function` 字段
- [ ] 把第 6 节示例存成文件运行，输出与文档一致
- [ ] 用 `python -m pdb` + `l/n/p/c/q` 走一遍
- [ ] 用 `PYTHONBREAKPOINT=0` 验证 `breakpoint()` 被跳过
- [ ] 用 `b 4, a == 1` 复现条件断点

## 11. 全教程收尾

```text
01 环境 → 02–16 语法与对象模型 → 17–19 核心协议 → 20–23 类型与模块化
→ 24–28 并发与异步 → 29–32 工程化与工具链
```

本章是第 32 章，也是教程最后一章。四章工程化的分工可以这样回顾：

| 章 | 解决 | 一句话 |
| --- | --- | --- |
| 29 构建发布 | 怎么把代码变成可分发的包 | 源码 → wheel → registry → site-packages |
| 30 项目管理工具 | 怎么可复现地装、锁、跑 | 一个项目、一个锁、一条命令 |
| 31 monorepo | 多个包怎么放一个仓 | 一把锁、单向依赖、CI 增量 |
| 32 断点调试 | 出事时怎么定位 | 先复现，再 `settrace`/`pdb`/日志 |

下一步不是继续学语法，而是把第 01 章那个「四步 Agent 回合」用真实工具与模型客户端实现一遍，并用本部分的手段保证它：

| 质量目标 | 用什么 |
| --- | --- |
| 可安装可发布 | 第 29 章 `pyproject.toml` + `uv build` |
| 可复现 | 第 30 章 `uv.lock` + `--locked` |
| 可扩展 | 第 31 章 workspace + 单向依赖 |
| 可并发 | 第 27 章 `TaskGroup` + 限流 |
| 可排查 | 第 32 章 结构化日志 + `faulthandler` + attach |