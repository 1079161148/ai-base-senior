"""第 29 章示例：只读解析 pyproject 元数据。"""

import tomllib

document = """
[project]
name = "agent-tools"
version = "0.1.0"
requires-python = ">=3.12"
"""
metadata = tomllib.loads(document)
print("项目名:", metadata["project"]["name"])
print("版本:", metadata["project"]["version"])
print("Python 要求:", metadata["project"]["requires-python"])
