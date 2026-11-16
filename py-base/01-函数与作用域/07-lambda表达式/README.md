# 07 lambda表达式

> 承接第 06 章：闭包说明「函数可以捕获外层名字」，本章讲只含单个表达式的匿名函数，以及它最合适的用武之地。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 05–06 章（函数、作用域） |
| 本章目标 | `lambda` 语法、与 `def` 的关系、`key=` 场景、闭包行为、可读边界 |
| 毕业标准 | 能说出 lambda 与 `def` 的等价关系；能解释 PEP 8 为何反对 `f = lambda ...` |
| 编码要求 | 能运行 `examples/lambda_demo.py` 并解释排序与倍增输出 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节；「未直连核对」的链接按官方文档通行表述整理。

## 1. 概念

- `lambda a, b: a + b` 创建小的匿名函数；官方明确：它在语法上**被限制为单个表达式**，语义上只是普通函数定义的**语法糖**。`[R1]`
- lambda 可用在任何需要函数对象的地方；与嵌套函数一样，能引用包含作用域的变量。`[R1]`
- 官方给出的两个典型用途：由函数返回小函数（`make_incrementor(n)`），以及把小函数当参数传给 `sort(key=lambda pair: pair[1])`。`[R1]`
- PEP 8 明确要求：**总是用 `def`，不要用赋值语句把 lambda 直接绑定给标识符**——`f = lambda x: 2*x` 会让函数对象的名字变成通用的 `<lambda>`，损害 traceback 可读性。`[R2]`
- lambda 没有语句、没有 `return`、不能写 docstring 与注解（第 20 章）；复杂逻辑一律 `def`。`[R1]` `[R2]`

## 2. 注意事项

1. **不要 `f = lambda ...`**，写 `def f(...)`。`[R2]`
2. **单表达式限制**：需要 `if` 语句、循环、异常处理时改 `def`。`[R1]`
3. **lambda 里也能写条件表达式**（`x if ... else ...`），但不等于可以写语句。`[R1]`
4. **闭包延迟绑定同样适用**：循环里生成 lambda 会共享外层名字（第 06 章）。`[R1]`
5. **不要把复杂业务逻辑塞进 `key=`**，可读性差且难调试。`[R2]`
6. **`map` / `filter` + lambda 通常不如推导式**，官方教程建议简单映射优先推导式。`[R3]`

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 调试可见性 | lambda 的 `__name__` 是 `<lambda>`，栈追踪不如具名函数清晰 | `[R2]` |
| 默认参数绑定 | 想固定闭包值时可用 `lambda x, n=n: ...`，但会改变签名 | `[R1]` |
| 类型标注 | lambda 不能带注解，公共 API 用 `def` 更合适 | `[R1]` |
| 表达式能力 | 不能包含 `yield`、`await` 等语句级结构（分别见 17 / 26 章） | `[R1]` |
| 性能 | lambda 不比等价 `def` 快，选择依据是表达力而非性能 | `[R1]` |

## 4. 最佳实践

1. **只在「一次性、单表达式、就地使用」时用 lambda**。`[R1]`
2. **`sorted` / `list.sort` 的 `key=` 是最典型场景**。`[R1]`
3. **需要复用、需要名字、需要文档时立刻改 `def`**。`[R2]`
4. **映射与过滤优先用推导式**，`map(lambda...)` 只在确有需要时用。`[R3]`
5. **捕获外层变量时保持作用域短小**（第 06 章）。

## 5. 最佳编码建议

- **命名表达意图**：`key=lambda item: item[1]` 尚可，`key=lambda x: x[1]` 建议改为具名函数。`[R2]`
- **不写嵌套三元表达式**，超过一层就换 `def`。`[R2]`
- **注释解释「为什么这样排序」**，而不是复述 lambda。`[R2]`
- **显式优于隐式、可读性 > 技巧性**（第 01 章）。

## 6. 编码示例

### 6.1 可运行脚本

`examples/lambda_demo.py`：

```python
"""第 07 章示例：lambda 作为一次性小函数。"""

tool_costs = [("search", 3), ("cache", 1), ("translate", 2)]
by_cost = sorted(tool_costs, key=lambda item: item[1])
by_name = sorted(tool_costs, key=lambda item: item[0])
print("按成本:", by_cost)
print("按名称:", by_name)

def make_multiplier(factor):
    """lambda 可引用包含作用域的变量 [R1]。"""
    return lambda value: value * factor

double = make_multiplier(2)
print("倍增:", double(5))
```

运行：

```powershell
cd 'E:\ai-agent-study\py-base\01-函数与作用域\07-lambda表达式'
python examples/lambda_demo.py
```

关键输出：按成本排序得到 `cache, translate, search`；`double(5)` 得 `10`，说明 lambda 记住了外层的 `factor`。`[R1]`

### 6.2 官方反例（不要这样写）

```python
f = lambda x: 2 * x
```

PEP 8 要求改成 `def f(x): return 2 * x`，理由是可读性与 traceback 中的函数名。`[R2]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org · **已核对** | https://docs.python.org/3.12/tutorial/controlflow.html | `lambda` 单表达式、是 `def` 的语法糖、可引用包含作用域、返回小函数与 `key=` 用法 |
| `[R2]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | 禁止 `f = lambda ...`、具名函数可读性、注释与命名约定 |
| `[R3]` | python.org · **已核对** | https://docs.python.org/3.12/tutorial/datastructures.html | 推导式优先于 map/filter、排序与 `key` 相关用法 |

## 8. 毕业自查清单

- [ ] 能说出 lambda 与 `def` 的等价关系及单表达式限制
- [ ] 能解释 PEP 8 为什么反对把 lambda 直接绑定给名字
- [ ] 能写出 `sorted(..., key=lambda ...)` 并说明 `key` 的作用
- [ ] 能解释闭包延迟绑定在 lambda 上同样成立
- [ ] 能运行 `examples/lambda_demo.py` 并解释两行排序结果与倍增结果

## 9. 下一章衔接

第 08 章 `类和对象`：函数与作用域讲完，开始面向对象——`class`、`__init__`、`self`、实例属性与类属性的差别。第 09–11 章继续类型、创建过程与可调用对象。
