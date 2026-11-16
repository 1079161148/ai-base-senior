# 21 模块化 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把截图里的「包/模块/成员关系、定义模块（导出）、导入模块、包、相对导入、搜索路径、循环导入」逐条展开，并补上命名空间包、`importlib`、`__pycache__`、`-m` 与直接运行的差异，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 实测） |
| 前置 | 第 02、20 章（环境、类型标注） |
| 覆盖范围 | 模块/包/成员模型、`__all__` 与私有约定、`__name__`、`import` 五步与 `sys.modules`、动态导入与 `reload`、`__init__.py`、相对导入、`sys.path`、循环导入、命名空间包 |
| 明确不覆盖 | 打包与发布（第 29/30 章）、可编辑安装、`pyproject.toml` 打包配置、命名空间包的分布式用法 |
| 学完验收 | 能说清 `import` 的执行步骤、能解释 `if __name__ == "__main__"`、能判断循环导入怎么修（见第 12 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Un]` `` 指向第 11 节官方链接；标「实测」的是本机 Python 3.12.8 在临时目录中运行的结果（实测用的临时包已清理）。

**推荐顺序**：

```text
1 包/模块/成员（第 1 节）    → 三层模型
2 定义模块（第 2 节）        → 导出、私有、__name__
3 导入模块（第 3 节）        → import 五步 + 缓存 + 动态导入
4 包（第 4 节）              → __init__.py 与元数据
5 相对导入（第 5 节）        → 什么时候能用
6 搜索路径（第 6 节）        → sys.path 构成
7 循环导入（第 7 节）        → 表现与修法
8 综合示例（第 8 节）
9 注意事项（第 9 节）        → 41 条错误对照
```

**与 README 的分工**：README 给结论与边界，本文件负责机制细节与实测证据。冲突时以本文件为准。

## 1. 包、模块、成员关系

### 1.1 三层模型

```text
包 package（目录，通常含 __init__.py）
├── 模块 module_a.py          ← 一个 .py 文件
│   ├── 成员 1（函数 / 类 / 变量）
│   ├── 成员 2
│   └── _私有成员
├── 模块 module_b.py
│   └── ...
└── 子包 subpackage/
    ├── __init__.py
    └── 模块 module_c.py
```

| 概念 | 定义 | 例子 | 依据 |
| --- | --- | --- | --- |
| 模块 | 一个 `.py` 文件（或扩展模块） | `app/util.py` | `[U1]` |
| 包 | 含 `__init__.py` 的目录 | `app/` | `[U1]` |
| 子包 | 包内的包 | `app/sub/` | `[U1]` |
| 成员 | 模块顶层定义的名字 | 函数、类、常量 | `[U1]` |
| 命名空间包 | 无 `__init__.py` 的目录 | `nspkg/` | `[U5]` |

### 1.2 一个模块就是一个命名空间

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 模块有自己的 `__dict__` | 所有成员都在里面 | `[U1]` |
| 模块名是 `__name__` | `app.util` | `[U1]` |
| 模块对象可当字典用 | `vars(module)` | `[U1]` |

```python
import app.util as util
print(sorted(k for k in vars(util) if not k.startswith("__")))
# ['helper']（实测）
```

### 1.3 包与模块的层级约束

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 包名即目录名 | 大小写敏感（Linux） | `[U1]` |
| 模块名即文件名（去掉 `.py`） | 不能含 `-` | `[U3]` |
| 包内模块不能与包同名 | 否则导入歧义 | `[U1]` |
| 目录里可以有非 `.py` 文件 | 但不可导入 | `[U1]` |

> 注意：模块名要能作为标识符，所以 `my-tool.py` 无法导入；文件名用下划线或小驼峰之外的短名（PEP 8 要求全小写）。`[U3]`

## 2. 定义模块（导出）

### 2.1 模块顶层就是「公开区」

```python
# app/config.py
print("CONFIG_EXEC")
_PREFIX = "internal"
__all__ = ["PUBLIC"]
PUBLIC = "ok"
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 顶层代码在导入时执行 | 包括 `print`、赋值、函数定义 | `[U1]` |
| 函数/类定义也是执行 | 创建对象并绑定名字 | `[U1]` |
| 私有只是约定 | 下划线开头不强制 | `[U3]` |

### 2.2 私有成员约定

```python
import app.config as config
print(config._PREFIX, config.PUBLIC)
# PRIVATE internal ok（实测）
```

