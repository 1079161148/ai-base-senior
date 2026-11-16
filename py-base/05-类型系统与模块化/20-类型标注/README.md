# 20 类型标注

> 承接第 18 章：核心语法与协议已完成。本章进入工程化第一站——把「参数是什么、返回什么」写进代码，让大型 Agent 项目可维护。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 05、04、09 章（函数、容器、类型） |
| 本章目标 | 变量/函数注解、`typing` 常用类型、`Optional`、Protocol、静态检查器定位 |
| 毕业标准 | 能解释注解**不参与运行时**；能说出 `list[str]` 与 `Optional[str]` 的含义 |
| 编码要求 | 能运行 `examples/typing_demo.py` 并解释 `__annotations__` 输出 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节；「未直连核对」的链接按官方文档通行表述整理。

## 1. 概念

- 函数注解是**完全可选**的元数据，存在 `__annotations__` 字典里，**对运行时行为没有影响**；解释器不因注解做类型检查。`[R1]` `[R4]`
- 参数注解写在 `:` 后，返回注解用 `->`；变量注解形如 `x: int = 1`。`[R1]` `[R2]`
- 3.9+ 可直接用内建泛型 `list[str]` / `dict[str, int]`；`typing` 提供 `Optional`、`Union`、`Literal`、`Protocol`、`TypeVar`、`ParamSpec` 等。`[R3]`
- `Optional[T]` 等价于 `T | None`；它表示「可能为 None」，**不是「可选参数」**（可选参数靠默认值）。`[R3]`
- `Protocol` 提供**结构化子类型**（静态鸭子类型），与第 19 章的运行时 ABC 互补。`[R5]`
- 类型检查器（mypy / pyright 等）是**独立的外部工具**，PEP 8 明确：不用类型检查器的人可以忽略注解。`[R4]`

## 2. 注意事项

1. **注解不等于校验**：外部输入仍必须在服务端独立校验（第 01 章）。`[R4]`
2. **别用 `Any` 掩盖类型问题**（第 01 章禁止）。`[R3]`
3. **`Optional` 与「有默认值」是两回事**。
4. **注解里的容器要写元素类型**，`dict` / `list` 裸写等于放弃信息。
5. **公共 API 优先标注**，内部一次性脚本可省略。
6. **不要为了通过检查器改运行时逻辑**。

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 运行时无强制 | 注解不抛异常，错误值照样传进去 | `[R1]` `[R4]` |
| 前向引用 | 引用尚未定义的类型用字符串或 `from __future__ import annotations`（第 21 章） | `[R2]` |
| 装饰器 | 装饰器会遮蔽真实签名，需 `wraps` / `ParamSpec`（第 13 章） | `[R3]` |
| 动态特性 | 元类、`getattr`、反射对静态检查器不透明（第 12 章） | `[R4]` |
| 第三方库 | 用 stub / `.pyi` 补充类型信息（第 23 章） | `[R4]` |

## 4. 最佳实践

1. **公共函数与跨模块数据结构优先标注**。`[R4]`
2. **用 `Protocol` 表达「需要哪些能力」**，少用具体类。`[R5]`
3. **把静态检查接进 CI**，但不在运行时重复校验。
4. **注解写不出来时先简化设计**，而不是塞 `Any`。
5. **配置与密钥不进注解、不进日志**（第 01 章）。

## 5. 最佳编码建议

- **冒号后一个空格、`->` 两侧空格**；有注解的默认值 `=` 两侧也要空格。`[R4]`
- **变量注解 `name: str` 不加多余空格**。`[R4]`
- **命名表达意图**，注释解释「为什么用 Protocol / Optional」。`[R4]`
- **显式优于隐式、不做预留抽象**（第 01 章）。

## 6. 编码示例

`examples/typing_demo.py`：

```python
"""第 20 章示例：类型标注只是元数据。"""

def build_report(tool_name: str, results: list[str], limit: int = 3) -> dict:
    """返回工具结果摘要 [R1]。"""
    return {"tool": tool_name, "items": results[:limit]}

report: dict = build_report("search", ["a", "b", "c", "d"])
print("结果:", report)
print("注解:", build_report.__annotations__)
```

运行：

```powershell
cd 'E:\ai-agent-study\py-base\05-类型系统与模块化\20-类型标注'
python examples/typing_demo.py
```

关键输出：`注解: {'tool_name': <class 'str'>, 'results': list[str], 'limit': <class 'int'>, 'return': <class 'dict'>}`——注解只是可读取的字典，没有做任何检查。`[R1]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org · **已核对** | https://docs.python.org/3.12/tutorial/controlflow.html | 函数注解是可选元数据、存在 `__annotations__`、不影响运行时 |
| `[R2]` | PEP 官方 · 未直连核对 | https://peps.python.org/pep-0526/ | 变量注解语法与格式 |
| `[R3]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/typing.html | `Optional` / `Union` / `Protocol` / `ParamSpec` / 内建泛型 |
| `[R4]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | 注解空格规则、类型检查器是可选独立工具、不使用者可忽略注解 |
| `[R5]` | PEP 官方 · 未直连核对 | https://peps.python.org/pep-0544/ | 结构化子类型（Protocol）与静态鸭子类型 |

## 8. 毕业自查清单

- [ ] 能解释注解为什么不影响运行时
- [ ] 能说出 `Optional[T]` 的真实含义
- [ ] 能说出 Protocol 与 ABC 的分工
- [ ] 能说出注解的空格格式要求
- [ ] 能运行 `examples/typing_demo.py` 并解释 `__annotations__` 输出

## 9. 下一章衔接

第 21 章 `模块化`：`import` 机制、包与 `__init__.py`、绝对/相对导入、`__name__ == "__main__"`；随后 22 标准库、23 第三方库。
