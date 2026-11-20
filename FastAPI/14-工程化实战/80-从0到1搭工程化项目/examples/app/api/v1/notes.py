"""积木 10 · 端点层：只做「解析请求 → 调服务 → 组响应」。

一个端点超过 10 行，说明业务跑错层了。
"""

from typing import Annotated

from fastapi import APIRouter, Path, Query, Request, Response, status

from app.api.deps import PaginationDep, ServiceDep, Writer
from app.schemas.note import Note, NoteCreate, NoteUpdate, Page

router = APIRouter(prefix="/notes", tags=["笔记"])

NoteId = Annotated[int, Path(ge=1, description="笔记 ID")]


@router.get("", response_model=Page[Note], summary="分页列表")
def list_notes(
    service: ServiceDep,
    page_and_size: PaginationDep,
    pinned: Annotated[bool | None, Query(description="按置顶过滤")] = None,
    q: Annotated[str | None, Query(max_length=50, description="标题关键字")] = None,
) -> Page[Note]:
    page, size = page_and_size
    rows, total = service.list(page=page, size=size, pinned=pinned, q=q)
    return Page[Note](
        items=[Note.model_validate(row) for row in rows],
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
    )


@router.post("", response_model=Note, status_code=status.HTTP_201_CREATED, summary="新建")
def create_note(
    payload: NoteCreate,
    service: ServiceDep,
    user: Writer,
    request: Request,
    response: Response,
) -> Note:
    row = service.create(title=payload.title, body=payload.body)
    # 用真实请求路径拼，避免把 api_prefix 硬编码进端点
    response.headers["Location"] = f"{request.url.path}/{row['id']}"
    return Note.model_validate(row)


@router.get("/{note_id}", response_model=Note, summary="详情")
def read_note(note_id: NoteId, service: ServiceDep) -> Note:
    return Note.model_validate(service.get(note_id))


@router.patch("/{note_id}", response_model=Note, summary="部分更新")
def update_note(note_id: NoteId, payload: NoteUpdate, service: ServiceDep, user: Writer) -> Note:
    row = service.update(note_id, **payload.model_dump(exclude_unset=True))
    return Note.model_validate(row)


@router.post("/{note_id}/pin", response_model=Note, summary="切换置顶")
def toggle_pin(note_id: NoteId, service: ServiceDep, user: Writer) -> Note:
    return Note.model_validate(service.toggle_pin(note_id))


@router.delete("/{note_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除")
def delete_note(note_id: NoteId, service: ServiceDep, user: Writer) -> Response:
    service.delete(note_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)