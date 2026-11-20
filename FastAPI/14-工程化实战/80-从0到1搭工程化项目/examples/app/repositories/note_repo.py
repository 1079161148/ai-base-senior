"""积木 6 · 仓储层：只做 SQL，不认识 HTTP、也不认识业务规则。

【原则】这一层可以 import `sqlite3`，但**禁止** import `fastapi`。
        换 Postgres 时只改这个文件（以及 session.py）。
"""

import sqlite3
from datetime import UTC, datetime
from typing import Any


def _to_dict(row: sqlite3.Row) -> dict[str, Any]:
    return {
        "id": row["id"],
        "title": row["title"],
        "body": row["body"],
        "pinned": bool(row["pinned"]),
        "created_at": datetime.fromisoformat(row["created_at"]),
    }


class NoteRepo:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self.conn = conn

    def create(self, *, title: str, body: str = "") -> dict[str, Any]:
        cursor = self.conn.execute(
            "INSERT INTO notes (title, body, created_at) VALUES (?, ?, ?)",
            (title, body, datetime.now(UTC).isoformat()),
        )
        created = self.get(cursor.lastrowid)
        assert created is not None
        return created

    def get(self, note_id: int) -> dict[str, Any] | None:
        row = self.conn.execute("SELECT * FROM notes WHERE id = ?", (note_id,)).fetchone()
        return _to_dict(row) if row else None

    def exists_title(self, title: str, *, exclude_id: int | None = None) -> bool:
        sql = "SELECT 1 FROM notes WHERE title = ?"
        params: list[Any] = [title]
        if exclude_id is not None:
            sql += " AND id != ?"
            params.append(exclude_id)
        return self.conn.execute(sql + " LIMIT 1", params).fetchone() is not None

    def list(
        self,
        *,
        limit: int,
        offset: int,
        pinned: bool | None = None,
        q: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        clauses: list[str] = []
        params: list[Any] = []
        if pinned is not None:
            clauses.append("pinned = ?")
            params.append(int(pinned))
        if q:
            clauses.append("LOWER(title) LIKE ?")
            params.append(f"%{q.lower()}%")
        where = f" WHERE {' AND '.join(clauses)}" if clauses else ""

        total = self.conn.execute(f"SELECT COUNT(*) FROM notes{where}", params).fetchone()[0]
        rows = self.conn.execute(
            f"SELECT * FROM notes{where} ORDER BY pinned DESC, id ASC LIMIT ? OFFSET ?",
            (*params, limit, offset),
        ).fetchall()
        return [_to_dict(row) for row in rows], int(total)

    def update(self, note_id: int, **fields: Any) -> dict[str, Any] | None:
        sets: list[str] = []
        params: list[Any] = []
        for key in ("title", "body", "pinned"):
            value = fields.get(key)
            if value is None:
                continue
            sets.append(f"{key} = ?")  # key 来自白名单，不是用户输入
            params.append(int(value) if key == "pinned" else value)
        if not sets:
            return self.get(note_id)
        params.append(note_id)
        self.conn.execute(f"UPDATE notes SET {', '.join(sets)} WHERE id = ?", params)
        return self.get(note_id)

    def delete(self, note_id: int) -> bool:
        return self.conn.execute("DELETE FROM notes WHERE id = ?", (note_id,)).rowcount > 0