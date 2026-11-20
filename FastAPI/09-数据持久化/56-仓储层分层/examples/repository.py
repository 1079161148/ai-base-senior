"""第 56 章 · 仓储层：**只有 SQL**，不含 HTTP、不含业务规则。

【判据】这里不该出现 HTTP 异常、状态码、请求对象；
        也不该出现「重名要拒绝」这类业务判断——那是 service 的事。
"""

import sqlite3

from models import Item


class ItemRepository:
    """【作用】把一个聚合的持久化操作收在一处，便于替换和测试"""

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
        cursor = self._conn.execute(
            "INSERT INTO items (name, price) VALUES (?, ?)", (name, price)
        )
        # 【要点】先在这里提交，保证跨请求可见；
        #         第 57 章会把它上移到依赖层，让「一次请求一个事务」成立
        self._conn.commit()
        return Item(id=int(cursor.lastrowid or 0), name=name, price=price)

    def delete(self, item_id: int) -> bool:
        cursor = self._conn.execute("DELETE FROM items WHERE id = ?", (item_id,))
        self._conn.commit()
        return cursor.rowcount > 0

    def count(self) -> int:
        return int(self._conn.execute("SELECT COUNT(*) FROM items").fetchone()[0])