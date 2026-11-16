# 30 项目管理工具 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把课件里的「pyenv 卸载、UV 简介、安装、Python 版本管理、创建项目、虚拟环境管理、Running Tools、构建发布、Makefile、命令速查」逐条展开，并补上课件没写但会踩的部分：锁文件语义、`--offline`/`--locked`/`--frozen` 的差别、`uv export`、`uv tool` 与项目依赖的取舍、Windows 没有 `make` 怎么办，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | uv 0.12.2 / Python 3.12.8（Windows 实测） |
| 前置 | 第 02、23、29 章（venv、依赖、构建） |
| 覆盖范围 | pyenv 迁移、安装与镜像、Python 版本固定、项目生命周期（init/add/remove/sync/run/tree）、虚拟环境、`uvx`/`uv tool`、`uv build`/`uv publish`、`Makefile`、锁文件与漂移检测 |
| 明确不覆盖 | Poetry/PDM/Hatch 的完整用法对比、私有索引鉴权细节、CI 平台特有语法 |
| 学完验收 | 能独立建一个可复现的 uv 项目、能解释 `uv.lock` 的作用、能写出可用的 `Makefile`（见第 15 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Gn]` `` 指向第 14 节官方链接；标「实测」的是本机 uv 0.12.2 / Windows 运行结果。

**本机环境基线**（实测）：

```text
uv 0.12.2 (46ead6098 2026-08-05 x86_64-pc-windows-msvc)
uvx 0.12.2
git 2.56.1.windows.1
python 3.12.8
make => NOT_FOUND          # Windows 默认没有 make
hatch / twine / build / poetry / pdm => NOT_FOUND
uv cache dir => C:\Users\Administrator\AppData\Local\uv\cache
```

**推荐顺序**：

```text
1 pyenv 卸载（第 1 节）      → 只有装了 pyenv 才需要
2 UV 简介（第 2 节）         → 它替代了谁
3 安装（第 3 节）            → 三平台 + 镜像
4 版本管理（第 4 节）        → 固定解释器
5 创建一个项目（第 5 节）    → 主线（重点）
6 虚拟环境（第 6 节）
7 Running Tools（第 7 节）
8 构建发布（第 8 节）
9 Makefile（第 9 节）        → 统一入口
10 命令速查（第 10 节）
11 注意事项（第 12 节）      → 41 条错误对照
```

**与 README 的分工**：README 给结论与边界，本文件负责命令语义、实测输出与坑。冲突时以本文件为准。

## 1. [可选] pyenv 卸载

### 1.1 为什么要卸

课件原文：之前用 `pyenv` 管理多版本 Python，现在 UV 集成了 Python 版本管理（`uv python install` / `list` / `pin`），不再需要 `pyenv`。

| 能力 | pyenv | uv | 依据 |
| --- | --- | --- | --- |
| 安装 Python | ✅（常需编译） | ✅（预编译，下载即用） | `[G4]` |
| 切换版本 | `pyenv local`/`global` | `uv python pin` | `[G4]` |
| 与虚拟环境联动 | 需 `pyenv-virtualenv` 插件 | 内建 | `[G2]` |
| 与依赖管理联动 | ❌ | ✅ 同一工具 | `[G2]` |

> 注意：pyenv 与 uv **可以共存**，但两个 shim 层同时改 `PATH` 会导致「`python` 到底是谁」混乱。要么统一到 uv，要么把 pyenv 的 shims 从 `PATH` 移除。`[G4]`

### 1.2 macOS（Homebrew 安装）

```shell
# 1. 卸载 pyenv
brew uninstall pyenv

# 2. 删除残留的 pyenv 目录和数据
rm -rf ~/.pyenv

# 3. 编辑 ~/.zshrc，移除以下内容：
#    - eval "$(pyenv init -)"
#    - export PYTHON_BUILD_MIRROR_URL="..."
#    然后执行 source ~/.zshrc 刷新
```

### 1.3 Windows（pyenv-win）

```powershell
# 1. 删除安装目录（默认路径）
rm -r $env:USERPROFILE\.pyenv

# 2. 打开「系统环境变量」，删除：
#    - 用户变量中的 PYENV
#    - 用户变量中的 PYTHON_BUILD_MIRROR_URL
#    - Path 中的 %USERPROFILE%\.pyenv\pyenv-win\bin
#    - Path 中的 %USERPROFILE%\.pyenv\pyenv-win\shims
```

| 步骤 | 容易漏的点 | 后果 |
| --- | --- | --- |
| 删安装目录 | 只删了 `bin` 没删 `versions` | 残留占空间 |
| 删环境变量 | `PYENV_ROOT` 还在 | 新 shell 仍报 pyenv 配置 |
| 清 Path | 顺序在前 | `python` 仍指向 pyenv shim |

### 1.4 验证

```shell
pyenv --version
# 输出类似：command not found: pyenv
# 说明卸载成功
```

```powershell
# Windows 建议同时确认
where.exe python
python --version
uv python find
```

| 检查项 | 期望 |
| --- | --- |
| `pyenv --version` | 命令不存在 |
| `where python` | 只剩系统 Python 或 uv 管理的 |
| `uv python find` | 返回可用解释器路径（实测：`C:\...\Python312\python.exe`） |

## 2. UV 简介

### 2.1 一句话

uv 是用 Rust 写的 Python 包与项目管理器，把「装包、锁依赖、管虚拟环境、管 Python 版本、跑工具、构建发布」收进一个可执行文件。`[G1]`

### 2.2 它替代了谁

| 被替代的工具 | uv 对应命令 | 说明 | 依据 |
| --- | --- | --- | --- |
| `pip` | `uv pip` | 安装包 | `[G1]` |
| `pip-tools` | `uv lock` / `uv sync` | 锁定版本、同步环境 | `[G1]` |
| `pipx` | `uv tool` | 安装/运行 CLI 工具 | `[G3]` |
| `virtualenv` / `venv` | `uv venv` | 管虚拟环境 | `[G2]` |
| `pyenv` | `uv python` | 管多版本 Python | `[G4]` |
| `poetry` / `pdm` | `uv init` / `add` / `remove` | 项目与依赖管理 | `[G2]` |
| `build` | `uv build` | 构建 sdist/wheel | `[G1]` |
| `twine` | `uv publish` | 上传到仓库 | `[G1]` |

> 注意：「替代」不等于「完全兼容」。`uv pip` 兼容 pip 的常用参数，但不支持 pip 的全部插件生态（如 `pip` 的第三方插件、`--config-settings` 的少数用法）。`[G1]`

### 2.3 快的来源

| 原因 | 说明 | 依据 |
| --- | --- | --- |
| Rust 实现 | 无 GIL、并行下载 | `[G1]` |
| 全局缓存 + 硬链接 | 多项目共享同一份包文件 | `[G1]` |
| 并行解析与安装 | 默认多线程 | `[G1]` |
| 预编译 Python | 不本地编译 | `[G4]` |

**实测的速度证据**（本机离线解析）：

```text
Resolved 1 package in 1ms
Resolved 4 packages in 2ms
Creating virtual environment at: .venv
```

| 观察 | 说明 |
| --- | --- |
| 解析耗时毫秒级 | 有缓存后几乎无感 |
| venv 创建秒级 | 不复制标准库 |

## 3. 安装

### 3.1 三平台

```shell
# macOS / Linux
curl -LsSf https://astral.sh/uv/install.sh | sh

