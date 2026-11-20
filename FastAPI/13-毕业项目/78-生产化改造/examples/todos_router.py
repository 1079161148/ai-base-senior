"""待办资源路由（依赖注入版）。

与第 77 章的区别：不再 import 全局 `store`，一切都从 `Depends` 进来。
"""

from typing import Annotated

from fastapi import APIRouter, Path, Response, status

from deps import FilterDep, PaginationDep, RepoDep, Writer
from errors import AppError
from models import Page, Priority, Stats, Todo, TodoCreate, TodoUpdate

router = APIRouter(prefix="/todos", tags=["待办"])

TodoId = Annotated[int, Path(ge=1, description="待办 ID")]


@router.get("", response_model=Page[Todo], summary="分页列表")
def list_todos(repo: RepoDep, page_and_size: PaginationDep, filters: FilterDep) -> Page[Todo]:
    page, size = page_and_size
    rows, total = repo.list(page=page, size=size, **filters)  # type: ignore[arg-type]
    return Page[Todo](
        items=[Todo.model_validate(row) for row in rows],
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size,
    )


@router.get("/stats", response_model=Stats, summary="统计")
def read_stats(repo: RepoDep) -> Stats:
    return Stats.model_validate(repo.stats())


@router.post("", response_model=Todo, status_code=status.HTTP_201_CREATED, summary="新建")
def create_todo(payload: TodoCreate, repo: RepoDep, user: Writer, response: Response) -> Todo:
    row = repo.create(payload.title, payload.priority)
    response.headers["Location"] = f"/api/v1/todos/{row['id']}"
    return Todo.model_validate(row)


@router.get("/{todo_id}", response_model=Todo, summary="详情")
def read_todo(todo_id: TodoId, repo: RepoDep) -> Todo:
    row = repo.get(todo_id)
    if row is None:
        raise AppError("not_found", f"待办 {todo_id} 不存在", status.HTTP_404_NOT_FOUND)
    return Todo.model_validate(row)


@router.patch("/{todo_id}", response_model=Todo, summary="部分更新")
def update_todo(todo_id: TodoId, payload: TodoUpdate, repo: RepoDep, user: Writer) -> Todo:
    row = repo.update(todo_id, **payload.model_dump(exclude_unset=True))
    if row is None:
        raise AppError("not_found", f"待办 {todo_id} 不存在", status.HTTP_404_NOT_FOUND)
    return Todo.model_validate(row)


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除")
def delete_todo(todo_id: TodoId, repo: RepoDep, user: Writer) -> Response:
    if not repo.delete(todo_id):
        raise AppError("not_found", f"待办 {todo_id} 不存在", status.HTTP_404_NOT_FOUND)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ============================================================
# 事务演示：写一半再抛错，验证 rollback
# ============================================================
@router.post("/_tx", include_in_schema=False)
def transaction_demo(repo: RepoDep, user: Writer) -> None:
    """【要点】插入后抛 `AppError`，依赖里的 `except` 会 rollback"""
    repo.create("这条不该留在库里", Priority.low)
    raise AppError("tx_demo", "事务演示：插入后故意失败", status.HTTP_409_CONFLICT)