| 写法 | 含义 | 是否真的私有 | 依据 |
| --- | --- | --- | --- |
| `_name` | 模块内部使用 | ❌ 仍可访问 | `[U3]` |
| `__name` | 类内名称改写，模块级无特殊含义 | ❌ | `[U3]` |
| `__all__` 里不列 | `import *` 不导出 | ✅ 仅对 `*` 有效 | `[U3]` |

> 注意：Python 没有模块级强制私有。想真正隐藏，把它放进函数内部，或用 `__all__` + 团队约定。`[U3]`

### 2.3 `__all__` 控制导出清单

```python
# app/config.py
__all__ = ["PUBLIC"]

# 另一个进程里
from app.config import *
print(sorted(k for k in dir() if not k.startswith("_")))
# STAR ['PUBLIC']（实测）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `__all__` 只影响 `from m import *` | 不影响 `import m` | `[U3]` |
| 不写 `__all__` 时 | `import *` 导出所有非下划线名 | `[U3]` |
| `__all__` 可以是任意可迭代 | 通常是 `list[str]` | `[U3]` |
| 名称写错不报错 | 只是少导出 | `[U3]` |

| 场景 | 建议 | 依据 |
| --- | --- | --- |
| 库的公共 API | 必须写 `__all__` | `[U3]` |
| 应用内部模块 | 可选 | `[U3]` |
| 想让某名字可见但不算 API | 不列进 `__all__` | `[U3]` |

### 2.4 `__name__` 与直接运行

```python
# app/util.py
print("UTIL_EXEC", __name__)
```

两种执行方式，`__name__` 不同：

```powershell
python app/util.py       # UTIL_EXEC __main__（实测）
python -c "import app.util"   # UTIL_EXEC app.util（实测）
```

| 执行方式 | `__name__` | 依据 |
| --- | --- | --- |
| `python app/util.py` | `"__main__"` | `[U1]` |
| `python -m app.util` | `"__main__"` | `[U1]` |
| `import app.util` | `"app.util"` | `[U1]` |
| 被其他模块导入 | 模块全名 | `[U1]` |

### 2.5 `if __name__ == "__main__":` 保护

```python
def main() -> int:
    print("run")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

| 作用 | 说明 | 依据 |
| --- | --- | --- |
| 导入时不执行入口逻辑 | 只定义函数/类 | `[U1]` |
| 可被测试直接调用 `main()` | 不必起子进程 | `[U1]` |
| `raise SystemExit(main())` | 把返回值当退出码 | `[U1]` |

| 反例 | 后果 | 依据 |
| --- | --- | --- |
| 顶层直接 `print` / 发请求 | 一导入就执行 | `[U1]` |
| 顶层读文件 | 导入即 I/O | `[U1]` |
| 顶层 `sys.exit()` | 导入方被终止 | `[U1]` |

> 注意：入口保护不只是「规范」，它是模块可测试、可复用的前提；顶层有副作用会让 `import` 变成一次隐式执行。`[U1]`

## 3. 导入模块

### 3.1 三种导入形式

| 写法 | 绑定什么 | 依据 |
| --- | --- | --- |
| `import app.util` | 绑定 `app`（顶层包名） | `[U1]` |
| `import app.util as util` | 绑定 `util` | `[U1]` |
| `from app.util import helper` | 绑定 `helper` | `[U1]` |
| `from app.util import helper as h` | 绑定 `h` | `[U1]` |
| `from . import util` | 包内相对导入 | `[U1]` |

