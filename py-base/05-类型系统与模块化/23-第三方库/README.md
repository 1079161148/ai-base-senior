# 23 第三方库

> 承接第 22 章：标准库不够用时才引入第三方库。本章讲选型、安装、版本约束与供应链风险——第 02 章的 `venv + pip + requirements.txt` 在这里正式派上用场。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 02、21–22 章（环境、模块化、标准库） |
| 本章目标 | PyPI / pip、版本约束、`requirements.txt`、选型标准、许可证与安全 |
| 毕业标准 | 能说出 `pip freeze` 不是 lockfile；能列出选型时要看的 4 项 |
| 编码要求 | 能运行 `examples/deps_demo.py` 并解释「未安装」分支 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节；「未直连核对」的链接按官方文档通行表述整理。**本课不联网安装任何第三方包**。

## 1. 概念

- 第三方包主要来自 PyPI，用 `python -m pip install <pkg>` 装进**当前虚拟环境**；用 `pip` 而非裸 `pip` 是为了避免解释器错配。`[R1]`
- 版本约束写法：`==1.4`、`>=1,<2`、`~=1.4.2`；应用项目为可复现宜写精确版本，库作者宜写范围。`[R1]`
- `pip install -r requirements.txt` 重建依赖；`pip freeze > requirements.txt` 导出已安装项。`[R1]`
- **`pip freeze` 不计算 lockfile、不做依赖求解**，默认还排除引导工具；完整锁定与哈希校验属于第 30 章。`[R2]`
- 系统 Python 可能被 PEP 668 标记为 externally-managed 而拒绝全局安装，正解是 venv（第 02 章）。`[R3]`
- `importlib.metadata` 可在运行时只读查询已安装包的版本与元数据（标准库，无需额外依赖）。`[R4]`

## 2. 注意事项

1. **不要全局装包、不要 `sudo pip`**。`[R1]` `[R3]`
2. **不要把 `pip freeze` 输出直接当锁定文件**。`[R2]`
3. **不要装功能重叠的两套库**（第 01 章依赖管理）。
4. **密钥、令牌不写进依赖文件或日志**（第 01 章）。
5. **`--user` 在 venv 内无效**。`[R1]`
6. **别直接执行网上抄来的安装脚本**，先审阅（第 02 章 pyenv-win 同理）。

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 供应链 | 依赖即代码，需关注维护状态、许可证、漏洞与来源可信度 | `[R1]` |
| 版本兼容 | 库可能声明 Python 版本上限，升级解释器前要核对 | `[R1]` |
| 直接/传递依赖 | `freeze` 混合两者，人工整理后才入库 | `[R2]` |
| 平台差异 | 含 C 扩展的包可能需要编译工具链 | `[R1]` |
| 锁定 | `pylock.toml` / 哈希校验 / 项目管理工具见第 30 章 | `[R2]` |

## 4. 最佳实践

1. **选型看四项**：维护活跃度、类型完备度、与现有技术栈契合度、退出成本（第 01 章）。
2. **关键依赖登记备选方案**，避免被单一库锁死。
3. **每个项目独立 venv + 锁定依赖**，保证可复现（第 02 章）。
4. **定期检查 EOL 与安全漏洞**，把检查放进 CI（第 30 章）。
5. **能用标准库就别引入依赖**（第 22 章）。

## 5. 最佳编码建议

- **导入按标准库 / 第三方 / 本地分组**（第 21 章）。`[R5]`
- **把第三方类型封装在自己的模块边界后**，方便替换。
- **注释解释「为什么选这个库」**。`[R5]`
- **不硬编码版本与凭据**，配置外置（第 01 章）。

## 6. 编码示例

`examples/deps_demo.py`（只读查询，不安装任何包）：

```python
"""第 23 章示例：只读查看已安装的包元数据。"""

import importlib.metadata

for name in ["pip", "setuptools", "definitely-not-installed"]:
    try:
        print(name, "版本:", importlib.metadata.version(name))
    except importlib.metadata.PackageNotFoundError:
        print(name, "未安装")
```

运行：

```powershell
cd 'E:\ai-agent-study\py-base\05-类型系统与模块化\23-第三方库'
python examples/deps_demo.py
```

关键输出：已装包打印版本，最后一个走 `PackageNotFoundError` 分支，说明查询是只读且可容错的。`[R4]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | PyPA 官方 · **已核对** | https://packaging.python.org/en/latest/tutorials/installing-packages/ | pip 安装、版本约束、`requirements.txt`、不要 sudo、`--user` 在 venv 内无效 |
| `[R2]` | PyPA 官方 · **已核对** | https://pip.pypa.io/en/stable/cli/pip_freeze/ | `freeze` 输出格式、不是 lockfile、排除引导工具 |
| `[R3]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0668/ | externally-managed 环境、引导用户使用 venv |
| `[R4]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/importlib.metadata.html | `version()` 与 `PackageNotFoundError` |
| `[R5]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | import 分组、命名与注释约定 |

## 8. 毕业自查清单

- [ ] 能说出 `pip freeze` 与 lockfile 的区别
- [ ] 能写出三种版本约束并说明各自适用场景
- [ ] 能列出第三方库选型的四项标准
- [ ] 能说出供应链风险至少两条与对应做法
- [ ] 能运行 `examples/deps_demo.py` 并解释「未安装」一行

## 9. 下一章衔接

第 28 章 `多线程与多进程`：工程化基础告一段落，按认知顺序先建立并发直觉（GIL、I/O 密集 vs CPU 密集），再进入 24 事件循环 → 25 Future → 26 协程 → 27 异步编程。
