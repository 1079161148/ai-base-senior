# 23 第三方库 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把截图里的「pip 概述、国内镜像源、安装/升级/卸载/查看、依赖管理、虚拟环境」逐条展开，并补上版本约束语义、PEP 668、供应链风险、`pyproject.toml` 与 lockfile，目标是**学一遍即可毕业**。
>
> **本章不联网安装任何包**。所有命令只做只读查询（`--version` / `show` / `list` / `freeze` / `check` / `config list`），安装类命令只给写法与说明。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12 + pip 24.3（本机 3.12.8 / 24.3.1 实测） |
| 前置 | 第 02、21–22 章（环境、模块化、标准库） |
| 覆盖范围 | PyPI 与 pip、`python -m pip`、镜像源、安装/升级/卸载/查看、版本约束、`requirements.txt`、`pyproject.toml`、lockfile、venv、PEP 668、选型与许可证 |
| 明确不覆盖 | 打包发布（29 章）、完整锁文件与哈希校验（30 章）、私有源搭建、C 扩展编译工具链细节 |
| 学完验收 | 能说清 `freeze` 为什么不是 lockfile、能写出版本约束并解释边界、能独立建 venv 并复现环境（见第 14 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Vn]` `` 指向第 13 节官方链接；标「实测」的是本机只读命令输出。

**推荐顺序**：

```text
1 pip 概述（第 1 节）        → 是什么、怎么调
2 镜像源（第 2 节）          → 为什么、怎么配
3 安装（第 3 节）            → 版本约束是核心
4 升级 / 卸载（第 4–5 节）   → 破坏性操作
5 查看与管理（第 6 节）      → 只读诊断
6 依赖管理（第 7 节）        → requirements vs lockfile
7 虚拟环境（第 8 节）        → 隔离是前提
8 选型与供应链（第 9 节）
9 综合示例（第 10 节）
10 注意事项（第 11 节）      → 41 条错误对照
```

**与 README 的分工**：README 给结论与边界，本文件负责命令细节、版本语义与风险清单。冲突时以本文件为准。

## 1. pip 概述

### 1.1 是什么

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| pip 是 Python 官方包管理器 | 从 PyPI 下载并安装 | `[V1]` |
| 3.4 起随解释器自带 | 通常无需单独装 | `[V1]` |
| 默认源是 PyPI | `https://pypi.org` | `[V1]` |
| 装进「当前解释器」的环境 | venv 内装就只影响 venv | `[V1]` |

本机实测：

```text
pip 24.3.1 from C:\Users\Administrator\AppData\Local\Programs\Python\Python312\Lib\site-packages\pip (python 3.12)
```

| 信息 | 含义 | 依据 |
| --- | --- | --- |
| `24.3.1` | pip 自身版本 | `[V1]` |
| 路径 | 装到了哪个 `site-packages` | `[V1]` |
| `(python 3.12)` | 绑定的解释器 | `[V1]` |

### 1.2 为什么推荐 `python -m pip`

| 写法 | 风险 | 依据 |
| --- | --- | --- |
| `pip install x` | 可能是别的解释器的 pip | `[V1]` |
| `python -m pip install x` | 明确用当前解释器 | `[V1]` |
| `pip3 install x` | 多解释器时仍可能错配 | `[V1]` |

```powershell
python -m pip --version
python -m pip help
```

本机实测输出：

```text
pip 24.3.1 from ...\Python312\Lib\site-packages\pip (python 3.12)
```

> 注意：一台机器上常有多个 Python（系统自带、pyenv、conda、IDE 内置）。`pip` 命令指向哪个 pip 取决于 `PATH` 顺序，而 `python -m pip` 永远跟当前 `python` 绑定。这是「装成功了但导入不到」的头号原因。`[V1]`

### 1.3 PyPI 与包名

| 概念 | 说明 | 依据 |
| --- | --- | --- |
| PyPI | Python Package Index | `[V1]` |
| 分发名（distribution name） | 安装时用的名字，如 `python-dateutil` | `[V1]` |
| 导入名（import name） | 代码里 `import` 的名字，如 `dateutil` | `[V1]` |
| 规范化 | 名字大小写/`-`/`_` 视为等价 | `[V1]` |

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| 装 `python-dateutil` 却 `import python-dateutil` | 导入名不是分发名 | `[V1]` |
| 装 `Pillow` 却 `import pillow` | 实际是 `PIL` | `[V1]` |
| 装 `beautifulsoup4` 却 `import bs4` | 名字不同 | `[V1]` |

```python
import importlib.metadata

print(importlib.metadata.version("pip"))                 # 24.3.1（实测）
print(importlib.metadata.packages_distributions()["pip"])  # ['pip']
```

> 注意：搞不清「导入名 ↔ 分发名」时，用 `importlib.metadata.packages_distributions()` 反查——它给出「导入名 → 分发名列表」的映射。`[V4]`

## 2. 国内镜像源

