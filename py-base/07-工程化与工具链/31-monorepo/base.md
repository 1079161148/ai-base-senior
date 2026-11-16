# 31 monorepo · 完整版（base.md）

> `README.md` 是「最小闭环」；本文件把课件里的「什么是 Monorepo、Multirepo VS Monorepo、搭建 Workspace 五步、包间依赖的三种模式」逐条展开，并补上课件没写但会踩的部分：`uv.lock` 在 workspace 里的唯一性、`(workspace)` 标记的读法、依赖方向与环形依赖（**实测 uv 不检测环**）、统一版本 vs 独立版本、CI 增量构建，目标是**学一遍即可毕业**。

| 项 | 内容 |
| --- | --- |
| 适用版本 | uv 0.12.2 / Python 3.12.8（Windows 实测） |
| 前置 | 第 21、29、30 章（包、构建、工具链） |
| 覆盖范围 | monorepo 取舍、workspace 搭建全流程、`[tool.uv.workspace]`、`[tool.uv.sources]` 四种来源、依赖方向与环、版本策略、构建与发布、CI 增量 |
| 明确不覆盖 | Bazel/Nx 等外部构建编排、远程缓存、多语言 monorepo |
| 学完验收 | 能从零搭一个可运行的三包 workspace、能解释 `(workspace)` 标记、能识别并打断循环依赖（见第 10 节） |

## 0. 怎么用这份文件

**依据约定**：行内 `` `[Mn]` `` 指向第 9 节官方链接；标「实测」的是本机 uv 0.12.2 / Windows 运行结果。

**推荐顺序**：

```text
1 什么是 Monorepo（第 1 节）   → 先判断该不该用
2 搭建 Workspace（第 2 节）    → 五步主线（重点）
3 包间依赖三种模式（第 3 节）  → sources 的四种写法
4 依赖方向与环（第 4 节）      → 架构约束
5 版本策略（第 5 节）          → 发版取舍
6 综合示例（第 6 节）
7 注意事项（第 7 节）          → 41 条错误对照
```

**与 README 的分工**：README 给结论与边界，本文件负责配置逐字段、实测证据与工程约束。冲突时以本文件为准。

## 1. 什么是 Monorepo

### 1.1 定义

**Monorepo（单一仓库）**：把多个相关的项目/包放在同一个代码仓库里管理的策略。

```text
my-monorepo/
├── packages/
│   ├── shared/          # 公共工具库
│   ├── agents/          # 业务能力包
│   └── client-sdk/      # 客户端 SDK
├── apps/
│   └── web-service/     # 可部署的服务
├── pyproject.toml       # workspace 根配置
├── uv.lock              # 全仓唯一锁文件
└── Makefile
```

| 术语 | 含义 | 依据 |
| --- | --- | --- |
| 仓库（repo） | 一个版本控制单元 | —— |
| 成员（member） | 仓库里的一个包，有自己的 `pyproject.toml` | `[M1]` |
| 根（root） | 声明 `members` 的 `pyproject.toml` | `[M1]` |
| 虚拟根（virtual root） | 不参与构建、只做 workspace 锚点 | `[M1]` |
| 锁（lock） | 全 workspace 共用一份 `uv.lock` | `[M1]` |

> 注意：monorepo 不等于「把所有代码塞一个目录」。判定标准是**是否共享一套版本控制 + 一套依赖解析 + 一套 CI**。三个仓库用同一个 CI 也不算 monorepo。`[M1]`

### 1.2 Multirepo VS Monorepo

课件给的六维对比：

| 对比维度 | MultiRepo | Monorepo |
| --- | --- | --- |
| **代码共享** | 需要发版、发布 pip 包才能共享 | 源码级别直接引用，即时生效 |
| **原子提交** | 跨仓库改动需要多个 PR 协同 | 一次提交完成所有关联改动 |
| **工具规范** | 各仓库独立配置工具 | 统一的工具与规范 |
| **重构成本** | 跨仓库重构代价极高 | 工具链覆盖整个仓库，安全重构 |
| **CI/CD** | 多个 Pipeline 各自独立 | 统一 CI，可增量检测受影响的包 |
| **适用场景** | 团队独立、版本节奏不一致的项目 | 紧密协作的微服务、SDK 集合、工具链 |

补充两个常被忽略的维度：

| 维度 | MultiRepo | Monorepo | 依据 |
| --- | --- | --- | --- |
| 权限粒度 | 按仓授权，天然隔离 | 单仓难按包控制写权限 | `[M1]` |
| 仓库体积/克隆时间 | 只拉需要的 | 全量克隆，历史越长越慢 | `[M1]` |

### 1.3 收益与代价（取舍）

| 收益 | 说明 | 依据 |
| --- | --- | --- |
| 原子改动 | 接口变更 + 调用方修改一次提交 | `[M1]` |
| 源码级共享 | 免发布即可联调 | `[M1]` |
| 统一依赖解析 | 一份 `uv.lock` 消除版本地狱 | `[M1]` |
| 统一工具链 | lint/format/test 一套配置 | `[M1]` |
| 易于安全重构 | 全仓搜索替换 + 一次 CI | `[M1]` |

