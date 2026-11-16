# 19 ABC

> 承接第 15 章：描述符约束「属性访问」，本章约束「实现契约」——用抽象基类声明接口，让缺失实现尽早暴露。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 08、09、14 章（类、类型、协议） |
| 本章目标 | `abc.ABC` / `abstractmethod`、虚拟子类、与鸭子类型/Protocol 的分工 |
| 毕业标准 | 能说出 ABC 与鸭子类型的取舍；能写出一个强制实现方法的基类 |
| 编码要求 | 能运行 `examples/abc_demo.py` 并解释 `isinstance` 与 `抽象方法` 两行 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节；「未直连核对」的链接按官方文档通行表述整理。本章为使用 `abc` 引入 `import`，模块化机制在第 21 章展开。

## 1. 概念

- `abc.ABC` 提供抽象基类基础设施；`@abstractmethod` 标记必须由子类实现的方法。**含未实现抽象方法的类不能被实例化**。`[R1]` `[R2]`
- 抽象方法可以有实现体，子类用 `super()` 调用；基类仍不可实例化。`[R1]`
- `register()` 可把无关类登记为**虚拟子类**，使 `isinstance` / `issubclass` 为真，但不需要继承，也不继承实现。`[R1]` `[R2]`
- `__subclasshook__` 可基于「有没有某方法」自动判定子类，是 ABC 与鸭子类型之间的桥。`[R1]`
- 标准库大量使用 ABC：`collections.abc` 定义 Iterable / Sequence / Mapping 等接口（第 17、22 章）。`[R3]`
- **与静态类型的分工**：ABC 是运行时检查，Protocol / 类型标注是静态检查（第 20 章），二者互补。`[R1]`

## 2. 注意事项

1. **不要把 ABC 当 Java 接口硬套**：Python 更常用鸭子类型 + 协议。`[R2]`
2. **`register` 只影响 `isinstance`**，不会给类补方法，误用会掩盖缺失实现。`[R1]`
3. **抽象方法签名要在子类保持一致**，否则调用时才炸。
4. **ABC 不检查返回类型**（第 20 章）。
5. **不要滥用深继承链**，优先组合（第 08 章）。
6. **异常类继承 `Exception` 而非 `BaseException`**（PEP 8，第 16 章）。`[R4]`

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 运行时 vs 静态 | ABC 在实例化时检查，Protocol 由类型检查器检查 | `[R1]` |
| 虚拟子类 | `isinstance` 为真 ≠ 具备行为，需要测试保障 | `[R2]` |
| 多重继承 | ABC 可作为 mixin，但 MRO 复杂度上升（第 08 章） | `[R1]` |
| 标准库 ABC | 优先复用 `collections.abc`，别自己重造 | `[R3]` |

## 4. 最佳实践

1. **只在「必须由子类提供实现」时用 `@abstractmethod`**。`[R1]`
2. **接口优先复用 `collections.abc` / `typing.Protocol`**。`[R3]`
3. **抽象基类写清 docstring**：约定哪些方法、哪些不变量。
4. **失败要快**：让缺失实现类在实例化时报错，而不是调用时静默出错（第 01 章）。

## 5. 最佳编码建议

- **类名用 `CapWords`，异常用 `Error` 后缀**。`[R4]`
- **注释解释「为什么需要运行时接口约束」**。`[R4]`
- **显式优于隐式、不做预留扩展**（第 01 章）。
- **公共接口用 `__all__` 明确导出**（PEP 8）。`[R4]`

## 6. 编码示例

`examples/abc_demo.py`：

```python
"""第 19 章示例：ABC 强制子类实现接口。"""

import abc

class Tool(abc.ABC):
    """工具接口。"""
    @abc.abstractmethod
    def run(self, argument):
        """执行工具并返回结果。"""

class Search(Tool):
    """搜索工具。"""
    def run(self, argument):
        return "result:" + argument

print("结果:", Search().run("AI news"))
print("isinstance:", isinstance(Search(), Tool))
print("未实现的抽象方法:", Tool.__abstractmethods__)
```

运行：

```powershell
cd 'E:\ai-agent-study\py-base\03-面向对象进阶与元编程\19-ABC'
python examples/abc_demo.py
```

关键输出：`结果: result:AI news`、`isinstance: True`、`未实现的抽象方法: frozenset({'run'})`——`Tool()` 本身不可实例化。`[R1]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/abc.html | `ABC`、`abstractmethod`、`register`、`__subclasshook__`、`__abstractmethods__` |
| `[R2]` | PEP 官方 · 未直连核对 | https://peps.python.org/pep-3119/ | ABC 动机、虚拟子类、与鸭子类型的关系 |
| `[R3]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/collections.abc.html | 标准库抽象基类（Iterable / Sequence / Mapping 等） |
| `[R4]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | 命名约定、`__all__`、异常命名、docstring |

## 8. 毕业自查清单

- [ ] 能说出 ABC 与鸭子类型各自的适用场景
- [ ] 能解释 `register()` 为什么不会给类补实现
- [ ] 能说出 ABC 与 Protocol 的区别（运行时 vs 静态）
- [ ] 能写出一个含 `@abstractmethod` 的基类并说明何时不可实例化
- [ ] 能运行 `examples/abc_demo.py` 并解释三行输出

## 9. 下一章衔接

第 12 章 `元类`：ABC 借助元类 `ABCMeta` 才能工作——至此前置知识齐备，终于可以讲「类是怎么被创建的」。这是模块 03 的最后一块，也是大纲编号 12 被放到最后学的原因。
