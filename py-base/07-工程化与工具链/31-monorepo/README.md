# 31 monorepo

> 承接第 30 章：工具链能锁一个项目了，本章处理「一个仓库放多个包」——布局、依赖方向、版本策略与 CI 影响。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 21、29–30 章（包、构建、工具链） |
| 本章目标 | monorepo 取舍、workspace、包边界与依赖方向、统一/独立版本策略 |
| 毕业标准 | 能说出 monorepo 的主要收益与代价；能解释为什么依赖方向必须单向无环 |
| 编码要求 | 能运行 `examples/monorepo_demo.py` 并解释依赖方向输出 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节；monorepo 没有 `python.org` 统一规范，依据以 **PyPA 官方指南 + GitHub 官方项目文档**为主，标注「未直连核对」。

## 1. 概念

- **monorepo**：一个版本库里放多个逻辑包（如 `agent-core` / `agent-tools` / `agent-cli`），共享一套 CI、工具链与依赖约束。`[R3]`
- 收益：跨包改动一次提交、统一版本与工具链、依赖可见；代价：仓库体积、CI 时间、权限边界变粗、发布耦合。`[R3]`
- **workspace** 是工具链提供的「单仓多包」能力：一个锁文件覆盖所有成员包，成员间用本地路径依赖相互引用。`[R3]`
- 常见布局 `packages/<name>/pyproject.toml`，每个包有自己的元数据（第 29 章）；命名空间包（PEP 420）可让多个包共享顶层命名空间。`[R2]`
- **依赖方向必须单向无环**：底层包不依赖上层应用；出现环通常意味着该抽公共包。`[R1]`
- 版本策略二选一：统一版本（同升同降、简单）或独立版本（各包按需发布、灵活但工具复杂）。`[R3]`

## 2. 注意事项

1. **不要为了「看起来统一」把无关项目塞进一个仓**，权限与发布节奏会互相拖累。
2. **包间不要循环依赖**，CI 加环检测。`[R1]`
3. **不要让每个包各用一套工具链/锁文件**（第 30 章）。
4. **CI 要按变更范围选择构建哪些包**，否则仓库一大就全量跑。
5. **`packages/*` 路径要进 `.gitignore` 排除项**：忽略各包的 `dist/` / `.venv/`。
6. **跨包导入要用可安装的包名**，不要靠相对路径拼 `sys.path`（第 21 章）。

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 发布耦合 | 统一版本会让未改动的包也发新版 | `[R3]` |
| 权限粒度 | 单仓难以按包控制写权限 | `[R3]` |
| 命名空间包 | 无 `__init__.py` 的包行为与普通包不同（第 21 章） | `[R2]` |
| 本地路径依赖 | 开发期方便，发布时要转成正常版本依赖 | `[R3]` |

## 4. 最佳实践

1. **先按依赖方向画包图，再决定目录结构**。`[R1]`
2. **一个 workspace 一把锁**，所有包用同一工具链（第 30 章）。
3. **公共能力沉到底层包**，上层只组合。
4. **CI 做变更检测 + 环检测 + 逐包测试**。
5. **取舍要写明**：为什么用 monorepo、什么时候该拆仓。

## 5. 最佳编码建议

- **包名短小全小写、与导入名一致**（第 21 章）。`[R4]`
- **注释解释「为什么拆这个包」**。`[R4]`
- **显式优于隐式、不做预留包**（第 01 章）。
- **配置与密钥不跨包共享硬编码**（第 01 章）。

## 6. 编码示例

`examples/monorepo_demo.py`（`PurePath` 只读，不访问磁盘）：

```python
"""第 31 章示例：monorepo 包布局与依赖方向（只读示意）。"""

import pathlib

packages = ["agent-tools", "agent-core", "agent-cli"]
for name in packages:
    marker = pathlib.PurePath("packages", name, "pyproject.toml")
    print("包路径:", marker.as_posix())

dependencies = {
    "agent-cli": ["agent-core"],
    "agent-core": ["agent-tools"],
    "agent-tools": [],
}
for name, deps in dependencies.items():
    print(name, "->", deps)
```

运行：

```powershell
cd 'E:\ai-agent-study\py-base\07-工程化与工具链\31-monorepo'
python examples/monorepo_demo.py
```

关键输出：三条 `packages/<name>/pyproject.toml` 路径，以及 `agent-cli -> agent-core -> agent-tools` 的单向依赖，底层包无依赖。`[R1]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org · 未直连核对 | https://docs.python.org/3.12/reference/import.html | 包导入与命名空间包语义、依赖方向不能成环 |
| `[R2]` | PEP 官方 · 未直连核对 | https://peps.python.org/pep-0420/ | 隐式命名空间包 |
| `[R3]` | GitHub 官方 / PyPA · 未直连核对 | https://github.com/astral-sh/uv | workspace 单仓多包、统一锁文件、路径依赖（官方文档） |
| `[R4]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | 包/模块命名、注释写「为什么」 |

## 8. 毕业自查清单

- [ ] 能说出 monorepo 的两项收益与两项代价
- [ ] 能解释 workspace 与一把锁的关系
- [ ] 能说出依赖方向为什么必须单向无环
- [ ] 能说出统一版本与独立版本的取舍
- [ ] 能运行 `examples/monorepo_demo.py` 并解释依赖图

## 9. 下一章衔接

第 32 章 `断点调试`：全教程最后一章——当上面所有工程化手段都没能防住问题时，怎么高效地定位它。
