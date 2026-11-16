# 02 python环境安装

> 承接第 01 章：那一章划清了「学什么、不学什么」，本章把「以 Python 3 为准、环境可复现」落成一套可执行的流程。**本章不教语法**，只解决一个问题：让代码在一个确定的解释器里跑起来。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 01 章（学习边界）；本机已装 `Python 3.12.8` |
| 本章目标 | 安装包核心组件与 REPL、版本选择与多版本管理（Windows / macOS / pyenv / pyenv-win）、安装验证、虚拟环境隔离、`pip` 与依赖记录、镜像源配置、忽略规则 |
| 毕业标准 | 能解释解释器 / venv / 依赖三层关系；能列出安装包核心组件；能说清版本管理器与虚拟环境的分工；能说清 pyenv 是什么、为什么 Windows 要用 pyenv-win；能独立建、激活、验证、重建一个 venv；能区分 pip 镜像源与 pyenv 下载镜像；能说清 `pip freeze` 不是 lockfile |
| 编码要求 | 能运行 `examples/check_env.py` 并用它的输出判断当前是否在虚拟环境中 |

## 0. 依据标注约定

本章每个解释与代码片段后用 `` `[Rn]` `` 标注依据，第 7 节是完整索引表。三类规范来源 + 一类辅助资料：

| 类型 | 来源 |
| --- | --- |
| python.org 官方 | `docs.python.org`、`devguide.python.org`、`peps.python.org`、`www.python.org` |
| 官方社区 | PyPA 的 `packaging.python.org`、`pip.pypa.io` |
| GitHub 官方仓库 | `github/gitignore`、`python/cpython`、`pyenv/pyenv`、`pyenv-win/pyenv-win` |
| 镜像服务方文档（辅助） | `developer.aliyun.com/mirror/pypi`：只用于说明某个具体镜像地址，**不是 pip 规范来源**；pip 的配置机制一律以 `[R21]` `[R22]` 为准 |

> 标注为「实测」的内容是本机只读检测结果，**不是官方依据**，只用于对照你自己的机器。
>
> **版本差异**：`[R21]` `[R22]` 查证时页面为 `pip documentation v26.3`，本机是 `pip 24.3.1`。本机已用只读命令 `python -m pip config debug` 验证 `pip config` 可用及配置文件路径；优先级等规则按官方 stable 文档表述，**未在 24.3.1 上逐条验证**。官方文档标注 macOS 的 `XDG_DATA_DIRS` / `XDG_DATA_HOME` 支持是 26.2 起新增，本机版本不适用。`[R21]`

## 1. 概念

### 1.1 安装包里到底有什么

从 `python.org` 下载的安装包（以 3.12 Windows full installer 为例）不只是一个 `python.exe`，它至少带这五类东西 `[R3]` `[R15]`：

| 组件 | 是什么 | 本课用在哪 | 依据 |
| --- | --- | --- | --- |
| 解释器 | **CPython**：官方术语表定义为「在 `python.org` 分发的 Python 语言规范实现（canonical implementation）」；Jython、IronPython、PyPy 属于其他实现 | 执行 `.py`、驱动 REPL | `[R14]` `[R18]` |
| 包管理器 | `pip`：把第三方包装进当前环境的 `site-packages`；安装包默认附带 | 第 4 节安装 / 导出依赖 | `[R3]` `[R7]` |
| 标准库 | 随解释器分发、无需 `pip install` 的模块集合；Windows 安装包通常包含完整标准库 | `os`、`sys`、`urllib`、`pathlib` 等 | `[R15]` |
| 交互式终端 | **REPL**：不带参数运行 `python` 进入交互模式；IDLE 也随标准发行版附带 | 第 03 章起随手验证表达式 | `[R14]` `[R16]` |
| 版本 / 环境工具 | Windows 的 `py` launcher；标准库里的 `venv`、`ensurepip` | 多版本切换、虚拟环境 | `[R3]` `[R5]` `[R15]` |

> 术语澄清：口语里的「装了 Python」，严谨说法是「装了 CPython 这一实现 + 标准库 + pip + 若干工具」。`pip` 是 PyPA 定位的包**安装器**，不是解释器的一部分。`[R7]` `[R14]`

**标准库四个例子**（按官方总览的分类）`[R15]`：

| 模块 | 官方分类 | 典型用途 |
| --- | --- | --- |
| `os` | Generic Operating System Services | 环境变量、进程信息、路径字符串操作 |
| `sys` | Python Runtime Services | 解释器版本、前缀路径、命令行参数 |
| `urllib` | Internet Protocols and Support | URL 处理与 HTTP 请求（`urllib.request`） |
| `pathlib` | File and Directory Access | 面向对象的路径操作 |

这四类都是标准库自带，**不需要也不能用 `pip` 安装**；`sys` 已被 `examples/check_env.py` 用到。`[R15]`

**REPL**：不带参数执行 `python` 进入交互模式，主提示符 `>>>`、续行次提示符 `...`；Windows 用 `Ctrl-Z` 加回车退出，Unix 用 `Ctrl-D`，也可 `quit()`。`-c` 执行一条命令、`-m` 运行模块、`-i` 会在执行脚本后进入交互模式。`[R16]` 可运行的只读自检见 6.3。

### 1.2 三层环境模型

| 层 | 是什么 | 谁决定 | 依据 |
| --- | --- | --- | --- |
| 解释器（base Python） | 提供标准库与 `python.exe`；一个机器可有多个版本 | 官方安装包 / `py` launcher | `[R1]` `[R2]` `[R3]` |
| 虚拟环境（venv） | 基于某个 base Python 的独立 `site-packages`，共享标准库 | `python -m venv .venv` | `[R5]` `[R9]` |
| 依赖 | 装进 venv 的第三方库，用 `requirements.txt` 记录以便重建 | `pip` | `[R7]` `[R8]` |

关键认知：**venv 不是复制一整份 Python**。它靠 `pyvenv.cfg` 标记自身，让 `sys.prefix` 指向环境目录、`sys.base_prefix` 指向 base Python，从而把标准库与第三方包的查找位置拆开。因此环境很轻，但也**不可整体搬移**。`[R5]` `[R9]`

### 1.3 版本怎么选

以官方状态页为准 `[R2]`（截至 2026-11 的页面数据）：