# Windows (PowerShell)
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"

# macOS 也可用 brew
brew install uv

# Windows 也可用 winget / scoop
winget install --id=astral-sh.uv -e
```

安装后确认：

```shell
uv --version
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 安装脚本会把 uv 加到 `PATH` | macOS/Linux 在 `~/.local/bin` | `[G1]` |
| Windows 装到 `%USERPROFILE%\.local\bin` | 需新开终端生效 | `[G1]` |
| 自更新 | `uv self update` | `[G1]` |
| 也可用 pip 装 | `pip install uv`（不推荐，会绑死某个解释器） | `[G1]` |

### 3.2 配置镜像源（国内加速）

课件给的 `~/.config/uv/uv.toml`：

```toml
[[index]]
name = "aliyun-private"
url = "阿里云私有源地址"
default = true

[[index]]
name = "tuna"
url = "https://pypi.tuna.tsinghua.edu.cn/simple"
```

| 平台 | 配置文件位置 | 依据 |
| --- | --- | --- |
| Linux/macOS | `~/.config/uv/uv.toml` | `[G9]` |
| Windows | `%APPDATA%\uv\uv.toml` | `[G9]` |
| 项目级 | `<project>/uv.toml` 或 `pyproject.toml` 的 `[[tool.uv.index]]` | `[G9]` |
| 环境变量 | `UV_INDEX_URL` / `UV_DEFAULT_INDEX` | `[G9]` |

| 配置项 | 作用 | 依据 |
| --- | --- | --- |
| `[[index]].name` | 索引标识，供 `[tool.uv.sources]` 引用 | `[G9]` |
| `[[index]].url` | 索引地址（`/simple` 结尾） | `[G9]` |
| `[[index]].default` | 是否作为主索引 | `[G9]` |
| `[[index]].explicit` | 仅显式引用时才用（防依赖混淆） | `[G9]` |
| `allow-insecure-host` | 允许 HTTP 主机 | `[G9]` |

> 注意：多个 `[[index]]` 时 uv 默认会**跨索引取最高版本**，与 pip 的 `extra-index-url` 风险相同。企业私有源建议 `explicit = true` 并配合 `[tool.uv.sources]` 显式指定，避免同名包被公共源抢占。`[G9]`

### 3.3 VSCode Code Runner 配置

课件给的是：

```json
"python": "uv run"
```

完整写法（`.vscode/settings.json`）：

```json
{
  "code-runner.executorMap": {
    "python": "uv run"
  },
  "code-runner.runInTerminal": true
}
```

| 配置 | 作用 |
| --- | --- |
| `executorMap.python` | 把 `python file.py` 换成 `uv run file.py` |
| `runInTerminal` | 需要交互/输入的脚本必须开 |

| 替代方案 | 说明 | 依据 |
| --- | --- | --- |
| 选 `.venv` 解释器 | `Python: Select Interpreter` 指向 `.venv` | 第 02 章 |
| `uv run` 手动跑 | 不依赖插件 | `[G2]` |
| tasks.json | 定义 `uv run` 任务 | `[G7]` |

## 4. Python 版本管理

```shell
# 查看所有可用的 Python 版本（可安装的）
uv python list

# 查看本地已安装的 Python 版本
uv python list --only-installed

# 安装特定 Python 版本
uv python install 3.12.3

# 安装最新稳定版
uv python install

# 安装多个版本
uv python install 3.11.9 3.12.3

# 卸载特定版本
uv python uninstall 3.12.3

# 查看当前环境使用的 Python 路径
uv python find

# 为当前项目固定版本（生成 .python-version）
uv python pin 3.12

# 移除固定（删除 .python-version）
uv python pin --rm

# 查看当前项目固定了哪个版本
uv python pin

# 用指定版本执行临时命令（不改项目设置）
uv run --python 3.11 python --version

# 创建虚拟环境时指定版本
uv venv --python 3.12

# 查看所有已安装版本及路径
uv python list --only-installed --verbose
```

实测：

```text
uv python list --only-installed
cpython-3.12.8-windows-x86_64-none    C:\Users\Administrator\AppData\Local\Programs\Python\Python312\python.exe

uv python find（在项目内）
C:\...\app\.venv\Scripts\python.exe
```

| 命令 | 副作用 | 依据 |
| --- | --- | --- |
| `uv python install` | 下载到 uv 的 Python 目录 | `[G4]` |
| `uv python pin` | **写** `.python-version` | `[G4]` |
| `uv python find` | 只读 | `[G4]` |
| `uv run --python` | 一次性覆盖，不改配置 | `[G4]` |

| `.python-version` 的作用 | 说明 | 依据 |
| --- | --- | --- |
| 声明项目要求 | `uv sync`/`uv run` 按它选解释器 | `[G4]` |
| 必须入库 | 团队一致 | `[G4]` |
| 与 `requires-python` 分工 | 前者是「开发用哪个」，后者是「包支持哪些」 | `[G6]` |

