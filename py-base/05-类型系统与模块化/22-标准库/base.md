# 22 标准库 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把截图里的「官方手册两个入口、内置 API、内置模块、标准库」展开成可查可用的清单，并对 12 个高频模块给出实测片段与坑，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测；截图引用 3.14 手册，结构相同） |
| 前置 | 第 02、21 章（环境、模块化） |
| 覆盖范围 | 标准库三层结构、内置函数/常量、按功能分组的模块表、12 个必会模块实测、选型判断、版本/平台差异 |
| 明确不覆盖 | 并发模块细节（24–28）、`asyncio`、第三方替代方案（23）、`tkinter`/`curses` GUI |
| 学完验收 | 能按场景选出模块、能说清 `decimal` 为什么替代 `float`、能避免 `json`/`csv`/`pathlib` 的常见坑（见第 13 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Zn]` `` 指向第 12 节官方链接；标「实测」的是本机 Python 3.12.8 运行结果。

**推荐顺序**：

```text
1 标准库是什么（第 1 节）    → 三层 + 两个入口
2 内置 API（第 2 节）        → 函数 / 常量 / 异常
3 模块分组表（第 3 节）      → 按功能查
4 必会 12 模块（第 4 节）    → 实测片段
5 深挖 decimal（第 5 节）    → 金额必看
6 选型判断（第 6 节）        → 何时换第三方
7 综合示例（第 7 节）
8 注意事项（第 8 节）        → 40 条错误对照
```

**与 README 的分工**：README 给结论与边界，本文件负责清单穷举与实测证据。冲突时以本文件为准。

## 1. 标准库是什么

### 1.1 官方手册两个入口

| 入口 | 链接 | 用途 | 依据 |
| --- | --- | --- | --- |
| 按功能 | https://docs.python.org/zh-cn/3.14/library/index.html | 知道「要做什么」时查 | `[Z1]` |
| 按名称 | https://docs.python.org/zh-cn/3/py-modindex.html | 知道「模块名」时查 | `[Z1]` |

> 注意：截图给的是 3.14 中文手册，本机是 3.12；把 URL 里的 `3.14` 换成 `3.12` 才是你正在用的版本。版本差异在标准库里是真实存在的（`tomllib` 3.11+、`graphlib` 3.9+、`pairwise` 3.10+）。

### 1.2 三层结构

```text
标准库
├── 内置 API（builtins）        ← 不用 import，直接可用
│   ├── 内置函数：len / print / sorted / isinstance ...
│   ├── 内置常量：True / False / None / NotImplemented / Ellipsis / __debug__
│   ├── 内置类型：int / str / list / dict / bytes ...
│   └── 内置异常：ValueError / KeyError / OSError ...（16 章）
├── 内置模块（built-in modules） ← 编译进解释器，如 sys / builtins / _thread
└── 标准库（stdlib）            ← 随解释器分发的 .py 模块，如 json / pathlib / re
```

本机实测规模：

```python
import sys, builtins
print(sys.version_info[:2], len(sys.stdlib_module_names), len(dir(builtins)))
# (3, 12) 301 158（实测）
```

| 层 | 数量（本机） | 是否需要 import | 依据 |
| --- | --- | --- | --- |
| 内置函数+类型+常量 | 158 个名字 | ❌ | `[Z1]` |
| 标准库模块名 | 301 个 | ✅ | `[Z6]` |
| 内置模块 | 数十个（`sys` / `builtins` 等） | ✅（但是 C 实现） | `[Z1]` |

> 注意：`sys.stdlib_module_names` 是 3.10+ 才有的集合，用来判断「这个模块是不是标准库」比维护白名单可靠；但它**不含**第三方包，也不含 `site-packages` 里的同名覆盖。`[Z6]`

### 1.3 与第三方库的边界

| 维度 | 标准库 | 第三方库 |
| --- | --- | --- |
| 安装 | 随解释器 | `pip install`（23 章） |
| 版本 | 跟 Python 走 | 独立版本 |
| 维护 | CPython 团队 | 各自社区 |
| 优点 | 零依赖、稳定、审计容易 | 更专业、更易用 |
| 缺点 | API 偏底层、更新慢 | 供应链风险 |
| 依据 | `[Z1]` | 23 章 |

| 场景 | 标准库够用 | 建议换第三方 |
| --- | --- | --- |
| HTTP 客户端 | `urllib.request` 能跑 | `httpx` / `requests` |
| 数据校验 | 手写 `if` | `pydantic` |
| 时区 | `zoneinfo` 够用 | `dateutil`（复杂规则） |
| 表格数据 | `csv` | `pandas`（分析场景） |
| 重试 | 手写循环 | `tenacity` |
| 依据 | `[Z1]` | 23 章 |

> 注意：判断标准不是「哪个更强」，而是「标准库是否让你写出**可维护**的代码」。为了省一个依赖而手写 200 行解析器，通常是亏的。`[Z4]`

### 1.4 版本与平台差异

| 模块/特性 | 起始版本 | 依据 |
| --- | --- | --- |
| `graphlib` | 3.9 | `[Z1]` |
| `zoneinfo` | 3.9 | `[Z1]` |
| `pairwise` | 3.10 | `[Z7]` |
| `tomllib` | 3.11 | `[Z1]` |
| `ExceptionGroup` | 3.11 | 16 章 |
| `typing.Self` | 3.11 | 20 章 |
| `type` 别名语法 | 3.12 | 20 章 |

| 平台差异 | 说明 | 依据 |
| --- | --- | --- |
| `os.name` | `nt` / `posix` | `[Z5]` |
| 路径分隔符 | `\` vs `/`，用 `pathlib` 抹平 | `[Z5]` |
| `signal` 部分行为 | Windows 受限 | `[Z1]` |
| `fcntl` / `pwd` / `grp` | 仅 Unix | `[Z1]` |
| `msvcrt` | 仅 Windows | `[Z1]` |

实测平台值：

```python
import os, sys
print(os.name, sys.platform, os.path.join("a", "b"))
# nt win32 a\b（实测）
```

> 注意：写跨平台代码时，路径一律用 `pathlib`；不要手拼 `"/"` 或 `"\\"`，也不要假设 `os.name == "posix"`。`[Z5]`

## 2. 内置 API（builtins）

### 2.1 内置函数分类

| 分类 | 函数 | 依据 |
| --- | --- | --- |
| 类型构造 | `bool` `int` `float` `complex` `str` `bytes` `bytearray` `list` `tuple` `set` `frozenset` `dict` `object` | `[Z1]` |
| 数值运算 | `abs` `divmod` `pow` `round` `hash` | `[Z1]` |
| 序列与迭代 | `len` `iter` `next` `range` `slice` `reversed` `sorted` `enumerate` `zip` `map` `filter` `all` `any` `sum` `min` `max` | `[Z1]` |
| 对象与属性 | `type` `isinstance` `issubclass` `getattr` `setattr` `hasattr` `delattr` `vars` `dir` `super` `property` `staticmethod` `classmethod` `callable` `id` | `[Z1]` |
| 执行与编译 | `compile` `eval` `exec` `globals` `locals` `breakpoint` `__import__` `help` | `[Z1]` |
| 文本与表示 | `repr` `ascii` `format` `chr` `ord` `bin` `oct` `hex` | `[Z1]` |
| I/O | `print` `input` `open` | `[Z1]` |
| 其他 | `memoryview` `classmethod` `aiter` `anext` | `[Z1]` |

```python
print(divmod(7, 2), round(2.675, 2), pow(2, 10, 1000))
print(sorted({"b": 1, "a": 2}), list(zip("ab", [1, 2])))
print(bin(10), oct(10), hex(10), chr(65), ord("A"))
```

| 容易忽略的 | 说明 | 依据 |
| --- | --- | --- |
| `round(2.675, 2)` | 得 `2.67`（浮点表示问题） | `[Z1]` |
| `pow(a, b, m)` | 模幂，密码学常用 | `[Z1]` |
| `any([])` / `all([])` | `False` / `True` | `[Z1]` |
| `sorted(dict)` | 排的是键 | `[Z1]` |

### 2.2 内置常量

| 常量 | 含义 | 依据 |
| --- | --- | --- |
| `True` / `False` | 布尔 | `[Z1]` |
| `None` | 空值 | `[Z1]` |
| `NotImplemented` | 二元运算「不支持」，返回给解释器 | `[Z1]` |
| `Ellipsis`（`...`） | 占位、切片语法、类型中表示变长 | `[Z1]` |
| `__debug__` | 非 `-O` 时为 `True` | `[Z1]` |

| 对比 | 区别 | 依据 |
| --- | --- | --- |
| `None` vs `NotImplemented` | 空值 vs 运算协议信号 | `[Z1]` |
| `...` vs `pass` | 表达式 vs 语句 | `[Z1]` |
| `NotImplemented` vs `NotImplementedError` | 值 vs 异常类 | 14 章 |

```python
print(__debug__, ... is Ellipsis, bool([]), all([]))
```

### 2.3 内置异常

| 分组 | 常见异常 | 依据 |
| --- | --- | --- |
| 值/类型 | `ValueError` `TypeError` `AttributeError` | `[Z1]` |
| 查找 | `KeyError` `IndexError` | `[Z1]` |
| 算术 | `ZeroDivisionError` `OverflowError` | `[Z1]` |
| IO | `OSError` `FileNotFoundError` `PermissionError` `TimeoutError` | `[Z1]` |
| 导入 | `ImportError` `ModuleNotFoundError` | `[Z1]` |
| 其他 | `RuntimeError` `StopIteration` `AssertionError` `NameError` | `[Z1]` |

> 详细层级与捕获策略见第 16 章，本节只做索引。

### 2.4 内置类型速查

| 类型 | 可变 | 有序 | 可哈希 | 依据 |
| --- | --- | --- | --- | --- |
| `int` / `float` / `complex` | ❌ | —— | ✅ | `[Z1]` |
| `str` | ❌ | ✅ | ✅ | `[Z1]` |
| `bytes` | ❌ | ✅ | ✅ | `[Z1]` |
| `bytearray` | ✅ | ✅ | ❌ | `[Z1]` |
| `list` | ✅ | ✅ | ❌ | `[Z1]` |
| `tuple` | ❌ | ✅ | 元素可哈希时 ✅ | `[Z1]` |
| `dict` | ✅ | ✅（3.7+ 插入序） | ❌ | `[Z1]` |
| `set` | ✅ | ❌ | ❌ | `[Z1]` |
| `frozenset` | ❌ | ❌ | ✅ | `[Z1]` |

## 3. 模块分组表（按功能）

### 3.1 文本处理

| 模块 | 用途 | 依据 |
| --- | --- | --- |
| `string` | 字符常量、`Template` | `[Z1]` |
| `re` | 正则 | `[Z1]` |
| `difflib` | 差异比较 | `[Z1]` |
| `textwrap` | 换行、缩进、截断 | `[Z1]` |
| `unicodedata` | Unicode 属性 | `[Z1]` |

### 3.2 数据类型

| 模块 | 用途 | 依据 |
| --- | --- | --- |
| `datetime` | 日期时间 | `[Z1]` |
| `zoneinfo` | IANA 时区（3.9+） | `[Z1]` |
| `calendar` | 日历计算 | `[Z1]` |
| `collections` | `Counter`/`deque`/`defaultdict`/`ChainMap` | `[Z7]` |
| `collections.abc` | 抽象基类（19 章） | `[Z7]` |
| `heapq` | 堆队列 | `[Z1]` |
| `bisect` | 有序插入/查找 | `[Z1]` |
| `array` | 紧凑数值数组 | `[Z1]` |
| `copy` | 浅拷贝/深拷贝 | `[Z1]` |
| `pprint` | 美化打印 | `[Z1]` |
| `enum` | 枚举 | `[Z1]` |
| `graphlib` | 拓扑排序（3.9+） | `[Z1]` |

### 3.3 数值与数学

| 模块 | 用途 | 依据 |
| --- | --- | --- |
| `math` | 标量数学 | `[Z1]` |
| `cmath` | 复数数学 | `[Z1]` |
| `decimal` | 十进制精确运算 | `[Z8]` |
| `fractions` | 分数 | `[Z1]` |
| `statistics` | 统计量 | `[Z1]` |
| `random` | 伪随机 | `[Z1]` |
| `secrets` | 密码学安全随机 | `[Z1]` |
| `numbers` | 数值抽象基类 | `[Z1]` |

### 3.4 函数式与迭代

| 模块 | 用途 | 依据 |
| --- | --- | --- |
| `itertools` | 迭代器工具（17 章） | `[Z7]` |
| `functools` | `cache`/`partial`/`wraps`/`reduce` | `[Z3]` |
| `operator` | 运算符函数版 | `[Z1]` |

### 3.5 文件、路径与持久化

| 模块 | 用途 | 依据 |
| --- | --- | --- |
| `pathlib` | 面向对象路径 | `[Z5]` |
| `os` / `os.path` | 系统接口、路径函数式 API | `[Z1]` |
| `shutil` | 复制/移动/磁盘用量 | `[Z1]` |
| `glob` / `fnmatch` | 通配符匹配 | `[Z1]` |
| `tempfile` | 临时文件/目录 | `[Z1]` |
| `fileinput` | 多文件逐行读取 | `[Z1]` |
| `json` | JSON 读写 | `[Z6]` |
| `csv` | CSV 读写 | `[Z1]` |
| `tomllib` | TOML 只读（3.11+） | `[Z1]` |
| `configparser` | INI 配置 | `[Z1]` |
| `sqlite3` | 嵌入式数据库 | `[Z1]` |
| `pickle` | 对象序列化（不可信数据禁用） | `[Z1]` |
| `shelve` / `dbm` | 键值持久化 | `[Z1]` |

### 3.6 压缩、加密、编码

| 模块 | 用途 | 依据 |
| --- | --- | --- |
| `zlib` / `gzip` / `bz2` / `lzma` | 压缩 | `[Z1]` |
| `zipfile` / `tarfile` | 归档 | `[Z1]` |
| `hashlib` | 哈希（MD5/SHA） | `[Z1]` |
| `hmac` | 消息认证码 | `[Z1]` |
| `secrets` | 令牌生成 | `[Z1]` |
| `base64` / `binascii` / `quopri` | 编码 | `[Z1]` |
| `struct` | 二进制打包 | `[Z1]` |

### 3.7 OS、运行时与日志

| 模块 | 用途 | 依据 |
| --- | --- | --- |
| `os` | 环境变量、进程、文件描述符 | `[Z1]` |
| `sys` | 解释器状态、`argv`、`path` | `[Z6]` |
| `io` | 流抽象 | `[Z1]` |
| `time` | 时间戳、`perf_counter` | `[Z1]` |
| `logging` | 日志 | `[Z1]` |
| `platform` | 平台信息 | `[Z1]` |
| `errno` | 错误码 | `[Z1]` |
| `ctypes` | 调用 C 库 | `[Z1]` |

### 3.8 并发与进程

| 模块 | 用途 | 依据 |
| --- | --- | --- |
| `threading` | 线程 | 28 章 |
| `multiprocessing` | 进程 | 28 章 |
| `concurrent.futures` | 线程/进程池 | 28 章 |
| `subprocess` | 子进程 | `[Z1]` |
| `queue` | 线程安全队列 | `[Z1]` |
| `asyncio` | 异步事件循环 | 24–27 章 |
| `contextvars` | 上下文变量 | `[Z1]` |

### 3.9 网络与互联网

| 模块 | 用途 | 依据 |
| --- | --- | --- |
| `socket` / `ssl` | 底层网络 | `[Z1]` |
| `http.client` / `http.server` | HTTP | `[Z1]` |
| `urllib.request` / `urllib.parse` | URL 与请求 | `[Z1]` |
| `smtplib` / `imaplib` / `poplib` | 邮件 | `[Z1]` |
| `uuid` | UUID | `[Z1]` |
| `socketserver` | 服务器框架 | `[Z1]` |

### 3.10 开发工具与调试

| 模块 | 用途 | 依据 |
| --- | --- | --- |
| `argparse` | 命令行参数 | `[Z1]` |
| `unittest` / `unittest.mock` | 测试 | `[Z1]` |
| `doctest` | 文档测试 | `[Z1]` |
| `pdb` | 调试器 | `[Z1]` |
| `traceback` | 回溯格式化（16 章） | `[Z1]` |
| `timeit` / `cProfile` / `profile` | 性能 | `[Z1]` |
| `tracemalloc` | 内存追踪 | `[Z1]` |
| `pydoc` | 文档生成 | `[Z1]` |
| `venv` / `ensurepip` | 环境与引导 | 23 章 |

### 3.11 运行时与导入

| 模块 | 用途 | 依据 |
| --- | --- | --- |
| `builtins` | 内置命名空间 | `[Z1]` |
| `__main__` | 入口模块 | 21 章 |
| `warnings` | 警告 | `[Z1]` |
| `atexit` | 退出钩子 | `[Z1]` |
| `gc` | 垃圾回收 | `[Z1]` |
| `inspect` | 反射 | `[Z1]` |
| `dataclasses` | 数据类 | `[Z1]` |
| `contextlib` | 上下文工具（18 章） | `[Z1]` |
| `abc` | 抽象基类（19 章） | `[Z1]` |
| `importlib` | 导入系统（21 章） | `[Z1]` |
| `pkgutil` / `runpy` / `zipimport` | 包与运行 | `[Z1]` |
| `ast` / `tokenize` / `dis` | 语法与字节码 | `[Z1]` |

### 3.12 多媒体与 GUI

| 模块 | 用途 | 依据 |
| --- | --- | --- |
| `wave` / `colorsys` | 音频、颜色 | `[Z1]` |
| `turtle` | 绘图教学 | `[Z1]` |
| `tkinter` | GUI | `[Z1]` |
| `curses` | 终端界面（Unix） | `[Z1]` |

## 4. 必会 12 个模块（实测）

### 4.1 `pathlib`

```python
import pathlib