| 分支 | 状态 | 首次发布 | EOL |
| --- | --- | --- | --- |
| 3.16 / `main` | feature（开发中） | 2027-10（计划） | 2032-10（计划） |
| 3.15 | bugfix | 2026-10-09 | 2031-10（计划） |
| 3.14 | bugfix | 2025-10-07 | 2030-10（计划） |
| 3.13 | security | 2024-10-07 | 2029-10（计划） |
| **3.12（本机）** | **security** | 2023-10-02 | 2028-10（计划） |
| 3.10 | end-of-life | 2021-10-04 | 2026-10-01 |

状态含义：`bugfix` 收缺陷与安全修复、约每两月出新二进制；`security` 只收安全修复、**不再发布新二进制**；`end-of-life` 完全停止。`[R2]`

**本课的选择**：继续用本机 3.12.8 学语法完全够用（第 03–28 章的语法主线不依赖新版本）；但**新建正式项目**优先选仍在 `bugfix` 的分支，或跟随团队 / 目标库的版本要求。另注：3.12 分支文档站当前显示 3.12.16，本机 3.12.8 不是该分支最新补丁，建议后续升级补丁版，不阻塞本章。`[R2]`

Windows 平台支持：3.12 支持 Windows 8.1 及以上。`[R3]`

### 1.4 Windows 安装方式（有一个容易踩的版本差异）

**Python 3.12（本机）**`[R3]`：

- 从 `python.org/downloads` 下载 full installer（web / offline，32/64-bit）；官方称它是「开发者做任何项目的最佳选项」。`[R1]` `[R3]`
- 安装首屏的 **Add Python to PATH** 勾上后，`python` 与 `pip` 才能在终端直接用，同时会把 `Scripts\` 加入 `PATH`；没勾可重跑安装器选 Modify，或手工改 `PATH`。`[R3]`
- 官方提醒：`PATH` 只对**单一系统级安装**可靠；多版本请用 `py` launcher，`py --list` 列出已装版本，`py -3.12` 指定版本。`[R3]`

**Python 3.14 及以后**`[R4]`：

- 官方推荐改用 **Python install manager**（`py list` / `py install`），可从 `python.org/downloads` 或 Microsoft Store 获取。`[R1]` `[R4]`
- 传统 full installer 自 3.14 起 deprecated、**3.16 起不再提供**（3.16 之前仍随版本提供）。`[R4]`

> **结论**：`docs.python.org/3/...` 默认指向当前主线（本文查证时为 3.15.2），里面 `py install` 之类的命令**不适用于本机 3.12**。查文档先看版本选择器，别把新版做法套到旧解释器上。`[R3]` `[R4]`

**本机实测**：`python --version` → `Python 3.12.8`；`py --list` → `-V:3.12 * Python 3.12 (64-bit)`；解释器位于 `C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe`。

### 1.5 版本管理器与 pyenv（Windows / macOS）

**版本管理器管「哪个 `python` 被解析到」，虚拟环境管「依赖装到哪」**——互补、不互相替代。pyenv 官方 README 明确写它**不管理 virtualenv**（需要时另装 `pyenv-virtualenv` 插件）；venv 也不会帮你换解释器版本。`[R5]` `[R18]`

#### pyenv 是什么

`pyenv` 的自我定位是 **"Simple Python version management"**（轻量 Python 版本管理器），官方 README 给出的关键特征 `[R18]`：

| 特征 | 官方表述 / 含义 |
| --- | --- |
| 只做一件事 | 在多个 Python 版本之间切换；遵循 UNIX「单一职责」传统 |
| 不依赖 Python | 纯 shell 脚本实现，没有「先用 Python 装 Python」的 bootstrap 问题 |
| 不注入 shell | 靠 **shim**（轻量转发脚本）目录插到 `PATH` 最前拦截 `python` / `pip`，而不是把逻辑加载进 shell |
| 不管理 virtualenv | 虚拟环境要自己用 `venv` 建，或另装 `pyenv-virtualenv` 插件 |
| 支持多发行版 | 除 CPython 外还可管理 PyPy、Stackless Python、Jython 等 |
| 三级作用域 | `global`（用户全局）、`local`（项目目录）、`shell`（当前会话），另可用 `PYENV_VERSION` 环境变量覆盖 |

工作原理一句话：`pyenv` 在 `$(pyenv root)/shims` 里为每个命令放一个转发脚本，执行时按 **`PYENV_VERSION` → 当前目录 `.python-version` → 逐级父目录 → `$(pyenv root)/version` → 系统 Python** 的顺序选出版本，再把命令转给 `$(pyenv root)/versions/<版本>/bin` 下真正的解释器。`[R18]`

> 关键边界：`pyenv local` 的目录级版本**不是虚拟环境**——pyenv-win README 也写明 "This is different than a virtual env, which needs to be explicitly activated"。选完版本后仍要 `python -m venv .venv` 隔离依赖。`[R5]` `[R18]` `[R19]`

#### 平台选择

| 平台 | 首选方案 | 依据 |
| --- | --- | --- |
| Windows 3.12 | 官方 `py` launcher：`py --list` 列版本、`py -3.12` 选版本 | `[R3]` |
| Windows 3.14+ | 官方 Python install manager：`py list` / `py install` | `[R4]` |
| macOS / Linux | 社区 `pyenv`（Homebrew 安装），或按官方 macOS 文档分别安装多个版本 | `[R17]` `[R18]` |

> **需要纠正的一点**：`pyenv` 官方 README 原文是 **"Pyenv does not officially support Windows"**，Windows 原生不可用（WSL 里能跑，但装的是 Linux 版 Python，拿不到 Windows 专有功能）。Windows 若坚持用 pyenv 风格，官方 README 指向 `pyenv-win` 这个独立 fork。`[R18]` `[R19]`
>
> **本课建议**：Windows 优先用官方 `py` launcher，而不是 `pyenv-win`——后者要把 `bin` 与 `shims` 放到 `PATH` 高优先级，README 还提示 Win10 1905+ 可能需要关闭系统自带的 Python 应用执行别名，容易与官方 launcher 打架。`[R3]` `[R19]`

#### macOS 安装 pyenv 的四个阶段 `[R18]`

1. **装 pyenv 本体**：Homebrew 是官方推荐方式（`brew update` / `brew install pyenv`）；也可用自动安装器 `curl -fsSL https://pyenv.run | bash` 或 `git clone` 到 `~/.pyenv`。`[R18]`
2. **初始化 shell**：`pyenv init --install` 把 shims / 补全 / shell 函数写入当前 shell 的启动文件，再 `exec "$SHELL"` 重启让 `PATH` 生效。`[R18]`
3. **装构建依赖**：官方明确要求 "Install Python build dependencies before attempting to install a new Python version"；`pyenv install-prerequisites` 只覆盖 Ubuntu / Debian / Mint，macOS 要按官方 wiki 的 suggested build environment 装。`[R18]` `[R20]`
4. **装版本并验证**：`pyenv install <版本>` → `pyenv --version` / `pyenv version`；可安装范围以 `pyenv install -l` 的真实输出为准。`[R18]` `[R19]`