> 注意：`.python-version` 与 `requires-python` 不是一回事。`.python-version` 决定**本地用哪个解释器**，`requires-python` 决定**这个包能被哪些版本安装**。两者冲突时（如 pin 3.13 但 `requires-python >=3.12,<3.13`），`uv sync` 会报错。`[G4]` `[G6]`

## 5. 快速上手：创建一个项目

### 5.1 初始化项目

```shell
# 创建目录并初始化
uv init my-project
cd my-project

# 对当前目录初始化
uv init

# 不创建 git 仓库
uv init --vcs none

# 生成 src layout 结构的目录（库）
uv init --lib
```

实测 `uv init --vcs none --no-readme --python 3.12 demo-app` 生成：

```text
30_FILES ['.python-version', 'pyproject.toml', 'src']
30_PYVER 3.12
```

```toml
[project]
name = "demo-app"
version = "0.1.0"
description = "Add your description here"
authors = [
    { name = "lhl", email = "1079161148@qq.com" }
]
requires-python = ">=3.12"
dependencies = []

[project.scripts]
demo-app = "demo_app:main"

[build-system]
requires = ["uv_build>=0.12.2,<0.13.0"]
build-backend = "uv_build"
```

| 生成物 | 作用 | 依据 |
| --- | --- | --- |
| `pyproject.toml` | 项目元数据 + 构建后端 | `[G2]` |
| `.python-version` | 固定解释器版本 | `[G4]` |
| `src/demo_app/__init__.py` | 包源码目录 | `[G2]` |
| `uv.lock` | 首次 `uv add`/`uv lock` 后生成 | `[G2]` |
| `.venv` | 首次 `uv sync`/`uv run` 后生成 | `[G2]` |

| `uv init` 变体 | 效果 | 依据 |
| --- | --- | --- |
| `--app`（默认） | 应用，带 `[project.scripts]` | `[G2]` |
| `--lib` | 库，src 布局 + 可发布 | `[G2]` |
| `--package` | 可被安装为包 | `[G2]` |
| `--bare` | 只生成 `pyproject.toml` | `[G2]` |
| `--no-workspace` | 不继承上层 workspace | `[G2]` |
| `--build-backend uv\|hatch\|setuptools\|...` | 指定后端 | `[G2]` |

### 5.2 配置脚本

课件原文：`uv init` 默认没有入口模块配置，要让项目能通过 `uv run` 执行或发布后提供命令行工具，需要配置 `[project.scripts]`：

```toml
[project.scripts]
# 等号左边是命令名称，右边是 "模块路径:函数名"
my-cli = "my_project:main"
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 格式是 `模块:函数` | 冒号不是点 | `[G6]` |
| 模块名用**导入名** | `my_project` 不是 `my-project` | 第 29 章 |
| 装好后进 `bin`/`Scripts` | 由 `entry_points.txt` 驱动 | 第 29 章 |
| `uv run my-cli` 直接可用 | 项目环境里已注册 | `[G2]` |

> 注意：`[project.scripts]` 只在**项目被安装进环境**时生效。`uv run` 会自动以可编辑模式安装本项目，所以能用；而 `uv pip install -r requirements.txt` 这种全局模式不会注册入口点。`[G2]`

### 5.3 安装依赖

```shell
uv add requests                 # 添加运行时依赖
uv add --dev pytest             # 添加开发依赖
uv add "fastapi>=0.100.0"       # 带版本约束
```

`uv add` 会自动做四件事：

```text
1 解析依赖树，找满足所有约束的版本
2 安装到项目 .venv
3 更新 pyproject.toml 的 dependencies
4 生成/更新 uv.lock
```

| 行为 | 依赖网络 | 依据 |
| --- | --- | --- |
| 解析 → 需要索引（或缓存） | ✅ | `[G2]` |
| 写 `pyproject.toml` | —— | `[G2]` |
| 写 `uv.lock` | —— | `[G2]` |

实测离线失败（缓存里没有 `requests`）：

```text
30_ADD_OFFLINE rc=1
× No solution found when resolving dependencies:
╰─▶ Because requests was not found in the cache and your project depends on requests,
    we can conclude that your project's requirements are unsatisfiable.
```

| 结论 | 说明 |
| --- | --- |
| `--offline` 只能命中缓存，不会联网 | 这是 CI 里「禁止联网构建」的开关 |
| 失败信息明确指向「缓存里没有」 | 不是版本冲突 |

`--dev` 写到哪：uv 0.12 默认写入 `[dependency-groups].dev`（PEP 735 标准依赖组）。**本机因离线无缓存未能实测该项**，以官方文档为准。`[G2]`

### 5.4 移除依赖

```shell
uv remove requests
```

| 行为 | 说明 | 依据 |
| --- | --- | --- |
| 从 `dependencies` 删除 | 同步改 `pyproject.toml` | `[G2]` |
| 更新 `uv.lock` | 重新解析 | `[G2]` |
| 从 `.venv` 卸载 | 下次 `uv sync` 生效 | `[G2]` |

### 5.5 同步环境

```shell
uv sync
```

实测：

```text
30_SYNC rc=0  Creating virtual environment at: .venv | Resolved 1 package | Building demo-app
30_SYNC_LOCKED rc=0  （--locked：锁文件必须已存在且一致）
```

| 命令 | 语义 | 依据 |
| --- | --- | --- |
| `uv sync` | 按 `uv.lock`（无则先解析）安装，可能更新锁 | `[G2]` |
| `uv sync --locked` | 要求锁文件已是最新，否则报错 | `[G2]` |
| `uv sync --frozen` | 完全不检查是否最新，按现有锁装 | `[G2]` |
| `uv sync --no-dev` | 不装开发组 | `[G2]` |
| `uv sync --all-packages` | workspace 全部成员 | 第 31 章 |
| `uv lock` | 只更新锁文件，不装 | `[G2]` |
| `uv lock --check` | 只检查锁是否需要更新 | `[G2]` |

**漂移检测实测**：

```text
30D_CHECK_CLEAN_RC 0
# 把 version 从 0.1.0 改成 0.2.0 后
30D_CHECK_DRIFT_RC 1
error: The lockfile at `uv.lock` needs to be updated, but `--check` was provided.
hint: To update the lockfile, run `uv lock`.
```

| 场景 | CI 该用 | 理由 | 依据 |
| --- | --- | --- | --- |
| 校验锁未漂移 | `uv lock --check` | 不改任何文件 | `[G2]` |
| 部署安装 | `uv sync --frozen` | 不改锁，装现有 | `[G2]` |
| 本地开发 | `uv sync` | 允许更新锁 | `[G2]` |

> 注意：`--locked` 与 `--frozen` 都能让 CI 失败于「锁过期」，但语义不同：`--locked` 会**验证**锁是否与 `pyproject.toml` 一致，`--frozen` **跳过验证**直接装。CI 里用 `--locked` 更安全。`[G2]`

### 5.6 运行项目

```shell
uv run src/main.py
uv run -m src.main
uv run python -c "import sys; print(sys.prefix)"
```

实测：

```text
30_RUN rc=0  C:\...\demo-app\.venv
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `uv run` 自动确保环境同步 | 缺依赖会先装 | `[G2]` |
| 无需手动激活 venv | 直接执行 | `[G2]` |
| `--package` 指定 workspace 成员 | 第 31 章 | `[G2]` |
| `--with pkg` 临时加依赖 | 一次运行 | `[G2]` |

