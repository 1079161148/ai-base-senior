"""第 57 章 · 服务层：业务规则 + 原子性语义。"""

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
        if self._repository.find_by_name(payload.name) is not None:
            raise DuplicateItemError(payload.name)
        item = self._repository.add(payload.name, payload.price)
        self._repository.add_audit(f"create:{payload.name}")
        return item

    def create_many(self, payloads: list[ItemCreate]) -> list[Item]:
        """【要点】循环里任何一条失败 → 抛异常 → 依赖 rollback → 前面写的也不落库

        这就是「一次请求一个事务」的原子性，不需要手写 savepoint
        """
        return [self.create_item(payload) for payload in payloads]

    def rename_then_fail(self, payload: ItemCreate) -> None:
        """【作用】故意先写后抛，用于验证回滚

        【实测】`RuntimeError` 冒到外层 → `get_db` 捕获 → rollback
        """
        self._repository.add(payload.name, payload.price)
        raise RuntimeError("故意失败")

    def audit_notes(self) -> list[str]:
        """【作用】读同一事务里的第二条写，验证「一个连接 = 一个事务」"""
        return self._repository.audit_notes()