原因是 `pyenv install` 提供的大多是**源码发行版并在本机编译**（README 原文 "source releases and are built from source"），与 `python.org` 的预编译安装包不是同一条路径；缺构建依赖只会在编译阶段才报错。`[R18]`

#### Windows 安装 pyenv 的实际情况 `[R18]` `[R19]`

Windows 上「安装 pyenv」实际是安装 `pyenv-win`——一个 fork 自 `rbenv-win` 的独立移植项目，装的是**原生 Windows Python 安装包**，因此没有 macOS 那条源码编译链路。`[R19]`

- 官方 README 列出 PowerShell 脚本、Git、zip、`pip install pyenv-win`、Chocolatey 五种安装方式，细节集中在 `docs/installation.md`。`[R19]`
- 装完必须重开终端，用 `pyenv --version` 验证；若提示 command not found，检查 `%USERPROFILE%\.pyenv\pyenv-win\bin` 与 `...\shims` 是否在 `PATH` 高优先级。`[R19]`
- 用 `pip` 装过新库或切换版本后，官方要求执行 `pyenv rehash` 更新 shim（且要在 `.pyenv` 目录之外执行）。`[R19]`

完整命令见 6.4，镜像源见 1.8 / 6.5；**本课不在本机安装 pyenv 或 pyenv-win**。

#### macOS 官方安装包的要点（不使用 pyenv 时） `[R17]`

- `python.org` 的 macOS 安装包把框架放到 `/Library/Frameworks/Python.framework`，在 `/usr/local/bin` 建符号链接，在 `/Applications/Python 3.12` 放 IDLE、Python Launcher 等应用。
- macOS 12.3 之前系统自带 Python 2.7；官方明确**不要修改或删除** `/System/Library/Frameworks/Python.framework` 与 `/usr/bin/python`，它们由 Apple 提供并供系统使用。
- 装完会同时存在「系统 Python」与「python.org Python」，务必留意 `PATH` 里谁在前；`python3` 与 `python` 的指向可能不同。

### 1.6 为什么必须用 venv

- **冲突场景**：应用 A 要 LibFoo 1，应用 B 要 LibFoo 2，全局安装必然互相破坏；venv 给每个应用独立安装目录。PyPA 教程与 Python 官方文档都以此作为首要动机。`[R5]` `[R7]`
- **官方对 venv 的定性**：默认与其他环境及系统包隔离；惯例命名 `.venv` 或 `venv`；**不纳入版本控制**；**视为可丢弃**（应能随时删掉重建，项目代码不放进去）；**不可移动或复制**（脚本 shebang 里是绝对路径，移动后应重建）。`[R5]`
- **激活的本质**：只是把环境的 `Scripts` 目录插到 `PATH` 前面，让裸 `python` 指向环境里那个解释器。**不激活也能用**，直接用环境的解释器绝对路径即可。`[R5]`
- **判定方式**：用 `sys.prefix != sys.base_prefix`，**不要依赖 `VIRTUAL_ENV` 环境变量**——因为不激活也能使用 venv，该变量可能不存在。`[R5]` `[R10]`

### 1.7 pip 与 requirements.txt

- 用 `python -m pip`（Windows 上 PyPA 教程写 `py -m pip`，用于选定版本），而不是裸 `pip`：避免 `PATH` 里那个 `pip` 与当前解释器不是一套。官方文档的排错表也明确推荐 `python -m pip`。`[R4]` `[R7]`
- 版本约束：`SomeProject==1.4`、`SomeProject>=1,<2`、`SomeProject~=1.4.2` 都是官方支持的 requirement specifier 写法。`[R7]`
- 安装依赖清单：`python -m pip install -r requirements.txt`。`[R7]`
- 导出已安装项：`python -m pip freeze > requirements.txt`（Windows 上 PyPA 写 `py -m pip freeze`）。`[R8]`
- **必须记住的边界**：`pip freeze` 只是「报告已安装的包」，官方文档明确写 **does not compute a lockfile or a solver result**；它默认还会排除 `pip` 等引导工具（3.12+ 只排除 `pip`，`--all` 可包含）。把它当完整锁定文件是常见误解。`[R8]`

### 1.8 镜像源：两条完全不同的下载链路

「配置镜像源」在本章里指两件**互不相关**的事，先分清再动手 `[R21]` `[R20]`：

| 链路 | 下载什么 | 谁在下载 | 配置项 | 依据 |
| --- | --- | --- | --- | --- |
| pip 包索引镜像 | 第三方包（wheel / sdist） | `pip` | `index-url` / `--index-url` / `PIP_INDEX_URL` | `[R21]` `[R22]` |
| pyenv 源码包镜像 | CPython 源码 tarball | `pyenv install` 背后的 `python-build` | `PYTHON_BUILD_MIRROR_URL` 等环境变量 | `[R20]` |

**pip 侧**：`pip` 默认从 PyPI 拉取包，`index-url` 换的是包索引地址。官方配置机制有三层——**命令行选项 > 环境变量 > 配置文件**；配置文件再分 `global` / `user` / `site` 三级，加载顺序 Global → User → Site → `PIP_CONFIG_FILE`（后者覆盖前面）。环境变量统一按 `PIP_<UPPER_LONG_NAME>` 命名，例如 `PIP_INDEX_URL`。`[R21]`

配置文件是标准 INI 格式，当前 user 级路径 `[R21]`：

| 平台 | user 级配置 |
| --- | --- |
| Windows | `%APPDATA%\pip\pip.ini` |
| macOS | `$HOME/Library/Application Support/pip/pip.conf`，否则 `$HOME/.config/pip/pip.conf` |
| Linux | `$HOME/.config/pip/pip.conf` |

```ini
[global]
index-url = https://<镜像服务方给出的地址>/simple
```