| 代价 | 说明 | 缓解 | 依据 |
| --- | --- | --- | --- |
| CI 时间随包数增长 | 全量跑太慢 | 变更检测 + 只跑受影响包 | `[M1]` |
| 发布耦合 | 统一版本会让未改的包也发版 | 独立版本策略 | `[M1]` |
| 权限边界变粗 | 单仓难以按包控权 | CODEOWNERS + 目录审阅 | —— |
| 仓库体积 | 克隆与 IDE 索引变慢 | 稀疏检出 / 分包 | —— |

> 注意：判断标准不是「是否先进」，而是**跨包改动是否高频**。跨包改动一周一次 → 发布 pip 包更省事；一天多次 → monorepo 才有净收益。`[M1]`

## 2. 搭建 Workspace

### 2.1 第一步：初始化根项目

```shell
mkdir my-monorepo && cd my-monorepo
uv init
```

根级 `pyproject.toml` 加 members：

```toml
[tool.uv.workspace]
members = [
    "packages/*",
    "apps/*",
]
```

`members` 支持 glob：

| 模式 | 匹配范围 | 依据 |
| --- | --- | --- |
| `packages/*` | `packages/` 下的**直接**子目录 | `[M1]` |
| `packages/**` | 所有层级子目录（含嵌套） | `[M1]` |
| `libs/*` | `libs/` 下直接子目录 | `[M1]` |
| `apps/*` | `apps/` 下直接子目录 | `[M1]` |

多个目录可同时配置：

```toml
[tool.uv.workspace]
members = [
    "packages/*",
    "apps/*",
    "libs/*",
]
```

| 可选键 | 作用 | 依据 |
| --- | --- | --- |
| `exclude` | 排除某些目录（即使匹配 glob） | `[M1]` |

**根要不要可安装？**

| 根类型 | 配置 | 适用 | 依据 |
| --- | --- | --- | --- |
| 虚拟根 | `[tool.uv] package = false` | 根不含代码，只做锚点 | `[M1]` |
| 实体根 | 有 `[build-system]` + 源码 | 根本身也是个包 | `[M1]` |

本课实测用的虚拟根：

```toml
[project]
name = "mono-root"
version = "0.1.0"
requires-python = ">=3.12"

[tool.uv.workspace]
members = ["packages/*", "apps/*"]

[tool.uv]
package = false
```

> 注意：虚拟根仍需 `[project]`（`name`/`version`），否则 uv 无法把它作为 workspace 锚点解析。`[M1]`

### 2.2 第二步：创建成员包

```shell
uv init --lib packages/shared
uv init --lib packages/agents
uv init app apps/web-service
```

实测结构（本课用 `uv_build` 后端手写）：

```text
packages/shared/pyproject.toml
packages/shared/src/shared/__init__.py
packages/agents/pyproject.toml
packages/agents/src/agents/__init__.py
apps/web-service/pyproject.toml
apps/web-service/main.py
```

| `uv init` 变体 | 生成 | 用途 | 依据 |
| --- | --- | --- | --- |
| `--lib` | src 布局 + 可发布后端 | 被他人依赖的包 | `[M3]` |
| `--app`（默认） | 可执行入口 + 后端 | 可部署服务 | `[M3]` |
| `--package` | 可安装 | 需要被 `import` | `[M3]` |
| `--no-package` | 不安装 | 纯脚本集合 | `[M3]` |
| `--no-workspace` | 不继承根 workspace | 独立子项目 | `[M3]` |

> 注意：`uv init` 在有 workspace 根的目录下默认会**自动加入**该 workspace。若不想加入，必须显式 `--no-workspace`，否则会被根 `members` 捕获。`[M3]`

### 2.3 第三步：成员包依赖

```toml
# packages/agents/pyproject.toml
[project]
name = "agents"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["shared"]

[tool.uv.sources]
shared = { workspace = true }

[build-system]
requires = ["uv_build>=0.12.2,<0.13.0"]
build-backend = "uv_build"
```

```toml
# apps/web-service/pyproject.toml
[project]
name = "web-service"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["agents"]

[tool.uv.sources]
agents = { workspace = true }
```

| 机制 | 作用 | 依据 |
| --- | --- | --- |
| `dependencies = ["shared"]` | 声明依赖名 | `[M6]` |
| `[tool.uv.sources] shared = { workspace = true }` | 告诉 uv「不从 PyPI 下，用工作区成员」 | `[M2]` |
| 成员必须可安装（有 `build-system`） | 否则无法作为依赖 | `[M9]` |

> 注意：`[tool.uv.sources]` 是 workspace 的**核心机制**。没有它，`dependencies = ["shared"]` 会去 PyPI 找 `shared`——很可能找到一个同名但无关的包，或者直接解析失败。`[M2]`

**同名优先级**：

| 情况 | uv 行为 | 依据 |
| --- | --- | --- |
| PyPI 与 workspace 同名，且写了 `workspace = true` | 用 workspace | `[M2]` |
| 想强制走 PyPI | `shared = { workspace = false }` | `[M2]` |
| 未写 `sources` | 走 PyPI（注意依赖混淆） | `[M2]` |

