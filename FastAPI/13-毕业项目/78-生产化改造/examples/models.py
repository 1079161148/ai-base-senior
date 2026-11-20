"""数据契约（与第 77 章一致，新增同构的 `Page` 泛型用法）。"""

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field


class Priority(StrEnum):
    low = "low"
    medium = "medium"
    high = "high"


class TodoCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    priority: Priority = Priority.medium


class TodoUpdate(BaseModel):
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