> 旧教程常写 `~/.pip/pip.conf`（Unix）或 `%HOME%\pip\pip.ini`（Windows），那属于官方明说的 **legacy** 路径；legacy 与当前路径同时存在时，**当前路径的值覆盖 legacy**。`[R21]` 镜像站帮助页也可能给 legacy 路径，别照抄。`[R23]`

**pyenv 侧**：`pyenv install` 由内置的 `python-build` 插件下载 CPython 源码包，官方 README 说它**默认先尝试 GitHub Pages 上的镜像** `https://pyenv.github.io/pythons/`，失败才回退到定义文件里的官方地址；可用 `PYTHON_BUILD_MIRROR_URL` 指向自建镜像、`PYTHON_BUILD_SKIP_MIRROR` 强制走官方地址、`PYTHON_BUILD_CACHE_PATH`（默认 `~/.pyenv/cache`，建目录即启用）缓存下载文件。`[R20]`

> 安全边界：`python-build` 在装有 `shasum` / `openssl` / `sha256sum` 时会**自动校验每个下载包的 SHA-2**；镜像 URL 按「镜像根 + 包的 SHA-2 校验和」拼出，所以自建镜像不是随手改个域名就能用。`[R20]` 这也是 pip 镜像与 pyenv 镜像不能共用同一个地址的原因。

**本课取舍**：镜像源是可选的网络加速配置，不是环境正确性的前提；命令在 6.5，**本课不修改你的 pip 配置**。

## 2. 注意事项

1. **文档版本要对齐解释器版本**：3.12 用 `docs.python.org/3.12/...`，新版安装方式完全不同。`[R3]` `[R4]`
2. **多版本不要靠手工改 `PATH`**：官方明说 `PATH` 只对单一安装可靠，多版本用 `py`。`[R3]`
3. **PowerShell 激活可能被策略拦**：官方给出的解法是 `Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser`。`[R5]` 本机实测 `CurrentUser` 已是 `RemoteSigned`，无需改动。
4. **不要往全局环境装包，更不要 `sudo pip`**：PyPA 教程明确要求「不要用 sudo 运行本教程任何命令」，权限报错就回去建 venv。`[R7]` `[R10]`
5. **`--user` 在 venv 内无效**：一旦处于虚拟环境，安装命令一律作用于该环境。`[R7]`
6. **UTF-8**：Windows 默认用 ANSI 代码页作文本文件编码，Python 提供 `-X utf8` / `PYTHONUTF8=1` 的 UTF-8 Mode；注意全局设置会影响机器上所有 Python 3.7+ 程序。`[R3]` 本课示例只输出中文短句，本机实测无需额外设置。
7. **不要把 `.venv/` 提交到 git**：官方定性是「不入库 + 可丢弃」；3.13+ 的 `venv` 甚至默认在环境目录内生成 `.gitignore`。`[R5]` `[R6]`
8. **别把版本管理器和虚拟环境混为一谈**：pyenv 换解释器、venv 隔离依赖；官方 README 明确 pyenv 不管理 virtualenv。`[R5]` `[R18]`
9. **Windows 别直接照抄 macOS 的 pyenv 教程**：`pyenv` 官方不支持 Windows；`pyenv-win` 是独立 fork，会改 `PATH`、可能与官方 launcher 冲突。`[R18]` `[R19]`
10. **macOS 别动系统自带 Python**：官方明确 `/usr/bin/python` 与 Apple 的 framework 供系统使用，不要修改或删除。`[R17]`
11. **镜像源走 HTTPS，别乱加 `trusted-host`**：`trusted-host` 会放宽对该主机的证书校验；HTTPS 证书链正常时不需要它。部分镜像站帮助页给的是 `http://` + `trusted-host` 老写法，应按同一域名的 HTTPS 地址改写。`[R21]` `[R23]`
12. **镜像 ≠ 官方 PyPI**：镜像站自述采用增量同步、与官方源不一定完全一致（官方已删除的恶意包镜像侧可能仍存在）；换源等于把包的下载来源交给第三方。`[R23]`
13. **`pyenv local` 不是 venv**：目录级版本选择只换解释器，依赖仍要 `python -m venv .venv` 隔离。`[R5]` `[R18]` `[R19]`
14. **macOS 装 pyenv 前先装构建依赖**：`pyenv install` 大多是源码编译，缺依赖会在编译阶段才失败；`pyenv install-prerequisites` 只适用于 Ubuntu / Debian / Mint。`[R18]` `[R20]`
15. **pyenv-win 装完要重开终端并按需 `rehash`**：`bin` / `shims` 必须处于 `PATH` 高优先级；用 `pip` 装过库后官方要求执行 `pyenv rehash`。`[R19]`

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 环境不可搬移 | 环境内脚本 shebang 含解释器绝对路径，移动目录后应重建而非复制 | `[R5]` |
| 系统 Python 可能被「外部管理」 | PEP 668 用 `EXTERNALLY-MANAGED` 标记文件让 `pip` 拒绝全局安装，并引导用户建 venv；`--break-system-packages` 是显式覆盖、带风险。上游未打补丁的 CPython 行为不变，Windows python.org 安装包一般属此列 | `[R10]` |
| venv 不隔离解释器本身 | 共享 base Python 的标准库；base 升级后环境可能需要重建 | `[R5]` `[R9]` |
| `pip freeze` ≠ 锁定 | 无依赖求解、无哈希校验；完整锁定与可复现构建属于第 30 章 | `[R8]` |
| 3.12 已进 security 阶段 | 只收安全修复、不再有新二进制；学习够用，长期项目要评估 | `[R2]` |
| 其他分发形态不是学习环境 | Microsoft Store 包面向交互式使用、nuget 面向 CI、embeddable 面向嵌入应用且不含 pip | `[R3]` |
| 本章不展开 `pyproject.toml` / 包管理器 | 属于第 29–30 章；本章只到 `venv + pip + requirements.txt` | 课程边界 |
| 版本管理器 ≠ 虚拟环境 | pyenv 只切解释器版本、不管理 virtualenv；两者要叠加用：先选版本，再 `python -m venv .venv` 隔离依赖 | `[R5]` `[R18]` |
| pyenv 装的是源码构建 | 官方 README 说明提供的大多是源码发行版、需构建依赖；与 `python.org` 预编译安装包不是同一条路径 | `[R18]` |
| Windows 第三方方案与官方 launcher 会打架 | `pyenv-win` 要求把 `bin` / `shims` 置于 `PATH` 高优先级，README 提示可能需要关闭系统 Python 应用执行别名 | `[R3]` `[R19]` |
| pip 配置有多层覆盖 | 命令行 > 环境变量 > 配置文件；配置文件 Global → User → Site → `PIP_CONFIG_FILE`。排查「改了没生效」先跑 `pip config debug` | `[R21]` `[R22]` |
| pyenv 镜像只影响源码包 | `PYTHON_BUILD_MIRROR_URL` 不作用于 VCS 拉取、包内部构建逻辑产生的下载，以及 `get-pip.py` 等滚动更新文件 | `[R20]` |
| 镜像源不保证与官方同步 | 增量同步下官方已删除的包镜像侧可能仍存在；生产环境应配合哈希 / 锁定（第 30 章） | `[R23]` |