### 2.4 [可选] 第四步：同步安装

```shell
uv sync --all-packages
```

执行后：

```text
1 读取所有成员包的 pyproject.toml
2 解析完整依赖树（含成员间依赖）
3 在根目录生成统一 uv.lock
4 在根目录创建 .venv，安装所有依赖
```

实测：

```text
31B_SYNC_ALL rc=0  Resolved 4 packages in 2ms | Building agents @ file:///.../packages/agents
                   Building shared @ file:///.../packages/shared
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 锁文件在**根**，不在成员目录 | 全仓唯一 | `[M1]` |
| `.venv` 在**根** | 所有成员共享 | `[M1]` |
| 成员以**可编辑**方式装入 | 改源码即生效 | `[M1]` |
| `--all-packages` 才装全部成员 | 默认只装根 | `[M1]` |

**实测的可编辑安装证据**：

```text
31B_EDITABLE  Package Version Editable project location
              agents  0.1.0   C:\...\packages\agents
              shared  0.1.0   C:\...\packages\shared
```

| 观察 | 说明 |
| --- | --- |
| `Editable project location` 指向源码目录 | 装的是链接不是副本 |
| 两个成员共享同一个 `.venv` | 依赖版本天然一致 |

**离线时的现实约束**（实测）：

| 后端 | `uv sync --all-packages --offline` | 原因 |
| --- | --- | --- |
| `uv_build` | ✅ 成功 | 后端随 uv 分发 |
| `hatchling` | ❌ 失败 | 需下载 `hatchling` 到隔离构建环境 |

```text
31_SYNC_ALL rc=1  Building agents @ ... | Building shared @ ...
31_BUILD_SHARED rc=2  error: Failed to build ... Caused by: Failed to resolve requirements from build-system.requires
```

| 结论 | 说明 | 依据 |
| --- | --- | --- |
| 纯离线环境优先 `uv_build` | 零额外依赖 | `[M9]` |
| 用 hatchling 需先预热缓存 | `uv cache` 里有才能离线 | `[M9]` |
| CI 里通常联网，不受影响 | 但要显式配置索引 | `[G9]` |

### 2.5 第五步：运行

```shell
uv run --package web-service python apps/web-service/main.py
```

实测：

```text
31B_RUN_PACKAGE rc=0  MAIN agents<-shared-ok
```

源码链路：`main.py` → `import agents` → `agents/__init__.py` 里 `from shared import VALUE` → `shared.VALUE = "shared-ok"`。

| 参数 | 作用 | 依据 |
| --- | --- | --- |
| `--package <名>` | 用该成员的依赖环境运行 | `[M1]` |
| `--all-packages` | 所有成员可见 | `[M1]` |
| 不指定 | 用根环境 | `[M1]` |

> 注意：不指定 `--package` 时，`uv run` 用的是**根**的依赖集。若根是虚拟（`package = false`）且没声明依赖，成员的三方依赖可能不可见——这是最常见的「明明装了却 import 失败」。`[M1]`

### 2.6 [可选] 使用 Makefile

```makefile
.PHONY: run-web
run-web:
	uv run --package web-service python apps/web-service/main.py
```

推荐补全：

```makefile
.PHONY: sync test build ci run-web

sync:
	uv sync --all-packages --locked

test:
	uv run --all-packages pytest -q

build:
	uv build --all-packages

run-web:
	uv run --package web-service python apps/web-service/main.py

ci: sync test build
```

| 目标 | 说明 | 依据 |
| --- | --- | --- |
| `sync` | `--locked` 防锁漂移 | 第 30 章 |
| `build` | `--all-packages` 全构建 | `[M9]` |
| Tab 缩进 | 必须真 Tab | 第 30 章 |

### 2.7 [可选] 安装第三方依赖

```shell
# 给某个成员包添加
uv add --package agents httpx

# 给项目根添加（开发工具）
uv add --dev ruff pytest
```

| 场景 | 命令 | 依据 |
| --- | --- | --- |
| 成员需要三方库 | `uv add --package <名> <pkg>` | `[M1]` |
| 全仓共用的开发工具 | `uv add --dev <pkg>`（根） | `[M1]` |
| 只在某成员用 | 成员自己的 `dev` 组 | `[M1]` |

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 依赖写进成员的 `pyproject.toml` | 不在根 | `[M1]` |
| 锁仍只有一份 | 根 `uv.lock` | `[M1]` |
| 版本冲突会在解析时暴露 | 同库两个成员要不同主版本 → 失败 | `[M1]` |

### 2.8 [可选] 构建

```shell
uv build                       # 全部
uv build --package shared      # 指定成员
uv build --all-packages
```

实测：

```text
31B_BUILD_SHARED rc=0  Successfully built dist\shared-0.1.0.tar.gz
                       Successfully built dist\shared-0.1.0-py3-none-any.whl
31B_DIST ['.gitignore', 'shared-0.1.0-py3-none-any.whl', 'shared-0.1.0.tar.gz']
```

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 产物落在**根** `dist/` | 统一收集 | `[M9]` |
| 只有可安装的成员能被构建 | 虚拟成员跳过 | `[M9]` |
| 文件名按 PEP 427 | 见第 29 章 | 第 29 章 |

### 2.9 [可选] 查看依赖关系

```shell
uv tree --package web-service
uv tree
```

实测输出：

```text
web-service v0.1.0
└── agents v0.1.0
    └── shared v0.1.0
