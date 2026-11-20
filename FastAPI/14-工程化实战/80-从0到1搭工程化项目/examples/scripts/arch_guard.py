"""架构守卫：分层依赖方向的唯一事实来源。

`tests/test_architecture.py` 与 `verify.py` 都调用这里的 `violations()`，
避免「测试里一套规则、验收里另一套规则」。

跑法：uv run python scripts/arch_guard.py
"""

import ast
import sys
from pathlib import Path

APP_DIR = Path(__file__).parent.parent / "app"

# 层 → 禁止 import 的模块前缀
# 【原则】依赖只能由外向内：api → services → repositories → db
FORBIDDEN: dict[str, tuple[str, ...]] = {
    "schemas": ("fastapi", "starlette", "sqlite3", "app.api", "app.services", "app.repositories", "app.db", "app.core"),
    "repositories": ("fastapi", "starlette", "app.api", "app.services"),
    "services": ("fastapi", "starlette", "sqlite3", "app.api"),
    "core": ("app.api", "app.services", "app.repositories", "app.db"),
    "db": ("app.api", "app.services", "app.repositories"),
}


def _layer_of(path: Path) -> str | None:
    parts = path.relative_to(APP_DIR).parts
    return parts[0] if len(parts) > 1 else None


def _imports(path: Path) -> set[str]:
    # utf-8-sig：Windows 编辑器可能写入 BOM，ast.parse 不接受 U+FEFF
    tree = ast.parse(path.read_text(encoding="utf-8-sig"), filename=str(path))
    found: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            found.update(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
    return found


def violations(app_dir: Path = APP_DIR) -> list[str]:
    problems: list[str] = []
    for path in sorted(app_dir.rglob("*.py")):
        layer = _layer_of(path)
        if layer not in FORBIDDEN:
            continue
        banned = FORBIDDEN[layer]
        for module in _imports(path):
            for prefix in banned:
                # 精确匹配，避免 `app.apix` 之类误伤
                if module == prefix or module.startswith(prefix + "."):
                    problems.append(f"{path.relative_to(app_dir)}: {layer} 不允许 import {module}")
    return problems


def main() -> int:
    problems = violations()
    for problem in problems:
        print("[VIOLATION]", problem)
    print(f"\n{len(problems)} 处违规" if problems else "\n分层依赖全部合法")
    return 1 if problems else 0


if __name__ == "__main__":
    raise SystemExit(main())