## 4. 最佳实践（从零到可复现）

> 以下命令**由你执行**；本课不在你的机器上创建 venv，避免留下临时环境。每条命令都标了依据。

**第 1 步｜验证解释器与 pip**（只读）`[R3]` `[R7]`

```powershell
python --version
py --list
python -m pip --version
```

**第 2 步｜在项目根建环境**，目录名用惯例 `.venv` `[R5]` `[R7]`

```powershell
python -m venv .venv
```

**第 3 步｜激活** `[R5]`

```powershell
# PowerShell
.\.venv\Scripts\Activate.ps1

# cmd.exe
.\.venv\Scripts\activate.bat
```

**第 4 步｜确认真的在环境里**（用 `sys.prefix` 判定，不看 `VIRTUAL_ENV`）`[R5]`

```powershell
python -c "import sys; print(sys.prefix != sys.base_prefix)"
```

**第 5 步｜安装依赖并导出清单** `[R7]` `[R8]`

```powershell
# SomeProject==1.4 是 [R7] 官方教程的格式示例，执行前换成真实包名与版本
python -m pip install "SomeProject==1.4"
python -m pip freeze > requirements.txt
```

**第 6 步｜在另一台机器 / 新目录重建** `[R5]` `[R7]`

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
```

**第 7 步｜退出环境** `[R5]`

```powershell
deactivate
```

> 顺序的理由：先确认「用哪个解释器」，再隔离，再装依赖，最后把依赖写成可重建的清单。跳过第 1 步是绝大多数「明明装了却 import 不到」的根因。

## 5. 最佳编码建议

- **显式指定解释器**：脚本与 CI 里用 `python -m pip`，不要写裸 `pip`；多版本场景用 `py -3.12 -m pip`。`[R4]` `[R7]`
- **环境判定用 `sys.prefix != sys.base_prefix`**，不用 `VIRTUAL_ENV`。`[R5]` `[R10]`
- **`requirements.txt` 入库，`.venv/` 不入库**；项目代码绝不写进环境目录。`[R5]` `[R7]`
- **直接依赖写精确版本**（应用项目要可复现），范围约束留给库作者；`pip freeze` 的输出要人工整理后再入库，因为它包含传递依赖且不区分直接与间接。`[R7]` `[R8]`
- **含密钥的配置不入库、不硬编码**：延续第 01 章的安全底线，配置走环境变量 / 配置中心。
- **命令按「本章目录」执行**：`examples/` 是相对本章目录的路径，在 `py-base` 根直接跑会报 `[Errno 2]`（第 01 章已踩过）。
- **失败要快**：本章自检脚本只做只读报告、不拦截；如何在环境不满足时明确抛错，属于第 16 章异常处理。
- **`.python-version` 与 `requirements.txt` 分开用**：前者由 `pyenv local` 生成、只记录解释器版本，后者记录依赖；不要把版本号写进业务代码。`[R18]`
- **Windows 不叠装第二个版本管理器**：已有官方 `py`，再加 `pyenv-win` 只会让 `PATH` 解析更难排查。`[R3]` `[R19]`
- **换源走官方机制，别手改一堆文件**：优先 `python -m pip config set global.index-url <URL>`，改完用 `pip config list` / `debug` 复核；临时换源用一次性的 `--index-url`，作用范围最小。`[R21]` `[R22]`
- **镜像 URL 写成配置项，不写进业务代码**：`PIP_INDEX_URL` 优先级高于配置文件，CI 里显式注入比全局改文件更可控。`[R21]`
- **自建 pyenv 镜像要保留 SHA-2 校验**：镜像根按包校验和拼接，别用 `PYTHON_BUILD_MIRROR_URL_SKIP_CHECKSUM` 绕过结构约束（官方标注该特性考虑弃用）。`[R20]`

## 6. 编码示例

### 6.1 只读环境自检（可运行）

`examples/check_env.py`。本章唯一新增语法是 `import sys`，其余仍是变量与 `print()`；`import` 机制在第 21 章、属性访问在第 08 章展开。**现在只需照抄运行、看懂最后一行**。

```python
"""第 02 章示例：只读环境自检。

只用到 import sys、变量与 print()。本章不教语法：
import 机制在第 21 章、对象属性在第 08 章展开。

运行（在本章目录下）：
    python examples/check_env.py
"""

import sys

version_info = sys.version_info
interpreter_path = sys.executable
is_venv = sys.prefix != sys.base_prefix

print("Python 版本信息:", version_info)
print("解释器路径:", interpreter_path)
print("prefix:", sys.prefix)
print("base_prefix:", sys.base_prefix)
print("是否在虚拟环境中:", is_venv)
```

依据：`sys.prefix` / `sys.base_prefix` 的判定语义见 `[R5]` `[R9]` `[R10]`。

运行（**先切到本章目录**，第 01 章的踩坑点）：

```powershell
cd 'E:\ai-agent-study\py-base\00-入门与环境\02-python环境安装'
python examples/check_env.py
```

本机实测输出：

```text
Python 版本信息: sys.version_info(major=3, minor=12, micro=8, releaselevel='final', serial=0)
解释器路径: C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe
prefix: C:\Users\Administrator\AppData\Local\Programs\Python\Python312
base_prefix: C:\Users\Administrator\AppData\Local\Programs\Python\Python312
是否在虚拟环境中: False
```

激活 venv 后 `prefix` 会指向 `.venv`，`base_prefix` 仍指向 base Python，最后一行变成 `True`。`[R5]` `[R9]`

### 6.2 `.gitignore` 最小片段

```gitignore
# 虚拟环境：官方定性为「不入库、可丢弃」，惯例名为 .venv 或 venv [R5]
.venv/
venv/