### 5.7 查看依赖树

```shell
uv tree
uv tree --package web-service
uv tree --depth 2
```

实测（单项目）：

```text
30_TREE rc=0  demo-app v0.1.0 | Resolved 1 package
```

| 参数 | 作用 | 依据 |
| --- | --- | --- |
| `--package` | 只看某个成员 | `[G2]` |
| `--depth N` | 限制深度 | `[G2]` |
| `--no-dedupe` | 不去重（完整展开） | `[G2]` |

## 6. 虚拟环境管理

### 6.1 创建

```shell
uv venv                 # 当前目录建 .venv
uv venv my-env          # 指定目录
uv venv --python 3.12   # 指定解释器
uv venv --python 3.11
```

实测：

```text
30B_VENV rc=0  Creating virtual environment at: .venv | Activate with: .venv\Scripts\activate
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 默认目录 `.venv` | 遵循社区约定 | `[G2]` |
| 秒级创建 | 不复制标准库 | `[G2]` |
| `--seed` 可预装 pip/setuptools | 默认不装 pip | `[G2]` |

### 6.2 激活与退出

```shell
# macOS / Linux
source .venv/bin/activate
deactivate

# Windows PowerShell
.venv\Scripts\Activate.ps1
deactivate

# Windows cmd
.venv\Scripts\activate.bat
```

| 需要激活的场景 | 不需要的场景 | 依据 |
| --- | --- | --- |
| 用裸 `python` / `pytest` 命令 | 用 `uv run` | `[G2]` |
| IDE 未配置解释器 | `uv run` 已注入环境 | `[G2]` |
| 调试器 attach | `uv run` 传入 | 第 32 章 |

> 注意：uv 的核心设计是「**不需要激活**」。`uv run` 会自己找到 `.venv` 并注入环境变量。激活只是为了让「裸命令」也能用，属于可选步骤。`[G2]`

### 6.3 查看环境信息

课件写 `uv venv --list`，实测 **uv 0.12.2 的 `uv venv` 没有 `--list` 选项**（`uv venv --help` 无该项）。查看环境的替代方式：

```shell
uv python find            # 当前项目实际使用的解释器（实测返回 .venv\Scripts\python.exe）
uv run python -c "import sys; print(sys.prefix, sys.version)"
uv pip list               # 环境里装了什么
dir .venv                 # 直接看目录
```

| 需求 | 正确命令 | 依据 |
| --- | --- | --- |
| 当前项目用哪个解释器 | `uv python find` | `[G4]` |
| 装了哪些包 | `uv pip list` / `uv tree` | `[G1]` |
| 缓存位置 | `uv cache dir` | `[G1]` |
| 已安装 Python 版本 | `uv python list --only-installed` | `[G4]` |

### 6.4 项目级 vs 全局级

| 模式 | 命令 | 关联 `pyproject.toml` | 依赖写哪里 | 依据 |
| --- | --- | --- | --- | --- |
| 项目级 | `uv add` / `uv sync` / `uv run` | ✅ | `pyproject.toml` + `uv.lock` | `[G2]` |
| 全局级 | `uv pip install` / `uv venv` | ❌ | 只改当前环境 | `[G1]` |

兼容存量 `requirements.txt`：

```shell
uv pip install -r requirements.txt
uv pip compile requirements.in -o requirements.txt
```

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 新项目用项目级 | 可锁定、可复现 | `[G2]` |
| 存量项目先 `uv pip` 过渡 | 零改造 | `[G1]` |
| 不要混用两种模式改同一环境 | 锁文件与实际不一致 | `[G2]` |

### 6.5 全局缓存

```shell
uv cache dir      # 实测：C:\Users\Administrator\AppData\Local\uv\cache
uv cache clean
uv cache prune
```

| 命令 | 作用 | 依据 |
| --- | --- | --- |
| `cache dir` | 打印缓存目录 | `[G1]` |
| `cache clean` | 清空（会影响其他项目） | `[G1]` |
| `cache prune` | 只清无用条目 | `[G1]` |

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 多项目共享缓存 | 靠硬链接，磁盘占用低 | `[G1]` |
| 缓存不是锁 | 删缓存不影响 `uv.lock` | `[G1]` |
| 离线安装依赖缓存 | `--offline` 只能命中缓存 | 实测 5.3 |

## 7. Running Tools —— 无需安装即可运行

### 7.1 `uvx`：一键运行

```shell
uvx ruff check .
uvx bandit@1.7.5 .
uvx cowsay -- "Hello, UV!"
```

`uvx` 的流程：

```text
1 在临时环境安装指定包
2 运行对应命令
3 结束后清理环境
```

| 等价传统写法 | 说明 | 依据 |
| --- | --- | --- |
| `pip install ruff && ruff check . && pip uninstall ruff` | uvx 一步完成 | `[G3]` |
| `pipx run ruff check .` | 同类工具 | `[G3]` |

| 参数 | 作用 | 依据 |
| --- | --- | --- |
| `pkg@version` | 指定版本 | `[G3]` |
| `--` 后传参数 | 避免与 uvx 自身参数混淆 | `[G3]` |
| `--with pkg` | 额外注入依赖 | `[G3]` |
| `--python 3.12` | 指定解释器 | `[G3]` |

> 注意：`uvx` 是**独立可执行**，不是 `uv x` 子命令。实测 `uv x --help` 报 `error: unrecognized subcommand 'x'`（uv 0.12.2），提示最接近的是 `export`。两者别写混。`[G3]`

### 7.2 `uv tool`：持久安装 CLI 工具

```shell
uv tool install ruff
ruff check .
uv tool list
uv tool upgrade ruff
uv tool uninstall ruff
```

实测本机已有一个工具：

```text
30B_TOOL_LIST  browser-act-cli v1.1.0 | - browser-act
```

| 命令 | 作用 | 依据 |
| --- | --- | --- |
| `uv tool install` | 装到独立环境 + 暴露可执行 | `[G3]` |
| `uv tool run` / `uvx` | 临时运行 | `[G3]` |
| `uv tool list` | 列出已装工具 | `[G3]` |
| `uv tool upgrade --all` | 全量升级 | `[G3]` |
| `uv tool dir` | 工具安装目录 | `[G3]` |

| 对比 | `uvx` | `uv tool install` | 依据 |
| --- | --- | --- | --- |
| 持久性 | 临时 | 持久 | `[G3]` |
| 环境隔离 | 临时环境 | 独立环境 | `[G3]` |
| 适合 | 一次性检查（lint/format） | 日常 CLI（如 `httpie`） | `[G3]` |

### 7.3 在项目中添加工具依赖

```shell
uv add --dev ruff black mypy
uv run ruff check .
uv run black .
uv run mypy src/
```

| 方式 | 优点 | 缺点 | 依据 |
| --- | --- | --- | --- |
| `uv add --dev` | 团队一致、锁版本 | 进项目依赖图 | `[G2]` |
| `uvx` | 不污染项目 | 版本不受控 | `[G3]` |
| `uv tool install` | 全局可用 | 与本项目版本可能不一致 | `[G3]` |

> 注意：团队协作推荐 `uv add --dev`，因为 `uv sync` 后所有人拿到同一版本；`uvx` 适合「临时看一眼」，不适合进 CI 卡版本。`[G3]`

## 8. 构建与发布

### 8.1 构建

```shell
uv build                  # sdist + wheel，产物进 dist/
uv build --package shared # 只构建 workspace 成员
uv build --out-dir out
```

实测：

```text
30_BUILD_APP rc=0  Building source distribution... | Successfully built dist\demo_app-0.1.0.tar.gz
                   Successfully built dist\demo_app-0.1.0-py3-none-any.whl
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 读 `[build-system]` 决定后端 | `uv_build` 随 uv 分发 | `[G1]` |
| 离线可构建（uv_build） | 实测成功 | 实测 |
| 换 hatchling 需联网 | 装不上后端就失败 | 第 29 章 |
| 产物命名规范 | PEP 427 | 第 29 章 |

