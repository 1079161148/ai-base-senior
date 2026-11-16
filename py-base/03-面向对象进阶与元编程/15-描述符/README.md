# 15 描述符

> 承接第 14 章：特殊方法解释了「语法如何映射到协议」，本章解释「属性访问到底怎么工作」——`property`、方法绑定、ORM 字段的共同底座。

| 项 | 内容 |
| --- | --- |
| 前置依赖 | 第 08、14 章（类、特殊方法） |
| 本章目标 | 描述符协议、数据描述符 / 非数据描述符、`property`、方法绑定、优先级 |
| 毕业标准 | 能说出属性查找优先级；能解释 `obj.method` 为什么自动带 `self` |
| 编码要求 | 能运行 `examples/descriptor_demo.py` 并解释 `写入` / `读取` 两行 |

## 0. 依据标注约定

本章 `` `[Rn]` `` 仅在本章有效，索引见第 7 节；「未直连核对」的链接按官方文档通行表述整理。

## 1. 概念

- 描述符是实现了 `__get__` / `__set__` / `__delete__` 中任一方法的对象，且**必须作为类属性**才生效。`[R1]` `[R2]`
- **数据描述符**（定义了 `__set__` 或 `__delete__`）优先于实例字典；**非数据描述符**（只有 `__get__`）会被实例字典中的同名键遮蔽。`[R1]`
- 属性查找大致顺序：数据描述符 → 实例 `__dict__` → 非数据描述符 / 类属性 → `__getattr__`。`[R1]`
- 函数是非数据描述符：它的 `__get__` 把实例绑成第一个参数，于是 `obj.method` 变成 bound method——这就是 `self` 的来源。`[R1]` `[R2]`
- `property` 是标准的数据描述符，把 getter / setter / deleter 包装成属性访问；`staticmethod` / `classmethod` 也是描述符。`[R2]` `[R3]`
- 描述符实例是**类属性**，状态要存到 `instance.__dict__` 或用 WeakKeyDictionary，不能存在描述符自身（否则所有实例共享）。`[R1]`

## 2. 注意事项

1. **描述符必须放在类上**，放进 `__init__` 的实例属性无效。`[R1]`
2. **别把每个实例的状态存在描述符自己的属性里**，会跨实例共享。`[R1]`
3. **`__get__(self, instance, owner)` 要处理 `instance is None`**（通过类访问时）。`[R1]`
4. **优先用 `property`，别手写描述符**；自研要有明确理由。`[R3]`
5. **`__getattribute__` 会绕过/影响描述符逻辑**，不要和描述符混着改。
6. **隐式状态变更难调试**（第 01 章），业务代码里克制使用。

## 3. 边界考虑

| 边界 | 说明 | 依据 |
| --- | --- | --- |
| 优先级 | 数据描述符 > 实例字典 > 非数据描述符，顺序决定遮蔽行为 | `[R1]` |
| 内存泄漏 | 用描述符自身 dict 存实例状态会强引用实例，考虑弱引用 | `[R2]` |
| 与 `__slots__` | slots 本身就是描述符，二者会冲突 | `[R1]` |
| 类型标注 | 描述符的泛型类型较复杂，见第 20 章 | `[R3]` |
| 元类 | 元类上的描述符影响类属性访问，见第 12 章 | `[R1]` |

## 4. 最佳实践

1. **需要受控属性访问时先用 `property`**。`[R3]`
2. **只在框架级复用逻辑时自研描述符**（校验、类型转换、ORM 字段）。`[R2]`
3. **状态按实例存储**，用 `instance.__dict__` 或弱引用容器。`[R1]`
4. **为描述符写清晰 docstring**，说明它何时触发。
5. **显式优于隐式**：能用普通方法说清就别用描述符（第 01 章）。

## 5. 最佳编码建议

- **命名表达意图**：`ValidatedString`，不用 `Desc1`。`[R4]`
- **注释解释「为什么用描述符而不是 property」**。`[R4]`
- **不吞异常、不静默失败**（第 16 章）。
- **不做预留扩展**（第 01 章）。

## 6. 编码示例

`examples/descriptor_demo.py`：

```python
"""第 15 章示例：一个最小数据描述符。"""

class Logged:
    """把值存在实例字典里，并打印读写 [R1]。"""
    def __get__(self, instance, owner):
        if instance is None:
            return self
        return instance.__dict__.get("_value")

    def __set__(self, instance, value):
        print("写入:", value)
        instance.__dict__["_value"] = value

class Tool:
    name = Logged()

tool = Tool()
tool.name = "search"
print("读取:", tool.name)
print("实例字典:", tool.__dict__)
```

运行：

```powershell
cd 'E:\ai-agent-study\py-base\03-面向对象进阶与元编程\15-描述符'
python examples/descriptor_demo.py
```

关键输出：`写入: search` → `读取: search` → `实例字典: {'_value': 'search'}`，证明状态存在实例而非描述符上。`[R1]`

## 7. 依据索引

| 编号 | 类型 / 核验状态 | 链接 | 支撑本章结论 |
| --- | --- | --- | --- |
| `[R1]` | python.org · 未直连核对 | https://docs.python.org/3.12/reference/datamodel.html | 描述符协议、数据/非数据描述符、属性查找优先级、函数绑定、`__slots__` |
| `[R2]` | python.org · 未直连核对 | https://docs.python.org/3.12/howto/descriptor.html | 描述符教程、状态存储、`property` / `staticmethod` / `classmethod` 的实现原理 |
| `[R3]` | python.org · 未直连核对 | https://docs.python.org/3.12/library/functions.html | `property` / `classmethod` / `staticmethod` 内置说明 |
| `[R4]` | PEP 官方 · **已核对** | https://peps.python.org/pep-0008/ | 命名约定、注释写「为什么」 |

## 8. 毕业自查清单

- [ ] 能说出数据描述符与非数据描述符的优先级差别
- [ ] 能解释 `obj.method` 为什么自动带 `self`
- [ ] 能说出描述符为什么必须定义在类上
- [ ] 能说出状态该存在哪里、为什么不能存在描述符自身
- [ ] 能运行 `examples/descriptor_demo.py` 并解释三行输出

## 9. 下一章衔接

第 19 章 `ABC`：描述符解决「属性怎么访问」，ABC 解决「接口怎么约束」；最后第 12 章 `元类` 才到「类怎么被创建」——这也是为什么大纲编号 12 要放到最后学。