# 字节码缓存：Python 会自动生成与失效重建 [R11]；条目参考 GitHub 官方模板 [R12]
__pycache__/
*.py[cod]
```

`__pycache__` 里的 `.pyc` 是导入时生成的缓存，Python 会按源文件时间戳 / 大小或哈希校验并在失效时重新生成，因此属于可再生文件。`[R11]`

> **未逐字核对的部分**：本次网络无法直连 GitHub 官方 `Python.gitignore` 的 raw 文件，`__pycache__/` 与 `*.py[cod]` 是按 Python 官方 import 文档 `[R11]` 与检索到的模板转载片段整理的，**未逐字比对官方模板原文**；生产项目请打开 `[R12]` 拉取完整模板。

### 6.3 REPL 与组件自检（只读，可运行）

REPL 需要交互式终端，这里用 `-c` 做等价的只读自检 `[R16]`：

```powershell
# 进入 REPL：不带参数运行解释器；在 >>> 后输入表达式，Windows 用 Ctrl-Z 回车退出 [R16]
python

# 不进 REPL，直接执行一条命令：看解释器版本与可执行文件路径 [R16]
python -c "import sys; print(sys.version_info, sys.executable)"

# 确认标准库模块来自本地安装；sys 是内置模块、没有 __file__，故用 version_info 代替 [R15]
python -c "import os, sys, urllib, pathlib; print(os.__file__); print(urllib.__file__); print(pathlib.__file__); print(sys.version_info)"
```

> 本章只要求照抄运行；`import` 机制在第 21 章、模块 `__file__` 属性在第 08 章展开。`python` 那一行必须**在交互终端里手动执行**，非交互环境会挂起等待输入。

本机实测（第 2、3 条）输出：

```text
sys.version_info(major=3, minor=12, micro=8, releaselevel='final', serial=0) C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe

C:\Users\Administrator\AppData\Local\Programs\Python\Python312\Lib\os.py
C:\Users\Administrator\AppData\Local\Programs\Python\Python312\Lib\urllib\__init__.py
C:\Users\Administrator\AppData\Local\Programs\Python\Python312\Lib\pathlib.py
sys.version_info(major=3, minor=12, micro=8, releaselevel='final', serial=0)
```

三条路径都落在 `Python312\Lib` 下，正好印证标准库随解释器分发、无需 `pip install`。`[R15]`

### 6.4 版本管理器的安装与使用

#### Windows：优先用官方 launcher，无需第三方 `[R3]`

（本机已实测两条命令输出 `Python 3.12.8` / `-V:3.12 *`）

```powershell
py --list
py -3.12 --version
```

#### macOS：安装 pyenv（官方 Homebrew 路径）`[R18]`

```bash
# 1 装本体：Homebrew 是官方推荐方式
brew update
brew install pyenv

# 2 把初始化代码写入当前 shell 的启动文件，重启 shell 让 shims 进入 PATH
pyenv init --install
exec "$SHELL"

# 3 装构建依赖：macOS 按官方 wiki 的 suggested build environment 装；
#   pyenv install-prerequisites 只适用于 Ubuntu / Debian / Mint [R18] [R20]

# 4 装版本并验证；前缀自动解析到该版本线的最新版本
pyenv install -l
pyenv install 3.12
pyenv version
```

> 其他官方安装方式：自动安装器 `curl -fsSL https://pyenv.run | bash`，或 `git clone https://github.com/pyenv/pyenv.git ~/.pyenv`；用自动安装器时初始化命令改为 `~/.pyenv/bin/pyenv init --install`。`[R18]`
>
> **Bash 特例**：若 `BASH_ENV` 指向 `.bashrc`，官方要求跳过 `init --install` 改用手工配置，把 `eval "$(pyenv init - bash)"` 只放进登录启动文件，否则可能出现无限循环。`[R18]`
>
> `pyenv install` 默认从源码构建，缺构建依赖会在编译阶段才失败；可安装范围以 `pyenv install -l` 的真实输出为准。`[R18]` `[R20]`

#### Windows：安装 pyenv-win（独立 fork，仅在确实需要时）`[R19]`

```powershell
# 官方 README Quick Start 原文：下载远程脚本并立即执行，执行前先审阅内容
Invoke-WebRequest -UseBasicParsing -Uri "https://raw.githubusercontent.com/pyenv-win/pyenv-win/master/pyenv-win/install-pyenv-win.ps1" -OutFile "./install-pyenv-win.ps1"; &"./install-pyenv-win.ps1"

# 装完重开 PowerShell 再验证
pyenv --version
pyenv install -l
pyenv install 3.12.8
pyenv global 3.12.8
pyenv rehash
python -c "import sys; print(sys.executable)"
```

> 官方 README 还列出 Git、zip、`pip install pyenv-win`、Chocolatey 等安装方式，细节在 `docs/installation.md`。`[R19]`
>
> 若提示 command not found：检查 `%USERPROFILE%\.pyenv\pyenv-win\bin` 与 `...\shims` 是否在 `PATH` 高优先级；Win10 1905+ 可能还需关闭 Python 应用执行别名。`[R19]`
>
> **风险提示**：远程脚本执行 + 改 `PATH`，本课**不执行、不安装**。更推荐 `[R3]` 的官方 `py` launcher：无第三方依赖、不改 `PATH` 优先级，也不会与系统别名冲突。`[R19]`

#### pyenv 日常使用（两套实现的命令名一致）`[R18]` `[R19]`

```bash
pyenv install -l              # 列出可安装版本 [R18] [R19]
pyenv install 3.12            # 安装；前缀自动解析到该版本线最新版 [R18]
pyenv versions                # 列出已安装版本 [R19]
pyenv global 3.12             # 用户全局 [R18]
pyenv local 3.12              # 当前目录，写入 .python-version [R18]
pyenv shell 3.12              # 仅当前会话（设置 PYENV_VERSION）[R18]
pyenv version                 # 当前生效版本及其来源 [R18] [R19]
pyenv which python            # 真正会被执行的可执行文件路径 [R18]
pyenv global system           # 回到系统 Python [R18]
pyenv uninstall 3.12.8        # 卸载；需精确版本名，唯一不做前缀解析的子命令 [R18]
```

```powershell
pyenv rehash                        # pyenv-win：装/卸 pip 库或切换版本后执行 [R19]
pyenv install -l | findstr 3.12     # pyenv-win 的列表过滤写法 [R19]
```