print(pathlib.PurePosixPath("/data/tools.json").suffix)   # .json（实测）
print(pathlib.Path("a") / "b.txt")                        # a\b.txt（实测）
print(pathlib.PurePath("x.tar.gz").suffixes)              # ['.tar', '.gz']（实测）
```

| 方法 | 作用 | 依据 |
| --- | --- | --- |
| `Path("a") / "b"` | 拼接 | `[Z5]` |
| `.suffix` / `.suffixes` | 扩展名 | `[Z5]` |
| `.stem` / `.name` | 去扩展名 / 文件名 | `[Z5]` |
| `.parent` / `.parents` | 上级目录 | `[Z5]` |
| `.exists()` / `.is_file()` | 判断 | `[Z5]` |
| `.read_text(encoding=...)` | 读文本（务必给编码） | `[Z5]` |
| `.write_text(...)` | 写文本 | `[Z5]` |
| `.mkdir(parents=True, exist_ok=True)` | 建目录 | `[Z5]` |
| `.glob("*.json")` | 通配 | `[Z5]` |
| `.iterdir()` | 遍历 | `[Z5]` |

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| 不给 `encoding` | 平台默认编码不同（Windows 是 GBK） | `[Z5]` |
| `Path` 与 `os.path` 混用 | 风格割裂 | `[Z5]` |
| `Path("a") + "b"` | `TypeError`，要用 `/` | `[Z5]` |
| Windows 下打印路径 | 反斜杠，属正常 | `[Z5]` |

### 4.2 `json`

```python
import json