shared v0.1.0
mono-root v0.1.0
agents v0.1.0 (*)
(*) Package tree already displayed
```

| 标记 | 含义 | 依据 |
| --- | --- | --- |
| `(workspace)` | 该依赖来自工作区成员（老版本显示） | `[M1]` |
| `(*)` | 该子树已显示过，去重 | `[M1]` |
| `--no-dedupe` | 完整展开，不折叠 `(*)` | `[M1]` |
| `--depth N` | 限制层数 | `[M1]` |

> 注意：`uv tree` 不加 `--package` 时会列出**每个** workspace 成员作为根，所以会看到 `shared`、`mono-root` 也各占一棵树。想看单条链路就用 `--package`。`[M1]`

## 3. 包间依赖的三种模式

### 3.1 源码链接（workspace 模式）

```toml
[tool.uv.sources]
shared = { workspace = true }
```

| 特点 | 说明 | 依据 |
| --- | --- | --- |
| 本地直接引用源码 | 改完即生效 | `[M2]` |
| 无需 `pip install -e` | uv 自动以可编辑安装 | `[M2]` |
| 适合日常开发 | 联调最快 | `[M2]` |
| 要求 | 成员必须是 workspace member | `[M2]` |

### 3.2 路径引用

```toml
[tool.uv.sources]
shared = { path = "../shared" }
```

| 特点 | 说明 | 依据 |
| --- | --- | --- |
| 引用 workspace **之外**的本地包 | 跨仓库联调 | `[M2]` |
| 路径可相对可绝对 | 相对路径便于提交 | `[M2]` |
| 支持 glob（多包） | `path = "../libs/*"` | `[M2]` |
| 发布前必须换成正常版本依赖 | 否则用户装不了 | `[M2]` |

> 注意：`path` 依赖会写进构建出的 `METADATA` 吗？——**不会**。uv 在构建时把 `path` / `workspace` 依赖解析成具体的版本约束（若成员有版本号）。如果成员没有 `version`，构建会失败。`[M2]`

### 3.3 Git 引用

```toml
[tool.uv.sources]
shared = { git = "https://github.com/org/shared.git", rev = "v0.1.0" }
```

| 写法 | 含义 | 依据 |
| --- | --- | --- |
| `rev = "v0.1.0"` | 指定 tag/commit | `[M2]` |
| `branch = "main"` | 指定分支 | `[M2]` |
| `tag = "v0.1.0"` | 等价写法 | `[M2]` |
| `subdirectory = "packages/shared"` | 包在子目录 | `[M2]` |

| 特点 | 说明 | 依据 |
| --- | --- | --- |
| 引用未发布到 PyPI 的包 | 私有库常用 | `[M2]` |
| 可锁定到 commit | `uv.lock` 记录 commit hash | `[M2]` |
| 需要网络与凭据 | 私有仓库要 token | `[M2]` |

### 3.4 第四种：URL 直链（补充）

```toml
[tool.uv.sources]
shared = { url = "https://example.com/shared-0.1.0-py3-none-any.whl" }
```

| 特点 | 说明 | 依据 |
| --- | --- | --- |
| 直接指向 wheel | 无索引也能装 | `[M2]` |
| 无版本约束能力 | 需手写完整 URL | `[M2]` |
| 适合内部临时分发 | 不适合长期 | `[M2]` |

### 3.5 四种模式对比

| 模式 | 开发体验 | 发布友好 | 可复现 | 依据 |
| --- | --- | --- | --- | --- |
| `workspace = true` | ★★★★★ 源码即时生效 | 需成员有 `version` | ★★★★ | `[M2]` |
| `path = "..."` | ★★★★ 本地即时 | 需换成版本依赖 | ★★★ | `[M2]` |
| `git + rev` | ★★ 需重新同步 | ★★★★ | ★★★★★（commit 锁定） | `[M2]` |
| `url = "..."` | ★ | ★★ | ★★★ | `[M2]` |

| 场景 | 推荐 | 依据 |
| --- | --- | --- |
| 同仓多包日常开发 | `workspace` | `[M2]` |
| 跨仓联调 | `path` | `[M2]` |
| 引用未发布的上游 | `git + tag` | `[M2]` |
| 临时验证产物 | `url` | `[M2]` |

## 4. 依赖方向与环形依赖

### 4.1 单向无环

```text
web-service  →  agents  →  shared
   (app)        (业务)     (基础)
```

| 规则 | 理由 | 依据 |
| --- | --- | --- |
| 上层依赖下层 | 基础库不能反向依赖业务 | `[M5]` |
| 不允许环 | Python 导入期会半初始化，行为不可预测 | `[M5]` |
| 出现环通常该抽公共包 | 把共用部分下沉 | `[M1]` |

### 4.2 实测：uv 不检测环

构造 `alpha ↔ beta` 的 workspace：

```toml
# packages/alpha/pyproject.toml
[project]
name = "alpha"
version = "0.1.0"
dependencies = ["beta"]

