"""内存仓库：只负责数据存取，不关心 HTTP。

【要点】分页与过滤放在仓库层，端点只做参数解析与编排。
        真实项目换成 SQL 时，替换本文件即可，端点不用动。
"""

import threading
from datetime import UTC, datetime
from typing import Any

from models import Priority


class TodoStore:
    def __init__(self) -> None:
        self._items: dict[int, dict[str, Any]] = {}
        self._next_id = 1
        # 【要点】TestClient/线程池会并发进端点，内存 dict 必须加锁
        self._lock = threading.Lock()

    # ---------------- 生命周期 ----------------
    def reset(self, seed: bool = True) -> None:
        with self._lock:
            self._items.clear()
            self._next_id = 1
        if seed:
            self.create("写第 77 章代码", priority=Priority.high, done=False)
            self.create("跑一遍 verify.py", priority=Priority.medium, done=True)
            self.create("整理复盘笔记", priority=Priority.low, done=False)

    # ---------------- 写 ----------------
    def create(self, title: str, priority: Priority = Priority.medium, done: bool = False) -> dict[str, Any]:
        with self._lock:
            item = {
                "id": self._next_id,
                "title": title,
                "done": done,
                "priority": priority,
                "created_at": datetime.now(UTC),
            }
            self._items[self._next_id] = item
            self._next_id += 1
            return dict(item)

    def update(self, todo_id: int, **changes: Any) -> dict[str, Any] | None:
        with self._lock:
            item = self._items.get(todo_id)
            if item is None:
                return None
            for key, value in changes.items():
                if value is not None:
                    item[key] = value
            return dict(item)

    def delete(self, todo_id: int) -> bool:
        with self._lock:
            return self._items.pop(todo_id, None) is not None

    # ---------------- 读 ----------------
    def get(self, todo_id: int) -> dict[str, Any] | None:
        with self._lock:
            item = self._items.get(todo_id)
            return dict(item) if item else None

    def list(
        self,
        *,
        page: int,
        size: int,
        done: bool | None = None,
        priority: Priority | None = None,
        q: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        with self._lock:
            rows = list(self._items.values())

        # 过滤顺序无影响，但统一在内存里做，避免端点里散落 if
        if done is not None:
            rows = [row for row in rows if row["done"] is done]
        if priority is not None:
            rows = [row for row in rows if row["priority"] == priority]
        if q:
            needle = q.lower()
            rows = [row for row in rows if needle in row["title"].lower()]

        # 【要点】按 id 升序，保证分页稳定（dict 顺序在 Python 3.7+ 才可靠，但别依赖）
        rows.sort(key=lambda row: row["id"])
        total = len(rows)
        start = (page - 1) * size
        return [dict(row) for row in rows[start : start + size]], total

    def stats(self) -> dict[str, Any]:
        with self._lock:
            rows = list(self._items.values())
        by_priority = {level.value: 0 for level in Priority}
        for row in rows:
            by_priority[row["priority"].value] += 1
        done = sum(1 for row in rows if row["done"])
        return {
            "total": len(rows),
            "done": done,
            "pending": len(rows) - done,
            "by_priority": by_priority,
        }


# 单例：本章不引入 DI 容器，第 78 章改成依赖注入
store = TodoStore()