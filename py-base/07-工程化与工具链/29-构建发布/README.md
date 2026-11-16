# 29 构建发布

> 承接第 27 章：代码与并发都写完了，本章讲怎么把它变成可分发的包——`pyproject.toml` 是现代 Python 打包的统一入口。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 21–23 章（模块化、依赖） |
| 本章目标 | `pyproject.toml`、`[project]` / `[build-system]`、sdist / wheel、`build` / `twine`、版本号 |
| 毕业标准 | 能说出 `pyproject.toml` 三段关键配置；能区分 sdist 与 wheel |
| 编码要求 | 能运行 `examples/packaging_demo.py` 并解释三段输出 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节；「未直连核对」的链接按官方文档通行表述整理。**本课不实际构建或上传任何包。**

## 1. 概念

- `pyproject.toml` 是打包配置的统一入口；`[build-system]` 声明构建后端与依赖（PEP 518），`[project]` 声明名称、版本、依赖、Python 版本要求等元数据（PEP 621）。`[R2]` `[R3]`
- 构建产物两类：**sdist**（源码归档）与 **wheel**（构建好的分发包）；wheel 安装更快、不需要在目标机器执行构建后端。`[R1]`
- 推荐流程：`python -m build` 生成两种产物 → `python -m twine upload dist/*` 上传；上传前先传 TestPyPI 验证。`[R1]`
- 版本号遵循 PEP 440；`requires-python` 声明兼容的 Python 版本范围。`[R1]` `[R4]`
- `python -m build` 会在隔离环境中安装构建依赖，避免本机环境污染（第 02 章 venv）。`[R1]`
- 包内代码要能被导入：`__init__.py` 与包结构见第 21 章；`__main__.py` 提供 `python -m pkg` 入口。`[R1]`

## 2. 注意事项

1. **不要把凭据写进 `pyproject.toml`**，上传令牌走环境变量 / CI secret。`[R1]`
2. **上传不可逆**：同一个版本号不能重复上传，先在 TestPyPI 演练。`[R1]`
3. **不要把 `.venv/`、`dist/`、密钥文件打进 sdist**，用 MANIFEST / `.gitignore` 控制。`[R1]`
4. **依赖写运行时真正需要的**，开发工具放可选依赖组（第 30 章）。
5. **发布前在本地干净 venv 里装一遍 wheel 验证**（第 02 章）。

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 构建后端 | setuptools / hatchling / flit 等，语法一致但行为差异由后端决定 | `[R2]` |
| 平台相关包 | 含 C 扩展需按平台产出多个 wheel | `[R1]` |
| 版本兼容 | `requires-python` 与实际 CI 测试矩阵要一致 | `[R3]` |
| 私有制品库 | 企业内部用私有 index，不要误传公开 PyPI | `[R1]` |

## 4. 最佳实践

1. **元数据全部集中在 `pyproject.toml`**，不散落在多个配置文件。`[R3]`
2. **CI 里做「构建 → 干净环境安装 → 冒烟测试」**。
3. **版本号与 tag 对齐**，变更有 CHANGELOG。
4. **上传用受限令牌**，用完吊销。
5. **完整锁定与依赖组交给第 30 章**。

## 5. 最佳编码建议

- **包名短小全小写**，与导入名一致（第 21 章）。`[R5]`
- **注释解释「为什么声明这个 Python 版本下限」**。`[R5]`
- **不硬编码版本号到业务代码**，从包元数据读取。
- **显式优于隐式、失败要快**（第 01 章）。

## 6. 编码示例

`examples/packaging_demo.py`（用标准库 `tomllib` 只读解析示例元数据，不写磁盘）：

```python
"""第 29 章示例：只读解析 pyproject 元数据。"""

import tomllib

document = """
[project]
name = "agent-tools"
version = "0.1.0"
requires-python = ">=3.12"
"""
metadata = tomllib.loads(document)
print("项目名:", metadata["project"]["name"])
print("版本:", metadata["project"]["version"])
print("Python 要求:", metadata["project"]["requires-python"])
```

运行：

```powershell
cd 'E:\ai-agent-study\py-base\07-工程化与工具链\29-构建发布'
python examples/packaging_demo.py
```

关键输出：`项目名: agent-tools`、`版本: 0.1.0`、`Python 要求: >=3.12`。`[project]` 字段来自 PEP 621。`[R3]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | PyPA 官方 · 未直连核对 | https://packaging.python.org/en/latest/tutorials/packaging-projects/ | `pyproject.toml`、`python -m build`、sdist / wheel、`twine`、TestPyPI、令牌 |
| `[R2]` | PEP 官方 · 未直连核对 | https://peps.python.org/pep-0518/ | `[build-system]` 与构建隔离 |
| `[R3]` | PEP 官方 · 未直连核对 | https://peps.python.org/pep-0621/ | `[project]` 元数据字段、`requires-python` |
| `[R4]` | PEP 官方 · 未直连核对 | https://peps.python.org/pep-0440/ | 版本标识与比较规则 |
| `[R5]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | 包/模块命名、注释写「为什么」 |

## 8. 毕业自查清单

- [ ] 能说出 `pyproject.toml` 的 `[build-system]` 与 `[project]` 各管什么
- [ ] 能区分 sdist 与 wheel
- [ ] 能说出上传前必须做的两步验证
- [ ] 能说出版本号与 `requires-python` 的作用
- [ ] 能运行 `examples/packaging_demo.py` 并解释三段输出

## 9. 下一章衔接

第 30 章 `项目管理工具`：把「构建发布」接上依赖锁定、环境复现与任务自动化——`uv` / Poetry / PDM / Hatch 的取舍；随后 31 monorepo、32 断点调试。
