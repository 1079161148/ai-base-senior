"""第 02 章示例：只读环境自检。

只用到 import sys、变量与 print()。本章不教语法：
import 机制在第 21 章、对象属性在第 08 章展开。

运行（在本章目录下）：
    python examples/check_env.py
"""

import sys

version_info = sys.version_info
interpreter_path = sys.executable
is_venv = sys.prefix != sys.base_prefix

print("Python 版本信息:", version_info)
print("解释器路径:", interpreter_path)
print("prefix:", sys.prefix)
print("base_prefix:", sys.base_prefix)
print("是否在虚拟环境中:", is_venv)