[tool.uv.sources]
beta = { workspace = true }
```

```toml
# packages/beta/pyproject.toml
[project]
name = "beta"
version = "0.1.0"
dependencies = ["alpha"]

[tool.uv.sources]
alpha = { workspace = true }
```

执行 `uv lock --offline`：

```text
31_CYCLE rc=0  Resolved 3 packages in 1ms
```

| 结论 | 说明 | 依据 |
| --- | --- | --- |
| **uv 不报环错误** | 锁文件正常生成 | 实测 |
| 环只在**运行时**炸 | `import alpha` 时遇到半初始化模块 | `[M5]` |
| 所以 CI 必须自己做环检测 | 工具链不兜底 | `[M1]` |

> 注意：这是本课最重要的实测结论之一。**依赖解析器只管「有没有解」，不管「架构是否合理」**。环依赖在 lock 阶段完全静默，等到有人 `import` 才炸，而且报错信息通常指向一个不相关的 `AttributeError`（半初始化模块）。`[M5]`

### 4.3 CI 环检测（可落地）

```python
"""检查 workspace 依赖是否有环。只读 pyproject.toml，不改文件。"""

from __future__ import annotations

import pathlib
import sys
import tomllib


def load_graph(root: pathlib.Path) -> dict[str, set[str]]:
    graph: dict[str, set[str]] = {}
    for pyproject in root.glob("**/pyproject.toml"):
        if ".venv" in pyproject.parts:
            continue
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        name = data.get("project", {}).get("name")
        if not name:
            continue
        sources = data.get("tool", {}).get("uv", {}).get("sources", {})
        local = {dep for dep, spec in sources.items() if isinstance(spec, dict) and ("workspace" in spec or "path" in spec)}
        graph[name] = local
    return graph


def find_cycles(graph: dict[str, set[str]]) -> list[list[str]]:
    cycles: list[list[str]] = []
    state: dict[str, int] = {}

    def walk(node: str, stack: list[str]) -> None:
        if state.get(node) == 1:
            cycles.append(stack[stack.index(node):] + [node])
            return
        if state.get(node) == 2:
            return
        state[node] = 1
        for dep in sorted(graph.get(node, ())):
            walk(dep, stack + [dep])
        state[node] = 2

    for node in sorted(graph):
        walk(node, [node])
    return cycles


graph = load_graph(pathlib.Path.cwd())
cycles = find_cycles(graph)
print("GRAPH", {key: sorted(value) for key, value in graph.items()})
print("CYCLES", cycles)
sys.exit(1 if cycles else 0)
```

| 输出 | 说明 |
| --- | --- |
| `CYCLES []` | 无环，退出码 0 |
| `CYCLES [['alpha','beta','alpha']]` | 有环，退出码 1，CI 失败 |

| 检查项 | 为什么必要 | 依据 |
| --- | --- | --- |
| 环检测 | uv 不查（实测） | `[M1]` |
| 方向检测 | 基础包不应依赖 app | `[M5]` |
| 公共包下沉判断 | 环通常是「该抽第三方包」的信号 | `[M1]` |

## 5. 版本策略

### 5.1 统一版本 vs 独立版本

| 策略 | 做法 | 优点 | 缺点 | 依据 |
| --- | --- | --- | --- | --- |
| 统一版本（fixed/lockstep） | 所有包同升同降，如全 `1.4.0` | 依赖关系简单、易沟通 | 未改动的包也发版、噪声大 | `[M1]` |
| 独立版本（independent） | 各包按需发版 | 版本语义精确 | 需要用 `~=` 管组合、工具更复杂 | `[M1]` |

| 判据 | 选统一 | 选独立 |
| --- | --- | --- |
| 包之间高频同步改动 | ✅ | —— |
| 包对外独立发布 | —— | ✅ |
| 团队小、发布少 | ✅ | —— |
| 有外部用户按包升级 | —— | ✅ |

### 5.2 独立版本的组合约束

```toml
# apps/web-service 依赖 agents 时，写清可用范围
dependencies = ["agents>=0.3,<0.5"]
```

| 写法 | 含义 | 依据 |
| --- | --- | --- |
| `agents>=0.3` | 0.3 以上都行（含 0.9、1.0） | `[M7]` |
| `agents>=0.3,<0.5` | 明确上界 | `[M7]` |
| `agents~=0.3.1` | `>=0.3.1,<0.4.0` | `[M7]` |

> 注意：`>=0.3` 在 0.x 阶段非常危险——`0.4` 可能是不兼容改动。0.x 阶段建议写 `~=` 或显式上界。`[M7]`

### 5.3 内部依赖的版本要求

| 事实 | 说明 | 依据 |
| --- | --- | --- |
| 成员必须有 `version` 才能被构建成带约束的依赖 | 否则 `uv build` 失败 | `[M9]` |
| `workspace = true` 在构建时会被替换成版本约束 | 锁文件记的是本地来源 | `[M2]` |
| 动态版本（`version` 来自 `__version__`）需后端支持 | 否则元数据缺失 | `[M6]` |

## 6. 综合示例：搭建并验证三包 workspace

### 6.1 目录与配置

```text
mono/
├── pyproject.toml                    # 虚拟根 + members
├── packages/shared/pyproject.toml
├── packages/shared/src/shared/__init__.py
├── packages/agents/pyproject.toml
├── packages/agents/src/agents/__init__.py
└── apps/web-service/
    ├── pyproject.toml
    └── main.py
