# 29 构建发布 · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把课件里的「库的开发流程、构建、发布和安装（发布前的准备 / 官方仓库 / 私有仓库）、可编辑依赖」逐条展开，并补上截图没写但跳不过去的部分：PEP 517/518/621/427/440/660、前端与后端的分工、产物内部结构、元数据映射、私有源配置，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | Python 3.12（本机 3.12.8 / Windows 实测） |
| 前置 | 第 21–23 章（包、依赖、venv） |
| 覆盖范围 | 源码 → wheel → registry → site-packages 四段链路、`pyproject.toml` 三段配置、构建前后端、sdist/wheel 内部结构、PEP 440 版本、PEP 621 元数据、twine/uv 发布、私有制品库、PEP 660 可编辑安装 |
| 明确不覆盖 | C 扩展与多平台 wheel（cibuildwheel）、conda、签名与 SLSA 供应链证明 |
| 学完验收 | 能写出可直接构建的 `pyproject.toml`、能解释 wheel 里每个目录的作用、能说清可编辑安装的 `.pth` 原理（见第 9 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Pn]` `` 指向第 8 节官方链接；标「实测」的是本机 Python 3.12.8 / uv 0.12.2 运行结果。

**推荐顺序**：

```text
1 库的开发流程（第 1 节）   → 先看全景四步
2 构建（第 2 节）           → pyproject + 产物结构（重点）
3 发布和安装（第 3 节）     → 仓库与不可逆性
4 可编辑依赖（第 4 节）     → 开发期的高频操作
5 综合示例（第 5 节）
6 注意事项（第 6 节）       → 41 条错误对照
```

**与 README 的分工**：README 给结论与边界，本文件负责规范依据、配置逐字段解释与实测证据。冲突时以本文件为准。

## 1. 库的开发流程

### 1.1 四步链路

```text
源代码  --build-->  wheel 包  --publish-->  仓库 registry  --install-->  site-packages
```

| 阶段 | 输入 | 输出 | 关键工具 | 依据 |
| --- | --- | --- | --- | --- |
| 构建 | 源码 + `pyproject.toml` | `dist/*.whl`、`dist/*.tar.gz` | `python -m build` / `uv build` | `[P1]` `[P4]` |
| 发布 | `dist/*` | 仓库里的版本记录 | `twine upload` / `uv publish` | `[P7]` |
| 安装 | 包名 + 版本约束 | `site-packages` 下的文件 | `pip install` / `uv add` | `[P7]` |
| 使用 | 已安装包 | `import` 成功 | —— | 第 21 章 |

| 概念 | 一句话 | 依据 |
| --- | --- | --- |
| **发行版（distribution）** | 发布单位，名字里可以有 `-`（`duyi-utils`） | `[P3]` |
| **导入包（import package）** | 代码单位，`import` 用的名字（`duyi_utils`） | 第 21 章 |
| **sdist** | 源码归档，安装时要在目标机执行构建 | `[P9]` |
| **wheel** | 已构建好的二进制/纯 Python 包，安装即解压 | `[P4]` |

> 注意：发行版名与导入名是**两个东西**。`duyi-utils` 装完后 `import duyi_utils`，两者靠规范化规则对应（`-` 与 `_` 等价，见 2.5）。`[P3]` `[P7]`

### 1.2 为什么要有 wheel

| 对比 | sdist（`.tar.gz`） | wheel（`.whl`） | 依据 |
| --- | --- | --- | --- |
| 内容 | 源码 + `pyproject.toml` | 已就位的文件树 + 元数据 | `[P4]` `[P9]` |
| 安装动作 | 解包 → 装构建依赖 → 跑后端 | 解压到 `site-packages` | `[P4]` |
| 需要编译器 | 可能有 C 扩展时需要 | 纯 Python 或已编译好 | `[P4]` |
| 安装速度 | 慢 | 快 | `[P4]` |
| 可复现 | 依赖构建环境 | 二进制一致 | `[P4]` |

实测产物（本机 `uv build --offline`）：

```text
duyi_utils-0.1.3-py3-none-any.whl
duyi_utils-0.1.3.tar.gz
```

| 文件名片段 | 含义 | 依据 |
| --- | --- | --- |
| `duyi_utils` | 规范化后的发行版名（`-` 变 `_`） | `[P4]` |
| `0.1.3` | 版本（PEP 440） | `[P5]` |
| `py3` | 支持 Python 3 全部小版本 | `[P4]` |
| `none` | 无 ABI 依赖（纯 Python） | `[P4]` |
| `any` | 与平台无关 | `[P4]` |

## 2. 构建

### 2.1 两个协议：517 管「怎么构建」，427 管「产物长什么样」

| 协议 | 内容 | 依据 |
| --- | --- | --- |
| PEP 517 | 定义 `build-backend` 接口：`build_wheel` / `build_sdist` / `prepare_metadata_for_build_wheel` | `[P1]` |
| PEP 518 | 定义 `[build-system]` 表，声明构建所需的依赖与隔离 | `[P2]` |
| PEP 427 | 定义 wheel 文件名与内部布局 | `[P4]` |
| PEP 621 | 定义 `[project]` 标准元数据字段 | `[P3]` |

| 角色 | 职责 | 常见实现 | 依据 |
| --- | --- | --- | --- |
| **构建前端（frontend）** | 读 `pyproject.toml`、建隔离环境、调用后端、收集产物 | `build`、`uv build`、`pip wheel`、Poetry、PDM | `[P1]` |
| **构建后端（backend）** | 真正把源码变成 wheel/sdist | `hatchling`、`setuptools`、`uv_build`、`poetry-core`、`pdm-backend`、`flit_core` | `[P1]` |

> 注意：「前端」和「后端」的划分是 PEP 517 的核心贡献——它让 `pip`/`build` 与具体打包工具解耦。换后端不用换命令，换命令不用改配置。`[P1]`

### 2.2 `pyproject.toml` 逐段拆解

课件原文（可直接用）：

```toml
# pyproject.toml

[build-system]                       # 构建系统配置，指定构建工具和依赖
requires = ["hatchling"]             # 依赖的后端构建工具
build-backend = "hatchling.build"    # 使用哪个工具的哪个模块来构建项目

[project]                            # 工程描述
name = "duyi-utils"                  # 发行版名称
version = "0.1.3"                    # 版本号，遵循语义化版本控制
description = "一个用于学习 Python 公共库构建和发布的示例工程"
requires-python = ">=3.14"           # 指定支持的 Python 版本
readme = "README.md"                 # 指定项目的 README 文件路径
dependencies = [
    "python-dateutil>=2.8",          # 依赖的第三方库，指定版本要求
    "Markdown>=3.5",
]

[tool.hatch.build.targets.sdist]     # 配置源代码分发包
# 配置留空，表示它会默认包含所有项目文件

[tool.hatch.build.targets.wheel]     # 配置 wheel 包
packages = ["src/duyi_utils"]        # wheel 的构建目标，指定包含的包路径
```

实测解析（`tomllib.loads`）：

```text
BUILD_BACKEND hatchling.build
BUILD_REQUIRES ['hatchling']
PROJECT_KEYS ['dependencies', 'description', 'name', 'readme', 'requires-python', 'scripts', 'version']
DEPS ['python-dateutil>=2.8', 'Markdown>=3.5']
SCRIPTS {'duyi': 'duyi_utils.cli:main'}
WHEEL_TARGET ['src/duyi_utils']
```

| 字段 | 必填 | 作用 | 依据 |
| --- | --- | --- | --- |
| `[build-system].requires` | 建议 | 构建时临时安装的依赖列表 | `[P2]` |
| `[build-system].build-backend` | 建议 | 后端模块路径，如 `hatchling.build` | `[P1]` |
| `name` | ✅ | 发行版名，规范化后必须唯一 | `[P3]` |
| `version` | ✅（可用动态版本） | PEP 440 版本 | `[P3]` `[P5]` |
| `description` | ❌ | 一句话简介，进 `Summary` | `[P3]` |
| `readme` | ❌ | README 路径 + 自动推断 content-type | `[P3]` |
| `requires-python` | ❌（强烈建议） | 兼容 Python 范围 | `[P3]` |
| `dependencies` | ❌ | 运行时依赖，PEP 508 格式 | `[P3]` |
| `[project.scripts]` | ❌ | 命令行入口点 | `[P3]` |
| `[project.optional-dependencies]` | ❌ | 可选依赖组（`pip install pkg[test]`） | `[P3]` |
| `classifiers` | ❌ | 分类器（许可证、状态、主题） | `[P3]` |
| `license` | ❌ | 许可证声明（PEP 639 后推荐 `license = "MIT"` + `license-files`） | `[P3]` |

| 常见错误 | 后果 | 依据 |
| --- | --- | --- |
| 少了 `[build-system]` | 前端回退 setuptools 隐式构建，行为不可控 | `[P1]` |
| `packages` 路径写错 | wheel 里没有代码，装完 `import` 失败 | 实测见 2.5 |
| `requires-python` 写太窄 | 用户在合法版本上装不上 | `[P3]` |
| `dependencies` 混入开发工具 | 生产镜像体积与攻击面变大 | `[P3]` |

### 2.3 前端 × 后端组合

| 前端命令 | 说明 | 依据 |
| --- | --- | --- |
| `python -m build` | PyPA 参考实现，默认隔离构建 | `[P7]` |
| `uv build` | uv 内置，行为同 `build`，可用 `--package` 指定 workspace 成员 | `[G1]` |
| `pip wheel .` | 只产 wheel，不产 sdist | `[P7]` |

| 后端 | 声明 | 特点 | 依据 |
| --- | --- | --- | --- |
| `hatchling` | `build-backend = "hatchling.build"` | 配置灵活，`[tool.hatch.build.targets.*]` 精细控制 | `[P1]` |
| `uv_build` | `build-backend = "uv_build"` | uv 自带，`src/` 布局零配置，纯 Python 优先 | `[G1]` |
| `setuptools` | `build-backend = "setuptools.build_meta"` | 生态最老，兼容面最广 | `[P1]` |
| `flit_core` | `build-backend = "flit_core.buildapi"` | 极简，要求 `__init__.py` 里有 `__version__` | `[P1]` |

> 注意：后端只影响「怎么把源码变成 wheel」，不影响 `[project]` 元数据语义。改后端时 `[project]` 不用动，但 `[tool.<backend>]` 配置要重写。`[P1]`

### 2.4 构建命令

课件原文（传统路线）：

```shell
# 1. 创建虚拟环境
python -m venv .venv

# 2. 激活虚拟环境
source .venv/bin/activate

# 3. 安装构建工具
pip install build

# 4. 运行构建
python -m build
```

uv 路线（一条命令）：

```shell
uv build                 # 产物进 dist/
uv build --package shared  # workspace 里只构建某个成员
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `build` 默认建隔离环境 | 避免污染当前环境 | `[P1]` |
| 隔离环境要装 `requires` 里的包 | 因此**离线时会失败** | `[P2]` |
| 顺序固定 | 先 sdist，再从 sdist 构建 wheel | `[P4]` |
| 产物目录 | `dist/` | `[P7]` |

本机实测：`build` / `twine` / `hatch` / `hatchling` 全部未安装：

```text
29C_IMPORT build rc=1 ModuleNotFoundError: No module named 'build'
29C_IMPORT twine rc=1 ModuleNotFoundError: No module named 'twine'
29C_IMPORT hatch rc=1 ModuleNotFoundError: No module named 'hatch'
29C_IMPORT hatchling rc=1 ModuleNotFoundError: No module named 'hatchling'
```

而 `uv build` 成功，因为 `uv_build` 后端随 uv 分发、无需额外下载：

```text
29D_BUILD rc=0 Successfully built dist\duyi_utils-0.1.3.tar.gz
                Successfully built dist\duyi_utils-0.1.3-py3-none-any.whl
```

### 2.5 产物内部结构（实测）

wheel 解压后的条目：

```text
duyi_utils/
duyi_utils/__init__.py
duyi_utils-0.1.3.dist-info/
duyi_utils-0.1.3.dist-info/WHEEL
duyi_utils-0.1.3.dist-info/METADATA
duyi_utils-0.1.3.dist-info/RECORD
```

| 条目 | 作用 | 依据 |
| --- | --- | --- |
| `<包名>/` | 实际代码，安装时原样落到 `site-packages` | `[P4]` |
| `<dist>-<ver>.dist-info/WHEEL` | wheel 元信息（版本、生成器、tag） | `[P4]` |
| `<dist>-<ver>.dist-info/METADATA` | core metadata（`Name`/`Version`/`Requires-*`） | `[P8]` |
| `<dist>-<ver>.dist-info/RECORD` | 每个文件的哈希与大小，用于卸载/校验 | `[P4]` |
| `<dist>-<ver>.dist-info/entry_points.txt` | 有 `[project.scripts]` 时才出现 | `[P3]` |

`METADATA` 实际内容（`[project]` 映射结果）：

```text
Metadata-Version: 2.3
Name: duyi-utils
Version: 0.1.3
Summary: 示例工程
Requires-Python: >=3.12
```

| 观察 | 说明 | 依据 |
| --- | --- | --- |
| `Name` 是 `duyi-utils`（连字符） | METADATA 保留原始名 | `[P8]` |
| 文件名是 `duyi_utils-...whl`（下划线） | 文件名按 PEP 427 规范化 | `[P4]` |
| `Metadata-Version: 2.3` | 后端决定，随 PEP 639 等推进 | `[P8]` |
| `Requires-Python` 直接来自 `requires-python` | 安装器据此拒绝不兼容环境 | `[P3]` |

sdist 解压后的条目：

```text
duyi_utils-0.1.3/PKG-INFO
duyi_utils-0.1.3/pyproject.toml
duyi_utils-0.1.3/pyproject.toml.orig
duyi_utils-0.1.3/src/duyi_utils/__init__.py
```

| 条目 | 作用 | 依据 |
| --- | --- | --- |
| `PKG-INFO` | sdist 的元数据（core metadata 的文本形式） | `[P9]` |
| `pyproject.toml` | 后端可能改写的版本 | `[P9]` |
| `pyproject.toml.orig` | 构建前的原始配置，便于追溯 | `[P9]` |
| `src/` | 完整源码树 | `[P9]` |

实测规范化函数：

```python
from packaging.utils import canonicalize_name, parse_wheel_filename, parse_sdist_filename

parse_wheel_filename("duyi_utils-0.1.3-py3-none-any.whl")
# ('duyi-utils', <Version('0.1.3')>, (), frozenset({<py3-none-any>}))
parse_sdist_filename("duyi_utils-0.1.3.tar.gz")
# ('duyi-utils', <Version('0.1.3')>)
canonicalize_name("Duyi.Utils")   # 'duyi-utils'
canonicalize_name("duyi_utils")   # 'duyi-utils'
```

```text
WHEEL duyi-utils 0.1.3 () ['py3-none-any']
SDIST ('duyi-utils', <Version('0.1.3')>)
CANON duyi-utils duyi-utils
```

> 注意：`Duyi.Utils`、`duyi_utils`、`duyi-utils` 规范化后**是同一个发行版**。这就是为什么 PyPI 上不能同时存在 `duyi-utils` 和 `duyi_utils`——它们冲突。`[P4]` `[P7]`

### 2.6 版本号：PEP 440

| 形式 | 示例 | 排序 | 依据 |
| --- | --- | --- | --- |
| 正式版 | `1.0.0` | 高于任何预发布 | `[P5]` |
| 预发布 | `1.0.0a1` / `1.0.0b2` / `1.0.0rc1` | a < b < rc < 正式 | `[P5]` |
| 开发版 | `1.0.0.dev1` | 低于同号预发布 | `[P5]` |
| 后发布 | `1.0.0.post1` | 高于正式版 | `[P5]` |
| 本地版本 | `1.0.0+cu118` | 仅本地标识，不上传 PyPI | `[P5]` |

实测：

```text
VER_ORDER True True          # 0.1.3 < 0.1.10；1.0.0a1 < 1.0.0
VER_NORMALIZE 1.0 1.0.0.post1  # v1.0 归一为 1.0；post1 保留
```

| 坑 | 说明 | 依据 |
| --- | --- | --- |
| `0.1.10` 与 `0.1.9` 按字符串比会错 | 必须按版本比较（`0.1.10 > 0.1.9`） | `[P5]` |
| `v1.0` 能解析但不建议 | 归一化后是 `1.0`，与 `1.0.0` 等价 | `[P5]` |
| 语义化版本 ≠ PEP 440 | SemVer 的 `+build` 与 PEP 440 本地版本语义不同 | `[P5]` |
| 已发布版本不可覆盖 | PyPI 不允同版本重传 | `[P7]` |

**语义化版本（SemVer）在 Python 里的映射**：

| SemVer | PEP 440 | 说明 |
| --- | --- | --- |
| `MAJOR.MINOR.PATCH` | `1.2.3` | 直接对应 |
| `1.2.3-alpha.1` | `1.2.3a1` | 预发布 |
| `1.2.3-beta.2` | `1.2.3b2` | 预发布 |
| `1.2.3-rc.1` | `1.2.3rc1` | 候选版 |
| `1.2.3+build.5` | `1.2.3+local.5` | 本地标识，PyPI 不接受 |

### 2.7 `requires-python` 与依赖约束

实测：

```text
SPEC_PY True False    # >=3.12 含 3.12.8；不含 3.11.9
REQ python-dateutil >=2.8
REQ_MARKER python_version < "3.11"
```

| 写法 | 含义 | 依据 |
| --- | --- | --- |
| `>=3.12` | 3.12 及以上 | `[P5]` |
| `>=3.12,<3.14` | 区间 | `[P5]` |
| `~=3.12.0` | 兼容版本（`>=3.12.0,<3.13.0`） | `[P5]` |
| `==3.12.*` | 通配 | `[P5]` |

| 依赖写法 | 含义 | 依据 |
| --- | --- | --- |
| `requests` | 任意版本 | `[P3]` |
| `requests>=2.31` | 下限 | `[P3]` |
| `requests~=2.31.0` | 兼容 | `[P3]` |
| `requests[security]` | 带可选依赖 | `[P3]` |
| `tomli>=2; python_version<"3.11"` | 环境标记 | `[P3]` |

> 注意：`requires-python` 只是**声明**，不会让安装器自动降级依赖；实际兼容性要靠 CI 矩阵验证。`[P3]` `[P7]`

### 2.8 三种布局与 `packages` 配置

| 布局 | 目录 | 后端配置 | 依据 |
| --- | --- | --- | --- |
| flat | `duyi_utils/__init__.py` | setuptools 自动发现 | `[P1]` |
| src | `src/duyi_utils/__init__.py` | `packages = ["src/duyi_utils"]` | `[P1]` |
| 多包 | `src/a/`、`src/b/` | `packages = ["src/a", "src/b"]` | `[P1]` |

| src 布局的好处 | 说明 | 依据 |
| --- | --- | --- |
| 必须安装才能导入 | 避免「本地能跑、装完不能跑」 | `[P1]` |
| 测试代码不混入包 | 打包更干净 | `[P9]` |
| 与 `uv_build` 零配置契合 | `src/<name>` 自动识别 | `[G1]` |

## 3. 发布和安装

### 3.1 发布前的准备

课件原文：

```shell
# 先构建（略）
pip install twine
twine check dist/*        # 【可选】验证构建产物的完整性
```

| 检查项 | 作用 | 依据 |
| --- | --- | --- |
| `twine check` | 校验 `METADATA` 与 `README` 渲染是否合法 | `[P7]` |
| 干净 venv 安装 | 验证 wheel 真的能装能用 | `[P7]` |
| TestPyPI 演练 | 验证上传流程与权限 | `[P7]` |
| 版本号未用过 | 避免上传被拒 | `[P7]` |

**上传前自查清单**：

```text
1 python -m build                       构建两类产物
2 twine check dist/*                    元数据合法性
3 pip install dist/*.whl（干净 venv）    安装 + import + 冒烟
4 twine upload --repository testpypi dist/*   TestPyPI 演练
5 twine upload dist/*                   正式上传
6 git tag v0.1.3                        与版本对齐
```

| 步骤 | 失败后的表现 | 依据 |
| --- | --- | --- |
| 1 | `dist/` 缺 wheel 或 sdist | `[P7]` |
| 2 | `twine` 报 `InvalidDistribution` | `[P7]` |
| 3 | `import` 报 `ModuleNotFoundError`（`packages` 配错） | 实测 2.5 |
| 4–5 | `403`/`400 File already exists` | `[P7]` |

### 3.2 发布到官方仓库（PyPI）

课件原文步骤：

1. 注册账号：https://pypi.org/account/register/
2. 创建 token：https://pypi.org/manage/account/token/
3. 复制 token
4. 运行 `twine upload dist/*` 上传

| 方式 | 命令 | 依据 |
| --- | --- | --- |
| 交互式 | `twine upload dist/*`（提示输入用户名/密码） | `[P7]` |
| token + 环境变量 | `TWINE_USERNAME=__token__ TWINE_PASSWORD=pypi-xxx twine upload dist/*` | `[P7]` |
| uv | `UV_PUBLISH_TOKEN=pypi-xxx uv publish` | `[G1]` |
| 配置文件 | `~/.pypirc`（权限 600，不入库） | `[P7]` |

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| token 用户名固定为 `__token__` | 不是账号名 | `[P7]` |
| 上传后不可删改同版本 | 只能 yank（撤回） | `[P7]` |
| 2FA 是 PyPI 强制要求 | 上传必须用 token，不能用密码 | `[P7]` |
| 元数据不可改 | `description` 等一旦发布即固定 | `[P7]` |

> 注意：**上传不可逆**。版本号写错就只能发一个新版本并 yank 旧的；yank 不等于删除，`pip install pkg==bad-version` 仍可能命中（除非约束排除）。所以第 4 步的 TestPyPI 演练不是可选项。`[P7]`

### 3.3 发布到私有仓库

课件原文：通常使用云服务完成私有仓库搭建，以阿里云效制品仓库为例：

1. 创建阿里云效制品仓库 https://packages.aliyun.com/
2. 按照仓库指南配置并上传包

安装侧配置（作为镜像源）：

```ini
[global]
index-url = 制品仓库地址
extra-index-url = 镜像源地址
trusted-host = packages.aliyun.com
```

然后 `pip install xxx` 即可。

| 方案 | 说明 | 依据 |
| --- | --- | --- |
| 云厂商托管（阿里云效、腾讯云、AWS CodeArtifact） | 免运维，按量计费 | `[P7]` |
| 自建（devpi、Nexus、Artifactory） | 可控，需运维 | `[P7]` |
| 文件共享目录（`--find-links`） | 最简，无索引能力 | `[P7]` |

| 配置项 | 作用 | 依据 |
| --- | --- | --- |
| `index-url` | 主索引地址 | `[P7]` |
| `extra-index-url` | 附加索引（公共源兜底） | `[P7]` |
| `trusted-host` | 允许 HTTP 或不校验证书的主机 | `[P7]` |
| 认证 | `index-url = https://user:pass@host/simple`（**不要入库**） | `[P7]` |

| 风险 | 说明 | 依据 |
| --- | --- | --- |
| `extra-index-url` 的依赖混淆攻击 | 私有包名被公共源同名包抢占 | `[P7]` |
| 凭据写进 `pip.conf` 后进入镜像 | 泄露 | 第 01 章安全底线 |
| `trusted-host` 放宽 TLS | 中间人风险 | `[P7]` |

> 注意：`extra-index-url` 会让 pip 在**两个源里挑最高版本**，不是「私有源优先」。防御依赖混淆要靠私有源独占包名 + `--index-url` 只指私有源 + 明确的 `--no-index` 场景。`[P7]`

### 3.4 安装侧

| 命令 | 场景 | 依据 |
| --- | --- | --- |
| `pip install duyi-utils` | 最新版 | `[P7]` |
| `pip install duyi-utils==0.1.3` | 精确版本 | `[P7]` |
| `pip install duyi-utils[test]` | 带可选依赖 | `[P3]` |
| `uv add duyi-utils` | 写入项目依赖并锁定 | `[G1]` |
| `pip install dist/*.whl` | 本地产物 | `[P7]` |

### 3.5 元数据与入口点的运行时读取

实测：

```text
META pip 24.3.1 >=3.8
EP_COUNT 27 ['agent-detector', 'pybabel', 'normalizer', 'detect-installer-test', 'email_validator']
```

```python
import importlib.metadata as metadata

metadata.metadata("pip")["Requires-Python"]        # '>=3.8'
metadata.entry_points(group="console_scripts")     # 27 个命令行入口
metadata.version("pip")                           # '24.3.1'
```

| 用途 | API | 依据 |
| --- | --- | --- |
| 读版本（不要在代码里硬编码） | `importlib.metadata.version("pkg")` | `[P8]` |
| 读依赖声明 | `metadata.requires("pkg")` | `[P8]` |
| 发现插件 | `entry_points(group="...")` | `[P3]` |
| 校验安装完整性 | `PackageMetadata` 各字段 | `[P8]` |

## 4. 可编辑依赖

### 4.1 是什么

课件原文：

> 可编辑安装（editable install）又称开发模式安装，通过 `pip install -e .` 将项目以链接形式安装到当前环境。
>
> 当项目被可编辑安装后，你对源码的任何修改都会**即时生效**，无需重新构建和重新安装。

| 场景 | 用可编辑安装 | 理由 | 依据 |
| --- | --- | --- | --- |
| 在 A 项目里开发公共库，B 项目实时引用 | ✅ | 改完即生效 | `[P6]` |
| 多包 workspace 本地联调 | ✅ | 免反复 `pip install` | `[G1]` |
| 生产部署 | ❌ | 依赖本地路径，不可复现 | `[P6]` |
| 发布前验证 | ❌ | 必须装 wheel 才能验证真实产物 | `[P7]` |

### 4.2 原理：`.pth` 一行路径

课件原文：

> 其原理是在 `site-packages` 中创建一个指向项目源码的链接（`.pth` 文件），而不是复制一份代码过去。

实测（PEP 660 由 `uv pip install -e .` 生成）：

```text
29D_EDITABLE_MARKERS ['_virtualenv.pth', 'duyi_utils.pth']
29D_PTH_CONTENT duyi_utils.pth ['C:\\...\\py29d_szwumax3\\src']
29D_IMPORT_FROM_VENV rc=0 C:\...\src\duyi_utils\__init__.py | hello
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| `site-packages` 里多一个 `<名字>.pth` | 内容是**路径**，不是代码 | `[P6]` |
| `.pth` 每行会被加到 `sys.path` | 解释器启动时由 `site` 模块处理 | `[P6]` |
| src 布局指向 `src` | 所以 `import duyi_utils` 能找到 | 实测 |
| 改源码立即生效 | 因为导入的就是源码文件 | `[P6]` |

再验证一次 `.pth` 的机制（纯标准库）：

```python
import pathlib, site, tempfile

root = pathlib.Path(tempfile.mkdtemp())
target = root / "src"
(target / "demo_pkg").mkdir(parents=True)
(target / "demo_pkg" / "__init__.py").write_text("VALUE = 42\n", encoding="utf-8")

site_dir = root / "site-packages"
site_dir.mkdir()
(site_dir / "demo_pkg.pth").write_text(str(target) + "\n", encoding="utf-8")

site.addsitedir(str(site_dir))
import demo_pkg
print(demo_pkg.VALUE)
```

```text
PTH_IMPORT 42 <tmp>\src\demo_pkg\__init__.py
PTH_IN_PATH True
```

| 结论 | 说明 | 依据 |
| --- | --- | --- |
| `.pth` 只是「加一个 sys.path 条目」 | 不含任何安装逻辑 | `[P6]` |
| 所以「可编辑」的本质是**路径导入** | 不是硬链接、不是符号链接 | `[P6]` |
| 也意味着源码目录被删 = 导入失败 | 无兜底 | `[P6]` |

### 4.3 PEP 660：现代可编辑安装

| 对比 | 传统 `.pth`（PEP 660 之前） | PEP 660 标准实现 | 依据 |
| --- | --- | --- | --- |
| 做法 | 直接写源码路径到 `.pth` | 后端生成 `__editable__` 查找器或 `.pth` | `[P6]` |
| 兼容性 | 只对纯 Python 有效 | 后端可支持编译扩展 | `[P6]` |
| 元数据 | 常缺失 | 生成完整的 `dist-info` | `[P6]` |
| 声明 | 后端须声明 `build_editable` 钩子 | 无钩子的后端报错 | `[P6]` |

| 命令 | 行为 | 依据 |
| --- | --- | --- |
| `pip install -e .` | 走 PEP 660 | `[P6]` |
| `pip install -e . --config-settings editable_mode=compat` | 回退传统 `.pth` | `[P6]` |
| `uv pip install -e .` | 同 PEP 660，速度快 | `[G1]` |
| `uv sync` | workspace 成员默认就是可编辑安装 | `[G1]` |

**实测的可编辑安装元数据**：

```text
31B_EDITABLE  Package Version Editable project location
              agents  0.1.0   C:\...\packages\agents
              shared  0.1.0   C:\...\packages\shared
```

| 观察 | 说明 |
| --- | --- |
| `uv pip list` 里标注 `Editable project location` | 说明装的是链接不是副本 |
| 成员间 `import` 直接走源码 | workspace 联调的基础 |

### 4.4 什么时候不要用

| 场景 | 问题 | 依据 |
| --- | --- | --- |
| CI 里用 `-e` 测发布 | 测的不是 dist 产物 | `[P7]` |
| Docker 镜像里用 `-e` | 源码路径不存在，启动失败 | `[P6]` |
| 依赖源码里的绝对路径 | 换机器即坏 | `[P6]` |
| 多人共享一个环境 | 互相覆盖 | 第 02 章 |

## 5. 综合示例：只读解析 pyproject 并给出构建建议

```python
"""第 29 章综合示例：解析 pyproject.toml 并做基础体检。"""

from __future__ import annotations

import tomllib

from packaging.specifiers import SpecifierSet
from packaging.version import Version

DOCUMENT = """
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "agent-tools"
version = "0.1.3"
requires-python = ">=3.12"
dependencies = ["python-dateutil>=2.8", "Markdown>=3.5"]

[tool.hatch.build.targets.wheel]
packages = ["src/agent_tools"]
"""


def inspect(document: str) -> dict[str, object]:
    data = tomllib.loads(document)
    project = data["project"]
    build = data.get("build-system", {})
    reports = {
        "name": project["name"],
        "version_ok": Version(project["version"]) >= Version("0.1.0"),
        "python_ok_for_312": SpecifierSet(project["requires-python"]).contains("3.12.8"),
        "has_backend": bool(build.get("build-backend")),
        "dependency_count": len(project.get("dependencies", [])),
        "wheel_targets": data.get("tool", {}).get("hatch", {}).get("build", {}).get("targets", {}).get("wheel", {}).get("packages", []),
    }
    return reports


print("REPORT", inspect(DOCUMENT))
```

本机实测输出：

```text
REPORT {'name': 'agent-tools', 'version_ok': True, 'python_ok_for_312': True, 'has_backend': True, 'dependency_count': 2, 'wheel_targets': ['src/agent_tools']}
```

**逐段说明**：

| 代码 | 用到的机制 | 依据 |
| --- | --- | --- |
| `tomllib.loads` | 标准库 3.11+ 只读 TOML | 第 22 章 |
| `Version(...) >= Version("0.1.0")` | PEP 440 比较，不是字符串比较 | `[P5]` |
| `SpecifierSet(...).contains("3.12.8")` | 判断运行时是否满足声明 | `[P5]` |
| `data["tool"]["hatch"]["build"]` | `[tool.<backend>]` 是后端私有配置 | `[P1]` |

> 注意：这段代码只读不写，适合放进 CI 的「打包体检」步骤。生产环境不要用 `tomllib` 去改配置——它是只读解析器。`[P5]`

## 6. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 没有 `[build-system]` | 回退 setuptools 隐式构建，行为漂移 | 显式声明后端 | `[P1]` |
| `build-backend` 写模块名猜错 | `BackendUnavailable` | 用文档给的完整路径 | `[P1]` |
| `requires` 漏了后端本身 | 隔离环境里构建失败 | `requires = ["hatchling"]` | `[P2]` |
| `packages` 路径写错 | wheel 里没有代码，装完 import 失败 | 构建后解压检查 | `[P4]` |
| flat 布局又写 `packages = ["src/..."]` | 打包为空 | 布局与配置对齐 | `[P1]` |
| `name` 用大写或点 | 规范化后可能与他人冲突 | 小写 + 连字符 | `[P4]` |
| `version` 写 `v1.0` | 能解析但不规范 | 写 `1.0.0` | `[P5]` |
| 版本号按字符串比大小 | `0.1.10 < 0.1.9` 判错 | 用 `Version` 比较 | `[P5]` |
| 已发布版本重传 | `400 File already exists` | 升版本号 | `[P7]` |
| 用密码上传 PyPI | 403（2FA 强制） | `__token__` + token | `[P7]` |
| token 写进 `pyproject.toml` | 泄露 | 环境变量 / CI secret | 第 01 章 |
| 不跑 `twine check` | README 渲染错、元数据非法 | 上传前必查 | `[P7]` |
| 只在 TestPyPI 验证就完事 | 正式源权限/名占用未验证 | 两处都过一遍 | `[P7]` |
| 直接用 `pip install -e .` 测发布 | 测的不是 dist 产物 | 干净 venv 装 wheel | `[P7]` |
| `requires-python` 写 `>=3.14` 但 CI 只测 3.12 | 用户装不上或跑不通 | CI 矩阵与声明一致 | `[P3]` |
| `dependencies` 塞 pytest/ruff | 生产镜像变大 | 用 `--dev` / 可选依赖组 | 第 30 章 |
| 依赖不写下限 | 装到不兼容的旧版 | `>=x.y` | `[P3]` |
| 依赖写死 `==` | 与上游其他包冲突 | 用 `~=` 或 `>=` | `[P5]` |
| `readme` 指向不存在的文件 | 构建报错 | 路径与实际一致 | `[P3]` |
| `[project.scripts]` 指向不存在的函数 | 装好后命令报 `ImportError` | 路径写 `模块:函数` | `[P3]` |
| `[project.scripts]` 的模块名含连字符 | `ModuleNotFoundError` | 用导入名（下划线） | `[P3]` |
| 把 `tests/` 打进 wheel | 包体积膨胀 | 用 `packages` 精确指定 | `[P9]` |
| 把 `.venv/` 打进 sdist | 产物巨大且含绝对路径 | `MANIFEST.in` / 后端排除 | `[P9]` |
| sdist 里没有 `pyproject.toml` | 无法从 sdist 重建 wheel | 检查后端 include 配置 | `[P9]` |
| 依赖 `uv_build` 却用 `python -m build` | 需要联网下载 `uv_build` | 统一前端 | `[G1]` |
| 离线环境用 `python -m build` | 装不上 `hatchling` | 预拉取或改用 `uv build` | `[P2]` |
| 私有源只配 `extra-index-url` | 依赖混淆攻击 | 私有包名独占 + 单索引 | `[P7]` |
| 凭据写进 `pip.conf` 提交 | 泄露 | 环境变量 / keyring | 第 01 章 |
| `trusted-host` 图省事全局放开 | TLS 校验失效 | 仅限内网主机 | `[P7]` |
| 生产镜像里 `pip install -e` | 启动即崩 | 装 wheel | `[P6]` |
| `.pth` 里的路径是绝对路径 | 换机器失效 | 由工具生成，不手写 | `[P6]` |
| 手动往 `site-packages` 丢 `.pth` | 环境不可复现 | 用 `pip install -e` | `[P6]` |
| 用 `--no-build-isolation` 加速 | 污染环境、结果不可复现 | 默认隔离 | `[P1]` |
| 构建时改了源码版本号但没重构建 | 产物版本与实际不符 | 构建前检查 `git status` | `[P7]` |
| `dist/` 里混着上一个版本的产物 | 上传了旧包 | 上传前清空 `dist/` | `[P7]` |
| 用 `yank` 当删除 | 消费者仍可能装到 | 发新版本 + 约束排除 | `[P7]` |
| 忽略 `RECORD` 校验 | 安装损坏不报错 | 用 `pip check` | `[P4]` |
| 在代码里硬编码版本号 | 与包元数据不一致 | `importlib.metadata.version` | `[P8]` |
| `classifiers` 写了已废弃的状态 | PyPI 展示错误 | 按官方列表更新 | `[P3]` |
| wheel 文件名手写不规范 | 安装器无法识别 | 交给后端生成 | `[P4]` |
| 在 PyPI 与私有源用同一版本号 | 升级来源不明 | 版本号全局唯一 | `[P7]` |

## 7. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 元数据集中在一个 `pyproject.toml` | 不散落 `setup.py`/`setup.cfg` | `[P3]` |
| 用 src 布局 | 强制「装过才能 import」 | `[P1]` |
| `requires-python` 与 CI 矩阵一致 | 声明可信 | `[P3]` |
| 版本号来自单一来源 | `pyproject.toml` 或动态版本插件 | `[P3]` |
| 运行时读版本用 `importlib.metadata` | 不硬编码 | `[P8]` |
| 上传用 token + 环境变量 | 不落盘 | `[P7]` |
| 先 TestPyPI 再正式 | 上传不可逆 | `[P7]` |
| CI 做「构建 → 装 wheel → 冒烟」 | 验证真实产物 | `[P7]` |
| 发布与 `git tag` 对齐 | 可追溯 | `[P7]` |
| changelog 与版本同步 | 用户可读 | `[P3]` |
| 私有源独占包名 | 防依赖混淆 | `[P7]` |
| 开发期用 `-e`、发布前用 wheel | 各归其位 | `[P6]` |

**风格示范**：

```python
"""release 模块：读取自身包元数据，避免版本号硬编码。

为什么从元数据读：版本号只在 pyproject.toml 维护一处，代码不会漂移。
"""

from __future__ import annotations

import importlib.metadata

DISTRIBUTION = "duyi-utils"


def current_version() -> str:
    """返回已安装的发行版版本；未安装时抛出 PackageNotFoundError。"""
    return importlib.metadata.version(DISTRIBUTION)
```

**命令清单（可直接抄进 README）**：

```powershell
# 构建
uv build

# 检查产物
uv run --with twine twine check dist/*

# 装到干净环境验证
uv venv .verify
uv pip install --python .verify\Scripts\python.exe dist\duyi_utils-0.1.3-py3-none-any.whl
.verify\Scripts\python.exe -c "import duyi_utils; print(duyi_utils.__version__)"

# 发布（token 走环境变量）
$env:UV_PUBLISH_TOKEN = "pypi-xxx"
uv publish
```

**边界**：

- 纯 Python 包的 `py3-none-any` wheel 与平台无关；含 C 扩展则必须按平台/ABI 出多个 wheel（本课不覆盖）。
- `sdist` 必须能独立重建 wheel，否则下游装不了。
- 私有源的可用性、鉴权、审计在企业内是独立课题。

## 8. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[P1]` | PEP 官方 | https://peps.python.org/pep-0517/ | 构建后端接口、`build_wheel`/`build_sdist`、前后端分离 |
| `[P2]` | PEP 官方 | https://peps.python.org/pep-0518/ | `[build-system]`、`requires`、构建隔离 |
| `[P3]` | PEP 官方 | https://peps.python.org/pep-0621/ | `[project]` 元数据字段、`dependencies`、`scripts`、`requires-python` |
| `[P4]` | PEP 官方 | https://peps.python.org/pep-0427/ | wheel 文件名与内部布局、`.dist-info` |
| `[P5]` | PEP 官方 | https://peps.python.org/pep-0440/ | 版本标识与比较、`~=`/`==` 语义 |
| `[P6]` | PEP 官方 | https://peps.python.org/pep-0660/ | 可编辑安装（editable）标准 |
| `[P7]` | PyPA 官方 | https://packaging.python.org/en/latest/tutorials/packaging-projects/ | `python -m build`、`twine`、TestPyPI、私有索引、上传流程 |
| `[P8]` | PyPA 官方 | https://packaging.python.org/en/latest/specifications/core-metadata/ | core metadata 字段、`Metadata-Version` |
| `[P9]` | PyPA 官方 | https://packaging.python.org/en/latest/specifications/source-distribution-format/ | sdist 格式、`PKG-INFO`、`pyproject.toml.orig` |
| `[P10]` | PEP 官方 | https://peps.python.org/pep-0008/ | 包/模块命名、注释写「为什么」 |

> **核对状态**：`[P10]` 与本章 `README.md` 已核对来源一致；`[P1]`–`[P9]` 按官方规范结构整理，**本次未逐页直连复核**（课件原文中的 PEP 0517/0427 链接与本章一致）。文中「实测」为本机 Python 3.12.8 + uv 0.12.2 的真实输出；`build`/`twine`/`hatchling` 本机未安装，相关命令行为按官方文档陈述，未执行。

## 9. 毕业自查清单

**能说清（概念层）**：

- [ ] 源码 → wheel → registry → site-packages 四步各自做什么
- [ ] sdist 与 wheel 的区别与适用场景
- [ ] 构建前端与后端的职责边界
- [ ] `[build-system]`、`[project]`、`[tool.<backend>]` 各管什么
- [ ] wheel 里 `dist-info` 三个文件的作用
- [ ] `Metadata-Version: 2.3` 从哪来
- [ ] PEP 440 里预发布/开发版/后发布的排序
- [ ] 为什么上传不可逆、`yank` 不等于删除
- [ ] 可编辑安装的 `.pth` 原理
- [ ] PEP 660 相比传统 `.pth` 解决了什么

**能写出（代码层）**：

- [ ] 一份可直接 `uv build` 的 `pyproject.toml`（src 布局）
- [ ] `[project.scripts]` 命令行入口
- [ ] 可选依赖组 + `pip install pkg[test]`
- [ ] `tomllib` 只读体检脚本（第 5 节）
- [ ] `importlib.metadata` 读版本与 entry points
- [ ] `pip install -e .` 后验证 `.pth` 内容

**能判断（避坑层）**：

- [ ] 看到 `packages` 配错能预判「装完 import 失败」
- [ ] 看到版本号按字符串比较能指出错
- [ ] 看到 `extra-index-url` 能指出依赖混淆风险
- [ ] 看到生产镜像 `pip install -e` 能指出路径失效
- [ ] 看到 `dependencies` 混开发工具能指出分组问题
- [ ] 看到 `dist/` 残留旧产物能指出会误传

**能跑通（验收层）**：

- [ ] 运行 `examples/packaging_demo.py` 并解释三段输出
- [ ] 把第 5 节示例存成文件运行，输出与文档一致
- [ ] 用 `uv build` 产出 wheel 与 sdist，并解压核对内部结构
- [ ] 在干净 venv 里装 wheel 并 `import` 成功

## 10. 下一章衔接

第 30 章 `项目管理工具`：构建发布解决「怎么分发」，下一章解决「怎么可复现地装、锁、跑」——`uv` 的完整生命周期、锁文件、依赖组、`Makefile` 统一入口。

本章留下的伏笔：

1. `uv build` 已经在用，第 30 章把它放回「初始化 → 装依赖 → 锁定 → 运行 → 构建 → 发布」的完整链路。
2. `pyproject.toml` 的 `[dependency-groups]` / `--dev` 分工在第 30 章展开。
3. 本章的私有源配置在第 30 章的镜像源设置里会再出现一次。