"""第 65 章 · 共享数据模型。

【要点】模型单独一层，避免 `users.py` 反向 import `items.py` 造成循环依赖。
"""

from pydantic import BaseModel, Field


class User(BaseModel):
    id: int
    name: str = Field(min_length=1, max_length=50)


class Item(BaseModel):
    id: int
    name: str
    price: int = Field(ge=0)


class AdminStats(BaseModel):
    users: int
    items: int