"""第 23 章示例：只读查看已安装的包元数据。"""

import importlib.metadata

for name in ["pip", "setuptools", "definitely-not-installed"]:
    try:
        print(name, "版本:", importlib.metadata.version(name))
    except importlib.metadata.PackageNotFoundError:
        print(name, "未安装")
