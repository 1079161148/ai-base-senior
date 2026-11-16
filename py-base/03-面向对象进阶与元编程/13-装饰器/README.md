# 13 装饰器

> 承接第 11 章：函数与可调用实例都是对象，装饰器就是「接收可调用对象、返回可调用对象」的函数。本章按认知顺序先于 14 / 15 / 19 / 12 章。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 05–07、11 章（函数、作用域、闭包、可调用对象） |
| 本章目标 | `@` 语法、无参/带参装饰器、`functools.wraps`、堆叠顺序、类装饰器 |
| 毕业标准 | 能手写日志装饰器；能解释为什么必须用 `wraps`；能说出多个装饰器的执行顺序 |
| 编码要求 | 能运行 `examples/decorator_demo.py` 并解释 `保留的函数名` 一行 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节；「未直连核对」的链接按官方文档通行表述整理。**本章为使用 `functools.wraps` 提前引入 `import`，模块化机制在第 21 章展开。**

## 1. 概念

- `@decorator` 写在函数定义前，等价于 `func = decorator(func)`；装饰器表达式在**函数定义时**求值。`[R1]` `[R2]`
- 装饰器本质：接收函数（或类）并返回新的可调用对象；常用闭包（第 06 章）保存状态。`[R2]`
- 多个装饰器**自下而上应用**：最靠近 `def` 的先执行，最上面的最后包装。`[R1]`
- 带参数的装饰器是「返回装饰器的函数」：`@retry(3)` 先调用 `retry(3)` 得到真正的装饰器。`[R2]`
- `functools.wraps` 把被包装函数的 `__name__` / `__doc__` / `__annotations__` 等元数据复制到 wrapper；不写它，调试与文档工具看到的全是 `wrapper`。`[R3]`
- 用 `*args, **kwargs` 透传参数，装饰器才不会破坏原函数签名（第 05 章）。`[R2]`
- 类装饰器接收类、返回类；`@dataclass` 是标准库中最常见的例子。`[R2]` `[R3]`

## 2. 注意事项

1. **总是用 `@functools.wraps(func)`**，否则元数据丢失。`[R3]`
2. **装饰器在导入时执行**，不要在里面做联网 / 读文件等副作用。
3. **`*args, **kwargs` 要原样透传**，还要 `return` 原函数结果。`[R2]`
4. **堆叠顺序容易搞反**，用日志验证一次再上生产。`[R1]`
5. **装饰器会改变可观测签名**，静态检查与 IDE 依赖 `wraps` / `ParamSpec`（第 20 章）。
6. **别在业务代码里写「自动注册一切」的隐式魔法**（第 01 章边界）。

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 签名与类型 | `wraps` 保留元数据但不改变底层签名，精确标注需 `ParamSpec`（第 20 章） | `[R3]` |
| 描述器交互 | 装饰方法时要注意描述符绑定（第 15 章） | `[R1]` |
| 异步函数 | 普通同步 wrapper 会破坏 `async def`，需 `asyncio.iscoroutinefunction`（第 27 章） | `[R2]` |
| 可测试性 | 装饰器逻辑与被装饰逻辑应尽量分开测 | `[R2]` |
| 元类 | 类装饰器与元类都能改类，优先前者（更显式） | `[R1]` |

## 4. 最佳实践

1. **装饰器只做横切关注点**：日志、计时、重试、缓存、权限。`[R2]`
2. **优先用标准库现成实现**：`functools.lru_cache` / `cache`、`contextlib`、`dataclasses`。`[R3]`
3. **保持装饰器无状态或状态显式**，别用模块级可变全局（第 06 章）。
4. **失败要快**：重试装饰器要有上限与明确异常，不静默吞错（第 01 章）。
5. **给装饰器写 docstring**，说明它改变了哪些行为。

## 5. 最佳编码建议

- **`wrapper(*args, **kwargs)` 固定写法 + `return` 结果**。`[R2]`
- **命名表达意图**：`retry`、`log_call`，不要 `deco1`。`[R4]`
- **注释解释「为什么需要这层包装」**。`[R4]`
- **不硬编码重试次数 / 超时**，走参数或配置。
- **显式优于隐式**（第 01 章）。

## 6. 编码示例

`examples/decorator_demo.py`：

```python
"""第 13 章示例：最小装饰器与 functools.wraps。"""

import functools

def log_call(func):
    """记录被装饰函数的调用，并保留其元数据 [R3]。"""
    @functools.wraps(func)
    def wrapper(*args, **kwargs):
        print("调用:", func.__name__)
        return func(*args, **kwargs)
    return wrapper

@log_call
def search(query):
    """返回模拟搜索结果。"""
    return ["result:" + query]

print("结果:", search("AI news"))
print("保留的函数名:", search.__name__)
print("保留的文档:", search.__doc__)
```

运行：

```powershell
cd 'E:\ai-agent-study\py-base\03-面向对象进阶与元编程\13-装饰器'
python examples/decorator_demo.py
```

关键输出：`调用: search`、`结果: ['result:AI news']`、`保留的函数名: search`——最后一行证明 `wraps` 生效；去掉它就会变成 `wrapper`。`[R3]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org · 未直连核对 | https://docs.python.org/3.12/reference/compound_stmts.html | 函数/类定义的装饰器语法、`@` 等价形式、堆叠应用顺序 |
| `[R2]` | PEP 官方 · 未直连核对 | https://peps.python.org/pep-0318/ | 装饰器动机、语法决策、带参装饰器与类装饰器 |
| `[R3]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/functools.html | `wraps` 保留元数据、`lru_cache` / `cache`、`partial` |
| `[R4]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | 命名约定、注释写「为什么」、docstring |

## 8. 毕业自查清单

- [ ] 能写出 `@decorator` 的等价赋值形式
- [ ] 能说明多个装饰器的应用顺序
- [ ] 能解释不用 `wraps` 会丢哪些元数据
- [ ] 能说出装饰器适合与不适合做什么
- [ ] 能运行 `examples/decorator_demo.py` 并解释三行输出

## 9. 下一章衔接

第 14 章 `魔法方法`：装饰器包装的是可调用对象；再往下一层，Python 的运算符、迭代、属性访问都由 `__xxx__` 协议驱动，理解它才能读懂框架源码。
