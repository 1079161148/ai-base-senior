# 16 异常处理

> 承接模块 03：前面章节遇到错误都是让程序直接终止，本章开始系统地「预期并处理失败」——Agents 开发里模型超时、工具报错、格式不符都靠它兜住。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 05、13–15 章（函数、装饰器、协议） |
| 本章目标 | 异常层级、`try/except/else/finally`、`raise`、异常链、捕获粒度 |
| 毕业标准 | 能说出 `else` / `finally` 各自何时执行；能解释为什么不写裸 `except:` |
| 编码要求 | 能运行 `examples/exception_demo.py` 并解释三组输入的输出 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节；「未直连核对」的链接按官方文档通行表述整理。

## 1. 概念

- 异常是对象，按类层级组织；用户自定义异常应继承 `Exception`（而非 `BaseException`），错误类用 `Error` 后缀。`[R2]` `[R3]`
- `try` 块应**尽量小**；`except` 捕获具体异常，`else` 在**未抛异常**时执行，`finally` **无论是否异常**都执行（用于清理）。`[R1]` `[R3]`
- 裸 `except:` 等价于 `except BaseException:`，会连 `SystemExit` / `KeyboardInterrupt` 一起吞掉；PEP 8 要求捕获具体异常。`[R3]`
- `raise` 重新抛出当前异常；`raise X from Y` 显式保留原因形成异常链，`raise X from None` 抑制上下文但要手动转移关键信息。`[R3]`
- 异常层级应按「捕获方关心的错误种类」设计，而不是按抛出位置；`[R3]`
- 不要捕获后抛更模糊的异常，会丢失上下文（第 01 章）。

## 2. 注意事项

1. **不写裸 `except:`、不静默 `pass`**。`[R3]`
2. **`except` 顺序从具体到一般**，否则子类分支永远命中不到。`[R1]`
3. **`try` 越短越好**，否则会误捕获 `else` 处理函数抛出的同类异常。`[R3]`
4. **`finally` 里不要 `return` / `break`**，会隐式取消正在传播的异常。`[R3]`
5. **不要用异常做正常控制流**（能用返回值/状态表达时用返回值，第 01 章）。
6. **异常消息要可操作**：说明原因 + 下一步（第 01 章）。

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 系统退出 | `SystemExit` / `KeyboardInterrupt` 继承 `BaseException`，通常不该被捕获 | `[R2]` `[R3]` |
| 资源管理 | `finally` 可用，但 `with` 更可靠（第 18 章） | `[R3]` |
| 异常与生成器 | 生成器内 `StopIteration` 有专门规则（第 17 章） | `[R2]` |
| 并发 | 子线程/任务里的异常不会自动冒泡到主线程（第 25 / 28 章） | `[R2]` |
| 日志 | 不把堆栈与敏感数据直接返回最终用户（第 01 章） | `[R3]` |

## 4. 最佳实践

1. **先缩小 `try`，再写具体 `except`，最后用 `finally`/`with` 清理**。`[R3]`
2. **边界层统一翻译异常**：把第三方库异常转成应用异常并保留 `from`。
3. **重试要有次数上限与明确异常类型**，不吞错（第 13 章）。
4. **记录日志时保留 traceback**，面向用户只给可操作提示。
5. **失败要快**：非法状态立即抛异常（第 01 章）。

## 5. 最佳编码建议

- **异常类名 `XxxError`，继承 `Exception`**。`[R3]`
- **`with` 优先于 `try/finally`** 管理资源。`[R3]`
- **注释解释「为什么在这里捕获/重试」**。`[R3]`
- **不暴露内部堆栈给最终用户**（第 01 章）。

## 6. 编码示例

`examples/exception_demo.py`：

```python
"""第 16 章示例：try/except/else/finally 与具体异常。"""

def parse_limit(value):
    """把字符串转为正整数；非法输入抛 ValueError [R1]。"""
    number = int(value)
    if number <= 0:
        raise ValueError("limit 必须为正数")
    return number

for raw in ["5", "0", "abc"]:
    try:
        limit = parse_limit(raw)
    except ValueError as error:
        print("输入无效:", raw, "->", type(error).__name__)
    else:
        print("解析成功:", limit)
    finally:
        print("清理:", raw)
```

运行：

```powershell
cd 'E:\ai-agent-study\py-base\04-异常与核心协议\16-异常处理'
python examples/exception_demo.py
```

关键输出：`5` 走 `else` 打印解析成功，`0` 与 `abc` 走 `except ValueError`，三组都打印「清理」——`finally` 无条件执行。`[R1]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org · 未直连核对 | https://docs.python.org/3.12/tutorial/errors.html | `try/except/else/finally`、`raise`、用户异常、异常链 |
| `[R2]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/exceptions.html | 异常层级、`BaseException` / `Exception`、`ValueError` / `TypeError` / `StopIteration` |
| `[R3]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | 具体 `except`、缩小 `try`、`raise X from Y`、`with` 优先、`finally` 不放 return、异常命名 |

## 8. 毕业自查清单

- [ ] 能说出 `else` 与 `finally` 的触发条件差别
- [ ] 能解释裸 `except:` 为什么危险
- [ ] 能说出 `raise X from Y` 的作用
- [ ] 能说出 `try` 块为什么要尽量小
- [ ] 能运行 `examples/exception_demo.py` 并解释三组输出

## 9. 下一章衔接

第 17 章 `迭代器与生成器`：`for` 背后的迭代协议、`yield` 惰性产出、流式输出为何依赖生成器；随后第 18 章 `上下文管理器`。
