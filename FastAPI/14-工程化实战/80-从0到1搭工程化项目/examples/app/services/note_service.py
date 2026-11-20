"""积木 7 · 服务层：业务规则集中在这里，唯一的「决策者」。

【原则】这一层可以 import `repositories` 和 `core.exceptions`，
        **禁止** import `fastapi` 与 `sqlite3`——业务与框架解耦，才能单测。
"""

from typing import Any

from app.core.exceptions import DuplicateTitle, NotFound
from app.repositories.note_repo import NoteRepo


class NoteService:
    def __init__(self, repo: NoteRepo) -> None:
        self.repo = repo

    def create(self, *, title: str, body: str = "") -> dict[str, Any]:
        if self.repo.exists_title(title):
            raise DuplicateTitle(title)
        return self.repo.create(title=title, body=body)

    def get(self, note_id: int) -> dict[str, Any]:
        note = self.repo.get(note_id)
        if note is None:
            raise NotFound("笔记", note_id)
        return note

    def list(
        self,
        *,
        page: int,
        size: int,
        pinned: bool | None = None,
        q: str | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        return self.repo.list(limit=size, offset=(page - 1) * size, pinned=pinned, q=q)

    def update(self, note_id: int, **fields: Any) -> dict[str, Any]:
        title = fields.get("title")
        if title:
            if self.repo.exists_title(title, exclude_id=note_id):
                raise DuplicateTitle(title)
        note = self.repo.update(note_id, **fields)
        if note is None:
            raise NotFound("笔记", note_id)
        return note

    def toggle_pin(self, note_id: int) -> dict[str, Any]:
        """业务动作：置顶/取消置顶，端点不需要知道当前状态"""
        note = self.get(note_id)
        return self.update(note_id, pinned=not note["pinned"])

    def delete(self, note_id: int) -> None:
        if not self.repo.delete(note_id):
            raise NotFound("笔记", note_id)