### 8.2 发布

```shell
uv publish
UV_PUBLISH_TOKEN=pypi-xxxxx uv publish
uv publish --publish-url 私有仓库地址 --username 用户名 --password 密码 dist/*
```

| 参数 | 作用 | 依据 |
| --- | --- | --- |
| `UV_PUBLISH_TOKEN` | 令牌（推荐） | `[G1]` |
| `--publish-url` | 目标索引 | `[G1]` |
| `--username`/`--password` | 私有源认证 | `[G1]` |
| `--check-url` | 已存在则跳过 | `[G1]` |
| `.pypirc` | 兼容传统配置 | `[G1]` |

| 对比 | `twine` | `uv publish` | 依据 |
| --- | --- | --- | --- |
| 需额外安装 | ✅ | ❌ | `[G1]` |
| `check` 命令 | `twine check` | 无直接等价 | 第 29 章 |
| 速度/并发 | 单线程 | 并行 | `[G1]` |

> 注意：`uv publish` 没有 `twine check` 的等价校验。发布前仍建议 `uvx twine check dist/*` 跑一遍元数据校验。`[G1]` `[P7]`

## 9. Makefile —— 统一项目命令入口

### 9.1 Windows 先装 make

课件原文：

```shell
# 方式一：Chocolatey
choco install make

# 方式二：winget
winget install GnuWin32.Make

# 方式三：通过 Git Bash（安装 Git 时勾选）
# 然后在 Git Bash 中运行 make，或将其加入 PATH
```

实测本机：`make => NOT_FOUND`。

| 方案 | 优点 | 缺点 | 依据 |
| --- | --- | --- | --- |
| Chocolatey / winget | 走 PATH，全局可用 | 需装包管理器 | `[G8]` |
| Git Bash 自带 | 已有 Git 就有 | 只能在 Git Bash 里用 | `[G8]` |
| 不用 make，用 `uv run` | 零依赖 | 命令仍散落 | `[G2]` |
| `poethepoet` / `taskipy` | 纯 Python、跨平台 | 多一个依赖 | `[G7]` |

### 9.2 一个典型的 Python + UV 项目 Makefile

```makefile
.PHONY: install test lint format build clean

install:
	uv sync

test:
	uv run pytest

lint:
	uv run ruff check .

format:
	uv run ruff format .

build:
	uv build

clean:
	rm -rf dist/
	rm -rf .pytest_cache/
	uv cache clean
```

| 语法 | 含义 | 依据 |
| --- | --- | --- |
| `.PHONY` | 声明「不是文件名」，避免同名文件跳过 | `[G8]` |
| `目标:` | 目标名 | `[G8]` |
| **Tab 缩进** | 命令行必须用 Tab，空格会报 `missing separator` | `[G8]` |
| `rm -rf` | Windows 的 cmd 没有 `rm`，需用 Git Bash 或改 `rmdir /s /q` | `[G8]` |