```python
import app.util                     # 用 app.util.helper()
import app.util as util             # 用 util.helper()
from app.util import helper          # 用 helper()
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `import a.b` 后本地只有 `a` | 要访问 `a.b` | `[U1]` |
| `from x import y` 是「取名字」 | 不是复制值 | `[U1]` |
| 导入后再绑定新值是本地副本 | 不影响源模块 | `[U1]` |

> 注意：`from m import x` 之后给 `x` 重新赋值，改的是当前模块的名字；原模块的 `m.x` 不变。这是「可变对象共享、名字不共享」的典型表现。`[U1]`

### 3.2 `import` 到底做了什么

```text
1. 查 sys.modules 缓存         → 命中则直接返回
2. 在 sys.path 中找模块/包      → 找不到抛 ModuleNotFoundError
3. 创建模块对象（含 __name__ 等）
4. 执行模块顶层代码            → 执行期间加入 sys.modules
5. 绑定名字到当前命名空间
```

| 步骤 | 关键点 | 依据 |
| --- | --- | --- |
| 1 | 缓存优先，第二次导入不再执行 | `[U2]` |
| 2 | 搜索路径来自 `sys.path` | `[U2]` |
| 3 | 模块对象先建好再执行 | `[U2]` |
| 4 | 执行期间已进缓存（循环导入因此能拿到半成品） | `[U2]` |
| 5 | 失败时从 `sys.modules` 移除 | `[U2]` |

### 3.3 模块只执行一次

```python
import app.util, app.util, sys
print("MODULES", "app.util" in sys.modules)
```

实测输出：

```text
APP_INIT app
UTIL_EXEC app.util
MODULES True
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 第二次导入不执行 | 直接取缓存 | `[U2]` |
| 同一进程内模块是单例 | `a is b` 为真 | `[U2]` |
| 模块级状态因此全进程共享 | 可变全局要谨慎 | `[U2]` |

```python
import app.util as a
import importlib
b = importlib.import_module("app.util")
print(a is b)    # True（实测）
```

### 3.4 动态导入

```python
import importlib

module = importlib.import_module("app.sub.deep")
print(module.__name__)     # app.sub.deep（实测）
```

| 方式 | 用法 | 依据 |
| --- | --- | --- |
| `importlib.import_module(name)` | 运行时按字符串导入 | `[U4]` |
| `__import__(name)` | 老 API，返回顶层包 | `[U4]` |
| `importlib.util.find_spec(name)` | 只查存在性，不导入 | `[U4]` |
| `importlib.metadata.version(name)` | 查已安装包版本（23 章） | `[U4]` |

```python
# 按插件名加载
import importlib

PLUGINS = {"cache": "plugins.cache", "search": "plugins.search"}
plugin = importlib.import_module(PLUGINS[name])
```

| 风险 | 说明 | 依据 |
| --- | --- | --- |
| 用户可控字符串 | 任意模块加载 | `[U4]` |
| 失败类型多 | `ModuleNotFoundError` / `AttributeError` | `[U4]` |
| 静态检查器看不见 | 类型推断失效 | 20 章 |

> 注意：动态导入的模块名如果来自用户输入，必须用白名单映射，不能直接 `import_module(用户输入)`。`[U4]`

### 3.5 `reload`：重载会重新执行

```python
import importlib
import app.util as util
importlib.reload(util)
```

实测输出：

```text
APP_INIT app
UTIL_EXEC app.util
UTIL_EXEC app.util      ← reload 又执行了一次
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `reload` 重新执行模块顶层 | 副作用会再来一次 | `[U4]` |
| 已有对象不会自动更新 | 旧引用仍是旧类 | `[U4]` |
| 只适合开发期 | 生产不要用 | `[U4]` |

### 3.6 导入的副作用清单

| 副作用 | 何时发生 | 依据 |
| --- | --- | --- |
| 顶层 `print` | 导入时 | `[U1]` |
| 顶层 I/O、网络 | 导入时 | `[U1]` |
| 注册表/单例初始化 | 导入时 | `[U1]` |
| 修改 `sys.path` | 导入时（极坏） | `[U3]` |
| 启动线程/任务 | 导入时（极坏） | `[U3]` |

> 注意：判断「这个模块能安全导入吗」的标准是：**导入是否只做定义，不做动作**。做不到就说明该重构。`[U3]`

## 4. 包（Package）

### 4.1 `__init__.py` 的作用

```text
app/
├── __init__.py
├── config.py
├── util.py
└── sub/
    ├── __init__.py
    └── deep.py
```

| 作用 | 说明 | 依据 |
| --- | --- | --- |
| 标记为包（传统包） | 没有它就不是常规包 | `[U1]` |
| 包导入时执行 | 先于子模块 | `[U3]` |
| 可定义包级 API | `from .util import helper` | `[U1]` |
| 可设 `__all__` | 控制 `from app import *` | `[U3]` |

实测（`python -m app.main`）：

```text
APP_INIT app          ← 包 __init__ 先执行
UTIL_EXEC app.util
CONFIG_EXEC
MAIN __main__ helper ok
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 导入子模块必先执行父包 `__init__` | 实测顺序 | `[U2]` |
| `__init__` 里导入子模块会拖慢启动 | 且可能循环 | `[U1]` |
| 空 `__init__.py` 完全合法 | 只作标记 | `[U1]` |