payload = {"tool": "search", "limit": 3, "name": "搜索"}
text = json.dumps(payload, ensure_ascii=False)
print(text)                       # {"tool": "search", "limit": 3, "name": "搜索"}（实测）
print(json.loads(text)["name"])   # 搜索（实测）
print(len(json.dumps(payload)))   # 54（含 ASCII 转义，实测）
```

| 参数 | 作用 | 依据 |
| --- | --- | --- |
| `ensure_ascii=False` | 保留中文 | `[Z6]` |
| `indent=2` | 美化 | `[Z6]` |
| `sort_keys=True` | 键排序，便于 diff | `[Z6]` |
| `default=str` | 不可序列化对象降级 | `[Z6]` |
| `cls=...` | 自定义编码器 | `[Z6]` |

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| 默认 `ensure_ascii=True` | 中文变 `\uXXXX` | `[Z6]` |
| 只支持 `str`/`int`/`float`/`bool`/`None`/`list`/`dict` | `datetime`/`Decimal` 需自定义 | `[Z6]` |
| `json.loads` 接受 `str`/`bytes` | 不是文件对象（那是 `load`） | `[Z6]` |
| 键必须是 `str` | `int` 键会被转成字符串 | `[Z6]` |
| `NaN`/`Infinity` 非标准 | 默认允许写出 | `[Z6]` |

```python
# 文件读写
path.write_text(json.dumps(payload, ensure_ascii=False), encoding="utf-8")
data = json.loads(path.read_text(encoding="utf-8"))
```

### 4.3 `datetime`

```python
import datetime

