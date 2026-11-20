"""第 56 章 · 服务层：**只有业务规则**，不含 SQL、不含 HTTP。

【判据】这里可以抛领域异常，但不该出现 HTTP 概念，也不该出现查询语句。
"""

from models import DuplicateItemError, Item, ItemCreate, ItemNotFoundError
from repository import ItemRepository


class ItemService:
    def __init__(self, repository: ItemRepository) -> None:
        self._repository = repository

    def list_items(self) -> list[Item]:
        return self._repository.list_all()

    def get_item(self, item_id: int) -> Item:
        item = self._repository.get(item_id)
        if item is None:
            raise ItemNotFoundError(item_id)
        return item

    def create_item(self, payload: ItemCreate) -> Item:
        """【要点】「名称不能重复」是业务规则，放在这里而不是数据库异常里

        【注意】仍然保留数据库唯一索引做最后防线——并发下两个请求可能同时通过
                这里的检查，靠 `IntegrityError` 兜底
        """
        if self._repository.find_by_name(payload.name) is not None:
            raise DuplicateItemError(payload.name)
        return self._repository.add(payload.name, payload.price)

    def delete_item(self, item_id: int) -> None:
        if not self._repository.delete(item_id):
            raise ItemNotFoundError(item_id)

    def count(self) -> int:
        return self._repository.count()