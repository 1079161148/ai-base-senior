"""第 31 章示例：monorepo 包布局与依赖方向（只读示意）。"""

import pathlib

packages = ["agent-tools", "agent-core", "agent-cli"]
for name in packages:
    marker = pathlib.PurePath("packages", name, "pyproject.toml")
    print("包路径:", marker.as_posix())

dependencies = {
    "agent-cli": ["agent-core"],
    "agent-core": ["agent-tools"],
    "agent-tools": [],
}
for name, deps in dependencies.items():
    print(name, "->", deps)
