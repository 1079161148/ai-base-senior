# 22 标准库

> 承接第 21 章：模块能拆了，本章盘点随解释器分发、**无需 `pip install`** 的工具箱——这是 Agents 应用最常被低估的一层。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 02、21 章（环境、模块化） |
| 本章目标 | 标准库分类与选型、`os` / `sys` / `pathlib` / `json` / `collections` / `logging` / `datetime` |
| 毕业标准 | 能说出标准库与第三方库的边界；能按场景选出合适的内置模块 |
| 编码要求 | 能运行 `examples/stdlib_demo.py` 并解释 `计数` 一行 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节；「未直连核对」的链接按官方文档通行表述整理。

## 1. 概念

- 标准库随解释器分发；官方总览按功能分类，`os` 属操作系统服务、`sys` 属运行时服务、`urllib` 属网络协议、`pathlib` 属文件与目录访问，`venv` / `ensurepip` 属打包与分发。Windows 安装包通常包含**完整标准库**。`[R1]`
- 常用模块与定位 `[R1]`：
  - 路径与系统：`pathlib`（面向对象路径）、`os`、`sys`
  - 数据与序列化：`json`、`csv`、`datetime`、`decimal`（精确十进制）
  - 容器增强：`collections`（`Counter` / `deque` / `defaultdict`）、`itertools`、`functools`
  - 并发与 I/O：`threading`、`concurrent.futures`、`asyncio`（第 24–28 章）、`subprocess`
  - 可观测性：`logging`、`traceback`、`time`
  - 调试：`pdb`（第 32 章）
- `collections.deque` 两端 append/pop 都快，补上第 04 章「list 不适合当队列」的结论。`[R2]`
- `functools` 提供 `wraps`（第 13 章）、`lru_cache`/`cache`、`partial`。`[R3]`
- `logging` 是标准库日志方案；敏感数据不入日志（第 01 章）。`[R1]`

## 2. 注意事项

1. **先查标准库再找第三方**（第 01 章「不造轮子」）。`[R1]`
2. **标准库不等于「总是最优」**：HTTP 客户端、日期时区等场景第三方库体验更好（第 23 章）。
3. **`pathlib` 与 `os.path` 不要混着用**，一个项目里统一一套。
4. **`json` 处理的是 `str`**，写文件注意编码与换行。
5. **不要用 `print` 代替日志**，生产环境需要级别、结构化与脱敏。`[R1]`

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 版本差异 | 标准库随 Python 版本演进，用法要对齐解释器版本（第 02 章） | `[R1]` |
| 平台差异 | 部分模块仅 Unix 可用，Windows 上需条件处理 | `[R1]` |
| 精确计算 | `float` 有精度问题，金额用 `decimal`（第 03 章边界） | `[R1]` |
| 深拷贝 | `copy.deepcopy` 处理嵌套可变对象（第 04 章浅拷贝边界） | `[R1]` |
| 第三方替代 | 什么时候该换库，见第 23 章 | 课程边界 |

## 4. 最佳实践

1. **路径一律用 `pathlib`**，跨平台且可读。`[R1]`
2. **配置用 `os.environ` / `json`**，密钥不硬编码（第 01 章）。
3. **计数用 `Counter`、队列用 `deque`**，别手写循环。`[R2]`
4. **缓存用 `functools.cache`** 并注明失效条件。`[R3]`
5. **日志分级、脱敏、输出到 stderr**，面向用户只给可操作提示。

## 5. 最佳编码建议

- **import 按标准库/第三方/本地分组**（第 21 章）。`[R4]`
- **命名表达意图、注释解释「为什么选这个模块」**。`[R4]`
- **显式优于隐式、失败要快**（第 01 章）。
- **不硬编码业务值**（第 01 章）。

## 6. 编码示例

`examples/stdlib_demo.py`（全程只读、不写磁盘）：

```python
"""第 22 章示例：标准库三件套。"""

import collections
import json
import pathlib

payload = json.dumps({"tool": "search", "limit": 3}, ensure_ascii=False)
print("序列化:", payload)
print("反序列化:", json.loads(payload))

counts = collections.Counter(["search", "cache", "search"])
print("计数:", counts.most_common())

suffix = pathlib.PurePath("data/tools.json").suffix
print("后缀:", suffix)
```

运行：

```powershell
cd 'E:\ai-agent-study\py-base\05-类型系统与模块化\22-标准库'
python examples/stdlib_demo.py
```

关键输出：`计数: [('search', 2), ('cache', 1)]`；`后缀: .json` 来自 `PurePath`，不访问磁盘。`[R1]` `[R2]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org · **已核对** | https://docs.python.org/3.12/library/index.html | 标准库分类、Windows 安装包通常含完整标准库、`os`/`sys`/`urllib`/`pathlib`/`venv`/`ensurepip` 归属 |
| `[R2]` | python.org · **已核对** | https://docs.python.org/3.12/tutorial/datastructures.html | `collections.deque` 用于队列、`Counter` 类需求的动机 |
| `[R3]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/functools.html | `wraps` / `cache` / `lru_cache` / `partial` |
| `[R4]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | import 分组与顺序、命名与注释约定 |

## 8. 毕业自查清单

- [ ] 能说出标准库与第三方库的边界
- [ ] 能列举 6 个常用标准库模块及其适用场景
- [ ] 能说出 `deque` 为什么比 list 适合队列
- [ ] 能说出金额计算为什么不能用 `float`
- [ ] 能运行 `examples/stdlib_demo.py` 并解释四行输出

## 9. 下一章衔接

第 23 章 `第三方库`：标准库不够用时怎么选、怎么装、怎么锁版本；随后进入并发主线，按认知顺序先学 28 多线程与多进程。
