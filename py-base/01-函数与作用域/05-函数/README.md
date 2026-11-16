# 05 函数

> 承接第 04 章：容器已能承载工具参数与结果，本章把重复逻辑封装成函数——第 01 章 Agent 示例里的「计划 / 工具 / 输出」从此可以各自成块。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 03–04 章（控制流、容器） |
| 本章目标 | `def`、参数传递、返回值、docstring、默认参数、关键字参数、`*args` / `**kwargs` |
| 毕业标准 | 能解释「参数值是对象引用」；能说清可变默认值为什么会跨调用累积；能写出带 docstring 的函数 |
| 编码要求 | 能运行 `examples/function_demo.py` 并解释两次 `append_result` 的输出 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节。标注「已核对」的页面在前几章已实际访问；「未直连核对」为官方文档通行表述整理，需按链接复核。

## 1. 概念

- `def` 引入函数定义，后跟函数名与括号内的形参列表；**函数体必须缩进**。函数体首语句可以是字符串字面量，即 docstring，官方建议养成写 docstring 的习惯。`[R1]` `[R2]`
- `return` 返回值；`return` 不带表达式、或执行到函数末尾，都返回 `None`。`[R1]`
- 调用时实参进入被调函数的**局部符号表**；官方原文称参数是 *call by value*，且值总是**对象引用**，脚注进一步说明更准确的说法是 *call by object reference*——传入可变对象时，调用方能看到被调方对它的原地修改。`[R1]`
- **默认值只在函数定义时求值一次**；默认值是可变对象（list / dict / 类实例）时会在多次调用间累积，官方给出的正解是默认值写 `None`、在函数体内初始化。`[R1]`
- 关键字参数形如 `kwarg=value`，必须跟在位置参数之后，顺序不重要，同一参数不能重复赋值；`*args` 收位置参数为 tuple，`**kwargs` 收关键字参数为 dict。`[R1]`
- `/` 之前为 positional-only，`*` 之后为 keyword-only；官方建议：参数名无意义或要防止改名破坏 API 用 positional-only，名字有含义用 keyword-only。`[R1]`
- 函数注解是**可选元数据**，存在 `__annotations__`，不影响运行时行为；系统展开在第 20 章。`[R1]`

## 2. 注意事项

1. **绝不用 `[]` / `{}` 作默认值**，用 `None` 兜底。`[R1]`
2. **不要假设传参是值拷贝**：原地修改传入的 list 会影响调用方。`[R1]`
3. **关键字参数必须在位置参数之后**，且不能重复给同一个参数。`[R1]`
4. **没有 `return` 的函数返回 `None`**，别把结果当列表用。`[R1]`
5. **`lambda` 不要直接绑定给名字**（应写 `def`），这是 PEP 8 的明确要求。`[R3]`
6. **函数名用 `lowercase_with_underscores`**，与 PEP 8 一致。`[R3]`

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 可变对象共享 | 参数与默认值都可能共享同一对象；需要隔离时显式复制 | `[R1]` |
| 作用域 | 函数内赋值默认创建局部变量；`global` / `nonlocal` 在第 06 章展开 | `[R1]` |
| 注解无运行时效果 | 注解不被解释器强制检查，类型检查器是独立工具；第 20 章 | `[R1]` `[R3]` |
| 递归与栈 | 每次调用创建新的局部符号表，深度过大有递归限制；属第 16 章后话题 | `[R1]` |
| 参数形式取舍 | positional-only 会限制调用方式，改 API 前要评估兼容性 | `[R1]` |

## 4. 最佳实践

1. **一个函数只做一件事**，函数名说明意图，副作用写进 docstring。`[R2]`
2. **默认参数用不可变值**，可变容器在函数内新建。`[R1]`
3. **公共 API 用 keyword-only** 让调用点自解释，避免依赖位置。`[R1]`
4. **返回值保持一致**：要么都带表达式，要么都显式 `return None`。`[R3]`
5. **不原地修改调用方传入的容器**，需要修改时返回新容器。`[R1]`

## 5. 最佳编码建议

- **docstring 第一行是简短摘要、首字母大写、句末句号**；多行时第二行留空。`[R2]`
- **类型比较用 `isinstance()`，与 `None` 比较用 `is None`**。`[R3]`
- **注释解释「为什么」**，不重复代码；`[R3]`
- **显式优于隐式、失败要快**：非法参数立即报错，不返回模糊的哨兵值（第 01 章约定）。
- **命名表达意图**，禁止 `data` / `temp` / `obj` 占位名（第 01 章约定）。

## 6. 编码示例

### 6.1 可运行脚本

`examples/function_demo.py`：

```python
"""第 05 章示例：函数定义、参数与返回值。"""

def build_report(tool_name, results, limit=3):
    """返回工具结果摘要；limit 控制保留条数。"""
    selected = results[:limit]
    return {"tool": tool_name, "count": len(selected), "items": selected}

def append_result(item, collected=None):
    """默认值为 None，避免可变默认值在多次调用间共享 [R1]。"""
    if collected is None:
        collected = []
    collected.append(item)
    return collected

print("报告:", build_report("search", ["a", "b", "c", "d"]))
print("关键字参数:", build_report(results=["x"], tool_name="cache", limit=1))
print("第一次:", append_result("a"))
print("第二次:", append_result("b"))
```

运行（先切到本章目录）：

```powershell
cd 'E:\ai-agent-study\py-base\01-函数与作用域\05-函数'
python examples/function_demo.py
```

关键输出：两次 `append_result` 分别得到 `['a']`、`['b']` 而非累积，因为默认值是 `None`、每次在函数内新建列表。`[R1]`

### 6.2 对照反例（只在 REPL 里观察，不要写进项目）

```python
def bad(item, collected=[]):
    collected.append(item)
    return collected
```

连续调用两次会累积，官方原文用这个例子说明默认值只求值一次。`[R1]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org · **已核对** | https://docs.python.org/3.12/tutorial/controlflow.html | `def`、docstring、`return` / `None`、参数按对象引用传递、默认值只求值一次与 `L=None` 正解、关键字参数、`*args` / `**kwargs`、`/` 与 `*`、函数注解、`lambda` |
| `[R2]` | PEP 官方 · 未直连核对 | https://peps.python.org/pep-0257/ | docstring 首行摘要、多行留空行、公共函数应写 docstring |
| `[R3]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | 不用 lambda 绑定名字、返回一致性、`isinstance()` / `is None`、命名约定 |

## 8. 毕业自查清单

- [ ] 能说清「参数值是对象引用」导致的原地修改可见性
- [ ] 能解释可变默认值为什么会跨调用累积，并写出 `None` 兜底版本
- [ ] 能说明 `return` 缺省时返回什么、docstring 首行怎么写
- [ ] 能说出 `*args` / `**kwargs` 与 `/`、`*` 各自的作用
- [ ] 能运行 `examples/function_demo.py` 并解释两次调用为何不累积

## 9. 下一章衔接

第 06 章 `作用域`：函数创建了新的局部符号表，但名字究竟怎么查找、何时需要 `global` / `nonlocal`、闭包为何能记住外层变量，下一章展开。
