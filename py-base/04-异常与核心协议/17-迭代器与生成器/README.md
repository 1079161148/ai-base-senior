# 17 迭代器与生成器

> 承接第 16 章：异常机制里 `StopIteration` 是专门留给迭代的。本章把 `for` 拆开，讲惰性产出——Agent 的流式输出正是建立在这上面。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 04、14、16 章（容器、特殊方法、异常） |
| 本章目标 | iterable / iterator、`iter()` / `next()`、`yield`、生成器表达式、`yield from` |
| 毕业标准 | 能说出 iterable 与 iterator 的区别；能解释生成器为什么省内存 |
| 编码要求 | 能运行 `examples/generator_demo.py` 并解释 `next` 之后剩余元素为何少了 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节；「未直连核对」的链接按官方文档通行表述整理。

## 1. 概念

- **iterable**：能传给 `iter()` 得到 iterator 的对象；**iterator**：实现 `__next__()`，耗尽时抛 `StopIteration`。`for` 循环就是不断 `next()` 直到捕获 `StopIteration`。`[R1]` `[R2]`
- 容器（list / dict / set）是 iterable，但不是 iterator；`iter(list)` 才返回迭代器。`[R2]`
- 含 `yield` 的函数返回**生成器对象**，函数体在每次 `next()` 时执行到下一个 `yield` 并暂停，因此**惰性**产出、不一次性占内存。`[R1]` `[R3]`
- 生成器表达式 `(expr for x in ...)` 与列表推导式外形相近，但返回生成器；官方教程强调 `range()` 也是「不真的造出列表」的 iterable。`[R4]`
- `yield from iterable` 把子迭代器的产出委托出去，是协程历史演进的基础（第 26 章）。`[R5]`
- 生成器只能被消费一次；耗尽后继续 `next()` 仍抛 `StopIteration`。`[R1]`

## 2. 注意事项

1. **生成器不能重复使用**，需要多次遍历就转成 list 或重新创建。`[R1]`
2. **别在生成器里吞 `StopIteration`**，会破坏迭代协议（PEP 479）。`[R5]`
3. **`next()` 要处理耗尽**，交互式代码里给默认值 `next(it, default)`。
4. **生成器内 `return value`** 会成为 `StopIteration.value`，普通遍历看不到。`[R1]`
5. **不要在生成器里做隐藏的副作用**，调用时才会发生，调试困难。

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 一次性 | 生成器与文件句柄一样是「流」，重读要重建 | `[R1]` |
| 并发/异步 | 同步生成器不能直接 `await`，异步生成器见第 27 章 | `[R5]` |
| 内存与延迟 | 惰性省内存，但把计算推迟到消费时，错误也更晚暴露 | `[R1]` |
| 上下文管理 | 生成器持有资源时需要 `with` / `finally` 保证释放（第 18 章） | `[R1]` |

## 4. 最佳实践

1. **数据量大或来自流时使用生成器**，小集合直接用 list。`[R1]`
2. **管道式处理用生成器表达式 + 内置函数**（`sum`、`any`、`sorted`）。`[R4]`
3. **复杂过滤逻辑写成生成器函数**而非多层推导式。`[R4]`
4. **需要复用结果时显式 `list(gen)`**，并注释原因。
5. **流式输出把「产出」与「渲染」解耦**（Agents 客户端常见形态）。

## 5. 最佳编码建议

- **命名表达意图**：`iter_tool_names()`，不用 `gen1`。`[R6]`
- **注释解释「为什么用惰性」**。`[R6]`
- **显式处理耗尽**，不依赖静默停止。
- **不在生成器里写不可见的全局状态修改**（第 06 章）。

## 6. 编码示例

`examples/generator_demo.py`：

```python
"""第 17 章示例：生成器惰性产出。"""

def tool_names(names, prefix=None):
    """按可选前缀过滤工具名，惰性产出 [R1]。"""
    for name in names:
        if prefix is None or name.startswith(prefix):
            yield name

source = ["search", "cache", "summarize"]
print("全部:", list(tool_names(source)))
print("前缀 s:", list(tool_names(source, "s")))

upper = (name.upper() for name in source)
print("第一个:", next(upper))
print("剩余:", list(upper))
```

运行：

```powershell
cd 'E:\ai-agent-study\py-base\04-异常与核心协议\17-迭代器与生成器'
python examples/generator_demo.py
```

关键输出：`全部: ['search', 'cache', 'summarize']`、`前缀 s: ['search', 'summarize']`、`第一个: SEARCH`、`剩余: ['CACHE', 'SUMMARIZE']`——生成器消费掉第一个后只剩两个。`[R1]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org · 未直连核对 | https://docs.python.org/3.12/tutorial/classes.html | 迭代器、`__next__`、`StopIteration`、生成器 |
| `[R2]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/stdtypes.html | 迭代器类型、`iter()` / `next()` 协议 |
| `[R3]` | PEP 官方 · 未直连核对 | https://peps.python.org/pep-0255/ | 简单生成器与 `yield` 的引入 |
| `[R4]` | python.org · **已核对** | https://docs.python.org/3.12/tutorial/controlflow.html | `range()` 是 iterable 而非 list、`enumerate()`、内置函数配合 |
| `[R5]` | PEP 官方 · 未直连核对 | https://peps.python.org/pep-0380/ | `yield from` 委托语法；PEP 479 的 `StopIteration` 规则 |
| `[R6]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | 命名约定、注释写「为什么」 |

## 8. 毕业自查清单

- [ ] 能说出 iterable 与 iterator 的区别，以及 `for` 如何终止
- [ ] 能解释生成器为什么省内存、为什么只能消费一次
- [ ] 能说出 `yield from` 的用途与它和协程的关系
- [ ] 能说出生成器表达式与列表推导式的差别
- [ ] 能运行 `examples/generator_demo.py` 并解释「剩余」一行

## 9. 下一章衔接

第 18 章 `上下文管理器`：`with` 用 `__enter__` / `__exit__` 保证资源释放，配合生成器的 `finally` 才能写出可靠的流式处理；随后第 20 章进入类型标注。
