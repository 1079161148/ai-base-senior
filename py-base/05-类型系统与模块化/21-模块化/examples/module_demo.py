"""第 21 章示例：模块、导入与 __name__。"""

import os
import sys

print("模块名:", __name__)
print("入口判断:", __name__ == "__main__")
print("os 来自:", os.__file__)
print("搜索路径首项:", sys.path[0])