> 注意：Makefile **必须用真正的 Tab**，很多编辑器会转成空格，报错 `Makefile:2: *** missing separator. Stop.`。VSCode 里对 `Makefile` 单独设置 `insertSpaces: false`。`[G8]`

### 9.3 带参数的目标

```makefile
.PHONY: publish

# 发布到指定仓库，用法: make publish REPO_URL=https://...
publish:
	uv publish --publish-url $(REPO_URL)
```

| 用法 | 说明 | 依据 |
| --- | --- | --- |
| `make publish REPO_URL=https://x` | 命令行传变量 | `[G8]` |
| `REPO_URL ?= 默认值` | 未传时用默认 | `[G8]` |
| `$(VAR)` | 引用变量 | `[G8]` |

### 9.4 串联多个任务

课件原文：

```makefile
.PHONY: ci

ci: 
	lint test build
```

**这个写法有问题**：`lint test build` 会被当成**一条命令**执行，shell 会报 `lint: command not found`。正确写法是把它们作为**依赖**：

```makefile
.PHONY: ci
ci: lint test build
```

或显式串联（任一步失败即停）：

```makefile
.PHONY: ci
ci:
	uv run ruff check .
	uv run pytest
	uv build
```

| 写法 | 行为 | 依据 |
| --- | --- | --- |
| `ci: lint test build` | 三个目标按序执行（依赖） | `[G8]` |
| 多行命令 | 逐条执行，非零退出即停 | `[G8]` |
| `ci: \n\tlint test build` | ❌ 一条命令，报 command not found | `[G8]` |

> 注意：make 的依赖默认**可以并行**（`make -j`），需要严格顺序时要么用多行命令，要么声明顺序依赖。CI 里用多行命令更直观。`[G8]`

### 9.5 推荐模板

```makefile
.PHONY: help install sync lint format type test cov build publish clean ci

# 默认目标：列出可用命令
help:
	@echo "install : 安装依赖"
	@echo "lint    : 代码检查"
	@echo "format  : 格式化"
	@echo "test    : 跑测试"
	@echo "ci      : 检查 + 测试 + 构建"

install:
	uv sync --locked

sync:
	uv sync

lint:
	uv run ruff check .

format:
	uv run ruff format .

type:
	uv run mypy src/

test:
	uv run pytest -q

cov:
	uv run pytest --cov=src --cov-report=term-missing

build:
	uv build

publish:
	uv publish --publish-url $(REPO_URL)

clean:
	uv run python -c "import shutil,pathlib;[shutil.rmtree(p,ignore_errors=True) for p in ('dist','.pytest_cache','.mypy_cache')]"

ci:
	uv sync --locked
	uv run ruff check .
	uv run pytest -q
	uv build
```

| 改进点 | 相比课件模板 | 依据 |
| --- | --- | --- |
| `help` 默认目标 | 新人 `make` 就能看说明 | `[G8]` |
| `install` 用 `--locked` | CI 里防止锁漂移 | `[G2]` |
| `clean` 用 Python 实现 | 跨平台，不依赖 `rm` | `[G8]` |
| `ci` 用多行命令 | 严格顺序、失败即停 | `[G8]` |

## 10. 常用命令速查

| 命令 | 作用 | 依据 |
| --- | --- | --- |
| `uv init` | 初始化项目 | `[G2]` |
| `uv add` | 添加依赖 | `[G2]` |
| `uv remove` | 移除依赖 | `[G2]` |
| `uv sync` | 同步环境 | `[G2]` |
| `uv lock` | 更新锁文件 | `[G2]` |
| `uv lock --check` | 检查锁是否过期 | `[G2]` |
| `uv run` | 在项目环境运行命令 | `[G2]` |
| `uv tree` | 依赖树 | `[G2]` |
| `uv export` | 导出 requirements 格式 | `[G2]` |
| `uv build` | 构建分发包 | `[G1]` |
| `uv publish` | 发布到仓库 | `[G1]` |
| `uv venv` | 创建虚拟环境 | `[G2]` |
| `uv pip list` | 列已装包 | `[G1]` |
| `uv python install` | 安装 Python | `[G4]` |
| `uv python list` | 列出 Python | `[G4]` |
| `uv python pin` | 固定项目版本 | `[G4]` |
| `uv tool install` | 安装 CLI 工具 | `[G3]` |
| `uvx` | 临时运行 CLI 工具 | `[G3]` |
| `uv cache clean` | 清缓存 | `[G1]` |
| `uv self update` | 更新 uv | `[G1]` |

**`uv export` 实测输出**：

```text
# This file was autogenerated by uv via the following command:
#    uv export --offline --no-hashes
-e .
```

| 用途 | 说明 | 依据 |
| --- | --- | --- |
| 交付给只用 pip 的环境 | 生成 `requirements.txt` | `[G2]` |
| Docker 构建 | `uv export` + `pip install -r` | `[G2]` |
| 默认带哈希 | 供应链校验 | `[G2]` |

## 11. 综合示例：只读检查项目工具链状态

```python
"""第 30 章综合示例：只读检查项目工具链状态。"""

from __future__ import annotations

import importlib.util
import pathlib
import shutil
import tomllib


def probe(root: pathlib.Path) -> dict[str, object]:
    pyproject = root / "pyproject.toml"
    data = tomllib.loads(pyproject.read_text(encoding="utf-8")) if pyproject.exists() else {}
    project = data.get("project", {})
    return {
        "has_pyproject": pyproject.exists(),
        "has_lock": (root / "uv.lock").exists(),
        "has_venv": (root / ".venv").exists(),
        "has_python_version": (root / ".python-version").exists(),
        "name": project.get("name"),
        "backend": data.get("build-system", {}).get("build-backend"),
        "dependency_count": len(project.get("dependencies", [])),
        "uv_on_path": shutil.which("uv") is not None,
        "tomllib": importlib.util.find_spec("tomllib") is not None,
    }


print("PROBE", probe(pathlib.Path.cwd()))
```

本机实测输出（在某 uv 项目根目录执行）：

```text
PROBE {'has_pyproject': True, 'has_lock': True, 'has_venv': True, 'has_python_version': True, 'name': 'demo-app', 'backend': 'uv_build', 'dependency_count': 0, 'uv_on_path': True, 'tomllib': True}
```

