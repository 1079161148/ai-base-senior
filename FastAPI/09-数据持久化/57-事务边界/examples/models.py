"""第 57 章 · 领域模型与领域异常。"""

from pydantic import BaseModel, Field


class Item(BaseModel):
    id: int
    name: str
    price: int


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    price: int = Field(ge=0)


class DuplicateItemError(Exception):
    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class ItemNotFoundError(Exception):
    def __init__(self, item_id: int) -> None:
        super().__init__(str(item_id))
        self.item_id = item_id