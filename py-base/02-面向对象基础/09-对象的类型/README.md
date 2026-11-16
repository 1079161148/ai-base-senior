# 09 对象的类型

> 承接第 08 章：类已经能造出实例，本章回答「这个对象到底是什么」——类型、身份与类型检查的边界。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 08 章（类与实例） |
| 本章目标 | `type()` / `isinstance()` / `id()`、`__class__` 与 `__mro__`、鸭子类型、类本身也是对象 |
| 毕业标准 | 能说清 `isinstance` 与 `type(...) is` 的差别；能解释「类自身也有类型」 |
| 编码要求 | 能运行 `examples/type_demo.py` 并解释 `类的类型` 那一行 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节；「未直连核对」的链接按官方文档通行表述整理。

## 1. 概念

- Python 中**一切皆对象**：每个对象都有身份（`id()`）、类型（`type()`）与值。身份在生命周期内不变且唯一；`is` 比较身份，`==` 比较值。`[R1]` `[R2]`
- `type(obj)` 返回对象的类型；对一个类调用 `type()` 通常得到 `type`——**类本身也是对象**，其类型即元类（第 12 章）。`[R1]` `[R2]`
- `isinstance(obj, cls)` 会把**继承关系**计入判断；`type(obj) is cls` 只看精确类型。PEP 8 明确要求类型判断用 `isinstance()`。`[R3]`
- `__mro__` 给出方法解析顺序；属性查找沿这条链进行（第 08 章）。`[R2]`
- **鸭子类型**：关注对象「能做什么」而非「是什么类」。这解释了为什么标准库大量用协议（`__len__`、`__iter__`，第 14 / 17 章）而非强制基类。`[R2]`
- 结构化类型检查（Protocol、静态类型）属于第 20 章；ABC 属于第 19 章。`[R2]`

## 2. 注意事项

1. **不要用 `type(x) is SomeClass` 做类型判断**，会漏掉子类。`[R3]`
2. **`is` 只用于 `None` / 单例身份比较**，不要用它比整数或字符串值。`[R3]`
3. **`bool` 是 `int` 的子类**，`isinstance(True, int)` 为真——需要排除时显式判断。`[R2]`
4. **`id()` 只在对象存活期间唯一**，对象销毁后 id 可能被复用。`[R1]`
5. **不要靠类型分发写长串 `if isinstance`**，优先多态 / 协议（第 14 章）。`[R2]`

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 静态类型不参与运行时 | 注解不强制检查，见第 20 章 | `[R3]` |
| 鸭子类型与运行时错误 | 缺少方法只在调用时暴露，需测试保障 | `[R2]` |
| 虚拟子类 | ABC 的 `register` 能让 `isinstance` 为真而无继承关系，见第 19 章 | `[R2]` |
| 元类 | 类的类型可以是 `type` 的子类，见第 12 章 | `[R2]` |

## 4. 最佳实践

1. **公共接口按能力设计**（有没有 `read()` / `__iter__`），不按具体类。`[R2]`
2. **必须校验时用 `isinstance`**，并把失败路径写清楚。`[R3]`
3. **调试用 `type(x).__name__`、`x.__dict__`**，不要把反射写进业务逻辑。`[R1]`
4. **类型标注交给第 20 章的工具链**，运行时不做重复校验。

## 5. 最佳编码建议

- **命名表达意图**、注释解释「为什么需要这个类型分支」。`[R3]`
- **布尔量用 `is_` / `has_` 前缀**（第 01 章）。
- **不捕获后抛更模糊的异常**（第 16 章）。
- **显式优于隐式、失败要快**（第 01 章）。

## 6. 编码示例

`examples/type_demo.py`：

```python
"""第 09 章示例：类型、身份与 isinstance。"""

class ToolCall:
    """一次工具调用。"""
    def __init__(self, name):
        self.name = name

call = ToolCall("search")
print("对象类型:", type(call).__name__)
print("类的类型:", type(ToolCall).__name__)
print("isinstance:", isinstance(call, ToolCall))
print("继承链:", [item.__name__ for item in ToolCall.__mro__])
print("身份不同:", id(call) != id(ToolCall("search")))
```

运行：

```powershell
cd 'E:\ai-agent-study\py-base\02-面向对象基础\09-对象的类型'
python examples/type_demo.py
```

关键输出：`类的类型: type`——类自身是 `type` 的实例，为第 12 章埋伏笔；`继承链: ['ToolCall', 'object']`。`[R2]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/functions.html | `type()` / `isinstance()` / `id()` / `callable()` 等内置函数说明 |
| `[R2]` | python.org · 未直连核对 | https://docs.python.org/3.12/reference/datamodel.html | 对象身份/类型/值、`__class__`、`__mro__`、类也是对象、鸭子类型与协议、`bool` 与 `int` |
| `[R3]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | 用 `isinstance()` 而非直接比类型、`is None`、不用 `==` 比布尔 |

## 8. 毕业自查清单

- [ ] 能说出身份、类型、值三者的区别与 `is` / `==` 的适用场景
- [ ] 能解释为什么 `isinstance` 比 `type(...) is` 更适合类型判断
- [ ] 能说出「类自身也有类型」指向哪一章
- [ ] 能解释鸭子类型与协议的关系
- [ ] 能运行 `examples/type_demo.py` 并解释 `type` 那一行

## 9. 下一章衔接

第 10 章 `对象的创建过程`：`ToolCall("search")` 背后 `__new__` 与 `__init__` 各做什么、谁调用它们；第 11 章 `可调用对象` 讲 `__call__`，第 13 章进入装饰器。