now = datetime.datetime(2026, 1, 2, 3, 4, 5, tzinfo=datetime.timezone.utc)
print(now.isoformat())                                  # 2026-01-02T03:04:05+00:00（实测）
print(now.strftime("%Y-%m-%d"))                         # 2026-01-02（实测）
print(datetime.datetime.fromisoformat("2026-01-02T03:04:05+00:00").year)   # 2026（实测）
```

| 类型 | 用途 | 依据 |
| --- | --- | --- |
| `date` | 日期 | `[Z1]` |
| `time` | 时刻 | `[Z1]` |
| `datetime` | 日期+时刻 | `[Z1]` |
| `timedelta` | 时间差 | `[Z1]` |
| `timezone.utc` | UTC | `[Z1]` |
| `zoneinfo.ZoneInfo("Asia/Shanghai")` | 命名时区（3.9+） | `[Z1]` |

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| naive vs aware | 不带时区的 `datetime` 不能安全比较 | `[Z1]` |
| `datetime.now()` 无时区 | 用 `now(timezone.utc)` | `[Z1]` |
| `strftime` 平台差异 | `%Y` 安全，`%e` 不通用 | `[Z1]` |
| 存数据库用 ISO 字符串 | 可排序、无歧义 | `[Z1]` |

### 4.4 `decimal`（详见第 5 节）

```python
from decimal import Decimal

print(0.1 + 0.2)                                        # 0.30000000000000004（实测）
print(Decimal("0.1") + Decimal("0.2"))                  # 0.3（实测）
print(Decimal("1.10") * 3)                              # 3.30（实测）
```

### 4.5 `collections`

```python
import collections

counts = collections.Counter("aabbbc")
print(counts.most_common(2), counts["a"])               # [('b', 3), ('a', 2)] 2（实测）

queue = collections.deque([1, 2, 3], maxlen=3)
queue.append(4)
print(list(queue), queue.popleft())                     # [2, 3, 4] 2（实测）

grouped = collections.defaultdict(list)
for key, value in [("a", 1), ("a", 2), ("b", 3)]:
    grouped[key].append(value)
print(dict(grouped))                                    # {'a': [1, 2], 'b': [3]}（实测）

Record = collections.namedtuple("Record", "name hits")
print(Record("search", 2)._asdict())                    # {'name': 'search', 'hits': 2}（实测）

chain = collections.ChainMap({"env": "dev"}, {"env": "prod", "debug": "1"})
print(chain["env"], list(chain))                        # dev ['env', 'debug']（实测）
```

| 类型 | 何时用 | 依据 |
| --- | --- | --- |
| `Counter` | 计数、Top-N | `[Z7]` |
| `deque` | 队列、滑动窗口（两端 O(1)） | `[Z7]` |
| `defaultdict` | 分组、累加 | `[Z7]` |
| `OrderedDict` | 需要 `move_to_end` 等显式顺序操作 | `[Z7]` |
| `namedtuple` | 轻量不可变记录 | `[Z7]` |
| `ChainMap` | 多层配置覆盖 | `[Z7]` |

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| `deque(maxlen=3)` 会丢最左 | 实测 `[1,2,3]` 变 `[2,3,4]` | `[Z7]` |
| `defaultdict` 读不存在的键会创建 | 用 `in` 先判断 | `[Z7]` |
| `Counter` 缺失键返回 0 | 不报 `KeyError` | `[Z7]` |
| `namedtuple` 不可变 | 要改就用 `_replace` | `[Z7]` |

### 4.6 `itertools` / `functools`

```python
import functools, itertools

print(list(itertools.islice(itertools.count(5, 5), 3)))     # [5, 10, 15]（实测）
print(list(itertools.chain("ab", [1])))                      # ['a', 'b', 1]（实测）
print([(k, len(list(g))) for k, g in itertools.groupby("aabbbc")])
# [('a', 2), ('b', 3), ('c', 1)]（实测）


@functools.lru_cache(maxsize=2)
def slow(value):
    return value * 2

print(slow(2), slow(2), slow.cache_info().hits)             # 4 4 1（实测）
print(functools.partial(int, base=2)("1010"))                # 10（实测）
```

| 工具 | 用途 | 依据 |
| --- | --- | --- |
| `functools.cache` | 无上限缓存（比 `lru_cache` 简单） | `[Z3]` |
| `functools.lru_cache(maxsize=n)` | 有界缓存 | `[Z3]` |
| `functools.partial` | 预绑定参数 | `[Z3]` |
| `functools.reduce` | 累积（可读性差，慎用） | `[Z3]` |
| `functools.wraps` | 装饰器保签名（13 章） | `[Z3]` |

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| `cache` 要求参数可哈希 | `list` 参数报错 | `[Z3]` |
| 缓存会持有对象 | 内存增长 | `[Z3]` |
| `partial(int, base=2)` | 关键字绑定 | `[Z3]` |
| `groupby` 只合并相邻 | 先排序 | 17 章 |

### 4.7 `re`

```python
import re