### 2.1 为什么用

| 原因 | 说明 | 依据 |
| --- | --- | --- |
| 网络延迟 | 直连 PyPI 慢 | `[V1]` |
| 超时失败 | 大包容易断 | `[V1]` |
| 稳定性 | 镜像通常更快 | `[V1]` |

| 风险 | 说明 | 依据 |
| --- | --- | --- |
| 同步延迟 | 新版本可能还没同步 | `[V1]` |
| 信任问题 | 镜像运营方可见请求 | `[V1]` |
| 配置残留 | 换机器后忘记 | `[V1]` |

### 2.2 常用镜像

| 镜像 | URL | 备注 |
| --- | --- | --- |
| 清华 TUNA | `https://pypi.tuna.tsinghua.edu.cn/simple` | 本机已配置（实测） |
| 阿里云 | `https://mirrors.aliyun.com/pypi/simple/` | 企业常用 |
| 中科大 | `https://pypi.mirrors.ustc.edu.cn/simple/` | 教育网较快 |
| 华为云 | `https://repo.huaweicloud.com/repository/pypi/simple/` | 企业常用 |

> 说明：上表为社区常用镜像，**可用性与同步状态需自行确认**（本文件不联网验证）。镜像地址会变化，以运营方文档为准。

### 2.3 三种配置方式

| 方式 | 命令 | 作用域 | 依据 |
| --- | --- | --- | --- |
| 临时 | `python -m pip install -i <URL> pkg` | 本次 | `[V1]` |
| 全局 | `python -m pip config set global.index-url <URL>` | 当前用户 | `[V1]` |
| 项目 | 项目内 `pip.ini` / `pip.conf` | 当前项目 | `[V1]` |

本机实测（已配置清华源）：

```text
global.index-url='https://pypi.tuna.tsinghua.edu.cn/simple'
```

```powershell
# 查看当前配置
python -m pip config list

# 查看配置文件位置
python -m pip config debug

# 恢复官方源
python -m pip config unset global.index-url
```

| 命令 | 作用 | 依据 |
| --- | --- | --- |
| `pip config list` | 列出生效配置 | `[V1]` |
| `pip config debug` | 显示各级配置文件路径 | `[V1]` |
| `pip config set` | 写配置 | `[V1]` |
| `pip config unset` | 删配置 | `[V1]` |

> 注意：镜像配置是**用户级**的，会影响这台机器上所有项目。团队项目更稳的做法是提交 `requirements.txt` + 文档说明，而不是依赖每个人本机的 `pip.ini`。`[V1]`

### 2.4 缓存

本机实测缓存目录：

```text
c:\users\administrator\appdata\local\pip\cache
```

| 命令 | 作用 | 依据 |
| --- | --- | --- |
| `pip cache dir` | 显示缓存目录 | `[V1]` |
| `pip cache list` | 列出缓存的 wheel | `[V1]` |
| `pip cache purge` | 清空缓存 | `[V1]` |

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| 缓存导致「装了旧版本」 | 加 `--no-cache-dir` | `[V1]` |
| 缓存占满磁盘 | 定期 `purge` | `[V1]` |

## 3. 安装第三方库

### 3.1 基础安装

```powershell
python -m pip install requests
python -m pip install "requests==2.32.3"
python -m pip install "requests>=2.31,<3"
```

| 写法 | 含义 | 依据 |
| --- | --- | --- |
| `install pkg` | 装最新版 | `[V1]` |
| `install "pkg==1.4.2"` | 精确版本 | `[V1]` |
| `install "pkg>=1,<2"` | 范围 | `[V1]` |
| `install "pkg~=1.4.2"` | 兼容版本（`>=1.4.2,<1.5`） | `[V1]` |
| `install "pkg!=1.5"` | 排除 | `[V1]` |

> 注意：`>=`、`<`、`==` 里的符号在 PowerShell 里有特殊含义，**必须加引号**，否则 `>` 会被当成重定向。这是 Windows 上最高频的安装事故。`[V1]`

### 3.2 版本约束语义（实测）

```python
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

print(Requirement("requests>=2,<3").specifier)     # <3,>=2（实测，被规范化排序）
print(Version("1.4.2") in SpecifierSet("~=1.4.2"))  # True（实测）
print(Version("1.5.0") in SpecifierSet("~=1.4.2"))  # False（实测）
print(Version("1.9") in SpecifierSet(">=1,<2"))     # True（实测）
print(Version("2.0") in SpecifierSet(">=1,<2"))     # False（实测）
print(Version("1.0a1") in SpecifierSet(">=1.0"))    # False（实测，预发布默认排除）
print(Version("1.10") > Version("1.9"))             # True（实测，按数值比而非字符串）
print(Version("2.0.0") == Version("2.0"))           # True（实测）
```