> 注意：`__init__.py` 里写重逻辑（读配置、连数据库）会让「导入包」变成一次隐式初始化，且顺序不可控；保持它只做导出。`[U3]`

### 4.2 包的元数据

```python
import app
print(app.__path__, app.__package__, app.__spec__.name)
print(app.__file__.endswith("__init__.py"))
```

实测输出：

```text
['C:\\Users\\...\\py21demo_xxx\\app'] app app
True
```

| 属性 | 值 | 依据 |
| --- | --- | --- |
| `__path__` | 包内搜索路径（list） | `[U2]` |
| `__package__` | 包名 | `[U2]` |
| `__spec__.name` | 完整模块名 | `[U2]` |
| `__file__` | `__init__.py` 路径 | `[U2]` |

子模块的元数据：

```python
import app.util as util
print(util.__name__, util.__package__, util.__spec__.name)
# META app.util app app.util True（实测）
```

| 属性 | 子模块的值 | 依据 |
| --- | --- | --- |
| `__name__` | `app.util` | `[U2]` |
| `__package__` | `app`（所在包） | `[U2]` |
| `__spec__.name` | `app.util` | `[U2]` |

### 4.3 子包与导入链

```powershell
python -m app.sub.deep
```

实测输出：

```text
APP_INIT app
SUB_INIT
UTIL_EXEC app.util
DEEP helper
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 逐级执行父包 | `app` → `app.sub` → 模块 | `[U2]` |
| 相对导入 `..util` 可用 | 因为 `__package__` 是 `app.sub` | `[U1]` |

### 4.4 命名空间包（无 `__init__.py`）

```powershell
python -c "import nspkg; print(nspkg.__path__, nspkg.__file__)"
```

实测输出：

```text
_NamespacePath(['C:\\Users\\...\\py21demo_xxx\\nspkg']) None
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 没有 `__init__.py` 也能导入 | PEP 420 | `[U5]` |
| `__file__` 是 `None` | 没有实体文件 | `[U5]` |
| `__path__` 是 `_NamespacePath` | 可跨多个目录合并 | `[U5]` |
| 导入时不执行任何代码 | 无 `__init__` | `[U5]` |

| 场景 | 用普通包 | 用命名空间包 |
| --- | --- | --- |
| 单体应用 | ✅ | ❌ |
| 多发行版共享前缀 | ❌ | ✅ |
| 需要包级初始化 | ✅ | ❌ |
| 依据 | `[U1]` | `[U5]` |

> 注意：命名空间包适合「多个独立发行版共用一个顶层名」（如 `google.*`），普通应用不要用——它让「包到底在哪」变得不确定。`[U5]`

## 5. 相对导入

### 5.1 语法

| 写法 | 含义 | 依据 |
| --- | --- | --- |
| `from . import util` | 当前包的同级模块 | `[U1]` |
| `from .util import helper` | 当前包的同级模块的成员 | `[U1]` |
| `from .. import base` | 上一级包 | `[U1]` |
| `from ..base import helper` | 上一级包的成员 | `[U1]` |

```python
# app/main.py
from .util import helper
from . import config
print("MAIN", __name__, helper(), config.PUBLIC)
```

### 5.2 只能在包内使用

```powershell
python -m app.main        # 成功：MAIN __main__ helper ok（实测）
python app/main.py        # 失败（实测）
```

失败信息：

```text
ImportError: attempted relative import with no known parent package
```

| 执行方式 | `__package__` | 相对导入 | 依据 |
| --- | --- | --- | --- |
| `python -m app.main` | `app` | ✅ | `[U1]` |
| `python app/main.py` | `None` | ❌ | `[U1]` |
| 被 `import app.main` | `app` | ✅ | `[U1]` |

> 注意：这是最高频的「明明代码没错却跑不起来」——直接用文件路径运行包内模块，`__package__` 是 `None`，相对导入无从解析。改用 `python -m 包.模块`。`[U1]`

### 5.3 `-m` 与直接运行的差别

| 维度 | `python -m app.main` | `python app/main.py` |
| --- | --- | --- |
| `__name__` | `__main__` | `__main__` |
| `__package__` | `app` | `None` |
| `sys.path[0]` | 当前工作目录 | 脚本所在目录 |
| 相对导入 | ✅ | ❌ |
| 父包 `__init__` | 先执行 | 不执行 |
| 依据 | `[U1]` | `[U1]` |