```

```toml
# 根 pyproject.toml
[project]
name = "mono-root"
version = "0.1.0"
requires-python = ">=3.12"

[tool.uv.workspace]
members = ["packages/*", "apps/*"]

[tool.uv]
package = false
```

```toml
# packages/shared/pyproject.toml
[project]
name = "shared"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = []

[build-system]
requires = ["uv_build>=0.12.2,<0.13.0"]
build-backend = "uv_build"
```

```toml
# packages/agents/pyproject.toml
[project]
name = "agents"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["shared"]

[tool.uv.sources]
shared = { workspace = true }

[build-system]
requires = ["uv_build>=0.12.2,<0.13.0"]
build-backend = "uv_build"
```

```toml
# apps/web-service/pyproject.toml
[project]
name = "web-service"
version = "0.1.0"
requires-python = ">=3.12"
dependencies = ["agents"]

[tool.uv.sources]
agents = { workspace = true }
```

```python
# packages/shared/src/shared/__init__.py
VALUE = "shared-ok"


def greet(name: str) -> str:
    return f"hello {name} from shared"
```

```python
# packages/agents/src/agents/__init__.py
from shared import VALUE


def describe() -> str:
    return "agents<-" + VALUE
```

```python
# apps/web-service/main.py
from agents import describe

print("MAIN", describe())
```

### 6.2 命令序列

```shell
uv sync --all-packages
uv tree --package web-service
uv run --package web-service python apps/web-service/main.py
uv build --package shared
```

本机实测结果：

```text
31B_SYNC_ALL rc=0       Resolved 4 packages in 2ms
31B_TREE                web-service v0.1.0 → agents v0.1.0 → shared v0.1.0
31B_RUN_PACKAGE         MAIN agents<-shared-ok
31B_BUILD_SHARED rc=0   shared-0.1.0.tar.gz / shared-0.1.0-py3-none-any.whl
31B_IMPORT_CHECK rc=0   shared-ok
```

**逐项说明**：

| 命令 | 验证了什么 | 依据 |
| --- | --- | --- |
| `sync --all-packages` | 全仓依赖一次装齐 | `[M1]` |
| `tree --package` | 依赖方向正确（单向） | `[M1]` |
| `run --package` | 源码链接生效，三层 import 通 | `[M1]` |
| `build --package` | 单个成员可独立发布 | `[M9]` |
| `pip list` 显示 editable | 装的是链接 | 第 29 章 |

### 6.3 改源码即时生效的验证

```shell
# 改 packages/shared/src/shared/__init__.py: VALUE = "shared-ok" → "shared-v2"
uv run --package web-service python apps/web-service/main.py
```

期望输出 `MAIN agents<-shared-v2`，**无需重新安装**。

| 现象 | 说明 | 依据 |
| --- | --- | --- |
| 立即生效 | 因为是路径导入 | 第 29 章 |
| 不改锁文件 | 版本号没变 | `[M1]` |
| 若改版本号则 `uv lock --check` 会报漂移 | 第 30 章 | `[G2]` |

## 7. 注意事项与新手错误对照表

| 错误写法 / 操作 | 现象 | 正确写法 | 依据 |
| --- | --- | --- | --- |
| 成员目录不在 `members` 里 | `uv sync` 完全忽略它 | 检查 glob 是否匹配 | `[M1]` |
| 把无关项目塞进一个仓 | 权限与发布节奏互相拖累 | 按「跨包改动频率」判断 | `[M1]` |
| 每个包各一套锁文件 | 版本地狱 | 全仓一份 `uv.lock` | `[M1]` |
| 成员目录里放自己的 `uv.lock` | 与根锁冲突 | 删掉成员锁 | `[M1]` |
| 成员没有 `build-system` | 无法被安装为依赖 | 加 `[build-system]` | `[M9]` |
| 成员没有 `version` | 构建时无版本约束 | 写 `version` | `[M6]` |
| `dependencies = ["shared"]` 但没写 `sources` | 去 PyPI 找同名包 | 加 `workspace = true` | `[M2]` |
| 想在 PyPI 找同名包但写了 `workspace` | 用了本地版 | `workspace = false` | `[M2]` |
| `path` 依赖写绝对路径 | 换机器失效 | 用相对路径 | `[M2]` |
| 发布时留下 `path` 依赖 | 用户装不上 | 换成版本约束 | `[M2]` |
| `git` 依赖不写 `rev`/`tag` | 每次解析结果可能变 | 锁定 commit/tag | `[M2]` |
| 私有 Git 仓库无凭据 | 解析失败 | 配 SSH key / token | `[M2]` |
| 不加 `--all-packages` 就 `sync` | 成员依赖没装 | 显式指定 | `[M1]` |
| `uv run` 不写 `--package` | 用根环境，成员依赖不可见 | 写 `--package` | `[M1]` |
| 依赖成环 | `uv lock` 仍 `rc=0`（实测），运行时炸 | CI 做环检测 | 实测 + `[M5]` |
| 基础包反向依赖 app | 架构倒挂 | 单向依赖 | `[M5]` |
| 循环依赖时 `import` 报 `AttributeError` | 半初始化模块 | 抽公共包 | `[M5]` |
| 用 `if TYPE_CHECKING` 掩盖环 | 运行时仍失败 | 真解环 | 第 20 章 |
| 统一版本下频繁全量发版 | 用户收到无意义更新 | 评估独立版本 | `[M1]` |
| 独立版本写 `>=0.3` 无上界 | 0.4 破坏性升级 | `~=` 或上界 | `[M7]` |
| 成员间用 `==` 精确锁死 | 无法独立升级 | 用兼容范围 | `[M7]` |
| 把 `dist/` 提交 | 仓库膨胀 | `.gitignore` | 第 29 章 |
| 各包各自 `dist/` 分散 | 找不到产物 | 统一根 `dist/` | `[M9]` |
| `uv build` 期望构建虚拟根 | 报「不是包」 | 用 `--package` | `[M9]` |
| CI 全量构建所有包 | 慢 | 变更检测 + 只建受影响 | `[M1]` |
| CI 全量测试 | 慢 | 按依赖图选测试范围 | `[M1]` |
| 用 `sys.path.append` 跨包导入 | 打包后失效 | 用可安装包名 | 第 21 章 |
| 命名空间包（PEP 420）与普通包混用 | 导入行为不同 | 明确取舍 | `[M4]` |
| 多个包共用同一顶层名 | 文件互相覆盖 | 各自独立顶层名 | `[M4]` |
| 成员包名与 PyPI 现有包同名 | 依赖混淆 | 加 `explicit` 索引 | 第 30 章 |
| 私有源与 workspace 同名 | 不确定用哪个 | 显式 `sources` | `[M2]` |
| 在成员目录执行 `uv sync` | uv 找到根，装全仓 | 明确当前目录语义 | `[M1]` |
| 用 `--no-workspace` 又期望共享锁 | 独立解析 | 想共享就别加 | `[M3]` |
| 每次改公共包都 `pip install -e` | 多余 | workspace 自动链接 | `[M2]` |
| 在根装所有三方依赖 | 成员边界模糊 | 依赖写在成员里 | `[M1]` |
| 成员版本号靠手改不同步 | 依赖解析失败 | 单一来源 | `[M6]` |
| 环依赖靠「反正能跑」 | 换导入顺序就炸 | 立刻拆环 | `[M5]` |
| 用 monorepo 却各包独立 CI | 失去统一收益 | 统一 CI + 增量 | `[M1]` |
| 不写 `requires-python` | 成员各支持不同版本 | 统一声明 | `[M6]` |
| 用 `hatchling` 又要求完全离线 | 构建失败（实测） | 改 `uv_build` 或预热缓存 | 实测 |
| 断言 `uv tree` 一定有 `(workspace)` | 新版显示 `(*)` | 按版本看输出 | 实测 |

## 8. 最佳实践与编码建议

| 建议 | 说明 | 依据 |
| --- | --- | --- |
| 先画依赖图再定目录 | 目录结构应反映依赖方向 | `[M1]` |
| 一个 workspace 一把锁 | 消除版本地狱 | `[M1]` |
| 公共能力沉到底层包 | 上层只组合 | `[M1]` |
| CI 做环检测 + 方向检测 | 工具不兜底（实测） | `[M5]` |
| CI 做变更检测 | 只跑受影响的包 | `[M1]` |
| 成员依赖写 `workspace = true` | 明确意图 | `[M2]` |
| 内部依赖 0.x 用 `~=` | 防不兼容升级 | `[M7]` |
| 根用虚拟项目 | 不产出无意义的包 | `[M1]` |
| 统一用 `--package` 运行 | 环境边界清晰 | `[M1]` |
| 构建产物统一到根 `dist/` | 便于发布流水线 | `[M9]` |
| 离线/受限环境优先 `uv_build` | 零额外依赖 | 实测 |
| 把取舍写进 README | 后人知道为什么 | `[M8]` |

**风格示范**：

```python
"""graph 模块：workspace 依赖图与环检测。

为什么自建：uv 的解析器不检查 workspace 环（实测 rc=0），架构约束必须由 CI 兜住。
"""

