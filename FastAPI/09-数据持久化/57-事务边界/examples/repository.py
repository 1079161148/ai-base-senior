"""第 57 章 · 仓储层：只执行语句，**不提交事务**。

【要点】`commit` 由 `get_db` 统一负责，仓储才能被复用到同一个事务里
        （两次写要么都成功、要么都不落库）。
"""

import sqlite3

from models import Item


class ItemRepository:
    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def list_all(self) -> list[Item]:
        rows = self._conn.execute("SELECT id, name, price FROM items ORDER BY id").fetchall()
        return [Item(**dict(row)) for row in rows]

    def get(self, item_id: int) -> Item | None:
        row = self._conn.execute(
            "SELECT id, name, price FROM items WHERE id = ?", (item_id,)
        ).fetchone()
        return Item(**dict(row)) if row else None

    def find_by_name(self, name: str) -> Item | None:
        row = self._conn.execute(
            "SELECT id, name, price FROM items WHERE name = ?", (name,)
        ).fetchone()
        return Item(**dict(row)) if row else None

    def add(self, name: str, price: int) -> Item:
        """【注意】这里**没有** commit——事务由依赖统一收尾"""
        cursor = self._conn.execute(
            "INSERT INTO items (name, price) VALUES (?, ?)", (name, price)
        )
        return Item(id=int(cursor.lastrowid or 0), name=name, price=price)

    def add_audit(self, note: str) -> None:
        self._conn.execute("INSERT INTO audit (note) VALUES (?)", (note,))

    def audit_notes(self) -> list[str]:
        rows = self._conn.execute("SELECT note FROM audit ORDER BY id").fetchall()
        return [row["note"] for row in rows]