```powershell
python -m app.util
```

实测输出 `UTIL_EXEC __main__`——`-m` 也是以 `__main__` 执行，但包上下文完整。`[U1]`

### 5.4 什么时候用相对导入

| 场景 | 建议 | 依据 |
| --- | --- | --- |
| 包内模块互相引用 | 相对导入 | `[U3]` |
| 跨包引用 | 绝对导入 | `[U3]` |
| 脚本入口 | 绝对导入 | `[U3]` |
| 测试文件 | 绝对导入 | `[U3]` |

> 注意：PEP 8 的立场是「绝对导入更常见、可读性更好」；相对导入只在包内层级深、路径长时更清晰。不要为了「看起来内聚」全用相对导入。`[U3]`

## 6. 搜索路径

### 6.1 `sys.path` 的构成

```text
[0] 脚本所在目录（直接运行）或当前目录（-m / -c）
[1..] PYTHONPATH 环境变量里的目录
[...] 标准库目录
[...] site-packages（第三方安装位置）
```

```python
import sys
print(sys.path[0] or ".")
# PATH0 .（实测，-c 时为空字符串，代表当前目录）
```

| 来源 | 何时生效 | 依据 |
| --- | --- | --- |
| 脚本目录 | `python script.py` | `[U6]` |
| 当前目录 | `python -m` / `python -c` | `[U6]` |
| `PYTHONPATH` | 启动时读取 | `[U6]` |
| 标准库 | 解释器内置 | `[U6]` |
| `site-packages` | `site` 模块加载 | `[U6]` |

### 6.2 模块名遮蔽

| 现象 | 原因 | 依据 |
| --- | --- | --- |
| 自己写的 `json.py` 抢了标准库 | 脚本目录在 `sys.path[0]` | `[U6]` |
| `random.py` 导致标准库 `random` 报错 | 同上 | `[U6]` |
| 装了两个同名包 | 路径顺序决定 | `[U6]` |

```python
import json
print(json.__file__)     # 必须指向标准库，不能是本地 json.py
```

| 检查手段 | 用法 | 依据 |
| --- | --- | --- |
| 看 `__file__` | `json.__file__` | `[U6]` |
| 看 `sys.path` | 确认目录顺序 | `[U6]` |
| `importlib.util.find_spec` | 查解析到哪个文件 | `[U4]` |

### 6.3 不要改 `sys.path`

| 反例 | 问题 | 依据 |
| --- | --- | --- |
| `sys.path.append("../../lib")` | 依赖运行目录 | `[U3]` |
| `sys.path.insert(0, ".")` | 可能与标准库冲突 | `[U6]` |
| 用 `__file__` 拼路径再 append | 部署即失效 | `[U3]` |

| 正解 | 说明 | 依据 |
| --- | --- | --- |
| 正规包结构 + 在项目根运行 | 最简单 | `[U1]` |
| `pip install -e .` | 可编辑安装（29 章） | `[U4]` |
| 控制台入口点 | 打包时声明 | 29 章 |

## 7. 循环导入

### 7.1 表现

```python
# cyc_a.py
print("A_START")
import cyc_b
A = 1
print("A_END")

# cyc_b.py
print("B_START")
import cyc_a
B = 2
print("B_END")
```

```powershell
python -c "import cyc_a; print('CYCLE_DONE', cyc_a.A)"
```

实测输出：

```text
A_START
B_START
B_END
A_END
CYCLE_DONE 1
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 用 `import m` 形式**不报错** | 只是拿到半初始化模块 | `[U2]` |
| 用 `from m import x` 会报错 | 名字还没绑定 | `[U2]` |
| 关键在「用到时」是否已初始化 | 顺序决定成败 | `[U2]` |

```python
# 换成 from 形式就会炸
from cyc_b import B     # ImportError: cannot import name 'B' from partially initialized module
```

| 写法 | 循环时 | 依据 |
| --- | --- | --- |
| `import b` + 用 `b.B` | 可能成功（延迟取属性） | `[U2]` |
| `from b import B` | 常在导入期失败 | `[U2]` |
| 函数内 import | 推迟到调用时 | `[U2]` |

### 7.2 三种修法

| 修法 | 做法 | 适用 | 依据 |
| --- | --- | --- | --- |
| 抽公共模块 | 把互相依赖的部分下沉到第三个模块 | 最优 | `[U3]` |
| 延迟导入 | 在函数内 `import` | 应急 | `[U2]` |
| 依赖注入 | 由调用方传入对象 | 解耦 | `[U3]` |

```python
# 反例：两个模块顶层互相 from import
# cyc_a.py: from cyc_b import B
# cyc_b.py: from cyc_a import A

