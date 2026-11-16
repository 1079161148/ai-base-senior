# 11 可调用对象

> 承接第 10 章：实例创建完成。本章让实例「像函数一样被调用」，并把函数、类、方法、lambda 统一到「可调用」这个概念下。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 05–10 章（函数、类、创建过程） |
| 本章目标 | `__call__`、`callable()`、可调用对象家族、用实例承载状态 |
| 毕业标准 | 能说清 `obj(x)` 背后调用什么；能判断什么时候该用类而不是闭包 |
| 编码要求 | 能运行 `examples/callable_demo.py` 并解释 `调用结果` 一行 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节；「未直连核对」的链接按官方文档通行表述整理。

## 1. 概念

- 定义 `__call__` 后，实例可以像函数一样写 `obj(args)`；`obj(args)` 等价于 `type(obj).__call__(obj, args)`。`[R1]`
- `callable(x)` 判断对象是否可被调用；函数、方法、类、lambda、实现了 `__call__` 的实例都返回 `True`。`[R2]`
- **类本身也可调用**：调用类就是实例化（第 10 章），所以 `callable(SomeClass)` 为真。`[R1]` `[R2]`
- 可调用实例的价值是**带状态的函数**：配置、计数、缓存可以放在实例属性里，比闭包更显式、更易测。`[R1]`
- 装饰器（第 13 章）、`functools.partial`、策略对象都建立在这一机制上。`[R3]`

## 2. 注意事项

1. **`__call__` 不要写隐藏的重副作用**，调用点看不出会改状态。`[R1]`
2. **`callable()` 为真不代表调用一定成功**，参数不匹配仍会抛 `TypeError`（第 16 章）。`[R2]`
3. **别为了「看起来像函数」硬加 `__call__`**，普通方法名更能表达意图。
4. **可调用实例与闭包二选一**：需要多个方法/可配置/可测试时用类。`[R1]`
5. **不要覆盖 `__call__` 的签名约定**，保持与文档一致。

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 状态共享 | 实例属性被多次调用共享，并发场景需同步（第 28 章） | `[R1]` |
| 元类层 | 类被调用由元类的 `__call__` 处理，见第 12 章 | `[R1]` |
| 内建可调用 | `len`、`sorted` 等也是可调用对象，本质一致 | `[R2]` |
| 描述符绑定 | 方法之所以能自动传 `self`，依赖描述符协议（第 15 章） | `[R1]` |

## 4. 最佳实践

1. **需要「有配置的函数」时用可调用实例**，把配置放 `__init__`。`[R1]`
2. **单一行为、无状态用普通函数**（第 05 章）。
3. **为 `__call__` 写 docstring**，说明副作用与返回类型。
4. **把计数 / 缓存等状态显式命名**，不用全局变量（第 06 章）。

## 5. 最佳编码建议

- **类名用 `CapWords`、方法用小写下划线**（第 08 章）。`[R4]`
- **注释解释「为什么用可调用对象而非闭包」**。`[R4]`
- **显式优于隐式、不可变优先**（第 01 章）。
- **外部输入在服务端校验**（第 01 章）。

## 6. 编码示例

`examples/callable_demo.py`：

```python
"""第 11 章示例：__call__ 让实例像函数一样调用。"""

class Tool:
    """带名字的工具，实例可直接调用。"""
    def __init__(self, name):
        self.name = name
        self.call_count = 0

    def __call__(self, argument):
        self.call_count = self.call_count + 1
        return self.name + ":" + argument

search = Tool("search")
print("实例可调用:", callable(search))
print("调用结果:", search("AI news"))
print("调用次数:", search.call_count)
print("函数可调用:", callable(len))
print("类可调用:", callable(Tool))
```

运行：

```powershell
cd 'E:\ai-agent-study\py-base\02-面向对象基础\11-可调用对象'
python examples/callable_demo.py
```

关键输出：`调用结果: search:AI news`、`调用次数: 1`；`callable(Tool)` 为 `True`，因为调用类就是实例化。`[R1]` `[R2]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org · 未直连核对 | https://docs.python.org/3.12/reference/datamodel.html | `object.__call__`、调用等价形式、实例可调用、元类 `__call__`、描述符绑定 |
| `[R2]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/functions.html | `callable()` 定义与返回语义 |
| `[R3]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/functools.html | `partial` 等可调用工具、装饰器保留元数据 |
| `[R4]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | 命名约定、注释写「为什么」、简单可读优先 |

## 8. 毕业自查清单

- [ ] 能说出 `obj(x)` 实际调用了哪个方法
- [ ] 能列举四类可调用对象（函数 / 方法 / 类 / 带 `__call__` 的实例）
- [ ] 能解释为什么 `callable(SomeClass)` 为真
- [ ] 能说出可调用实例相对闭包的优势与代价
- [ ] 能运行 `examples/callable_demo.py` 并解释五行输出

## 9. 下一章衔接

第 13 章 `装饰器`：可调用对象 + 闭包 +「函数也是对象」三者合起来，就是装饰器的全部基础。按认知顺序先学装饰器，再回到 14 魔法方法、15 描述符、19 ABC，最后才到 12 元类。