print(re.findall(r"\d+", "a1b22c333"))                  # ['1', '22', '333']（实测）
print(re.sub(r"\s+", " ", " a  b ").strip())            # a b（实测）
```

| 函数 | 用途 | 依据 |
| --- | --- | --- |
| `re.search` | 找第一个 | `[Z1]` |
| `re.match` | 从开头匹配 | `[Z1]` |
| `re.fullmatch` | 整串匹配 | `[Z1]` |
| `re.findall` | 所有匹配（含分组时返回分组） | `[Z1]` |
| `re.sub` | 替换 | `[Z1]` |
| `re.compile` | 复用模式（循环里必做） | `[Z1]` |

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| 用 `re.match` 当 `fullmatch` | 只匹配开头 | `[Z1]` |
| 循环里反复编译 | 慢，用 `compile` | `[Z1]` |
| 字符串里有反斜杠 | 用原始字符串 `r"..."` | `[Z1]` |
| 贪婪匹配 | 用 `*?` / `+?` | `[Z1]` |
| 用正则解析 HTML/JSON | 不可靠，用专门解析器 | `[Z1]` |

### 4.8 `logging`

```python
import logging, sys

logging.basicConfig(
    level=logging.INFO,
    format="LOG %(levelname)s %(message)s",
    stream=sys.stderr,
)
logging.getLogger("demo").info("stdlib logging to stderr")
```

实测：日志写到 **stderr**（`LOG INFO stdlib logging to stderr`），不污染 stdout。

| 级别 | 用途 | 依据 |
| --- | --- | --- |
| `DEBUG` | 排查细节 | `[Z1]` |
| `INFO` | 正常事件 | `[Z1]` |
| `WARNING` | 异常但可继续（默认级别） | `[Z1]` |
| `ERROR` | 功能失败 | `[Z1]` |
| `CRITICAL` | 进程无法继续 | `[Z1]` |

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| 用 `print` 代替日志 | 无级别、无法关闭 | `[Z1]` |
| 日志里打印敏感数据 | 泄露 | `[Z4]` |
| `basicConfig` 调多次 | 只有第一次生效 | `[Z1]` |
| `logger.exception` 用在 `except` 外 | 无堆栈 | `[Z1]` |
| 日志写 stdout | 污染数据输出 | `[Z1]` |

### 4.9 `os` / `sys`

```python
import os, sys

print(os.name, os.path.join("a", "b"))                  # nt a\b（实测）
print(os.environ.get("USERPROFILE") is not None)         # True（实测）
print(sys.platform, sys.path[0] or ".")                 # win32 .（实测）
```

| 用途 | 模块 | 依据 |
| --- | --- | --- |
| 环境变量 | `os.environ` | `[Z1]` |
| 路径拼接 | `pathlib` 优先，`os.path` 次选 | `[Z5]` |
| 命令行参数 | `sys.argv` | `[Z6]` |
| 退出 | `sys.exit(code)` / `raise SystemExit` | `[Z6]` |
| 搜索路径 | `sys.path`（21 章） | `[Z6]` |
| 标准流 | `sys.stdin/stdout/stderr` | `[Z6]` |

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| `os.environ["KEY"]` 缺失报 `KeyError` | 用 `.get` | `[Z1]` |
| 改 `os.environ` 只影响本进程 | 不持久 | `[Z1]` |
| `sys.exit()` 在库代码里 | 调用方被终止 | `[Z6]` |
| Windows 下 `os.environ` 大小写不敏感 | 与 Linux 不同 | `[Z1]` |

### 4.10 `subprocess`

```python
import subprocess, sys

result = subprocess.run([sys.executable, "--version"], capture_output=True, text=True)
print(result.stdout.strip())        # Python 3.12.8（实测）
```

| 参数 | 作用 | 依据 |
| --- | --- | --- |
| `capture_output=True` | 捕获 stdout/stderr | `[Z1]` |
| `text=True` | 返回 `str` | `[Z1]` |
| `check=True` | 非零退出抛 `CalledProcessError` | `[Z1]` |
| `timeout=` | 超时抛 `TimeoutExpired` | `[Z1]` |
| `shell=True` | 走 shell（**命令注入风险**） | `[Z1]` |

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| `shell=True` + 用户输入 | 命令注入 | `[Z1]` |
| 不设 `timeout` | 卡死 | `[Z1]` |
| 忽略 `returncode` | 失败被当成功 | `[Z1]` |
| 用 `os.system` | 无法捕获输出 | `[Z1]` |

### 4.11 `sqlite3`

```python
import sqlite3

connection = sqlite3.connect(":memory:")
connection.execute("CREATE TABLE tool (name TEXT, hits INT)")
connection.execute("INSERT INTO tool VALUES (?, ?)", ("search", 2))
print(connection.execute("SELECT name, hits FROM tool").fetchall())
# [('search', 2)]（实测）
print(sqlite3.sqlite_version.split(".")[0])              # 3（实测）
connection.close()
```

| 要点 | 说明 | 依据 |
| --- | --- | --- |
| 参数化用 `?` | 防 SQL 注入 | `[Z1]` |
| `commit()` 或 `with connection:` | 事务 | `[Z1]` |
| `row_factory = sqlite3.Row` | 按列名取值 | `[Z1]` |
| 连接要 `close()` | 或用上下文管理器 | `[Z1]` |

### 4.12 `hashlib` / `secrets` / `uuid`

```python
import base64, hashlib, secrets, uuid

print(hashlib.sha256(b"abc").hexdigest()[:16])           # ba7816bf8f01cfea（实测）
print(base64.b64encode(b"abc").decode())                 # YWJj（实测）
print(len(secrets.token_hex(8)), len(secrets.token_urlsafe(8)))   # 16 11（实测）
print(uuid.uuid5(uuid.NAMESPACE_DNS, "example.com"))
# cfbff0d1-9375-5685-968c-48ce8b15ae17（实测）
```

| 用途 | 用 | 依据 |
| --- | --- | --- |
| 校验文件完整性 | `hashlib.sha256` | `[Z1]` |
| 存密码 | `hashlib.scrypt` / `bcrypt`（第三方） | `[Z1]` |
| 生成令牌 | `secrets`（不是 `random`） | `[Z1]` |
| 稳定 ID | `uuid.uuid5` | `[Z1]` |
| 随机 ID | `uuid.uuid4` | `[Z1]` |

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| 用 `random` 生成令牌 | 可预测 | `[Z1]` |
| MD5/SHA1 用于安全场景 | 已不安全 | `[Z1]` |
| `hashlib.md5` 传 `str` | 需先 `encode` | `[Z1]` |
| 直接用 SHA256 存密码 | 无盐、无迭代 | `[Z1]` |

### 4.13 其他常用（速查）

```python
import copy, enum, math, pprint, statistics, struct, textwrap

