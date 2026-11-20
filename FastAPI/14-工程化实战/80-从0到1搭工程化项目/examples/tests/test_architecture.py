"""架构守卫：分层依赖方向错了就让测试红。"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.db.migrate import applied_versions, migrate  # noqa: E402
from scripts.arch_guard import violations  # noqa: E402


def test_layers_do_not_leak() -> None:
    problems = violations()

    assert problems == [], "\n".join(problems)


def test_migrations_are_idempotent(tmp_path: Path) -> None:
    settings = get_settings()
    settings.db_path = str(tmp_path / "m.db")

    first = migrate(settings)
    second = migrate(settings)

    assert first == ["0001_init", "0002_add_pinned"], first
    assert second == [], second
    assert applied_versions(settings) == first