| 约束 | 含义 | 适用 | 依据 |
| --- | --- | --- | --- |
| `==1.4.2` | 精确 | 应用锁定 | `[V7]` |
| `>=1.4,<2` | 范围 | 库作者 | `[V7]` |
| `~=1.4.2` | `>=1.4.2,<1.5` | 允许补丁 | `[V7]` |
| `~=1.4` | `>=1.4,<2` | 允许次版本 | `[V7]` |
| `!=1.5.0` | 排除问题版本 | 临时规避 | `[V7]` |

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| 字符串比较版本 | `"10" < "9"` | `[V7]` |
| 预发布默认不匹配 | 需 `--pre` | `[V7]` |
| `~=1.4.2` 以为能升到 1.5 | 实际 `<1.5` | `[V7]` |
| 约束写太松 | 依赖漂移 | `[V7]` |

### 3.3 一次装多个 / 从文件装

```powershell
python -m pip install requests httpx pydantic
python -m pip install -r requirements.txt
```

| 场景 | 写法 | 依据 |
| --- | --- | --- |
| 多个包 | 空格分隔 | `[V1]` |
| 从文件 | `-r requirements.txt` | `[V6]` |
| 从本地 wheel | `install ./dist/pkg-1.0-py3-none-any.whl` | `[V1]` |
| 从 git | `install "git+https://github.com/u/r.git@v1.0"` | `[V1]` |
| 从本地目录（可编辑） | `install -e .` | `[V1]` |

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| `-e .` 要求有打包配置 | 需 `pyproject.toml` | `[V1]` |
| git 安装不锁 commit | `@v1.0` 标签也可能移动 | `[V1]` |
| 从 URL 装 | 无哈希校验 | `[V1]` |

### 3.4 常用开关

| 开关 | 作用 | 依据 |
| --- | --- | --- |
| `--no-deps` | 不装依赖 | `[V1]` |
| `--no-cache-dir` | 不用缓存 | `[V1]` |
| `--dry-run` | 只演示不安装 | `[V1]` |
| `--upgrade` | 升级到最新 | `[V1]` |
| `--force-reinstall` | 强制重装 | `[V1]` |
| `--pre` | 允许预发布 | `[V1]` |
| `--index-url` | 指定源 | `[V1]` |
| `--only-binary :all:` | 只允许 wheel | `[V1]` |

```powershell
# 最安全的预演：不联网也基本可用（只解析已缓存/已装信息）
python -m pip install --dry-run "requests>=2.31,<3"
```

> 注意：`--dry-run` 仍可能访问网络解析依赖；它保证的是「不落盘」。真要验证，先在 venv 里做。`[V1]`

## 4. 升级第三方库

### 4.1 升级单个 / 全部

```powershell
python -m pip install --upgrade requests
python -m pip list --outdated
```

| 命令 | 作用 | 依据 |
| --- | --- | --- |
| `install --upgrade pkg` | 升到最新（受约束） | `[V1]` |
| `list --outdated` | 列出可升级项 | `[V1]` |
| `install --upgrade pip` | 升级 pip 自身 | `[V1]` |

### 4.2 升级为什么危险

| 风险 | 说明 | 依据 |
| --- | --- | --- |
| 破坏性变更 | 主版本升级常有不兼容 | `[V7]` |
| 传递依赖联动 | 一个包升级可能连带多个 | `[V2]` |
| 无法回滚 | 没有 lockfile 就说不清原来是什么 | `[V2]` |
| 环境不一致 | 开发机升级、生产没升 | `[V1]` |

| 做法 | 说明 | 依据 |
| --- | --- | --- |
| 先看 changelog | 确认破坏性变更 | `[V1]` |
| 在 venv 里试 | 隔离爆炸半径 | `[V1]` |
| 有测试再升 | 回归验证 | `[V1]` |
| 一个包一次 | 便于定位 | `[V1]` |

> 注意：`pip install --upgrade` 不等于「安全升级」——它会装到约束允许的最新版，可能跨主版本。生产环境应基于 lockfile 精确重装，而不是升级。`[V2]`

## 5. 卸载第三方库

```powershell
python -m pip uninstall requests
python -m pip uninstall -y requests
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 只删该包的文件 | 不动依赖 | `[V1]` |
| 不会自动清理孤儿依赖 | 需 `pip check` / 工具 | `[V1]` |
| 可能留下 `*.dist-info` 残留 | 用 `--force-reinstall` 修 | `[V1]` |

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| 卸载被依赖的包 | 其它包运行时报 `ModuleNotFoundError` | `[V1]` |
| 在系统 Python 里卸载 | 可能坏掉系统工具 | `[V3]` |
| 卸载后没重装 | 环境与 `requirements.txt` 不一致 | `[V1]` |

> 注意：卸载前先 `pip show pkg` 看 `Required-by`，确认没有别的包依赖它；更稳的做法是**直接删 venv 重建**，而不是逐个卸载。`[V1]`

## 6. 查看与管理包

### 6.1 四个只读命令

```powershell
python -m pip list
python -m pip list --format=freeze
python -m pip show pip
python -m pip freeze
python -m pip check
```

本机实测（节选）：

```text
# pip show pip
Name: pip
Version: 24.3.1
Summary: The PyPA recommended tool for installing Python packages.
Home-page: https://pip.pypa.io/
Author:
Author-email: The pip developers <distutils-sig@python.org>

