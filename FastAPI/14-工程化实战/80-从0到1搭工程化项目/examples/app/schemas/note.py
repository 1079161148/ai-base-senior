"""积木 5 · 契约层：只依赖 pydantic，不碰数据库也不碰 HTTP。

【原则】请求模型与响应模型分开，客户端能传的字段永远少于服务端能返回的字段。
"""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class NoteCreate(BaseModel):
    title: str = Field(min_length=1, max_length=120)
    body: str = Field(default="", max_length=2000)


class NoteUpdate(BaseModel):
    """全字段可选 = 部分更新；未传的字段保持原值"""

    title: str | None = Field(default=None, min_length=1, max_length=120)
    body: str | None = Field(default=None, max_length=2000)


class Note(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    body: str
    pinned: bool
    created_at: datetime


class Page[T](BaseModel):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int