"""种子数据：本地开发用，走服务层而不是直接 INSERT。

跑法：uv run python scripts/seed.py
"""

import sqlite3
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.config import get_settings  # noqa: E402
from app.db.migrate import migrate  # noqa: E402
from app.repositories.note_repo import NoteRepo  # noqa: E402
from app.services.note_service import NoteService  # noqa: E402

SEEDS = [
    ("第一次搭骨架", "先让 /healthz 返回 200，再谈别的"),
    ("配置外置", "任何字面量都不该出现在业务代码里"),
    ("写完就跑验收", "verify.py 是唯一可信的完成标准"),
]


def main() -> None:
    settings = get_settings()
    print("migrated:", migrate(settings))
    # 脚本不是请求，直接管理连接；不要在脚本里复用 `get_conn` 这个生成器依赖
    with sqlite3.connect(settings.db_path) as conn:
        conn.row_factory = sqlite3.Row
        service = NoteService(NoteRepo(conn))
        for title, body in SEEDS:
            try:
                service.create(title=title, body=body)
                print("created:", title)
            except Exception as exc:  # 重复执行 seed 时跳过已存在的
                print("skipped:", title, type(exc).__name__)


if __name__ == "__main__":
    main()