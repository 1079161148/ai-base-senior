"""数据契约：请求体、响应体、分页信封。

【要点】请求模型与响应模型分开写，不要用同一个类：
        客户端能传 `done` 不等于客户端能传 `id` / `created_at`。
"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Priority(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120, description="标题，1~120 字")
    priority: Priority = Field(default=Priority.medium, description="优先级")


class TodoUpdate(BaseModel):
    """【要点】全部可选 = 部分更新语义；未传的字段保持原值"""

    title: str | None = Field(default=None, min_length=1, max_length=120)
    done: bool | None = None
    priority: Priority | None = None


class Todo(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    done: bool
    priority: Priority
    created_at: datetime


class Page[T](BaseModel):
    """【作用】分页信封：客户端永远知道自己在第几页、共几页"""

    items: list[T]
    total: int
    page: int
    size: int
    pages: int


class Stats(BaseModel):
    total: int
    done: int
    pending: int
    by_priority: dict[str, int]