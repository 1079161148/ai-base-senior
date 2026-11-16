# 18 上下文管理器

> 承接第 17 章：生成器持有资源时必须保证释放，`with` 就是标准答案。本章也是 Agents 里管理连接、会话、临时状态的必备工具。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 14、16、17 章（特殊方法、异常、生成器） |
| 本章目标 | `with` 协议、`__enter__` / `__exit__`、`contextlib.contextmanager`、异常抑制 |
| 毕业标准 | 能说出 `__exit__` 三个参数；能解释返回 `True` 会怎样；能用生成器写上下文管理器 |
| 编码要求 | 能运行 `examples/context_demo.py` 并解释「进入 / 会话 / 退出」顺序 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节；「未直连核对」的链接按官方文档通行表述整理。

## 1. 概念

- `with expr as var:` 在语句体前调用 `__enter__()`，把返回值绑到 `var`；无论正常还是异常退出，都调用 `__exit__(exc_type, exc_value, traceback)`。`[R1]` `[R2]`
- `__exit__` 返回**真值**会抑制异常（吞掉它）；返回 `None` / `False` 则异常继续传播。**抑制要极其克制**。`[R1]`
- `contextlib.contextmanager` 把「带单个 `yield` 的生成器」变成上下文管理器：`yield` 前是进入逻辑，`finally` 里是退出逻辑。`[R3]`
- 标准库常见实现：`open()` 文件、`threading.Lock`、`contextlib.suppress` / `redirect_stdout`、`asyncio` 的异步上下文管理器（第 27 章）。`[R3]`
- `with` 可同时管理多个上下文，从左到右进入、从右到左退出。`[R2]`
- PEP 8 明确：局部资源用 `with` 保证及时可靠清理，优于手写 `try/finally`。`[R4]`

## 2. 注意事项

1. **不要随手在 `__exit__` 返回 `True`**，会静默吞掉错误（第 01 章禁止静默失败）。`[R1]`
2. **`@contextmanager` 函数里只能 `yield` 一次**。`[R3]`
3. **退出逻辑必须放 `finally`**，否则异常时不会执行。`[R3]`
4. **`with conn:` 语义不透明时改用显式方法**（如 `conn.begin_transaction()`），PEP 8 有明确建议。`[R4]`
5. **别在 `__enter__` 里做隐藏的重副作用**。

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 异常传播 | 返回 `True` 抑制、返回假值传播；生成器版靠 `try/except` 控制 | `[R1]` `[R3]` |
| 异步 | 异步资源需 `async with` / `__aenter__`（第 27 章） | `[R3]` |
| 嵌套顺序 | 多上下文按「后进先出」退出 | `[R2]` |
| 生成器资源 | 第 17 章的惰性流要与 `with` 组合，保证消费完释放 | `[R3]` |

## 4. 最佳实践

1. **所有局部资源优先 `with`**，不手写 `try/finally`。`[R4]`
2. **简单场景用 `@contextmanager`**，复杂状态/可复用用类实现。`[R3]`
3. **退出逻辑写进 `finally`**，并注释清理了什么。
4. **让异常正常传播**，只在明确知道要忽略时 `contextlib.suppress(具体异常)`。`[R3]`

## 5. 最佳编码建议

- **命名表达意图**：`tool_session`，不用 `ctx1`。`[R4]`
- **注释解释「为什么需要这个上下文」**。`[R4]`
- **不吞异常、不丢上下文**（第 01 章）。
- **配置与凭据走环境变量**（第 01 章）。

## 6. 编码示例

`examples/context_demo.py`：

```python
"""第 18 章示例：with 与 contextlib.contextmanager。"""

import contextlib

@contextlib.contextmanager
def tool_session(name):
    """进入/退出时打印，清理逻辑放 finally [R3]。"""
    print("进入:", name)
    try:
        yield {"tool": name}
    finally:
        print("退出:", name)

with tool_session("search") as session:
    print("会话:", session)
```

运行：

```powershell
cd 'E:\ai-agent-study\py-base\04-异常与核心协议\18-上下文管理器'
python examples/context_demo.py
```

关键输出顺序：`进入: search` → `会话: {'tool': 'search'}` → `退出: search`，`finally` 保证退出逻辑执行。`[R1]` `[R3]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org · 未直连核对 | https://docs.python.org/3.12/reference/datamodel.html | `__enter__` / `__exit__` 协议与异常抑制 |
| `[R2]` | python.org · 未直连核对 | https://docs.python.org/3.12/reference/compound_stmts.html | `with` 语句语义、多上下文进入/退出顺序 |
| `[R3]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/contextlib.html | `@contextmanager`、`suppress`、异步上下文管理器、`ExitStack` |
| `[R4]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | 局部资源用 `with`、上下文管理器应通过单独方法表达语义、命名与注释 |

## 8. 毕业自查清单

- [ ] 能说出 `with` 进入与退出各调用什么方法
- [ ] 能解释 `__exit__` 返回 `True` 的后果与风险
- [ ] 能用 `@contextmanager` 写出一个上下文管理器
- [ ] 能说出 `with` 相比手写 `try/finally` 的优势
- [ ] 能运行 `examples/context_demo.py` 并解释三行顺序

## 9. 下一章衔接

第 20 章 `类型标注`：核心协议讲完，进入工程化——先给函数与容器加上类型标注，再在第 21 章讲模块化、22 标准库、23 第三方库。