print(math.isclose(0.1 + 0.2, 0.3), math.gcd(12, 18))    # True 6（实测）
print(statistics.mean([1, 2, 3]), statistics.median([1, 3, 2]))   # 2 2（实测）
print(textwrap.shorten("a b c d e f", width=7))          # a [...]（实测）
print(pprint.pformat({"b": 1, "a": [1, 2]}, width=20).replace("\n", "|"))
# {'a': [1, 2],| 'b': 1}（实测）
print(struct.unpack("<i", struct.pack("<i", 42))[0])     # 42（实测）

original = {"tags": ["a"]}
shallow = copy.copy(original)
deep = copy.deepcopy(original)
original["tags"].append("b")
print(shallow["tags"], deep["tags"])                     # ['a', 'b'] ['a']（实测）


class Level(enum.IntEnum):
    LOW = 1
    HIGH = 2


print(Level.HIGH.value, Level(1).name, isinstance(Level.LOW, int))   # 2 LOW True（实测）
```

| 需求 | 模块 | 依据 |
| --- | --- | --- |
| 数值近似比较 | `math.isclose` | `[Z1]` |
| 统计量 | `statistics` | `[Z1]` |
| 文本缩进/截断 | `textwrap` | `[Z1]` |
| 结构化打印 | `pprint` | `[Z1]` |
| 二进制协议 | `struct` | `[Z1]` |
| 深拷贝 | `copy.deepcopy` | `[Z1]` |
| 枚举 | `enum` | `[Z1]` |
| 数据类 | `dataclasses` | `[Z1]` |
| 命令行 | `argparse` | `[Z1]` |
| 临时目录 | `tempfile.TemporaryDirectory` | `[Z1]` |
| 文件匹配 | `glob` / `shutil.which` | `[Z1]` |

## 5. 深挖 `decimal`：为什么金额不能用 `float`

### 5.1 浮点的本质问题

```python
print(0.1 + 0.2)                    # 0.30000000000000004（实测）
print(0.1 + 0.2 == 0.3)             # False（实测）
print(Decimal("0.1") + Decimal("0.2") == Decimal("0.3"))   # True（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `float` 是二进制浮点 | 0.1 无法精确表示 | `[Z8]` |
| 误差会累积 | 求和/比较出错 | `[Z8]` |
| `Decimal` 是十进制 | 精确表示十进制小数 | `[Z8]` |

### 5.2 构造方式决定精度

```python
from decimal import Decimal

print(Decimal(0.1))
# 0.1000000000000000055511151231257827021181583404541015625（实测）
print(Decimal("0.1"))               # 0.1（实测）
```

| 写法 | 结果 | 依据 |
| --- | --- | --- |
| `Decimal("0.1")` | ✅ 精确 | `[Z8]` |
| `Decimal(0.1)` | ❌ 把浮点误差带进来 | `[Z8]` |
| `Decimal(str(0.1))` | ✅ 可用 | `[Z8]` |
| `Decimal(1)` | ✅ 整数 | `[Z8]` |

> 注意：`Decimal(float)` 是明确的陷阱——你以为是「转成十进制」，实际是把浮点的二进制误差原样搬进来。**永远用字符串或整数构造**。`[Z8]`

### 5.3 精度与舍入

```python
from decimal import Decimal, ROUND_HALF_UP, getcontext

print(Decimal(1) / Decimal(3))      # 0.3333333333333333333333333333（实测）
print(getcontext().prec)             # 28（实测）
print(Decimal("1.005").quantize(Decimal("0.01")))                        # 1.00（实测）
print(Decimal("1.005").quantize(Decimal("0.01"), rounding=ROUND_HALF_UP))  # 1.01（实测）
```

| 概念 | 默认 | 依据 |
| --- | --- | --- |
| 精度 `prec` | 28 位有效数字 | `[Z8]` |
| 舍入模式 | `ROUND_HALF_EVEN`（银行家舍入） | `[Z8]` |
| 金额舍入 | 显式指定 `ROUND_HALF_UP` | `[Z8]` |

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| 默认银行家舍入 | `1.005` → `1.00` 而非 `1.01` | `[Z8]` |
| 用 `round()` 处理金额 | 同样是浮点问题 | `[Z8]` |
| `quantize` 不指定舍入 | 财务对账会差一分 | `[Z8]` |
| 混用 `float` 与 `Decimal` | `TypeError` | `[Z8]` |

```python
# 金额计算的推荐写法
def to_money(value: str) -> Decimal:
    return Decimal(value).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)


def total(values: list[str]) -> Decimal:
    return sum((Decimal(value) for value in values), Decimal("0")).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
```

### 5.4 `decimal` 的代价

| 维度 | `float` | `Decimal` |
| --- | --- | --- |
| 速度 | 快（硬件） | 慢（软件模拟） |
| 内存 | 小 | 大 |
| 精确性 | 二进制近似 | 十进制精确 |
| 适用 | 科学计算、图形 | 金额、计费、对账 |

> 注意：不要「全项目换 `Decimal`」——只在**需要十进制精确**的边界（金额、税率、账单）用，其余继续 `float`。`[Z8]`

## 6. 选型判断

| 需求 | 先用标准库 | 何时换第三方 | 依据 |
| --- | --- | --- | --- |
| 读配置 | `json` / `tomllib` / `configparser` | 复杂 schema 校验 → pydantic | `[Z1]` |
| 日期时区 | `datetime` + `zoneinfo` | 复杂重复规则 → dateutil | `[Z1]` |
| HTTP | `urllib.request` | 重试/连接池/异步 → httpx | 23 章 |
| 表格 | `csv` | 分析/聚合 → pandas | 23 章 |
| 命令行 | `argparse` | 子命令复杂 → click/typer | 23 章 |
| 日志 | `logging` | 结构化/采集 → structlog | 23 章 |
| 测试 | `unittest` | 更简洁 → pytest | 23 章 |
| 重试 | 手写循环 | 退避策略 → tenacity | 23 章 |

| 判断项 | 问自己 | 依据 |
| --- | --- | --- |
| 标准库能否 20 行内解决 | 能就别装 | `[Z4]` |
| 是否核心路径 | 核心更该用成熟库 | `[Z4]` |
| 团队是否熟悉 | 不熟就加学习成本 | `[Z4]` |
| 退出成本 | 换库要改多少处 | `[Z4]` |