# 正解 1：抽 base.py，两者都只依赖 base
# 正解 2：函数内延迟导入（仅应急）
def render() -> str:
    from cyc_b import B
    return str(B)
```

| 判断 | 结论 | 依据 |
| --- | --- | --- |
| 循环依赖是设计问题吗 | 通常是 | `[U3]` |
| 延迟导入是正解吗 | 只是止血 | `[U2]` |
| 何时可接受循环 | 仅类型注解（`TYPE_CHECKING`） | 20 章 |

> 注意：`if TYPE_CHECKING: import x` 只解决「注解用到的类型」，不解决运行时逻辑依赖；运行时仍循环，就得拆。`[U2]`

### 7.3 依赖方向

```text
入口/编排层  →  业务层  →  基础设施层  →  工具/常量
```

| 规则 | 说明 | 依据 |
| --- | --- | --- |
| 只能单向 | 下层不 import 上层 | `[U3]` |
| 公共类型下沉 | 避免 A↔B | `[U3]` |
| 入口只做装配 | 不写业务 | `[U3]` |

## 8. 综合示例：包结构与入口

```text
demo/
├── __init__.py            # 只做导出
├── config.py              # 常量与 __all__
├── tools.py               # 业务函数
└── __main__.py            # python -m demo 的入口
```

```python
# demo/__init__.py
"""demo 包：只导出公共 API。"""
from .tools import run

__all__ = ["run"]
```

```python
# demo/config.py
__all__ = ["DEFAULT_LIMIT"]
DEFAULT_LIMIT = 3
_TIMEOUT = 30          # 内部使用，不导出
```

```python
# demo/tools.py
from .config import DEFAULT_LIMIT


def run(names: list[str], limit: int = DEFAULT_LIMIT) -> list[str]:
    return names[:limit]
```

```python
# demo/__main__.py
from .tools import run


