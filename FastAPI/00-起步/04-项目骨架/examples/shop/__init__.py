"""shop 包：第 04 章的项目骨架示例。

包（package）与模块的区别：目录里有 `__init__.py` 才是包，才能被 `import shop.xxx` 导入。
Python 3.3+ 有「隐式命名空间包」，没有 `__init__.py` 也能导入，
但**显式写 `__init__.py` 更可控**（能放版本号、能控制 `from shop import *` 的范围）。
"""

__version__ = "0.1.0"