# pip list --format=freeze
agent-detector==2.0.0
annotated-doc==0.0.5
annotated-types==0.8.0
anyio==4.15.1
babel==2.18.0
backrefs==8.0
certifi==2026.7.22
charset-normalizer==3.4.9

# pip check
No broken requirements found.

# pip freeze 条数
90
```

| 命令 | 输出 | 用途 | 依据 |
| --- | --- | --- | --- |
| `list` | 表格（包名/版本） | 人看 | `[V1]` |
| `list --format=freeze` | `name==version` | 机器读 | `[V1]` |
| `show pkg` | 元数据（含 `Requires` / `Required-by`） | 查依赖关系 | `[V1]` |
| `freeze` | `name==version` | 导出环境 | `[V2]` |
| `check` | 依赖冲突 | 体检 | `[V1]` |

### 6.2 `show` 里最该看的两行

| 字段 | 含义 | 依据 |
| --- | --- | --- |
| `Requires` | 这个包依赖谁 | `[V1]` |
| `Required-by` | 谁依赖它 | `[V1]` |
| `Location` | 装在哪个 `site-packages` | `[V1]` |

```powershell
python -m pip show requests
```

> 注意：`Required-by` 为空不代表能安全卸载——运行时动态导入的依赖不会体现在元数据里。`[V1]`

### 6.3 用标准库查版本（脚本化）

```python
import importlib.metadata

for name in ["pip", "packaging"]:
    try:
        print(name, importlib.metadata.version(name))
    except importlib.metadata.PackageNotFoundError:
        print(name, "未安装")
# pip 24.3.1 / packaging 26.2（实测）
```

| API | 作用 | 依据 |
| --- | --- | --- |
| `version(name)` | 取版本 | `[V4]` |
| `metadata(name)` | 取全部元数据 | `[V4]` |
| `packages_distributions()` | 导入名 → 分发名 | `[V4]` |
| `requires(name)` | 取依赖声明 | `[V4]` |

实测元数据：

```text
META pip 24.3.1 ['Author-email', 'Classifier', 'Classifier', 'Classifier']（实测）
```

### 6.4 判断是否在虚拟环境

```python
import sys
print(sys.prefix != sys.base_prefix, sys.prefix)
# False C:\Users\Administrator\AppData\Local\Programs\Python\Python312（实测，不在 venv）
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| venv 内 `sys.prefix != sys.base_prefix` | 判定标准 | `[V1]` |
| `CONDA_PREFIX` 存在 | conda 环境 | `[V1]` |
| `sys.path` 含 venv 的 `site-packages` | 实测 `['site-packages']` | `[V6]` |

> 注意：本机当前**不在 venv 内**（实测），所有 `pip install` 都会装进系统 Python——这正是最该避免的做法。`[V3]`

## 7. 依赖管理

### 7.1 `requirements.txt`

```text
# requirements.txt
requests==2.32.3
pydantic>=2.6,<3
httpx~=0.27
```

```powershell
python -m pip install -r requirements.txt
python -m pip freeze > requirements.txt
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `-r` 按行安装 | 支持注释 `#` | `[V6]` |
| 支持 `-e .` / `--index-url` | 行内选项 | `[V6]` |
| `freeze` 导出**当前环境全部** | 含传递依赖 | `[V2]` |
| `freeze` 不排序、不分组 | 人工整理 | `[V2]` |

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| 直接 `freeze` 入库 | 混入开发依赖、平台特定包 | `[V2]` |
| 把 `freeze` 当 lockfile | 无哈希、无求解 | `[V2]` |
| 混用 `~=` 与 `==` | 复现性不一致 | `[V7]` |
| 注释写在行尾带空格 | 可能被当作版本一部分 | `[V6]` |

### 7.2 `freeze` 与 lockfile 的区别

| 维度 | `pip freeze` | lockfile（如 `pylock.toml` / `poetry.lock` / `uv.lock`） |
| --- | --- | --- |
| 是否求解依赖 | ❌ 只记录当前 | ✅ 求解后记录 |
| 是否含哈希 | ❌ | ✅ |
| 是否区分直接/传递 | ❌ 混在一起 | ✅ 分层 |
| 是否可复现跨平台 | ❌ | ✅（含 marker） |
| 依据 | `[V2]` | `[V2]` |