from __future__ import annotations

import pathlib
import tomllib
from collections.abc import Iterator


def iter_members(root: pathlib.Path) -> Iterator[tuple[str, set[str]]]:
    """产出 (包名, 本地依赖集合)。"""
    for pyproject in root.glob("*/**/pyproject.toml"):
        if ".venv" in pyproject.parts:
            continue
        data = tomllib.loads(pyproject.read_text(encoding="utf-8"))
        name = data.get("project", {}).get("name")
        if not name:
            continue
        sources = data.get("tool", {}).get("uv", {}).get("sources", {})
        yield name, {dep for dep, spec in sources.items() if isinstance(spec, dict) and ("workspace" in spec or "path" in spec)}


def has_cycle(graph: dict[str, set[str]]) -> bool:
    """深度优先判断是否存在环。"""
    visiting: set[str] = set()
    done: set[str] = set()

    def walk(node: str) -> bool:
        if node in visiting:
            return True
        if node in done:
            return False
        visiting.add(node)
        for dep in graph.get(node, ()):
            if walk(dep):
                return True
        visiting.discard(node)
        done.add(node)
        return False

    return any(walk(node) for node in graph)
```

**边界**：

- workspace 只解决「代码共享 + 依赖解析」，不解决构建缓存与任务编排（需要 Bazel/Nx/turbo 之类）。
- 跨包的类型检查与测试范围仍要自己按依赖图裁剪。
- 单仓权限控制要靠代码托管平台的目录级审阅规则。

## 9. 依据索引

| 编号 | 类型 | 链接 | 支撑内容 |
| --- | --- | --- | --- |
| `[M1]` | 官方文档（Astral） | https://docs.astral.sh/uv/concepts/projects/workspaces/ | `[tool.uv.workspace]`、`members` glob、单锁、`--all-packages`、`--package` |
| `[M2]` | 官方文档（Astral） | https://docs.astral.sh/uv/concepts/projects/dependencies/ | `[tool.uv.sources]` 的 workspace/path/git/url 写法与优先级 |
| `[M3]` | 官方文档（Astral） | https://docs.astral.sh/uv/concepts/projects/layout/ | `uv init --lib/--app/--package/--no-workspace` 的目录约定 |
| `[M4]` | PEP 官方 | https://peps.python.org/pep-0420/ | 隐式命名空间包 |
| `[M5]` | python.org | https://docs.python.org/3.12/reference/import.html | 导入期半初始化模块、循环导入行为 |
| `[M6]` | PEP 官方 | https://peps.python.org/pep-0621/ | `[project]` 的 `name`/`version`/`dependencies` |
| `[M7]` | PEP 官方 | https://peps.python.org/pep-0440/ | `~=`、上界、0.x 语义 |
| `[M8]` | PEP 官方 | https://peps.python.org/pep-0008/ | 包/模块命名、注释写「为什么」 |
| `[M9]` | 官方文档（Astral） | https://docs.astral.sh/uv/concepts/projects/build/ | `uv build --package`、构建后端要求、产物位置 |

> **核对状态**：`[M8]` 与本章 `README.md` 已核对来源一致；`[M1]`–`[M9]` 按官方文档结构整理，**本次未逐页直连复核**。文中「实测」为本机 uv 0.12.2 / Python 3.12.8 / Windows 的真实输出（全部 `--offline`）；`uv tree` 的 `(workspace)` 标记在本机版本显示为 `(*)`，已在 2.9 说明差异。

## 10. 毕业自查清单

**能说清（概念层）**：

- [ ] monorepo 与 multirepo 的六维差异
- [ ] monorepo 的两项主要收益与两项主要代价
- [ ] workspace 与「一把锁」的关系
- [ ] 虚拟根（`package = false`）的作用
- [ ] `[tool.uv.sources]` 四种模式的取舍
- [ ] 为什么依赖方向必须单向无环
- [ ] 为什么 uv 不会帮你报环（实测）
- [ ] 统一版本与独立版本的适用场景
- [ ] `(*)` 与 `(workspace)` 的含义差异

**能写出（代码层）**：

- [ ] 根 `pyproject.toml` + `members` glob
- [ ] 三个成员的依赖声明与 `workspace = true`
- [ ] `uv sync --all-packages` → `uv run --package` → `uv build --package` 全链路
- [ ] 环检测脚本（4.3 节）
- [ ] 依赖图可视化（`uv tree --no-dedupe`）
- [ ] Makefile 统一入口

**能判断（避坑层）**：

- [ ] 看到成员缺 `build-system` 能指出无法安装
- [ ] 看到 `dependencies` 无 `sources` 能指出走 PyPI
- [ ] 看到 `path` 依赖写进发布配置能指出用户装不上
- [ ] 看到环依赖且 `uv lock` 成功能指出工具不兜底
- [ ] 看到 `uv run` 不写 `--package` 能指出环境边界
- [ ] 看到成员各带 `uv.lock` 能指出冲突

**能跑通（验收层）**：

- [ ] 运行 `examples/monorepo_demo.py` 并解释依赖方向输出
- [ ] 把第 6 节工程手工搭起来并跑通 `MAIN agents<-shared-ok`
- [ ] 改 `shared.VALUE` 后不重装即可见变化
- [ ] 用 4.3 节脚本检出自己构造的环依赖

## 11. 下一章衔接

第 32 章 `断点调试`：全教程最后一章——工程化手段都没防住问题时，怎么用 `sys.settrace`/`pdb`/`debugpy` 高效定位，而不是靠 `print` 猜。

本章留下的伏笔：

1. 多包 workspace 的调试要用 `--package` 选环境，第 32 章的 `debugpy` + `Makefile` 会用到。
2. 环依赖运行时炸出的 `AttributeError`，正是第 32 章 `pdb` 的典型排查场景。
3. `uv run --package xxx python -m debugpy ...` 是本章与下一章的接缝。