"""待办资源路由。

【要点】`/stats` 必须定义在 `/{todo_id}` **之前**，
        否则会被 `/{todo_id}` 抢走，`stats` 当成 `int` 解析 → 422。
"""

from typing import Annotated

from fastapi import APIRouter, HTTPException, Path, Query, Response, status

from models import Page, Priority, Stats, Todo, TodoCreate, TodoUpdate
from security import Writer
from store import store

router = APIRouter(prefix="/todos", tags=["待办"])

TodoId = Annotated[int, Path(ge=1, description="待办 ID")]


@router.get("", response_model=Page[Todo], summary="分页列表")
def list_todos(
    page: Annotated[int, Query(ge=1, description="页码，从 1 开始")] = 1,
    size: Annotated[int, Query(ge=1, le=100, description="每页条数，1~100")] = 10,
    done: Annotated[bool | None, Query(description="按完成状态过滤")] = None,
    priority: Annotated[Priority | None, Query(description="按优先级过滤")] = None,
    q: Annotated[str | None, Query(max_length=50, description="标题关键字（不区分大小写）")] = None,
) -> Page[Todo]:
    rows, total = store.list(page=page, size=size, done=done, priority=priority, q=q)
    pages = (total + size - 1) // size
    return Page[Todo](
        items=[Todo.model_validate(row) for row in rows],
        total=total,
        page=page,
        size=size,
        pages=pages,
    )


# 【要点】静态路径必须在动态路径之前注册
@router.get("/stats", response_model=Stats, summary="统计")
def read_stats() -> Stats:
    return Stats.model_validate(store.stats())


@router.post("", response_model=Todo, status_code=status.HTTP_201_CREATED, summary="新建")
def create_todo(payload: TodoCreate, user: Writer, response: Response) -> Todo:
    row = store.create(payload.title, priority=payload.priority)
    # 【作用】201 应带 Location，客户端据此能直接 GET 到新资源
    response.headers["Location"] = f"/api/v1/todos/{row['id']}"
    return Todo.model_validate(row)


@router.get("/{todo_id}", response_model=Todo, summary="详情")
def read_todo(todo_id: TodoId) -> Todo:
    row = store.get(todo_id)
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": f"待办 {todo_id} 不存在"},
        )
    return Todo.model_validate(row)


@router.patch("/{todo_id}", response_model=Todo, summary="部分更新")
def update_todo(todo_id: TodoId, payload: TodoUpdate, user: Writer) -> Todo:
    row = store.update(todo_id, **payload.model_dump(exclude_unset=True))
    if row is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": f"待办 {todo_id} 不存在"},
        )
    return Todo.model_validate(row)


@router.delete("/{todo_id}", status_code=status.HTTP_204_NO_CONTENT, summary="删除")
def delete_todo(todo_id: TodoId, user: Writer) -> Response:
    if not store.delete(todo_id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "not_found", "message": f"待办 {todo_id} 不存在"},
        )
    return Response(status_code=status.HTTP_204_NO_CONTENT)