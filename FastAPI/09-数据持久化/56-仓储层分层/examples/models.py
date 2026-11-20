"""第 56 章 · 领域模型与领域异常（不依赖 FastAPI）。"""

from pydantic import BaseModel, Field


class Item(BaseModel):
    id: int
    name: str
    price: int


class ItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    price: int = Field(ge=0)


class DuplicateItemError(Exception):
    """【作用】领域异常：名称重复是业务规则，不是 HTTP 概念

    【要点】service 只抛它，由 router 层统一翻译成 409
    """

    def __init__(self, name: str) -> None:
        super().__init__(name)
        self.name = name


class ItemNotFoundError(Exception):
    """找不到资源"""

    def __init__(self, item_id: int) -> None:
        super().__init__(str(item_id))
        self.item_id = item_id