## 7. 综合示例：配置 → 统计 → 日志

```python
"""第 22 章综合示例：pathlib + json + logging + Counter + Decimal。"""

import json
import logging
import pathlib
import tempfile
from collections import Counter
from decimal import Decimal

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


def build_report(records):
    counter = Counter(record["tool"] for record in records)
    cost = sum(Decimal(str(record["cost"])) for record in records)
    return {
        "counts": counter.most_common(),
        "cost": str(cost.quantize(Decimal("0.01"))),
        "total": len(records),
    }


with tempfile.TemporaryDirectory() as tmp:
    path = pathlib.Path(tmp) / "records.json"
    path.write_text(
        json.dumps(
            [
                {"tool": "search", "cost": 0.1},
                {"tool": "cache", "cost": 0.2},
                {"tool": "search", "cost": 0.1},
            ]
        ),
        encoding="utf-8",
    )
    records = json.loads(path.read_text(encoding="utf-8"))
    report = build_report(records)
    logging.info("report %s", report)
    print("REPORT", report)
    print("SUFFIX", path.suffix, "EXISTS", path.exists())
```

本机实测输出：

```text
REPORT {'counts': [('search', 2), ('cache', 1)], 'cost': '0.40', 'total': 3}
SUFFIX .json EXISTS True

INFO report {'counts': [('search', 2), ('cache', 1)], 'cost': '0.40', 'total': 3}   ← stderr
```

**逐段说明**：

| 代码 | 用到的机制 | 依据 |
| --- | --- | --- |
| `TemporaryDirectory` | 自动清理 | `[Z1]` |
| `pathlib.Path / "records.json"` | 路径拼接 | `[Z5]` |
| `write_text(..., encoding="utf-8")` | 显式编码 | `[Z5]` |
| `json.dumps/loads` | 序列化 | `[Z6]` |
| `Counter(...).most_common()` | 计数排行 | `[Z7]` |
| `Decimal(str(...))` | 金额精确累加 | `[Z8]` |
| `quantize(Decimal("0.01"))` | 保留两位 | `[Z8]` |
| `logging.info` | 写 stderr | `[Z1]` |

> 注意：`Decimal(str(record["cost"]))` 里的 `str()` 是必需的——JSON 解析出来的 `cost` 是 `float`，直接 `Decimal(float)` 会把误差带进来。`[Z8]`

## 8. 注意事项与新手错误对照表

| 错误写法 / 操作 | 报错或现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| `0.1 + 0.2 == 0.3` | `False` | `math.isclose` 或 `Decimal` | `[Z8]` |
| 金额用 `float` | 累加差几分 | `Decimal(str(x))` | `[Z8]` |
| `Decimal(0.1)` | 带浮点长尾 | `Decimal("0.1")` | `[Z8]` |
| 金额默认舍入 | `1.005` → `1.00` | `ROUND_HALF_UP` | `[Z8]` |
| `read_text()` 不给 `encoding` | Windows 下 GBK 乱码 | `encoding="utf-8"` | `[Z5]` |
| `Path("a") + "b"` | `TypeError` | `Path("a") / "b"` | `[Z5]` |
| `pathlib` 与 `os.path` 混用 | 风格割裂、难维护 | 统一 `pathlib` | `[Z5]` |
| `json.dumps` 中文变 `\uXXXX` | 不可读 | `ensure_ascii=False` | `[Z6]` |
| `json.dump` 传 `datetime` | `TypeError` | `default=str` 或自定义 | `[Z6]` |
| `json.load(f)` 传字符串 | `AttributeError` | `json.loads(str)` | `[Z6]` |
| `csv` 读出来的数字 | 是 `str`（实测 `'2'`） | 手动 `int()` | `[Z1]` |
| `csv` 读写不给 `newline=""` | 空行/换行错乱 | `open(..., newline="")` | `[Z1]` |
| `deque(maxlen=n)` 以为不丢 | 自动丢头（实测） | 确认容量 | `[Z7]` |
| `defaultdict` 读不存在的键 | 创建默认值 | `in` 判断 | `[Z7]` |
| `groupby` 前不排序 | 同名分组多个 | 先 `sorted` | `[Z7]` |
| `re.match` 当整串匹配 | 只匹配开头 | `fullmatch` | `[Z1]` |
| 循环里 `re.match(pattern)` | 反复编译 | `re.compile` | `[Z1]` |
| 正则解析 HTML | 脆弱 | `html.parser` | `[Z1]` |
| 用 `print` 当日志 | 无级别、无法关闭 | `logging` | `[Z1]` |
| 日志写 stdout | 污染数据 | `stream=sys.stderr` | `[Z1]` |
| `basicConfig` 多次调用 | 只有第一次生效 | 配置一次 | `[Z1]` |
| 日志打印令牌/密码 | 泄露 | 脱敏 | `[Z4]` |
| `os.environ["KEY"]` | 缺失报 `KeyError` | `os.environ.get` | `[Z1]` |
| 库代码里 `sys.exit()` | 调用方被终止 | 抛异常/返回码 | `[Z6]` |
| `subprocess(shell=True)` 拼用户输入 | 命令注入 | 列表参数 + 不用 shell | `[Z1]` |
| `subprocess` 不设 `timeout` | 卡死 | `timeout=30` | `[Z1]` |
| `subprocess` 不看 `returncode` | 失败当成功 | `check=True` | `[Z1]` |
| 用 `os.system` | 拿不到输出 | `subprocess.run` | `[Z1]` |
| `sqlite3` 字符串拼 SQL | 注入 | `?` 参数化 | `[Z1]` |
| `sqlite3` 不 `commit` | 数据丢失 | `with conn:` / `commit()` | `[Z1]` |
| 用 `random` 生成令牌 | 可预测 | `secrets` | `[Z1]` |
| SHA256 直接存密码 | 无盐无迭代 | `scrypt`/`bcrypt` | `[Z1]` |
| `hashlib.md5("abc")` | `TypeError` | `"abc".encode()` | `[Z1]` |
| `datetime.now()` 当 UTC | 时区错乱 | `now(timezone.utc)` | `[Z1]` |
| naive 与 aware 相减 | `TypeError` | 统一带时区 | `[Z1]` |
| `copy.copy` 当深拷贝 | 嵌套对象共享（实测） | `deepcopy` | `[Z1]` |
| `pickle.loads` 不可信数据 | 任意代码执行 | 用 `json` | `[Z1]` |
| `tempfile` 手写临时名 | 冲突/不安全 | `TemporaryDirectory` | `[Z1]` |
| `glob` 递归忘记 `**` | 只扫一层 | `rglob` / `**` | `[Z1]` |
| 用 `sys.stdlib_module_names` 判第三方 | 会误判 | 对比 `site-packages` | `[Z6]` |