> 版本选择优先级：`PYENV_VERSION`（`pyenv shell`）> 当前目录 `.python-version`（`pyenv local`）> 逐级父目录 > `$(pyenv root)/version`（`pyenv global`）> 系统 Python。`[R18]`
>
> **`pyenv local` 换的是解释器，不是虚拟环境**；选完版本仍要 `python -m venv .venv` 隔离依赖。`[R5]` `[R18]` `[R19]`

### 6.5 配置镜像源（pip 与 pyenv）

> 以下命令**由你执行**；本课只做只读检测，**不修改本机 pip 配置**。

**先看本机现状**（`pip config debug` 会列出所有配置文件与生效值，只读）`[R22]`

```powershell
python -m pip --version
python -m pip config list
python -m pip config debug
```

本机实测（只读）：`pip 24.3.1`；user 级配置文件 `%APPDATA%\pip\pip.ini` 已存在，其中 `global.index-url = https://pypi.tuna.tsinghua.edu.cn/simple`。也就是说本机**已经配置了 pip 镜像源**，无需重复设置；下面只是演示「如果由你来配，官方写法是什么」。

**pip：临时换源**（只影响这一条命令）`[R21]` `[R22]`

```powershell
# SomeProject 是 [R7] 官方教程的示例包名，执行前换成真实包名
python -m pip install --index-url https://mirrors.aliyun.com/pypi/simple/ SomeProject
```

**pip：设为当前用户默认**（写入 user 级配置）`[R21]` `[R22]`

```powershell
python -m pip config set global.index-url https://mirrors.aliyun.com/pypi/simple/
python -m pip config list
python -m pip config unset global.index-url   # 撤销，回到 pip 默认源
```

> `global.index-url` 里的 `global` 是**配置节名**（对所有 pip 子命令生效），不是「写进 global 级文件」；未传 `--user` / `--global` / `--site` 时，`pip config set` 默认改 user 文件。Windows 官方示例也写成 `py -m pip config ...`。`[R22]`

**pip：单次会话用环境变量覆盖** `[R21]`

```powershell
$env:PIP_INDEX_URL = "https://mirrors.aliyun.com/pypi/simple/"   # 仅当前 PowerShell 会话
```

```bash
export PIP_INDEX_URL="https://mirrors.aliyun.com/pypi/simple/"   # 仅当前 shell 会话
```

> 优先级：命令行 `--index-url` > `PIP_INDEX_URL` > 配置文件；配置文件内部 `[命令名]` 段又覆盖 `[global]` 段。想让改动可追溯，优先用一次性命令行参数或 CI 注入环境变量，而不是改全局文件。`[R21]`

**镜像地址的可靠性说明**：`https://mirrors.aliyun.com/pypi/simple/` 已直连确认返回 PyPI Simple 索引页；镜像服务方帮助页给的是 `http://` + `trusted-host` 的老写法与 legacy 配置路径，本课改用 HTTPS、不加 `trusted-host`、按 `[R21]` 的当前 user 路径。镜像站自述采用增量同步、与官方 PyPI 内容不完全一致，换源等于信任第三方，生产环境要配合哈希 / 锁定（第 30 章）。`[R21]` `[R23]`

**pyenv：源码包下载镜像与缓存**（macOS / Linux；pyenv-win 装的是 Windows 安装包，机制不同）`[R20]` `[R19]`

```bash
mkdir -p ~/.pyenv/cache                                    # 建目录即启用下载缓存 [R20]
export PYTHON_BUILD_MIRROR_URL="https://<自建镜像根>"      # 覆盖默认镜像根 [R20]
export PYTHON_BUILD_SKIP_MIRROR=1                         # 强制从官方原始地址下载 [R20]
pyenv install 3.12
```

> 默认行为是**先试** `https://pyenv.github.io/pythons/`、失败回退官方 URL；配合 `PYTHON_BUILD_MIRROR_NO_FALLBACK=1` 可禁止回退、让失败显性化。`[R20]`
>
> 下载需要代理时用 `http_proxy` / `https_proxy`（pyenv 主 README 明确给出），这与 `PYTHON_BUILD_MIRROR_URL` 是两回事。`[R18]`
>
> 自建镜像的根 URL 后面会拼上包的 SHA-2 校验和，不是把 `python.org/ftp/python` 的目录直接复制过去就能用；`python-build` 在装有 `shasum` / `openssl` / `sha256sum` 时会自动校验下载包。`[R20]`

## 7. 依据索引

