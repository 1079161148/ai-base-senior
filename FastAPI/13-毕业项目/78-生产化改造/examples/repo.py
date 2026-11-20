"""仓储层：所有 SQL 集中在这里。

【要点】`WHERE` 片段是**白名单拼接**（只在固定字符串里选），
        用户输入一律走 `?` 占位符，不存在注入面。
"""

import sqlite3
from datetime import UTC, datetime
from typing import Any

from models import Priority


def _to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "done": bool(row["done"]),
        "priority": Priority(row["priority"]),
        "created_at": datetime.fromisoformat(row["created_at"]),
    }


class TodoRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    # ---------------- 写 ----------------
    def create(self, title: str, priority: Priority) -> dict[str, Any]:
        cursor = self.conn.execute(
            "INSERT INTO todos (title, done, priority, created_at) VALUES (?, ?, ?, ?)",
            (title, 0, priority.value, datetime.now(UTC).isoformat()),
        )
        created = self.get(cursor.lastrowid)
        assert created is not None  # 刚插入的行一定存在
        return created

    def update(self, todo_id: int, **changes: Any) -> dict[str, Any] | None:
        fields: list[str] = []
        params: list[Any] = []
        for key in ("title", "done", "priority"):
            value = changes.get(key)
            if value is None:
                continue
            fields.append(f"{key} = ?")  # key 来自固定白名单，非用户输入
            params.append(value.value if isinstance(value, Priority) else int(value) if key == "done" else value)
        if not fields:
            return self.get(todo_id)
        params.append(todo_id)
        self.conn.execute(f"UPDATE todos SET {', '.join(fields)} WHERE id = ?", params)
        return self.get(todo_id)

    def delete(self, todo_id: int) -> bool:
        cursor = self.conn.execute("DELETE FROM todos WHERE id = ?", (todo_id,))
        return cursor.rowcount > 0

    # ---------------- 读 ----------------
    def get(self, todo_id: int) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM todos WHERE id = ?", (todo_id,)).fetchone()
        return _to_dict(row) if row else None

    def list(
        self,
        *,
        page: int,
        size: int,
        done: bool | None = None,
        priority: Priority | None = None,
        q: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        clauses: list[str] = []
        params: list[Any] = []
        if done is not None:
            clauses.append("done = ?")
            params.append(int(done))
        if priority is not None:
            clauses.append("priority = ?")
            params.append(priority.value)
        if q:
            clauses.append("LOWER(title) LIKE ?")
            params.append(f"%{q.lower()}%")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""

        total = self.conn.execute(f"SELECT COUNT(*) FROM todos{where}", params).fetchone()[0]
        rows = self.conn.execute(
            f"SELECT * FROM todos{where} ORDER BY id LIMIT ? OFFSET ?",
            (*params, size, (page - 1) * size),
        ).fetchall()
        return [_to_dict(row) for row in rows], int(total)

    def stats(self) -> dict[str, Any]:
        total = self.conn.execute("SELECT COUNT(*) FROM todos").fetchone()[0]
        done = self.conn.execute("SELECT COUNT(*) FROM todos WHERE done = 1").fetchone()[0]
        by_priority = {level.value: 0 for level in Priority}
        for row in self.conn.execute("SELECT priority, COUNT(*) AS n FROM todos GROUP BY priority"):
            by_priority[row["priority"]] = int(row["n"])
        return {
            "total": int(total),
            "done": int(done),
            "pending": int(total) - int(done),
            "by_priority": by_priority,
        }

    # ---------------- 测试辅助 ----------------
    def reset(self) -> None:
        self.conn.execute("DELETE FROM todos")
        self.conn.execute("DELETE FROM sqlite_sequence WHERE name = 'todos'")