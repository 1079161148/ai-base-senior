"""服务层单测：不启动 HTTP、不建 app，直接验业务规则。"""

import pytest

from app.core.exceptions import DuplicateTitle, NotFound
from app.services.note_service import NoteService


def test_create(service: NoteService) -> None:
    note = service.create(title="标题", body="正文")

    assert note["title"] == "标题"
    assert note["pinned"] is False


def test_duplicate_title_raises(service: NoteService) -> None:
    service.create(title="重复")

    with pytest.raises(DuplicateTitle) as exc:
        service.create(title="重复")
    assert exc.value.status_code == 409


def test_missing_raises(service: NoteService) -> None:
    with pytest.raises(NotFound):
        service.get(999)


def test_update_keeps_other_fields(service: NoteService) -> None:
    service.create(title="原标题", body="原正文")
    updated = service.update(1, body="新正文")

    assert updated["body"] == "新正文"
    assert updated["title"] == "原标题"


def test_update_to_existing_title_raises(service: NoteService) -> None:
    service.create(title="A")
    service.create(title="B")

    with pytest.raises(DuplicateTitle):
        service.update(2, title="A")


def test_toggle_pin(service: NoteService) -> None:
    service.create(title="置顶我")

    assert service.toggle_pin(1)["pinned"] is True
    assert service.toggle_pin(1)["pinned"] is False


def test_list_orders_pinned_first(service: NoteService) -> None:
    service.create(title="普通")
    service.create(title="要置顶")
    service.toggle_pin(2)

    rows, total = service.list(page=1, size=10)

    assert total == 2
    assert [row["title"] for row in rows] == ["要置顶", "普通"]