| 编号 | 类型 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org | https://www.python.org/downloads/ | 官方安装包下载入口（由 `[R3]` `[R4]` 指向） |
| `[R2]` | python.org | https://devguide.python.org/versions/ | 分支状态、3.12 security、EOL 日期、状态含义 |
| `[R3]` | python.org | https://docs.python.org/3.12/using/windows.html | 3.12 full installer、Add Python to PATH、`py --list`、UTF-8 Mode、Store/nuget/embeddable 定位 |
| `[R4]` | python.org | https://docs.python.org/3/using/windows.html | 3.14+ Python install manager、full installer deprecated、推荐 `python -m pip` |
| `[R5]` | python.org | https://docs.python.org/3.12/library/venv.html | venv 创建/激活命令表、不入库/可丢弃/不可搬移、`sys.prefix != sys.base_prefix`、`RemoteSigned`、`VIRTUAL_ENV` 不可靠 |
| `[R6]` | python.org | https://docs.python.org/3/library/venv.html | 3.13+ 默认生成 `.gitignore`、`--without-scm-ignore-files` |
| `[R7]` | PyPA 官方 | https://packaging.python.org/en/latest/tutorials/installing-packages/ | 验证 Python/pip、venv 动机、`python -m pip` 写法、版本约束、`-r requirements.txt`、不要 sudo、`--user` 在 venv 内无效 |
| `[R8]` | PyPA 官方 | https://pip.pypa.io/en/stable/cli/pip_freeze/ | `pip freeze` 输出格式、不是 lockfile、排除引导工具、导出示例 |
| `[R9]` | PEP 官方 | https://peps.python.org/pep-0405/ | venv 设计动机、`pyvenv.cfg`、`sys.prefix`/`sys.base_prefix` 分裂、隔离机制 |
| `[R10]` | PEP 官方 | https://peps.python.org/pep-0668/ | `EXTERNALLY-MANAGED`、`--break-system-packages`、venv 判定、上游 CPython 行为不变 |
| `[R11]` | python.org | https://docs.python.org/3.12/reference/import.html | `.pyc` 缓存生成与失效重建机制 |
| `[R12]` | GitHub 官方 | https://github.com/github/gitignore/blob/main/Python.gitignore | Python 项目 `.gitignore` 官方模板（本次 raw 未直连成功，见 6.2 说明） |
| `[R13]` | GitHub 官方 | https://github.com/python/cpython/tree/3.12/Lib/venv/ | CPython `venv` 标准库源码（`[R5]` 页面给出的 Source code 链接） |
| `[R14]` | python.org | https://docs.python.org/3.12/glossary.html | CPython 是「在 `python.org` 分发的规范实现」、`interactive` / `>>>` / IDLE 词条 |
| `[R15]` | python.org | https://docs.python.org/3.12/library/index.html | 标准库分类（`os` / `sys` / `urllib` / `pathlib`）、Windows 安装包通常含完整标准库、`venv` / `ensurepip` 归属 |
| `[R16]` | python.org | https://docs.python.org/3.12/tutorial/interpreter.html | REPL 交互模式、`>>>` / `...` 提示符、退出方式、`-c` / `-m` / `-i` |
| `[R17]` | python.org | https://docs.python.org/3.12/using/mac.html | macOS framework / `/usr/local/bin` / Applications 布局、Apple 自带 Python 警告、PATH 一致性 |
| `[R18]` | GitHub 官方 | https://github.com/pyenv/pyenv | pyenv 定位（纯 shell / shim / 不管 virtualenv）、**不支持 Windows**、Homebrew 与自动安装器、`pyenv init --install`、版本选择优先级、源码构建、`http_proxy`、`install -l` / `global` / `local` / `shell` / `which` / `uninstall` |
| `[R19]` | GitHub 官方 | https://github.com/pyenv-win/pyenv-win | Windows fork 定位、Quick Start 安装脚本与多种安装方式、`pyenv --version` / `versions` / `version` / `rehash`、命令列表、`bin` / `shims` 的 PATH 配置与应用执行别名冲突、`pyenv local` 不是 venv |
| `[R20]` | GitHub 官方 | https://github.com/pyenv/pyenv/tree/master/plugins/python-build | `python-build` README：默认 GitHub Pages 镜像与回退逻辑、`PYTHON_BUILD_MIRROR_URL` / `SKIP_MIRROR` / `NO_FALLBACK` / `CACHE_PATH` / `MIRROR_URL_SKIP_CHECKSUM`、SHA-2 校验、镜像按校验和拼接、构建依赖与 `install-prerequisites` 适用平台 |
| `[R21]` | PyPA 官方 | https://pip.pypa.io/en/stable/topics/configuration/ | pip 三种配置机制与优先级、`global` / `user` / `site` 路径与 legacy 路径、INI 写法、`PIP_<UPPER_LONG_NAME>` 命名、macOS XDG 差异（26.2 起） |
| `[R22]` | PyPA 官方 | https://pip.pypa.io/en/stable/cli/pip_config/ | `pip config list` / `set` / `get` / `unset` / `edit` / `debug` 用法、`global.index-url` 键名、默认修改 user 文件、`py -m pip config` Windows 写法 |
| `[R23]` | 镜像服务方（辅助） | https://developer.aliyun.com/mirror/pypi | 镜像地址、镜像站自述的增量同步与安全声明；HTTPS 索引 https://mirrors.aliyun.com/pypi/simple/ 已直连确认返回 Simple Index；页面给出的是 legacy 路径与 `http://` + `trusted-host` 老写法，**非规范依据** |

## 8. 毕业自查清单

- [ ] 能画出「解释器 → venv → 依赖」三层关系，并说明 venv 为什么不复制标准库
- [ ] 能说出 3.12 当前处于哪个支持阶段，以及为什么本章仍可用它学语法
- [ ] 能说清 3.12 与 3.14+ 在 Windows 安装方式上的差异，且不会把 `py install` 套到本机
- [ ] 能解释激活 venv 到底改了什么，以及为什么 `VIRTUAL_ENV` 不能用来判定
- [ ] 能独立完成第 4 节的 7 步流程，并用 `examples/check_env.py` 验证 `True` / `False`
- [ ] 能说出 `pip freeze` 与 lockfile 的区别，并知道完整锁定留到第 30 章
- [ ] 能说出 `.venv/` 不入库的两条官方理由，以及 `.pyc` 缓存为何可忽略
- [ ] 能列出安装包 5 类核心组件，并说出 `os` / `sys` / `urllib` / `pathlib` 为什么不需要 `pip install`
- [ ] 能说清 REPL 的进入与退出方式，并用 `python -c` 做只读自检
- [ ] 能说清版本管理器与虚拟环境的分工，以及 Windows 上为什么不该照抄 macOS 的 pyenv 教程
- [ ] 能写出 `pyenv global` / `local` / `shell` 三个作用域的差别，以及 `py` launcher 在本机的对应命令
- [ ] 能说清 pyenv 是什么（纯 shell + shim + 三级作用域），以及它为什么不管 virtualenv
- [ ] 能说出 macOS 安装 pyenv 的四个阶段，以及 Windows 为什么要用 pyenv-win 或官方 `py`
- [ ] 能写出 `pyenv install -l` / `versions` / `version` / `which` / `rehash` 各自的用途
- [ ] 能区分 pip 包索引镜像与 pyenv 源码包镜像，说出 `index-url` 与 `PYTHON_BUILD_MIRROR_URL` 分别由谁读取
- [ ] 能用 `python -m pip config list` / `debug` 查看本机换源状态，并说出命令行 / 环境变量 / 配置文件的优先级
- [ ] 能说明为什么换源要坚持 HTTPS、不乱加 `trusted-host`，以及镜像同步滞后的风险

## 9. 下一章衔接

第 03 章 `python基本语法`：环境已经确定，开始正式学语法——字面量、变量、运算符、控制流与基本 I/O。REPL 是第 03 章随手验证表达式的练习场。本章刻意回避的 `import`、属性访问、比较运算会在第 03、08、21 章系统展开；`os` / `pathlib` 等标准库在第 21–22 章模块化与标准库部分正式使用；到第 04 章容器类型时，就能真正开始处理第 01 章示例里那些「工具参数与结果」。版本管理器、镜像源、虚拟环境都属于一次性的环境配置，后续章节不再重复；所有示例都假定 `python` 指向一个确定的 3.12 解释器。