```powershell
# freeze 的已知行为：默认排除引导工具（pip/setuptools 等）
python -m pip freeze --exclude pip
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `freeze` 默认排除引导工具 | 官方文档明确 | `[V2]` |
| 完整锁定见第 30 章 | 不在本章范围 | `[V2]` |

> 注意：`pip freeze` 的输出长度在本机是 90 行（实测），其中绝大部分是传递依赖；直接提交它会把「我没打算依赖的东西」固化成契约。`[V2]`

### 7.3 `pyproject.toml`

```toml
[project]
name = "agent-demo"
version = "0.1.0"
requires-python = ">=3.11"
dependencies = [
    "requests>=2.31,<3",
    "pydantic>=2.6,<3",
]

[project.optional-dependencies]
dev = ["pytest>=8", "ruff>=0.5"]
```

| 字段 | 作用 | 依据 |
| --- | --- | --- |
| `requires-python` | 声明支持的 Python 版本 | `[V1]` |
| `dependencies` | 运行时依赖 | `[V1]` |
| `optional-dependencies` | 分组（dev/test） | `[V1]` |
| `[build-system]` | 构建后端 | 29 章 |

| 对比 | `requirements.txt` | `pyproject.toml` |
| --- | --- | --- |
| 定位 | 安装清单 | 项目元数据 + 依赖声明 |
| 能否安装项目本身 | ❌ | ✅ |
| 能否分组 | 需多文件 | ✅ extra |
| 依据 | `[V6]` | `[V1]` |

> 注意：`pyproject.toml` 声明的是**范围**（给库消费者看），lockfile 记录的是**精确解**（给自己复现）。两者不是替代关系。`[V2]`

### 7.4 依赖分层建议

| 文件 | 内容 | 依据 |
| --- | --- | --- |
| `requirements.txt` | 运行时直接依赖（精确版本） | `[V6]` |
| `requirements-dev.txt` | 测试/lint/格式化 | `[V6]` |
| lockfile | 全部精确解 + 哈希 | `[V2]` |

```text
# requirements-dev.txt
-r requirements.txt
pytest>=8
ruff>=0.5
```

## 8. 虚拟环境

### 8.1 为什么要隔离

| 问题 | 不隔离 | 隔离后 | 依据 |
| --- | --- | --- | --- |
| 版本冲突 | A 项目要 v1，B 要 v2 | 各自 venv | `[V1]` |
| 污染系统 | 系统工具可能被换版本 | 不影响系统 | `[V3]` |
| 无法复现 | 说不清装了啥 | `freeze` 即清单 | `[V2]` |
| 权限问题 | 需管理员/`sudo` | 用户目录即可 | `[V3]` |

### 8.2 创建与激活（Windows）

```powershell
# 在项目根目录
python -m venv .venv

# 激活（PowerShell）
.\.venv\Scripts\Activate.ps1

# 激活（cmd）
.venv\Scripts\activate.bat

# 确认
python -c "import sys; print(sys.prefix != sys.base_prefix)"    # True

# 退出
deactivate
```

| 命令 | 作用 | 依据 |
| --- | --- | --- |
| `python -m venv .venv` | 创建 | `[V1]` |
| `.venv\Scripts\Activate.ps1` | PowerShell 激活 | `[V1]` |
| `deactivate` | 退出 | `[V1]` |
| `--system-site-packages` | 继承系统包（不推荐） | `[V1]` |
| `--clear` | 清空后重建 | `[V1]` |

本机 `venv --help` 实测参数：

```text
usage: venv [-h] [--system-site-packages] [--symlinks | --copies] [--clear]
            [--upgrade] [--without-pip] [--prompt PROMPT] [--upgrade-deps]
            ENV_DIR [ENV_DIR ...]
```

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| PowerShell 执行策略拦截脚本 | 需 `Set-ExecutionPolicy` 或用 `activate.bat` | `[V1]` |
| 忘了激活就 `pip install` | 装进系统 Python（本机现状） | `[V1]` |
| 把 `.venv` 提交进 git | 巨大、平台相关 | `[V1]` |
| IDE 选错解释器 | 装到了别处 | `[V1]` |
| 在 venv 里用 `--user` | 无效（官方明确） | `[V1]` |

### 8.3 PEP 668：系统环境被保护

```text
error: externally-managed-environment

× This environment is externally managed
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 新版发行版把系统 Python 标记为 externally-managed | 拒绝全局 `pip install` | `[V3]` |
| 正解是 venv 或 `pipx` | 不要 `--break-system-packages` | `[V3]` |
| 报错不是 bug | 是保护机制 | `[V3]` |

| 错误应对 | 后果 | 依据 |
| --- | --- | --- |
| `--break-system-packages` | 破坏系统包管理 | `[V3]` |
| `sudo pip install` | 同上 | `[V3]` |
| 改用 venv | ✅ | `[V3]` |

### 8.4 环境复现流程

```powershell
# 1 建并激活
python -m venv .venv
.\.venv\Scripts\Activate.ps1

# 2 升级 pip
python -m pip install --upgrade pip

# 3 安装依赖
python -m pip install -r requirements.txt

# 4 验证
python -m pip check
python -c "import sys; print(sys.prefix)"
```

