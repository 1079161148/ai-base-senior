# 12 元类

> 模块 03 收尾：装饰器 → 魔法方法 → 描述符 → ABC 全部学完，才具备理解「类如何被创建」的前置知识。本章按认知顺序最后讲，但保留大纲原编号 12。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 08–11、13–15、19 章 |
| 本章目标 | `type` 是默认元类、`metaclass=`、`type()` 动态建类、元类 `__new__`、何时不该用 |
| 毕业标准 | 能说出 `type(type(obj))` 是什么；能解释 `ABCMeta` 为什么是元类；能说清「能读懂但不要自己造」的判据 |
| 编码要求 | 能运行 `examples/metaclass_demo.py` 并解释 `已注册` 一行 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节；「未直连核对」的链接按官方文档通行表述整理。

## 1. 概念

- **类自身也是对象**；创建类的「类」叫元类。默认情况下 `type` 就是元类，`type(SomeClass)` 返回 `type`（第 09 章）。`[R1]`
- `type(name, bases, namespace)` 可以**动态创建类**：三个参数分别是类名、基类 tuple、属性字典。`[R1]`
- `class C(metaclass=M):` 指定自定义元类；类体执行后，解释器调用元类来构建类对象，并把结果绑定到名字。`[R1]` `[R2]`
- 元类最常重写的是 `__new__(mcls, name, bases, namespace)`（创建类对象）与 `__init__`（初始化类对象）；`__call__` 控制**实例**创建（第 10 章）。`[R1]`
- `abc.ABCMeta` 就是元类：它在类创建时收集 `@abstractmethod`，因此 ABC 能阻止实例化（第 19 章）。`[R3]`
- 元类继承会冲突：多个基类带不同元类时，必须有一个是所有其他元类的子类。`[R1]`
- 类装饰器（第 13 章）能完成大多数「改类」需求，且更显式。`[R2]`

## 2. 注意事项

1. **不要用元类做「自动注册一切」的隐式魔法**，调试成本极高（第 01 章边界）。
2. **优先类装饰器 / `__init_subclass__` / `__set_name__`**，它们是更轻的替代。`[R1]`
3. **元类里抛错会发生在导入时**，错误信息要可操作。
4. **`super().__new__(mcls, ...)` 必须透传 `namespace`**，否则类体定义丢失。
5. **元类属性与类属性查找顺序不同**，别混用。
6. **本章目标是「读懂框架源码」**，Agents 应用开发极少需要自写元类（第 01 章）。

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 元类冲突 | 多继承时元类必须兼容，否则 `TypeError` | `[R1]` |
| 导入期副作用 | 元类代码在模块导入时执行，不能做 I/O | `[R1]` |
| 与描述符 | 元类上的描述符作用于类属性访问（第 15 章） | `[R1]` |
| 与 `__init_subclass__` | 后者在父类上定义、无需元类，是更简单的扩展点 | `[R1]` |
| 静态类型 | 元类行为对类型检查器不透明（第 20 章） | `[R2]` |

## 4. 最佳实践

1. **默认不用元类**；先问「类装饰器够不够」。`[R2]`
2. **读框架时识别元类的三个信号**：`metaclass=`、`ABCMeta`、动态 `type(...)` 建类。
3. **必须用元类时保持极薄**：只做注册 / 校验，不塞业务逻辑。
4. **写清楚 docstring 与错误信息**，说明类创建时发生了什么。
5. **显式优于隐式**（第 01 章）。

## 5. 最佳编码建议

- **命名表达意图**：`RegisterMeta`，不用 `Meta1`。`[R4]`
- **注释解释「为什么必须用元类」**——这是典型的非直觉取舍。`[R4]`
- **不硬编码、不吞异常、失败要快**（第 01 章）。
- **读懂 > 能写**：本章毕业标准是能解释，不是鼓励自造。

## 6. 编码示例

`examples/metaclass_demo.py`：

```python
"""第 12 章示例：type 动态建类与最小自定义元类。"""

def run(self, argument):
    return self.name + ":" + argument

DynamicTool = type("DynamicTool", (), {"name": "search", "run": run})
print("动态类:", DynamicTool().run("AI news"))

class RegisterMeta(type):
    """记录被创建的类，仅用于演示机制 [R1]。"""
    created = []

    def __new__(mcls, name, bases, namespace):
        cls = super().__new__(mcls, name, bases, namespace)
        mcls.created.append(name)
        return cls

class Index(metaclass=RegisterMeta):
    pass

class Query(metaclass=RegisterMeta):
    pass

print("已注册:", RegisterMeta.created)
print("类的类型:", type(Query).__name__)
```

运行：

```powershell
cd 'E:\ai-agent-study\py-base\03-面向对象进阶与元编程\12-元类'
python examples/metaclass_demo.py
```

关键输出：`动态类: search:AI news`、`已注册: ['Index', 'Query']`、`类的类型: RegisterMeta`——最后一行为什么不是 `type`：显式指定了元类。`[R1]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org · 未直连核对 | https://docs.python.org/3.12/reference/datamodel.html | 元类、`type(name, bases, dict)`、类创建步骤、`__init_subclass__` / `__set_name__`、元类冲突、`__call__` |
| `[R2]` | PEP 官方 · 未直连核对 | https://peps.python.org/pep-3115/ | 元类 `__prepare__` 与类体命名空间、现代元类语法动机 |
| `[R3]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/abc.html | `ABCMeta` 是元类、抽象方法收集时机 |
| `[R4]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | 命名约定、注释写「为什么」 |

## 8. 毕业自查清单

- [ ] 能说出 `type(SomeClass)` 与 `type(type(SomeClass))` 分别是什么
- [ ] 能写出 `type(name, bases, namespace)` 动态建类
- [ ] 能解释元类 `__new__` 与 `__call__` 各管哪一步
- [ ] 能说出至少两个「不用元类」的替代方案
- [ ] 能运行 `examples/metaclass_demo.py` 并解释 `类的类型` 一行

## 9. 下一章衔接

第 16 章 `异常处理`：面向对象主线结束，转入「程序出错时怎么办」——异常层级、`try/except/else/finally`、异常链，随后 17 迭代器与生成器、18 上下文管理器。