def main() -> int:
    print("RESULT", run(["search", "cache", "summarize"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
```

本机实测（包结构相同，`python -m demo`）：

```text
RESULT ['search', 'cache', 'summarize']
```

**逐段说明**：

| 代码 | 用到的机制 | 依据 |
| --- | --- | --- |
| `__init__.py` 只 import 与 `__all__` | 包级 API | `[U1]` |
| `__main__.py` | `python -m demo` 的执行入口 | `[U1]` |
| `if __name__ == "__main__"` | 可被测试直接调用 `main()` | `[U1]` |
| 相对导入 | 包内引用 | `[U3]` |
| `_TIMEOUT` 不导出 | 私有约定 | `[U3]` |

> 注意：`python -m demo` 与 `python demo/__main__.py` 不等价——后者 `__package__` 为 `None`，相对导入会失败。`[U1]`

## 9. 注意事项与新手错误对照表

| 错误写法 / 操作 | 报错或现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 直接 `python pkg/mod.py` | `ImportError: attempted relative import` | `python -m pkg.mod` | `[U1]` |
| `from m import *` | 命名空间污染 | 显式导入 | `[U3]` |
| 自建 `json.py` / `typing.py` | 遮蔽标准库 | 改名 | `[U6]` |
| 模块名带 `-` | 无法导入 | 下划线 | `[U3]` |
| 模块名大写 | Linux 上路径不一致 | 全小写 | `[U3]` |
| 顶层写 `print` / 请求 | 导入即执行 | 放进 `main()` | `[U1]` |
| 顶层 `sys.exit()` | 导入方被终止 | `__main__` 保护 | `[U1]` |
| `__init__.py` 里连数据库 | 导入变初始化 | 只做导出 | `[U3]` |
| `__all__` 写错名字 | 少导出，不报错 | 测试校验 | `[U3]` |
| 以为 `_x` 不能访问 | 实际能访问 | 只当约定 | `[U3]` |
| `import a.b` 后直接用 `b` | `NameError` | `a.b` 或 `as b` | `[U1]` |
| `from m import x` 后改 `x` | 源模块不变 | 明确语义 | `[U1]` |
| 两个模块顶层互 `from import` | `ImportError` 半初始化 | 抽公共 / 延迟 | `[U2]` |
| 用延迟导入掩盖设计问题 | 逻辑仍纠缠 | 拆层 | `[U3]` |
| `sys.path.append(...)` 拼相对路径 | 换目录即失效 | 包结构 + 安装 | `[U3]` |
| 修改 `sys.path` 插入项目根 | 与标准库冲突 | 正规安装 | `[U6]` |
| `reload` 当热更新用 | 旧对象不更新 | 重启进程 | `[U4]` |
| 动态导入用户输入 | 任意模块加载 | 白名单 | `[U4]` |
| 依赖 `__file__` 拼资源路径 | 打包后失效 | `importlib.resources` | `[U4]` |
| 同名模块出现在两个路径 | 随机命中 | 检查 `__file__` | `[U6]` |
| 在包里放 `__main__.py` 却用文件路径跑 | 相对导入失败 | `python -m pkg` | `[U1]` |
| 包名与模块名相同 | 导入歧义 | 改名 | `[U1]` |
| 用命名空间包做普通应用 | 定位不确定 | 普通包 | `[U5]` |
| 以为无 `__init__.py` 不是包 | 3.3+ 是命名空间包 | 了解 PEP 420 | `[U5]` |
| 导入时启动线程 | 无法控制生命周期 | 显式启动 | `[U3]` |
| 循环导入靠「顺序调换」修 | 脆弱 | 拆依赖 | `[U3]` |
| `from . import x` 写在脚本文件里 | `ImportError` | 脚本用绝对导入 | `[U1]` |
| 测试文件用相对导入 | 直接跑失败 | 绝对导入 + `-m pytest` | `[U3]` |
| 模块级可变全局 | 多模块共享污染 | 函数封装 | `[U2]` |
| `importlib.reload` 后旧实例不更新 | 类身份混淆 | 重建实例 | `[U4]` |
| 忘记 `__spec__` 为 `None` 的情况 | 反射报错 | 判空 | `[U2]` |
| 用 `dir()` 当公共 API | 包含内部名 | 用 `__all__` | `[U3]` |
| 包内文件用绝对路径读资源 | 安装后路径变 | `importlib.resources` | `[U4]` |
| 一个文件 import 整个包 | 启动慢 | 按需导入 | `[U1]` |
| 循环导入只发生在类型注解 | 用 `TYPE_CHECKING` | 符合规范 | 20 章 |
| 模块名与变量名冲突 | 覆盖模块对象 | 改别名 | `[U1]` |
| 在 `__init__.py` 里 `import *` | 不可控 | 显式导出 | `[U3]` |
| 以为 `import` 会拷贝值 | 实际共享对象 | 理解引用 | `[U1]` |
| 把脚本放包内当入口 | 相对导入失败 | `-m` 或独立脚本 | `[U1]` |
| `python -m` 时 `sys.path[0]` 是 cwd | 路径假设错 | 不假设路径 | `[U6]` |
| 用文件路径判断包位置 | 打包/zip 后失效 | `__spec__` / 资源 API | `[U4]` |

## 10. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 按职责拆模块 | 编排 / 业务 / 基础设施 | `[U3]` |
| 入口用 `main()` + 保护 | 可测试、可复用 | `[U1]` |
| 公共 API 写 `__all__` | 明确契约 | `[U3]` |
| 绝对导入为主 | 可读、可搜索 | `[U3]` |
| 包内深层级可用相对导入 | 减少重复前缀 | `[U3]` |
| `__init__.py` 只做导出 | 不写逻辑 | `[U3]` |
| 依赖方向单向 | 防循环 | `[U3]` |
| 不在顶层做 I/O | 保证可导入 | `[U1]` |
| 资源用 `importlib.resources` | 兼容打包 | `[U4]` |
| import 分组：标准库/第三方/本地 | 组间空行 | `[U3]` |

**风格示范**：

```python
"""tools 模块：提供工具调用编排。

为什么单独成模块：编排层与基础设施层分离，避免循环导入。
"""

from __future__ import annotations

import json
import logging
from collections.abc import Iterable

from .config import DEFAULT_LIMIT

logger = logging.getLogger(__name__)


def run_all(names: Iterable[str], limit: int = DEFAULT_LIMIT) -> list[str]:
    """执行并返回结果名列表。"""
    picked = list(names)[:limit]
    logger.info("run_all size=%d", len(picked))
    return picked
```

**import 顺序**（PEP 8）：

| 组 | 内容 | 依据 |
| --- | --- | --- |
| 1 | 标准库 | `[U3]` |
| 2 | 第三方 | `[U3]` |
| 3 | 本地/本项目 | `[U3]` |
| 组间 | 空一行 | `[U3]` |
| 每行 | 只导一个模块 | `[U3]` |

## 11. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[U1]` | python.org | https://docs.python.org/3.12/tutorial/modules.html | 模块与包、导入执行语义、`__name__`、`-m`、相对导入、`__init__.py` |
| `[U2]` | python.org | https://docs.python.org/3.12/reference/import.html | 导入系统五步、`sys.modules`、半初始化模块、`__path__` / `__spec__`、`__pycache__` |
| `[U3]` | PEP 官方 | https://peps.python.org/pep-0008/ | import 位置与分组、绝对导入优先、避免 `import *`、`__all__`、模块命名 |
| `[U4]` | python.org | https://docs.python.org/3.12/library/importlib.html | `import_module` / `reload` / `find_spec` / `resources` |
| `[U5]` | PEP 官方 | https://peps.python.org/pep-0420/ | 命名空间包（隐式命名空间包） |
| `[U6]` | python.org | https://docs.python.org/3.12/library/sys.html | `sys.path`、`sys.modules`、`sys.path[0]` 语义 |
| `[U7]` | GitHub 官方 | https://github.com/python/cpython/blob/main/Doc/tutorial/modules.rst | 官方教程源文件（`[U1]` 页脚 Show Source） |
| `[U8]` | PEP 官方 | https://peps.python.org/pep-0328/ | 绝对导入与显式相对导入的语法 |

> **核对状态**：`[U2]` `[U3]` 与本章 `README.md` 已核对来源一致；其余按 `docs.python.org/3.12` 与 `peps.python.org` 官方结构整理，**本次未逐页直连复核**。文中「实测」均为本机 Python 3.12.8 在临时目录运行的结果。

## 12. 毕业自查清单

**能说清（概念层）**：

- [ ] 包、模块、成员三者的关系
- [ ] `import` 的五个步骤与 `sys.modules` 的作用
- [ ] 为什么模块只执行一次
- [ ] `__all__` 到底影响什么、不影响什么
- [ ] `_private` 是不是真私有
- [ ] `__name__ == "__main__"` 的两种触发方式
- [ ] `__init__.py` 的四个作用
- [ ] 命名空间包与普通包的区别
- [ ] `-m` 与直接运行的四处差异
- [ ] 循环导入什么时候报错、什么时候不报
- [ ] `sys.path` 的构成顺序

**能写出（代码层）**：

- [ ] 带 `__all__` 的模块
- [ ] 带 `main()` + `__main__` 保护的入口
- [ ] `python -m pkg` 可运行的 `__main__.py`
- [ ] 包内相对导入（`from .util import x`）
- [ ] 动态导入白名单映射
- [ ] 用 `importlib.resources` 读包内资源

**能判断（避坑层）**：

- [ ] 看到直接跑包内文件能指出相对导入失败
- [ ] 看到自建 `json.py` 能指出遮蔽标准库
- [ ] 看到顶层副作用能指出导入即执行
- [ ] 看到 `sys.path.append` 能指出部署失效
- [ ] 看到循环导入能给出「抽公共模块」方案
- [ ] 看到 `from . import x` 写在脚本里能指出不合法
- [ ] 看到 `reload` 当热更新能指出旧对象不更新

**能跑通（验收层）**：

- [ ] 运行 `examples/module_demo.py` 并解释四行输出
- [ ] 建一个两模块包，分别用 `python -m` 与直接运行验证差异
- [ ] 在 REPL 验证 `sys.modules` 缓存
- [ ] 造一个循环导入并改成抽公共模块

## 13. 下一章衔接

第 22 章 `标准库`：模块能拆了，接着盘点随解释器自带、无需安装的工具箱——`pathlib`、`json`、`collections`、`logging` 等。

本章留下的伏笔：

1. `importlib.metadata` 属于标准库，第 23 章用它查询已安装包版本。
2. `sys.path` 与 `site-packages` 的关系，决定「pip 装的东西为什么能被导入」。
3. 包结构决定了测试与打包方式（第 29/30 章）。