| 步骤 | 目的 | 依据 |
| --- | --- | --- |
| 1 | 隔离 | `[V1]` |
| 2 | 老 pip 解析慢/有 bug | `[V1]` |
| 3 | 按清单装 | `[V6]` |
| 4 | 确认无冲突 | `[V1]` |

## 9. 选型与供应链

### 9.1 四项标准

| 维度 | 看什么 | 依据 |
| --- | --- | --- |
| 维护活跃度 | 最近提交、issue 响应、发版节奏 | `[V1]` |
| 类型完备度 | 有 `py.typed` / stub | 20 章 |
| 技术栈契合 | 与现有异步/同步模型一致 | `[V1]` |
| 退出成本 | 封装在自己的边界后有多容易换 | `[V1]` |

### 9.2 许可证

| 许可证 | 商用 | 注意 | 依据 |
| --- | --- | --- | --- |
| MIT / BSD / Apache-2.0 | ✅ | 保留版权声明 | `[V1]` |
| LGPL | 通常 ✅ | 动态链接义务 | `[V1]` |
| GPL | 有传染性 | 分发时需开源 | `[V1]` |
| AGPL | 更严格 | 网络服务也可能触发 | `[V1]` |
| 无许可证 | ❌ 默认保留所有权利 | 不要用 | `[V1]` |

> 说明：上表是通行理解，**不构成法律意见**；商用前请让法务确认，尤其 AGPL 与「无许可证」的包。

### 9.3 安全检查

| 手段 | 作用 | 依据 |
| --- | --- | --- |
| 关注安全公告 | 及时升级 | `[V1]` |
| 固定版本 + 哈希 | 防篡改 | `[V2]` |
| 只从可信源装 | 防抢注/投毒 | `[V1]` |
| 审阅安装脚本 | 防任意代码执行 | `[V1]` |
| 检查包名相似度 | 防 typosquatting | `[V1]` |

| 风险 | 例子 | 依据 |
| --- | --- | --- |
| 抢注/仿冒 | 包名差一个字母 | `[V1]` |
| 依赖混淆 | 私有包名被公开抢注 | `[V1]` |
| 安装时执行代码 | `setup.py` 可任意执行 | `[V1]` |
| 传递依赖投毒 | 深层依赖被劫持 | `[V1]` |

### 9.4 退出成本

| 做法 | 效果 | 依据 |
| --- | --- | --- |
| 第三方库封装在适配层 | 换库只改一处 | 第 01 章 |
| 只用其最小能力 | 减少耦合 | 第 01 章 |
| 记录备选方案 | 出问题能切换 | 第 01 章 |

## 10. 综合示例：只读依赖审计

```python
"""第 23 章综合示例：不联网，只读检查已安装依赖。"""

import importlib.metadata
import re
import sys

REQUIRED = {"pip": ">=24", "packaging": ">=20", "definitely-missing": ">=1"}


def parse_version(text):
    return tuple(int(part) for part in re.findall(r"\d+", text)[:2])


def audit(required):
    for name, spec in required.items():
        try:
            current = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            print("MISSING", name, spec)
            continue
        print("CHECK", name, current, spec, parse_version(current) >= parse_version(spec))


audit(REQUIRED)
print("PYTHON_OK", sys.version_info[:2] >= (3, 12))
```

本机实测输出：

```text
CHECK pip 24.3.1 >=24 True
CHECK packaging 26.2 >=20 True
MISSING definitely-missing >=1
PYTHON_OK True
```

**逐段说明**：

| 代码 | 用到的机制 | 依据 |
| --- | --- | --- |
| `importlib.metadata.version` | 只读查版本 | `[V4]` |
| `PackageNotFoundError` | 未安装分支 | `[V4]` |
| `re.findall(r"\d+")` | 简易版本解析 | 22 章 |
| `sys.version_info` | 解释器版本门槛 | 22 章 |
| 无网络调用 | 可安全跑在 CI | `[V1]` |

> 注意：这个示例的版本比较是**简化版**（只取前两段数字），真实项目应使用 `packaging.version.Version` / `SpecifierSet`——预发布、`~=`、`!=` 等语义它都实现好了。`[V7]`

## 11. 注意事项与新手错误对照表

