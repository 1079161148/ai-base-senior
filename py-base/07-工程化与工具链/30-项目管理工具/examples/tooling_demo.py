"""第 30 章示例：只读检查本机可用的项目管理工具。"""

import shutil

for name in ["python", "pip", "uv", "poetry", "pdm", "hatch"]:
    print(name, "->", shutil.which(name) is not None)