**逐段说明**：

| 代码 | 机制 | 依据 |
| --- | --- | --- |
| `tomllib.loads` | 3.11+ 标准库只读 TOML | 第 22 章 |
| `shutil.which("uv")` | 判断命令是否在 `PATH` | 第 22 章 |
| `importlib.util.find_spec` | 判断模块可导入 | 第 21 章 |
| 只读 | 不改任何文件 | 第 01 章 |

> 注意：这段代码适合放进 CI 的「环境体检」步骤，检查锁文件是否入库、venv 是否被误提交（`has_venv` 为 `True` 时应确认 `.gitignore` 已忽略）。`[G2]`

## 12. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 把 `.venv/` 提交进仓库 | 仓库膨胀、跨平台失效 | `.gitignore` 忽略 | `[G2]` |
| 把 `uv.lock` 加进 `.gitignore` | 环境不可复现 | 锁文件必须入库 | `[G2]` |
| 手改 `uv.lock` | 下次 `uv sync` 被覆盖 | 用 `uv add`/`uv lock` | `[G2]` |
| CI 用 `uv sync` 不用 `--locked` | 锁漂移不被发现 | `uv sync --locked` | `[G2]` |
| 用 `--frozen` 代替 `--locked` | 跳过一致性校验 | 优先 `--locked` | `[G2]` |
| `uv add --offline` 装新包 | `No solution found`（实测） | 先联网缓存或预拉取 | `[G1]` |
| 混用 `uv pip install` 与 `uv add` | 锁文件与实际不一致 | 项目内只用 `uv add` | `[G2]` |
| `uv pip install` 后忘了 `uv lock` | 别人 `sync` 装不到 | 改依赖一律走 `uv add/remove` | `[G2]` |
| 在系统 Python 上 `uv pip install` | 污染全局 | 先 `uv venv` | `[G1]` |
| 以为要激活 venv 才能跑 | 多余步骤 | `uv run` 自动注入 | `[G2]` |
| 在 venv 里再 `uv venv` | 嵌套环境 | 一个项目一个 `.venv` | `[G2]` |
| `uv venv --list`（按课件写） | `unexpected argument` | 用 `uv python find` | 实测 |
| `uv x ruff`（按 pipx 习惯写） | `unrecognized subcommand 'x'` | `uvx ruff` | 实测 |
| `[project.scripts]` 写 `pkg.cli`（点号） | 入口点解析失败 | 写 `pkg.cli:main` | `[G6]` |
| `[project.scripts]` 模块名用连字符 | `ModuleNotFoundError` | 用下划线导入名 | 第 29 章 |
| `.python-version` 与 `requires-python` 冲突 | `uv sync` 报错 | 两者对齐 | `[G4]` |
| 手改 `.python-version` 成不存在的版本 | `uv run` 触发下载/fail | 用 `uv python pin` | `[G4]` |
| 依赖写 `requests` 无上限 | 大版本破坏性升级 | 关键依赖写 `~=` | 第 29 章 |
| 依赖全写 `==` | 与其他包冲突 | 只在应用层锁定 | `[G5]` |
| 开发工具写进 `dependencies` | 生产镜像变大 | `uv add --dev` | `[G2]` |
| 不分组装依赖 | 生产装 pytest | `--no-dev` | `[G2]` |
| `uv tool install` 装项目依赖也用 | 版本漂移 | 项目内用 `--dev` | `[G3]` |
| `uvx` 用在 CI 里卡版本 | 版本不受控、构建不可复现 | `uvx pkg@1.2.3` 或 `--dev` | `[G3]` |
| 缓存目录放进项目 | 被提交 | 缓存在用户目录 | `[G1]` |
| `uv cache clean` 在 CI 里随手跑 | 下轮构建全量下载 | 只在必要时清 | `[G1]` |
| 镜像源配多个 `[[index]]` 不加 `explicit` | 依赖混淆 | 私有源加 `explicit` | `[G9]` |
| 镜像地址写成 `-i https://x/simple`（pip 语法） | uv 不认 | `[[index]]` 或 `UV_DEFAULT_INDEX` | `[G9]` |
| `make` 在 Windows 直接跑 | `make: 无法将"make"识别为...` | 先装 make 或用 `uv run` | 实测 |
| Makefile 用空格缩进 | `missing separator` | 用 Tab | `[G8]` |
| `ci:` 后写 `lint test build` 一行 | `command not found` | `ci: lint test build` | `[G8]` |
| Makefile 里写 `rm -rf` | Windows cmd 不认 | Git Bash 或改 Python 清理 | `[G8]` |
| `.PHONY` 漏写 | 同名文件导致目标被跳过 | 显式声明 | `[G8]` |
| 在 Makefile 里 `cd` 后写下一行 | 每行独立 shell，`cd` 不生效 | 合并一行或 `cd x && cmd` | `[G8]` |
| `uv build` 后忘了 `dist/` 已在 `.gitignore` | 误提交产物 | 忽略 `dist/` | 第 29 章 |
| 发布前不跑 `twine check` | 元数据非法 | `uvx twine check dist/*` | `[G1]` |
| 把 token 写进 `Makefile` | 泄露 | 环境变量 | 第 01 章 |
| 用 `pip install uv` 装 uv | 绑死解释器、升级麻烦 | 官方安装脚本 | `[G1]` |
| 项目内同时有 `requirements.txt` 和 `uv.lock` | 双份真相 | 二选一 | `[G5]` |
| 用 `pip freeze` 当锁文件 | 只记录当前环境，非解析结果 | 用 `uv lock` | `[G5]` |
| `uv sync` 前先手动 `pip install` | 结果被覆盖 | 只信 `uv.lock` | `[G2]` |
| 在 Jupyter 里 `uv run` | 内核不是 uv 环境 | 先选解释器 | 第 24 章 |