| 错误写法 / 操作 | 报错或现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 全局 `pip install` | 污染系统 Python | venv | `[V3]` |
| `sudo pip install` | 破坏系统包管理 | venv | `[V3]` |
| `--break-system-packages` | 掩盖问题 | venv | `[V3]` |
| `pip install "pkg>=1,<2"` 不加引号（PowerShell） | 被当重定向 | 加引号 | `[V1]` |
| 用 `pip` 而非 `python -m pip` | 解释器错配 | `python -m pip` | `[V1]` |
| venv 内用 `--user` | 无效 | 去掉 | `[V1]` |
| 把 `.venv` 提交 git | 仓库巨大 | `.gitignore` | `[V1]` |
| 忘激活就装 | 装到系统 | 先激活再装 | `[V1]` |
| `pip freeze` 直接当 lockfile | 无求解、无哈希 | 用 lockfile | `[V2]` |
| `freeze` 混入开发依赖 | 生产多装一堆 | 分层 requirements | `[V6]` |
| 约束写 `>=1.0` 不设上限 | 依赖漂移 | `<2` 或精确 | `[V7]` |
| 约束写 `*` | 不可复现 | 精确或范围 | `[V7]` |
| 手工比较版本字符串 | `"10" < "9"` | `packaging.version` | `[V7]` |
| 以为 `~=1.4.2` 能到 1.5 | 实际 `<1.5` | 看语义 | `[V7]` |
| 预发布装不上 | 默认排除 | `--pre` | `[V7]` |
| `pip install --upgrade` 生产用 | 跨主版本破坏 | lockfile 重装 | `[V2]` |
| 升级不读 changelog | 踩破坏性变更 | 先读再升 | `[V1]` |
| 一次升级所有包 | 无法定位问题 | 一次一个 | `[V1]` |
| `uninstall` 被依赖的包 | 运行时 `ModuleNotFoundError` | 先看 `Required-by` | `[V1]` |
| 卸载后不核对 | 环境漂移 | `pip check` | `[V1]` |
| 装 `python-dateutil` 后 `import python-dateutil` | `ModuleNotFoundError` | `import dateutil` | `[V1]` |
| 装 `Pillow` 后 `import Pillow` | 实际 `import PIL` | 查文档 | `[V1]` |
| 从不明 URL 装包 | 无校验、可能投毒 | 官方源 + 哈希 | `[V1]` |
| `git+...@main` 当锁定 | 分支会动 | 钉 commit | `[V1]` |
| `-e .` 但无打包配置 | 报错 | 先写 `pyproject.toml` | `[V1]` |
| 只看 `pip list` 判断兼容 | 不含依赖约束 | `pip check` | `[V1]` |
| 忽略 `pip check` 警告 | 运行期才炸 | 立即修 | `[V1]` |
| 镜像配在项目里却不提交 | 换人即失效 | 文档说明 | `[V1]` |
| 依赖镜像的最新版 | 同步延迟 | 必要时指定官方源 | `[V1]` |
| 缓存导致装旧版 | 版本不符 | `--no-cache-dir` | `[V1]` |
| 用系统 Python 跑脚本 | 依赖缺失 | 项目 venv | `[V3]` |
| IDE 解释器选错 | 装了却导不到 | 核对 `sys.executable` | `[V1]` |
| 无许可证的包用于商用 | 法律风险 | 换包 | `[V1]` |
| GPL 包混进闭源分发 | 传染 | 法务确认 | `[V1]` |
| 依赖 `setup.py` 逻辑 | 安装期执行代码 | 优先 wheel | `[V1]` |
| 装功能重叠的两个库 | 维护成本翻倍 | 选一个 | 第 01 章 |
| 版本上限写死到补丁 | 安全更新进不来 | 允许补丁 | `[V7]` |
| 只锁直接依赖 | 传递依赖漂移 | lockfile | `[V2]` |
| 生产环境无 lockfile | 无法复现 | 提交 lockfile | `[V2]` |
| 密钥写进 `requirements.txt` 或 URL | 泄露 | 环境变量/密钥管理 | 第 01 章 |
| 在 CI 里 `pip install` 不缓存 | 每次全下载 | 缓存 `pip cache dir` | `[V1]` |

## 12. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 每个项目独立 venv | 隔离是前提 | `[V1]` |
| 一律 `python -m pip` | 避免错配 | `[V1]` |
| 版本约束写范围 + 上限 | 可升级但不漂移 | `[V7]` |
| 应用提交 lockfile | 可复现 | `[V2]` |
| 依赖分层（运行/开发） | 生产精简 | `[V6]` |
| 先查标准库 | 不造轮子 | 22 章 |
| 选型看四项 | 维护/类型/契合/退出 | 第 01 章 |
| 第三方库封在适配层 | 可替换 | 第 01 章 |
| 定期 `pip check` + 安全公告 | 及早发现 | `[V1]` |
| 装包前确认在 venv 内 | 看 `sys.prefix` | `[V1]` |
| 生产用 `--no-deps` + lockfile 精确装 | 可控 | `[V2]` |
| 不在生产 `--upgrade` | 用新 lockfile 重建 | `[V2]` |

**风格示范**：

```text
# requirements.txt —— 只列直接依赖，应用场景用精确版本
requests==2.32.3
pydantic==2.9.2
httpx==0.27.2
```

```text
# requirements-dev.txt
-r requirements.txt
pytest==8.3.3
ruff==0.6.9
```

```toml
# pyproject.toml（库场景：给范围，不给精确版本）
[project]
requires-python = ">=3.11"
dependencies = [
    "requests>=2.31,<3",
    "pydantic>=2.6,<3",
]
```