## 9. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 先查标准库再装包 | 不造轮子 | `[Z4]` |
| 路径一律 `pathlib` | 跨平台、可读 | `[Z5]` |
| 文本 I/O 必给 `encoding` | 避免平台默认 | `[Z5]` |
| 金额用 `Decimal` + 显式舍入 | 精确对账 | `[Z8]` |
| 计数用 `Counter`、队列用 `deque` | 别手写 | `[Z7]` |
| 缓存用 `functools.cache` | 注明失效条件 | `[Z3]` |
| 日志分级 + 脱敏 + stderr | 可观测 | `[Z1]` |
| 外部命令用列表参数 + `timeout` | 防注入、防卡死 | `[Z1]` |
| SQL 全参数化 | 防注入 | `[Z1]` |
| 随机令牌用 `secrets` | 密码学安全 | `[Z1]` |
| 版本特性查手册 | 别凭记忆 | `[Z1]` |
| import 分组（标准库/第三方/本地） | 可读 | `[Z4]` |

**风格示范**：

```python
"""records 模块：读取记录并汇总。

为什么用 Decimal：金额累加不能用 float。
"""

from __future__ import annotations

import json
import logging
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

logger = logging.getLogger(__name__)
CENT = Decimal("0.01")


def load_records(path: Path) -> list[dict]:
    """读取 JSON 记录，失败时抛出 JSONDecodeError。"""
    logger.debug("loading %s", path)
    return json.loads(path.read_text(encoding="utf-8"))


def total_cost(records: list[dict]) -> Decimal:
    """累加金额，按分四舍五入。"""
    amount = sum((Decimal(str(item["cost"])) for item in records), Decimal("0"))
    return amount.quantize(CENT, rounding=ROUND_HALF_UP)
```

**边界**：

- 标准库的 `sqlite3`、`csv`、`json` 都不做业务校验，外部数据必须自己校验。
- `pickle`、`marshal` 不能处理不可信输入（反序列化可执行任意代码）。
- 跨版本兼容要查 `sys.version_info`，不要假设新特性存在。

## 10. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[Z1]` | python.org | https://docs.python.org/3.12/library/index.html | 标准库总览与按功能分类、各模块归属、版本与平台差异 |
| `[Z2]` | python.org | https://docs.python.org/3.12/tutorial/datastructures.html | `deque` 用于队列、`Counter` 类需求动机 |
| `[Z3]` | python.org | https://docs.python.org/3.12/library/functools.html | `cache` / `lru_cache` / `partial` / `wraps` / `reduce` |
| `[Z4]` | PEP 官方 | https://peps.python.org/pep-0008/ | import 分组、命名与注释约定 |
| `[Z5]` | python.org | https://docs.python.org/3.12/library/pathlib.html | `Path` 拼接/后缀/读写/`glob` |
| `[Z6]` | python.org | https://docs.python.org/3.12/library/json.html | `dumps` / `loads` / `ensure_ascii` / `default` |
| `[Z7]` | python.org | https://docs.python.org/3.12/library/collections.html | `Counter` / `deque` / `defaultdict` / `namedtuple` / `ChainMap` |
| `[Z8]` | python.org | https://docs.python.org/3.12/library/decimal.html | `Decimal` 构造、精度、量化与舍入模式 |

> **核对状态**：`[Z1]` `[Z2]` `[Z4]` 与本章 `README.md` 已核对来源一致；其余按 `docs.python.org/3.12` 官方结构整理，**本次未逐页直连复核**。文中「实测」结论为本机 Python 3.12.8 运行结果；数量类结论（301 / 158）随版本与构建选项变化。

## 11. 毕业自查清单

**能说清（概念层）**：

- [ ] 标准库的三层结构（内置 API / 内置模块 / 标准库）
- [ ] 官方手册两个入口分别何时用
- [ ] 标准库与第三方库的边界怎么判断
- [ ] `float` 为什么不能算钱、`Decimal` 为什么可以
- [ ] `Decimal(float)` 为什么危险
- [ ] `deque` 为什么比 `list` 适合队列
- [ ] `json` 的 `ensure_ascii` 影响什么
- [ ] `csv` 读出来的数字为什么是字符串
- [ ] 日志为什么要写 stderr

**能写出（代码层）**：

- [ ] `pathlib` 建目录/读文件/`glob`（含 `encoding`）
- [ ] `json` 中文安全序列化 + 文件读写
- [ ] `Decimal` 金额累加 + `quantize` + `ROUND_HALF_UP`
- [ ] `Counter` Top-N + `deque(maxlen)` + `defaultdict` 分组
- [ ] `functools.cache` 缓存 + `partial`
- [ ] `logging` 配置到 stderr + 分级
- [ ] `subprocess.run` 带 `capture_output` / `text` / `timeout`
- [ ] `sqlite3` 参数化查询 + 事务

**能判断（避坑层）**：

- [ ] 看到 `0.1 + 0.2 == 0.3` 能指出浮点问题
- [ ] 看到 `Decimal(0.1)` 能指出长尾
- [ ] 看到 `read_text()` 无编码能指出 Windows 乱码
- [ ] 看到 `deque(maxlen=)` 能指出会丢数据
- [ ] 看到 `re.match` 当整串匹配能指出只匹配开头
- [ ] 看到 `shell=True` 拼用户输入能指出注入
- [ ] 看到 `pickle.loads` 外部数据能指出反序列化风险

**能跑通（验收层）**：

- [ ] 运行 `examples/stdlib_demo.py` 并解释输出
- [ ] 把第 7 节示例存成文件运行，输出与文档一致
- [ ] 在 REPL 对比 `float` 与 `Decimal` 的求和结果
- [ ] 用 `sys.stdlib_module_names` 判断某模块是否标准库

## 12. 下一章衔接

第 23 章 `第三方库`：标准库不够用时怎么选、怎么装、怎么锁版本——`pip`、镜像、`requirements.txt`、虚拟环境与供应链风险。

本章留下的伏笔：

1. `importlib.metadata` 是标准库，第 23 章用它做只读依赖审计。
2. `venv` / `ensurepip` 同属标准库，第 23 章的虚拟环境正是它们实现。
3. `sqlite3` / `csv` / `json` 的边界校验责任，在第 23 章选型时会变成「要不要引入 pydantic」的决策。