## 13. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 一个项目一个 `.venv` + 一个 `uv.lock` | 环境唯一真相 | `[G2]` |
| 锁文件入库、CI 用 `--locked` | 可复现 | `[G2]` |
| 依赖分运行时/开发两组 | 生产瘦身 | `[G2]` |
| `.python-version` 入库 | 团队一致 | `[G4]` |
| 常用命令进 Makefile | 新人一条命令上手 | `[G8]` |
| `uv run` 优先于激活 venv | 少一步、少出错 | `[G2]` |
| 临时工具用 `uvx`、常驻用 `uv tool` | 各归其位 | `[G3]` |
| 私有源显式声明 `explicit` | 防依赖混淆 | `[G9]` |
| 定期 `uv lock --upgrade` 小步升级 | 避免大版本跳跃 | `[G2]` |
| 发布前 `uvx twine check` | 元数据校验 | 第 29 章 |
| 把工具版本写进配置 | 团队一致 | `[G2]` |
| 用 `uv export` 兼容纯 pip 环境 | 过渡友好 | `[G2]` |

**风格示范**：

```python
"""docs 模块：从包元数据生成环境快照，避免手抄版本号。

为什么读元数据：版本只在 pyproject.toml 维护，文档不会漂移。
"""

from __future__ import annotations

import importlib.metadata
import platform
import sys


def snapshot(distributions: list[str]) -> dict[str, str]:
    """返回 Python 与指定发行版的版本快照。"""
    report = {
        "python": platform.python_version(),
        "implementation": platform.python_implementation(),
        "executable": sys.executable,
    }
    for name in distributions:
        try:
            report[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            report[name] = "NOT_INSTALLED"
    return report
```

**边界**：

- uv 的锁文件是跨平台的，但**依赖解析可能因平台标记不同而不同**（如仅 Windows 的依赖），CI 多平台时要各自校验。
- `--offline` 只能命中缓存，不能替代私有源镜像。
- `Makefile` 只是「命令别名」，不是构建系统；真正的构建语义在后端。

## 14. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[G1]` | 官方文档（Astral） | https://docs.astral.sh/uv/ | uv 总览、`build`/`publish`/`pip`/`cache`/`self update`、离线模式 |
| `[G2]` | 官方文档（Astral） | https://docs.astral.sh/uv/concepts/projects/ | `init`/`add`/`remove`/`sync`/`lock`/`run`/`tree`、`--locked`/`--frozen`、项目目录结构 |
| `[G3]` | 官方文档（Astral） | https://docs.astral.sh/uv/concepts/tools/ | `uvx`、`uv tool install/list/upgrade` |
| `[G4]` | 官方文档（Astral） | https://docs.astral.sh/uv/concepts/python-versions/ | `uv python install/list/pin/find`、`.python-version` |
| `[G5]` | PEP 官方 | https://peps.python.org/pep-0751/ | `pylock.toml` 互操作锁文件规范 |
| `[G6]` | PEP 官方 | https://peps.python.org/pep-0621/ | `[project]`、`[project.scripts]` 入口点格式 |
| `[G7]` | PyPA 官方 | https://packaging.python.org/en/latest/guides/tool-recommendations/ | 工具选型标准、任务运行器 |
| `[G8]` | GNU 官方手册 | https://www.gnu.org/software/make/manual/ | Makefile 语法、`.PHONY`、变量、依赖与 Tab 规则 |
| `[G9]` | 官方文档（Astral） | https://docs.astral.sh/uv/configuration/indexes/ | `[[index]]`、`explicit`、镜像与依赖混淆防护 |
| `[G10]` | PEP 官方 | https://peps.python.org/pep-0008/ | 命名、注释写「为什么」 |

> **核对状态**：`[G10]` 与本章 `README.md` 已核对来源一致；`[G1]`–`[G9]` 按官方文档结构整理，**本次未逐页直连复核**。文中「实测」为本机 uv 0.12.2 / Python 3.12.8 / Windows 的真实输出，全部使用 `--offline`；`uv add --dev` 的写入位置（`[dependency-groups]`，PEP 735）**未实测**，按官方文档陈述。

## 15. 毕业自查清单

**能说清（概念层）**：

- [ ] uv 替代了哪些工具，各自对应哪个命令
- [ ] `uv.lock` 与 `requirements.txt` 的区别
- [ ] `--locked` / `--frozen` / `--offline` 的区别
- [ ] 项目级（`uv add`）与全局级（`uv pip`）的边界
- [ ] `.python-version` 与 `requires-python` 的分工
- [ ] `uvx` 与 `uv tool install` 的取舍
- [ ] 为什么 `uv run` 不需要激活 venv
- [ ] `Makefile` 的 Tab 规则与 `.PHONY` 作用

**能写出（代码层）**：

- [ ] 从零 `uv init` 到 `uv run` 的完整命令链
- [ ] `[project.scripts]` + `uv run <cmd>`
- [ ] `make install/test/lint/ci` 四个目标
- [ ] `uv lock --check` 进 CI
- [ ] `uv export` 生成 `requirements.txt`
- [ ] 第 11 节的只读体检脚本
- [ ] 私有源 `[[index]]` + `explicit` 配置

**能判断（避坑层）**：

- [ ] 看到 `uv venv --list` 能指出本机版本不支持
- [ ] 看到 `uv x` 能指出应为 `uvx`
- [ ] 看到 Makefile 空格缩进能指出 `missing separator`
- [ ] 看到 `ci:` 后单行三个词能指出是错误串联
- [ ] 看到 CI 用 `uv sync` 能指出该加 `--locked`
- [ ] 看到 `.venv` 入库能指出问题
- [ ] 看到多 `[[index]]` 无 `explicit` 能指出依赖混淆

**能跑通（验收层）**：

- [ ] 运行 `examples/tooling_demo.py` 并解释输出为何因机器而异
- [ ] 把第 11 节示例存成文件运行，输出与文档一致
- [ ] 建一个项目：`init` → `lock` → `sync` → `run` → `build` 全链路
- [ ] 复现一次 `uv lock --check` 的漂移报错

## 16. 下一章衔接

第 31 章 `monorepo`：一个仓库放多个包时，uv 的 workspace 能力怎么用、`[tool.uv.sources]` 如何把成员包链接起来、依赖方向与环形依赖怎么把控。

本章留下的伏笔：

1. `uv sync --all-packages` 在第 31 章才会用到。
2. `uv run --package <成员>` 是 workspace 的日常入口。
3. `uv build --package <成员>` 让单仓多包可以各自发布。