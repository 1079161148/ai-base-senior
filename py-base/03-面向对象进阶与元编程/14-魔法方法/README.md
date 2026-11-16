# 14 魔法方法

> 承接第 13 章：装饰器改的是「函数对象」，本章往下一层，讲 Python 用 `__xxx__` 协议把运算符、容器行为、字符串表示交给用户类实现。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 08–13 章（类、创建、可调用、装饰器） |
| 本章目标 | 常用特殊方法、协议与鸭子类型、`__str__` / `__repr__`、比较与哈希、容器协议 |
| 毕业标准 | 能说出 `len(obj)` 背后调什么；能解释为什么实现 `__eq__` 后 `__hash__` 会变 |
| 编码要求 | 能运行 `examples/magic_demo.py` 并解释为什么 `ToolBatch` 可以被迭代 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节；「未直连核对」的链接按官方文档通行表述整理。

## 1. 概念

- 特殊方法（dunder）由解释器在特定语法下**隐式调用**：`len(x)` → `type(x).__len__(x)`，`x[i]` → `__getitem__`，`x + y` → `__add__`。用户代码不应直接调用它们。`[R1]`
- 常用分组 `[R1]`：
  - 表示：`__str__`（给人看）、`__repr__`（给开发者/调试看，应尽可能无歧义）、`__format__`
  - 容器：`__len__`、`__getitem__`、`__setitem__`、`__contains__`、`__iter__`（第 17 章）
  - 比较与哈希：`__eq__` / `__ne__` / `__lt__` 等、`__hash__`
  - 属性访问：`__getattr__` / `__getattribute__` / `__setattr__`（与第 15 章描述符配合）
  - 生命周期与资源：`__enter__` / `__exit__`（第 18 章）、`__call__`（第 11 章）
- 定义了 `__eq__` 但没定义 `__hash__` 时，实例默认**不可哈希**；这是为了维持「相等对象哈希值相等」的契约。`[R1]`
- 只实现 `__getitem__` 且索引从 0 开始，对象也能被 `for` 迭代（旧式迭代协议回退）；显式 `__iter__` 更清晰。`[R1]`
- PEP 8 建议：实现排序比较时把六个比较操作都补齐，或用 `functools.total_ordering`。`[R2]`

## 2. 注意事项

1. **不要手写 `obj.__len__()`**，用 `len(obj)`。`[R1]`
2. **`__repr__` 面向调试**，`__str__` 面向展示，别混为一谈。`[R1]`
3. **可变对象别实现 `__hash__`**，否则做 dict 键会出错。`[R1]`
4. **`__getattr__` 只在找不到属性时触发**，`__getattribute__` 每次都触发，别滥用。
5. **不要发明新的 `__xxx__` 名字**，它们保留给语言机制。`[R2]`
6. **`__eq__` 要处理类型不匹配**，返回 `NotImplemented` 让对方尝试，而不是直接 `False`。`[R1]`

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 隐式调用绕过实例字典 | 特殊方法在**类型**上查找，给实例塞同名属性无效 | `[R1]` |
| 哈希契约 | 相等必须哈希相等；可变 + 可哈希是危险组合 | `[R1]` |
| 反射与运算符 | 右侧运算有 `__radd__` 等反射版本 | `[R1]` |
| 性能 | `__getattribute__` 在每次属性访问路径上，加逻辑要谨慎 | `[R1]` |

## 4. 最佳实践

1. **优先实现少量协议**（`__len__` + `__getitem__`），不要为了「完整」堆方法。`[R1]`
2. **用 `@dataclass` 生成样板方法**（第 13 章）。
3. **排序类补齐六个比较或用 `total_ordering`**。`[R2]`
4. **把特殊方法的行为写进类 docstring**，因为它们不在调用点显形。
5. **资源类优先实现上下文管理器**（第 18 章）而不是依赖 `__del__`。

## 5. 最佳编码建议

- **特殊方法只做协议要求的事**，不塞业务逻辑。
- **注释解释「为什么实现这个协议」**。`[R2]`
- **命名表达意图、显式优于隐式**（第 01 章）。
- **失败要快**：非法索引抛 `IndexError` 等标准异常（第 16 章）。

## 6. 编码示例

`examples/magic_demo.py`：

```python
"""第 14 章示例：__len__ / __getitem__ / __str__。"""

class ToolBatch:
    """一组工具名，支持 len、索引与迭代。"""
    def __init__(self, names):
        self.names = list(names)

    def __len__(self):
        return len(self.names)

    def __getitem__(self, index):
        return self.names[index]

    def __str__(self):
        return "ToolBatch(" + ",".join(self.names) + ")"

batch = ToolBatch(["search", "cache"])
print("长度:", len(batch))
print("索引:", batch[0])
print("迭代:", [name for name in batch])
print("字符串:", str(batch))
```

运行：

```powershell
cd 'E:\ai-agent-study\py-base\03-面向对象进阶与元编程\14-魔法方法'
python examples/magic_demo.py
```

关键输出：`长度: 2`、`索引: search`、`迭代: ['search', 'cache']`——`for` 能工作是因为 `__getitem__` 提供了迭代回退。`[R1]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org · 未直连核对 | https://docs.python.org/3.12/reference/datamodel.html | 特殊方法查找规则、表示/容器/比较/哈希/属性访问协议、`NotImplemented`、旧式迭代回退 |
| `[R2]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | 补齐六个比较操作、不发明 dunder、注释写「为什么」、`isinstance()` |

## 8. 毕业自查清单

- [ ] 能说出 `len(x)`、`x[i]`、`x + y` 各自触发哪个特殊方法
- [ ] 能解释特殊方法为什么在类型上查找而非实例字典
- [ ] 能说出实现 `__eq__` 后哈希发生什么变化
- [ ] 能解释 `__str__` 与 `__repr__` 的受众差别
- [ ] 能运行 `examples/magic_demo.py` 并解释迭代为什么能工作

## 9. 下一章衔接

第 15 章 `描述符`：属性访问背后的真正机制——`property`、`staticmethod`、`classmethod` 与方法绑定都建立在描述符协议上；随后 19 ABC 与 12 元类。
