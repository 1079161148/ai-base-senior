"""积木 3 · 迁移：按文件名顺序执行未应用过的 `.sql`，幂等。

    migrations/
    ├── 0001_init.sql
    └── 0002_add_pinned.sql

【原则】表结构只通过迁移改变，应用启动时自动 `migrate()`。
        手工改库是「本地能跑、上线就崩」的头号原因。
"""

import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from app.core.config import Settings

MIGRATIONS_DIR = Path(__file__).parent / "migrations"

TRACKING_TABLE = """
CREATE TABLE IF NOT EXISTS schema_migrations (
    version    TEXT PRIMARY KEY,
    applied_at TEXT NOT NULL
);
"""


def applied_versions(settings: Settings) -> list[str]:
    with sqlite3.connect(settings.db_path) as conn:
        conn.execute(TRACKING_TABLE)
        rows = conn.execute("SELECT version FROM schema_migrations ORDER BY version").fetchall()
    return [row[0] for row in rows]


def migrate(settings: Settings) -> list[str]:
    """返回本次新应用的版本号列表；重复调用返回空列表。"""
    applied: list[str] = []
    with sqlite3.connect(settings.db_path) as conn:
        conn.execute(TRACKING_TABLE)
        done = {row[0] for row in conn.execute("SELECT version FROM schema_migrations")}
        for path in sorted(MIGRATIONS_DIR.glob("*.sql")):
            version = path.stem
            if version in done:
                continue
            conn.executescript(path.read_text(encoding="utf-8"))
            conn.execute(
                "INSERT INTO schema_migrations (version, applied_at) VALUES (?, ?)",
                (version, datetime.now(UTC).isoformat()),
            )
            applied.append(version)
        conn.commit()
    return applied


if __name__ == "__main__":
    from app.core.config import get_settings as _get_settings

    print(migrate(_get_settings()))