| 场景 | 依赖写法 | 依据 |
| --- | --- | --- |
| 应用（部署） | 精确版本 + lockfile | `[V2]` |
| 库（被依赖） | 范围 + 上限 | `[V7]` |
| 内部工具 | 范围，允许较快演进 | `[V7]` |

**边界**：

- 不要为了「装得快」而长期不用 venv——代价是不可复现。
- 不要在 `requirements.txt` 里放密钥、私有源 token（会进版本库）。
- 不要把「装上了」当作「验证过」：`pip check` 只查元数据冲突，不查运行时行为。

## 13. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[V1]` | PyPA 官方 | https://packaging.python.org/en/latest/tutorials/installing-packages/ | pip 安装、`python -m pip`、版本约束、venv、不要 `sudo`、`--user` 在 venv 内无效 |
| `[V2]` | PyPA 官方 | https://pip.pypa.io/en/stable/cli/pip_freeze/ | `freeze` 输出格式、不是 lockfile、默认排除引导工具 |
| `[V3]` | PEP 官方 | https://peps.python.org/pep-0668/ | externally-managed 环境、引导使用 venv |
| `[V4]` | python.org | https://docs.python.org/3.12/library/importlib.metadata.html | `version()` / `metadata()` / `packages_distributions()` / `requires()` |
| `[V5]` | PEP 官方 | https://peps.python.org/pep-0008/ | import 分组、命名与注释约定 |
| `[V6]` | PyPA 官方 | https://pip.pypa.io/en/stable/reference/requirements-file-format/ | `requirements.txt` 语法、注释、`-r` / `-e` / 行内选项 |
| `[V7]` | PyPA 官方 | https://packaging.python.org/en/latest/specifications/version-specifiers/ | `==` / `>=` / `~=` / `!=` / 预发布语义、版本比较规则 |
| `[V8]` | python.org | https://docs.python.org/3.12/library/venv.html | `python -m venv` 参数、激活方式 |

> **核对状态**：`[V1]` `[V2]` `[V3]` `[V5]` 与本章 `README.md` 已核对来源一致；其余按官方文档结构整理，**本次未逐页直连复核**。全部结论未联网验证安装行为；镜像可用性、许可证判断需自行确认。

## 14. 毕业自查清单

**能说清（概念层）**：

- [ ] pip 与 PyPI 的关系、`3.4 起自带`
- [ ] 为什么用 `python -m pip` 而不是 `pip`
- [ ] 国内镜像的收益与风险
- [ ] 五种版本约束的含义与边界
- [ ] `~=1.4.2` 与 `~=1.4` 的区别
- [ ] 预发布为什么默认装不上
- [ ] `pip freeze` 为什么不是 lockfile
- [ ] `requirements.txt` 与 `pyproject.toml` 的分工
- [ ] PEP 668 是什么、为什么不能 `--break-system-packages`
- [ ] 选型四项标准
- [ ] 供应链风险至少三条

**能写出（命令层）**：

- [ ] `python -m venv .venv` + 激活 + 确认 `sys.prefix`
- [ ] 精确版本安装、范围安装、多包安装
- [ ] `pip list --outdated` / `show` / `check` / `freeze`
- [ ] 分层 `requirements.txt` + `-r` 引用
- [ ] `pyproject.toml` 的 `dependencies` 与 `optional-dependencies`
- [ ] 用 `packaging.version` 正确比较版本
- [ ] 用 `importlib.metadata` 做只读审计

**能判断（避坑层）**：

- [ ] 看到全局 `pip install` 能指出污染系统
- [ ] 看到 PowerShell 里 `>=` 不加引号能指出重定向
- [ ] 看到 `freeze` 当 lockfile 能指出无求解无哈希
- [ ] 看到 `--break-system-packages` 能指出破坏系统
- [ ] 看到生产 `--upgrade` 能指出不可复现
- [ ] 看到 `import` 名与包名不一致能指出查 `packages_distributions`
- [ ] 看到无许可证依赖能指出法律风险

**能跑通（验收层）**：

- [ ] 运行 `examples/deps_demo.py` 并解释「未安装」一行
- [ ] 把第 10 节示例存成文件运行，输出与文档一致
- [ ] 在本机确认当前是否 venv（实测为 `False`）
- [ ] 建一个空 venv，装一个包，`freeze` 后删 venv 重建

## 15. 下一章衔接

第 28 章 `多线程与多进程`：工程化基础到此收束——环境、模块、依赖都能管了，接下来按认知顺序建立并发直觉（GIL、I/O 密集 vs CPU 密集），再进入 24 事件循环 → 25 Future → 26 协程 → 27 异步编程。

本章留下的伏笔：

1. 异步库（`httpx`、`aiohttp`）的选型标准与本章四项一致，但要额外看「是否原生 async」。
2. `venv` + lockfile 是后面所有章节实验的可复现前提。
3. 供应链意识在引入并发/异步库时更重要——它们往往带来大量传递依赖。